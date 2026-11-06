"""Deterministic traffic through actual T11 persistence, with finite physical holds."""
from __future__ import annotations

from pathlib import Path
import pytest


def test_target_caps_and_scales_only_playing_run() -> None:
    # Given: a pinned run with ten seconds left.
    from app.operations import contracts_v3 as c
    from app.operations.time_adapter_v3 import EPOCH_AT
    from app.operations.traffic import traffic_target
    run = c.FactoryRun.model_validate({'id':'RUN','bundle_id':'BUNDLE','bundle_hash':'0'*64,'profile':'v3_contract_test','scenario_id':'NORMAL','seed':1,'elapsed_ms':90000,'duration_ms':100000,'revision':0,'event_sequence':0,'playing':True,'speed':4,'epoch_at':EPOCH_AT,'started_at':EPOCH_AT})
    # When: the same target conversion receives wall time and capped steps.
    targets = (traffic_target(run,wall_ms=1000),traffic_target(run,steps=48),traffic_target(run.model_copy(update={'playing':False}),wall_ms=1000))
    # Then: only playing wall time scales, and duration is never exceeded.
    assert targets == (94000,100000,90000)


@pytest.mark.parametrize('options',[{'steps':0},{'steps':49},{'steps':True},{'wall_ms':float('nan')},{'wall_ms':-1},{'wall_ms':1.5},{'steps':1,'wall_ms':1},{}])
def test_target_rejects_invalid_contract_before_work(options) -> None:
    from app.operations.bundle_registry import ServiceError
    from app.operations.traffic import traffic_target
    from types import SimpleNamespace
    run = SimpleNamespace(elapsed_ms=0,duration_ms=100000,playing=True,speed=1)
    with pytest.raises(ServiceError) as error:
        traffic_target(run,**options)
    assert error.value.code == 'invalid_contract'

from tests.operations.test_factory_service import database  # noqa: F401
from sqlalchemy.orm import Session
from factory_fleet_bundle import scenario,assign,fleet_binding
from factory_traffic_bundle import execute


@pytest.fixture(scope='module')
def traffic_bundle(tmp_path_factory):
    from tools.build_factory_traffic_bundle import build_bundle
    return build_bundle(tmp_path_factory.mktemp('traffic-parent')/'bundle',full_admission=False)


def test_feasible_full100_actual_7140m_writer_arrival(database,traffic_bundle) -> None:
    # Given: all 100 registered physical bodies, a selected truck and retained intent.
    from app.operations import service_v3 as service
    from app.operations.traffic import TrafficIntent
    case=scenario(database,traffic_bundle)
    assign(case,{'from_node_id':'v2:n:WAREHOUSE:dock','to_node_id':case.vehicle.node_id})
    intent=TrafficIntent('job:1','EMPTY_APPROACH',0,2_000_000,(fleet_binding(case.world,case.fleet),))
    # When: the product executes semantic boundaries within a single large target.
    result=execute(database,intent,1_500_000,'full100-arrival')
    with Session(database) as session: state=service.load_snapshot(session)
    # Then: actual analytic travel is persisted and the endpoint enters QUEUED.
    job=next(j for j in state.transport_jobs if j.id == 'job:1')
    movements=tuple(m for m in state.movement_segments if m.job_id == job.id)
    assert job.status == 'QUEUED'
    assert len(movements) == 1 and movements[0].end_ms-movements[0].start_ms == 1_427_925
    assert next(v for v in state.vehicle_states if v.fleet_id == case.fleet.id).node_id == 'v2:n:WAREHOUSE:dock'
    assert result.run.elapsed_ms == 1_500_000


def test_feasible_four_direction_turning_and_unrelated_route(database,traffic_bundle,tmp_path) -> None:
    # Given: four disjoint actual inbound poses and off-line admitted exit slots.
    from math import pi
    from app.operations import service_v3 as service
    from factory_traffic_bundle import focused_bundle,assign_intents,execute_many
    placements=(('fleet:truck:01','v2:n:road:junction:3',-pi/2),('fleet:truck:02','v2:n:bay:truck:01:park',pi),('fleet:truck:03','v2:n:road:junction:5',pi/2),('fleet:truck:04','v2:traffic:v1:road:west',0.),('fleet:truck:05','v2:n:CS-CR-05:dock',0.))
    focused=focused_bundle(traffic_bundle,tmp_path/'focused',placements)
    requests=(('north','fleet:truck:01','v2:traffic:v1:exit:east'),('east','fleet:truck:02','v2:traffic:v1:exit:south'),('south','fleet:truck:03','v2:traffic:v1:exit:west'),('west','fleet:truck:04','v2:traffic:v1:exit:north'),('unrelated','fleet:truck:05','v2:n:CS-CR-06:dock'))
    intents=assign_intents(database,focused,requests)
    # When: the unchanged product executor resolves all actors and times.
    execute_many(database,intents,600_000,'four-direction')
    with Session(database) as session: state=service.load_snapshot(session)
    # Then: each reaches its fixed endpoint and an unrelated movement overlaps.
    assert {j.status for j in state.transport_jobs} == {'QUEUED'}
    arrivals={j.id:min(e.at_ms for e in state.events if e.event_type == 'JOB_QUEUED' and e.payload.job_id == j.id) for j in state.transport_jobs}
    assert all(t <= 600_000 for t in arrivals.values())
    unrelated=next(m for m in state.movement_segments if m.job_id == 'unrelated')
    assert any(m.job_id != 'unrelated' and m.start_ms < unrelated.end_ms and unrelated.start_ms < m.end_ms for m in state.movement_segments)


def test_feasible_opposing_rail_real_siding_and_tail(database,traffic_bundle,tmp_path) -> None:
    # Given: two admitted 85m envelopes outside the contested main section.
    from math import pi
    from app.operations import service_v3 as service
    from factory_traffic_bundle import focused_bundle,assign_intents,execute_many
    placements=(('fleet:locomotive:01','v2:traffic:v1:rail:west-hold',0.),('fleet:locomotive:02','v2:n:rail:destination-buffer',pi))
    focused=focused_bundle(traffic_bundle,tmp_path/'focused-rail',placements)
    requests=(('a-west','fleet:locomotive:01','v2:traffic:v1:rail:east-terminal'),('b-east','fleet:locomotive:02','v2:traffic:v1:rail:west-hold'))
    intents=assign_intents(database,focused,requests)
    # When: the product resolves the occupied swap through connected siding geometry.
    execute_many(database,intents,2_000_000,'opposing-rail')
    with Session(database) as session: state=service.load_snapshot(session)
    # Then: both actually arrive, and the western consist physically visits siding.
    assert {j.status for j in state.transport_jobs} == {'QUEUED'}
    rows=tuple(m for m in state.movement_segments if m.job_id == 'a-west')
    assert any(m.to_position_m == (3600.,0.,4700.) for m in rows)
    assert next(v for v in state.vehicle_states if v.fleet_id == 'fleet:locomotive:01').position_m == (5500.,0.,4300.)
    assert next(v for v in state.vehicle_states if v.fleet_id == 'fleet:locomotive:02').position_m == (2000.,0.,4300.)
    from factory_traffic_bundle import assert_continuous_clearance
    assert assert_continuous_clearance(state,focused.verified.world,focused.initial_snapshot,2000000)>0
    siding_arrival=next(m.end_ms for m in rows if m.to_position_m==(3600.,0.,4700.))
    siding_departure=min(m.start_ms for m in rows if m.start_ms>=siding_arrival and m.from_position_m==(3600.,0.,4700.))
    held=next(r for r in state.reservations if r.job_id=='a-west' and r.resource_id=='traffic:v1:block:siding:hold' and r.start_ms<siding_arrival)
    assert held.end_ms==3600000 and held.released_at_ms>siding_departure+28000
    assert siding_departure>siding_arrival



def test_feasible_actual_cargo_full100_writer_capacity_and_custody(database,traffic_bundle,tmp_path) -> None:
    # Given: real source-slot cargo, actual loading phase and typed contact proof.
    from app.operations import service_v3 as service
    from app.operations.traffic import TrafficIntent
    from app.operations.fleet_contracts import CustodyObservation
    from factory_traffic_bundle import cargo_bundle,assert_continuous_clearance
    from factory_fleet_bundle import advance,transition,custody
    bundle=cargo_bundle(traffic_bundle,tmp_path/'cargo')
    case=scenario(database,bundle);material=case.state.materials[0]
    assign(case,{'material_id':material.id,'from_node_id':case.vehicle.node_id,'to_node_id':'v2:n:WAREHOUSE:dock'})
    advance(case,1000);transition(case,'EMPTY_APPROACH');advance(case,2000);transition(case,'QUEUED');advance(case,3000);transition(case,'LOADING');advance(case,4000)
    proof,bindings=custody(case,case.fleet.id)
    intent=TrafficIntent('job:1','MOVING',0,2_000_000,bindings,CustodyObservation.model_validate(proof))
    # When: the product carries that proof unchanged through actual route dispatch.
    execute(database,intent,1_500_000,'cargo-full100')
    with Session(database) as session: state=service.load_snapshot(session)
    # Then: physical custody stays on the actual truck and unloading begins at dock.
    assert state.transport_jobs[0].status == 'UNLOADING'
    assert next(a for a in state.attachments if a.released_at_ms is None).owner_id == case.fleet.id
    assert state.movement_segments[0].end_ms-state.movement_segments[0].start_ms == 1_427_925
    assert assert_continuous_clearance(state,case.world,bundle.initial_snapshot,1_500_000)>0


