"""Pure final quality and physical shipment transitions sharing transport reservations.

Specifications are synthetic provenance from lot/work/order, not measurements.
Only manufacturing creates physical versions. All edits occur on an owned clone.
"""
# noqa: SIZE_OK -- T9's assigned module owns the complete quality/dispatch state machine.
from dataclasses import dataclass
from datetime import timedelta
from functools import lru_cache
from typing import Final, assert_never

from app.operations import contracts as c
from app.operations.catalog import OperationRoute, route
from app.operations.events import EventDraft, diff_models, emit_event
from app.operations.fixtures import ShipmentMembership, shipment_memberships
from app.operations.layout import FactoryLayout, load_factory_layout
from app.operations.travel import shipment_duration_ms

ENDPOINTS: Final = ('final-inspection', 'final-packaging')
DEPARTED: Final = ('DISPATCHED', 'AT_PORT', 'IN_TRANSIT', 'DELIVERED')


@dataclass(frozen=True, slots=True)
class OrderTotals:
    produced_kg: int
    dispatched_kg: int
    delivered_kg: int
    remaining_dispatch_kg: int
    remaining_delivery_kg: int
    status: c.OrderStatus


@lru_cache(maxsize=1)
def _layout() -> FactoryLayout:
    return load_factory_layout()


@lru_cache(maxsize=20)
def _route(product: c.ProductId) -> OperationRoute:
    return route(product)


@lru_cache(maxsize=20)
def _memberships(product: c.ProductId) -> tuple[ShipmentMembership, ...]:
    return shipment_memberships(product)


def _source_order(model: c.SimulationModel, material: c.Material) -> c.OperationsOrder:
    return model.orders[model.work_orders[model.lots[material.lot_id].work_order_id].order_id]


def _inspection(model: c.SimulationModel, material: c.Material) -> c.Inspection | None:
    return next((row for row in model.inspections.values() if row.material_id == material.id and row.inspected_version_id == material.current_version_id), None)


def _passed(model: c.SimulationModel, material: c.Material) -> bool:
    inspection = _inspection(model, material)
    return material.active and material.quality_status == 'PASSED' and inspection is not None and inspection.status == 'PASSED' and inspection.end_ms is not None and inspection.end_ms <= model.run.elapsed_ms


def order_totals(model: c.SimulationModel, order_id: c.EntityId) -> OrderTotals:
    """Count current final physical units once; receipt orders remain immutable."""
    order = model.orders[order_id]
    produced = sum(row.weight_kg for row in model.materials.values() if _passed(model, row) and _source_order(model, row).id == order_id and row.form == _route(order.product_id).output_form)
    assignments = tuple(row for row in model.shipment_materials.values() if row.active and model.shipments[row.shipment_id].order_id == order_id)
    dispatched = sum(model.materials[row.material_id].weight_kg for row in assignments if model.shipments[row.shipment_id].status in DEPARTED)
    delivered = sum(model.materials[row.material_id].weight_kg for row in assignments if model.shipments[row.shipment_id].status == 'DELIVERED')
    status: c.OrderStatus = 'RECEIVED'
    if any(row.order_id == order_id and row.active for row in model.allocations.values()):
        status = 'IN_PRODUCTION'
    if produced == order.quantity_kg:
        status = 'READY'
    if dispatched:
        status = 'DISPATCHED' if dispatched == order.quantity_kg else 'PARTIALLY_DISPATCHED'
    if delivered:
        status = 'DELIVERED' if delivered == order.quantity_kg else 'PARTIALLY_DELIVERED'
    return OrderTotals(produced, dispatched, delivered, order.quantity_kg - dispatched, order.quantity_kg - delivered, status)


def _require(condition: bool, code: str, entity_id: str) -> None:
    if not condition:
        raise c.ContractViolation(code, entity_id)


def _reserve(model: c.SimulationModel, owner: c.EntityId, names: tuple[str, ...], at_ms: c.Milliseconds, release: bool = False) -> None:
    """Reserve real shared carriers/hooks; called only on the transaction clone."""
    for name in names:
        key = c.EntityId(name)
        resource = model.resources[key]
        _require(resource.reserved_by in (None, owner) and resource.available_at_ms <= at_ms and (resource.unavailable_from_ms is None or at_ms < resource.unavailable_from_ms or (resource.unavailable_until_ms is not None and at_ms >= resource.unavailable_until_ms)), 'resource_busy', name)
        model.resources[key] = resource.model_copy(update={'reserved_by': None if release else owner})


