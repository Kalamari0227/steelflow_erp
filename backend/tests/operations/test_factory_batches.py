"""Completed-batch behavior on actual migrated SQLite and exact admitted world."""
# noqa: SIZE_OK -- explicit domain rejection matrix shares the same owned scenario driver.
from __future__ import annotations

import itertools
import shutil

import pytest
from pydantic import ValidationError
from sqlalchemy import text, update
from sqlalchemy.orm import Session

from app.operations import contracts_v3 as c, models_v3 as rows, projection_v3 as projection, service_v3 as service
from app.operations.batch_contracts import BatchCompletion, distribute_kg
from app.operations.batch_service import record_completed_batch
from app.operations.batches import plan_completed_batch, validate_edges
from app.operations.bundle_registry import ServiceError
from app.operations.stock_contracts import StockAllocationCommand, event, identity
from tests.operations.factory_batch_bundle import (
    PORT, apply, binding, build_bundle, completion, evidence, load, save, sql_state, stock_state,
)
from tests.operations.test_factory_service import database  # noqa: F401


@pytest.fixture(scope='module')
def bundle(tmp_path_factory):
    return build_bundle(tmp_path_factory.mktemp('t10-bundle'))


def test_merge_split_remainder_when_ids_permuted_is_stable():
    # Given / When
    result = distribute_kg(2002, ('C', 'A', 'B'))
    # Then
    assert result == {'A': 668, 'B': 667, 'C': 667}


@pytest.mark.parametrize('total,ids', [(True, ('A',)), (1.0, ('A',)), (0, ('A',)), (1, ('A', 'B')), (5, ('A', 'A')), (9007199254740992, ('A',))])
def test_double_count_or_cycle_when_split_input_invalid_is_rejected(total, ids):
    # Given / When / Then
    with pytest.raises(ValueError):
        distribute_kg(total, ids)


def test_merge_split_when_two_receipts_external_and_three_outputs_preserves_mass(database, bundle, tmp_path):
    # Given: actual trusted receipt writes, explicit orders and admitted support.
    before = stock_state(database, bundle)
    request = completion(before)
    target = evidence(tmp_path, 'happy')
    # When
    reply = apply(database, request, (binding(bundle),))
    after = load(database)
    # Then
    active = sorted((row for row in after.materials if row.active), key=lambda row: row.id)
    assert [(row.id, row.weight_kg) for row in active] == [('A', 668), ('B', 667), ('C', 667)]
    assert all(row.quality_status == 'PENDING' and row.availability_status == 'WIP' and row.origin_stock_lot_id is row.production_lot_id is None for row in active)
    assert {row.id for row in after.materials if not row.active} == {row.id for row in before.materials}
    assert all(row.availability_status == 'CONSUMED' for row in after.materials if not row.active)
    assert all(sum(a.material_id == row.id and a.released_at_ms is None for a in after.attachments) == int(row.active) for row in after.materials)
    assert after.receipts == before.receipts and after.stock_lots == before.stock_lots
    assert tuple(row for row in after.material_versions if row.id in {v.id for v in before.material_versions}) == before.material_versions
    assert len(after.allocations) == 3 and {row.order_id for row in after.allocations} == {'order:1', 'order:2'}
    assert sorted((row.kind, row.quantity_kg) for row in after.mass_ledger if row.batch_id is not None) == [('BYPRODUCT', 4), ('EXTERNAL_ADDITION', 7), ('IRRECOVERABLE_LOSS', 2)]
    kpis = projection.project_world(after).kpis
    assert (kpis.received_kg, kpis.additions_kg, kpis.active_kg, kpis.byproduct_kg, kpis.loss_kg) == (2001, 7, 2002, 4, 2)
    # Independently fixed 2x3 integer table, not a call back into planner.
    source_ids = sorted(row.current_version_id for row in before.materials)
    version_ids = {row.material_id: row.id for row in after.material_versions}
    assert {(row.input_version_id, row.output_version_id, row.transferred_kg) for row in after.version_edges} == {(source_ids[0], version_ids['A'], 334), (source_ids[1], version_ids['A'], 332), (source_ids[0], version_ids['B'], 333), (source_ids[1], version_ids['B'], 332), (source_ids[0], version_ids['C'], 332), (source_ids[1], version_ids['C'], 333)}
    kinds = [row.event_type for row in reply.delta.upserts.events]
    assert kinds == ['ATTACHMENT_RELEASED'] * 2 + ['BATCH_COMPLETED', 'MATERIAL_MERGED'] + ['ATTACHMENT_ACQUIRED'] * 3 + ['MATERIAL_ALLOCATED'] * 3
    assert all(row.at_ms == 1000 for row in reply.delta.upserts.events)
    assert not any(row.event_type in ('BATCH_STARTED', 'PROCESS_STARTED', 'QUALITY_RECORDED', 'SHIPMENT_DELIVERED') for row in reply.delta.upserts.events)
    detail = projection.material_detail(after, 'A')
    assert len(detail.lineage_materials) == 5 and len(detail.versions) == 5 and len(detail.version_edges) == 6
    save(target / 'commands.json', request.model_dump(mode='json'))
    save(target / 'assertions.json', {'batch_residual': 0, 'global_residual': 0, 'parents': 2, 'outputs': 3, 'orders': 2, 'edges': 6, 'kpis': kpis.model_dump(mode='json'), 'synthetic_accounting_only': True})
    save(target / 'world.json', projection.project_world(after).model_dump(mode='json'))
    save(target / 'material-A.json', detail.model_dump(mode='json'))
    save(target / 'reply.json', reply.model_dump(mode='json'))
    save(target / 'sql-dump.json', sql_state(database))
    shutil.copy2(database.url.database, target / 'committed.sqlite')
    for artifact in bundle.verified.artifacts:
        (target / artifact.descriptor.path).with_name('bundle-' + artifact.descriptor.path).write_bytes(artifact.content)
    (target / 'bundle.json').write_bytes(bundle.verified.manifest_bytes)
    (target / 'domain.json').write_text(bundle.initial_snapshot.model_dump_json())


