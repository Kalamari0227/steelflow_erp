"""Physical final quality, whole-unit dispatch and partial delivery behavior."""
# noqa: SIZE_OK -- T9 ownership confines related quality and shipment scenarios to this test file.
from datetime import timedelta
from math import ceil, dist

from app.operations.layout import load_factory_layout

from app.operations import contracts as c
from app.operations.fixtures import build_fixture
from app.operations.fulfillment import OrderTotals, fulfillment_transition, order_totals


def test_initial_stock_cannot_be_shipped() -> None:
    # Given: received material has no final inspection or warehouse receipt.
    plan = build_fixture()
    model = c.SimulationModel(run=c.OperationsRun(id=plan.run_id, scenario_id='NORMAL', elapsed_ms=0, duration_ms=3600000, revision=0, event_sequence=0, playing=False, speed=1, epoch_at=c.EPOCH_AT, started_at=c.EPOCH_AT, plan_revision=0), orders={row.id: c.OperationsOrder(**{**row.model_dump(), 'due_at': c.EPOCH_AT + timedelta(days=2)}) for row in plan.orders}, materials={row.id: row for row in plan.materials}, shipments={row.id: row for row in plan.shipments})
    # When: aggregate the untouched received order.
    totals = order_totals(model, c.EntityId('ORD-ga'))
    # Then: no production, dispatch or delivery credit exists.
    assert (totals.produced_kg, totals.dispatched_kg, totals.delivered_kg, totals.remaining_delivery_kg) == (0, 0, 0, 60300)

import json
import os
from dataclasses import asdict, fields
from pathlib import Path
from typing import Literal, assert_never

import pytest

from app.operations.fulfillment import next_boundary, ready_fulfillment
from app.operations.lineage import transform_material
from app.operations.transport import prepare_process_transfer, transport_transition


def final_model(product: c.ProductId = 'ga') -> c.SimulationModel:
    """Inject explicitly completed manufacturing; preserve real split/version ledger."""
    plan = build_fixture()
    selected = {row.id for row in plan.materials if row.id.startswith(f'MAT-{product}-')}
    model = c.SimulationModel(run=c.OperationsRun(id=plan.run_id, scenario_id='NORMAL', elapsed_ms=1000, duration_ms=3600000, revision=0, event_sequence=0, playing=False, speed=1, epoch_at=c.EPOCH_AT, started_at=c.EPOCH_AT, plan_revision=0), orders={row.id: c.OperationsOrder(**{**row.model_dump(), 'due_at': c.EPOCH_AT + timedelta(days=2)}) for row in plan.orders}, work_orders={row.id: row for row in plan.work_orders}, lots={row.id: row for row in plan.lots}, materials={row.id: row for row in plan.materials if row.id in selected}, material_versions={row.id: row for row in plan.material_versions if row.material_id in selected}, processes={row.id: row for row in plan.processes if row.material_id in selected}, allocations={row.id: row.model_copy(update={'active': True}) for row in plan.allocations if row.material_id in selected}, shipments={row.id: row for row in plan.shipments if row.order_id == f'ORD-{product}'}, resources={row.id: row for row in plan.resources})
    while True:
        pending = sorted((row for row in model.processes.values() if model.materials[row.material_id].active and row.source_step_id not in ('final-inspection', 'final-packaging') and row.status != 'COMPLETED' and (row.predecessor_id is None or model.processes[row.predecessor_id].status == 'COMPLETED')), key=lambda row: (row.step_ordinal, row.id))
        if not pending:
            break
        process = pending[0]
        transform_material(model, process, c.Milliseconds(1000))
        model.processes[process.id] = process.model_copy(update={'status': 'COMPLETED', 'start_ms': 0, 'end_ms': 1000})
    for key, material in model.materials.items():
        if material.active:
            model.materials[key] = material.model_copy(update={'location_id': c.EntityId('OPS-FINAL-INSPECTION-ENTRY')})
    return model


