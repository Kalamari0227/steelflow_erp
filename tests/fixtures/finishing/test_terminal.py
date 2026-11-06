"""Actual isolated T10 N:M records for source-bound synthetic welding/shearing."""
from __future__ import annotations

import copy
import hashlib
import json
import math
import os
from pathlib import Path
import sys

import pytest
from pydantic import TypeAdapter
from sqlalchemy import update
from sqlalchemy.orm import Session

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'backend'))
sys.path.insert(0, str(ROOT / 'backend/tests/operations'))
from test_factory_service import database  # noqa: F401 -- real migrated SQLite fixture
from factory_batch_bundle import build_bundle, sql_state, load
from app.operations import contracts_v3 as c, service_v3 as service, models_v3 as models
from app.operations.batch_contracts import BatchCompletion
from app.operations.batch_service import record_completed_batch
from app.operations.bundle_registry import admit_contract_test, ServiceError
from app.operations.motion_bindings import AssetBindingValue
from app.operations.stock_contracts import event

SOURCE = Path(os.environ['FINISHING_TERMINAL_BINDINGS'])
assert hashlib.sha256(SOURCE.read_bytes()).hexdigest() == os.environ['FINISHING_TERMINAL_BINDINGS_SHA']
DATA = json.loads(SOURCE.read_text())
OUTPUT = Path(os.environ['FINISHING_TERMINAL_OUTPUT'])
CASES = [(row['owner_id'], kind) for row in DATA['rows'] for kind in ['weld', 'cut'] if ('strip_clamp' if kind == 'weld' else 'output_cutter') in row['spec']['moving']]


def save(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, default=str, allow_nan=False) + '\n')


def dims(length: float, thickness: float) -> dict:
    return {'length_mm': length * 1000, 'width_mm': 1200, 'thickness_mm': thickness * 1000, 'diameter_mm': None, 'inner_diameter_mm': None}


def bundle_for(target: Path, row: dict, operation: str):
    total = 800
    template = build_bundle(target / 'template', (total, 1))
    domain = template.verified.collections.model_dump(mode='json')
    run = template.initial_snapshot.run.model_dump(mode='json')
    owner = row['owner_id']; binding = row['binding']; prefix = 'synthetic:T21:' + owner + ':' + operation
    world = template.verified.world.model_dump(mode='json')
    owner_row = next(o for o in world['owners'] if o['id'] == owner)
    for socket in binding['sockets']:
        if not any(s['id'] == socket['socket_id'] for s in owner_row['sockets']):
            owner_row['sockets'].append({'id': socket['socket_id'], 'pose': {'position': socket['position_m'], 'yaw_rad': 0}})
    sockets = [operation + '_in_support', operation + '_out_support'] if operation == 'weld' else ['cutter_in_support', 'work' if row['spec']['kind']=='coiler' else 'intermediate_strip_support']
    ports = []
    for socket_id in sockets:
        socket = next(s for s in binding['sockets'] if s['socket_id'] == socket_id)
        node_id = 'v2:' + prefix + ':node:' + socket_id
        x,y,z=socket['position_m'];yaw=owner_row['pose']['yaw_rad'];ox,oy,oz=owner_row['pose']['position']
        world['nodes'].append({'id': node_id, 'position': [ox+math.cos(yaw)*x+math.sin(yaw)*z,oy+y,oz-math.sin(yaw)*x+math.cos(yaw)*z], 'modes': ['roller']})
        port_id = 'v2:' + prefix + ':port:' + socket_id
        world['ports'].append({'id': port_id, 'owner_id': owner, 'socket_id': socket_id, 'node_id': node_id, 'capacity_kg': 60000, 'modes': ['roller']})
        ports.append(port_id)
    thickness = .002 if operation == 'cut' and row['spec']['kind'] == 'cold_mill' else row['spec']['thickness_m']
    form = 'STRIP' if operation == 'weld' else row['spec']['input_form'] if row['spec']['kind'] == 'coiler' else 'THIN_STRIP' if thickness == .002 else 'STRIP'
    ids = [prefix + ':A', prefix + ':B'] if operation == 'weld' else [prefix + ':input']
    input_kg=400 if operation=='weld' else 800
    input_length=4 if operation=='weld' else 8
    for i, ident in enumerate(ids):
        stock = {'run_id': run['id'], 'id': ident, 'source_kind': 'OPENING', 'grade': 'SYNTHETIC-CS', 'form': form, 'quantity_kg': input_kg, 'received_at_ms': 0}
        domain['stock_lots'].append(stock)
        domain['materials'].append({'run_id': run['id'], 'id': ident, 'grade': stock['grade'], 'form': form, 'dimensions': dims(input_length, thickness), 'weight_kg': input_kg, 'current_version_id': ident + ':v1', 'origin_stock_lot_id': ident, 'production_lot_id': None, 'quality_status': 'PENDING', 'availability_status': 'WIP', 'active': True})
        domain['material_versions'].append({'run_id': run['id'], 'id': ident + ':v1', 'material_id': ident, 'ordinal': 1, 'grade': stock['grade'], 'form': form, 'dimensions': dims(input_length, thickness), 'weight_kg': input_kg, 'cause_event_id': None})
        domain['attachments'].append({'run_id': run['id'], 'id': ident + ':support', 'material_id': ident, 'kind': 'slot', 'owner_id': ports[i if operation == 'weld' else 0], 'socket_id': sockets[i if operation == 'weld' else 0], 'acquired_at_ms': 0, 'released_at_ms': None})
        domain['allocations'].append({'run_id': run['id'], 'id': ident + ':work', 'material_id': ident, 'order_id': 'order:1', 'work_order_id': 'work:1', 'quantity_kg': input_kg, 'active': True})
    domain['mass_ledger'].append({'run_id': run['id'], 'id': prefix + ':opening', 'source_id': prefix + ':opening', 'kind': 'OPENING_STOCK', 'quantity_kg': total, 'at_ms': 0, 'material_id': None, 'batch_id': None, 'event_id': None})
    artifacts = {item.descriptor.path: item.content for item in template.verified.artifacts}
    artifacts['collections.json'] = c.FactoryCollections.model_validate(domain).model_dump_json().encode()
    artifacts['world.json'] = json.dumps(world).encode()
    manifest = json.loads(template.verified.manifest_bytes)
    manifest['bundle_id'] = prefix + ':bundle'
    for item in manifest['artifacts']:
        item['sha256'] = hashlib.sha256(artifacts[item['path']]).hexdigest()
    raw = json.dumps(manifest, indent=2).encode()
    run.update(bundle_id=manifest['bundle_id'], bundle_hash=hashlib.sha256(raw).hexdigest())
    initial = c.FactorySnapshot.model_validate({**domain, 'run': run})
    admitted = admit_contract_test(raw, artifacts, initial)
    save(target / 'source.json', {'synthetic': True, 'live_producer': False, 'binding_file_sha256': hashlib.sha256(SOURCE.read_bytes()).hexdigest(), 'asset_manifest_sha256': DATA['manifest_sha256'], 'source_step_id': row['source_step_id'], 'parent_owner_id': owner, 'functions': row['spec']['moving'], 'integer_mass_basis': '100kg per metre is an explicit synthetic accounting scale, not measured steel density', 'operation': operation})
    save(target / 'initial.json', initial.model_dump(mode='json'));save(target / 'world.json', world);save(target / 'binding.json', binding)
    return admitted, ports, ids, form, thickness