def test_determinism_steps_speed_causal_receipts(database,traffic_bundle,tmp_path) -> None:
    # Given: identical immutable intents and actual admitted initial geometry.
    from math import pi
    from hashlib import sha256
    import json
    from sqlalchemy import text
    from app.operations import contracts_v3 as c, service_v3 as service
    from app.operations.traffic import traffic_target
    from app.operations.traffic_service import TrafficCommand
    from factory_traffic_bundle import focused_bundle,assign_intents,execute_many,normalize_traffic,assert_continuous_clearance
    placements=(('fleet:truck:01','v2:n:road:junction:3',-pi/2),('fleet:truck:02','v2:n:bay:truck:01:park',pi),('fleet:truck:03','v2:n:road:junction:5',pi/2),('fleet:truck:04','v2:traffic:v1:road:west',0.),('fleet:truck:05','v2:n:CS-CR-05:dock',0.))
    focused=focused_bundle(traffic_bundle,tmp_path/'deterministic-input',placements)
    requests=(('north','fleet:truck:01','v2:traffic:v1:exit:east'),('east','fleet:truck:02','v2:traffic:v1:exit:south'),('south','fleet:truck:03','v2:traffic:v1:exit:west'),('west','fleet:truck:04','v2:traffic:v1:exit:north'),('unrelated','fleet:truck:05','v2:n:CS-CR-06:dock'))
    variants=(('steps1',1,None),('steps48',48,None),('speed1',None,1),('speed2',None,2),('speed4',None,4))
    normalized=[];hashes=[];proofs=[]
    root=Path(__file__).absolute().parents[3]
    inputs=('backend/app/operations/traffic.py','backend/app/operations/traffic_service.py','backend/app/operations/traffic_world.py','backend/app/operations/jobs.py','backend/app/operations/fleet.py','backend/app/operations/fleet_persistence.py','backend/app/operations/motion_math.py','backend/tests/operations/factory_traffic_bundle.py','shared/factory-world-v2.json','shared/motion-recipes.json','shared/asset-requirements.json','shared/coverage-registry.json')
    producer_hashes={p:sha256((root/p).read_bytes()).hexdigest() for p in inputs}
    (tmp_path/'producer-before.json').write_text(json.dumps(producer_hashes,indent=2))
    # When: only product target conversion and executor handle every chunk/boundary.
    for variant,steps,speed in variants:
        if normalized:
            with Session(database) as session,session.begin():
                state=service.load_snapshot(session)
                service.apply_command(session,c.FactoryCommand(action='pause',run_id=state.run.id,expected_revision=state.run.revision,command_id='variant-pause'))
                state=service.load_snapshot(session)
                service.apply_command(session,c.FactoryCommand(action='reset',run_id=state.run.id,expected_revision=state.run.revision,command_id='variant-reset'))
        intents=assign_intents(database,focused,requests)
        with Session(database) as session: state=service.load_snapshot(session)
        baseline=state.run.event_sequence
        fixed_input=TrafficCommand(run_id=state.run.id,expected_revision=state.run.revision,command_id='INPUT',target_ms=300000,intents=intents).model_dump(mode='json')['intents']
        (tmp_path/(variant+'-intents.json')).write_text(json.dumps(fixed_input,sort_keys=True,indent=2))
        assert state.run.bundle_hash==sha256(focused.verified.manifest_bytes).hexdigest()
        if speed is not None:
            with Session(database) as session,session.begin():
                state=service.load_snapshot(session)
                service.apply_command(session,c.FactoryCommand(action='speed',speed=speed,run_id=state.run.id,expected_revision=state.run.revision,command_id='variant-speed'))
                state=service.load_snapshot(session)
                service.apply_command(session,c.FactoryCommand(action='play',run_id=state.run.id,expected_revision=state.run.revision,command_id='variant-play'))
        counter=0
        while True:
            with Session(database) as session: state=service.load_snapshot(session)
            if state.run.elapsed_ms>=300000: break
            target=traffic_target(state.run,steps=steps) if steps is not None else traffic_target(state.run,wall_ms=1000)
            execute_many(database,intents,min(300000,target),variant+':'+str(counter));counter+=1
        result=normalize_traffic(database,intents,baseline)
        normalized.append(result.content);hashes.append(sha256(result.content.encode()).hexdigest())
        (tmp_path/(variant+'-normalized.json')).write_text(result.content)
        (tmp_path/(variant+'-raw.json')).write_text(result.raw_json)
        (tmp_path/(variant+'-bijection.json')).write_text(result.mapping_json)
        bounds=assert_continuous_clearance(state,focused.verified.world,focused.initial_snapshot,300000)
        assert bounds>0 and {j.status for j in state.transport_jobs}=={'QUEUED'}
        with database.connect() as connection:
            assert connection.execute(text('PRAGMA integrity_check')).scalar_one()=='ok'
            assert connection.execute(text('PRAGMA foreign_key_check')).all()==[]
        proofs.append({'variant':variant,'run_id':state.run.id,'bundle_hash':state.run.bundle_hash,'world_sha256':sha256((tmp_path/'deterministic-input/world.json').read_bytes()).hexdigest(),'outer_command_count':counter,'target_ms':state.run.elapsed_ms,'normalized_sha256':hashes[-1],'raw_sha256':sha256(result.raw_json.encode()).hexdigest(),'bijection_sha256':sha256(result.mapping_json.encode()).hexdigest(),'continuous_bounds':bounds,'all_jobs_arrived':True,'sqlite_integrity':'ok','foreign_keys':'ok'})
        (tmp_path/'variant-proofs.json').write_text(json.dumps(proofs,indent=2))
    # Then: causal order, business IDs/windows/outcomes are byte-identical.
    (tmp_path/'normalized-hashes.json').write_text(json.dumps(hashes,indent=2))
    assert len(set(normalized))==1
    current_hashes={p:sha256((root/p).read_bytes()).hexdigest() for p in inputs}
    (tmp_path/'producer-after.json').write_text(json.dumps(current_hashes,indent=2))
    assert current_hashes==producer_hashes


def test_replay_consumed_custody_and_changed_payload_are_atomic(database,traffic_bundle,tmp_path) -> None:
    # Given: an actual cargo entry and its generating receipt, not a local queue.
    from app.operations import service_v3 as service
    from app.operations.bundle_registry import ServiceError
    from app.operations.fleet_contracts import CustodyObservation
    from app.operations.traffic import TrafficIntent
    from app.operations.traffic_service import TrafficCommand
    from factory_fleet_bundle import custody
    from factory_traffic_bundle import loading_case,sql_fingerprint
    case,_=loading_case(database,traffic_bundle,tmp_path/'cargo-replay')
    proof,bindings=custody(case,case.fleet.id)
    intent=TrafficIntent('job:1','MOVING',0,2_000_000,bindings,CustodyObservation.model_validate(proof))
    command=TrafficCommand(run_id=case.state.run.id,expected_revision=case.state.run.revision,command_id='cargo-entry',target_ms=10000,intents=(intent,))
    with Session(database) as session,session.begin(): first=service.advance_traffic(session,command)
    before=sql_fingerprint(database)
    # When: exact replay precedes stale checks; changed-body replay cannot mutate.
    with Session(database) as session,session.begin(): replay=service.advance_traffic(session,command)
    assert replay.replayed and replay.run==first.run and sql_fingerprint(database)==before
    with pytest.raises(ServiceError) as caught:
        with Session(database) as session,session.begin(): service.advance_traffic(session,command.model_copy(update={'target_ms':11000}))
    assert caught.value.code=='idempotency_conflict' and sql_fingerprint(database)==before
    # Then: a new chunk verifies consumed proof and never repeats attachment handoff.
    execute(database,intent,1_500_000,'cargo-after-entry')
    with Session(database) as session: state=service.load_snapshot(session)
    assert state.transport_jobs[0].status=='UNLOADING'
    assert len(state.attachments)==2


@pytest.mark.parametrize('mutation',['missing','owner','socket','material','unrelated'])
def test_deadlock_or_blocked_invalid_custody_has_no_sql_mutation(database,traffic_bundle,tmp_path,mutation) -> None:
    # Given: a real loading boundary and a malformed or unrelated trusted proof.
    from app.operations.bundle_registry import ServiceError
    from app.operations.fleet_contracts import CustodyObservation
    from app.operations.traffic import TrafficIntent
    from factory_fleet_bundle import custody
    from factory_traffic_bundle import loading_case,sql_fingerprint
    case,_=loading_case(database,traffic_bundle,tmp_path/'cargo-invalid')
    proof,bindings=custody(case,case.fleet.id)
    phase='MOVING'
    if mutation=='owner': proof['owner_id']='not-the-assigned-owner'
    if mutation=='socket': proof['socket_id']='not-an-admitted-socket'
    if mutation=='material': proof['material']['material_id']='unknown-material'
    if mutation=='unrelated': phase='EMPTY_APPROACH'
    intent=TrafficIntent('job:1',phase,0,2_000_000,bindings,None if mutation=='missing' else CustodyObservation.model_validate(proof))
    before=sql_fingerprint(database)
    # When: the trusted product adapter parses and validates the command.
    with pytest.raises(ServiceError) as caught: execute(database,intent,1_500_000,'invalid-cargo')
    # Then: the entire SQL database, including rows/events/receipts/revision, is unchanged.
    assert caught.value.code=='invalid_contract' and sql_fingerprint(database)==before


