"""Pure custody transitions over shared paths; material location is authoritative."""
from functools import lru_cache
from math import dist
from typing import assert_never

from app.operations import contracts as c
from app.operations.events import EventDraft, diff_models, emit_event
from app.operations.engine import material_ready_at
from app.operations.layout import FactoryLayout, TransferPath, load_factory_layout
from app.operations.travel import travel_duration_ms


@lru_cache(maxsize=1)
def _layout() -> FactoryLayout:
    return load_factory_layout()


def resolve_path(source: c.EntityId, destination: c.EntityId) -> TransferPath:
    """Resolve equipment-owned anchors without manufacturing an off-layout route."""
    layout = _layout()
    locations = {row.id: row for row in layout.locations}
    if source not in locations or destination not in locations:
        raise c.ContractViolation('transport_location', f'{source}->{destination}')
    paths = [row for row in layout.paths if locations[row.from_location_id].owner_id == locations[source].owner_id and row.to_location_id == destination]
    if len(paths) != 1:
        raise c.ContractViolation('transport_path', f'{source}->{destination}')
    if dist(locations[source].position, locations[paths[0].from_location_id].position) >= 0.01:
        raise c.ContractViolation('transport_custody', source)
    return paths[0]


def _path(transfer: c.Transfer) -> TransferPath:
    path = resolve_path(transfer.from_location_id, transfer.to_location_id)
    if (path.from_location_id, path.mode, path.vehicle_id) != (transfer.from_location_id, transfer.mode, transfer.vehicle_id):
        raise c.ContractViolation('transport_path', transfer.id)
    return path


def _resource_ids(path: TransferPath) -> tuple[c.EntityId, ...]:
    return tuple(c.EntityId(value) for value in (path.pickup_crane_id, path.vehicle_id, path.drop_crane_id, path.id if path.custody_location_id else None) if value is not None)


def _validate(model: c.SimulationModel, transfer: c.Transfer, at_ms: c.Milliseconds) -> None:
    material, path = model.materials[transfer.material_id], _path(transfer)
    order = model.orders[model.work_orders[model.lots[material.lot_id].work_order_id].order_id]
    if transfer.mode == 'roller' and path.custody_location_id is None:
        raise c.ContractViolation('transport_custody', path.id)
    if not material.active or material.weight_kg > transfer.capacity_kg:
        raise c.ContractViolation('transport_capacity', transfer.id)
    if sum(row.material_id == material.id and row.status != 'ARRIVED' for row in model.transfers.values()) != 1:
        raise c.ContractViolation('transport_duplicate', material.id)
    if material.form in ('HOT_METAL', 'LIQUID_STEEL') and transfer.mode != {'HOT_METAL': 'hot_metal_car', 'LIQUID_STEEL': 'ladle_car'}[material.form]:
        raise c.ContractViolation('transport_form', transfer.id)
    if material.form in ('HOT_STRIP', 'STRIP', 'THIN_STRIP', 'COATED_STRIP', 'WIRE') and transfer.mode != 'roller':
        raise c.ContractViolation('transport_form', transfer.id)
    resource_ids = _resource_ids(path)
    capabilities = resource_ids or (c.EntityId(next(row.owner_id for row in _layout().locations if row.id == path.to_location_id)),)
    for resource_id in capabilities:
        resource = model.resources[resource_id]
        if material.weight_kg > resource.capacity_kg:
            raise c.ContractViolation('transport_capacity', resource.id)
        if material.form not in resource.compatible_forms:
            raise c.ContractViolation('transport_form', resource.id)
        if resource.compatible_grades and order.grade not in resource.compatible_grades:
            raise c.ContractViolation('transport_grade', resource.id)
        if order.width_mm is not None and ((resource.min_width_mm is not None and order.width_mm < resource.min_width_mm) or (resource.max_width_mm is not None and order.width_mm > resource.max_width_mm)):
            raise c.ContractViolation('transport_width', resource.id)
        if resource_id in resource_ids and (resource.reserved_by not in (None, transfer.id) or resource.available_at_ms > at_ms or (resource.unavailable_from_ms is not None and resource.unavailable_from_ms <= at_ms and (resource.unavailable_until_ms is None or at_ms < resource.unavailable_until_ms))):
            raise c.ContractViolation('transport_reserved', resource.id)