def _event(model: c.SimulationModel, kind: c.EventType, entity_id: c.EntityId, at_ms: c.Milliseconds, *, material_id: c.EntityId | None = None, process_id: c.EntityId | None = None) -> c.OperationEvent:
    entity_type: c.EntityKind = 'shipment' if entity_id in model.shipments else 'process' if entity_id in model.processes else 'material'
    return emit_event(model, EventDraft(kind, entity_type, entity_id, at_ms, material_id=material_id, process_id=process_id))


def _endpoint(model: c.SimulationModel, process: c.ProcessExecution, at_ms: c.Milliseconds) -> None:
    material = model.materials[process.material_id]
    _require(material.active and any(row.material_id == material.id and row.active for row in model.allocations.values()), 'inactive_allocation', material.id)
    station = next(row for row in _layout().equipment if row.id == process.equipment_id)
    inspect = process.source_step_id == 'final-inspection'
    match process.status:
        case 'QUEUED' | 'BLOCKED':
            _require(process.predecessor_id is not None and model.processes[process.predecessor_id].status == 'COMPLETED' and process.ready_at_ms <= at_ms, 'predecessor', process.id)
            _require(material.location_id == station.anchors.entry.location_id and not any(row.material_id == material.id and row.status != 'ARRIVED' for row in model.transfers.values()), 'station_arrival', material.id)
            if not inspect:
                _require(_passed(model, material), 'quality', material.id)
            _reserve(model, process.id, (process.equipment_id,), at_ms)
            _require(material.weight_kg <= model.resources[process.equipment_id].capacity_kg and material.form == process.input_form, 'process_capacity_or_form', material.id)
            end = c.Milliseconds(at_ms + (2000 if inspect else 1500))
            model.processes[process.id] = process.model_copy(update={'status': 'RUNNING', 'start_ms': at_ms, 'end_ms': end, 'blocked_reason': None})
            model.materials[material.id] = material.model_copy(update={'location_id': c.EntityId(station.anchors.work.location_id)})
            if inspect:
                inspection = c.Inspection(run_id=model.run.id, id=c.EntityId(f'INSPECT-{material.current_version_id}'), material_id=material.id, inspected_version_id=material.current_version_id, status=material.quality_status, start_ms=at_ms, end_ms=end)
                model.inspections[inspection.id] = inspection
            _event(model, 'INSPECTION_STARTED' if inspect else 'PACKAGING_STARTED', process.id, at_ms, material_id=material.id, process_id=process.id)
        case 'RUNNING':
            _require(process.end_ms == at_ms, 'boundary_time', process.id)
            inspection = _inspection(model, material)
            _require(inspection is not None, 'inspection_version', material.id)
            if inspection is None:
                return
            if not inspect:
                _require(_passed(model, material), 'quality', material.id)
            quality: c.QualityStatus = inspection.status
            if inspect:
                match quality:
                    case 'PENDING' | 'PASSED':
                        quality, kind = 'PASSED', 'INSPECTION_PASSED'
                    case 'HOLD':
                        kind = 'INSPECTION_HELD'
                    case 'FAILED':
                        kind = 'INSPECTION_FAILED'
                    case unreachable:
                        assert_never(unreachable)
                event = _event(model, kind, process.id, at_ms, material_id=material.id, process_id=process.id)
                model.inspections[inspection.id] = inspection.model_copy(update={'status': quality, 'release_event_id': event.id if quality == 'PASSED' else None})
            else:
                _event(model, 'PACKAGING_COMPLETED', process.id, at_ms, material_id=material.id, process_id=process.id)
                model.inspections[inspection.id] = inspection.model_copy(update={'packaging_end_ms': at_ms})
            model.processes[process.id] = process.model_copy(update={'status': 'COMPLETED'})
            for successor in tuple(model.processes.values()):
                if successor.predecessor_id == process.id:
                    model.processes[successor.id] = successor.model_copy(update={'ready_at_ms': at_ms})
            model.materials[material.id] = material.model_copy(update={'location_id': c.EntityId(station.anchors.exit.location_id), 'quality_status': quality, 'availability_status': 'WIP' if quality == 'PASSED' else 'QUARANTINED'})
            _reserve(model, process.id, (process.equipment_id,), at_ms, release=True)
        case 'COMPLETED':
            raise c.ContractViolation('already_completed', process.id)
        case unreachable:
            assert_never(unreachable)


