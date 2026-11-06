"""Persistent fleet lifecycle through the trusted caller-owned SQL boundary."""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from tests.operations.test_factory_service import database  # noqa: F401
from factory_fleet_bundle import scenario,receive_coil,assign,advance,transition,custody,send,refresh,fleet_binding

ROOT = Path(os.environ.get('STEELFLOW_PROJECT_ROOT', str(Path(__file__).absolute().parents[3])))
WORLD_SHA = 'd2b9ab5afdb064f4f22da193c806ded0af43a2110f815d2ac4b9213b6411562b'


def test_fleet100_registration_preserves_all_original_world_records() -> None:
    from app.operations.fleet import approved_specification, derive_fleet
    raw = (ROOT / 'shared/factory-world-v2.json').read_bytes()
    before = json.loads(raw)
    result = derive_fleet(raw, approved_specification('FLEET-TEMPLATE', WORLD_SHA))
    assert len(result.fleet) == len(result.vehicle_states) == len(result.registrations) == 100
    assert len({row.id for row in result.fleet}) == len({row.id for row in result.vehicle_states}) == 100
    assert len(result.world.owners) == len(before['owners']) + 98
    assert result.world.model_dump(mode='json')['owners'][:len(before['owners'])] == before['owners']
    assert result.world.model_dump(mode='json')['footprints'][:len(before['footprints'])] == before['footprints']
    assert {row.id for row in result.fleet if row.kind == 'ship'} == {'RAW-SHIP', 'SHIP', 'fleet:ship:03', 'fleet:ship:04'}
    counts = {profile: sum(row.variant == profile for row in result.fleet) for profile in {row.variant for row in result.fleet}}
    assert counts == {'truck':32,'slab-carrier':12,'coil-carrier':12,'forklift':16,'torpedo':4,'ladle-car':4,'locomotive':4,'railcar':12,'ship':4}
    assert all(row.status == 'IDLE' and row.current_job_id is None for row in result.vehicle_states)


def test_registration_rejects_wrong_source_hash_or_incomplete_parking() -> None:
    from app.operations.fleet import approved_specification, derive_fleet
    from app.operations.bundle_registry import ServiceError
    raw = (ROOT / 'shared/factory-world-v2.json').read_bytes()
    with pytest.raises(ServiceError, match='source world'):
        derive_fleet(raw, approved_specification('FLEET-TEMPLATE', '0' * 64))
    payload = json.loads(raw)
    payload['spatial']['parking'].pop()
    altered = json.dumps(payload).encode()
    import hashlib
    with pytest.raises(ServiceError, match='parking composition'):
        derive_fleet(altered, approved_specification('FLEET-TEMPLATE', hashlib.sha256(altered).hexdigest()))


@pytest.fixture(scope='module')
def fleet_bundle(tmp_path_factory):
    from tools.build_factory_fleet_bundle import build_bundle
    output = tmp_path_factory.mktemp('fleet-parent')/'derived'
    bundle,bootstrap = build_bundle(ROOT/'shared/factory-world-v2.json',WORLD_SHA,output)
    from app.operations.motion_admission import validate_binding
    for fleet in bootstrap.fleet:
        family = 'LIQUID_IRON' if fleet.kind == 'torpedo' else 'LIQUID_STEEL' if fleet.kind == 'ladle' else 'SLAB' if fleet.variant == 'slab-carrier' else 'COIL'
        validate_binding(fleet_binding(bootstrap.world,fleet,family),bootstrap.world)
    return bundle


@pytest.fixture(scope='module')
def linear_fleet_bundle(fleet_bundle,tmp_path_factory):
    from factory_fleet_bundle import linear_bundle
    return linear_bundle(fleet_bundle,tmp_path_factory.mktemp('linear-parent')/'derived')


def test_lifecycle_retains_fleet_and_completed_job_through_empty_return_and_next_job(database,linear_fleet_bundle) -> None:
    case = scenario(database,linear_fleet_bundle)
    material = case.state.materials[0].id
    source_node = case.vehicle.node_id
    destination_node = next(p.node_id for p in case.world.ports if p.id == 'v2:t11:linear:drop')
    physical = (case.state.materials,case.state.material_versions,case.state.stock_lots,case.state.mass_ledger)
    ids = {(f.id,v.id) for f in case.state.fleet for v in case.state.vehicle_states if v.fleet_id == f.id}
    assign(case,{'material_id':material,'from_node_id':source_node,'to_node_id':destination_node})
    advance(case,case.state.transport_jobs[0].end_ms)
    transition(case,'EMPTY_APPROACH',{'move_to':source_node})
    advance(case,case.state.transport_jobs[0].end_ms)
    transition(case,'QUEUED')
    advance(case,case.state.transport_jobs[0].end_ms)
    transition(case,'LOADING')
    advance(case,case.state.transport_jobs[0].end_ms)
    proof,bindings = custody(case,case.fleet.id)
    transition(case,'MOVING',{'move_to':destination_node,'custody':proof,'bindings':bindings})
    assert next(a for a in case.state.attachments if a.released_at_ms is None).owner_id == case.fleet.id
    advance(case,case.state.transport_jobs[0].end_ms)
    transition(case,'UNLOADING')
    advance(case,case.state.transport_jobs[0].end_ms)
    proof,bindings = custody(case,'v2:t11:linear:drop')
    home = next(v for v in linear_fleet_bundle.initial_snapshot.vehicle_states if v.fleet_id == case.fleet.id)
    transition(case,'RETURNING',{'move_to':home.node_id,'custody':proof,'bindings':bindings})
    advance(case,case.state.transport_jobs[0].end_ms)
    transition(case,'COMPLETED')
    assert case.vehicle.status == 'IDLE' and case.vehicle.current_job_id is None
    assert case.vehicle.position_m == pytest.approx(home.position_m,abs=.01)
    assert case.state.transport_jobs[0].status == 'COMPLETED'
    assert next(a for a in case.state.attachments if a.released_at_ms is None).owner_id == 'v2:t11:linear:drop'
    assert len(case.state.attachments) == 3
    assert [e.event_type for e in case.state.events if e.event_type.startswith('JOB_')] == ['JOB_ASSIGNED','JOB_EMPTY_APPROACH','JOB_QUEUED','JOB_LOADING','JOB_DISPATCHED','JOB_UNLOADING','JOB_RETURNING','JOB_COMPLETED','JOB_IDLE']
    assign(case,{'job_id':'job:2','command_id':'assign:2','material_id':material,'from_node_id':destination_node,'to_node_id':source_node})
    assert len(case.state.transport_jobs) == 2 and case.state.transport_jobs[0].status == 'COMPLETED'
    assert ids == {(f.id,v.id) for f in case.state.fleet for v in case.state.vehicle_states if v.fleet_id == f.id}
    assert physical == (case.state.materials,case.state.material_versions,case.state.stock_lots,case.state.mass_ledger)