def _create(model: c.SimulationModel, transfer: c.Transfer, at_ms: c.Milliseconds) -> c.TransitionResult:
    owned = model.clone()
    owned.transfers[transfer.id] = transfer
    owned.materials[transfer.material_id] = model.materials[transfer.material_id].model_copy(update={'location_id': transfer.from_location_id})
    return c.TransitionResult(owned, diff_models(model, owned))


def _transfer(model: c.SimulationModel, material_id: c.EntityId, path: TransferPath) -> c.Transfer:
    match path.mode:
        case 'ship':
            raise c.ContractViolation('transport_ship_owner', path.id)
        case 'roller' | 'flatbed' | 'hot_metal_car' | 'ladle_car' as mode:
            capacities = [model.resources[key].capacity_kg for key in _resource_ids(path)]
            destination = c.EntityId(next(row.owner_id for row in _layout().locations if row.id == path.to_location_id))
            return c.Transfer(run_id=model.run.id, id=c.EntityId(f'TR-{material_id}-{path.id}'), material_id=material_id, from_location_id=c.EntityId(path.from_location_id), to_location_id=c.EntityId(path.to_location_id), mode=mode, vehicle_id=c.EntityId(path.vehicle_id) if path.vehicle_id else None, crane_id=c.EntityId(path.pickup_crane_id) if path.pickup_crane_id else None, status='WAITING', capacity_kg=min(capacities) if capacities else model.resources[destination].capacity_kg, travel_duration_ms=travel_duration_ms(path))
        case unreachable:
            assert_never(unreachable)


def prepare_process_transfer(model: c.SimulationModel, process_id: c.EntityId, at_ms: c.Milliseconds) -> c.TransitionResult:
    """Create only the next eligible handoff, or preserve the existing active one."""
    process = model.processes[process_id]
    material = model.materials[process.material_id]
    if process.status not in ('QUEUED', 'BLOCKED') or not material.active or process.ready_at_ms > at_ms:
        raise c.ContractViolation('transport_process', process.id)
    if process.predecessor_id is not None and model.processes[process.predecessor_id].status != 'COMPLETED':
        raise c.ContractViolation('transport_predecessor', process.id)
    equipment = next(row for row in _layout().equipment if row.id == process.equipment_id)
    if any(row.material_id == material.id and row.status != 'ARRIVED' for row in model.transfers.values()) or material.location_id in (equipment.anchors.entry.location_id, equipment.anchors.buffer.location_id, equipment.anchors.work.location_id):
        return c.TransitionResult(model.clone(), c.TransitionDelta())
    path = resolve_path(material.location_id, c.EntityId(equipment.anchors.entry.location_id))
    transfer = _transfer(model, material.id, path).model_copy(update={'id': c.EntityId(f'TR-{process.id}-{path.id}'), 'process_id': process.id})
    return _create(model, transfer, at_ms)


def prepare_warehouse_transfer(model: c.SimulationModel, material_id: c.EntityId, at_ms: c.Milliseconds) -> c.TransitionResult:
    """Hand packaged material to the real warehouse roller path once."""
    if any(row.material_id == material_id and row.status != 'ARRIVED' for row in model.transfers.values()) or model.materials[material_id].location_id in ('OPS-WAREHOUSE-ENTRY', 'OPS-WAREHOUSE-BUFFER'):
        return c.TransitionResult(model.clone(), c.TransitionDelta())
    path = resolve_path(model.materials[material_id].location_id, c.EntityId('OPS-WAREHOUSE-ENTRY'))
    return _create(model, _transfer(model, material_id, path), at_ms)


