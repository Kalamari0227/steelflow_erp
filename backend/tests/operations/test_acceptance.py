import json
import os
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import BaseModel, ConfigDict

from app.main import create_app
from app.operations import contracts as c
from app.operations.fulfillment import fulfillment_transition
from app.schemas import CoilDetail, MaterialDetail, OrderDetail, World
from tests.operations.test_fulfillment import serialized, stock_model
from tests.operations.test_migration_preservation import legacy_bytes, populated_legacy
from tests.test_simulation import command, complete, completion_steps, read_world


class ExpectedProduct(BaseModel):
    model_config = ConfigDict(frozen=True)
    id: c.ProductId
    output: c.MaterialForm
    input_units: int
    final_units: tuple[int, ...]


class ExpectedRoutes(BaseModel):
    model_config = ConfigDict(frozen=True)
    products: tuple[ExpectedProduct, ...]


def record(name: str, value: str, fallback: Path) -> None:
    directory = Path(os.environ.get('T18_EVIDENCE_DIR', str(fallback)))
    directory.mkdir(parents=True, exist_ok=True)
    (directory / name).write_text(value)


def advance_to(client: TestClient, target_ms: int) -> World:
    for state in completion_steps(client, target_ms):
        pass
    return state


def test_all_twenty_routes_when_delivered_match_independent_forms_and_full_links(client: TestClient, tmp_path: Path) -> None:
    expectations = ExpectedRoutes.model_validate_json((Path(__file__).resolve().parents[3] / 'tests/fixtures/operations_route_expectations.json').read_text())
    initial = read_world(client)
    assert len(initial.orders) == len(expectations.products) == 20
    assert len(initial.materials) == 22 and initial.shipment_materials == ()
    final = complete(client)
    for expected in expectations.products:
        detail = OrderDetail.model_validate(client.get(f'/api/v1/orders/ORD-{expected.id}').json())
        active = [row for row in detail.materials if row.active]
        assert sorted(row.weight_kg for row in active) == sorted(expected.final_units * expected.input_units)
        assert all(row.form == expected.output and row.quality_status == 'PASSED' for row in active)
        assert detail.order.status == 'DELIVERED'
        assert detail.order.delivered_kg == detail.order.quantity_kg == sum(row.weight_kg for row in active)
        assert detail.order.remaining_delivery_kg == detail.order.remaining_dispatch_kg == 0
        assert detail.customer.id == detail.order.customer_id
        for material in active:
            view = MaterialDetail.model_validate(client.get(f'/api/v1/materials/{material.id}').json())
            assert view.material == material and view.order.id == detail.order.id
            assert view.lot.id == material.lot_id and view.work_order.id == view.lot.work_order_id
            assert view.location.id == material.location_id
            assert any(row.status == 'PASSED' and row.inspected_version_id == material.current_version_id for row in view.inspections)
            assert len(view.shipments) == 1 and view.shipments[0].status == 'DELIVERED'
            response = client.get(f'/api/v1/coils/{material.id}')
            if expected.output.endswith('_COIL'):
                assert response.status_code == 200
                coil = CoilDetail.model_validate(response.json())
                assert coil.order.id == detail.order.id and coil.coil.id == material.id
                assert coil.shipment is not None and coil.shipment.id == view.shipments[0].id
            else:
                assert response.status_code == 404
    assert final.mass_balance.model_dump() == {'initial_kg': 408000, 'additions_kg': 1200, 'active_kg': 407300, 'loss_kg': 1900}
    assert len(final.inventory_materials) == 24
    assert read_world(client) == final
    record('T18-all-routes-world.json', final.model_dump_json(indent=2), tmp_path)


