"""Pure schema3 projection probes on the actual shared N:M contract fixture."""
from pathlib import Path

import pytest

from app.operations.contracts_v3 import FactorySnapshot
from app.operations.contracts_v3_core import ContractViolation, EntityId
from app.operations import projection_v3 as p

FIXTURE = Path(__file__).resolve().parents[3] / 'shared/fixtures/factory-contract-test-v3/domain.json'


@pytest.fixture
def state() -> FactorySnapshot:
    return FactorySnapshot.model_validate_json(FIXTURE.read_text())


def test_stock_detail_when_unallocated_preserves_null_provenance(state: FactorySnapshot) -> None:
    # Given / When
    detail = p.material_detail(state, EntityId('stock-coil'))
    # Then
    assert detail.order is detail.work_order is detail.production_lot is detail.current_allocation is None
    assert detail.material.grade == 'SYNTHETIC'
    assert detail.current_version.dimensions.width_mm == 1000
    assert detail.current_attachment.owner_id == 'v2:road-slot'
    assert detail.origin_stock_lot.id == 'stock-coil'
    assert detail.current_job is None


def test_lineage_when_merge_split_preserves_all_siblings_and_excludes_stock(state: FactorySnapshot) -> None:
    # Given / When
    detail = p.material_detail(state, EntityId('out-a'))
    # Then
    assert {r.material_id for r in detail.versions} == {'in-a', 'in-b', 'out-a', 'out-b'}
    assert len(detail.version_edges) == 4
    assert len(detail.batch_io) == 5
    assert len(detail.process_batches) == 1
    assert 'stock-coil' not in {r.id for r in detail.lineage_materials}


def test_world_when_read_preserves_snapshot_and_uses_ledger_mass(state: FactorySnapshot) -> None:
    # Given
    before = state.model_dump_json()
    # When
    world = p.project_world(state)
    # Then
    assert world.kpis.opening_kg == 2500
    assert world.kpis.active_kg == world.kpis.available_kg == 2400
    assert world.kpis.loss_kg == 100
    assert world.kpis.active_material_count == 3
    assert state.model_dump_json() == before
    assert world.model_dump(exclude={'kpis'}) == state.model_dump()


@pytest.mark.parametrize('material_id', ['in-a', 'out-a', 'missing'])
def test_coil_when_noncoil_or_missing_returns_not_found(state: FactorySnapshot, material_id: str) -> None:
    # Given / When / Then
    with pytest.raises(ContractViolation) as error:
        p.coil_detail(state, EntityId(material_id))
    assert error.value.code == 'not_found'


def test_coil_when_stock_coil_has_no_order_is_readable(state: FactorySnapshot) -> None:
    # Given / When
    detail = p.coil_detail(state, EntityId('stock-coil'))
    # Then
    assert detail.order is None
    assert [r.id for r in p.project_coils(state).materials] == ['stock-coil']


def test_projections_when_called_share_revision_and_preserve_n_m(state: FactorySnapshot) -> None:
    # Given / When
    results = [p.project_production(state), p.project_orders(state), p.project_shipments(state), p.project_events(state)]
    # Then
    assert all(r.run_id == state.run.id and r.revision == state.run.revision for r in results)
    assert p.project_production(state).batch_io == state.batch_io
    assert p.project_orders(state).orders == ()


def test_reply_when_receipt_is_older_preserves_applied_run_and_revision(state: FactorySnapshot) -> None:
    # Given
    from app.operations.contracts_v3 import CommandResult
    original = CommandResult(run=state.run, command_id=EntityId('receipt'), replayed=True, delta=None)
    current = FactorySnapshot.model_validate({**state.model_dump(), 'run': {**state.run.model_dump(), 'revision': 2}})
    # When
    reply = p.project_command_reply(current, original)
    # Then
    assert reply.applied_revision == 0 and reply.run.revision == 2
    assert reply.applied_run_id == state.run.id and reply.replayed


def test_order_when_missing_returns_typed_not_found(state: FactorySnapshot) -> None:
    # Given / When / Then
    with pytest.raises(ContractViolation) as error:
        p.order_detail(state, EntityId('missing'))
    assert error.value.code == 'not_found'


def test_detail_when_allocated_stock_is_in_transport_keeps_custody_and_leg(state: FactorySnapshot) -> None:
    # Given: explicit synthetic order/job rows enrich the admitted business fixture, not a scheduler claim.
    raw = state.model_dump(mode='json')
    identity = {'run_id': state.run.id}
    raw['orders'] = [{**identity, 'id': 'order', 'customer_id': 'synthetic-customer', 'product_id': 'hr', 'grade': 'SYNTHETIC', 'quantity_kg': 500, 'due_at': '2026-10-31T00:00:00.000Z'}]
    raw['work_orders'] = [{**identity, 'id': 'work', 'order_id': 'order', 'route_id': 'test-route', 'route_version': 1, 'planned_kg': 500, 'status': 'RELEASED'}]
    raw['allocations'] = [{**identity, 'id': 'allocation', 'material_id': 'stock-coil', 'order_id': 'order', 'work_order_id': 'work', 'quantity_kg': 500, 'active': True}]
    raw['shipments'] = [{**identity, 'id': 'shipment', 'order_id': 'order', 'mode': 'ROAD', 'status': 'LOADING', 'capacity_kg': 500}]
    raw['shipment_legs'] = [{**identity, 'id': 'leg', 'shipment_id': 'shipment', 'ordinal': 0, 'mode': 'ROAD', 'from_node_id': 'v2:road-a', 'to_node_id': 'v2:road-b', 'status': 'LOADING', 'eta_ms': 2000, 'start_ms': 1000, 'end_ms': None}]
    raw['shipment_materials'] = [{**identity, 'id': 'membership', 'shipment_id': 'shipment', 'material_id': 'stock-coil', 'active': True}]
    raw['transport_jobs'] = [{**identity, 'id': 'job', 'fleet_id': None, 'equipment_id': 'test-crane', 'material_id': 'stock-coil', 'shipment_leg_id': 'leg', 'from_node_id': 'v2:road-a', 'to_node_id': 'v2:road-b', 'status': 'LOADING', 'ready_at_ms': 0, 'start_ms': 1000, 'end_ms': None, 'blocked_resource_id': None}]
    enriched = FactorySnapshot.model_validate(raw)
    # When
    detail = p.material_detail(enriched, EntityId('stock-coil'))
    order = p.order_detail(enriched, EntityId('order'))
    # Then
    assert detail.current_allocation.id == 'allocation'
    assert detail.order.id == 'order' and detail.work_order.id == 'work'
    assert detail.production_lot is None
    assert detail.current_job.id == 'job' and detail.shipment_legs[0].id == 'leg'
    assert detail.current_attachment.owner_id == 'v2:road-slot'
    assert order.materials[0].id == 'stock-coil' and order.order.customer_id == 'synthetic-customer'


def test_detail_when_storage_row_order_changes_is_deterministic(state: FactorySnapshot) -> None:
    # Given
    reversed_rows = state.model_copy(update={name: tuple(reversed(getattr(state, name))) for name in ('materials', 'material_versions', 'version_edges', 'batch_io', 'process_batches', 'attachments')})
    # When
    actual = p.material_detail(reversed_rows, EntityId('out-a'))
    # Then
    assert actual == p.material_detail(state, EntityId('out-a'))
