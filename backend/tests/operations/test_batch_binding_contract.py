"""Strict existing binding-union preservation at the real transactional writer."""
from __future__ import annotations

import copy
import hashlib
import json
import math
from pathlib import Path

import pytest
from pydantic import TypeAdapter
from sqlalchemy import text, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.operations import batch_service, contracts_v3 as c, models_v3 as models, service_v3 as service
from app.operations.batch_contracts import BatchCompletion
from app.operations.bundle_registry import ServiceError, admit_contract_test
from app.operations.motion_bindings import AssetBinding, AssetBindingValue, InternalFeedAssetBinding, LiftedInternalFeedBinding
from app.operations.stock_contracts import event
from tests.operations.factory_batch_bundle import apply, binding, build_bundle, completion, load, sql_state, stock_state
from tests.operations.test_factory_service import database  # noqa: F401

ROOT = Path(__file__).resolve().parents[3]
GO06 = json.loads((ROOT / 'tests/fixtures/finishing/go06-batch-binding.json').read_text())


def dimensions(length: float):
    """Declared synthetic strip dimensions; no generated asset is needed."""
    return {'length_mm':length*1000,'width_mm':1200,'thickness_mm':GO06['thickness_m']*1000,'diameter_mm':None,'inner_diameter_mm':None}


def go_bundle(target: Path):
    """Extend the existing exact-world test bundle with one closed GO06 case."""
    template=build_bundle(target/'template',(800,1));domain=template.verified.collections.model_dump(mode='json');run=template.initial_snapshot.run.model_dump(mode='json');world=template.verified.world.model_dump(mode='json');owner=next(o for o in world['owners'] if o['id']==GO06['source_owner_id']);ports=[]
    parsed=TypeAdapter(AssetBindingValue).validate_python(GO06['binding'])
    assert isinstance(parsed,InternalFeedAssetBinding) and parsed.owner_id=='CS-GO-06'
    for socket in parsed.sockets:
        if not any(s['id']==socket.socket_id for s in owner['sockets']):owner['sockets'].append({'id':socket.socket_id,'pose':{'position':list(socket.position_m),'yaw_rad':0}})
    for socket_id in ['cutter_in_support','intermediate_strip_support']:
        socket=next(s for s in parsed.sockets if s.socket_id==socket_id);x,y,z=socket.position_m;yaw=owner['pose']['yaw_rad'];ox,oy,oz=owner['pose']['position'];node_id='v2:binding-test:GO06:node:'+socket_id;port_id='v2:binding-test:GO06:port:'+socket_id
        world['nodes'].append({'id':node_id,'position':[ox+math.cos(yaw)*x+math.sin(yaw)*z,oy+y,oz-math.sin(yaw)*x+math.cos(yaw)*z],'modes':['roller']})
        world['ports'].append({'id':port_id,'owner_id':parsed.owner_id,'socket_id':socket_id,'node_id':node_id,'capacity_kg':60000,'modes':['roller']});ports.append(port_id)
    ident='synthetic:binding-test:GO06:stock';version=ident+':v1';form=GO06['form']
    domain['stock_lots'].append({'run_id':run['id'],'id':ident,'source_kind':'OPENING','grade':'SYNTHETIC-CS','form':form,'quantity_kg':800,'received_at_ms':0})
    domain['materials'].append({'run_id':run['id'],'id':ident,'grade':'SYNTHETIC-CS','form':form,'dimensions':dimensions(8),'weight_kg':800,'current_version_id':version,'origin_stock_lot_id':ident,'production_lot_id':None,'quality_status':'PENDING','availability_status':'WIP','active':True})
    domain['material_versions'].append({'run_id':run['id'],'id':version,'material_id':ident,'ordinal':1,'grade':'SYNTHETIC-CS','form':form,'dimensions':dimensions(8),'weight_kg':800,'cause_event_id':None})
    domain['attachments'].append({'run_id':run['id'],'id':ident+':support','material_id':ident,'kind':'slot','owner_id':ports[0],'socket_id':'cutter_in_support','acquired_at_ms':0,'released_at_ms':None})
    domain['allocations'].append({'run_id':run['id'],'id':ident+':work','material_id':ident,'order_id':'order:1','work_order_id':'work:1','quantity_kg':800,'active':True})
    domain['mass_ledger'].append({'run_id':run['id'],'id':ident+':opening','source_id':ident+':opening','kind':'OPENING_STOCK','quantity_kg':800,'at_ms':0,'material_id':None,'batch_id':None,'event_id':None})
    artifacts={item.descriptor.path:item.content for item in template.verified.artifacts};artifacts['collections.json']=c.FactoryCollections.model_validate(domain).model_dump_json().encode();artifacts['world.json']=json.dumps(world).encode();manifest=json.loads(template.verified.manifest_bytes);manifest['bundle_id']='binding-test-GO06'
    for artifact in manifest['artifacts']:artifact['sha256']=hashlib.sha256(artifacts[artifact['path']]).hexdigest()
    raw=json.dumps(manifest,indent=2).encode();run.update(bundle_id=manifest['bundle_id'],bundle_hash=hashlib.sha256(raw).hexdigest());initial=c.FactorySnapshot.model_validate({**domain,'run':run})
    return admit_contract_test(raw,artifacts,initial),ports,[ident],form