def _stock(model: c.SimulationModel, material: c.Material, at_ms: c.Milliseconds) -> c.SimulationModel:
    inspection = _inspection(model, material)
    _require(_passed(model, material) and inspection is not None and inspection.packaging_end_ms is not None and inspection.packaging_end_ms <= at_ms, 'packaging', material.id)
    _require(material.availability_status == 'WIP', 'stock_status', material.id)
    arrived = any(row.material_id == material.id and row.to_location_id == 'OPS-WAREHOUSE-ENTRY' and row.status == 'ARRIVED' for row in model.transfers.values())
    if not arrived:
        from app.operations.transport import prepare_warehouse_transfer
        return prepare_warehouse_transfer(model, material.id, at_ms).model
    _require(material.location_id == 'OPS-WAREHOUSE-ENTRY', 'warehouse_arrival', material.id)
    model.materials[material.id] = material.model_copy(update={'location_id': c.EntityId('OPS-WAREHOUSE-BUFFER'), 'availability_status': 'AVAILABLE'})
    _event(model, 'MATERIAL_AVAILABLE', material.id, at_ms, material_id=material.id)
    return model


def _members(model: c.SimulationModel, shipment: c.OperationsShipment) -> tuple[c.Material, ...]:
    members = tuple(row for row in _memberships(model.orders[shipment.order_id].product_id) if row.shipment_id == shipment.id)
    _require(bool(members) and all(row.material_id in model.materials for row in members), 'missing_members', shipment.id)
    return tuple(model.materials[row.material_id] for row in members)


def _eligible(model: c.SimulationModel, shipment: c.OperationsShipment, materials: tuple[c.Material, ...], allocating: bool) -> None:
    order = model.orders[shipment.order_id]
    recipe = _route(order.product_id)
    expected = {row.material_id: row.final_planned_kg for row in _memberships(order.product_id)}
    for material in materials:
        _require(_passed(model, material), 'quality', material.id)
        inspection = _inspection(model, material)
        _require(inspection is not None and inspection.packaging_end_ms is not None and inspection.packaging_end_ms <= model.run.elapsed_ms and any(row.material_id == material.id and row.to_location_id == 'OPS-WAREHOUSE-ENTRY' and row.status == 'ARRIVED' for row in model.transfers.values()), 'current_stock', material.id)
        source = _source_order(model, material)
        _require((source.grade, source.width_mm, source.thickness_mm) == (order.grade, order.width_mm, order.thickness_mm) and material.form == recipe.output_form, 'specification', material.id)
        _require(source.id == order.id and any(row.material_id == material.id and row.order_id == order.id and row.active for row in model.allocations.values()), 'wrong_order', material.id)
        version = model.material_versions[material.current_version_id]
        _require((version.material_id, version.form, version.weight_kg) == (material.id, material.form, material.weight_kg) and material.weight_kg == expected[material.id], 'whole_unit', material.id)
        if allocating:
            _require(not any(row.material_id == material.id and row.active for row in model.shipment_materials.values()), 'already_assigned', material.id)
            _require(material.availability_status == 'AVAILABLE' and material.location_id == recipe.dispatch_location_id, 'current_stock', material.id)
        _require(not any(row.material_id == material.id and row.status != 'ARRIVED' for row in model.transfers.values()), 'active_transfer', material.id)
        for name in ('CRANE-WAREHOUSE', 'CRANE-PORT', 'CRANE-SHIP', 'CRANE-CUSTOMER'):
            _require(material.weight_kg <= model.resources[c.EntityId(name)].capacity_kg, 'crane_capacity', material.id)
    total = sum(row.weight_kg for row in materials)
    _require(total <= min(shipment.capacity_kg, model.resources[c.EntityId('FLATBED-A')].capacity_kg, model.resources[c.EntityId('SHIP-A')].capacity_kg), 'shipment_capacity', shipment.id)


