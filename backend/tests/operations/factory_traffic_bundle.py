"""Traffic fixtures retain source geometry and call the product boundary executor."""
from __future__ import annotations

from pathlib import Path
import json

from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.operations import contracts_v3 as c, service_v3 as service
from app.operations.bundle_registry import ContractTestBundle, admit_contract_test
from app.operations.traffic import TrafficIntent
from app.operations.traffic_service import TrafficCommand


def read_fixture(path: Path) -> ContractTestBundle:
    """Load the exact archived manifest; never rebuild silently on restart."""
    manifest=(path/'bundle.json').read_bytes()
    artifacts={a['path']:(path/a['path']).read_bytes() for a in json.loads(manifest)['artifacts']}
    return admit_contract_test(manifest,artifacts,c.FactorySnapshot.model_validate_json((path/'domain.json').read_bytes()))


def execute(engine: Engine, intent: TrafficIntent, target_ms: int, command_id: str) -> c.CommandResult:
    """Only target/chunk construction lives in tests; all business boundaries are product."""
    with Session(engine) as session,session.begin():
        before=service.load_snapshot(session)
        return service.advance_traffic(session,TrafficCommand(run_id=before.run.id,expected_revision=before.run.revision,command_id=command_id,target_ms=target_ms,intents=(intent,)))


def focused_bundle(original: ContractTestBundle, output: Path, placements: tuple[tuple[str,str,float],...]) -> ContractTestBundle:
    """Separately admitted focused initial states; no full100-throughput claim."""
    from hashlib import sha256
    from app.operations.fleet import FleetBootstrap,validate_initial_geometry
    world=original.verified.world; states=[]
    for old in original.initial_snapshot.vehicle_states:
        placement=next((p for p in placements if p[0] == old.fleet_id),None)
        if placement is None: states.append(old); continue
        _,node_id,yaw=placement
        point=next(n.position for n in world.nodes if n.id == node_id)
        fleet=next(f for f in original.initial_snapshot.fleet if f.id == old.fleet_id)
        height=next(s.pose.position[1] for o in world.owners if o.id == fleet.id for s in o.sockets if s.id == fleet.load_socket_id)
        states.append(old.model_copy(update={'node_id':node_id,'position_m':(point[0],point[1]-height,point[2]),'yaw_rad':yaw}))
    validate_initial_geometry(FleetBootstrap(next(a.content for a in original.verified.artifacts if a.descriptor.role == 'world'),world,original.initial_snapshot.fleet,tuple(states),()))
    domain=c.FactoryCollections.model_validate({**original.verified.collections.model_dump(),'vehicle_states':states})
    artifacts={a.descriptor.path:a.content for a in original.verified.artifacts}; manifest=original.verified.manifest.model_dump(mode='json')
    manifest['bundle_id']='T15-FOCUSED-'+sha256(domain.model_dump_json().encode()).hexdigest()[:20]
    for a in manifest['artifacts']:
        if a['role'] == 'domain': artifacts[a['path']]=domain.model_dump_json().encode()
        a['sha256']=sha256(artifacts[a['path']]).hexdigest()
    raw=json.dumps(manifest,sort_keys=True,indent=2).encode()
    initial=c.FactorySnapshot.model_validate({**domain.model_dump(),'run':{**original.initial_snapshot.run.model_dump(),'bundle_id':manifest['bundle_id'],'bundle_hash':sha256(raw).hexdigest()}})
    result=admit_contract_test(raw,artifacts,initial)
    output.mkdir(parents=True,exist_ok=False)
    for name,content in artifacts.items(): (output/name).write_bytes(content)
    (output/'bundle.json').write_bytes(raw);(output/'domain.json').write_text(initial.model_dump_json())
    (output/'focused-initial.json').write_text(json.dumps({'kind':'separate focused admitted initial fixture','placements':placements,'retained_original_owner_records':631,'full100_throughput':False},indent=2))
    return result