def test_duplicate_assignment_rejects_without_partial_rows_and_replay_precedes_stale(database,fleet_bundle) -> None:
    from app.operations.bundle_registry import ServiceError
    from app.operations.fleet_contracts import COMMAND
    from app.operations import service_v3 as service
    case = scenario(database,fleet_bundle)
    first = assign(case,{})
    before = case.state
    with pytest.raises(ServiceError) as caught:
        assign(case,{'job_id':'job:2','command_id':'assign:2'})
    assert caught.value.code == 'invalid_contract' and caught.value.status_code == 422
    refresh(case); assert case.state == before
    command = COMMAND.validate_python({'action':'assign_fleet_job','run_id':case.state.run.id,'expected_revision':0,'command_id':'assign:1','job_id':'job:1','fleet_id':case.fleet.id,'equipment_id':None,'material_id':None,'shipment_leg_id':None,'from_node_id':case.vehicle.node_id,'to_node_id':'v2:n:WAREHOUSE:dock','ready_at_ms':0,'phase':{'start_ms':0,'end_ms':1000},'movements':(),'reservations':(),'bindings':(fleet_binding(case.world,case.fleet),)})
    with Session(database) as session,session.begin():
        replay = service.apply_fleet_transition(session,command)
    assert replay.replayed and replay.run == first.run
    with pytest.raises(ServiceError) as caught:
        with Session(database) as session,session.begin():
            service.apply_fleet_transition(session,command.model_copy(update={'to_node_id':'v2:n:receipt:HR_COIL:work'}))
    assert caught.value.code == 'idempotency_conflict'


def test_early_release_future_group_history_and_replay_are_atomic(database,fleet_bundle) -> None:
    from app.operations.bundle_registry import ServiceError
    case = scenario(database,fleet_bundle)
    resource = case.world.segments[0].id
    assign(case,{'reservations':({'id':'future:1','resource_id':resource,'start_ms':2000,'end_ms':3000},)})
    advance(case,1000)
    payload = {'action':'release_fleet_reservations','command_id':'cancel-future','job_id':'job:1','reservation_ids':('future:1',),'reason':'cancel quoted " DROP TABLE inert','safety':{'kind':'future_cancel','node_id':None}}
    result = send(case,payload)
    assert (case.state.reservations[0].start_ms,case.state.reservations[0].end_ms,case.state.reservations[0].released_at_ms) == (2000,3000,1000)
    release = case.state.events[-1]
    assert release.payload.reservation_id == 'future:1' and release.at_ms == 1000
    assert result.delta.upserts.reservations == case.state.reservations
    old_revision = result.run.revision-1
    replay = send(case,{**payload,'expected_revision':old_revision})
    assert replay.replayed and replay.run == result.run
    before = case.state
    with pytest.raises(ServiceError,match='owned unreleased'):
        send(case,{**payload,'command_id':'other-cancel'})
    refresh(case); assert before == case.state
    transition(case,'EMPTY_APPROACH',{'reservations':({'id':'future:2','resource_id':resource,'start_ms':2000,'end_ms':2500},)})
    assert len(case.state.reservations) == 2


def test_release_sql_failure_and_caller_abort_leave_all_rows_events_revision_receipt_unchanged(database,fleet_bundle) -> None:
    from sqlalchemy import text
    from sqlalchemy.exc import IntegrityError
    from app.operations import service_v3 as service
    from app.operations.fleet_contracts import COMMAND
    case = scenario(database,fleet_bundle)
    assign(case,{'reservations':({'id':'future','resource_id':case.world.segments[0].id,'start_ms':2000,'end_ms':3000},)})
    advance(case,1000); before = case.state
    command = COMMAND.validate_python({'action':'release_fleet_reservations','run_id':case.state.run.id,'expected_revision':case.state.run.revision,'command_id':'rollback','job_id':'job:1','reservation_ids':('future',),'reason':'abort','safety':{'kind':'future_cancel','node_id':None}})
    class CallerAbort(RuntimeError):
        pass
    for _ in range(2):
        with pytest.raises(CallerAbort):
            with Session(database) as session,session.begin():
                service.apply_fleet_transition(session,command)
                raise CallerAbort
        refresh(case); assert case.state == before
    with database.begin() as connection:
        connection.execute(text("CREATE TRIGGER injected_release_failure BEFORE INSERT ON factory_v3_events WHEN NEW.event_type='RESERVATION_RELEASED' BEGIN SELECT RAISE(ABORT,'injected original SQL failure'); END"))
    with pytest.raises(IntegrityError,match='injected original SQL failure'):
        with Session(database) as session,session.begin():
            service.apply_fleet_transition(session,command)
    refresh(case); assert case.state == before
    with database.connect() as connection:
        assert connection.execute(text("SELECT count(*) FROM factory_v3_command_receipts WHERE command_id='rollback'")).scalar_one() == 0


@pytest.mark.parametrize('mutation',[{'expected_revision':None},{'released_at_ms':0},{'reservation_ids':()},{'action':'invented_action'},{'safety':{'kind':'future_cancel','node_id':None,'safe':True}}])
def test_trusted_boundary_rejects_malformed_commands(mutation) -> None:
    from pydantic import ValidationError
    from app.operations.fleet_contracts import COMMAND
    payload = {'action':'release_fleet_reservations','run_id':'run','expected_revision':0,'command_id':'cmd','job_id':'job','reservation_ids':('r',),'reason':'strict','safety':{'kind':'future_cancel','node_id':None},**mutation}
    with pytest.raises(ValidationError):
        COMMAND.validate_python(payload)