def test_replay_post_first_action_sql_failure_rolls_back_every_table(database,traffic_bundle) -> None:
    # Given: a later arrival write fails after actual clock/dispatch actions.
    from sqlalchemy import text
    from sqlalchemy.exc import IntegrityError
    from app.operations.traffic import TrafficIntent
    from factory_traffic_bundle import sql_fingerprint
    case=scenario(database,traffic_bundle)
    assign(case,{'from_node_id':'v2:n:WAREHOUSE:dock','to_node_id':case.vehicle.node_id})
    intent=TrafficIntent('job:1','EMPTY_APPROACH',0,2_000_000,(fleet_binding(case.world,case.fleet),))
    with database.begin() as connection:
        connection.execute(text("CREATE TRIGGER traffic_injected_failure BEFORE INSERT ON factory_v3_events WHEN NEW.event_type='JOB_QUEUED' BEGIN SELECT RAISE(ABORT,'traffic later arrival failure'); END"))
    before=sql_fingerprint(database)
    # When: the unchanged product executor reaches the injected later boundary.
    with pytest.raises(IntegrityError,match='traffic later arrival failure'): execute(database,intent,1_500_000,'rollback-all')
    # Then: every clock/action/child+outer receipt rolls back in the caller transaction.
    assert sql_fingerprint(database)==before


def test_feasible_temporarily_full_dock_real_departure(database,traffic_bundle,tmp_path) -> None:
    # Given: an unreserved physical truck actually fills the destination dock.
    from math import pi
    from app.operations import service_v3 as service
    from factory_traffic_bundle import focused_bundle,assign_intents,execute_many,assert_continuous_clearance
    placements=(('fleet:truck:01','v2:n:bay:truck:01:park',pi),('fleet:truck:02','v2:traffic:v1:exit:east',-pi/2))
    focused=focused_bundle(traffic_bundle,tmp_path/'dock',placements)
    intents=assign_intents(database,focused,(('a-arrive','fleet:truck:01','v2:traffic:v1:exit:east'),('b-depart','fleet:truck:02','v2:traffic:v1:road:west')))
    # When: real reverse-allowed departure clears the admitted dock before entry.
    execute_many(database,intents,400000,'temporary-dock')
    with Session(database) as session: state=service.load_snapshot(session)
    # Then: the arrival waited for actual travel, and no moving/stationary body overlaps.
    assert {j.status for j in state.transport_jobs}=={'QUEUED'}
    arriving=next(m for m in state.movement_segments if m.job_id=='a-arrive')
    departing=next(m for m in state.movement_segments if m.job_id=='b-depart')
    assert arriving.start_ms>=departing.end_ms
    assert assert_continuous_clearance(state,focused.verified.world,focused.initial_snapshot,400000)>0


def test_deadlock_or_blocked_permanent_dock_keeps_physical_occupancy_and_deadline(database,traffic_bundle,tmp_path) -> None:
    # Given: the same dock occupant has no known committed departure.
    from math import pi
    from app.operations import service_v3 as service
    from factory_traffic_bundle import focused_bundle,assign_intents,execute_many
    focused=focused_bundle(traffic_bundle,tmp_path/'permanent-dock',(('fleet:truck:01','v2:n:bay:truck:01:park',pi),('fleet:truck:02','v2:traffic:v1:exit:east',-pi/2)))
    intents=assign_intents(database,focused,(('a-arrive','fleet:truck:01','v2:traffic:v1:exit:east'),))
    # When: retries cross a large target with the fixed retained readiness.
    execute_many(database,intents,100000,'permanent-1');execute_many(database,intents,3600000,'permanent-2')
    with Session(database) as session: state=service.load_snapshot(session)
    # Then: exactly one reasoned block is retained, with no movement/eviction/renewed horizon.
    job=state.transport_jobs[0]
    events=[e for e in state.events if e.event_type=='JOB_BLOCKED']
    assert job.status=='BLOCKED' and len(events)==1
    assert events[0].payload.reason=='traffic:terminal:occupied_until_deadline'
    assert state.movement_segments==()
    assert next(v for v in state.vehicle_states if v.fleet_id=='fleet:truck:02').position_m==(-170.,0.,-1840.)


def test_restart_mid_arc_sql_http_and_raw_identity(database,traffic_bundle,tmp_path) -> None:
    # Given: actual route execution stopped inside its first analytic circular arc.
    import json,sqlite3
    from sqlalchemy import create_engine,text
    from app.operations import service_v3 as service
    from app.operations.traffic import TrafficIntent
    from factory_traffic_bundle import restart_advance,capture_http,sql_fingerprint,execute_many
    case=scenario(database,traffic_bundle)
    assign(case,{'from_node_id':'v2:n:WAREHOUSE:dock','to_node_id':case.vehicle.node_id})
    intent=TrafficIntent('job:1','EMPTY_APPROACH',0,2_000_000,(fleet_binding(case.world,case.fleet),))
    execute_many(database,(intent,),50000,'midarc')
    with Session(database) as session: mid=service.load_snapshot(session)
    raw_prefix=mid.events
    # Preserve exact pinned inputs for the real server without initializing another run.
    bundle_path=tmp_path/'http-bundle';bundle_path.mkdir()
    (bundle_path/'bundle.json').write_bytes(traffic_bundle.verified.manifest_bytes)
    for a in traffic_bundle.verified.artifacts: (bundle_path/a.descriptor.path).write_bytes(a.content)
    (bundle_path/'domain.json').write_text(traffic_bundle.initial_snapshot.model_dump_json())
    before_http=capture_http(database,bundle_path,mid.run.id,tmp_path/'http-before')
    reference_path=tmp_path/'uninterrupted.sqlite'
    with sqlite3.connect(database.url.database) as source,sqlite3.connect(reference_path) as target: source.backup(target)
    reference=create_engine('sqlite:///'+str(reference_path))
    # When: a new Python process, then a new HTTP process, resume the exact same DB.
    execute_many(reference,(intent,),1500000,'restart-finish')
    restart_advance(database,(intent,),1500000,'restart-finish',tmp_path/'new-process')
    after_http=capture_http(database,bundle_path,mid.run.id,tmp_path/'http-after')
    with Session(database) as session: after=service.load_snapshot(session)
    # Then: old raw identities remain unchanged and all SQL equals uninterrupted execution.
    assert after.events[:len(raw_prefix)]==raw_prefix
    assert sql_fingerprint(database)==sql_fingerprint(reference)
    assert after.transport_jobs[0].status=='QUEUED'
    assert json.loads(before_http[0])['run']['id']==json.loads(after_http[0])['run']['id']==mid.run.id
    assert json.loads(after_http[0])==json.loads(after_http[2])
    with database.connect() as connection:
        assert connection.execute(text('PRAGMA integrity_check')).scalar_one()=='ok'
        assert connection.execute(text('PRAGMA foreign_key_check')).all()==[]
    reference.dispose()


def test_restart_while_waiting_full_dock_preserves_raw_sql(database,traffic_bundle,tmp_path) -> None:
    # Given: a waiting actor while the departing body's tail still fills the dock.
    from math import pi
    import sqlite3
    from sqlalchemy import create_engine
    from app.operations import service_v3 as service
    from factory_traffic_bundle import focused_bundle,assign_intents,execute_many,restart_advance,sql_fingerprint
    focused=focused_bundle(traffic_bundle,tmp_path/'restart-dock',(('fleet:truck:01','v2:n:bay:truck:01:park',pi),('fleet:truck:02','v2:traffic:v1:exit:east',-pi/2)))
    intents=assign_intents(database,focused,(('a-arrive','fleet:truck:01','v2:traffic:v1:exit:east'),('b-depart','fleet:truck:02','v2:traffic:v1:road:west')))
    execute_many(database,intents,1500,'waiting-dock')
    with Session(database) as session: before=service.load_snapshot(session)
    assert next(j for j in before.transport_jobs if j.id=='a-arrive').status=='ASSIGNED'
    reference_path=tmp_path/'dock-reference.sqlite'
    with sqlite3.connect(database.url.database) as source,sqlite3.connect(reference_path) as target: source.backup(target)
    reference=create_engine('sqlite:///'+str(reference_path))
    # When: the product resumes in a separate Python process with the same immutable intents.
    execute_many(reference,intents,400000,'dock-finish')
    restart_advance(database,intents,400000,'dock-finish',tmp_path/'dock-process')
    # Then: raw stored history and final SQL exactly match uninterrupted execution.
    with Session(database) as session: after=service.load_snapshot(session)
    assert after.events[:len(before.events)]==before.events
    assert {j.status for j in after.transport_jobs}=={'QUEUED'}
    assert sql_fingerprint(database)==sql_fingerprint(reference)
    reference.dispose()


def test_deadlock_or_blocked_canonical_no_siding_swap_is_infeasible(database,tmp_path) -> None:
    # Given: the canonical occupied single line, with no invented passing geometry.
    from app.operations import service_v3 as service
    from factory_traffic_bundle import canonical_no_siding_bundle,assign_intents,execute_many
    bundle=canonical_no_siding_bundle(tmp_path/'canonical-no-siding')
    intents=assign_intents(database,bundle,(('a-train','fleet:locomotive:01','v2:n:bay:locomotive:02:park'),('b-train','fleet:locomotive:02','v2:n:bay:locomotive:01:park')))
    before_positions=bundle.initial_snapshot.vehicle_states
    # When: the product attempts the opposed occupied swap through the finite horizon.
    execute_many(database,intents,3600000,'no-siding')
    with Session(database) as session: state=service.load_snapshot(session)
    # Then: both retain their actual bodies and one exact reason, with no teleport.
    assert {j.status for j in state.transport_jobs}=={'BLOCKED'}
    assert state.movement_segments==()
    blocked=[e for e in state.events if e.event_type=='JOB_BLOCKED']
    assert len(blocked)==2 and all(e.payload.reason=='traffic:terminal:occupied_until_deadline' for e in blocked)
    assert {v.fleet_id:v.position_m for v in state.vehicle_states}=={v.fleet_id:v.position_m for v in before_positions}


