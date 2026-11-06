"""Trusted fleet registration, exact spatial identity and physical load invariants."""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from math import atan2, cos, dist, pi, sin
from typing import TYPE_CHECKING, Final

from . import contracts_v3 as c
from .bundle_registry import ServiceError, validate_world_references
from .contracts_v3_core import ACTIVE_JOB_STATUSES, Contract, Digest, Dimension, FleetKind, FleetMode, Id, Positive, PositiveKg, RunKey
from .motion_admission import validate_binding
from .motion_bindings import AssetBinding, FORM_FAMILIES
from .world_contract import FactoryWorld, parse_world
from .world_geometry import compose_pose, transform_point
from .world_types import Footprint, Owner, Point, Pose, Socket
from .world_trajectory import Arc, Line, Trajectory, fillet_trajectory

if TYPE_CHECKING:
    from .fleet_contracts import FleetContext


def require(condition: bool, detail: str) -> None:
    if not condition:
        raise ServiceError('invalid_contract', detail, 422)


class ProfileRegistration(Contract):
    profile_id: Id
    kind: FleetKind
    mode: FleetMode
    count: Positive
    capacity_kg: PositiveKg
    support_height_m: Dimension


class FleetSpecification(Contract):
    run_id: RunKey
    source_sha256: Digest
    profiles: tuple[ProfileRegistration, ...]


class FleetRegistration(Contract):
    fleet_id: Id
    vehicle_state_id: Id
    profile_id: Id
    home_parking_id: Id
    home_slot_id: Id
    home_node_id: Id
    bay_owner_id: Id
    bay_socket_id: Id
    root_pose: Pose
    capacity_kg: PositiveKg


@dataclass(frozen=True, slots=True)
class FleetBootstrap:
    world_bytes: bytes
    world: FactoryWorld
    fleet: tuple[c.FleetAsset, ...]
    vehicle_states: tuple[c.VehicleState, ...]
    registrations: tuple[FleetRegistration, ...]


_PROFILES: Final = (
    ('truck','truck','road',32,50000,2.), ('slab-carrier','carrier','road',12,50000,2.),
    ('coil-carrier','carrier','road',12,50000,2.), ('forklift','forklift','road',16,25000,2.),
    ('torpedo','torpedo','hot_metal_rail',4,25000,4.), ('ladle-car','ladle','hot_metal_rail',4,25000,4.),
    ('locomotive','locomotive','rail',4,100000,3.), ('railcar','railcar','rail',12,50000,3.),
    ('ship','ship','water',4,100000,15.),
)


def approved_specification(run_id: str, source_sha256: str) -> FleetSpecification:
    """Explicit synthetic capacities and the approved exact 100-position composition."""
    return FleetSpecification.model_validate({'run_id':run_id,'source_sha256':source_sha256,'profiles':[dict(profile_id=p,kind=k,mode=m,count=n,capacity_kg=kg,support_height_m=h) for p,k,m,n,kg,h in _PROFILES]})


