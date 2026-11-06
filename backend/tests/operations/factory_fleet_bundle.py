"""Owned T11 full-world fixtures and actual typed motion binding observations."""
from __future__ import annotations

from pathlib import Path
from dataclasses import dataclass
from collections import deque
from math import atan2, pi

from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.operations import contracts_v3 as c
from app.operations.motion_bindings import AssetBinding
from app.operations.motion_policy import load_policies
from app.operations.world_contract import FactoryWorld
from app.operations.bundle_registry import ContractTestBundle

WORLD_SHA = 'd2b9ab5afdb064f4f22da193c806ded0af43a2110f815d2ac4b9213b6411562b'


def fleet_binding(world: FactoryWorld, fleet: c.FleetAsset, family: str = 'COIL') -> AssetBinding:
    """Admit real graph sockets against all mechanics named by the reviewed policy."""
    owner = next(row for row in world.owners if row.id == fleet.id)
    policy_id = 'policy:equipment:ship' if fleet.id == 'SHIP' else 'policy:fleet:'+fleet.variant
    policy = next(row for row in load_policies().policies if row.id == policy_id)
    functions = tuple({'function_id':name,'node_id':name,'kind':'state' if name in policy.state_bound_fixed_functions else 'rotation','axis':(0.,1.,0.),'pivot_m':(0.,0.,0.),'min_value':-1.,'max_value':1.} for name in (*policy.required_functions,*policy.state_bound_fixed_functions))
    socket = next(row for row in owner.sockets if row.id == fleet.load_socket_id)
    return AssetBinding.model_validate({'owner_id':owner.id,'policy_id':policy_id,'sockets':({'socket_id':socket.id,'family':family,'position_m':socket.pose.position,'orientation_xyzw':(0.,0.,0.,1.),'motion_function_ids':()},),'functions':functions})


def stationary_binding(world: FactoryWorld, location_id: str, family: str = 'COIL') -> AssetBinding:
    location = next(row for row in (*world.slots,*world.ports) if row.id == location_id)
    owner = next(row for row in world.owners if row.id == location.owner_id)
    socket = next(row for row in owner.sockets if row.id == location.socket_id)
    return AssetBinding.model_validate({'owner_id':owner.id,'policy_id':'policy:equipment:stock','sockets':({'socket_id':socket.id,'family':family,'position_m':socket.pose.position,'orientation_xyzw':(0.,0.,0.,1.),'motion_function_ids':()},),'functions':()})


@dataclass(slots=True)
class Scenario:
    """Mutable test driver retains the latest immutable persisted snapshot."""
    engine: Engine
    bundle: ContractTestBundle
    state: c.FactorySnapshot
    phase_movements: tuple[c.MovementSegment,...] = ()
    phase_heading_offset: float = 0.

    @property
    def world(self) -> FactoryWorld:
        return self.bundle.verified.world

    @property
    def fleet(self) -> c.FleetAsset:
        return next(f for f in self.state.fleet if f.id == 'fleet:truck:01')

    @property
    def vehicle(self) -> c.VehicleState:
        return next(v for v in self.state.vehicle_states if v.fleet_id == self.fleet.id)


def scenario(engine: Engine, bundle: ContractTestBundle) -> Scenario:
    from app.operations import service_v3 as service
    with Session(engine) as session,session.begin():
        state = service.initialize_once(session,test_bundle=bundle)
    return Scenario(engine,bundle,state)


def refresh(case: Scenario) -> None:
    from app.operations import service_v3 as service
    with Session(case.engine) as session:
        case.state = service.load_snapshot(session)


def send(case: Scenario, payload: dict) -> c.CommandResult:
    from app.operations import service_v3 as service
    from app.operations.fleet_contracts import COMMAND
    command = COMMAND.validate_python({'run_id':case.state.run.id,'expected_revision':case.state.run.revision,**payload})
    with Session(case.engine) as session,session.begin():
        result = service.apply_fleet_transition(session,command)
    refresh(case)
    return result