@pytest.mark.parametrize('kind',['no_route','no_continuous_path'])
def test_deadlock_or_blocked_actual_directed_path_and_heading(database,traffic_bundle,tmp_path,kind) -> None:
    # Given: either a real one-way terminal, or a body perpendicular to departure.
    from math import pi
    from app.operations import service_v3 as service
    from factory_traffic_bundle import focused_bundle,assign_intents,execute_many
    node='v2:traffic:v1:exit:north' if kind=='no_route' else 'v2:n:bay:truck:01:park'
    yaw=0. if kind=='no_route' else pi/2
    focused=focused_bundle(traffic_bundle,tmp_path/'blocked-path',(('fleet:truck:01',node,yaw),))
    intents=assign_intents(database,focused,(('path-blocked','fleet:truck:01','v2:n:WAREHOUSE:dock'),))
    # When: the product checks the directed graph and actual pinned body heading.
    execute_many(database,intents,3600000,'path-blocked')
    with Session(database) as session: state=service.load_snapshot(session)
    # Then: finite reasoned blocking preserves the exact starting body and custody.
    assert state.transport_jobs[0].status=='BLOCKED' and state.movement_segments==()
    assert next(e.payload.reason for e in state.events if e.event_type=='JOB_BLOCKED')=='traffic:terminal:'+kind
    assert next(v.position_m for v in state.vehicle_states if v.fleet_id=='fleet:truck:01')==next(v.position_m for v in focused.initial_snapshot.vehicle_states if v.fleet_id=='fleet:truck:01')


def test_feasible_real_offload_return_and_complete_at_home(database,traffic_bundle,tmp_path) -> None:
    # Given: actual 20t cargo delivered through the full route and still on truck.
    from app.operations import service_v3 as service
    from app.operations.fleet_contracts import CustodyObservation
    from app.operations.traffic import TrafficIntent
    from factory_fleet_bundle import custody,refresh
    from factory_traffic_bundle import loading_case,execute_many
    case,_=loading_case(database,traffic_bundle,tmp_path/'return-cargo')
    proof,bindings=custody(case,case.fleet.id)
    moving=TrafficIntent('job:1','MOVING',0,3_600_000,bindings,CustodyObservation.model_validate(proof))
    execute_many(database,(moving,),1500000,'deliver-before-return');refresh(case)
    port=next(p.id for p in case.world.ports if p.node_id=='v2:n:WAREHOUSE:dock')
    unload,bindings=custody(case,port)
    returning=TrafficIntent('job:1','RETURNING',0,3_600_000,bindings,CustodyObservation.model_validate(unload))
    # When: typed actual offload enters the trusted return route, then completes home.
    execute_many(database,(returning,),3000000,'offload-return')
    with Session(database) as session: state=service.load_snapshot(session)
    # Then: no cargo or future reservation is abandoned, and the fleet is actually home.
    assert state.transport_jobs[0].status=='COMPLETED'
    vehicle=next(v for v in state.vehicle_states if v.fleet_id==case.fleet.id)
    home=next(v for v in traffic_bundle.initial_snapshot.vehicle_states if v.fleet_id==case.fleet.id)
    assert vehicle.status=='IDLE' and vehicle.position_m==home.position_m and vehicle.current_job_id is None
    assert next(a for a in state.attachments if a.released_at_ms is None).owner_id==port
    assert not any(r.released_at_ms is None and r.end_ms>3000000 for r in state.reservations)


@pytest.mark.parametrize('kind',['alias','profile'])
def test_deadlock_or_blocked_invalid_bundle_resource_has_zero_sql_mutation(database,traffic_bundle,tmp_path,kind) -> None:
    import json
    from app.operations.bundle_registry import ServiceError
    from app.operations.traffic import TrafficIntent
    from factory_traffic_bundle import world_variant,sql_fingerprint
    raw=traffic_bundle.verified.world.model_dump(mode='json')
    if kind=='alias': raw['spatial']['parking'][0]['id']=raw['nodes'][0]['id']
    else:
        policy=next(p for p in raw['spatial']['segment_policies'] if p['segment_id']=='road:shared:297:back')
        policy['profile_ids']=['forklift']
    variant=world_variant(traffic_bundle,json.dumps(raw).encode(),tmp_path/'invalid-world')
    case=scenario(database,variant);assign(case,{'from_node_id':'v2:n:WAREHOUSE:dock','to_node_id':case.vehicle.node_id})
    intent=TrafficIntent('job:1','EMPTY_APPROACH',0,2000000,(fleet_binding(case.world,case.fleet),))
    before=sql_fingerprint(database)
    with pytest.raises(ServiceError) as caught: execute(database,intent,1500000,'invalid-world')
    assert caught.value.code==('invalid_contract' if kind=='alias' else 'unsupported_bundle')
    assert sql_fingerprint(database)==before


def test_deadlock_or_blocked_stationary_cargo_without_reservation_is_an_obstacle(database,traffic_bundle,tmp_path) -> None:
    from math import pi
    from app.operations import service_v3 as service
    from factory_traffic_bundle import cargo_bundle,focused_bundle,assign_intents,execute_many
    cargo=cargo_bundle(traffic_bundle,tmp_path/'stationary-stock')
    focused=focused_bundle(cargo,tmp_path/'stationary-cargo-focus',(('fleet:truck:01','v2:n:CS-CR-05:dock',0.),('fleet:truck:02','v2:n:road:junction:3',-pi/2)))
    intents=assign_intents(database,focused,(('cargo-obstacle','fleet:truck:02','v2:n:bay:truck:01:park'),))
    execute_many(database,intents,3600000,'stationary-cargo')
    with Session(database) as session: state=service.load_snapshot(session)
    assert state.transport_jobs[0].status=='BLOCKED' and not state.movement_segments
    assert state.attachments[0].released_at_ms is None and state.attachments[0].owner_id==cargo.initial_snapshot.attachments[0].owner_id


def test_deadlock_or_blocked_actual_destination_capacity_keeps_source_custody(database,traffic_bundle,tmp_path) -> None:
    import json
    from app.operations import service_v3 as service
    from app.operations.fleet_contracts import CustodyObservation
    from app.operations.traffic import TrafficIntent
    from factory_fleet_bundle import custody
    from factory_traffic_bundle import world_variant,loading_case,execute_many
    raw=traffic_bundle.verified.world.model_dump(mode='json')
    for port in raw['ports']:
        if port['node_id']=='v2:n:WAREHOUSE:dock': port['capacity_kg']=10000
    variant=world_variant(traffic_bundle,json.dumps(raw).encode(),tmp_path/'small-dock')
    case,_=loading_case(database,variant,tmp_path/'capacity-cargo')
    proof,bindings=custody(case,case.fleet.id)
    intent=TrafficIntent('job:1','MOVING',0,3600000,bindings,CustodyObservation.model_validate(proof))
    execute_many(database,(intent,),3600000,'capacity-block')
    with Session(database) as session: state=service.load_snapshot(session)
    assert state.transport_jobs[0].status=='BLOCKED' and not state.movement_segments
    assert next(e.payload.reason for e in state.events if e.event_type=='JOB_BLOCKED')=='traffic:terminal:capacity_exceeded'
    assert len(state.attachments)==1 and state.attachments[0].released_at_ms is None