def assign_intents(engine: Engine, bundle: ContractTestBundle, requests: tuple[tuple[str,str,str],...]) -> tuple[TrafficIntent,...]:
    """T16 selection is explicit fixture input; no scheduling policy is duplicated."""
    from app.operations.fleet_contracts import AssignFleetJob
    from factory_fleet_bundle import fleet_binding
    with Session(engine) as session,session.begin():
        service.initialize_once(session,test_bundle=bundle)
        intents=[]
        for job_id,fleet_id,target in requests:
            state=service.load_snapshot(session);fleet=next(f for f in state.fleet if f.id == fleet_id);vehicle=next(v for v in state.vehicle_states if v.fleet_id == fleet_id)
            bindings=(fleet_binding(bundle.verified.world,fleet),)
            service.apply_fleet_transition(session,AssignFleetJob.model_validate({'action':'assign_fleet_job','run_id':state.run.id,'expected_revision':state.run.revision,'command_id':'fixture:assign:'+job_id,'job_id':job_id,'fleet_id':fleet_id,'equipment_id':None,'material_id':None,'shipment_leg_id':None,'from_node_id':target,'to_node_id':vehicle.node_id,'ready_at_ms':0,'phase':{'start_ms':0,'end_ms':1000},'movements':(),'reservations':(),'bindings':bindings}))
            intents.append(TrafficIntent(job_id,'EMPTY_APPROACH',0,3_600_000,bindings))
        return tuple(intents)


def execute_many(engine: Engine, intents: tuple[TrafficIntent,...], target_ms: int, command_id: str) -> c.CommandResult:
    with Session(engine) as session,session.begin():
        before=service.load_snapshot(session)
        return service.advance_traffic(session,TrafficCommand(run_id=before.run.id,expected_revision=before.run.revision,command_id=command_id,target_ms=target_ms,intents=intents))


from dataclasses import dataclass



def cargo_bundle(original: ContractTestBundle, output: Path, weight_kg: int = 20000) -> ContractTestBundle:
    """Explicit real opening stock at the truck's actual load-source support slot."""
    from hashlib import sha256
    import json
    from app.operations import contracts_v3 as c
    from app.operations.bundle_registry import admit_contract_test
    root=Path(__file__).absolute().parents[3]
    fixture=json.loads((root/'shared/fixtures/factory-contract-test-v3/domain.json').read_bytes())
    run_id=original.initial_snapshot.run.id
    material={**fixture['materials'][0],'run_id':run_id,'weight_kg':weight_kg}
    version={**fixture['material_versions'][0],'run_id':run_id,'weight_kg':weight_kg}
    stock={**fixture['stock_lots'][0],'run_id':run_id,'quantity_kg':weight_kg}
    vehicle=next(v for v in original.initial_snapshot.vehicle_states if v.fleet_id=='fleet:truck:01')
    slot=next(s for s in original.verified.world.slots if s.node_id==vehicle.node_id)
    attachment={'run_id':run_id,'id':'traffic:opening:custody','material_id':material['id'],'kind':'slot','owner_id':slot.id,'socket_id':slot.socket_id,'acquired_at_ms':0,'released_at_ms':None}
    ledger={'run_id':run_id,'id':'traffic:opening:mass','source_id':'traffic:opening:mass','kind':'OPENING_STOCK','quantity_kg':weight_kg,'at_ms':0,'material_id':material['id'],'batch_id':None,'event_id':None}
    domain=c.FactoryCollections.model_validate({**original.verified.collections.model_dump(),'materials':(material,),'material_versions':(version,),'stock_lots':(stock,),'attachments':(attachment,),'mass_ledger':(ledger,)})
    artifacts={a.descriptor.path:a.content for a in original.verified.artifacts};manifest=original.verified.manifest.model_dump(mode='json')
    manifest['bundle_id']='T15-CARGO-'+sha256(domain.model_dump_json().encode()).hexdigest()[:20]
    for a in manifest['artifacts']:
        if a['role']=='domain': artifacts[a['path']]=domain.model_dump_json().encode()
        a['sha256']=sha256(artifacts[a['path']]).hexdigest()
    raw=json.dumps(manifest,sort_keys=True,indent=2).encode()
    initial=c.FactorySnapshot.model_validate({**domain.model_dump(),'run':{**original.initial_snapshot.run.model_dump(),'bundle_id':manifest['bundle_id'],'bundle_hash':sha256(raw).hexdigest()}})
    result=admit_contract_test(raw,artifacts,initial)
    output.mkdir(parents=True,exist_ok=False)
    for name,content in artifacts.items(): (output/name).write_bytes(content)
    (output/'bundle.json').write_bytes(raw);(output/'domain.json').write_text(initial.model_dump_json())
    return result