@pytest.mark.parametrize('stock_kg,external,planned,expected', [(11, 0, (1338, 668), (669, 669, 668)), (11, 7, (1342, 671), (671, 671, 671))])
def test_merge_split_when_stock_and_external_additions_are_distinct(database, tmp_path, stock_kg, external, planned, expected):
    # Given
    bundle = build_bundle(tmp_path / 'stock-bundle', planned)
    before = stock_state(database, bundle, (1000, 1001, stock_kg))
    request = completion(before, stock_addition=True, external=external)
    # When
    apply(database, request, (binding(bundle),))
    after = load(database)
    # Then
    assert tuple(row.weight_kg for row in after.materials if row.active) == expected
    assert len(after.receipts) == 3 and sum(row.quantity_kg for row in after.receipts) == 2012
    assert sum(row.quantity_kg for row in after.mass_ledger if row.kind == 'EXTERNAL_ADDITION') == external
    assert len([row for row in after.materials if not row.active]) == 3
    assert sum(row.quantity_kg for row in after.batch_io if row.role == 'STOCK_ADDITION') == 11
    save(evidence(tmp_path, 'happy') / f'stock-addition-{external}.json', {'request': request.model_dump(mode='json'), 'world': projection.project_world(after).model_dump(mode='json'), 'sql': sql_state(database), 'expected': expected})


def test_merge_split_when_order_permuted_and_unequal_outputs_stays_deterministic(database, bundle):
    # Given
    before = stock_state(database, bundle)
    request = completion(before)
    # When: compare exact plan over same state, not command-derived ID normalization.
    baseline = plan_completed_batch(before, request, bundle.verified.world, (binding(bundle),))
    plans = [plan_completed_batch(before, request.model_copy(update={'outputs': permutation, 'inputs': tuple(reversed(request.inputs))}), bundle.verified.world, (binding(bundle),)) for permutation in itertools.permutations(request.outputs)]
    # Then
    assert all(plan == baseline for plan in plans)
    unequal = tuple(row.model_copy(update={'quantity_kg': kg, 'work_order_id': None}) for row, kg in zip(request.outputs, (1, 1000, 1001), strict=True))
    assert sum(row.weight_kg for row in plan_completed_batch(before, request.model_copy(update={'outputs': unequal}), bundle.verified.world, (binding(bundle),)).state.materials if row.active) == 2002