def go_case(database, target: Path):
    """Initialize the exact actual GO06 source-bound admitted split fixture."""
    target.mkdir()
    admitted, ports, ids, form = go_bundle(target)
    with Session(database) as session, session.begin():
        state = service.initialize_once(session, test_bundle=admitted)
        service.apply_command(session, c.FactoryCommand(action='step', run_id=state.run.id, expected_revision=state.run.revision, command_id='binding-test-clock', steps=10))
    state = load(database)
    request = BatchCompletion.model_validate({'run_id': state.run.id, 'expected_revision': state.run.revision, 'command_id': 'binding-test-split', 'recipe_id': GO06['source_step_id'], 'process_id': 'binding-test-process', 'start_ms': 0, 'end_ms': 10000, 'inputs': [{'material_version_id': m.current_version_id, 'quantity_kg': m.weight_kg} for m in state.materials], 'stock_additions': [], 'external_additions': [], 'outputs': [{'material_id': ids[0]+':C'+str(i), 'grade': 'SYNTHETIC-CS', 'form': form, 'dimensions': dimensions(4), 'quantity_kg': 400, 'destination_id': port, 'work_order_id': 'work:1'} for i, port in enumerate(ports)], 'byproducts': [], 'losses': []})
    return state, request, TypeAdapter(AssetBindingValue).validate_python(GO06['binding'])


def observe(session: Session, state, request):
    """Write the actual terminal process and completion event in the caller transaction."""
    process = c.ProcessExecution(run_id=state.run.id, id=request.process_id, work_order_id='work:1', route_step_id='go-06', equipment_id='CS-GO-06', status='COMPLETED', ready_at_ms=0, start_ms=0, end_ms=10000, planned_duration_ms=10000, blocked_reason=None)
    session.execute(models.ProcessExecution.__table__.insert().values(**process.model_dump(mode='json')))
    completed = event(state, 'binding-test-completed', 1, 'PROCESS_COMPLETED', 'process', process.id, c.EventContext(material_ids=tuple(m.id for m in state.materials), process_id=process.id, work_order_id='work:1'))
    session.execute(models.FactoryEvent.__table__.insert().values(**completed.model_dump(mode='json')))
    session.execute(update(models.FactoryRun).where(models.FactoryRun.id == state.run.id).values(event_sequence=completed.sequence))


def test_extended_binding_when_actual_go06_split_retains_subtype_and_exact_replay(database, tmp_path, monkeypatch):
    # Given: actual admitted GO06, its complete nested feed and a real migrated database.
    state, request, original = go_case(database, tmp_path/'go')
    before_binding = copy.deepcopy(original.model_dump())
    captured = []
    real_plan = batch_service.plan_completed_batch
    def capture(*args):
        captured.extend(args[3])
        return real_plan(*args)
    monkeypatch.setattr(batch_service, 'plan_completed_batch', capture)
    # When: the real caller transaction commits its observed 1:2 split.
    with Session(database) as session, session.begin():
        observe(session, state, request)
        result = batch_service.record_completed_batch(session, request, asset_bindings=(original,))
    after = load(database)
    # Then: strict reparsing preserves every subtype field and mass/lineage.
    assert isinstance(captured[0], InternalFeedAssetBinding) and captured[0] is not original
    assert captured[0].model_dump() == before_binding == original.model_dump()
    assert len([m for m in after.materials if m.active]) == 2
    assert sum(m.weight_kg for m in after.materials if m.active) == 800
    assert len(after.version_edges) == 2
    assert all(next(v for v in after.material_versions if v.id == old.id) == old for old in state.material_versions)
    with Session(database) as session, session.begin():
        service.apply_command(session, c.FactoryCommand(action='step', run_id=after.run.id, expected_revision=after.run.revision, command_id='binding-later-clock', steps=1))
    before_replay = sql_state(database)
    with Session(database) as session, session.begin():
        replay = batch_service.record_completed_batch(session, request, asset_bindings=(original,))
    assert replay.replayed and replay.run == result.run and sql_state(database) == before_replay
    malformed = original.model_copy(update={'internal_feeds': ()})
    with pytest.raises(ServiceError, match='internal_feeds') as invalid:
        with Session(database) as session, session.begin():
            batch_service.record_completed_batch(session, request, asset_bindings=(malformed,))
    assert invalid.value.code == 'invalid_contract' and sql_state(database) == before_replay
    with pytest.raises(ServiceError) as changed:
        with Session(database) as session, session.begin():
            batch_service.record_completed_batch(session, request.model_copy(update={'end_ms':9999}), asset_bindings=(original,))
    assert changed.value.code == 'idempotency_conflict' and sql_state(database) == before_replay