@dataclass(frozen=True,slots=True)
class NormalizedTraffic:
    content: str
    mapping_json: str
    raw_json: str


def normalize_traffic(engine: Engine, intents: tuple[TrafficIntent,...], baseline_sequence: int = 0) -> NormalizedTraffic:
    """Verify exact SQL/child-receipt origin before normalizing opaque event IDs."""
    from hashlib import sha256
    import json
    from sqlalchemy import select
    from app.operations import models_v3 as rows
    from app.operations.traffic_service import _semantic_id
    with Session(engine) as session:
        state=service.load_snapshot(session)
        receipts=tuple(session.scalars(select(rows.CommandReceipt).where(rows.CommandReceipt.run_id==state.run.id)))
    events=[];mapping=[];raw=[];event_map={};source_map={}
    by_job={i.job_id:i for i in intents}
    for event in state.events:
        if event.sequence<=baseline_sequence or event.entity_type=='run': continue
        candidates=[]
        for receipt in receipts:
            token=sha256((receipt.command_id+':'+str(event.sequence)).encode()).hexdigest()
            if event.id!='fleet:event:'+token or event.source_id!='fleet:source:'+token: continue
            reply=c.CommandResult.model_validate(receipt.reply_json); delta=reply.delta
            assert delta is not None
            emitted=delta.upserts.events
            assert list(e.sequence for e in emitted)==sorted(e.sequence for e in emitted)
            matches=[index for index,e in enumerate(emitted) if e.id==event.id]
            assert len(matches)==1 and emitted[matches[0]]==event
            job=next((j for j in delta.upserts.transport_jobs if j.id==event.payload.job_id),None)
            if job is not None:
                cause=next(e for e in emitted if e.event_type.startswith('JOB_'))
                assert cause.payload.reason is not None and cause.payload.reason.startswith('traffic:')
                expected=_semantic_id(by_job[job.id],event.at_ms,job.status+':'+cause.payload.reason)
                annotation=_semantic_id(by_job[job.id],event.at_ms,'terminal_annotation:'+cause.payload.reason.removeprefix('traffic:terminal:'))
                if receipt.command_id == annotation:
                    from app.operations.traffic_service import _annotation_origin,_context
                    with Session(engine) as proof_session:
                        request=_annotation_origin(proof_session,_context(proof_session,state),by_job[job.id],intents,event)
                    assert request.command_id == annotation
                    expected=annotation

            else:
                group=tuple(r.id for r in delta.upserts.reservations)
                assert all(e.event_type=='RESERVATION_RELEASED' and e.payload.reason=='traffic:interval_end' for e in emitted)
                expected=_semantic_id(by_job[event.payload.job_id],event.at_ms,'release:'+':'.join(sorted(group)))
            assert receipt.command_id==expected
            candidates.append((receipt.command_id,matches[0],token,receipt.payload_digest))
        assert len(candidates)==1, ('missing/ambiguous generating child',event.id)
        command_id,ordinal,token,digest=candidates[0]
        stable='traffic:event:'+command_id+':'+str(ordinal)
        source='traffic:source:'+command_id+':'+str(ordinal)
        assert stable not in event_map.values() and source not in source_map.values()
        event_map[event.id]=stable;source_map[event.source_id]=source
        raw.append(event.model_dump(mode='json'))
        item=event.model_dump(mode='json');item.update({'run_id':'RUN','id':stable,'source_id':source,'sequence':len(events)+1})
        events.append(item)
        mapping.append({'raw_event_id':event.id,'raw_source_id':event.source_id,'stable_event_id':stable,'stable_source_id':source,'command_id':command_id,'local_ordinal':ordinal,'raw_sequence':event.sequence,'proved_hash':token,'payload_digest':digest})
    from app.operations.contracts_v3_validation import collections
    payload={'events':events}
    for name,records in collections(state).items():
        if name=='events': continue
        normalized=[]
        for record in records:
            item=record.model_dump(mode='json',exclude={'run_id'})
            if item.get('event_id') is not None:
                assert any(e.id==item['event_id'] for e in state.events)
                item['event_id']=event_map.get(item['event_id'],item['event_id'])
            normalized.append(item)
        payload[name]=normalized
    return NormalizedTraffic(json.dumps(payload,sort_keys=True,separators=(',',':')),json.dumps(mapping,sort_keys=True,indent=2),json.dumps(raw,sort_keys=True,indent=2))