def transition(model: c.SimulationModel, key: str, at_ms: int | None = None) -> c.SimulationModel:
    when = model.run.elapsed_ms if at_ms is None else at_ms
    clocked = model.clone()
    clocked.run = model.run.model_copy(update={'elapsed_ms': when})
    return fulfillment_transition(clocked, c.EntityId(key), c.Milliseconds(when)).model


def arrive_transport(model: c.SimulationModel, material_id: str) -> c.SimulationModel:
    transfer = next(row for row in model.transfers.values() if row.material_id == material_id and row.status != 'ARRIVED')
    assert transfer.status == 'WAITING'
    current = model
    for _ in range(4):
        row = current.transfers[transfer.id]
        if row.status == 'ARRIVED':
            return current
        boundary = current.run.elapsed_ms if row.status == 'WAITING' else row.phase_end_ms
        assert boundary is not None and boundary >= current.run.elapsed_ms
        current.run = current.run.model_copy(update={'elapsed_ms': boundary})
        current = transport_transition(current, transfer.id, boundary).model
    assert current.transfers[transfer.id].status == 'ARRIVED'
    return current



def make_stock(model: c.SimulationModel, material_id: str) -> c.SimulationModel:
    processes = {row.source_step_id: row for row in model.processes.values() if row.material_id == material_id and row.source_step_id in ('final-inspection', 'final-packaging')}
    inspection, packaging = processes[c.EntityId('final-inspection')], processes[c.EntityId('final-packaging')]
    model = transition(model, inspection.id)
    model = transition(model, inspection.id, model.run.elapsed_ms + 2000)
    model = prepare_process_transfer(model, packaging.id, model.run.elapsed_ms).model
    model = arrive_transport(model, material_id)
    model = transition(model, packaging.id)
    model = transition(model, packaging.id, model.run.elapsed_ms + 1500)
    model = transition(model, material_id)
    model = arrive_transport(model, material_id)
    return transition(model, material_id)


def stock_model(product: c.ProductId = 'ga') -> c.SimulationModel:
    model = final_model(product)
    for material in tuple(model.materials.values()):
        if material.active:
            model = make_stock(model, material.id)
    return model


def serialized(model: c.SimulationModel) -> str:
    return json.dumps({field.name: model.run.model_dump(mode='json') if field.name == 'run' else [row.model_dump(mode='json') for row in getattr(model, field.name).values()] for field in fields(model)}, sort_keys=True)


def deliver(model: c.SimulationModel, shipment_id: str, trace: list[str]) -> c.SimulationModel:
    while model.shipments[c.EntityId(shipment_id)].status != 'DELIVERED':
        shipment = model.shipments[c.EntityId(shipment_id)]
        model = transition(model, shipment_id, shipment.phase_end_ms)
        trace.append(serialized(model))
    return model