def transport_transition(model: c.SimulationModel, transfer_id: c.EntityId, at_ms: c.Milliseconds) -> c.TransitionResult:
    """Atomically cross one due custody boundary, emitting centrally sequenced events."""
    transfer, owned = model.transfers[transfer_id], model.clone()
    path, material = _path(transfer), model.materials[transfer.material_id]
    _validate(model, transfer, at_ms)
    match transfer.status:
        case 'ARRIVED':
            raise c.ContractViolation('transport_arrived', transfer.id)
        case 'LOADING' | 'IN_TRANSIT' | 'UNLOADING':
            if transfer.phase_end_ms != at_ms:
                raise c.ContractViolation('transport_boundary', transfer.id)
            custodian = transfer.vehicle_id if transfer.status == 'IN_TRANSIT' else transfer.crane_id
            expected = path.custody_location_id or (model.resources[custodian].location_id if custodian is not None else None)
            if material.location_id != expected or any(model.resources[key].reserved_by != transfer.id for key in _resource_ids(path)):
                raise c.ContractViolation('transport_custody', transfer.id)
        case 'WAITING':
            if material.location_id != transfer.from_location_id:
                raise c.ContractViolation('transport_custody', transfer.id)
        case unreachable:
            assert_never(unreachable)
    crane = transfer.crane_id
    status: c.TransferStatus
    event_type: c.EventType
    duration: int | None
    match transfer.status, transfer.mode:
        case 'WAITING', 'roller':
            location = path.custody_location_id or path.to_location_id
            status, event_type, duration = 'IN_TRANSIT', 'TRANSFER_DEPARTED', transfer.travel_duration_ms
        case 'WAITING', ('flatbed' | 'hot_metal_car' | 'ladle_car'):
            crane = c.EntityId(path.pickup_crane_id or '')
            location = model.resources[crane].location_id
            status, event_type, duration = 'LOADING', 'TRANSFER_LOADING', 1000
        case 'LOADING', _:
            location = model.resources[c.EntityId(path.vehicle_id or '')].location_id
            status, event_type, duration = 'IN_TRANSIT', 'TRANSFER_DEPARTED', transfer.travel_duration_ms
        case 'IN_TRANSIT', 'roller':
            location = path.to_location_id
            status, event_type, duration = 'ARRIVED', 'TRANSFER_ARRIVED', None
        case 'IN_TRANSIT', ('flatbed' | 'hot_metal_car' | 'ladle_car'):
            crane = c.EntityId(path.drop_crane_id or '')
            location = model.resources[crane].location_id
            status, event_type, duration = 'UNLOADING', 'TRANSFER_UNLOADING', 1000
        case 'UNLOADING', _:
            location = path.to_location_id
            status, event_type, duration = 'ARRIVED', 'TRANSFER_ARRIVED', None
        case unreachable:
            assert_never(unreachable)
    for key in _resource_ids(path):
        owned.resources[key] = model.resources[key].model_copy(update={'reserved_by': None if status == 'ARRIVED' else transfer.id, 'available_at_ms': at_ms})
    owned.materials[material.id] = material.model_copy(update={'location_id': c.EntityId(location)})
    owned.transfers[transfer.id] = transfer.model_copy(update={'status': status, 'crane_id': crane, 'phase_start_ms': at_ms, 'phase_end_ms': c.Milliseconds(at_ms + duration) if duration is not None else None})
    if transfer.status == 'WAITING':
        emit_event(owned, EventDraft('TRANSFER_STARTED', 'transfer', transfer.id, at_ms, material_id=material.id, process_id=transfer.process_id, from_location_id=material.location_id, to_location_id=c.EntityId(location)))
    emit_event(owned, EventDraft(event_type, 'transfer', transfer.id, at_ms, material_id=material.id, process_id=transfer.process_id, from_location_id=material.location_id, to_location_id=c.EntityId(location)))
    return c.TransitionResult(owned, diff_models(model, owned))


def ready_transfers(model: c.SimulationModel) -> tuple[c.EntityId, ...]:
    ready = []
    for transfer in model.transfers.values():
        if transfer.status == 'ARRIVED' or (transfer.status != 'WAITING' and transfer.phase_end_ms != model.run.elapsed_ms):
            continue
        try:
            _validate(model, transfer, model.run.elapsed_ms)
        except c.ContractViolation:
            continue
        material = model.materials[transfer.material_id]
        order_id = model.work_orders[model.lots[material.lot_id].work_order_id].order_id
        process = model.processes.get(transfer.process_id) if transfer.process_id else None
        ready.append((transfer.status == 'WAITING', process.ready_at_ms if process else material_ready_at(model, material.id), order_id, material.id, process.step_ordinal if process else 0, transfer.id))
    selected: list[c.EntityId] = []
    claimed: set[c.EntityId] = set()
    for candidate in sorted(ready):
        transfer_id = candidate[-1]
        resources = set(_resource_ids(_path(model.transfers[transfer_id])))
        if resources.isdisjoint(claimed):
            selected.append(transfer_id)
            claimed.update(resources)
    return tuple(selected)


def next_boundary(model: c.SimulationModel) -> c.Milliseconds | None:
    boundaries = [row.phase_end_ms for row in model.transfers.values() if row.status in ('LOADING', 'IN_TRANSIT', 'UNLOADING') and row.phase_end_ms is not None]
    return min(boundaries, default=None)