def test_ga_when_first_shipment_delivers_order_remains_partial_until_second(client: TestClient, tmp_path: Path) -> None:
    completed = complete(client)
    first_delivery = next(row.at_ms for row in completed.events if row.event_type == 'SHIPMENT_DELIVERED' and row.entity_id == 'SHIP-ga-01')
    second_delivery = next(row.at_ms for row in completed.events if row.event_type == 'SHIPMENT_DELIVERED' and row.entity_id == 'SHIP-ga-02')
    assert first_delivery < second_delivery
    command(client, c.SimulationCommand(action='reset'))
    step_ms = read_world(client).simulation.step_ms
    before_first = advance_to(client, ((first_delivery - 1) // step_ms) * step_ms)
    assert before_first.run.elapsed_ms < first_delivery
    assert next(row for row in before_first.orders if row.id == 'ORD-ga').delivered_kg == 0
    partial = advance_to(client, first_delivery)
    assert first_delivery <= partial.run.elapsed_ms < second_delivery
    order = next(row for row in partial.orders if row.id == 'ORD-ga')
    assert order.status == 'PARTIALLY_DELIVERED'
    assert order.delivered_kg == 40200 and order.remaining_delivery_kg == 20100
    first_members = [row for row in partial.shipment_materials if row.shipment_id == 'SHIP-ga-01' and row.active]
    assert {row.material_id for row in first_members} == {'MAT-ga-01', 'MAT-ga-02'}
    assert all(not row.loaded for row in first_members)
    before_second = advance_to(client, ((second_delivery - 1) // step_ms) * step_ms)
    assert before_second.run.elapsed_ms < second_delivery
    pending = next(row for row in before_second.orders if row.id == 'ORD-ga')
    assert pending.status == 'PARTIALLY_DELIVERED' and pending.delivered_kg == 40200 and pending.remaining_delivery_kg == 20100
    final = advance_to(client, second_delivery)
    order = next(row for row in final.orders if row.id == 'ORD-ga')
    assert order.status == 'DELIVERED' and order.delivered_kg == 60300 and order.remaining_delivery_kg == 0
    second_members = [row for row in final.shipment_materials if row.shipment_id == 'SHIP-ga-02' and row.active]
    assert {row.material_id for row in second_members} == {'MAT-ga-03'}
    assert len({row.lot_id for row in final.materials if row.id in order.material_ids}) == 2
    record('T18-partial-delivery.json', json.dumps({'first_ms': first_delivery, 'second_ms': second_delivery, 'partial': partial.model_dump(mode='json'), 'final': final.model_dump(mode='json')}), tmp_path)


def test_split_when_shipped_retires_parent_and_preserves_child_genealogy(client: TestClient, tmp_path: Path) -> None:
    final = complete(client)
    for product, child_kg in (('plate', 9950), ('ti-sheet', 5950)):
        parent_id = f'MAT-{product}-01'
        parent = next(row for row in final.materials if row.id == parent_id)
        assert not parent.active and parent.availability_status == 'CONSUMED'
        edges = [row for row in final.lineage_edges if row.parent_material_id == parent.id]
        assert {row.child_material_id for row in edges} == {f'{parent_id}:A', f'{parent_id}:B'}
        assert sum(row.transferred_kg for row in edges) == child_kg * 2
        children = [row for row in final.materials if row.id in {edge.child_material_id for edge in edges}]
        assert all(row.active and row.weight_kg == child_kg and row.lineage_id == parent.lineage_id for row in children)
        assert parent.id not in {row.id for row in final.inventory_materials}
        assert parent.id not in {row.material_id for row in final.shipment_materials}
        assert {row.material_id for row in final.shipment_materials if row.shipment_id == f'SHIP-{product}-01'} == {row.id for row in children}
    record('T18-split-lineage.json', json.dumps({'materials': [row.model_dump(mode='json') for row in final.materials if 'plate' in row.id or 'ti-sheet' in row.id], 'lineage': [row.model_dump(mode='json') for row in final.lineage_edges]}), tmp_path)


@pytest.mark.parametrize('quality', ['PENDING', 'HOLD', 'FAILED'])
def test_acceptance_when_quality_unreleased_rejects_assignment_without_mutation(quality: c.QualityStatus, tmp_path: Path) -> None:
    model = stock_model()
    inspection = next(row for row in model.inspections.values() if row.material_id == 'MAT-ga-01')
    model.inspections[inspection.id] = inspection.model_copy(update={'status': quality})
    before = serialized(model)
    with pytest.raises(c.ContractViolation, match='quality'):
        fulfillment_transition(model, c.EntityId('SHIP-ga-01'), model.run.elapsed_ms)
    assert serialized(model) == before
    record(f'T18-quality-{quality}.json', json.dumps({'quality': quality, 'rejected': True, 'unchanged': True}), tmp_path)


def test_acceptance_when_mass_mutation_fails_database_rolls_back(client: TestClient, db_path: Path, tmp_path: Path) -> None:
    state = command(client, c.SimulationCommand(action='step', steps=48))
    assert state.mass_movements
    with sqlite3.connect(db_path) as connection:
        before = tuple(connection.iterdump())
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute('UPDATE mass_movements SET output_kg=1 WHERE run_id=?', (state.run.id,))
        assert tuple(connection.iterdump()) == before
    assert canonical_world(read_world(client)) == canonical_world(state)
    record('T18-mass-rejection.json', json.dumps({'run_id': state.run.id, 'rejected': True, 'database_unchanged': True}), tmp_path)


def test_acceptance_when_concurrent_command_and_retired_run_cannot_overwrite(client: TestClient, tmp_path: Path) -> None:
    before = read_world(client)
    def submit(index: int) -> int:
        response = client.post('/api/v1/simulation/step', json={'run_id': before.run.id, 'expected_revision': before.run.revision, 'command_id': f't18-{index}'})
        return response.status_code
    with ThreadPoolExecutor(max_workers=2) as pool:
        statuses = list(pool.map(submit, (1, 2)))
    assert sorted(statuses) == [200, 409]
    assert read_world(client).run.elapsed_ms == 1000
    reset = command(client, c.SimulationCommand(action='reset'))
    rejected = client.post('/api/v1/simulation/step', json={'run_id': before.run.id, 'command_id': 't18-retired'})
    assert rejected.status_code == 409
    assert canonical_world(read_world(client)) == canonical_world(reset)
    record('T18-command-conflicts.json', json.dumps({'statuses': statuses, 'retired_status': rejected.status_code, 'original': before.run.id, 'current': reset.run.id}), tmp_path)


def canonical_world(world: World) -> str:
    return world.model_dump_json(include=set(World.model_fields))


def test_acceptance_when_live_run_executes_preserves_populated_legacy_history(populated_legacy: Path, tmp_path: Path) -> None:
    with sqlite3.connect(populated_legacy) as connection:
        before = legacy_bytes(connection)
    with TestClient(create_app(f'sqlite+aiosqlite:///{populated_legacy}', clock_enabled=False, bootstrap_mode='legacy_fixture')) as client:
        first = complete(client)
        command(client, c.SimulationCommand(action='reset'))
        assert client.get('/api/v1/events?run_id=legacy-run-a').status_code == 200
        assert len(client.get('/api/v1/events?run_id=legacy-run-a').json()) == 2
        assert len(client.get('/api/v1/journey/events?run_id=journey-b').json()) == 2
        assert client.get(f'/api/v1/events?run_id={first.run.id}').json() == [row.model_dump(mode='json') for row in first.events]
    with sqlite3.connect(populated_legacy) as connection:
        after = legacy_bytes(connection)
        for table, old in before.items():
            assert after[table]['columns'] == old['columns']
            assert all(row in after[table]['rows'] for row in old['rows'])
            if table not in ('customers', 'locations', 'operation_events'):
                assert after[table] == old
        assert connection.execute('PRAGMA foreign_key_check').fetchall() == []
    record('T18-legacy-preservation.json', json.dumps({'before': before, 'after': after, 'old_rows_preserved': True}), tmp_path)