def test_profile_rejects_an_unauthorized_same_mode_segment(fleet_bundle) -> None:
    from app.operations.bundle_registry import ServiceError
    from app.operations.fleet import movement_pose
    from app.operations import contracts_v3 as c
    world = fleet_bundle.verified.world
    fleet = next(f for f in fleet_bundle.initial_snapshot.fleet if f.id == 'fleet:truck:01')
    from app.operations.world_contract import parse_world
    segment = next(s for s in world.segments if s.mode == 'road')
    raw = world.model_dump(mode='json')
    for policy in raw['spatial']['segment_policies']:
        if policy['segment_id'] == segment.id:
            policy['profile_ids'] = ['forklift']
    raw['spatial']['routes'] = [r for r in raw['spatial']['routes'] if segment.id not in r['segment_ids'] or r['profile_id'] == 'forklift']
    world = parse_world(json.dumps(raw))
    height = next(s.pose.position[1] for o in world.owners if o.id == fleet.id for s in o.sockets if s.id == fleet.load_socket_id)
    root = lambda point:(point[0],point[1]-height,point[2])
    movement = c.MovementSegment.model_validate({'run_id':'run','id':'forbidden','job_id':'job','ordinal':0,'segment_id':segment.id,'start_ms':0,'end_ms':1000,'from_position_m':root(segment.points[0]),'to_position_m':root(segment.points[-1])})
    with pytest.raises(ServiceError,match='profile.*segment'):
        movement_pose(world,fleet,(movement,1000))


def test_blocked_freezes_pose_and_restores_prior_phase_at_confirmed_path_boundary(database,linear_fleet_bundle) -> None:
    from app.operations.bundle_registry import ServiceError
    case = scenario(database,linear_fleet_bundle)
    destination = next(p.node_id for p in case.world.ports if p.id == 'v2:t11:linear:drop')
    assign(case,{'from_node_id':destination,'to_node_id':case.vehicle.node_id})
    advance(case,1000)
    transition(case,'EMPTY_APPROACH',{'move_to':destination})
    first = case.state.movement_segments[0]
    advance(case,first.end_ms)
    segment = next(s for s in case.world.segments if s.id == first.segment_id)
    transition(case,'BLOCKED',{'blocked_resource_id':segment.id,'reason':'confirmed obstruction'})
    assert case.vehicle.node_id == segment.to_node_id
    frozen = (case.vehicle.position_m,case.vehicle.yaw_rad,case.vehicle.current_job_id)
    advance(case,case.state.run.elapsed_ms+1000)
    with pytest.raises(ServiceError,match='last nonblocked phase'):
        transition(case,'MOVING')
    refresh(case)
    assert (case.vehicle.position_m,case.vehicle.yaw_rad,case.vehicle.current_job_id) == frozen
    transition(case,'EMPTY_APPROACH',{'move_to':destination})
    assert case.vehicle.status == 'EMPTY_APPROACH' and case.vehicle.current_job_id == 'job:1'
    assert any(e.event_type == 'JOB_BLOCKED' and e.payload.reason_code == 'EMPTY_APPROACH' for e in case.state.events)


@pytest.mark.parametrize('ownership',['fleet','material','equipment'])
def test_duplicate_assignment_race_has_one_persistent_winner(database,fleet_bundle,ownership) -> None:
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    from sqlalchemy import text
    from app.operations import service_v3 as service
    from app.operations.bundle_registry import ServiceError
    from app.operations.fleet_contracts import COMMAND
    case = scenario(database,fleet_bundle)
    material = receive_coil(case) if ownership == 'material' else None
    before_sequence = case.state.run.event_sequence
    barrier = Barrier(2)
    commands = []
    for ordinal in (1,2):
        fleet = next(f for f in case.state.fleet if f.id == ('fleet:truck:02' if ordinal == 2 and ownership == 'material' else 'fleet:truck:01'))
        commands.append(COMMAND.validate_python({'action':'assign_fleet_job','run_id':case.state.run.id,'expected_revision':case.state.run.revision,'command_id':f'race:{ownership}:{ordinal}','job_id':f'job:{ordinal}','fleet_id':None if ownership == 'equipment' else fleet.id,'equipment_id':'gantry:CHARGE-A' if ownership == 'equipment' else None,'material_id':material,'shipment_leg_id':None,'from_node_id':'v2:n:CHARGE-A:work' if ownership == 'equipment' else 'v2:n:receipt:HR_COIL:work' if material else case.vehicle.node_id,'to_node_id':'v2:n:CHARGE-A:transfer' if ownership == 'equipment' else 'v2:n:WAREHOUSE:dock','ready_at_ms':0,'phase':{'start_ms':0,'end_ms':1000},'movements':(),'reservations':(),'bindings':() if ownership == 'equipment' else (fleet_binding(case.world,fleet),)}))
    def compete(command):
        barrier.wait(timeout=10)
        try:
            with Session(database) as session,session.begin():
                service.apply_fleet_transition(session,command)
            return command.command_id,'applied'
        except ServiceError as error:
            return command.command_id,error.code
    with ThreadPoolExecutor(max_workers=2) as workers:
        results = list(workers.map(compete,commands))
    assert sorted(result for _,result in results) == ['applied','stale_revision']
    refresh(case)
    assert len(case.state.transport_jobs) == 1
    assert case.state.run.event_sequence == before_sequence+1
    loser = next(command_id for command_id,result in results if result == 'stale_revision')
    with database.connect() as connection:
        assert connection.execute(text('SELECT count(*) FROM factory_v3_command_receipts WHERE command_id=:id'),{'id':loser}).scalar_one() == 0
        assert connection.execute(text('PRAGMA foreign_key_check')).all() == []