INVALID_REQUESTS = [
    ('bool', lambda raw: raw['inputs'][0].update(quantity_kg=True)),
    ('float', lambda raw: raw['inputs'][0].update(quantity_kg=1.0)),
    ('string', lambda raw: raw['inputs'][0].update(quantity_kg='1000')),
    ('negative', lambda raw: raw['inputs'][0].update(quantity_kg=-1)),
    ('zero', lambda raw: raw['inputs'][0].update(quantity_kg=0)),
    ('null', lambda raw: raw['inputs'][0].update(quantity_kg=None)),
    ('unsafe', lambda raw: raw['external_additions'][0].update(quantity_kg=9007199254740992)),
    ('overflow', lambda raw: raw['external_additions'][0].update(quantity_kg=9007199254740991)),
    ('duplicate-roles', lambda raw: raw['stock_additions'].append(raw['inputs'][0])),
    ('duplicate-input', lambda raw: raw['inputs'].append(raw['inputs'][0])),
    ('partial-input', lambda raw: raw['inputs'][0].update(quantity_kg=1)),
    ('missing-version', lambda raw: raw['inputs'][0].update(material_version_id='other-run-only')),
    ('empty-inputs', lambda raw: raw.update(inputs=[])),
    ('empty-outputs', lambda raw: raw.update(outputs=[])),
    ('mass-imbalance', lambda raw: raw['outputs'][0].update(quantity_kg=667)),
    ('duplicate-output', lambda raw: raw['outputs'][1].update(material_id='A')),
    ('external-receipt-reuse', lambda raw: raw['external_additions'][0].update(source_id='receipt:0')),
    ('source-duplicate', lambda raw: raw['losses'][0].update(source_id='external:1')),
    ('destination-missing', lambda raw: raw['outputs'][0].update(destination_id='missing-port')),
    ('slot-instead-of-port', lambda raw: raw['outputs'][0].update(destination_id='receipt:HR_COIL')),
    ('work-missing', lambda raw: raw['outputs'][0].update(work_order_id='missing-work')),
    ('work-overallocated', lambda raw: raw['outputs'][2].update(work_order_id='work:1')),
    ('wrong-grade', lambda raw: raw['outputs'][0].update(grade='OTHER')),
    ('past-end', lambda raw: raw.update(end_ms=999)),
    ('future-end', lambda raw: raw.update(end_ms=1001)),
    ('zero-interval', lambda raw: raw.update(start_ms=1000)),
    ('unknown-process', lambda raw: raw.update(process_id='missing-process')),
    ('null-revision', lambda raw: raw.update(expected_revision=None)),
    ('omitted-nullable', lambda raw: raw.pop('process_id')),
    ('unknown-key', lambda raw: raw.update(quality_status='PASSED')),
]


@pytest.mark.parametrize('name,mutate', INVALID_REQUESTS, ids=[row[0] for row in INVALID_REQUESTS])
def test_double_count_or_cycle_when_contract_invalid_preserves_every_sql_row(database, bundle, tmp_path, name, mutate):
    # Given
    state = stock_state(database, bundle)
    raw = completion(state).model_dump(mode='json')
    mutate(raw)
    before = sql_state(database)
    # When
    with pytest.raises((ServiceError, ValidationError)) as error:
        apply(database, BatchCompletion.model_validate(raw), (binding(bundle),))
    # Then
    after = sql_state(database)
    assert before == after
    expected_code = 'not_found' if name in ('missing-version', 'destination-missing', 'slot-instead-of-port', 'work-missing', 'unknown-process') else 'invalid_contract'
    if isinstance(error.value, ServiceError):
        assert (error.value.code, error.value.status_code) == (expected_code, 404 if expected_code == 'not_found' else 422)
    target = evidence(tmp_path, 'failure/' + name)
    save(target / 'request.json', raw)
    save(target / 'error.json', {'error': str(error.value), 'code': expected_code, 'status': 404 if expected_code == 'not_found' else 422})
    save(target / 'before.json', before)
    save(target / 'after.json', after)