@pytest.mark.parametrize(('owner_id', 'operation'), CASES)
def test_terminal_source_nm_when_actual_completed_observation(database, tmp_path: Path, owner_id: str, operation: str):
    # Given: fresh exact source binding, actual two/one initial stocks and migrated DB.
    target = OUTPUT / (owner_id + '-' + operation);target.mkdir(parents=True, exist_ok=False)
    row = next(r for r in DATA['rows'] if r['owner_id'] == owner_id)
    bundle, ports, ids, form, thickness = bundle_for(target, row, operation)
    binding = TypeAdapter(AssetBindingValue).validate_python(row['binding'])
    with Session(database) as session, session.begin():
        state = service.initialize_once(session, test_bundle=bundle)
        save(target / 'seed-state.json', state.model_dump(mode='json'))
        service.apply_command(session, c.FactoryCommand(action='step', run_id=state.run.id, expected_revision=state.run.revision, command_id='synthetic:clock:' + owner_id, steps=10))
    state = load(database);assert state.run.elapsed_ms == 10000
    save(target / 'before.json', state.model_dump(mode='json'))
    process_id = 'synthetic:T21:process:' + owner_id + ':' + operation
    output_ids = [ids[0] + ':joined'] if operation == 'weld' else [ids[0] + ':C0', ids[0] + ':C1']
    output_length = 8 if operation == 'weld' else 4
    request = BatchCompletion.model_validate({'run_id': state.run.id, 'expected_revision': state.run.revision, 'command_id': 'synthetic:T21:terminal:' + owner_id + ':' + operation, 'recipe_id': row['source_step_id'], 'process_id': process_id, 'start_ms': 0, 'end_ms': 10000, 'inputs': [{'material_version_id': m.current_version_id, 'quantity_kg': m.weight_kg} for m in state.materials], 'stock_additions': [], 'external_additions': [], 'outputs': [{'material_id': ident, 'grade': 'SYNTHETIC-CS', 'form': form, 'dimensions': dims(output_length, thickness), 'quantity_kg': 800 if operation == 'weld' else 400, 'destination_id': ports[-1] if operation == 'weld' else ports[i], 'work_order_id': 'work:1'} for i, ident in enumerate(output_ids)], 'byproducts': [], 'losses': []})
    def observe(session: Session, variant: str):
        process = c.ProcessExecution.model_validate({'run_id': state.run.id, 'id': process_id, 'work_order_id': 'work:2' if variant == 'wrong-work' else 'work:1', 'route_step_id': 'wrong-source' if variant == 'wrong-source' else row['source_step_id'], 'equipment_id': 'CS-GI-02' if variant == 'wrong-owner' and owner_id != 'CS-GI-02' else 'CS-CR-02' if variant == 'wrong-owner' else owner_id, 'status': 'RUNNING' if variant == 'running' else 'COMPLETED', 'ready_at_ms': 0, 'start_ms': 0, 'end_ms': 10000, 'planned_duration_ms': 10000, 'blocked_reason': None})
        session.execute(models.ProcessExecution.__table__.insert().values(**process.model_dump(mode='json')))
        if variant != 'no-event':
            completed = event(state, 'synthetic:T21:completed:' + owner_id, 1, 'PROCESS_COMPLETED', 'process', process_id, c.EventContext(material_ids=tuple(ids), process_id=process_id, work_order_id='work:1'))
            session.execute(models.FactoryEvent.__table__.insert().values(**completed.model_dump(mode='json')))
            session.execute(update(models.FactoryRun).where(models.FactoryRun.id == state.run.id).values(event_sequence=completed.sequence))
    before_sql = sql_state(database);save(target / 'before-sql.json', before_sql)
    for variant in ['no-event', 'running', 'wrong-owner', 'wrong-work', 'wrong-source', 'mass']:
        # When: malformed terminal observations enter the actual transaction seam.
        changed = request.model_copy(update={'outputs': (request.outputs[0].model_copy(update={'quantity_kg': request.outputs[0].quantity_kg + 1}), *request.outputs[1:])}) if variant == 'mass' else request
        with pytest.raises(ServiceError) as rejected:
            with Session(database) as session, session.begin():
                observe(session, variant);record_completed_batch(session, changed, asset_bindings=(binding,))
        # Then: every SQL table and process observation is rolled back.
        expected_detail = {'no-event':'actual process completion event missing','running':'batch process completion/window/recipe mismatch','wrong-owner':'input is outside completed process equipment','wrong-work':'process input work allocation mismatch','wrong-source':'batch process completion/window/recipe mismatch','mass':'batch mass imbalance'}[variant]
        assert rejected.value.code == 'invalid_contract' and rejected.value.detail == expected_detail
        assert sql_state(database) == before_sql
        save(target / ('negative-' + variant + '.json'), {'code': rejected.value.code, 'detail': rejected.value.detail, 'before': before_sql, 'after': sql_state(database)})
    with Session(database) as session, session.begin():
        observe(session, 'valid');reply = record_completed_batch(session, request, asset_bindings=(binding,))
    after = load(database);save(target / 'request.json', request.model_dump(mode='json'));save(target / 'after.json', after.model_dump(mode='json'));save(target / 'reply.json', reply.model_dump(mode='json'))
    assert sorted(m.id for m in after.materials if m.active) == sorted(output_ids)
    assert sum(m.weight_kg for m in after.materials if m.active) == 800
    assert len(after.version_edges) == 2
    assert all(next(v for v in after.material_versions if v.id == old.id) == old for old in state.material_versions)
    assert sum(x.quantity_kg for x in after.mass_ledger if x.kind == 'OPENING_STOCK') == 800
    assert [e.event_type for e in after.events].count('MATERIAL_MERGED' if operation == 'weld' else 'MATERIAL_SPLIT') == 1
    saved_sql = sql_state(database)
    with Session(database) as session, session.begin():
        replay = record_completed_batch(session, request, asset_bindings=(binding,))
    assert replay.replayed and sql_state(database) == saved_sql
    changed = request.model_copy(update={'end_ms': 9999})
    with pytest.raises(ServiceError):
        with Session(database) as session, session.begin():
            record_completed_batch(session, changed, asset_bindings=(binding,))
    assert sql_state(database) == saved_sql
    save(target / 'after-sql.json', saved_sql)
    with database.connect() as connection:
        raw = connection.connection.driver_connection
        (target / 'committed.sql').write_text('\n'.join(raw.iterdump()) + '\n')
    save(target / 'receipt.json', {'status': 'PASS_ACTUAL_T10_NM_ONLY', 'operation': operation, 'source_owner_id': owner_id, 'input_count': len(ids), 'output_count': len(output_ids), 'negative_rollback_cases': 6, 'exact_replay_unchanged': True, 'changed_replay_rejected': True, 'all_original_versions_preserved': True, 'geometry_and_T58_cycle': 'separate mandatory evidence'})
