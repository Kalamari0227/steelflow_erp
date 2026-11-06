"""Deterministic boundary scheduler; transport and fulfillment are injected seams."""
from dataclasses import dataclass

from app.operations import contracts as c
from app.operations.catalog import load_catalog
from app.operations.events import EventDraft, diff_models, emit_event
from app.operations.layout import load_factory_layout
from app.operations.fixtures import shipment_memberships
from app.operations.lineage import mass_balance, transform_material


def unchanged(model: c.SimulationModel, entity_id: c.EntityId, at_ms: c.Milliseconds) -> c.TransitionResult:
    return c.TransitionResult(model.clone(), c.TransitionDelta())


def none_ready(model: c.SimulationModel) -> tuple[c.EntityId, ...]:
    return ()


def no_boundary(model: c.SimulationModel) -> c.Milliseconds | None:
    return None


@dataclass(frozen=True, slots=True)
class EngineCallbacks:
    prepare_process_transfer: c.TransportTransition = unchanged
    transport_transition: c.TransportTransition = unchanged
    ready_transfers: c.ReadyTransfers = none_ready
    next_transport_boundary: c.NextBoundary = no_boundary
    fulfillment_transition: c.FulfillmentTransition = unchanged
    ready_fulfillment: c.ReadyTransfers = none_ready
    next_fulfillment_boundary: c.NextBoundary = no_boundary


def order_for(model: c.SimulationModel, material_id: c.EntityId) -> c.OperationsOrder:
    material = model.materials[material_id]
    return model.orders[model.work_orders[model.lots[material.lot_id].work_order_id].order_id]


def queue_key(model: c.SimulationModel, process: c.ProcessExecution) -> tuple[int, str, str, int]:
    return process.ready_at_ms, order_for(model, process.material_id).id, process.material_id, process.step_ordinal


def material_ready_at(model: c.SimulationModel, material_id: c.EntityId) -> int:
    """Use persisted physical readiness; only untouched source inventory starts at zero."""
    material = model.materials[material_id]
    packaged = [row.packaging_end_ms for row in model.inspections.values()
                if row.material_id == material_id and row.inspected_version_id == material.current_version_id and row.packaging_end_ms is not None]
    if packaged:
        return max(packaged)
    return max((row.at_ms for row in model.events.values()
                if row.material_id == material_id or (row.entity_type == 'material' and row.entity_id == material_id)), default=0)


def transition_key(model: c.SimulationModel, entity_id: c.EntityId) -> tuple[int, int, str, str, int, str]:
    """Finish due phases and resource-free prerequisites, then compare actual ready work.

    Shipment allocation and stock receipt reveal waiting work without acquiring a
    carrier. A loaded dispatch continues ownership already acquired by loading.
    Only phase completion/settlement precedes the shared waiting queue.
    """
    if entity_id in model.transfers:
        row = model.transfers[entity_id]
        process = model.processes.get(row.process_id) if row.process_id else None
        key = queue_key(model, process) if process else (material_ready_at(model, row.material_id), order_for(model, row.material_id).id, row.material_id, 0)
        return int(row.status == 'WAITING'), *key, entity_id
    if entity_id in model.processes:
        process = model.processes[entity_id]
        return int(process.status != 'RUNNING'), *queue_key(model, process), entity_id
    if entity_id in model.materials:
        return 0, material_ready_at(model, entity_id), order_for(model, entity_id).id, entity_id, 0, entity_id
    shipment = model.shipments[entity_id]
    members = tuple(row.material_id for row in model.shipment_materials.values() if row.shipment_id == entity_id and row.active)
    if not members:
        members = tuple(row.material_id for row in shipment_memberships(model.orders[shipment.order_id].product_id) if row.shipment_id == entity_id)
    ready_at = shipment.phase_start_ms
    if ready_at is None:
        ready_at = max(material_ready_at(model, key) for key in members)
    waiting = shipment.status == 'ALLOCATED' or (shipment.status == 'AT_PORT' and shipment.phase_end_ms is None)
    return int(waiting), ready_at, shipment.order_id, min(members), 0, entity_id


def fits(model: c.SimulationModel, process: c.ProcessExecution, resource: c.ResourceSpec) -> bool:
    material, order = model.materials[process.material_id], order_for(model, process.material_id)
    return (material.weight_kg <= resource.capacity_kg and material.form in resource.compatible_forms
            and (not resource.compatible_grades or order.grade in resource.compatible_grades)
            and (order.width_mm is None or ((resource.min_width_mm is None or order.width_mm >= resource.min_width_mm)
                                           and (resource.max_width_mm is None or order.width_mm <= resource.max_width_mm))))