@pytest.mark.parametrize('mutation',['foreign_copy','missing_child','fake_claim','event_hash','source_hash','local_order','payload'])
def test_replay_normalizer_requires_exact_actual_generating_child(database,traffic_bundle,mutation,tmp_path) -> None:
    # Given: real SQL events, child and aggregate receipts from actual mid-arc execution.
    from hashlib import sha256
    from sqlalchemy import select,update,delete
    from app.operations import service_v3 as service,models_v3 as rows
    from app.operations.bundle_registry import ServiceError
    from app.operations.traffic import TrafficIntent
    from factory_traffic_bundle import normalize_traffic,sql_fingerprint
    case=scenario(database,traffic_bundle);assign(case,{'from_node_id':'v2:n:WAREHOUSE:dock','to_node_id':case.vehicle.node_id})
    intent=TrafficIntent('job:1','EMPTY_APPROACH',0,2000000,(fleet_binding(case.world,case.fleet),))
    baseline=case.state.run.event_sequence
    execute(database,intent,50000,'normalizer-input')
    expected=normalize_traffic(database,(intent,),baseline).content
    if mutation!='foreign_copy':
        # Simulate offline archive corruption only in this owned negative fixture.
        # The original guarded SQL bytes are backed up; no product guard changes.
        import sqlite3,json
        from sqlalchemy import text
        with sqlite3.connect(database.url.database) as source,sqlite3.connect(tmp_path/'guarded-before-corruption.sqlite') as backup: source.backup(backup)
        with database.begin() as connection:
            triggers=connection.execute(text("SELECT name,sql FROM sqlite_master WHERE type='trigger' AND tbl_name IN ('factory_v3_events','factory_v3_command_receipts')")).all()
            (tmp_path/'offline-corruption-guards.json').write_text(json.dumps([{'name':name,'sql':sql} for name,sql in triggers],indent=2))
            for name,_ in triggers: connection.exec_driver_sql('DROP TRIGGER "'+name.replace('"','""')+'"')
    with Session(database) as session,session.begin():
        state=service.load_snapshot(session)
        event=next(e for e in state.events if e.event_type=='JOB_EMPTY_APPROACH')
        receipt=next(r for r in session.scalars(select(rows.CommandReceipt).where(rows.CommandReceipt.run_id==state.run.id)) if event.id=='fleet:event:'+sha256((r.command_id+':'+str(event.sequence)).encode()).hexdigest())
        match mutation:
            case 'foreign_copy':
                session.execute(rows.CommandReceipt.__table__.insert().values(run_id=receipt.run_id,command_id='foreign-identical-copy',payload_digest=receipt.payload_digest,result_run_id=receipt.result_run_id,result_revision=receipt.result_revision,reply_json=receipt.reply_json))
            case 'missing_child': session.execute(delete(rows.CommandReceipt).where(rows.CommandReceipt.run_id==state.run.id,rows.CommandReceipt.command_id==receipt.command_id))
            case 'fake_claim': session.execute(update(rows.CommandReceipt).where(rows.CommandReceipt.run_id==state.run.id,rows.CommandReceipt.command_id==receipt.command_id).values(command_id='fake-claimed-command'))
            case 'event_hash': session.execute(update(rows.FactoryEvent).where(rows.FactoryEvent.run_id==state.run.id,rows.FactoryEvent.id==event.id).values(id='fleet:event:'+'0'*64))
            case 'source_hash': session.execute(update(rows.FactoryEvent).where(rows.FactoryEvent.run_id==state.run.id,rows.FactoryEvent.id==event.id).values(source_id='fleet:source:'+'0'*64))
            case 'local_order':
                raw=dict(receipt.reply_json);raw['delta']={**raw['delta'],'upserts':{**raw['delta']['upserts'],'events':list(reversed(raw['delta']['upserts']['events']))}}
                session.execute(update(rows.CommandReceipt).where(rows.CommandReceipt.run_id==state.run.id,rows.CommandReceipt.command_id==receipt.command_id).values(reply_json=raw))
            case 'payload': session.execute(update(rows.FactoryEvent).where(rows.FactoryEvent.run_id==state.run.id,rows.FactoryEvent.id==event.id).values(payload={**event.payload.model_dump(mode='json'),'reason':'traffic:tampered'}))
    # When: normalization proves causal identity against the actual stored SQL row.
    if mutation=='foreign_copy':
        assert normalize_traffic(database,(intent,),baseline).content==expected
        execute(database,intent,60000,'after-foreign-copy')
    else:
        with pytest.raises((AssertionError,ServiceError)): normalize_traffic(database,(intent,),baseline)
        if mutation!='local_order':
            before=sql_fingerprint(database)
            with pytest.raises(ServiceError) as caught: execute(database,intent,60000,'after-corrupt-child')
            assert caught.value.code=='unsupported_bundle' and sql_fingerprint(database)==before


@pytest.mark.parametrize('kind',['run','revision','nonfinite'])
def test_replay_traffic_stale_and_strict_before_lock_leave_all_sql(database,traffic_bundle,monkeypatch,kind) -> None:
    from app.operations import service_v3 as service
    from app.operations.bundle_registry import ServiceError
    from app.operations.traffic import TrafficIntent
    from app.operations.traffic_service import TrafficCommand
    from factory_traffic_bundle import sql_fingerprint
    case=scenario(database,traffic_bundle);assign(case,{'from_node_id':'v2:n:WAREHOUSE:dock','to_node_id':case.vehicle.node_id})
    intent=TrafficIntent('job:1','EMPTY_APPROACH',0,2000000,(fleet_binding(case.world,case.fleet),))
    command=TrafficCommand(run_id=case.state.run.id,expected_revision=case.state.run.revision,command_id='stale-strict',target_ms=1000,intents=(intent,))
    expected={'run':'stale_run','revision':'stale_revision','nonfinite':'invalid_contract'}[kind]
    if kind=='run': command=command.model_copy(update={'run_id':'not-the-selected-run'})
    if kind=='revision': command=command.model_copy(update={'expected_revision':0})
    if kind=='nonfinite':
        command=command.model_copy(update={'target_ms':float('nan')})
        def forbidden_lock(session): raise AssertionError('invalid scalar reached writer lock')
        monkeypatch.setattr(service,'_writer_lock',forbidden_lock)
    before=sql_fingerprint(database)
    with pytest.raises(ServiceError) as caught:
        with Session(database) as session,session.begin(): service.advance_traffic(session,command)
    assert caught.value.code==expected and sql_fingerprint(database)==before


def _terminal_cargo_case(database, traffic_bundle, tmp_path, mixed=False):
    import json
    from app.operations.traffic import TrafficIntent
    from app.operations.fleet_contracts import CustodyObservation
    from factory_fleet_bundle import custody
    from factory_traffic_bundle import world_variant,loading_case,execute_many
    raw=traffic_bundle.verified.world.model_dump(mode='json')
    for port in raw['ports']:
        if port['node_id']=='v2:n:WAREHOUSE:dock': port['capacity_kg']=10000
    bundle=world_variant(traffic_bundle,json.dumps(raw).encode(),tmp_path/'small-dock')
    if mixed:
        from factory_traffic_bundle import focused_bundle
        bundle=focused_bundle(bundle,tmp_path/'mixed-initial',(('fleet:truck:02','v2:n:CS-CR-05:dock',0.),))
    case,_=loading_case(database,bundle,tmp_path/'cargo')
    proof,bindings=custody(case,case.fleet.id)
    intent=TrafficIntent('job:1','MOVING',0,3600000,bindings,CustodyObservation.model_validate(proof))
    intents=(intent,)
    if mixed:
        from app.operations import service_v3 as service
        from app.operations.fleet_contracts import AssignFleetJob
        with Session(database) as session,session.begin():
            state=service.load_snapshot(session);fleet=next(f for f in state.fleet if f.id=='fleet:truck:02');vehicle=next(v for v in state.vehicle_states if v.fleet_id==fleet.id)
            other_bindings=(fleet_binding(case.world,fleet),)
            service.apply_fleet_transition(session,AssignFleetJob.model_validate({'action':'assign_fleet_job','run_id':state.run.id,'expected_revision':state.run.revision,'command_id':'terminal-cargo:other-assign','job_id':'job:other','fleet_id':fleet.id,'equipment_id':None,'material_id':None,'shipment_leg_id':None,'from_node_id':'v2:n:CS-CR-06:dock','to_node_id':vehicle.node_id,'ready_at_ms':state.run.elapsed_ms,'phase':{'start_ms':state.run.elapsed_ms,'end_ms':21000},'movements':(),'reservations':(),'bindings':other_bindings}))
        intents=(*intents,TrafficIntent('job:other','EMPTY_APPROACH',20000,3600000,other_bindings))
    execute_many(database,intents,10000,'terminal-cargo:first')
    return intents


def test_repair_terminal_capacity_retained_input_restart_and_replay(database,traffic_bundle,tmp_path):
    from app.operations import service_v3 as service
    from app.operations.traffic_service import TrafficCommand
    from app.operations.bundle_registry import ServiceError
    from factory_traffic_bundle import execute_many,restart_advance,sql_fingerprint
    intent,=_terminal_cargo_case(database,traffic_bundle,tmp_path)
    with Session(database) as session: before=service.load_snapshot(session)
    restart_advance(database,(intent,),20000,'terminal-cargo:restart',tmp_path/'process')
    with Session(database) as session: after=service.load_snapshot(session)
    assert before.transport_jobs==after.transport_jobs and before.attachments==after.attachments
    assert before.movement_segments==after.movement_segments and before.reservations==after.reservations
    assert len([e for e in after.events if e.event_type=='JOB_BLOCKED'])==1
    assert intent.deadline_ms==3600000 and after.run.elapsed_ms==20000
    fingerprint=sql_fingerprint(database)
    with Session(database) as session,session.begin():
        replay=service.advance_traffic(session,TrafficCommand(run_id=before.run.id,expected_revision=before.run.revision,command_id='terminal-cargo:restart',target_ms=20000,intents=(intent,)))
        assert replay.replayed
    for command in (TrafficCommand(run_id=before.run.id,expected_revision=before.run.revision,command_id='terminal-cargo:stale',target_ms=30000,intents=(intent,)),TrafficCommand(run_id=before.run.id,expected_revision=before.run.revision,command_id='terminal-cargo:restart',target_ms=30000,intents=(intent,))):
        with pytest.raises(ServiceError):
            with Session(database) as session,session.begin(): service.advance_traffic(session,command)
        assert sql_fingerprint(database)==fingerprint
    execute_many(database,(intent,),30000,'terminal-cargo:next')


@pytest.mark.parametrize('mutation',['proof_removed','owner','socket','material','anchor','previous_anchor','channels','readiness','deadline','phase','bindings'])
def test_repair_terminal_capacity_changed_input_is_atomic(database,traffic_bundle,tmp_path,mutation):
    from dataclasses import replace
    from app.operations.fleet_contracts import CustodyObservation
    from app.operations.bundle_registry import ServiceError
    from factory_traffic_bundle import execute_many,sql_fingerprint
    intent,=_terminal_cargo_case(database,traffic_bundle,tmp_path)
    raw=intent.custody.model_dump(mode='json')
    if mutation=='proof_removed': changed=replace(intent,custody=None)
    elif mutation=='readiness': changed=replace(intent,ready_at_ms=1)
    elif mutation=='deadline': changed=replace(intent,deadline_ms=3599999)
    elif mutation=='phase': changed=replace(intent,phase='EMPTY_APPROACH')
    elif mutation=='bindings': changed=replace(intent,bindings=tuple(reversed(intent.bindings)))
    else:
        if mutation=='owner': raw['owner_id']='fleet:truck:02'
        elif mutation=='socket': raw['socket_id']='other-socket'
        elif mutation=='material': raw['material']['material_id']='other-material'
        elif mutation=='anchor': raw['anchor']['position_m'][0]+=1
        elif mutation=='previous_anchor': raw['previous_anchor']['position_m'][0]+=1
        elif mutation=='channels': raw['channels'][0]['end_value']=1.
        changed=replace(intent,custody=CustodyObservation.model_validate(raw))
    before=sql_fingerprint(database)
    with pytest.raises(ServiceError): execute_many(database,(changed,),20000,'terminal-cargo:changed')
    assert sql_fingerprint(database)==before