def advance(case: Scenario, target: int) -> None:
    from app.operations import service_v3 as service
    difference = target-case.state.run.elapsed_ms
    assert difference >= 0 and difference%1000 == 0
    while difference:
        steps = min(48,difference//1000)
        with Session(case.engine) as session,session.begin():
            service.apply_command(session,c.FactoryCommand.model_validate({'action':'step','run_id':case.state.run.id,'expected_revision':case.state.run.revision,'command_id':'clock:'+str(case.state.run.revision),'steps':steps}))
        refresh(case)
        difference = target-case.state.run.elapsed_ms


def observed_vehicle(case: Scenario) -> dict:
    """Independent graph endpoint observation, rather than the product pose helper."""
    vehicle = case.vehicle
    position,yaw,node = vehicle.position_m,vehicle.yaw_rad,vehicle.node_id
    job = next((j for j in case.state.transport_jobs if j.id == vehicle.current_job_id),None)
    if job is not None and job.status != 'BLOCKED':
        rows = [m for m in case.phase_movements if m.job_id == job.id and m.end_ms == case.state.run.elapsed_ms]
        if rows:
            movement = max(rows,key=lambda m:m.ordinal)
            segment = next(s for s in case.world.segments if s.id == movement.segment_id)
            a,b = segment.points[-2:]
            position = movement.to_position_m
            yaw = atan2(-(b[2]-a[2]),b[0]-a[0])+case.phase_heading_offset; node = segment.to_node_id
    return {'node_id':node,'pose':{'position':position,'yaw_rad':yaw}}


def route_observations(case: Scenario, target: str) -> tuple[list[dict],int]:
    """Test-only graph traversal supplies observations; product kernel has no dispatcher."""
    observation = observed_vehicle(case)
    source = observation['node_id']; world = case.world
    allowed = {p.segment_id for p in world.spatial.segment_policies if case.fleet.variant in p.profile_ids}
    queue = deque([(source,[])])
    visited = {source}; selected = None
    while queue:
        node,path = queue.popleft()
        if node == target:
            selected = path; break
        for segment in world.segments:
            if segment.id in allowed and segment.from_node_id == node and segment.to_node_id not in visited:
                visited.add(segment.to_node_id);queue.append((segment.to_node_id,[*path,segment]))
    assert selected is not None,'explicit test observation path must exist'
    owner = next(o for o in world.owners if o.id == case.fleet.id)
    height = next(s.pose.position[1] for s in owner.sockets if s.id == case.fleet.load_socket_id)
    ordinal = max((m.ordinal for m in case.state.movement_segments if m.job_id == case.vehicle.current_job_id),default=-1)+1
    start = case.state.run.elapsed_ms
    result = []
    for i,segment in enumerate(selected):
        result.append({'id':f'movement:{case.vehicle.current_job_id}:{ordinal+i}','ordinal':ordinal+i,'segment_id':segment.id,'start_ms':start+1000*i,'end_ms':start+1000*(i+1),'from_position_m':(segment.points[0][0],segment.points[0][1]-height,segment.points[0][2]),'to_position_m':(segment.points[-1][0],segment.points[-1][1]-height,segment.points[-1][2])})
    return result,start+max(1,len(result))*1000


def receive_coil(case: Scenario) -> str:
    from app.operations import service_v3 as service
    from app.operations.stock_contracts import ReceiptCompletion
    request = ReceiptCompletion.model_validate({'run_id':case.state.run.id,'expected_revision':case.state.run.revision,'source_id':'fleet-receipt','source_kind':'PURCHASED','form':'HR_COIL','grade':'SYNTHETIC-CS','dimensions':{'width_mm':1000.,'thickness_mm':2.,'diameter_mm':1200.,'inner_diameter_mm':600.},'quantity_kg':20000,'measured_kg':20000,'quality_status':'PASSED','destination_id':'v2:p:receipt:HR_COIL:work'})
    with Session(case.engine) as session,session.begin():
        service.record_completed_receipt(session,request)
    refresh(case)
    return case.state.materials[0].id


def assign(case: Scenario, options: dict) -> c.CommandResult:
    now = case.state.run.elapsed_ms
    payload = {'action':'assign_fleet_job','command_id':options.get('command_id','assign:1'),'job_id':options.get('job_id','job:1'),'fleet_id':case.fleet.id,'equipment_id':None,'material_id':options.get('material_id'),'shipment_leg_id':None,'from_node_id':options.get('from_node_id',case.vehicle.node_id),'to_node_id':options.get('to_node_id','v2:n:WAREHOUSE:dock'),'ready_at_ms':now,'phase':{'start_ms':now,'end_ms':now+1000},'movements':(),'reservations':options.get('reservations',()),'bindings':(fleet_binding(case.world,case.fleet),)}
    result = send(case,payload)
    case.phase_movements = ()
    case.phase_heading_offset = 0.
    return result


def transition(case: Scenario, target: str, options: dict | None = None) -> c.CommandResult:
    options = options or {}; job = next(j for j in case.state.transport_jobs if j.id == case.vehicle.current_job_id)
    now = case.state.run.elapsed_ms
    movements,end = route_observations(case,options['move_to']) if 'move_to' in options else (list(options.get('movements',())),options.get('end_ms',now+1000))
    payload = {'action':'transition_fleet_job','command_id':options.get('command_id',f'{job.id}:{target}:{case.state.run.revision}'),'job_id':job.id,'expected_status':job.status,'target_status':target,'phase':None if target in ('COMPLETED','BLOCKED') else {'start_ms':now,'end_ms':end},'vehicle':options.get('vehicle',observed_vehicle(case)),'movements':movements,'reservations':options.get('reservations',()),'release_reservation_ids':options.get('release_reservation_ids',()),'safety':options.get('safety'),'custody':options.get('custody'),'bindings':options.get('bindings',(fleet_binding(case.world,case.fleet),)),'blocked_resource_id':options.get('blocked_resource_id'),'reason':options.get('reason')}
    result = send(case,payload)
    if target != 'BLOCKED':
        case.phase_movements = tuple(c.MovementSegment.model_validate({'run_id':case.state.run.id,'job_id':job.id,**row}) for row in movements)
        if movements:
            segment = next(s for s in case.world.segments if s.id == movements[0]['segment_id'])
            a,b = segment.points[:2]
            tangent = atan2(-(b[2]-a[2]),b[0]-a[0])
            difference = abs((payload['vehicle']['pose']['yaw_rad']-tangent+pi)%(2*pi)-pi)
            case.phase_heading_offset = pi if abs(pi-difference) <= .000001 else 0.
    return result


def custody(case: Scenario, destination: str) -> tuple[dict,tuple[AssetBinding,...]]:
    """Actual graph anchors and reviewed policy channels feed public T58 evaluation."""
    material = case.state.materials[0]
    current = next(a for a in case.state.attachments if a.material_id == material.id and a.released_at_ms is None)
    load = fleet_binding(case.world,case.fleet)
    if destination == case.fleet.id:
        prior = stationary_binding(case.world,current.owner_id)
        binding = load; owner = next(o for o in case.world.owners if o.id == case.fleet.id)
        kind,owner_id,socket_id = owner.kind,owner.id,case.fleet.load_socket_id
        recipe = 'motion:scope:road:travel'; window = 'travel'
    else:
        prior = load; binding = stationary_binding(case.world,destination)
        location = next(p for p in (*case.world.slots,*case.world.ports) if p.id == destination)
        kind,owner_id,socket_id = 'slot',destination,location.socket_id
        recipe = 'motion:scope:internal:idle'; window = 'hold'
    socket = next(s for s in binding.sockets if s.socket_id == socket_id)
    old_socket = next(s for s in prior.sockets if s.socket_id == current.socket_id)
    channels = tuple({'function_id':f.function_id,'node_id':f.node_id,'kind':f.kind,'window_id':window,'axis':f.axis,'pivot_m':f.pivot_m,'start_value':0.,'end_value':0.} for f in binding.functions)
    observation = {'acquired_attachment_id':'attachment:'+str(case.state.run.revision),'kind':kind,'owner_id':owner_id,'socket_id':socket_id,'material':{'material_id':material.id,'material_version_id':material.current_version_id,'form':material.form,'dimensions':material.dimensions,'support_local_mm':(0.,-600.,0.),'orientation_xyzw':(0.,0.,0.,1.)},'anchor':{'owner_id':binding.owner_id,'socket_id':socket_id,'position_m':socket.position_m,'orientation_xyzw':socket.orientation_xyzw},'previous_anchor':{'owner_id':prior.owner_id,'socket_id':current.socket_id,'position_m':old_socket.position_m,'orientation_xyzw':old_socket.orientation_xyzw},'previous_channels':(),'recipe_id':recipe,'channels':channels,'frozen_progress':0.}
    return observation,(load,prior) if prior.owner_id != load.owner_id else (load,binding)


def linear_bundle(original: ContractTestBundle, output: Path, reverse_allowed: bool = True, resource_collision: bool = False) -> ContractTestBundle:
    """Explicit test-only stock station on the real straight home/junction edge."""
    import hashlib
    import json
    from app.operations.bundle_registry import admit_contract_test
    from app.operations.fleet import FleetBootstrap, validate_initial_geometry
    from app.operations.world_contract import parse_world
    raw = original.verified.world.model_dump(mode='json')
    if resource_collision:
        raw['spatial']['parking'][0]['id'] = raw['nodes'][0]['id']
    for profile in raw['spatial']['profiles']:
        if profile['id'] == 'truck':
            profile['reverse_allowed'] = reverse_allowed
    run_id = original.initial_snapshot.run.id
    vehicle = next(v for v in original.initial_snapshot.vehicle_states if v.fleet_id == 'fleet:truck:01')
    source = next(s for s in original.verified.world.slots if s.node_id == vehicle.node_id)
    edge = next(s for s in original.verified.world.segments if s.id == 'road:shared:297:back')
    assert edge.from_node_id == vehicle.node_id and len(edge.points) == 2
    point = edge.points[-1]
    midpoint = [(a+b)/2 for a,b in zip(edge.points[0],edge.points[-1],strict=True)]
    original_node = next(n for n in raw['nodes'] if n['id'] == vehicle.node_id)
    raw['nodes'].append({**original_node,'id':'v2:t11:linear:mid','position':midpoint})
    original_policy = next(p for p in raw['spatial']['segment_policies'] if p['segment_id'] == edge.id)
    stops = {s.id:s.node_id for s in original.verified.world.spatial.stops}
    additions = [('t11:linear:first',edge.from_node_id,'v2:t11:linear:mid',list(edge.points[0]),midpoint),('t11:linear:second','v2:t11:linear:mid',edge.to_node_id,midpoint,list(edge.points[-1]))]
    for identity,source_node,target_node,start,end in additions:
        raw['segments'].append({**edge.model_dump(mode='json'),'id':identity,'from_node_id':source_node,'to_node_id':target_node,'points':[start,end],'conflict_zone_ids':[]})
        raw['spatial']['segment_policies'].append({**original_policy,'id':'policy:'+identity,'segment_id':identity,'stop_ids':[s for s in original_policy['stop_ids'] if stops[s] in {source_node,target_node}]})
    raw['owners'].append({'id':'t11:linear:stock','kind':'equipment','pose':{'position':[point[0],point[1]-2.,point[2]],'yaw_rad':0.},'sockets':[{'id':'stock','pose':{'position':[0.,2.,0.],'yaw_rad':0.}}],'modes':['road']})
    raw['footprints'].append({'id':'footprint:t11:linear:stock','owner_id':'t11:linear:stock','pose':{'position':[point[0],-2.,point[2]],'yaw_rad':0.},'size_m':[10.,4.,10.]})
    raw['ports'].append({'id':'v2:t11:linear:drop','owner_id':'t11:linear:stock','socket_id':'stock','node_id':edge.to_node_id,'capacity_kg':100000,'modes':['road']})
    world_bytes = json.dumps(raw,sort_keys=True,indent=2).encode()
    world = parse_world(world_bytes)
    assert world.owners[:len(original.verified.world.owners)] == original.verified.world.owners
    assert world.footprints[:len(original.verified.world.footprints)] == original.verified.world.footprints
    assert world.nodes[:len(original.verified.world.nodes)] == original.verified.world.nodes
    assert world.segments[:len(original.verified.world.segments)] == original.verified.world.segments
    validate_initial_geometry(FleetBootstrap(world_bytes,world,original.initial_snapshot.fleet,original.initial_snapshot.vehicle_states,()))
    fixture = json.loads((Path(__file__).absolute().parents[3]/'shared/fixtures/factory-contract-test-v3/domain.json').read_text())
    material = {**fixture['materials'][0],'run_id':run_id,'weight_kg':20000}
    version = {**fixture['material_versions'][0],'run_id':run_id,'weight_kg':20000}
    stock = {**fixture['stock_lots'][0],'run_id':run_id,'quantity_kg':20000}
    attachment = {'run_id':run_id,'id':'linear:opening-custody','material_id':material['id'],'kind':'slot','owner_id':source.id,'socket_id':source.socket_id,'acquired_at_ms':0,'released_at_ms':None}
    ledger = {'run_id':run_id,'id':'linear:opening-mass','source_id':'linear:opening-mass','kind':'OPENING_STOCK','quantity_kg':20000,'at_ms':0,'material_id':material['id'],'batch_id':None,'event_id':None}
    domain = c.FactoryCollections.model_validate({**original.verified.collections.model_dump(),'materials':(material,),'material_versions':(version,),'stock_lots':(stock,),'attachments':(attachment,),'mass_ledger':(ledger,)})
    artifacts = {a.descriptor.path:a.content for a in original.verified.artifacts}
    manifest = original.verified.manifest.model_dump(mode='json')
    manifest['bundle_id'] = 'T11-LINEAR-'+hashlib.sha256(world_bytes).hexdigest()[:20]
    for row in manifest['artifacts']:
        if row['role'] == 'world':
            artifacts[row['path']] = world_bytes
        if row['role'] == 'domain':
            artifacts[row['path']] = domain.model_dump_json().encode()
        row['sha256'] = hashlib.sha256(artifacts[row['path']]).hexdigest()
    manifest_bytes = json.dumps(manifest,sort_keys=True,indent=2).encode()
    run = {**original.initial_snapshot.run.model_dump(),'bundle_id':manifest['bundle_id'],'bundle_hash':hashlib.sha256(manifest_bytes).hexdigest()}
    state = c.FactorySnapshot.model_validate({**domain.model_dump(),'run':run})
    result = admit_contract_test(manifest_bytes,artifacts,state)
    output.mkdir(parents=True,exist_ok=False)
    for path,content in artifacts.items():
        (output/path).write_bytes(content)
    (output/'bundle.json').write_bytes(manifest_bytes)
    (output/'domain.json').write_text(state.model_dump_json())
    (output/'fixture-purpose.json').write_text(json.dumps({'purpose':'T11 trusted linear lifecycle; no T15 path generation or canonical activation','original_owners_retained':len(original.verified.world.owners),'test_station_owners_added':1,'source_slot':source.id,'source_node':source.node_id,'destination_port':'v2:t11:linear:drop','destination_node':edge.to_node_id,'forward_edge':'road:shared:297:out','reverse_edge':edge.id,'opening_kg':20000,'added_node':'v2:t11:linear:mid','added_segments':['t11:linear:first','t11:linear:second'],'added_policies':['policy:t11:linear:first','policy:t11:linear:second'],'truck_reverse_allowed':reverse_allowed},indent=2)+'\n')
    return result