def assert_continuous_clearance(state: c.FactorySnapshot, world, initial: c.FactorySnapshot, horizon_ms: int) -> int:
    """Independent geometric proof: clip analytic primitives to shared time windows.

    This oracle never reads reservation resources. Circular chord sagitta bounds
    and circumscribed full body/85m-consist radii conservatively bound all poses.
    """
    from math import hypot,dist
    from app.operations.world_trajectory import Line,Arc,Trajectory,fillet_trajectory
    profiles={p.id:p for p in world.spatial.profiles};segments={s.id:s for s in world.segments}
    actors=[]
    for fleet in state.fleet:
        profile=profiles[fleet.variant]
        body=hypot(abs(profile.body_offset_m[0])+max(profile.size_m[0],profile.consist_length_m)/2,abs(profile.body_offset_m[2])+profile.size_m[2]/2)
        load=hypot(abs(profile.load_offset_m[0])+profile.load_size_m[0]/2,abs(profile.load_offset_m[2])+profile.load_size_m[2]/2)
        radius=max(body,load)+profile.clearance_m
        bottom=min(profile.body_offset_m[1]-profile.size_m[1]/2,profile.load_offset_m[1]-profile.load_size_m[1]/2)
        top=max(profile.body_offset_m[1]+profile.size_m[1]/2,profile.load_offset_m[1]+profile.load_size_m[1]/2)+profile.clearance_m
        height=next(s.pose.position[1] for o in world.owners if o.id==fleet.id for s in o.sockets if s.id==fleet.load_socket_id)
        vehicle=next(v for v in initial.vehicle_states if v.fleet_id==fleet.id)
        point=(vehicle.position_m[0],vehicle.position_m[1]+height,vehicle.position_m[2]);previous=0;pieces=[]
        jobs={j.id for j in state.transport_jobs if j.fleet_id==fleet.id}
        rows=sorted((m for m in state.movement_segments if m.job_id in jobs),key=lambda m:(m.start_ms,m.ordinal))
        for row in rows:
            if previous<row.start_ms: pieces.append((previous,row.start_ms,None,point))
            path=fillet_trajectory(segments[row.segment_id].points,profile.min_turn_radius_m)
            pieces.append((row.start_ms,row.end_ms,path,None));point=path.primitives[-1].end;previous=row.end_ms
        if previous<horizon_ms: pieces.append((previous,horizon_ms,None,point))
        actors.append((fleet.id,radius,(bottom,top),pieces))
    def clipped(piece,lo,hi):
        start,end,path,point=piece
        if path is None: return ((Line(point,point),0.),)
        lower=path.length*(lo-start)/(end-start);upper=path.length*(hi-start)/(end-start)
        parts=[];prefix=0.
        for part in path.primitives:
            a=max(0.,(lower-prefix)/part.length);b=min(1.,(upper-prefix)/part.length)
            if a<b:
                if isinstance(part,Line):
                    p=tuple(x+(y-x)*a for x,y in zip(part.start,part.end));q=tuple(x+(y-x)*b for x,y in zip(part.start,part.end));parts.append(Line(p,q))
                else: parts.append(Arc(part.at(a),part.at(b),part.center,part.radius,part.angle*(b-a)))
            prefix+=part.length
        return Trajectory(tuple(parts),path.radius_m).bounded_chords(.005)
    def point_distance(p,a,b):
        dx,dz=b[0]-a[0],b[2]-a[2];n=dx*dx+dz*dz
        f=max(0.,min(1.,((p[0]-a[0])*dx+(p[2]-a[2])*dz)/n)) if n else 0.
        return hypot(p[0]-a[0]-f*dx,p[2]-a[2]-f*dz)
    def gap(a,b):
        ax,az=a.end[0]-a.start[0],a.end[2]-a.start[2];bx,bz=b.end[0]-b.start[0],b.end[2]-b.start[2]
        dx,dz=b.start[0]-a.start[0],b.start[2]-a.start[2];det=ax*bz-az*bx
        if abs(det)>1e-10:
            ta=(dx*bz-dz*bx)/det;tb=(dx*az-dz*ax)/det
            if 0<=ta<=1 and 0<=tb<=1: return 0.
        return min(point_distance(p,x,y) for p,x,y in ((a.start,b.start,b.end),(a.end,b.start,b.end),(b.start,a.start,a.end),(b.end,a.start,a.end)))
    checked=0
    for index,(aid,ar,av,ap) in enumerate(actors):
        for bid,br,bv,bp in actors[index+1:]:
            for a in ap:
                for b in bp:
                    lo=max(a[0],b[0]);hi=min(a[1],b[1])
                    if lo>=hi: continue
                    for x,xe in clipped(a,lo,hi):
                        for y,ye in clipped(b,lo,hi):
                            if max(x.start[1],x.end[1])+av[1]<min(y.start[1],y.end[1])+bv[0] or max(y.start[1],y.end[1])+bv[1]<min(x.start[1],x.end[1])+av[0]: continue
                            separation=gap(x,y)-(ar+br+xe+ye)
                            assert separation>=-1e-7,(aid,bid,lo,hi,separation)
                            checked+=1
    return checked