@pytest.mark.parametrize('feasible',[False,True])
def test_repair_three_ready_recovery_finite_custody_tail_and_restart(database,traffic_bundle,tmp_path,feasible):
    from math import pi
    import json,sqlite3
    from sqlalchemy import create_engine
    from app.operations import service_v3 as service
    from factory_traffic_bundle import focused_bundle,assign_intents,execute_many,restart_advance,sql_fingerprint,assert_continuous_clearance
    placements=(('fleet:locomotive:01','v2:n:destination:rail:4300:unload' if feasible else 'v2:traffic:v1:rail:west-hold',0.),('fleet:locomotive:02','v2:n:rail:destination-buffer',pi),('fleet:locomotive:03','v2:n:transfer:rail:rail' if feasible else 'v2:n:destination:rail:4300:unload',pi))
    focused=focused_bundle(traffic_bundle,tmp_path/'competition',placements)
    requests=(('a-west','fleet:locomotive:01','v2:n:rail:destination-buffer' if feasible else 'v2:traffic:v1:rail:east-terminal'),('b-east','fleet:locomotive:02','v2:n:transfer:rail:rail' if feasible else 'v2:traffic:v1:rail:west-hold'),('c-recovery','fleet:locomotive:03','v2:traffic:v1:rail:west-hold' if feasible else 'v2:n:rail:destination-buffer'))
    intents=assign_intents(database,focused,requests)
    execute_many(database,intents,358000,'competition:mid')
    with Session(database) as session: mid=service.load_snapshot(session)
    reference_path=tmp_path/'reference.sqlite'
    with sqlite3.connect(database.url.database) as source,sqlite3.connect(reference_path) as target: source.backup(target)
    reference=create_engine('sqlite:///'+str(reference_path))
    execute_many(reference,intents,3600000,'competition:finish')
    restart_advance(database,intents,3600000,'competition:finish',tmp_path/'process')
    with Session(database) as session: state=service.load_snapshot(session)
    assert sql_fingerprint(reference)==sql_fingerprint(database)
    assert state.events[:len(mid.events)]==mid.events
    assert {j.id:j.status for j in state.transport_jobs}==({'a-west':'BLOCKED','b-east':'QUEUED','c-recovery':'QUEUED'} if feasible else {'a-west':'BLOCKED','b-east':'BLOCKED','c-recovery':'BLOCKED'})
    bounds=assert_continuous_clearance(state,focused.verified.world,focused.initial_snapshot,3600000)
    terminal=[e for e in state.events if e.event_type=='JOB_BLOCKED' and e.payload.reason.startswith('traffic:terminal:')]
    if not feasible:
        assert len(terminal)==3 and all(e.at_ms==357511 and e.payload.reason=='traffic:terminal:occupied_until_deadline' for e in terminal)
        assert len(state.movement_segments)==1 and state.movement_segments[0].to_position_m==(3600.,0.,4700.)
        held=next(r for r in state.reservations if r.job_id=='a-west' and r.resource_id=='traffic:v1:block:siding:hold')
        assert held.end_ms==3600000 and held.released_at_ms is None
    else:
        assert len(terminal)==1 and terminal[0].at_ms==978511
        assert any(m.job_id=='a-west' and m.to_position_m==(3600.,0.,4700.) for m in state.movement_segments)
    (tmp_path/'result.json').write_text(json.dumps({'fixture':'later_terminal' if feasible else 'original_infeasible','feasible':False,'bounds':bounds,'jobs':[(j.id,j.status) for j in state.transport_jobs],'terminal':[(e.payload.job_id,e.at_ms,e.payload.reason) for e in terminal],'raw_restart_identical':True},indent=2))
    reference.dispose()


@pytest.mark.parametrize('mutation',['missing_child','child_payload','missing_outer','outer_digest'])
def test_repair_terminal_capacity_origin_proof_is_atomic(database,traffic_bundle,tmp_path,mutation):
    import json,sqlite3
    from sqlalchemy import select,delete,update,text
    from app.operations import models_v3 as rows,service_v3 as service
    from app.operations.bundle_registry import ServiceError
    from app.operations.traffic_service import _semantic_id
    from factory_traffic_bundle import execute_many,sql_fingerprint
    intent,=_terminal_cargo_case(database,traffic_bundle,tmp_path)
    with Session(database) as session:
        state=service.load_snapshot(session)
        event=next(e for e in state.events if e.event_type=='JOB_BLOCKED')
        child_id=_semantic_id(intent,event.at_ms,'BLOCKED:'+event.payload.reason)
    with sqlite3.connect(database.url.database) as source,sqlite3.connect(tmp_path/'guarded-before-corruption.sqlite') as backup: source.backup(backup)
    with database.begin() as connection:
        guards=connection.execute(text("SELECT name,sql FROM sqlite_master WHERE type='trigger' AND tbl_name='factory_v3_command_receipts'")).all()
        (tmp_path/'offline-corruption-guards.json').write_text(json.dumps([{'name':n,'sql':s} for n,s in guards],indent=2))
        for name,_ in guards: connection.exec_driver_sql('DROP TRIGGER "'+name.replace('"','""')+'"')
    with Session(database) as session,session.begin():
        child=session.get(rows.CommandReceipt,(state.run.id,child_id))
        # An identical aggregate copy cannot replace the actual semantic child.
        session.execute(rows.CommandReceipt.__table__.insert().values(run_id=child.run_id,command_id='foreign-copy',payload_digest=child.payload_digest,result_run_id=child.result_run_id,result_revision=child.result_revision,reply_json=child.reply_json))
        key=child_id if mutation in {'missing_child','child_payload'} else 'terminal-cargo:first'
        where=(rows.CommandReceipt.run_id==state.run.id,rows.CommandReceipt.command_id==key)
        if mutation in {'missing_child','missing_outer'}: session.execute(delete(rows.CommandReceipt).where(*where))
        elif mutation=='child_payload':
            raw=json.loads(json.dumps(child.reply_json));raw['delta']['upserts']['events'][0]['payload']['reason']='traffic:terminal:no_route'
            session.execute(update(rows.CommandReceipt).where(*where).values(reply_json=raw))
        else: session.execute(update(rows.CommandReceipt).where(*where).values(payload_digest='0'*64))
    before=sql_fingerprint(database)
    with pytest.raises(ServiceError): execute_many(database,(intent,),20000,'terminal-cargo:corrupt')
    assert sql_fingerprint(database)==before


def test_repair_terminal_capacity_mixed_other_actor_advances(database,traffic_bundle,tmp_path):
    from app.operations import service_v3 as service
    from factory_traffic_bundle import execute_many
    intents=_terminal_cargo_case(database,traffic_bundle,tmp_path,mixed=True)
    with Session(database) as session: before=service.load_snapshot(session)
    execute_many(database,intents,400000,'terminal-cargo:mixed-next')
    with Session(database) as session: after=service.load_snapshot(session)
    assert next(j.status for j in after.transport_jobs if j.id=='job:other')=='QUEUED'
    assert next(j for j in before.transport_jobs if j.id=='job:1')==next(j for j in after.transport_jobs if j.id=='job:1')
    assert after.attachments==before.attachments
    assert not any(m.job_id=='job:1' for m in after.movement_segments)
    assert len([e for e in after.events if e.event_type=='JOB_BLOCKED' and e.payload.job_id=='job:1'])==1