def test_partial_delivery_when_ga_two_shipments(tmp_path: Path) -> None:
    # Given: three final inspected, packaged and actually received physical units.
    model = stock_model()
    original_orders = model.orders.copy()
    trace: list[str] = []
    # When: deliver the first whole two-unit shipment then the remaining unit.
    first = deliver(model, 'SHIP-ga-01', trace)
    second = deliver(first, 'SHIP-ga-02', trace)
    # Then: first receipt leaves a real 20100 kg remainder; second alone closes order.
    assert asdict(order_totals(first, c.EntityId('ORD-ga'))) == {'produced_kg': 60300, 'dispatched_kg': 40200, 'delivered_kg': 40200, 'remaining_dispatch_kg': 20100, 'remaining_delivery_kg': 20100, 'status': 'PARTIALLY_DELIVERED'}
    assert asdict(order_totals(second, c.EntityId('ORD-ga'))) == {'produced_kg': 60300, 'dispatched_kg': 60300, 'delivered_kg': 60300, 'remaining_dispatch_kg': 0, 'remaining_delivery_kg': 0, 'status': 'DELIVERED'}
    assert second.orders == original_orders and second.material_versions == model.material_versions
    assert [row.event_type for row in first.events.values()].count('ORDER_DELIVERED') == 0
    assert [row.event_type for row in second.events.values()].count('ORDER_DELIVERED') == 1
    for snapshot in map(json.loads, trace):
        materials = {row['id']: row for row in snapshot['materials']}
        for shipment in snapshot['shipments']:
            if shipment['status'] in ('DISPATCHED', 'DELIVERED') or (shipment['status'] == 'IN_TRANSIT' and shipment['location_id'] == 'OPS-SHIP-A-CARGO'):
                members = [row for row in snapshot['shipment_materials'] if row['shipment_id'] == shipment['id']]
                assert all(materials[row['material_id']]['location_id'] == shipment['location_id'] for row in members)
        for resource in snapshot['resources']:
            if resource['id'].startswith('CRANE-'):
                assert sum(row['weight_kg'] for row in materials.values() if row['location_id'] == resource['location_id']) <= resource['capacity_kg']
    destination = Path(os.environ.get('T09_EVIDENCE_DIR', str(tmp_path)))
    (destination / 'T09-partial-delivery.json').write_text(json.dumps({'fixture_boundary': 'manufacturing completed explicitly by transform_material; due_at injected; final inspection onward uses public fulfillment/transport functions', 'first': asdict(order_totals(first, c.EntityId('ORD-ga'))), 'second': asdict(order_totals(second, c.EntityId('ORD-ga'))), 'trace': [json.loads(row) for row in trace]}, indent=2))


@pytest.mark.parametrize('product,total', [('plate', 19900), ('ti-sheet', 11900)])
def test_split_children_ship_together(product: c.ProductId, total: int, tmp_path: Path) -> None:
    # Given: real lineage transform consumed a parent and produced two children.
    model = stock_model(product)
    trace: list[str] = []
    # When: actual public shipment transitions deliver the planned child batch.
    result = deliver(model, f'SHIP-{product}-01', trace)
    # Then: both whole children travel together; parent never gains shipment credit.
    assert sorted(row.material_id for row in result.shipment_materials.values()) == [f'MAT-{product}-01:A', f'MAT-{product}-01:B']
    assert order_totals(result, c.EntityId(f'ORD-{product}')).delivered_kg == total
    assert not result.materials[c.EntityId(f'MAT-{product}-01')].active
    destination = Path(os.environ.get('T09_EVIDENCE_DIR', str(tmp_path)))
    (destination / f'T09-{product}-delivery.json').write_text(json.dumps({'trace': [json.loads(row) for row in trace]}, indent=2))


@pytest.mark.parametrize('quality', ['PENDING', 'HOLD', 'FAILED'])
def test_rejects_unreleased_quality_without_mutation(quality: c.QualityStatus) -> None:
    # Given: current-version inspection is not passed despite physical warehouse stock.
    model = stock_model()
    material = model.materials[c.EntityId('MAT-ga-01')]
    inspection = next(row for row in model.inspections.values() if row.material_id == material.id)
    model.inspections[inspection.id] = inspection.model_copy(update={'status': quality})
    before = serialized(model)
    # When / Then: rejection preserves every collection and event sequence.
    with pytest.raises(c.ContractViolation, match='quality') as error:
        fulfillment_transition(model, c.EntityId('SHIP-ga-01'), model.run.elapsed_ms)
    assert serialized(model) == before
    print(quality, error.value, 'FULL_STATE_UNCHANGED')


Failure = Literal['wrong_order', 'specification', 'already_assigned', 'shipment_capacity', 'current_stock', 'whole_unit', 'old_version', 'resource_busy', 'crane_capacity', 'active_transfer']