def loading_case(engine: Engine, bundle: ContractTestBundle, output: Path):
    """Fixture-only T16 preparation: real stock at source and actual LOADING hold."""
    from factory_fleet_bundle import scenario,assign,advance,transition
    cargo=cargo_bundle(bundle,output)
    case=scenario(engine,cargo)
    assign(case,{'material_id':case.state.materials[0].id,'from_node_id':case.vehicle.node_id,'to_node_id':'v2:n:WAREHOUSE:dock'})
    advance(case,1000);transition(case,'EMPTY_APPROACH');advance(case,2000);transition(case,'QUEUED');advance(case,3000);transition(case,'LOADING');advance(case,4000)
    return case,cargo


def sql_fingerprint(engine: Engine) -> str:
    """Exact complete SQLite logical rows/schema comparison, including receipts."""
    from hashlib import sha256
    import sqlite3
    with sqlite3.connect(engine.url.database) as connection:
        return sha256('\n'.join(connection.iterdump()).encode()).hexdigest()


def restart_advance(engine: Engine, intents: tuple[TrafficIntent,...], target_ms: int, command_id: str, output: Path) -> None:
    """A separate Python process replays the same immutable explicit intent file."""
    import os,subprocess,sys
    with Session(engine) as session: state=service.load_snapshot(session)
    encoded=json.dumps(TrafficCommand(run_id=state.run.id,expected_revision=state.run.revision,command_id=command_id,target_ms=target_ms,intents=intents).model_dump(mode='json')['intents'],sort_keys=True)
    output.mkdir(parents=True,exist_ok=False);input_path=output/'intents.json';input_path.write_text(encoded)
    code="""import json,sys
from pathlib import Path
from sqlalchemy import create_engine,event
from sqlalchemy.orm import Session
from app.operations import service_v3 as service
from app.operations.traffic_service import TrafficCommand
engine=create_engine('sqlite:///'+sys.argv[1])
@event.listens_for(engine,'connect')
def fk(connection,record): connection.execute('PRAGMA foreign_keys=ON')
with Session(engine) as session,session.begin():
 state=service.load_snapshot(session)
 command=TrafficCommand.model_validate({'run_id':state.run.id,'expected_revision':state.run.revision,'command_id':sys.argv[4],'target_ms':int(sys.argv[3]),'intents':json.loads(Path(sys.argv[2]).read_text())})
 result=service.advance_traffic(session,command)
 print(result.model_dump_json())
engine.dispose()
"""
    result=subprocess.run([sys.executable,'-c',code,str(engine.url.database),str(input_path),str(target_ms),command_id],env={**os.environ,'PYTHONPATH':str(Path(__file__).absolute().parents[2])},capture_output=True,text=True,check=False)
    (output/'stdout.json').write_text(result.stdout);(output/'stderr.log').write_text(result.stderr);(output/'exit.json').write_text(json.dumps({'exit':result.returncode}))
    assert result.returncode==0,result.stderr
    assert input_path.read_text()==encoded