@pytest.mark.parametrize('name', ['missing-binding', 'wrong-family', 'wrong-socket', 'wrong-rest', 'wrong-policy', 'capacity', 'hold', 'failed', 'quarantined', 'active-transport', 'active-shipment', 'custody-after-start', 'wrong-custody-socket', 'parent-output-cycle', 'reused-version-id', 'order-overplanned', 'work-not-released', 'pending-stock', 'old-version', 'missing-edges', 'transposed-edges'])
def test_double_count_or_cycle_when_context_invalid_preserves_sql(database, bundle, tmp_path, name):
    # Given
    state = stock_state(database, bundle)
    request = completion(state)
    bindings = (binding(bundle),)
    material = state.materials[0]
    with database.begin() as connection:
        if name in ('hold', 'failed', 'pending-stock'):
            connection.execute(text('UPDATE factory_v3_materials SET quality_status=:status WHERE run_id=:run AND id=:id'), {'status': {'hold': 'HOLD', 'failed': 'FAILED', 'pending-stock': 'PENDING'}[name], 'run': state.run.id, 'id': material.id})
        if name == 'quarantined':
            connection.execute(text("UPDATE factory_v3_materials SET availability_status='QUARANTINED' WHERE run_id=:run AND id=:id"), {'run': state.run.id, 'id': material.id})
        if name in ('order-overplanned', 'work-not-released'):
            connection.execute(text('UPDATE factory_v3_' + ('orders SET quantity_kg=1' if name == 'order-overplanned' else "work_orders SET status='PLANNED'") + " WHERE run_id=:run AND id=:id"), {'run': state.run.id, 'id': 'order:1' if name == 'order-overplanned' else 'work:1'})
        if name in ('custody-after-start', 'wrong-custody-socket'):
            connection.execute(text('UPDATE factory_v3_attachments SET ' + ('acquired_at_ms=1' if name == 'custody-after-start' else "socket_id='transfer'") + ' WHERE run_id=:run'), {'run': state.run.id})
        if name == 'active-transport':
            node = next(row.node_id for row in bundle.verified.world.ports if row.id == PORT)
            connection.execute(rows.TransportJob.__table__.insert().values(run_id=state.run.id, id='active-job', fleet_id=None, equipment_id='receipt:HR_COIL', material_id=material.id, shipment_leg_id=None, from_node_id=node, to_node_id=node, status='ASSIGNED', ready_at_ms=0, start_ms=None, end_ms=None, blocked_resource_id=None))
        if name == 'active-shipment':
            connection.execute(rows.Shipment.__table__.insert().values(run_id=state.run.id, id='active-shipment', order_id='order:1', mode='ROAD', status='ALLOCATED', capacity_kg=material.weight_kg))
            connection.execute(rows.ShipmentMaterial.__table__.insert().values(run_id=state.run.id, id='active-link', shipment_id='active-shipment', material_id=material.id, active=True))
    if name == 'missing-binding':
        bindings = ()
    if name in ('wrong-family', 'wrong-socket', 'wrong-rest', 'wrong-policy'):
        raw = bindings[0].model_dump()
        if name == 'wrong-family': raw['sockets'][0]['family'] = 'PLATE'
        if name == 'wrong-socket': raw['sockets'][0]['socket_id'] = 'transfer'
        if name == 'wrong-rest': raw['sockets'][0]['position_m'] = (99., 99., 99.)
        if name == 'wrong-policy': raw['policy_id'] = 'missing-policy'
        bindings = (type(bindings[0]).model_validate(raw),)
    if name == 'capacity':
        raw = request.model_dump()
        raw['external_additions'][0]['quantity_kg'] = 500007
        raw['outputs'][0]['quantity_kg'] = 500668
        for row in raw['outputs']: row['work_order_id'] = None
        request = BatchCompletion.model_validate(raw)
    if name in ('parent-output-cycle', 'reused-version-id'):
        output = request.outputs[0].model_copy(update={'material_id': material.id if name == 'parent-output-cycle' else material.current_version_id})
        request = request.model_copy(update={'outputs': (output, *request.outputs[1:])})
    if name == 'old-version':
        with database.begin() as connection:
            old = next(row for row in state.material_versions if row.material_id == material.id).model_copy(update={'id': 'old-version', 'ordinal': 2})
            connection.execute(rows.MaterialVersion.__table__.insert().values(**old.model_dump(mode='json')))
        item = next(row for row in request.inputs if row.material_version_id == material.current_version_id).model_copy(update={'material_version_id': 'old-version'})
        request = request.model_copy(update={'inputs': (item, *[row for row in request.inputs if row.material_version_id != material.current_version_id])})
    before = sql_state(database)
    # When
    with pytest.raises(ServiceError) as error:
        if name in ('missing-edges', 'transposed-edges'):
            plan = plan_completed_batch(state, request, bundle.verified.world, bindings)
            edges = () if name == 'missing-edges' else tuple(row.model_copy(update={'transferred_kg': row.transferred_kg + 1}) for row in plan.delta.upserts.version_edges)
            validate_edges(request, type(plan)(plan.state, plan.delta.model_copy(update={'upserts': plan.delta.upserts.model_copy(update={'version_edges': edges})})))
        else:
            apply(database, request, bindings)
    # Then
    assert sql_state(database) == before
    assert error.value.status_code == 422
    assert error.value.code == ('unsupported_bundle' if name in ('missing-binding', 'wrong-family', 'wrong-socket', 'wrong-rest', 'wrong-policy', 'wrong-custody-socket') else 'invalid_contract')
    target = evidence(tmp_path, 'failure/' + name)
    save(target / 'request.json', request.model_dump(mode='json'))
    save(target / 'error.json', {'code': error.value.code, 'status': error.value.status_code, 'detail': error.value.detail})
    save(target / 'before.json', before)
    save(target / 'after.json', sql_state(database))