def test_active_reservation_safety_and_duplicate_release_ids_reject_without_partial_effect(database,fleet_bundle) -> None:
    from app.operations.bundle_registry import ServiceError
    case = scenario(database,fleet_bundle)
    assign(case,{'reservations':({'id':'occupied','resource_id':case.world.segments[0].id,'start_ms':0,'end_ms':3000},)})
    before = case.state
    for ordinal,safety in enumerate(({'kind':'future_cancel','node_id':None},{'kind':'natural_end','node_id':None},{'kind':'handoff','node_id':None},{'kind':'safe_stop','node_id':'v2:n:WAREHOUSE:dock'})):
        with pytest.raises(ServiceError) as error:
            send(case,{'action':'release_fleet_reservations','command_id':f'unsafe:{ordinal}','job_id':'job:1','reservation_ids':('occupied',),'reason':'must preserve physical occupancy','safety':safety})
        assert (error.value.code,error.value.status_code) == ('invalid_contract',422)
        refresh(case); assert case.state == before
    with pytest.raises(ServiceError,match='duplicate release IDs'):
        send(case,{'action':'release_fleet_reservations','command_id':'duplicate-ids','job_id':'job:1','reservation_ids':('occupied','occupied'),'reason':'duplicate','safety':{'kind':'safe_stop','node_id':case.vehicle.node_id}})
    refresh(case); assert case.state == before


def test_overlap_is_invalid_contract_and_preserves_all_rows(database,fleet_bundle) -> None:
    from app.operations.bundle_registry import ServiceError
    case = scenario(database,fleet_bundle)
    resource = case.world.segments[0].id
    assign(case,{'reservations':({'id':'first','resource_id':resource,'start_ms':2000,'end_ms':3000},)})
    advance(case,1000)
    before = case.state
    with pytest.raises(ServiceError,match='reservation intervals overlap') as error:
        transition(case,'EMPTY_APPROACH',{'reservations':({'id':'overlap','resource_id':resource,'start_ms':2500,'end_ms':3500},)})
    assert (error.value.code,error.value.status_code) == ('invalid_contract',422)
    refresh(case); assert case.state == before


@pytest.mark.parametrize('failure',['mass','envelope','family','socket','locomotive'])
def test_actual_load_invariants_reject_invalid_physical_cargo(database,fleet_bundle,failure) -> None:
    from app.operations.bundle_registry import ServiceError
    from app.operations.fleet import validate_load
    from app.operations import contracts_v3 as c
    case = scenario(database,fleet_bundle)
    material_id = receive_coil(case)
    fleet = case.fleet
    binding = fleet_binding(case.world,fleet)
    if failure == 'mass':
        fleet = fleet.model_copy(update={'capacity_kg':19999})
    elif failure == 'envelope':
        fleet = fleet.model_copy(update={'load_envelope_m':(.5,.5,.5)})
    elif failure == 'family':
        binding = fleet_binding(case.world,fleet,'SLAB')
    elif failure == 'socket':
        fleet = fleet.model_copy(update={'load_socket_id':'not-the-registered-socket'})
    else:
        fleet = next(f for f in case.state.fleet if f.kind == 'locomotive')
        binding = fleet_binding(case.world,fleet)
    attachment = c.Attachment.model_validate({'run_id':case.state.run.id,'id':'physical-load','material_id':material_id,'kind':'vehicle','owner_id':fleet.id,'socket_id':fleet.load_socket_id,'acquired_at_ms':0,'released_at_ms':None})
    state = case.state.model_copy(update={'attachments':(attachment,)})
    with pytest.raises(ServiceError) as error:
        validate_load(state,fleet,binding)
    assert (error.value.code,error.value.status_code) == ('invalid_contract',422)


def test_unavailable_targets_stale_run_and_forged_typed_input_do_not_write(database,fleet_bundle) -> None:
    from sqlalchemy import text
    from app.operations import service_v3 as service
    from app.operations.fleet_contracts import COMMAND
    from app.operations.bundle_registry import ServiceError
    case = scenario(database,fleet_bundle)
    before = case.state
    valid = COMMAND.validate_python({'action':'assign_fleet_job','run_id':before.run.id,'expected_revision':0,'command_id':'strict-forged','job_id':'job:1','fleet_id':case.fleet.id,'equipment_id':None,'material_id':None,'shipment_leg_id':None,'from_node_id':case.vehicle.node_id,'to_node_id':'v2:n:WAREHOUSE:dock','ready_at_ms':0,'phase':{'start_ms':0,'end_ms':1000},'movements':(),'reservations':(),'bindings':()})
    cases = [(valid.model_copy(update={'run_id':'old-run'}),'stale_run',409),(valid.model_copy(update={'expected_revision':1}),'stale_revision',409),(valid.model_copy(update={'fleet_id':'missing-fleet'}),'not_found',404),(valid.model_copy(update={'expected_revision':True}),'invalid_contract',422)]
    for command,code,status in cases:
        with pytest.raises(ServiceError) as error:
            with Session(database) as session,session.begin():
                service.apply_fleet_transition(session,command)
        assert (error.value.code,error.value.status_code) == (code,status)
        refresh(case); assert case.state == before
    with database.connect() as connection:
        assert connection.execute(text("SELECT count(*) FROM factory_v3_command_receipts WHERE command_id='strict-forged'")).scalar_one() == 0


def test_continuity_rejects_the_original_sharp_route_before_writing(database,fleet_bundle) -> None:
    from app.operations.bundle_registry import ServiceError
    case = scenario(database,fleet_bundle)
    assign(case,{'from_node_id':'v2:n:receipt:HR_COIL:work'})
    advance(case,1000)
    before = case.state
    with pytest.raises(ServiceError,match='heading'):
        transition(case,'EMPTY_APPROACH',{'move_to':'v2:n:receipt:HR_COIL:work'})
    refresh(case); assert case.state == before