@pytest.mark.parametrize('variant', ['nested-extra','empty','extra-feed','unknown-kind','radius-zero','radius-nan','radius-infinite','ratio-zero','ratio-nan','missing-driver','missing-socket','foreign-owner','duplicate-owner','invalid-axis','roller-relation'])
def test_tampered_binding_when_writer_revalidates_complete_dump_rolls_back_every_table(database, tmp_path, variant):
    # Given: model_copy can forge an already-created model; this boundary must distrust it.
    state, request, original = go_case(database, tmp_path/'go')
    raw = original.model_dump(); feed = raw['internal_feeds'][0]
    match variant:
        case 'nested-extra': feed['unregistered'] = True
        case 'empty': raw['internal_feeds'] = []
        case 'extra-feed': raw['internal_feeds'] = (*raw['internal_feeds'], copy.deepcopy(feed))
        case 'unknown-kind': feed['kind'] = 'invented_feed'
        case 'radius-zero': feed['rollers'][0]['radius_m'] = 0
        case 'radius-nan': feed['rollers'][0]['radius_m'] = float('nan')
        case 'radius-infinite': feed['rollers'][0]['radius_m'] = float('inf')
        case 'ratio-zero': feed['rollers'][0]['ratio'] = 0
        case 'ratio-nan': feed['rollers'][0]['ratio'] = float('nan')
        case 'missing-driver': feed['driver_function_id'] = 'missing_driver'
        case 'missing-socket': feed['custody_socket_id'] = 'missing_socket'
        case 'foreign-owner': raw['owner_id'] = 'CS-GO-09'
        case 'invalid-axis': raw['functions'][0]['axis'] = [2,0,0]
        case 'roller-relation': feed['rollers'][0]['ratio'] *= 2
        case 'duplicate-owner': pass
        case _: raise AssertionError('Unregistered test variant')
    tampered = original.model_copy(update=raw); bindings = (original, original) if variant == 'duplicate-owner' else (tampered,)
    original_repr = repr(tampered.model_dump()); before = sql_state(database)
    # When: malformed input enters after real process/event writes in the caller transaction.
    with pytest.raises(ServiceError) as error:
        with Session(database) as session, session.begin():
            observe(session, state, request)
            batch_service.record_completed_batch(session, request, asset_bindings=bindings)
    # Then: no process/event/receipt/domain row remains, including NaN/Infinity cases.
    assert error.value.code == ('unsupported_bundle' if variant in {'missing-driver','missing-socket','roller-relation'} else 'invalid_contract')
    assert sql_state(database) == before and repr(tampered.model_dump()) == original_repr


@pytest.mark.parametrize('timing', ['BEFORE','AFTER'])
def test_extended_binding_when_receipt_write_fails_rolls_back_process_and_batch(database, tmp_path, timing):
    # Given
    state, request, original = go_case(database, tmp_path/'go')
    with database.begin() as connection:
        connection.execute(text(f"CREATE TRIGGER binding_receipt_failure {timing} INSERT ON factory_v3_command_receipts BEGIN SELECT RAISE(ABORT,'binding receipt failure'); END"))
    before = sql_state(database)
    # When
    with pytest.raises(IntegrityError, match='binding receipt failure'):
        with Session(database) as session, session.begin():
            observe(session, state, request)
            batch_service.record_completed_batch(session, request, asset_bindings=(original,))
    # Then
    assert sql_state(database) == before


def test_legacy_base_binding_when_writer_revalidates_retains_exact_base_class(database, tmp_path, monkeypatch):
    # Given
    bundle = build_bundle(tmp_path/'base'); state = stock_state(database,bundle); original = binding(bundle)
    captured = []; real_plan = batch_service.plan_completed_batch
    def capture(*args):
        captured.extend(args[3]); return real_plan(*args)
    monkeypatch.setattr(batch_service,'plan_completed_batch',capture)
    # When
    apply(database,completion(state),(original,))
    # Then
    assert type(captured[0]) is AssetBinding and captured[0] is not original and captured[0].model_dump() == original.model_dump()


def test_registered_lifted_binding_when_reparsed_retains_closed_existing_subtype(database, tmp_path, monkeypatch):
    # Given: the existing registered T65 case, never an invented lift authority.
    state, request, _ = go_case(database,tmp_path/'go')
    cases=json.loads((ROOT/'shared/fixtures/finishing-continuity-cases.json').read_text())['cases']
    raw=next(case['request']['context']['asset_bindings'][0] for case in cases if case['request']['envelope']['anchor']['owner_id']=='CS-GO-05')
    original=TypeAdapter(AssetBindingValue).validate_python(raw); captured=[]; real_plan=batch_service.plan_completed_batch
    def capture(*args):
        captured.extend(args[3]); return real_plan(*args)
    monkeypatch.setattr(batch_service,'plan_completed_batch',capture)
    # When: complete parsing succeeds, then the genuinely missing GO06 owner must reject.
    with pytest.raises(ServiceError) as error:
        with Session(database) as session,session.begin():
            observe(session,state,request);batch_service.record_completed_batch(session,request,asset_bindings=(original,))
    # Then
    assert error.value.code=='unsupported_bundle'
    assert isinstance(captured[0],InternalFeedAssetBinding) and isinstance(captured[0].internal_feeds[0],LiftedInternalFeedBinding)
    assert captured[0].model_dump()==original.model_dump() and captured[0] is not original