@pytest.mark.parametrize('failure', ['wrong_order', 'specification', 'already_assigned', 'shipment_capacity', 'current_stock', 'whole_unit', 'old_version', 'resource_busy', 'crane_capacity', 'active_transfer'])
def test_rejects_ineligible_shipment_without_mutation(failure: Failure) -> None:
    # Given: one independently invalid shipment prerequisite.
    model = stock_model()
    material = model.materials[c.EntityId('MAT-ga-01')]
    shipment = model.shipments[c.EntityId('SHIP-ga-01')]
    key = shipment.id
    match failure:
        case 'wrong_order':
            allocation = next(row for row in model.allocations.values() if row.material_id == material.id)
            model.allocations[allocation.id] = allocation.model_copy(update={'order_id': c.EntityId('ORD-gi')})
        case 'specification':
            model.materials[material.id] = material.model_copy(update={'form': 'GI_COIL'})
        case 'already_assigned':
            row = c.ShipmentMaterial(run_id=model.run.id, id=c.EntityId('DUPLICATE'), shipment_id=c.EntityId('SHIP-ga-02'), material_id=material.id)
            model.shipment_materials[row.id] = row
        case 'shipment_capacity':
            carrier = model.resources[c.EntityId('FLATBED-A')]
            model.resources[carrier.id] = carrier.model_copy(update={'capacity_kg': 30000})
        case 'current_stock':
            model.materials[material.id] = material.model_copy(update={'location_id': 'OPS-PACKAGING-EXIT'})
        case 'whole_unit':
            model.materials[material.id] = material.model_copy(update={'weight_kg': 10000})
        case 'old_version':
            inspection = next(row for row in model.inspections.values() if row.material_id == material.id)
            model.inspections[inspection.id] = inspection.model_copy(update={'inspected_version_id': f'{material.id}:V01'})
        case 'resource_busy':
            model = transition(model, shipment.id)
            carrier = model.resources[c.EntityId('FLATBED-A')]
            model.resources[carrier.id] = carrier.model_copy(update={'reserved_by': c.EntityId('OTHER-TRANSFER')})
        case 'crane_capacity':
            crane = model.resources[c.EntityId('CRANE-WAREHOUSE')]
            model.resources[crane.id] = crane.model_copy(update={'capacity_kg': 15000})
        case 'active_transfer':
            transfer = next(row for row in model.transfers.values() if row.material_id == material.id)
            model.transfers[transfer.id] = transfer.model_copy(update={'status': 'WAITING'})
        case unreachable:
            assert_never(unreachable)
    before = serialized(model)
    # When / Then: no failed allocation/loading leaks rows, positions or sequence.
    with pytest.raises(c.ContractViolation, match='quality' if failure == 'old_version' else failure) as error:
        fulfillment_transition(model, key, model.run.elapsed_ms)
    assert serialized(model) == before
    print(failure, error.value, 'FULL_STATE_UNCHANGED')


def test_final_process_and_stock_gates() -> None:
    # Given: manufacturing is finished but quality and packaging are pending.
    model = final_model()
    key = c.EntityId('MAT-ga-01')
    versions = model.material_versions.copy()
    # When: complete the real quality/packaging/warehouse sequence.
    result = make_stock(model, key)
    # Then: quality timing, endpoint predecessor credit and physical arrival all exist.
    inspection = next(row for row in result.inspections.values() if row.material_id == key)
    assert (inspection.start_ms, inspection.end_ms, inspection.packaging_end_ms) == (1000, 3000, 5500)
    assert all(row.status == 'COMPLETED' for row in result.processes.values() if row.material_id == key)
    assert result.materials[key].availability_status == 'AVAILABLE'
    assert result.material_versions == versions
    assert any(row.material_id == key and row.to_location_id == 'OPS-WAREHOUSE-ENTRY' and row.status == 'ARRIVED' for row in result.transfers.values())