def process_completion(session, state, request, variant='valid'):
    """Actual T18 integration seam: observed process/event share caller SQL txn."""
    process_id = identity('process-observation', 'process')
    for material in state.materials:
        session.execute(update(rows.Material).where(rows.Material.run_id == state.run.id, rows.Material.id == material.id).values(quality_status='HOLD' if variant == 'hold' else 'PENDING', availability_status='WIP'))
        session.execute(rows.MaterialAllocation.__table__.insert().values(run_id=state.run.id, id='process-allocation:' + material.id, material_id=material.id, order_id='order:1', work_order_id='work:1', quantity_kg=material.weight_kg, active=True))
    process = c.ProcessExecution.model_validate({'run_id': state.run.id, 'id': process_id, 'work_order_id': 'work:1', 'route_step_id': request.recipe_id, 'equipment_id': 'receipt:CR_COIL' if variant == 'wrong-owner' else 'receipt:HR_COIL', 'status': 'RUNNING' if variant == 'running' else 'COMPLETED', 'ready_at_ms': 0, 'start_ms': 0, 'end_ms': 1000, 'planned_duration_ms': 1000, 'blocked_reason': None})
    session.execute(rows.ProcessExecution.__table__.insert().values(**process.model_dump(mode='json')))
    if variant != 'no-event':
        completed = event(state, 'actual-process-completion', 1, 'PROCESS_COMPLETED', 'process', process_id, c.EventContext(material_ids=tuple(row.id for row in state.materials), process_id=process_id, work_order_id='work:1'))
        session.execute(rows.FactoryEvent.__table__.insert().values(**completed.model_dump(mode='json')))
        session.execute(update(rows.FactoryRun).where(rows.FactoryRun.id == state.run.id).values(event_sequence=completed.sequence))
    outputs = tuple(row.model_copy(update={'work_order_id': 'work:1'}) for row in request.outputs)
    return request.model_copy(update={'process_id': process_id, 'outputs': outputs, 'recipe_id': 'wrong-recipe' if variant == 'wrong-recipe' else request.recipe_id, 'start_ms': 1 if variant == 'wrong-window' else request.start_ms})