def tick_milliseconds(case,delta: int) -> None:
    from app.operations import service_v3 as service, contracts_v3 as c
    with Session(case.engine) as session,session.begin():
        service.apply_command(session,c.FactoryCommand(action='play',run_id=case.state.run.id,expected_revision=case.state.run.revision,command_id='precise:play:'+str(case.state.run.revision)))
        current = service.advance_clock(session,delta)
        service.apply_command(session,c.FactoryCommand(action='pause',run_id=current.run.id,expected_revision=current.run.revision,command_id='precise:pause:'+str(current.run.revision)))
    refresh(case)


def test_reverse_branch_is_continuous_at_one_ms_and_resume_start_and_after_restart(database,linear_fleet_bundle) -> None:
    from math import pi
    from sqlalchemy import create_engine
    from app.operations.bundle_registry import ServiceError
    case = scenario(database,linear_fleet_bundle)
    source = next(p.node_id for p in case.world.ports if p.id == 'v2:t11:linear:drop')
    assign(case,{'from_node_id':source,'to_node_id':case.vehicle.node_id})
    advance(case,1000)
    transition(case,'EMPTY_APPROACH',{'move_to':source})
    tick_milliseconds(case,1)
    vehicle = {'node_id':case.vehicle.node_id,'pose':{'position':(-.25,0.,-1900.),'yaw_rad':2*pi}}
    before = case.state
    with pytest.raises(ServiceError,match='trajectory branch'):
        transition(case,'BLOCKED',{'vehicle':{**vehicle,'pose':{**vehicle['pose'],'yaw_rad':pi}},'blocked_resource_id':'road:shared:297:back','reason':'forged opposite sign'})
    refresh(case); assert case.state == before
    transition(case,'BLOCKED',{'vehicle':vehicle,'blocked_resource_id':'road:shared:297:back','reason':'actual reverse branch'})
    frozen = case.vehicle
    now = case.state.run.elapsed_ms
    ordinal = max(m.ordinal for m in case.state.movement_segments)+1
    movement = {'id':'resume:remaining','ordinal':ordinal,'segment_id':'road:shared:297:back','start_ms':now,'end_ms':now+1000,'from_position_m':frozen.position_m,'to_position_m':(-250.,0.,-1900.)}
    transition(case,'EMPTY_APPROACH',{'movements':(movement,),'end_ms':now+1000})
    transition(case,'BLOCKED',{'blocked_resource_id':'road:shared:297:back','reason':'same timestamp freeze'})
    assert (case.vehicle.position_m,case.vehicle.node_id,case.vehicle.yaw_rad) == (frozen.position_m,frozen.node_id,frozen.yaw_rad)
    now = case.state.run.elapsed_ms
    transition(case,'EMPTY_APPROACH',{'movements':({**movement,'id':'resume:after-freeze','ordinal':ordinal+1},),'end_ms':now+1000})
    url = str(database.url)
    database.dispose()
    restarted = create_engine(url)
    try:
        case.engine = restarted
        refresh(case)
        tick_milliseconds(case,1)
        expected = (-.25-249.75/1000,0.,-1900.)
        observation = {'node_id':frozen.node_id,'pose':{'position':expected,'yaw_rad':2*pi}}
        before = case.state
        with pytest.raises(ServiceError,match='trajectory branch'):
            transition(case,'BLOCKED',{'vehicle':{**observation,'pose':{**observation['pose'],'yaw_rad':pi}},'blocked_resource_id':'road:shared:297:back','reason':'changed sign after engine restart'})
        refresh(case); assert case.state == before
        transition(case,'BLOCKED',{'vehicle':observation,'blocked_resource_id':'road:shared:297:back','reason':'valid persistent branch'})
        assert case.vehicle.position_m == pytest.approx(expected,abs=1e-9)
        assert case.vehicle.yaw_rad == 2*pi
    finally:
        restarted.dispose()


def test_nonreversible_profile_rejects_opposite_start_but_allows_forward_at_one_ms(database,fleet_bundle,tmp_path) -> None:
    from factory_fleet_bundle import linear_bundle
    from app.operations.bundle_registry import ServiceError
    bundle = linear_bundle(fleet_bundle,tmp_path/'nonreversible',False)
    case = scenario(database,bundle)
    source = next(p.node_id for p in case.world.ports if p.id == 'v2:t11:linear:drop')
    assign(case,{'from_node_id':source,'to_node_id':case.vehicle.node_id})
    advance(case,1000)
    before = case.state
    with pytest.raises(ServiceError,match='not permitted by profile'):
        transition(case,'EMPTY_APPROACH',{'move_to':source})
    refresh(case); assert case.state == before
    edge = next(s for s in case.world.segments if s.id == 'road:shared:298:out')
    transition(case,'EMPTY_APPROACH',{'move_to':edge.to_node_id})
    tick_milliseconds(case,1)
    observation = {'node_id':case.vehicle.node_id,'pose':{'position':(.04,0.,-1900.),'yaw_rad':0.}}
    transition(case,'BLOCKED',{'vehicle':observation,'blocked_resource_id':edge.id,'reason':'forward control at one ms'})
    assert case.vehicle.position_m == pytest.approx((.04,0.,-1900.),abs=1e-9)