def test_d5_feasible_ready_road_recovery_competition_restart(database,traffic_bundle,tmp_path):
    from math import pi
    import json,sqlite3
    from sqlalchemy import create_engine
    from app.operations import service_v3 as service
    from factory_traffic_bundle import focused_bundle,assign_intents,execute_many,restart_advance,normalize_traffic,assert_continuous_clearance
    focused=focused_bundle(traffic_bundle,tmp_path/'input',(('fleet:truck:01','v2:n:road:junction:3',-pi/2),('fleet:truck:02','v2:n:road:junction:5',pi/2),('fleet:truck:03','v2:n:bay:truck:01:park',pi)))
    intents=assign_intents(database,focused,(('a-north','fleet:truck:01','v2:n:road:junction:5'),('b-south','fleet:truck:02','v2:n:road:junction:3'),('c-compete','fleet:truck:03','v2:traffic:v1:exit:south')))
    with Session(database) as session: baseline=service.load_snapshot(session).run.event_sequence
    execute_many(database,intents,120850,'competition:hold')
    with Session(database) as session: held=service.load_snapshot(session)
    assert next(j.status for j in held.transport_jobs if j.id=='a-north')=='BLOCKED'
    copy=tmp_path/'reference.sqlite'
    with sqlite3.connect(database.url.database) as a,sqlite3.connect(copy) as b:a.backup(b)
    chunked_path=tmp_path/'chunked.sqlite'
    with sqlite3.connect(database.url.database) as a,sqlite3.connect(chunked_path) as b:a.backup(b)
    reference=create_engine('sqlite:///'+str(copy))
    execute_many(reference,intents,600000,'competition:finish')
    restart_advance(database,intents,600000,'competition:finish',tmp_path/'restart')
    with Session(database) as session: state=service.load_snapshot(session)
    assert state.events[:len(held.events)]==held.events
    assert {j.status for j in state.transport_jobs}=={'QUEUED'}
    expected=normalize_traffic(reference,intents,baseline);actual=normalize_traffic(database,intents,baseline)
    assert actual.content==expected.content and actual.raw_json==expected.raw_json
    chunked=create_engine('sqlite:///'+str(chunked_path))
    for target in (*range(168850,600000,48000),600000): execute_many(chunked,intents,target,'competition:48:'+str(target))
    varied=normalize_traffic(chunked,intents,baseline)
    assert varied.content==actual.content
    competitor=next(m for m in state.movement_segments if m.job_id=='c-compete')
    recovering=next(m for m in state.movement_segments if m.job_id=='a-north')
    shared={r.resource_id for r in state.reservations if r.job_id=='c-compete'}&{r.resource_id for r in state.reservations if r.job_id=='a-north'}
    assert shared and competitor.end_ms<recovering.start_ms
    bounds=assert_continuous_clearance(state,focused.verified.world,focused.initial_snapshot,600000)
    (tmp_path/'proof.json').write_text(json.dumps({'shared_resources':sorted(shared),'collision_bounds':bounds,'raw_restart_identical':True,'all_arrived':True},indent=2))
    (tmp_path/'normalized.json').write_text(actual.content);(tmp_path/'bijection.json').write_text(actual.mapping_json)
    (tmp_path/'chunk48-bijection.json').write_text(varied.mapping_json)
    reference.dispose();chunked.dispose()


def _d5_late_hold(database,traffic_bundle,tmp_path,committed=True):
    from math import pi
    from factory_traffic_bundle import focused_bundle,assign_intents,execute_many
    focused=focused_bundle(traffic_bundle,tmp_path/'input',(('fleet:locomotive:01','v2:n:destination:rail:4300:unload',0.),('fleet:locomotive:02','v2:n:rail:destination-buffer',pi),('fleet:locomotive:03','v2:n:transfer:rail:rail',pi)))
    intents=assign_intents(database,focused,(('a-west','fleet:locomotive:01','v2:n:rail:destination-buffer'),('b-east','fleet:locomotive:02','v2:n:transfer:rail:rail'),('c-recovery','fleet:locomotive:03','v2:traffic:v1:rail:west-hold')))
    if committed: execute_many(database,intents,358000,'d5:held')
    return intents


@pytest.mark.parametrize('committed',[False,True])
def test_d5_annotation_strict_replay_stale_and_atomic_guards(database,traffic_bundle,tmp_path,monkeypatch,committed):
    import json
    from dataclasses import replace
    from app.operations import traffic_service as ts,service_v3 as service
    from app.operations.bundle_registry import ServiceError
    from factory_traffic_bundle import execute_many
    intents=_d5_late_hold(database,traffic_bundle,tmp_path,committed)
    original=ts._annotate_terminal;observed=[]
    def checked(session,request,scope):
        before=service.load_snapshot(session)
        current=ts.next_traffic_boundary(ts._context(session,before),intents,before.run.elapsed_ms)
        planned=next(d for d in current.decisions if d.job_id==request.job_id)
        assert len(planned.blocking_resource_ids)>1
        assert request.primary_blocking_resource_id==min(planned.blocking_resource_ids)
        cases=[request.model_copy(update={'expected_revision':request.expected_revision-1}),request.model_copy(update={'held_event_id':'unknown-hold'}),request.model_copy(update={'primary_blocking_resource_id':'unknown-resource'}),request.model_copy(update={'intents':(replace(intents[0],deadline_ms=3599999),*intents[1:])}),request.model_copy(update={'job_id':'b-east'}),request.model_copy(update={'reason_code':float('nan')})]
        for bad in cases:
            with pytest.raises(ServiceError): original(session,bad,scope)
            assert service.load_snapshot(session)==before
        reply=original(session,request,scope)
        assert original(session,request,scope).replayed
        with pytest.raises(ServiceError) as conflict: original(session,request.model_copy(update={'reason_code':'no_route'}),scope)
        assert conflict.value.code=='idempotency_conflict'
        for update in ({'expected_revision':request.expected_revision+1},{'held_event_id':'changed-hold'},{'primary_blocking_resource_id':'changed-primary'},{'job_id':'changed-job'},{'intents':(replace(intents[0],ready_at_ms=1),*intents[1:])}):
            with pytest.raises(ServiceError) as changed: original(session,request.model_copy(update=update),scope)
            assert changed.value.code=='idempotency_conflict'
        from pydantic import ValidationError
        with pytest.raises(ValidationError): ts._TrafficTerminal.model_validate({**request.model_dump(),'blocking_resource_ids':('obsolete',)})
        assert service.load_snapshot(session).run==reply.run
        observed.append({'request':request.model_dump(mode='json'),'reply':reply.model_dump(mode='json'),'full_server_blockers':planned.blocking_resource_ids,'negative_cases':len(cases),'exact_replayed':True})
        return reply
    monkeypatch.setattr(ts,'_annotate_terminal',checked)
    execute_many(database,intents,1000000,'d5:annotated')
    execute_many(database,intents,1100000,'d5:retained')
    assert len(observed)==1
    (tmp_path/'annotation-proof.json').write_text(json.dumps(observed,indent=2))
    from factory_traffic_bundle import normalize_traffic
    with Session(database) as session:
        state=service.load_snapshot(session)
        baseline=max(e.sequence for e in state.events if e.event_type=='JOB_ASSIGNED')
    normalized=normalize_traffic(database,intents,baseline)
    assert observed[0]['request']['command_id'] in {r['command_id'] for r in json.loads(normalized.mapping_json)}
    (tmp_path/'bijection.json').write_text(normalized.mapping_json)


def test_d5_annotation_post_write_failure_rolls_back_outer(database,traffic_bundle,tmp_path,monkeypatch):
    from app.operations import traffic_service as ts
    from factory_traffic_bundle import execute_many,sql_fingerprint
    intents=_d5_late_hold(database,traffic_bundle,tmp_path)
    before=sql_fingerprint(database);original=ts._annotate_terminal;seen=[]
    def fail(session,request,scope):
        result=original(session,request,scope);seen.append(result)
        raise RuntimeError('injected after durable annotation')
    monkeypatch.setattr(ts,'_annotate_terminal',fail)
    with pytest.raises(RuntimeError,match='injected after durable annotation'): execute_many(database,intents,1000000,'d5:rollback')
    assert len(seen)==1 and sql_fingerprint(database)==before


@pytest.mark.parametrize('mutation',['missing_hold','corrupt_hold','missing_outer','corrupt_outer'])
def test_d5_annotation_hold_origin_provenance_is_atomic(database,traffic_bundle,tmp_path,mutation):
    import json,sqlite3
    from sqlalchemy import delete,update,text
    from app.operations import models_v3 as rows,service_v3 as service
    from app.operations.traffic_service import _semantic_id
    from app.operations.bundle_registry import ServiceError
    from factory_traffic_bundle import execute_many,sql_fingerprint
    intents=_d5_late_hold(database,traffic_bundle,tmp_path)
    with Session(database) as session:
        state=service.load_snapshot(session)
        held=next(e for e in state.events if e.event_type=='JOB_BLOCKED' and e.payload.job_id=='a-west')
        child_id=_semantic_id(intents[0],held.at_ms,'BLOCKED:traffic:corridor_boundary')
    with sqlite3.connect(database.url.database) as a,sqlite3.connect(tmp_path/'guarded-before.sqlite') as b:a.backup(b)
    with database.begin() as connection:
        guards=connection.execute(text("SELECT name,sql FROM sqlite_master WHERE type='trigger' AND tbl_name='factory_v3_command_receipts'")).all()
        (tmp_path/'offline-guards.json').write_text(json.dumps([{'name':n,'sql':s} for n,s in guards]))
        for name,_ in guards: connection.exec_driver_sql('DROP TRIGGER "'+name.replace('"','""')+'"')
    with Session(database) as session,session.begin():
        key=child_id if mutation.endswith('hold') else 'd5:held'
        where=(rows.CommandReceipt.run_id==state.run.id,rows.CommandReceipt.command_id==key)
        if mutation.startswith('missing'): session.execute(delete(rows.CommandReceipt).where(*where))
        else: session.execute(update(rows.CommandReceipt).where(*where).values(payload_digest='0'*64))
    before=sql_fingerprint(database)
    with pytest.raises(ServiceError): execute_many(database,intents,1000000,'d5:invalid-origin')
    assert sql_fingerprint(database)==before


def test_d6_known_future_release_forbids_annotation(database,traffic_bundle,tmp_path):
    from app.operations import traffic_service as ts,service_v3 as service
    from app.operations.bundle_registry import ServiceError
    from factory_traffic_bundle import sql_fingerprint
    intents=_d5_late_hold(database,traffic_bundle,tmp_path)
    before=sql_fingerprint(database)
    with pytest.raises(ServiceError):
        with Session(database) as session,session.begin():
            state=service.load_snapshot(session);context=ts._context(session,state)
            from app.operations.traffic import plan_traffic
            pending=tuple(i for i in intents if next(j.status for j in state.transport_jobs if j.id==i.job_id)!='QUEUED')
            decision=next(d for d in plan_traffic(context,pending) if d.job_id=='a-west')
            assert decision.kind=='wait' and decision.next_retry_ms>state.run.elapsed_ms
            held=next(e for e in reversed(state.events) if e.event_type=='JOB_BLOCKED' and e.payload.job_id=='a-west')
            outer=ts.TrafficCommand(run_id=state.run.id,expected_revision=state.run.revision,command_id='d6:wait',target_ms=1000000,intents=intents)
            request=ts._TrafficTerminal(action='annotate_traffic_terminal',run_id=state.run.id,expected_revision=state.run.revision,command_id=ts._semantic_id(intents[0],state.run.elapsed_ms,'terminal_annotation:occupied_until_deadline'),job_id='a-west',held_event_id=held.id,intents=intents,reason_code='occupied_until_deadline',primary_blocking_resource_id=decision.blocking_resource_ids[0])
            ts._annotate_terminal(session,request,ts._TrafficScope(outer,state.run.event_sequence))
    assert sql_fingerprint(database)==before