def test_packaging_completion_does_not_credit_stock() -> None:
    # Given: the sequence has reached packaging but no warehouse transfer occurred.
    model = final_model()
    processes = {row.source_step_id: row for row in model.processes.values() if row.material_id == 'MAT-ga-01'}
    model = transition(model, processes[c.EntityId('final-inspection')].id)
    model = transition(model, processes[c.EntityId('final-inspection')].id, 3000)
    model = prepare_process_transfer(model, processes[c.EntityId('final-packaging')].id, model.run.elapsed_ms).model
    model = arrive_transport(model, 'MAT-ga-01')
    model = transition(model, processes[c.EntityId('final-packaging')].id)
    # When: packaging completes.
    result = transition(model, processes[c.EntityId('final-packaging')].id, 5500)
    # Then: material is still WIP and cannot be allocated to a shipment.
    assert result.materials[c.EntityId('MAT-ga-01')].availability_status == 'WIP'
    assert result.materials[c.EntityId('MAT-ga-01')].location_id == 'OPS-PACKAGING-EXIT'
    assert 'SHIP-ga-01' not in ready_fulfillment(result)


def test_cannot_depart_when_only_first_unit_loaded() -> None:
    # Given: first GA coil loaded, second is still on the crane.
    model = transition(stock_model(), 'SHIP-ga-01')
    model = transition(model, 'SHIP-ga-01')
    model = transition(model, 'SHIP-ga-01', model.run.elapsed_ms + 1000)
    shipment = model.shipments[c.EntityId('SHIP-ga-01')]
    model.shipments[shipment.id] = shipment.model_copy(update={'status': 'LOADED'})
    before = serialized(model)
    # When / Then: even a forged status cannot bypass all-material loading.
    with pytest.raises(c.ContractViolation, match='all_loaded'):
        fulfillment_transition(model, shipment.id, model.run.elapsed_ms)
    assert serialized(model) == before


def test_next_boundary_and_readiness_are_pure() -> None:
    # Given: one running inspection, another cannot use its reserved station.
    model = final_model()
    process = next(row for row in model.processes.values() if row.material_id == 'MAT-ga-01' and row.source_step_id == 'final-inspection')
    model = transition(model, process.id)
    before = serialized(model)
    # When: discover the next schedulable boundary.
    boundary = next_boundary(model)
    # Then: scheduled completion is exact and probing has no observable effects.
    assert boundary == 3000 and ready_fulfillment(model) == ()
    assert serialized(model) == before


@pytest.mark.parametrize('field,value', [('grade', 'SYNTHETIC-TI'), ('width_mm', 1500.0), ('thickness_mm', 3.0)])
def test_source_specification_is_independent_of_target_order(field: str, value: str | float) -> None:
    # Given: claimed allocation matches GA, physical provenance resolves to a different spec.
    model = stock_model()
    work = model.work_orders[c.EntityId('WO-ga-01')]
    source = model.orders[c.EntityId('ORD-gi')].model_copy(update={field: value})
    model.orders[source.id] = source
    model.work_orders[work.id] = work.model_copy(update={'order_id': source.id})
    before = serialized(model)
    # When / Then: allocation alone cannot rewrite the physical source specification.
    with pytest.raises(c.ContractViolation, match='specification'):
        fulfillment_transition(model, c.EntityId('SHIP-ga-01'), model.run.elapsed_ms)
    assert serialized(model) == before


@pytest.mark.parametrize('quality', ['HOLD', 'FAILED'])
def test_final_inspection_honors_injected_quality(quality: c.QualityStatus) -> None:
    # Given: explicit quality policy outcome is injected before the final inspection.
    model = final_model()
    material = model.materials[c.EntityId('MAT-ga-01')]
    model.materials[material.id] = material.model_copy(update={'quality_status': quality})
    process = next(row for row in model.processes.values() if row.material_id == material.id and row.source_step_id == 'final-inspection')
    model = transition(model, process.id)
    # When: the real inspection boundary completes.
    result = transition(model, process.id, 3000)
    # Then: held/failed material remains quarantined and packaging cannot start.
    assert result.materials[material.id].quality_status == quality
    assert result.materials[material.id].availability_status == 'QUARANTINED'
    assert not any(row.material_id == material.id and row.release_event_id for row in result.inspections.values())
    assert not any(result.processes[key].material_id == material.id for key in ready_fulfillment(result) if key in result.processes)