def derive_fleet(source: bytes, specification: FleetSpecification) -> FleetBootstrap:
    """Create a new world; preserve all original owner and footprint records."""
    specification = FleetSpecification.model_validate(specification.model_dump())
    require(sha256(source).hexdigest() == specification.source_sha256, 'source world hash differs')
    require(specification.profiles == approved_specification(specification.run_id,specification.source_sha256).profiles,'fleet specification differs from approved composition')
    world = parse_world(source)
    require(world.spatial is not None, 'fleet requires admitted spatial profiles')
    spatial = world.spatial
    if spatial is None:
        raise ServiceError('unsupported_bundle', 'spatial profiles missing', 422)
    specs = {row.profile_id:row for row in specification.profiles}
    require(len(specs) == len(specification.profiles) and sum(row.count for row in specs.values()) == 100, 'fleet specification composition')
    profiles = {row.id:row for row in spatial.profiles}
    slots = {row.id:row for row in world.slots}; nodes = {row.id:row for row in world.nodes}; owners = {row.id:row for row in world.owners}
    counts = {key:sum(row.profile_id == key for row in spatial.parking) for key in specs}
    require(len(spatial.parking) == 100 and counts == {key:row.count for key,row in specs.items()}, 'parking composition differs')
    fleets: list[c.FleetAsset] = []; states: list[c.VehicleState] = []; registrations: list[FleetRegistration] = []
    added_owners: list[Owner] = []; added_footprints: list[Footprint] = []
    for profile_id, spec in specs.items():
        profile = profiles.get(profile_id)
        require(profile is not None, 'missing fleet profile')
        if profile is None:
            raise ServiceError('unsupported_bundle', profile_id, 422)
        for ordinal, parking in enumerate(sorted((p for p in spatial.parking if p.profile_id == profile_id), key=lambda p:p.id), 1):
            require(parking.capacity_positions == 1, 'parking must hold exactly one fleet asset')
            slot = slots[parking.slot_id]; bay = owners[slot.owner_id]; node = nodes[slot.node_id]
            require(bay.kind == 'equipment' and profile.mode in node.modes, 'parking owner or mode differs')
            socket = next(s for s in bay.sockets if s.id == slot.socket_id)
            require(dist(compose_pose(socket.pose,bay.pose).position,node.position) <= .01 and abs(node.position[1]-spec.support_height_m) <= .01, 'parking support contact differs')
            fleet_id = ('RAW-SHIP' if ordinal == 1 else 'SHIP') if profile_id == 'ship' and ordinal <= 2 else f'fleet:{profile_id}:{ordinal:02d}'
            state_id = 'state:' + fleet_id
            pose = Pose(position=(node.position[0],node.position[1]-spec.support_height_m,node.position[2]),yaw_rad=bay.pose.yaw_rad)
            load_socket = 'hold' if profile_id == 'ship' else 'load'
            if fleet_id in owners:
                existing = owners[fleet_id]
                require(profile_id == 'ship' and existing.kind == 'ship' and any(s.id == load_socket and s.pose.position == (0.,spec.support_height_m,0.) for s in existing.sockets), 'existing fleet owner differs')
            else:
                kind = 'ship' if spec.kind == 'ship' else 'railcar' if spec.kind == 'railcar' else 'vehicle'
                added_owners.append(Owner.model_validate({'id':fleet_id,'kind':kind,'pose':pose,'sockets':(Socket.model_validate({'id':load_socket,'pose':Pose(position=(0.,spec.support_height_m,0.),yaw_rad=0.)}),),'modes':(profile.mode,)}))
                center = transform_point(profile.body_offset_m,Pose(position=node.position,yaw_rad=pose.yaw_rad))
                added_footprints.append(Footprint.model_validate({'id':'footprint:'+fleet_id,'owner_id':fleet_id,'pose':Pose(position=center,yaw_rad=pose.yaw_rad),'size_m':profile.size_m}))
            fleets.append(c.FleetAsset.model_validate({'run_id':specification.run_id,'id':fleet_id,'kind':spec.kind,'variant':profile_id,'capacity_kg':spec.capacity_kg,'length_m':profile.size_m[0],'load_envelope_m':profile.load_size_m,'turn_radius_m':profile.min_turn_radius_m,'mode':spec.mode,'load_socket_id':load_socket}))
            states.append(c.VehicleState.model_validate({'run_id':specification.run_id,'id':state_id,'fleet_id':fleet_id,'status':'IDLE','node_id':node.id,'position_m':pose.position,'yaw_rad':pose.yaw_rad,'current_job_id':None,'available_at_ms':0}))
            registrations.append(FleetRegistration.model_validate({'fleet_id':fleet_id,'vehicle_state_id':state_id,'profile_id':profile_id,'home_parking_id':parking.id,'home_slot_id':slot.id,'home_node_id':node.id,'bay_owner_id':bay.id,'bay_socket_id':slot.socket_id,'root_pose':pose,'capacity_kg':spec.capacity_kg}))
    raw = json.dumps({**world.model_dump(mode='json'),'owners':[row.model_dump(mode='json') for row in (*world.owners,*added_owners)],'footprints':[row.model_dump(mode='json') for row in (*world.footprints,*added_footprints)]},sort_keys=True,indent=2).encode()
    derived = parse_world(raw)
    result = FleetBootstrap(raw,derived,tuple(fleets),tuple(states),tuple(registrations))
    validate_world_references(c.FactoryCollections(fleet=result.fleet,vehicle_states=result.vehicle_states),derived)
    validate_initial_geometry(result)
    return result