@pytest.mark.parametrize('variant', ['valid', 'hold', 'wrong-owner', 'running', 'no-event', 'wrong-recipe', 'wrong-window', 'wrong-work', 'abandon-work'])
def test_merge_split_when_process_linked_pending_wip_joins_completion_transaction(database, tmp_path, variant):
    # Given: explicit work1 can carry all outputs, without changing stored template.
    bundle = build_bundle(tmp_path / 'process-bundle', (2002, 667))
    state = stock_state(database, bundle)
    request = completion(state)
    before = sql_state(database)
    target = evidence(tmp_path, 'process/' + variant)
    # When
    try:
        with Session(database) as session, session.begin():
            observed = process_completion(session, state, request, variant)
            if variant == 'wrong-work':
                session.execute(update(rows.ProcessExecution).where(rows.ProcessExecution.run_id == state.run.id).values(work_order_id='work:2'))
            if variant == 'abandon-work':
                observed = observed.model_copy(update={'outputs': tuple(row.model_copy(update={'work_order_id': None}) for row in observed.outputs)})
            reply = record_completed_batch(session, observed, asset_bindings=(binding(bundle),))
    except ServiceError as error:
        assert variant != 'valid'
        assert (error.code, error.status_code) == ('invalid_contract', 422)
        assert sql_state(database) == before
        save(target / 'error.json', {'code': error.code, 'status': error.status_code, 'detail': error.detail})
        save(target / 'before.json', before)
        save(target / 'after.json', sql_state(database))
    else:
        assert variant == 'valid'
        after = load(database)
        assert after.processes[0].status == 'COMPLETED'
        assert len(after.process_batches) == 1 and len(after.allocations) == 5
        assert len([row for row in after.allocations if row.active]) == 3
        assert all(row.quality_status == 'PENDING' and row.availability_status == 'WIP' for row in after.materials if row.active)
        assert [row.event_type for row in after.events].count('PROCESS_COMPLETED') == 1
        assert all(row.payload.process_id == observed.process_id for row in reply.delta.upserts.events)
        save(target / 'world.json', projection.project_world(after).model_dump(mode='json'))
        save(target / 'sql.json', sql_state(database))
    save(target / 'request.json', observed.model_dump(mode='json'))


def test_merge_split_when_current_output_is_consumed_again_records_one_to_one_and_keeps_ledger_source(database, bundle, tmp_path):
    # Given: actual PENDING/WIP batch output, process-linked next completion.
    before = stock_state(database, bundle)
    apply(database, completion(before), (binding(bundle),))
    state = load(database)
    material = next(row for row in state.materials if row.id == 'C')
    with Session(database) as session, session.begin():
        service.apply_command(session, c.FactoryCommand(action='step', run_id=state.run.id, expected_revision=state.run.revision, command_id='clock:2000', steps=1))
    state = load(database)
    raw = completion(before).model_dump(mode='json')
    raw.update(expected_revision=state.run.revision, command_id='batch:2', start_ms=1000, end_ms=2000, inputs=[{'material_version_id': material.current_version_id, 'quantity_kg': 667}], stock_additions=[], external_additions=[], byproducts=[], losses=[], outputs=[{**raw['outputs'][2], 'material_id': 'D', 'quantity_kg': 667}])
    process_id = identity('second-process', 'process')
    raw['process_id'] = process_id
    request = BatchCompletion.model_validate(raw)
    # When
    with Session(database) as session, session.begin():
        process = c.ProcessExecution.model_validate({'run_id': state.run.id, 'id': process_id, 'work_order_id': 'work:2', 'route_step_id': request.recipe_id, 'equipment_id': 'receipt:HR_COIL', 'status': 'COMPLETED', 'ready_at_ms': 1000, 'start_ms': 1000, 'end_ms': 2000, 'planned_duration_ms': 1000, 'blocked_reason': None})
        session.execute(rows.ProcessExecution.__table__.insert().values(**process.model_dump(mode='json')))
        completed = event(state, 'second-process-completed', 1, 'PROCESS_COMPLETED', 'process', process_id, c.EventContext(material_ids=('C',), process_id=process_id))
        session.execute(rows.FactoryEvent.__table__.insert().values(**completed.model_dump(mode='json')))
        session.execute(update(rows.FactoryRun).where(rows.FactoryRun.id == state.run.id).values(event_sequence=completed.sequence))
        reply = record_completed_batch(session, request, asset_bindings=(binding(bundle),))
    # Then: root/version count increases, receipts/ledger incoming remains 2008kg.
    after = load(database)
    assert len(after.material_versions) == 6 and len(after.process_batches) == 2
    assert after.mass_ledger == state.mass_ledger
    assert projection.project_world(after).kpis.active_kg == 2002
    assert [row.event_type for row in reply.delta.upserts.events].count('MATERIAL_TRANSFORMED') == 1
    assert next(row for row in after.materials if row.id == 'C').availability_status == 'CONSUMED'
    save(evidence(tmp_path, 'happy') / 'continued-version-ledger.json', {'world': projection.project_world(after).model_dump(mode='json'), 'new_roots_not_mass_source': True})