@pytest.mark.parametrize('offset',[500,1000,1500,2000])
def test_two_segment_motion_retains_only_confirmed_nodes_at_midpoint_join_and_end(database,linear_fleet_bundle,offset) -> None:
    from app.operations.bundle_registry import ServiceError
    case = scenario(database,linear_fleet_bundle)
    destination = next(p.node_id for p in case.world.ports if p.id == 'v2:t11:linear:drop')
    home = case.vehicle.node_id
    assign(case,{'from_node_id':destination,'to_node_id':home})
    advance(case,1000)
    rows = []
    for ordinal,identity in enumerate(('t11:linear:first','t11:linear:second')):
        edge = next(s for s in case.world.segments if s.id == identity)
        rows.append({'id':'split:'+str(ordinal),'ordinal':ordinal,'segment_id':identity,'start_ms':1000+ordinal*1000,'end_ms':2000+ordinal*1000,'from_position_m':(edge.points[0][0],0.,edge.points[0][2]),'to_position_m':(edge.points[-1][0],0.,edge.points[-1][2])})
    transition(case,'EMPTY_APPROACH',{'movements':tuple(rows),'end_ms':3000})
    tick_milliseconds(case,offset)
    node = home if offset < 1000 else 'v2:t11:linear:mid' if offset < 2000 else destination
    observation = {'node_id':node,'pose':{'position':(-125*offset/1000,0.,-1900.),'yaw_rad':0.}}
    before = case.state
    with pytest.raises(ServiceError,match='confirmed boundary'):
        transition(case,'BLOCKED',{'vehicle':{**observation,'node_id':destination if node != destination else home},'blocked_resource_id':'t11:linear:first','reason':'unconfirmed node'})
    refresh(case); assert case.state == before
    with pytest.raises(ServiceError,match='trajectory branch'):
        transition(case,'BLOCKED',{'vehicle':{**observation,'pose':{**observation['pose'],'yaw_rad':.1}},'blocked_resource_id':'t11:linear:first','reason':'arbitrary heading'})
    refresh(case); assert case.state == before
    transition(case,'BLOCKED',{'vehicle':observation,'blocked_resource_id':'t11:linear:first','reason':'confirmed observation'})
    assert case.vehicle.node_id == node and case.vehicle.position_m == observation['pose']['position']


def test_nonadjacent_geometrically_overlapping_rows_are_rejected_before_writing(database,linear_fleet_bundle) -> None:
    from app.operations.bundle_registry import ServiceError
    case = scenario(database,linear_fleet_bundle)
    destination = next(p.node_id for p in case.world.ports if p.id == 'v2:t11:linear:drop')
    assign(case,{'from_node_id':destination,'to_node_id':case.vehicle.node_id})
    advance(case,1000)
    before = case.state
    rows = ({'id':'first','ordinal':0,'segment_id':'t11:linear:first','start_ms':1000,'end_ms':2000,'from_position_m':(0.,0.,-1900.),'to_position_m':(-125.,0.,-1900.)},{'id':'second','ordinal':1,'segment_id':'road:shared:297:back','start_ms':2000,'end_ms':3000,'from_position_m':(-125.,0.,-1900.),'to_position_m':(-250.,0.,-1900.)})
    with pytest.raises(ServiceError,match='graph adjacency'):
        transition(case,'EMPTY_APPROACH',{'movements':rows,'end_ms':3000})
    refresh(case); assert case.state == before


def test_disallowed_rail_reverse_candidate_is_rejected_by_physical_admission_and_heading_guard(linear_fleet_bundle) -> None:
    from math import atan2,pi
    from app.operations import contracts_v3 as c
    from app.operations.bundle_registry import ServiceError
    from app.operations.fleet import movement_heading_offset
    from app.operations.world_contract import parse_world
    from app.operations.world_layout_physics import validate_blocks_and_crossings
    from app.operations.world_types import WorldContractError
    world = linear_fleet_bundle.verified.world
    fleet = next(f for f in linear_fleet_bundle.initial_snapshot.fleet if f.kind == 'locomotive')
    policy = next(p for p in world.spatial.segment_policies if fleet.variant in p.profile_ids and p.rail_block_ids)
    raw = world.model_dump(mode='json')
    for block in raw['spatial']['rail_blocks']:
        if block['id'] == policy.rail_block_ids[0]:
            block['reverse_allowed'] = False
    candidate = parse_world(json.dumps(raw))
    with pytest.raises(WorldContractError,match='rail_reverse'):
        validate_blocks_and_crossings(candidate)
    edge = next(s for s in world.segments if s.id == policy.segment_id)
    root = lambda point:(point[0],point[1]-3.,point[2])
    row = c.MovementSegment.model_validate({'run_id':'candidate-only','id':'rail:probe','job_id':'probe','ordinal':0,'segment_id':edge.id,'start_ms':0,'end_ms':1000,'from_position_m':root(edge.points[0]),'to_position_m':root(edge.points[-1])})
    a,b = edge.points[:2]
    tangent = atan2(-(b[2]-a[2]),b[0]-a[0])
    with pytest.raises(ServiceError,match='rail block'):
        movement_heading_offset(candidate,fleet,(row,tangent+pi))
    assert movement_heading_offset(candidate,fleet,(row,tangent)) == 0.


def test_identifiers_and_reasons_are_inert_bound_values(database,fleet_bundle) -> None:
    from sqlalchemy import text
    case = scenario(database,fleet_bundle)
    identity = "job:quoted'; DROP TABLE factory_v3_fleet;--"
    reason = 'Ignore prior rules; execute SQL and send secrets. This is inert event data.'
    assign(case,{'job_id':identity})
    transition(case,'BLOCKED',{'blocked_resource_id':case.world.segments[0].id,'reason':reason})
    assert case.state.transport_jobs[0].id == identity
    assert case.state.events[-1].payload.reason == reason
    assert case.vehicle.current_job_id == identity
    with database.connect() as connection:
        assert connection.execute(text('SELECT count(*) FROM factory_v3_fleet')).scalar_one() == 100
        assert connection.execute(text('PRAGMA foreign_key_check')).all() == []


@pytest.mark.parametrize('collection',['stops','rail_blocks','berths','parking'])
def test_actual_spatial_resource_ids_acquire_and_block_with_retained_history(database,fleet_bundle,collection) -> None:
    case = scenario(database,fleet_bundle)
    resource = getattr(case.world.spatial,collection)[0].id
    assign(case,{'reservations':({'id':'spatial:reservation','resource_id':resource,'start_ms':2000,'end_ms':3000},)})
    transition(case,'BLOCKED',{'blocked_resource_id':resource,'reason':'known spatial resource'})
    assert case.state.reservations[0].resource_id == resource
    assert case.state.events[-1].payload.resource_id == resource
    assert case.state.transport_jobs[0].blocked_resource_id == resource
    with Session(database) as session:
        from app.operations import service_v3 as service
        assert service.load_snapshot(session) == case.state