def _intersects(a: Footprint, b: Footprint) -> bool:
    if min(a.pose.position[1]+a.size_m[1]/2,b.pose.position[1]+b.size_m[1]/2)-max(a.pose.position[1]-a.size_m[1]/2,b.pose.position[1]-b.size_m[1]/2) <= 1e-9:
        return False
    def axes(yaw: float) -> tuple[tuple[float,float],tuple[float,float]]:
        return ((cos(yaw),-sin(yaw)),(sin(yaw),cos(yaw)))
    aa,bb = axes(a.pose.yaw_rad),axes(b.pose.yaw_rad)
    delta = (b.pose.position[0]-a.pose.position[0],b.pose.position[2]-a.pose.position[2])
    for axis in (*aa,*bb):
        ra = sum(a.size_m[k]*abs(axis[0]*aa[i][0]+axis[1]*aa[i][1])/2 for i,k in enumerate((0,2)))
        rb = sum(b.size_m[k]*abs(axis[0]*bb[i][0]+axis[1]*bb[i][1])/2 for i,k in enumerate((0,2)))
        if abs(delta[0]*axis[0]+delta[1]*axis[1]) >= ra+rb-1e-9:
            return False
    return True


def validate_initial_geometry(bootstrap: FleetBootstrap) -> None:
    """Allow support-plane contact while rejecting actual body/load penetration."""
    world = bootstrap.world
    if world.spatial is None:
        raise ServiceError('unsupported_bundle','fleet spatial profiles missing',422)
    profiles = {row.id:row for row in world.spatial.profiles}; owners = {row.id:row for row in world.owners}
    fixed = tuple(row for row in world.footprints if owners[row.owner_id].kind not in {'vehicle','railcar','ship'})
    occupied: list[tuple[Footprint,...]] = []
    for fleet,vehicle in zip(bootstrap.fleet,bootstrap.vehicle_states,strict=True):
        profile = profiles[fleet.variant]
        socket = next(s for s in owners[fleet.id].sockets if s.id == fleet.load_socket_id)
        support = compose_pose(socket.pose,Pose(position=vehicle.position_m,yaw_rad=vehicle.yaw_rad))
        boxes = tuple(Footprint.model_validate({'id':fleet.id+':'+kind,'owner_id':fleet.id,'pose':Pose(position=transform_point(offset,support),yaw_rad=vehicle.yaw_rad),'size_m':size}) for kind,offset,size in (('body',profile.body_offset_m,profile.size_m),('load',profile.load_offset_m,profile.load_size_m)))
        for box in boxes:
            require(all(not _intersects(box,other) for other in fixed), 'initial fleet penetrates fixed geometry: '+box.id)
            require(all(not _intersects(box,other) for group in occupied for other in group), 'initial fleet envelopes overlap: '+box.id)
        occupied.append(boxes)