def test_r6_annotation_replay_after_other_actor_moves_restart_http(database,traffic_bundle,tmp_path,monkeypatch):
    from math import pi
    from dataclasses import replace
    import json,sqlite3
    from sqlalchemy import create_engine,text
    from app.operations import service_v3 as service,traffic_service as ts
    from app.operations.bundle_registry import ServiceError
    from factory_traffic_bundle import focused_bundle,assign_intents,execute_many,restart_advance,capture_http,sql_fingerprint,normalize_traffic,assert_continuous_clearance
    placements=(('fleet:locomotive:01','v2:n:destination:rail:4300:unload',0.),('fleet:locomotive:02','v2:n:rail:destination-buffer',pi),('fleet:locomotive:03','v2:n:transfer:rail:rail',pi),('fleet:truck:05','v2:n:CS-CR-05:dock',0.))
    focused=focused_bundle(traffic_bundle,tmp_path/'input',placements)
    raw=assign_intents(database,focused,(('a-west','fleet:locomotive:01','v2:n:rail:destination-buffer'),('b-east','fleet:locomotive:02','v2:n:transfer:rail:rail'),('c-recovery','fleet:locomotive:03','v2:traffic:v1:rail:west-hold'),('d-later','fleet:truck:05','v2:n:CS-CR-06:dock')))
    intents=tuple(replace(i,ready_at_ms=1050000) if i.job_id=='d-later' else i for i in raw)
    original=ts._annotate_terminal;captured=[]
    def remember(session,request,scope):
        result=original(session,request,scope);captured.append((request,scope,result));return result
    monkeypatch.setattr(ts,'_annotate_terminal',remember)
    execute_many(database,intents,1000000,'r6:annotation')
    assert len(captured)==1
    with Session(database) as session: annotated=service.load_snapshot(session)
    execute_many(database,intents,1500000,'r6:other-actor-moved')
    with Session(database) as session: moved=service.load_snapshot(session)
    request,scope,reply=captured[0]
    rows=tuple(m for m in moved.movement_segments if m.job_id=='d-later')
    assert rows and all(m.start_ms>reply.run.elapsed_ms and m.end_ms<=moved.run.elapsed_ms for m in rows)
    assert next(v for v in annotated.vehicle_states if v.fleet_id=='fleet:truck:05').position_m!=next(v for v in moved.vehicle_states if v.fleet_id=='fleet:truck:05').position_m
    assert next(j for j in annotated.transport_jobs if j.id=='a-west')==next(j for j in moved.transport_jobs if j.id=='a-west')
    assert annotated.attachments==moved.attachments
    before=sql_fingerprint(database)
    def forbidden(*args,**kwargs): raise AssertionError('exact annotation replay attempted state/planner reconstruction')
    with monkeypatch.context() as replay_patch:
        replay_patch.setattr(ts,'_context',forbidden)
        with Session(database) as session,session.begin():
            replay=original(session,request,scope)
            assert replay.replayed and replay.model_copy(update={'replayed':False})==reply
            with pytest.raises(ServiceError) as changed: original(session,request.model_copy(update={'primary_blocking_resource_id':'changed-valid-primary'}),scope)
            assert changed.value.code=='idempotency_conflict'
    assert sql_fingerprint(database)==before
    before_http=capture_http(database,tmp_path/'input',moved.run.id,tmp_path/'http-before')
    reference_path=tmp_path/'reference.sqlite'
    with sqlite3.connect(database.url.database) as a,sqlite3.connect(reference_path) as b:a.backup(b)
    reference=create_engine('sqlite:///'+str(reference_path))
    execute_many(reference,intents,1600000,'r6:restart-retained')
    restart_advance(database,intents,1600000,'r6:restart-retained',tmp_path/'restart')
    after_http=capture_http(database,tmp_path/'input',moved.run.id,tmp_path/'http-after')
    with Session(database) as session: after=service.load_snapshot(session)
    assert after.events[:len(moved.events)]==moved.events
    assert sql_fingerprint(reference)==sql_fingerprint(database)
    baseline=max(e.sequence for e in after.events if e.event_type=='JOB_ASSIGNED')
    normalized=normalize_traffic(database,intents,baseline)
    assert normalized.content==normalize_traffic(reference,intents,baseline).content
    with database.connect() as conn:
        assert conn.execute(text('PRAGMA integrity_check')).scalar_one()=='ok'
        assert conn.execute(text('PRAGMA foreign_key_check')).all()==[]
    assert json.loads(before_http[0])['run']['id']==json.loads(after_http[0])['run']['id']==after.run.id
    assert json.loads(after_http[0])==json.loads(after_http[2])
    bounds=assert_continuous_clearance(after,focused.verified.world,focused.initial_snapshot,1600000)
    (tmp_path/'proof.json').write_text(json.dumps({'annotation_at_ms':reply.run.elapsed_ms,'later_actor_actual_windows':[(m.start_ms,m.end_ms) for m in rows],'exact_child_replay_after_actual_move':True,'replay_reconstructed_state':False,'collision_bounds':bounds,'all_sql_restart_identical':True,'held_job_custody_retained':True,'fk_integrity':'ok'},indent=2))
    (tmp_path/'annotation-request.json').write_text(request.model_dump_json(indent=2))
    (tmp_path/'normalized.json').write_text(normalized.content);(tmp_path/'raw.json').write_text(normalized.raw_json);(tmp_path/'bijection.json').write_text(normalized.mapping_json)
    reference.dispose()


@pytest.mark.parametrize('kind',['mid_edge','arbitrary_blocked'])
def test_r6_annotation_rejects_actual_ineligible_blocked_jobs_atomically(database,traffic_bundle,tmp_path,kind):
    import json
    from app.operations import traffic_service as ts,service_v3 as service
    from app.operations.bundle_registry import ServiceError
    from factory_traffic_bundle import execute_many,sql_fingerprint
    intents=_d5_late_hold(database,traffic_bundle,tmp_path,committed=False)
    if kind=='mid_edge': execute_many(database,intents,100000,'r6:actual-mid-edge')
    writer_rejection=None
    if kind=='mid_edge':
        writer_before=sql_fingerprint(database)
        with pytest.raises(ServiceError) as interrupted:
            with Session(database) as session,session.begin():
                state=service.load_snapshot(session);context=ts._context(session,state)
                job=next(j for j in state.transport_jobs if j.id=='a-west')
                assert job.status=='EMPTY_APPROACH'
                origin=next(o for o in context.phase_origins if o.job_id==job.id)
                assert origin.movements[-1].start_ms<state.run.elapsed_ms<origin.movements[-1].end_ms
                ts._send(session,context,intents[0],target='BLOCKED',reason='traffic:corridor_boundary')
        assert 'safe stop pose differs' in str(interrupted.value)
        assert sql_fingerprint(database)==writer_before
        writer_rejection=str(interrupted.value)
    else:
        with Session(database) as session,session.begin():
            state=service.load_snapshot(session)
            ts._send(session,ts._context(session,state),intents[0],target='BLOCKED',reason='operator:hold')
    with Session(database) as session:
        state=service.load_snapshot(session)
        held=next((e for e in reversed(state.events) if e.event_type=='JOB_BLOCKED' and e.payload.job_id=='a-west'),None)
        assert next(j.status for j in state.transport_jobs if j.id=='a-west')==('EMPTY_APPROACH' if kind=='mid_edge' else 'BLOCKED')
        outer=ts.TrafficCommand(run_id=state.run.id,expected_revision=state.run.revision,command_id='r6:ineligible',target_ms=state.run.elapsed_ms,intents=intents)
        request=ts._TrafficTerminal(action='annotate_traffic_terminal',run_id=state.run.id,expected_revision=state.run.revision,command_id=ts._semantic_id(intents[0],state.run.elapsed_ms,'terminal_annotation:occupied_until_deadline'),job_id='a-west',held_event_id=held.id if held else 'no-held-event',intents=intents,reason_code='occupied_until_deadline',primary_blocking_resource_id='fleet:locomotive:02')
        scope=ts._TrafficScope(outer,state.run.event_sequence)
    before=sql_fingerprint(database)
    with pytest.raises(ServiceError) as rejected:
        with Session(database) as session,session.begin(): ts._annotate_terminal(session,request,scope)
    assert rejected.value.code=='invalid_contract' and sql_fingerprint(database)==before
    assert ('assigned blocked job' if kind=='mid_edge' else 'latest safe corridor hold') in str(rejected.value)
    (tmp_path/'proof.json').write_text(json.dumps({'kind':kind,'actual_blocked_event':None if held is None else held.model_dump(mode='json'),'actual_mid_edge_block_writer_rejection':writer_rejection,'annotation_rejection':str(rejected.value),'all_sql_fingerprint_unchanged':True},indent=2))