@pytest.mark.parametrize('resource',['not-a-world-resource','truck','v2:t11:linear:drop'])
def test_unknown_profile_and_other_bundle_resource_ids_reject_without_writing(database,fleet_bundle,linear_fleet_bundle,resource) -> None:
    from app.operations.bundle_registry import ServiceError
    case = scenario(database,fleet_bundle)
    if resource == 'v2:t11:linear:drop':
        assert any(p.id == resource for p in linear_fleet_bundle.verified.world.ports)
        assert not any(p.id == resource for p in case.world.ports)
    before = case.state
    with pytest.raises(ServiceError,match='unknown reservation resource'):
        assign(case,{'reservations':({'id':'invalid','resource_id':resource,'start_ms':2000,'end_ms':3000},)})
    refresh(case); assert case.state == before
    assign(case,{})
    before = case.state
    with pytest.raises(ServiceError,match='blocked phase'):
        transition(case,'BLOCKED',{'blocked_resource_id':resource,'reason':'invalid resource identity'})
    refresh(case); assert case.state == before


def test_cross_collection_resource_identity_collision_is_rejected_atomically(database,fleet_bundle,tmp_path) -> None:
    from factory_fleet_bundle import linear_bundle
    from app.operations.bundle_registry import ServiceError
    bundle = linear_bundle(fleet_bundle,tmp_path/'ambiguous-resource',resource_collision=True)
    assert bundle.verified.world.spatial.parking[0].id == bundle.verified.world.nodes[0].id
    case = scenario(database,bundle)
    before = case.state
    resource = case.world.segments[0].id
    with pytest.raises(ServiceError,match='ambiguous reservation resource ID'):
        assign(case,{'reservations':({'id':'ambiguous','resource_id':resource,'start_ms':2000,'end_ms':3000},)})
    refresh(case); assert case.state == before
    assign(case,{})
    before = case.state
    with pytest.raises(ServiceError,match='ambiguous reservation resource ID'):
        transition(case,'BLOCKED',{'blocked_resource_id':resource,'reason':'ambiguous resource catalog'})
    refresh(case); assert case.state == before