@pytest.mark.parametrize('fault', ['no_packaging', 'no_arrival', 'missing_port_member', 'early_inspection'])
def test_later_gates_cannot_be_bypassed(fault: str) -> None:
    # Given: an otherwise eligible state loses one actual predecessor fact.
    model = stock_model()
    shipment_id = c.EntityId('SHIP-ga-01')
    key = shipment_id
    if fault == 'no_packaging':
        inspection = next(row for row in model.inspections.values() if row.material_id == 'MAT-ga-01')
        model.inspections[inspection.id] = inspection.model_copy(update={'packaging_end_ms': None})
    if fault == 'no_arrival':
        model.transfers = {key: row for key, row in model.transfers.items() if row.to_location_id != 'OPS-WAREHOUSE-ENTRY'}
    if fault == 'missing_port_member':
        while model.shipments[shipment_id].status != 'AT_PORT':
            model = transition(model, shipment_id, model.shipments[shipment_id].phase_end_ms)
        row = next(row for row in model.shipment_materials.values() if row.material_id == 'MAT-ga-02')
        del model.shipment_materials[row.id]
    if fault == 'early_inspection':
        model = final_model()
        key = next(row.id for row in model.processes.values() if row.material_id == 'MAT-ga-01' and row.source_step_id == 'final-inspection')
        model = transition(model, key)
        model.run = model.run.model_copy(update={'elapsed_ms': 2999})
    before = serialized(model)
    # When / Then: no early stock, incomplete sea departure or early release is possible.
    with pytest.raises(c.ContractViolation):
        fulfillment_transition(model, key, model.run.elapsed_ms)
    assert serialized(model) == before


def test_public_scheduler_preserves_hook_capacity_and_leg_durations(tmp_path: Path) -> None:
    # Given: both complete GA batches compete for the real shared flatbed and ship.
    model = stock_model()
    trace: list[str] = []
    first_delivered: OrderTotals | None = None
    # When: only public readiness and boundary discovery drive all shipment phases.
    for _ in range(100):
        ready = ready_fulfillment(model)
        if ready:
            model = fulfillment_transition(model, ready[0], model.run.elapsed_ms).model
            trace.append(serialized(model))
        else:
            boundary = next_boundary(model)
            if boundary is None:
                break
            assert boundary > model.run.elapsed_ms
            model.run = model.run.model_copy(update={'elapsed_ms': boundary})
        if first_delivered is None and model.shipments[c.EntityId('SHIP-ga-01')].status == 'DELIVERED':
            first_delivered = order_totals(model, c.EntityId('ORD-ga'))
        for resource in model.resources.values():
            if resource.id.startswith('CRANE-'):
                assert sum(row.weight_kg for row in model.materials.values() if row.location_id == resource.location_id) <= resource.capacity_kg
    # Then: each hook carries at most one whole coil and all approved leg times remain exact.
    assert first_delivered is not None and first_delivered.remaining_delivery_kg == 20100
    assert order_totals(model, c.EntityId('ORD-ga')).status == 'DELIVERED'
    events = [row for row in model.events.values() if row.entity_id == 'SHIP-ga-01']
    arrival = next(row.at_ms for row in events if row.event_type == 'SHIPMENT_AT_PORT')
    sailing = next(row.at_ms for row in events if row.event_type == 'SHIPMENT_SAILING')
    unloading = [row.at_ms for row in events if row.event_type == 'TRANSFER_UNLOADING']
    delivered = next(row.at_ms for row in events if row.event_type == 'SHIPMENT_DELIVERED')
    assert sailing - arrival == 2000
    layout = load_factory_layout()
    sea = next(path for path in layout.paths if path.id == 'PATH-SHIP--CUSTOMER')
    sea_ms = max(3000, ceil(sum(dist(a, b) for a, b in zip(sea.points, sea.points[1:])) / 10 * 10) * 100)
    assert unloading[0] - sailing == sea_ms and delivered - unloading[0] == 1000
    road = next(path for path in layout.paths if path.id == 'PATH-WAREHOUSE--PORT')
    buffer = next(row.position for row in layout.locations if row.id == 'OPS-PORT-BUFFER')
    road_points = (*road.points, buffer)
    road_ms = max(3000, ceil(sum(dist(a, b) for a, b in zip(road_points, road_points[1:])) / 20 * 10) * 100)
    dispatch = next(row.at_ms for row in events if row.event_type == 'SHIPMENT_DISPATCHED')
    assert arrival - dispatch == road_ms
    assert unloading[1] - unloading[0] == 500
    destination = Path(os.environ.get('T09_EVIDENCE_DIR', str(tmp_path)))
    (destination / 'T09-scheduler-custody.json').write_text(json.dumps({'first_delivery': asdict(first_delivered), 'trace': [json.loads(row) for row in trace]}, indent=2))