def validate_load(state: c.FactorySnapshot, fleet: c.FleetAsset, binding: AssetBinding) -> None:
    """Validate every actual socket load, including total kg and physical envelope."""
    require(fleet.kind != 'locomotive','locomotive cannot carry direct cargo')
    require(binding.owner_id == fleet.id,'load binding owner differs')
    socket = next((row for row in binding.sockets if row.socket_id == fleet.load_socket_id),None)
    require(socket is not None,'load binding socket missing')
    if socket is None:
        return
    loaded = [a.material_id for a in state.attachments if a.owner_id == fleet.id and a.socket_id == fleet.load_socket_id and a.released_at_ms is None]
    materials = [m for m in state.materials if m.id in loaded]
    require(sum(m.weight_kg for m in materials) <= fleet.capacity_kg,'fleet load exceeds capacity')
    for material in materials:
        require(socket.family in FORM_FAMILIES[material.form],'fleet load form differs from binding')
        require(fleet.kind != 'torpedo' or material.form == 'HOT_METAL','torpedo requires hot metal')
        require(fleet.kind != 'ladle' or material.form == 'LIQUID_STEEL','ladle requires liquid steel')
        require(fleet.variant != 'slab-carrier' or socket.family == 'SLAB','slab carrier requires slab family')
        require(fleet.variant != 'coil-carrier' or socket.family == 'COIL','coil carrier requires coil family')
        dimensions = material.dimensions
        shape = (dimensions.width_mm,dimensions.diameter_mm,dimensions.diameter_mm) if socket.family in {'COIL','WIRE_COIL'} else (dimensions.length_mm,dimensions.thickness_mm,dimensions.width_mm)
        require(all(value is not None for value in shape),'physical load dimensions missing')
        require(all(value is not None and value/1000 <= bound for value,bound in zip(shape,fleet.load_envelope_m,strict=True)),'physical load envelope exceeds fleet')


def validate_fleet_state(context: FleetContext) -> None:
    """New writer invariants do not retroactively tighten unrelated old archives."""
    state,initial,world = context.state,context.initial,context.world
    require({f.id:f.model_dump(exclude={'run_id'}) for f in state.fleet} == {f.id:f.model_dump(exclude={'run_id'}) for f in initial.fleet},'registered fleet identities and capacities are immutable')
    require({(v.id,v.fleet_id) for v in state.vehicle_states} == {(v.id,v.fleet_id) for v in initial.vehicle_states},'registered vehicle states are retained')
    require(len(state.vehicle_states) == len(state.fleet),'one vehicle state per registered fleet')
    jobs = {row.id:row for row in state.transport_jobs}
    for vehicle in state.vehicle_states:
        if vehicle.status == 'IDLE':
            require(vehicle.current_job_id is None,'idle vehicle points to a job')
        else:
            job = jobs.get(vehicle.current_job_id)
            require(job is not None and job.fleet_id == vehicle.fleet_id and job.status == vehicle.status,'active vehicle/job state differs')
    for job in state.transport_jobs:
        if job.fleet_id is not None and job.status in ACTIVE_JOB_STATUSES:
            require(any(v.fleet_id == job.fleet_id and v.current_job_id == job.id and v.status == job.status for v in state.vehicle_states),'active job lacks its vehicle')
    require(all(sum(a.material_id == m.id and a.released_at_ms is None for a in state.attachments) == 1 for m in state.materials if m.active),'active material needs exactly one current attachment')
    validate_world_references(state,world)
    require(world.spatial is not None,'fleet profiles missing')
    if world.spatial is not None:
        profiles = {p.id:p for p in world.spatial.profiles}
        for fleet in state.fleet:
            profile = profiles.get(fleet.variant)
            require(profile is not None and fleet.length_m == profile.size_m[0] and fleet.load_envelope_m == profile.load_size_m and fleet.turn_radius_m == profile.min_turn_radius_m,'registered fleet geometry differs from pinned profile')


def _at_distance(path: Trajectory, distance: float) -> tuple[Point,float]:
    remaining = min(path.length,max(0.,distance))
    for index,part in enumerate(path.primitives):
        if remaining <= part.length + 1e-9 or index == len(path.primitives)-1:
            fraction = min(1.,max(0.,remaining / part.length))
            match part:
                case Line():
                    point = tuple(a+(b-a)*fraction for a,b in zip(part.start,part.end,strict=True))
                    return point,atan2(-(part.end[2]-part.start[2]),part.end[0]-part.start[0])
                case Arc():
                    point = part.at(fraction)
                    angle = atan2(point[2]-part.center[2],point[0]-part.center[0])
                    return point,-angle-(pi/2 if part.angle > 0 else -pi/2)
        remaining -= part.length
    raise ServiceError('invalid_contract','empty movement trajectory',422)