def ready_processes(model: c.SimulationModel) -> tuple[c.ProcessExecution, ...]:
    return tuple(sorted((row for row in model.processes.values()
                         if row.status in ('QUEUED', 'BLOCKED') and model.materials[row.material_id].active
                         and row.ready_at_ms <= model.run.elapsed_ms
                         and (row.predecessor_id is None or model.processes[row.predecessor_id].status == 'COMPLETED')),
                        key=lambda row: queue_key(model, row)))


def release_plan(model: c.SimulationModel) -> None:
    if model.run.event_sequence:
        return
    emit_event(model, EventDraft('PLAN_RELEASED', 'run', c.EntityId(model.run.id), c.Milliseconds(0)))
    for row in sorted(model.work_orders.values(), key=lambda row: (row.order_id, row.id)):
        model.work_orders[row.id] = row.model_copy(update={'status': 'RELEASED'})
        emit_event(model, EventDraft('WORK_ORDER_RELEASED', 'work_order', row.id, c.Milliseconds(0), order_id=row.order_id))
    for row in sorted(model.allocations.values(), key=lambda row: (row.order_id, row.material_id)):
        model.allocations[row.id] = row.model_copy(update={'active': True})
        emit_event(model, EventDraft('MATERIAL_ALLOCATED', 'material', row.material_id, c.Milliseconds(0), material_id=row.material_id, order_id=row.order_id))


def scenario_resource(model: c.SimulationModel, process: c.ProcessExecution) -> c.ProcessExecution:
    """Apply the fixed incident once at the first otherwise executable GA finishing slot."""
    at = model.run.elapsed_ms
    primary = model.resources.get(c.EntityId('HSM-A'))
    if primary is None or process.equipment_id != primary.id or model.run.scenario_id == 'NORMAL':
        return process
    active = [row for row in model.processes.values() if row.status == 'RUNNING' and row.equipment_id == primary.id]
    arrived = model.materials[process.material_id].location_id == 'OPS-HSM-A-ENTRY'
    if (arrived and process.material_id == 'MAT-ga-01' and primary.unavailable_from_ms is None
            and not active and primary.available_at_ms <= at and fits(model, process, primary)):
        primary = primary.model_copy(update={'unavailable_from_ms': at, 'unavailable_until_ms': c.Milliseconds(at + 12000)})
        model.resources[primary.id] = primary
        emit_event(model, EventDraft('RESOURCE_DOWN', 'resource', primary.id, at, reason='finishing_mill_outage'))
    start, end = primary.unavailable_from_ms, primary.unavailable_until_ms
    if not arrived or model.run.scenario_id != 'RECOVERY' or start is None or end is None or not start + 1000 <= at < end:
        return process
    reserve = model.resources[c.EntityId('HSM-B')]
    busy = any(row.status == 'RUNNING' and row.equipment_id == reserve.id for row in model.processes.values())
    unavailable = reserve.unavailable_from_ms is not None and reserve.unavailable_from_ms <= at and (reserve.unavailable_until_ms is None or at < reserve.unavailable_until_ms)
    if busy or unavailable or reserve.available_at_ms > at or reserve.reserved_by not in (None, process.id) or not fits(model, process, reserve):
        return process
    routed = process.model_copy(update={'equipment_id': reserve.id, 'status': 'QUEUED', 'blocked_reason': None})
    model.processes[routed.id] = routed
    model.resources[reserve.id] = reserve.model_copy(update={'reserved_by': process.id})
    emit_event(model, EventDraft('RECOVERY_ROUTED', 'process', process.id, at, material_id=process.material_id, process_id=process.id, reason='HSM-B'))
    return routed