def capture_http(engine: Engine, bundle_path: Path, run_id: str, output: Path) -> tuple[str,...]:
    """Real owned ephemeral HTTP process reads this same migrated SQL database."""
    import os,socket,subprocess,sys
    import httpx2
    output.mkdir(parents=True,exist_ok=False)
    code="""import socket,sys,uvicorn
from pathlib import Path
from app.main import create_app
from factory_traffic_bundle import read_fixture
bundle=read_fixture(Path(sys.argv[2]))
app=create_app('sqlite+aiosqlite:///'+sys.argv[1],clock_enabled=False,test_bundle=bundle)
server=uvicorn.Server(uvicorn.Config(app,host='127.0.0.1',port=0,log_level='info'))
server.run(sockets=[socket.socket(fileno=int(sys.argv[3]))])
"""
    records=[];responses=[]
    with socket.socket() as listener, (output/'server.log').open('w') as log:
        listener.bind(('127.0.0.1',0));listener.listen(128);port=listener.getsockname()[1]
        assert port not in {8000,4173,8002,4175}
        env={**os.environ,'PYTHONPATH':os.pathsep.join((str(Path(__file__).absolute().parents[2]),str(Path(__file__).absolute().parent)))}
        with subprocess.Popen([sys.executable,'-c',code,str(engine.url.database),str(bundle_path),str(listener.fileno())],env=env,pass_fds=(listener.fileno(),),stdout=log,stderr=subprocess.STDOUT) as process:
            try:
                limits=httpx2.Limits(max_connections=200,max_keepalive_connections=40,keepalive_expiry=30.)
                transport=httpx2.HTTPTransport(http2=True,retries=3,limits=limits,socket_options=[(socket.IPPROTO_TCP,socket.TCP_NODELAY,1)])
                with httpx2.Client(transport=transport,timeout=httpx2.Timeout(connect=5.,read=30.,write=10.,pool=10.),follow_redirects=True) as client:
                    for name,path in [('health','/health'),('world','/api/v1/world'),('events','/api/v1/events'),('run-world','/api/v1/runs/'+run_id+'/world')]:
                        response=client.get('http://127.0.0.1:'+str(port)+path)
                        (output/(name+'.json')).write_text(response.text)
                        records.append({'path':path,'status':response.status_code})
                        assert response.status_code==200,response.text
                        if name!='health': responses.append(response.text)
            finally:
                process.terminate()
                try: process.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    process.kill();process.wait(timeout=15)
                (output/'server-identity.json').write_text(json.dumps({'pid':process.pid,'port':port,'exit':process.returncode,'requests':records},indent=2))
    with socket.socket() as probe: gone=probe.connect_ex(('127.0.0.1',port))!=0
    (output/'cleanup.json').write_text(json.dumps({'owned_pid':process.pid,'owned_port':port,'process_exited':process.poll() is not None,'listener_gone':gone}))
    assert gone
    return tuple(responses)