def test_double_count_or_cycle_when_allocated_wip_is_publicly_allocated_again_rejects(database, bundle, tmp_path):
    # Given
    state = stock_state(database, bundle)
    apply(database, completion(state), (binding(bundle),))
    state = load(database)
    before = sql_state(database)
    command = StockAllocationCommand.model_validate({'action': 'allocate_stock', 'run_id': state.run.id, 'expected_revision': state.run.revision, 'command_id': 'duplicate-output-allocation', 'material_id': 'A', 'order_id': 'order:1', 'mode': 'direct_sale'})
    # When
    with pytest.raises(ServiceError) as error:
        with Session(database) as session, session.begin():
            service.allocate_stock(session, command)
    # Then
    assert (error.value.code, error.value.status_code) == ('invalid_contract', 422)
    assert sql_state(database) == before
    save(evidence(tmp_path, 'failure/double-allocation') / 'assertions.json', {'request': command.model_dump(mode='json'), 'code': error.value.code, 'status': error.value.status_code, 'before': before, 'after': sql_state(database)})


def test_merge_split_when_customer_has_active_stock_counts_mass_without_delivery_claim(database, bundle, tmp_path):
    # Given: a synthetic terminal observation, no shipment/leg/delivery events.
    state = stock_state(database, bundle)
    request = completion(state)
    customer_port = 'v2:p:CUSTOMER:work'
    customer_binding = binding(bundle, customer_port).model_copy(update={'policy_id': 'policy:equipment:delivery'})
    outputs = tuple(row.model_copy(update={'destination_id': customer_port}) if row.material_id == 'C' else row for row in request.outputs)
    request = request.model_copy(update={'outputs': outputs})
    # When
    apply(database, request, (binding(bundle), customer_binding))
    after = load(database)
    # Then
    material = next(row for row in after.materials if row.id == 'C')
    assert material.active and material.availability_status == 'WIP'
    assert next(row for row in after.attachments if row.material_id == 'C' and row.released_at_ms is None).owner_id == customer_port
    assert projection.project_world(after).kpis.active_kg == 2002
    assert not after.shipments and not after.shipment_legs
    assert not any(row.event_type == 'SHIPMENT_DELIVERED' for row in after.events)
    target = evidence(tmp_path, 'customer-stock')
    save(target / 'fixture.json', request.model_dump(mode='json'))
    save(target / 'world.json', projection.project_world(after).model_dump(mode='json'))
    save(target / 'assertions.json', {'kind': 'customer-stock accounting', 'customer_kg': material.weight_kg, 'active_kg': 2002, 'delivery_workflow_proven': False, 'physical_move_proven': False, 'sql': sql_state(database)})


def test_merge_split_when_external_dominates_omits_zero_edges_without_fake_roots(database, bundle):
    # Given
    state = stock_state(database, bundle, (1,))
    raw = completion(state, external=2000, byproduct=0, loss=0).model_dump()
    for output, kg in zip(raw['outputs'], (1, 1000, 1000), strict=True):
        output.update(quantity_kg=kg, work_order_id=None)
    request = BatchCompletion.model_validate(raw)
    # When
    apply(database, request, (binding(bundle),))
    after = load(database)
    # Then
    assert len(after.material_versions) == 4 and len(after.version_edges) == 1
    edge = after.version_edges[0]
    assert edge.transferred_kg == 1
    assert next(row for row in after.material_versions if row.id == edge.output_version_id).material_id == 'A'
    assert len(after.receipts) == 1 and len(after.stock_lots) == 1


def test_double_count_or_cycle_when_forged_model_copy_crosses_service_boundary_is_reparsed(database, bundle, tmp_path):
    # Given
    state = stock_state(database, bundle)
    request = completion(state)
    unsafe = request.model_copy(update={'inputs': (request.inputs[0].model_copy(update={'quantity_kg': True}), *request.inputs[1:])})
    before = sql_state(database)
    # When
    with pytest.raises(ServiceError) as error:
        apply(database, unsafe, (binding(bundle),))
    # Then
    assert (error.value.code, error.value.status_code) == ('invalid_contract', 422)
    assert sql_state(database) == before
    save(evidence(tmp_path, 'failure/forged-model-copy') / 'assertions.json', {'error': error.value.detail, 'before': before, 'after': sql_state(database)})