def _distance_of(path: Trajectory, point: Point) -> float:
    prefix = 0.
    for part in path.primitives:
        match part:
            case Line():
                delta = tuple(b-a for a,b in zip(part.start,part.end,strict=True))
                t = sum((p-a)*d for p,a,d in zip(point,part.start,delta,strict=True))/(part.length**2)
                projected = tuple(a+min(1.,max(0.,t))*d for a,d in zip(part.start,delta,strict=True))
                if -.000001 <= t <= 1.000001 and dist(projected,point) <= .01:
                    return prefix+min(1.,max(0.,t))*part.length
            case Arc():
                start = atan2(part.start[2]-part.center[2],part.start[0]-part.center[0])
                angle = atan2(point[2]-part.center[2],point[0]-part.center[0])-start
                angle = (angle+pi)%(2*pi)-pi
                t = angle/part.angle
                if -.000001 <= t <= 1.000001 and dist(part.at(min(1.,max(0.,t))),point) <= .01:
                    return prefix+min(1.,max(0.,t))*part.length
        prefix += part.length
    raise ServiceError('invalid_contract','movement observation leaves approved graph trajectory',422)


def movement_pose(world: FactoryWorld, fleet: c.FleetAsset, observation: tuple[c.MovementSegment,int]) -> Pose:
    """Project an admitted phase interval along its actual analytic graph trajectory."""
    row,at_ms = observation
    if world.spatial is None:
        raise ServiceError('unsupported_bundle','movement profile missing',422)
    profile = next((p for p in world.spatial.profiles if p.id == fleet.variant),None)
    if profile is None:
        raise ServiceError('unsupported_bundle','fleet movement profile missing',422)
    segment = next((s for s in world.segments if s.id == row.segment_id),None)
    if segment is None:
        raise ServiceError('not_found',row.segment_id,404)
    require(segment.mode == profile.mode,'movement segment mode differs')
    policy = next((p for p in world.spatial.segment_policies if p.segment_id == segment.id),None)
    if policy is None or any(key not in {b.id for b in world.spatial.rail_blocks} for key in policy.rail_block_ids):
        raise ServiceError('unsupported_bundle','movement segment policy or rail block missing',422)
    require(profile.id in policy.profile_ids,'fleet profile is not allowed on movement segment')
    owner = next(o for o in world.owners if o.id == fleet.id)
    socket = next(s for s in owner.sockets if s.id == fleet.load_socket_id)
    require(socket.pose.position[0] == socket.pose.position[2] == 0.,'fleet support offset requires approved trajectory adapter')
    height = socket.pose.position[1]
    path = fillet_trajectory(segment.points,profile.min_turn_radius_m)
    start_support = (row.from_position_m[0],row.from_position_m[1]+height,row.from_position_m[2])
    begin = _distance_of(path,start_support)
    require(dist((row.to_position_m[0],row.to_position_m[1]+height,row.to_position_m[2]),segment.points[-1]) <= .01,'movement endpoint differs from graph')
    fraction = min(1.,max(0.,(at_ms-row.start_ms)/(row.end_ms-row.start_ms)))
    point,yaw = _at_distance(path,begin+(path.length-begin)*fraction)
    return Pose(position=(point[0],point[1]-height,point[2]),yaw_rad=yaw)


def movement_heading_offset(world: FactoryWorld, fleet: c.FleetAsset, observation: tuple[c.MovementSegment,float]) -> float:
    """Recover the admitted body-heading branch without changing path direction."""
    row,yaw = observation
    tangent = movement_pose(world,fleet,(row,row.start_ms)).yaw_rad
    difference = abs((yaw-tangent+pi)%(2*pi)-pi)
    if difference <= .000001:
        return 0.
    require(world.spatial is not None,'movement spatial profile missing')
    profile = next(p for p in world.spatial.profiles if p.id == fleet.variant)
    policy = next(p for p in world.spatial.segment_policies if p.segment_id == row.segment_id)
    blocks = {b.id:b for b in world.spatial.rail_blocks}
    require(abs(pi-difference) <= .000001 and profile.reverse_allowed,'movement body heading is not permitted by profile')
    require(all(key in blocks and blocks[key].reverse_allowed for key in policy.rail_block_ids),'movement reverse heading is not permitted by rail block')
    return pi