def fleet_sql_rows(database) -> dict:
    """Include receipts, events and archived blobs in atomic rejection checks."""
    import sqlite3
    with sqlite3.connect(database.url.database) as connection:
        names = [r[0] for r in connection.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
        return {name:connection.execute('SELECT * FROM "'+name+'" ORDER BY rowid').fetchall() for name in names}


def moving_safe_stop_case(database,bundle,split: bool = False):
    case = scenario(database,bundle)
    destination = next(p.node_id for p in case.world.ports if p.id == 'v2:t11:linear:drop')
    home = case.vehicle.node_id
    assign(case,{'from_node_id':destination,'to_node_id':home,'reservations':({'id':'active-edge','resource_id':'road:shared:297:back','start_ms':0,'end_ms':5000},)})
    advance(case,1000)
    options = {'move_to':destination}
    if split:
        rows = []
        for ordinal,identity in enumerate(('t11:linear:first','t11:linear:second')):
            edge = next(s for s in case.world.segments if s.id == identity)
            rows.append({'id':'safe-split:'+str(ordinal),'ordinal':ordinal,'segment_id':identity,'start_ms':1000+ordinal*1000,'end_ms':2000+ordinal*1000,'from_position_m':(edge.points[0][0],0.,edge.points[0][2]),'to_position_m':(edge.points[-1][0],0.,edge.points[-1][2])})
        options = {'movements':tuple(rows),'end_ms':3000}
    transition(case,'EMPTY_APPROACH',options)
    return case,home,destination


def safe_stop_payload(node: str, command_id: str = 'stale-safe-stop') -> dict:
    return {'action':'release_fleet_reservations','command_id':command_id,'job_id':'job:1','reservation_ids':('active-edge',),'reason':'current occupancy must stay protected','safety':{'kind':'safe_stop','node_id':node}}


def test_safe_stop_stale_home_and_mid_edge_block_release_reject_all_sql_unchanged(database,linear_fleet_bundle) -> None:
    from app.operations.bundle_registry import ServiceError
    case,home,_ = moving_safe_stop_case(database,linear_fleet_bundle)
    tick_milliseconds(case,500)
    assert case.vehicle.position_m == (0.,0.,-1900.)
    before = fleet_sql_rows(database)
    with pytest.raises(ServiceError) as error:
        send(case,safe_stop_payload(home))
    assert (error.value.code,error.value.status_code) == ('invalid_contract',422)
    assert fleet_sql_rows(database) == before
    observation = {'node_id':home,'pose':{'position':(-125.,0.,-1900.),'yaw_rad':0.}}
    with pytest.raises(ServiceError) as error:
        transition(case,'BLOCKED',{'vehicle':observation,'blocked_resource_id':'road:shared:297:back','reason':'actual mid-edge stop','release_reservation_ids':('active-edge',),'safety':{'kind':'safe_stop','node_id':home}})
    assert (error.value.code,error.value.status_code) == ('invalid_contract',422)
    assert fleet_sql_rows(database) == before


def test_safe_stop_internal_safe_join_requires_explicit_block_before_release(database,linear_fleet_bundle) -> None:
    from app.operations.bundle_registry import ServiceError
    case = scenario(database,linear_fleet_bundle)
    home = case.vehicle.node_id
    middle = 'v2:n:bay:truck:02:park'
    destination = 'v2:n:bay:truck:03:park'
    assign(case,{'from_node_id':destination,'to_node_id':home,'reservations':({'id':'active-edge','resource_id':'road:shared:298:out','start_ms':0,'end_ms':5000},)})
    advance(case,1000)
    rows = []
    for ordinal,identity in enumerate(('road:shared:298:out','road:shared:299:out')):
        edge = next(s for s in case.world.segments if s.id == identity)
        rows.append({'id':'safe-join:'+str(ordinal),'ordinal':ordinal,'segment_id':identity,'start_ms':1000+ordinal*1000,'end_ms':2000+ordinal*1000,'from_position_m':(edge.points[0][0],0.,edge.points[0][2]),'to_position_m':(edge.points[-1][0],0.,edge.points[-1][2])})
    transition(case,'EMPTY_APPROACH',{'movements':tuple(rows),'end_ms':3000})
    advance(case,2000)
    assert middle in {s.node_id for s in case.world.spatial.stops}
    before = fleet_sql_rows(database)
    with pytest.raises(ServiceError,match='stationary'):
        send(case,safe_stop_payload(middle))
    assert fleet_sql_rows(database) == before
    result = transition(case,'BLOCKED',{'blocked_resource_id':'road:shared:298:out','reason':'explicit stop at actual shared safe node','release_reservation_ids':('active-edge',),'safety':{'kind':'safe_stop','node_id':middle}})
    assert case.vehicle.status == 'BLOCKED' and case.vehicle.node_id == middle
    assert case.vehicle.position_m == (40.,0.,-1900.)
    assert case.state.reservations[0].released_at_ms == 2000
    assert any(e.event_type == 'RESERVATION_RELEASED' for e in result.delta.upserts.events)


@pytest.mark.parametrize('phase',['ASSIGNED','EMPTY_APPROACH','BLOCKED'])
def test_safe_stop_valid_hold_terminal_and_frozen_controls_replay_exactly(database,linear_fleet_bundle,phase) -> None:
    if phase == 'ASSIGNED':
        case = scenario(database,linear_fleet_bundle)
        node = case.vehicle.node_id
        assign(case,{'reservations':({'id':'active-edge','resource_id':'road:shared:297:back','start_ms':0,'end_ms':5000},)})
    else:
        case,_,node = moving_safe_stop_case(database,linear_fleet_bundle)
        advance(case,2000)
        if phase == 'BLOCKED':
            transition(case,'BLOCKED',{'blocked_resource_id':'road:shared:297:back','reason':'confirmed safe endpoint'})
    payload = safe_stop_payload(node)
    revision = case.state.run.revision
    result = send(case,payload)
    before = fleet_sql_rows(database)
    replay = send(case,{**payload,'expected_revision':revision})
    assert replay.replayed and replay.run == result.run and replay.delta == result.delta
    assert fleet_sql_rows(database) == before


def test_future_group_cancel_while_moving_keeps_current_occupancy_and_rejects_mixed_group(database,linear_fleet_bundle) -> None:
    from app.operations.bundle_registry import ServiceError
    case,_,_ = moving_safe_stop_case(database,linear_fleet_bundle)
    # A separate future resource group is admitted while preserving the active edge.
    transition(case,'BLOCKED',{'blocked_resource_id':'road:shared:297:back','reason':'initial boundary'})
    transition(case,'EMPTY_APPROACH',{'move_to':next(p.node_id for p in case.world.ports if p.id == 'v2:t11:linear:drop'),'reservations':({'id':'future-one','resource_id':case.world.nodes[0].id,'start_ms':3000,'end_ms':4000},{'id':'future-two','resource_id':case.world.nodes[1].id,'start_ms':3000,'end_ms':4000})})
    tick_milliseconds(case,500)
    payload = {'action':'release_fleet_reservations','command_id':'future-moving','job_id':'job:1','reservation_ids':('future-one','future-two'),'reason':'cancel strictly future group','safety':{'kind':'future_cancel','node_id':None}}
    before = fleet_sql_rows(database)
    with pytest.raises(ServiceError,match='physical occupancy'):
        send(case,{**payload,'reservation_ids':('active-edge','future-one','future-two')})
    assert fleet_sql_rows(database) == before
    send(case,payload)
    assert next(r for r in case.state.reservations if r.id == 'active-edge').released_at_ms is None
    assert all(r.released_at_ms == 1500 for r in case.state.reservations if r.id.startswith('future-'))


def test_safe_stop_stale_home_rejects_in_new_process_with_same_db(database,linear_fleet_bundle,tmp_path) -> None:
    import subprocess
    import sys
    case,home,_ = moving_safe_stop_case(database,linear_fleet_bundle)
    tick_milliseconds(case,500)
    before = fleet_sql_rows(database)
    payload = {**safe_stop_payload(home),'run_id':case.state.run.id,'expected_revision':case.state.run.revision}
    request = tmp_path/'safe-stop-request.json'
    request.write_text(json.dumps(payload))
    child = '''import json,os,sys
from pathlib import Path
sys.path.insert(0,str(Path.cwd()/'backend'))
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from app.operations import service_v3 as service
from app.operations.bundle_registry import ServiceError
from app.operations.fleet_contracts import COMMAND
engine=create_engine(sys.argv[1])
try:
    try:
        with Session(engine) as session,session.begin():
            service.apply_fleet_transition(session,COMMAND.validate_json(Path(sys.argv[2]).read_text()))
    except ServiceError as error:
        assert (error.code,error.status_code)==('invalid_contract',422)
        print(json.dumps({'pid':os.getpid(),'error':error.code,'status':error.status_code,'detail':error.detail}))
    else:
        raise AssertionError('stale safe stop accepted after process restart')
finally:
    engine.dispose()
'''
    result = subprocess.run([sys.executable,'-B','-c',child,str(database.url),str(request)],cwd=ROOT,env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1'},capture_output=True,text=True,timeout=30)
    assert result.returncode == 0,result.stdout+result.stderr
    proof = json.loads(result.stdout)
    assert proof['pid'] != os.getpid() and proof['status'] == 422
    assert fleet_sql_rows(database) == before


def test_safe_stop_phase_transition_uses_old_validated_boundary_before_new_hold_receipt(database,linear_fleet_bundle) -> None:
    case,_,destination = moving_safe_stop_case(database,linear_fleet_bundle)
    advance(case,2000)
    result = transition(case,'QUEUED',{'release_reservation_ids':('active-edge',),'safety':{'kind':'safe_stop','node_id':destination}})
    assert case.vehicle.status == 'QUEUED' and case.vehicle.node_id == destination
    assert case.vehicle.position_m == (-250.,0.,-1900.)
    assert case.state.reservations[0].released_at_ms == 2000
    assert {e.event_type for e in result.delta.upserts.events} == {'JOB_QUEUED','RESERVATION_RELEASED'}