def _shipment(model: c.SimulationModel, shipment: c.OperationsShipment, at_ms: c.Milliseconds) -> None:
    materials = _members(model, shipment)
    rows = tuple(row for row in model.shipment_materials.values() if row.shipment_id == shipment.id and row.active)
    if shipment.status != 'PLANNED':
        _require({row.material_id for row in rows} == {row.id for row in materials}, 'membership', shipment.id)
    if shipment.status == 'DISPATCHED':
        _require(all(row.loaded for row in rows), 'all_loaded', shipment.id)
    state, location, end = shipment.status, shipment.location_id, None
    kind: c.EventType
    match state:
        case 'PLANNED':
            _eligible(model, shipment, materials, allocating=True)
            for material in materials:
                row = c.ShipmentMaterial(run_id=model.run.id, id=c.EntityId(f'{shipment.id}:{material.id}'), shipment_id=shipment.id, material_id=material.id)
                model.shipment_materials[row.id] = row
                model.materials[material.id] = material.model_copy(update={'availability_status': 'RESERVED'})
            state, kind = 'ALLOCATED', 'SHIPMENT_ALLOCATED'
        case 'ALLOCATED':
            _eligible(model, shipment, materials, allocating=False)
            _require({row.material_id for row in rows} == {row.id for row in materials}, 'membership', shipment.id)
            _reserve(model, shipment.id, ('FLATBED-A', 'CRANE-WAREHOUSE', 'CRANE-PORT'), at_ms)
            material = materials[0]
            model.materials[material.id] = material.model_copy(update={'location_id': c.EntityId('OPS-CRANE-WAREHOUSE-HOOK')})
            state, kind, end = 'LOADING', 'SHIPMENT_LOADING', at_ms + 1000
        case 'LOADING':
            _require(shipment.phase_end_ms == at_ms, 'boundary_time', shipment.id)
            unloaded = [row for row in rows if not row.loaded]
            _require(bool(unloaded), 'membership', shipment.id)
            row = unloaded[0]
            material = model.materials[row.material_id]
            _require(material.location_id == 'OPS-CRANE-WAREHOUSE-HOOK', 'load_location', material.id)
            model.shipment_materials[row.id] = row.model_copy(update={'loaded': True})
            model.materials[material.id] = material.model_copy(update={'location_id': c.EntityId('OPS-FLATBED-A-CARGO')})
            _event(model, 'MATERIAL_LOADED', shipment.id, at_ms, material_id=material.id)
            if len(unloaded) > 1:
                following = model.materials[unloaded[1].material_id]
                model.materials[following.id] = following.model_copy(update={'location_id': c.EntityId('OPS-CRANE-WAREHOUSE-HOOK')})
                kind, end = 'SHIPMENT_LOADING', at_ms + 1000
            else:
                state, kind, location = 'LOADED', 'SHIPMENT_LOADED', c.EntityId('OPS-FLATBED-A-CARGO')
        case 'LOADED':
            _eligible(model, shipment, materials, allocating=False)
            _require({row.material_id for row in rows} == {row.id for row in materials} and all(row.loaded for row in rows) and all(row.location_id == 'OPS-FLATBED-A-CARGO' for row in materials), 'all_loaded', shipment.id)
            _require(model.resources[c.EntityId('FLATBED-A')].reserved_by == shipment.id, 'carrier_owner', shipment.id)
            state, kind, end = 'DISPATCHED', 'SHIPMENT_DISPATCHED', at_ms + shipment_duration_ms(_layout(), 'road')
        case 'DISPATCHED':
            _require(shipment.phase_end_ms == at_ms, 'boundary_time', shipment.id)
            state, kind, location = 'AT_PORT', 'SHIPMENT_AT_PORT', c.EntityId('OPS-PORT-BUFFER')
            _reserve(model, shipment.id, ('FLATBED-A', 'CRANE-WAREHOUSE'), at_ms, release=True)
        case 'AT_PORT':
            if shipment.phase_end_ms is None:
                _require(all(row.loaded for row in rows) and all(row.location_id == 'OPS-PORT-BUFFER' for row in materials), 'port_loading', shipment.id)
                _reserve(model, shipment.id, ('SHIP-A', 'CRANE-PORT', 'CRANE-SHIP', 'CRANE-CUSTOMER'), at_ms)
                for row in rows:
                    model.shipment_materials[row.id] = row.model_copy(update={'loaded': False})
                first = model.materials[rows[0].material_id]
                model.materials[first.id] = first.model_copy(update={'location_id': c.EntityId('OPS-CRANE-PORT-HOOK')})
                kind, end = 'SHIPMENT_LOADING', at_ms + 2000 // len(rows)
            else:
                unloaded = [row for row in rows if not row.loaded]
                _require(shipment.phase_end_ms == at_ms and bool(unloaded), 'port_loading', shipment.id)
                row = unloaded[0]
                material = model.materials[row.material_id]
                _require(material.location_id == 'OPS-CRANE-PORT-HOOK', 'port_loading', material.id)
                model.shipment_materials[row.id] = row.model_copy(update={'loaded': True})
                model.materials[material.id] = material.model_copy(update={'location_id': c.EntityId('OPS-SHIP-A-CARGO')})
                _event(model, 'MATERIAL_LOADED', shipment.id, at_ms, material_id=material.id)
                if len(unloaded) > 1:
                    following = model.materials[unloaded[1].material_id]
                    model.materials[following.id] = following.model_copy(update={'location_id': c.EntityId('OPS-CRANE-PORT-HOOK')})
                    kind, end = 'SHIPMENT_LOADING', at_ms + 2000 // len(rows)
                else:
                    _require(all(model.materials[row.material_id].location_id == 'OPS-SHIP-A-CARGO' for row in rows), 'all_loaded', shipment.id)
                    state, kind, location, end = 'IN_TRANSIT', 'SHIPMENT_SAILING', c.EntityId('OPS-SHIP-A-CARGO'), at_ms + shipment_duration_ms(_layout(), 'sea')
                    _reserve(model, shipment.id, ('CRANE-PORT', 'CRANE-SHIP'), at_ms, release=True)
        case 'IN_TRANSIT':
            _require(shipment.phase_end_ms == at_ms, 'boundary_time', shipment.id)
            if shipment.location_id == 'OPS-SHIP-A-CARGO':
                _require(all(row.loaded for row in rows) and all(row.location_id == 'OPS-SHIP-A-CARGO' for row in materials), 'customer_arrival', shipment.id)
                first = model.materials[rows[0].material_id]
                model.materials[first.id] = first.model_copy(update={'location_id': c.EntityId('OPS-CRANE-CUSTOMER-HOOK')})
                kind, location, end = 'TRANSFER_UNLOADING', c.EntityId('OPS-CUSTOMER-ENTRY'), at_ms + 1000 // len(rows)
            else:
                loaded = [row for row in rows if row.loaded]
                _require(shipment.location_id == 'OPS-CUSTOMER-ENTRY' and bool(loaded), 'customer_arrival', shipment.id)
                row = loaded[0]
                material = model.materials[row.material_id]
                _require(material.location_id == 'OPS-CRANE-CUSTOMER-HOOK', 'customer_arrival', material.id)
                model.shipment_materials[row.id] = row.model_copy(update={'loaded': False})
                model.materials[material.id] = material.model_copy(update={'location_id': c.EntityId('OPS-CUSTOMER-BUFFER')})
                if len(loaded) > 1:
                    following = model.materials[loaded[1].material_id]
                    model.materials[following.id] = following.model_copy(update={'location_id': c.EntityId('OPS-CRANE-CUSTOMER-HOOK')})
                    kind, end = 'TRANSFER_UNLOADING', at_ms + 1000 // len(rows)
                else:
                    _require(all(model.materials[row.material_id].location_id == 'OPS-CUSTOMER-BUFFER' for row in rows), 'customer_arrival', shipment.id)
                    state, kind, location = 'DELIVERED', 'SHIPMENT_DELIVERED', c.EntityId('OPS-CUSTOMER-BUFFER')
                    _reserve(model, shipment.id, ('SHIP-A', 'CRANE-CUSTOMER'), at_ms, release=True)
        case 'DELIVERED':
            raise c.ContractViolation('already_delivered', shipment.id)
        case unreachable:
            assert_never(unreachable)
    model.shipments[shipment.id] = shipment.model_copy(update={'status': state, 'location_id': location, 'phase_start_ms': at_ms, 'phase_end_ms': end, 'etd_at': model.run.epoch_at + timedelta(milliseconds=at_ms * 60) if kind == 'SHIPMENT_DISPATCHED' else shipment.etd_at, 'delivered_at': model.run.epoch_at + timedelta(milliseconds=at_ms * 60) if state == 'DELIVERED' else shipment.delivered_at})
    if kind in ('SHIPMENT_DISPATCHED', 'SHIPMENT_AT_PORT', 'SHIPMENT_SAILING', 'SHIPMENT_DELIVERED'):
        for material in materials:
            model.materials[material.id] = material.model_copy(update={'location_id': location, 'availability_status': 'SHIPPED'})
    _event(model, kind, shipment.id, at_ms)
    if state == 'DELIVERED' and order_totals(model, shipment.order_id).remaining_delivery_kg == 0:
        emit_event(model, EventDraft('ORDER_DELIVERED', 'order', shipment.order_id, at_ms, order_id=shipment.order_id))