def advance_model(model: c.SimulationModel, target_ms: c.Milliseconds, callbacks: EngineCallbacks = EngineCallbacks()) -> c.TransitionResult:
    """Advance every crossed boundary on a clone; revision belongs to the command service."""
    if target_ms < model.run.elapsed_ms:
        raise c.ContractViolation('clock_rewind', str(target_ms))
    target = c.Milliseconds(min(target_ms, model.run.duration_ms))
    current = model.clone()
    if target == model.run.elapsed_ms:
        return c.TransitionResult(current, c.TransitionDelta())
    layout = load_factory_layout()
    stations = {row.id: row for row in layout.equipment}
    roles = {step.key: step.role for route in load_catalog().routes for step in route.steps}
    release_plan(current)
    while True:
        at = current.run.elapsed_ms
        before_pass = current.clone()
        for resource in tuple(current.resources.values()):
            if resource.unavailable_until_ms == at and not any(event.event_type == 'RESOURCE_RESTORED' and event.entity_id == resource.id for event in current.events.values()):
                emit_event(current, EventDraft('RESOURCE_RESTORED', 'resource', resource.id, at))
        completed = sorted((row for row in current.processes.values() if row.status == 'RUNNING' and row.end_ms == at
                            and roles[row.route_step_id] in ('manufacturing', 'intermediate_inspection')), key=lambda row: queue_key(current, row))
        for process in completed:
            current.processes[process.id] = process.model_copy(update={'status': 'COMPLETED'})
            material = current.materials[process.material_id]
            current.materials[material.id] = material.model_copy(update={'location_id': c.EntityId(stations[process.equipment_id].anchors.exit.location_id)})
            emit_event(current, EventDraft('PROCESS_COMPLETED', 'process', process.id, at, material_id=material.id, process_id=process.id))
            transform_material(current, process, at)
            resource = current.resources[process.equipment_id]
            current.resources[resource.id] = resource.model_copy(update={'reserved_by': None, 'available_at_ms': at})
            for successor in tuple(current.processes.values()):
                if successor.predecessor_id == process.id:
                    current.processes[successor.id] = successor.model_copy(update={'ready_at_ms': at})
        for candidate in ready_processes(current):
            current = callbacks.prepare_process_transfer(current, candidate.id, at).model
            process = scenario_resource(current, current.processes[candidate.id])
            if process.equipment_id != candidate.equipment_id:
                current = callbacks.prepare_process_transfer(current, process.id, at).model
        candidates = [(transition_key(current, key), True, key) for key in callbacks.ready_transfers(current)]
        candidates += [(transition_key(current, key), False, key) for key in callbacks.ready_fulfillment(current)]
        if candidates:
            _, transporting, key = min(candidates)
            transition = callbacks.transport_transition if transporting else callbacks.fulfillment_transition
            current = transition(current, key, at).model
            if current != before_pass:
                continue
        for process in ready_processes(current):
            if roles[process.route_step_id] not in ('manufacturing', 'intermediate_inspection'):
                continue
            process = current.processes[process.id]
            resource, material = current.resources[process.equipment_id], current.materials[process.material_id]
            active = sum(row.status == 'RUNNING' and row.equipment_id == resource.id for row in current.processes.values())
            outage = resource.unavailable_from_ms is not None and resource.unavailable_from_ms <= at and (resource.unavailable_until_ms is None or at < resource.unavailable_until_ms)
            moving = any(row.material_id == material.id and row.status != 'ARRIVED' for row in current.transfers.values())
            station = stations[process.equipment_id]
            arrived = material.location_id in (station.anchors.entry.location_id, station.anchors.buffer.location_id, station.anchors.work.location_id)
            reason = ('resource_incompatible' if not fits(current, process, resource) else 'resource_unavailable' if outage
                      else 'resource_busy' if active >= resource.parallel_capacity or resource.available_at_ms > at or resource.reserved_by not in (None, process.id)
                      else 'awaiting_arrival' if moving or not arrived else None)
            if reason:
                if process.blocked_reason != reason:
                    current.processes[process.id] = process.model_copy(update={'status': 'BLOCKED', 'blocked_reason': reason})
                    emit_event(current, EventDraft('PROCESS_BLOCKED', 'process', process.id, at, material_id=material.id, process_id=process.id, reason=reason))
                continue
            current.processes[process.id] = process.model_copy(update={'status': 'RUNNING', 'blocked_reason': None, 'start_ms': at, 'end_ms': c.Milliseconds(at + process.planned_duration_ms)})
            current.materials[material.id] = material.model_copy(update={'location_id': c.EntityId(station.anchors.work.location_id)})
            current.resources[resource.id] = resource.model_copy(update={'reserved_by': process.id})
            emit_event(current, EventDraft('PROCESS_STARTED', 'process', process.id, at, material_id=material.id, process_id=process.id, order_id=order_for(current, material.id).id))
        mass_balance(current)
        if current != before_pass:
            continue
        boundaries = [target]
        boundaries.extend(row.end_ms for row in current.processes.values() if row.status == 'RUNNING' and row.end_ms is not None and row.end_ms > at)
        boundaries.extend(row.ready_at_ms for row in current.processes.values() if row.status in ('QUEUED', 'BLOCKED') and row.ready_at_ms > at)
        for resource in current.resources.values():
            boundaries.extend(value for value in (resource.available_at_ms, resource.unavailable_until_ms, resource.unavailable_from_ms) if value is not None and value > at)
            if current.run.scenario_id == 'RECOVERY' and resource.id == 'HSM-A' and resource.unavailable_from_ms is not None and resource.unavailable_from_ms + 1000 > at:
                boundaries.append(resource.unavailable_from_ms + 1000)
        boundaries.extend(value for value in (callbacks.next_transport_boundary(current), callbacks.next_fulfillment_boundary(current)) if value is not None and value > at)
        if at == target:
            break
        current.run = current.run.model_copy(update={'elapsed_ms': c.Milliseconds(min(boundaries))})
    return c.TransitionResult(current, diff_models(model, current))