def test_packaging_fifo_uses_actual_inspection_completion(tmp_path: Path) -> None:
    # Given: MAT-ga-02 clears inspection before lexically earlier MAT-ga-01.
    model = final_model()
    packaging_ids = []
    for material_id in ('MAT-ga-02', 'MAT-ga-01'):
        inspection = next(row for row in model.processes.values() if row.material_id == material_id and row.source_step_id == 'final-inspection')
        packaging = next(row for row in model.processes.values() if row.material_id == material_id and row.source_step_id == 'final-packaging')
        model = transition(model, inspection.id)
        model = transition(model, inspection.id, model.run.elapsed_ms + 2000)
        model = prepare_process_transfer(model, packaging.id, model.run.elapsed_ms).model
        model = arrive_transport(model, material_id)
        packaging_ids.append(packaging.id)
    # When: the public scheduler starts the first eligible packaging candidate.
    ready = tuple(key for key in ready_fulfillment(model) if key in packaging_ids)
    result = fulfillment_transition(model, ready[0], model.run.elapsed_ms)
    # Then: actual release times control contention instead of fixture zero/ID order.
    assert [model.processes[key].ready_at_ms for key in packaging_ids] == [3000, 6000]
    assert result.model.processes[packaging_ids[0]].status == 'RUNNING'
    assert result.model.processes[packaging_ids[1]].status == 'QUEUED'
    destination = Path(os.environ.get('T09_EVIDENCE_DIR', str(tmp_path)))
    (destination / 'T09-packaging-fifo.json').write_text(json.dumps({'ready': ready, 'processes': [result.model.processes[key].model_dump(mode='json') for key in packaging_ids], 'delta': result.delta.model_dump(mode='json')}, indent=2))


@pytest.mark.parametrize('product', ['ga', 'sts-cr', 'ti-cr'])
def test_packaged_finished_units_use_real_flatbed_handoff_before_warehouse_stock(product):
    model = final_model(product)
    material = next(row for row in model.materials.values() if row.active)
    stocked = make_stock(model, material.id)
    transfer = next(row for row in stocked.transfers.values() if row.material_id == material.id and row.to_location_id == 'OPS-WAREHOUSE-ENTRY')
    assert transfer.mode == 'flatbed' and transfer.vehicle_id == 'FLATBED-A'
    assert transfer.status == 'ARRIVED'
    events = [row for row in stocked.events.values() if row.entity_id == transfer.id]
    assert [row.event_type for row in events] == ['TRANSFER_STARTED', 'TRANSFER_LOADING', 'TRANSFER_DEPARTED', 'TRANSFER_UNLOADING', 'TRANSFER_ARRIVED']
    assert events[3].at_ms - events[2].at_ms == transfer.travel_duration_ms >= 3000
    available = next(row for row in stocked.events.values() if row.material_id == material.id and row.event_type == 'MATERIAL_AVAILABLE')
    assert available.at_ms == events[-1].at_ms
    assert stocked.materials[material.id].location_id == 'OPS-WAREHOUSE-BUFFER'
    assert all(row.reserved_by != transfer.id for row in stocked.resources.values())