def fulfillment_transition(model: c.SimulationModel, entity_id: c.EntityId, at_ms: c.Milliseconds) -> c.TransitionResult:
    """Apply one due endpoint, warehouse or shipment boundary; failures change nothing."""
    _require(at_ms == model.run.elapsed_ms, 'clock_boundary', entity_id)
    updated = model.clone()
    if entity_id in updated.processes:
        process = updated.processes[entity_id]
        _require(process.source_step_id in ENDPOINTS, 'not_fulfillment', entity_id)
        _endpoint(updated, process, at_ms)
    elif entity_id in updated.materials:
        updated = _stock(updated, updated.materials[entity_id], at_ms)
    elif entity_id in updated.shipments:
        _shipment(updated, updated.shipments[entity_id], at_ms)
    else:
        raise c.ContractViolation('unknown_entity', entity_id)
    return c.TransitionResult(updated, diff_models(model, updated))


def ready_fulfillment(model: c.SimulationModel) -> tuple[c.EntityId, ...]:
    """Return only transitions that can make progress at the current clock boundary."""
    candidates = [row.id for row in model.processes.values() if row.source_step_id in ENDPOINTS and model.materials[row.material_id].active and ((row.status == 'RUNNING' and row.end_ms == model.run.elapsed_ms) or (row.status in ('QUEUED', 'BLOCKED') and row.predecessor_id is not None and model.processes[row.predecessor_id].status == 'COMPLETED' and model.resources[row.equipment_id].reserved_by is None))]
    candidates += [row.id for row in model.materials.values() if row.active and row.availability_status == 'WIP' and _passed(model, row)]
    candidates += [row.id for row in model.shipments.values() if row.status != 'DELIVERED' and (row.phase_end_ms is None or row.phase_end_ms == model.run.elapsed_ms)]
    ready = []
    def queue_key(key: c.EntityId) -> tuple[int, str, str, int]:
        if key in model.processes:
            process = model.processes[key]
            return process.ready_at_ms, _source_order(model, model.materials[process.material_id]).id, process.material_id, process.step_ordinal
        if key in model.materials:
            return 0, _source_order(model, model.materials[key]).id, key, 0
        shipment = model.shipments[key]
        return shipment.phase_start_ms or 0, shipment.order_id, key, 0

    for key in sorted(candidates, key=queue_key):
        try:
            result = fulfillment_transition(model, key, model.run.elapsed_ms)
        except c.ContractViolation:
            continue
        if result.delta != c.TransitionDelta():
            ready.append(key)
    return tuple(ready)


def next_boundary(model: c.SimulationModel) -> c.Milliseconds | None:
    """Next timed boundary; blocked prerequisites never produce a zero-time loop."""
    if ready_fulfillment(model):
        return model.run.elapsed_ms
    times = [row.end_ms for row in model.processes.values() if row.source_step_id in ENDPOINTS and row.status == 'RUNNING' and row.end_ms is not None]
    times += [row.phase_end_ms for row in model.shipments.values() if row.status != 'DELIVERED' and row.phase_end_ms is not None]
    times += [row.available_at_ms for row in model.resources.values() if row.reserved_by is None]
    times += [row.unavailable_until_ms for row in model.resources.values() if row.unavailable_until_ms is not None]
    future = [value for value in times if value > model.run.elapsed_ms]
    return c.Milliseconds(min(future)) if future else None