def canonical_no_siding_bundle(output: Path) -> ContractTestBundle:
    """The unchanged canonical single line plus verified aliases, no added siding."""
    from hashlib import sha256
    from app.operations.fleet import derive_fleet,approved_specification
    from app.operations.traffic_world import SOURCE_SHA,corridor_identity
    from app.operations.world_contract import parse_world
    from app.operations.world_spatial_geometry import validate_factory_layout
    from app.operations.world_layout_requirements import LayoutRequirements
    from app.operations.time_adapter_v3 import EPOCH_AT
    root=Path(__file__).absolute().parents[3]
    bootstrap=derive_fleet((root/'shared/factory-world-v2.json').read_bytes(),approved_specification('TRAFFIC-CANONICAL',SOURCE_SHA))
    raw=bootstrap.world.model_dump(mode='json');spatial=raw['spatial']
    for source_id in ('rail:1:out','rail:1:back'):
        source=next(s for s in raw['segments'] if s['id']==source_id);policy=next(p for p in spatial['segment_policies'] if p['segment_id']==source_id)
        identity=corridor_identity('locomotive',(source_id,),'holding')
        raw['segments'].append({**source,'id':identity,'conflict_zone_ids':list(source['conflict_zone_ids'])})
        spatial['segment_policies'].append({**policy,'id':'policy:'+identity,'segment_id':identity,'profile_ids':['locomotive']})
        spatial['routes'].append({'id':identity,'profile_id':'locomotive','kind':'holding','from_node_id':source['from_node_id'],'to_node_id':source['to_node_id'],'segment_ids':[source_id]})
        for zone in raw['conflict_zones']:
            if zone['id'] in source['conflict_zone_ids']: zone['segment_ids'].append(identity)
        for block in spatial['rail_blocks']:
            if block['id'] in policy['rail_block_ids']: block['segment_ids'].append(identity)
    world_bytes=json.dumps(raw,sort_keys=True,indent=2).encode()
    output.mkdir(parents=True,exist_ok=False);(output/'world.json').write_bytes(world_bytes)
    proof=validate_factory_layout(world_bytes,LayoutRequirements.read(root))
    domain=c.FactoryCollections(fleet=bootstrap.fleet,vehicle_states=bootstrap.vehicle_states)
    artifacts={'world.json':world_bytes,'collections.json':domain.model_dump_json().encode(),'schema.json':json.dumps({'format':'factory-contract-test-schema-v1','schema_version':3,'fixture_version':'factory-v2','profile':'v3_contract_test','purpose':'T15 canonical no-siding infeasible counterexample'}).encode(),'reader.json':json.dumps({'format':'factory-contract-test-reader-v1','schema_version':3,'reader':'app.operations.contracts_v3.FactorySnapshot','purpose':'T15 canonical no-siding counterexample'}).encode()}
    desc=[('domain','collections.json','factory-contract-test-collections-v1'),('world','world.json','factory-world-v2'),('schema','schema.json','factory-contract-test-schema-v1'),('reader','reader.json','factory-contract-test-reader-v1')]
    bid='T15-NO-SIDING-'+sha256(world_bytes).hexdigest()[:20]
    manifest=json.dumps({'format':'factory-contract-test-bundle-v1','bundle_id':bid,'profile':'v3_contract_test','schema_version':3,'fixture_version':'factory-v2','artifacts':[{'role':role,'path':path,'format':fmt,'sha256':sha256(artifacts[path]).hexdigest()} for role,path,fmt in desc]},sort_keys=True,indent=2).encode()
    run=c.FactoryRun.model_validate({'id':'TRAFFIC-CANONICAL','bundle_id':bid,'bundle_hash':sha256(manifest).hexdigest(),'profile':'v3_contract_test','scenario_id':'NORMAL','seed':15,'elapsed_ms':0,'duration_ms':10800000,'revision':0,'event_sequence':0,'playing':False,'speed':1,'epoch_at':EPOCH_AT,'started_at':EPOCH_AT})
    initial=c.FactorySnapshot.model_validate({**domain.model_dump(),'run':run})
    result=admit_contract_test(manifest,artifacts,initial)
    for name,content in artifacts.items(): (output/name).write_bytes(content)
    (output/'bundle.json').write_bytes(manifest);(output/'domain.json').write_text(initial.model_dump_json())
    (output/'admission.json').write_text(json.dumps({'sha256':proof.raw_sha256,'swept_checks':proof.swept_checks,'registered_crossings':proof.registered_crossings,'added_physical_track':False},indent=2))
    return result


def world_variant(original: ContractTestBundle, world_bytes: bytes, output: Path) -> ContractTestBundle:
    """An explicit negative-test bundle, never a mutation of pinned/shared bytes."""
    from hashlib import sha256
    manifest=original.verified.manifest.model_dump(mode='json');artifacts={a.descriptor.path:a.content for a in original.verified.artifacts}
    manifest['bundle_id']='T15-VARIANT-'+sha256(world_bytes).hexdigest()[:20]
    for a in manifest['artifacts']:
        if a['role']=='world': artifacts[a['path']]=world_bytes
        a['sha256']=sha256(artifacts[a['path']]).hexdigest()
    raw=json.dumps(manifest,sort_keys=True,indent=2).encode()
    initial=original.initial_snapshot.model_copy(update={'run':original.initial_snapshot.run.model_copy(update={'bundle_id':manifest['bundle_id'],'bundle_hash':sha256(raw).hexdigest()})})
    result=admit_contract_test(raw,artifacts,initial)
    output.mkdir(parents=True,exist_ok=False)
    for name,content in artifacts.items(): (output/name).write_bytes(content)
    (output/'bundle.json').write_bytes(raw);(output/'domain.json').write_text(initial.model_dump_json())
    return result
