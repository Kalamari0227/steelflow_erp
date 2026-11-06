"""Pure completed-batch transition over physical versions and accounting IO."""
# noqa: SIZE_OK -- one sealed transition owns the inseparable mass/custody/allocation invariants.
from __future__ import annotations

from . import contracts_v3 as c
from .batch_contracts import BatchCompletion, edge_quantities, safe_total
from .bundle_registry import ServiceError
from .contracts_v3_core import ACTIVE_JOB_STATUSES, EntityId, Kilograms
from .motion_admission import validate_binding
from .motion_bindings import AssetBinding, FORM_FAMILIES
from .motion_types import MotionError
from .stock_contracts import TransitionPlan, event, identity, require, transition
from .world_contract import FactoryWorld
from .world_types import Port


def support_port(world: FactoryWorld, bindings: tuple[AssetBinding, ...], destination: str, form: str) -> Port:
    """Resolve the exact graph port and its admitted material support socket."""
    port = next((row for row in world.ports if row.id == destination), None)
    if port is None:
        raise ServiceError('not_found', 'batch support port not found: ' + destination, 404)
    binding = next((row for row in bindings if row.owner_id == port.owner_id), None)
    if binding is None:
        raise ServiceError('unsupported_bundle', 'exact batch asset binding missing: ' + port.owner_id, 422)
    try:
        validate_binding(binding, world)
    except MotionError as error:
        raise ServiceError('unsupported_bundle', str(error), 422) from error
    socket = next((row for row in binding.sockets if row.socket_id == port.socket_id), None)
    if socket is None or socket.family not in FORM_FAMILIES[form]:
        raise ServiceError('unsupported_bundle', 'batch support socket/family missing', 422)
    return port


def validate_edges(request: BatchCompletion, plan: TransitionPlan) -> None:
    """Require the exact new transport table without tightening old archives."""
    versions = {row.material_id: row.id for row in plan.delta.upserts.material_versions}
    expected = {(source, versions[target], kg) for source, target, kg in edge_quantities(request)}
    actual = {(row.input_version_id, row.output_version_id, row.transferred_kg) for row in plan.delta.upserts.version_edges}
    require(len(actual) == len(plan.delta.upserts.version_edges) and actual == expected, 'new batch edge set differs from deterministic accounting')


def plan_completed_batch(state: c.FactorySnapshot, request: BatchCompletion, world: FactoryWorld, asset_bindings: tuple[AssetBinding, ...]) -> TransitionPlan:
    """Consume whole current units and create new PENDING/WIP physical outputs."""
    require(bool(request.inputs) and bool(request.outputs), 'batch requires inputs and outputs')
    require(0 <= request.start_ms < request.end_ms == state.run.elapsed_ms <= state.run.duration_ms, 'batch interval differs from current terminal observation')
    require(len({row.owner_id for row in asset_bindings}) == len(asset_bindings), 'duplicate asset binding owner')
    physical = (*request.inputs, *request.stock_additions)
    require(len({row.material_version_id for row in physical}) == len(physical), 'duplicate physical input roles')
    require(len({row.material_id for row in request.outputs}) == len(request.outputs), 'duplicate output material')
    source_rows = (*request.external_additions, *request.byproducts, *request.losses)
    require(len({row.source_id for row in source_rows}) == len(source_rows), 'duplicate accounting source')
    used_sources = {row.source_id for row in state.receipts} | {row.source_id for row in state.mass_ledger} | {row.source_id for row in state.batch_io if row.source_id is not None}
    require(all(row.source_id not in used_sources for row in source_rows), 'accounting source already used')
    edge_cells = edge_quantities(request)
    versions = {row.id: row for row in state.material_versions}
    materials = {row.id: row for row in state.materials}
    physical_ids = set(versions) | set(materials)
    require(all(row.material_id not in physical_ids for row in request.outputs), 'output physical identity already exists')
    process = None
    if request.process_id is not None:
        process = next((row for row in state.processes if row.id == request.process_id), None)
        if process is None:
            raise ServiceError('not_found', 'batch process not found', 404)
        require(process.status == 'COMPLETED' and (process.route_step_id, process.start_ms, process.end_ms) == (request.recipe_id, request.start_ms, request.end_ms), 'batch process completion/window/recipe mismatch')
        require(any(row.event_type == 'PROCESS_COMPLETED' and row.entity_type == 'process' and row.entity_id == process.id and row.payload.process_id == process.id and row.at_ms == request.end_ms for row in state.events), 'actual process completion event missing')
    parents: list[c.Material] = []
    released: list[c.Attachment] = []
    parent_allocations: list[c.MaterialAllocation] = []
    for row in physical:
        version = versions.get(row.material_version_id)
        if version is None:
            raise ServiceError('not_found', 'input material version not found', 404)
        material = materials[version.material_id]
        require(material.active and material.current_version_id == version.id and material.weight_kg == row.quantity_kg, 'input is not a whole current active version')
        require(not any(io.material_version_id == version.id and io.role in ('INPUT', 'STOCK_ADDITION') for io in state.batch_io), 'input version already consumed')
        allowed = ('AVAILABLE', 'RESERVED') if process is None else ('WIP', 'AVAILABLE', 'RESERVED')
        qualities = ('PASSED',) if process is None else ('PENDING', 'PASSED')
        require(material.availability_status in allowed and material.quality_status in qualities, 'input quality or availability is ineligible')
        quality = sorted((q for q in state.quality if q.material_id == material.id and q.material_version_id == version.id), key=lambda q: (q.at_ms, q.id))
        require(process is not None or (bool(quality) and quality[-1].status == 'PASSED'), 'stock input lacks current passed quality')
        require(not quality or quality[-1].status in qualities, 'current quality observation prevents consumption')
        require(not any(job.material_id == material.id and job.status in ACTIVE_JOB_STATUSES for job in state.transport_jobs), 'input has active transport job')
        require(not any(link.material_id == material.id and link.active for link in state.shipment_materials), 'input has active shipment link')
        custody = tuple(item for item in state.attachments if item.material_id == material.id and item.released_at_ms is None)
        require(len(custody) == 1 and custody[0].kind == 'slot' and custody[0].acquired_at_ms <= request.start_ms, 'input requires one observed current port custody before start')
        port = support_port(world, asset_bindings, custody[0].owner_id, material.form)
        require(custody[0].socket_id == port.socket_id, 'input custody socket differs from exact port')
        allocations = tuple(item for item in state.allocations if item.material_id == material.id and item.active)
        if process is not None:
            require(port.owner_id == process.equipment_id, 'input is outside completed process equipment')
            if row in request.inputs and process.work_order_id is not None:
                require(len(allocations) == 1 and allocations[0].work_order_id == process.work_order_id, 'process input work allocation mismatch')
        parents.append(material)
        released.append(custody[0].model_copy(update={'released_at_ms': request.end_ms}))
        parent_allocations.extend(allocations)
    require(len({row.id for row in parents}) == len(parents), 'physical material consumed twice')
    output_ports = {row.material_id: support_port(world, asset_bindings, row.destination_id, row.form) for row in request.outputs}
    parent_ids = {row.id for row in parents}
    for port_id in {port.id for port in output_ports.values()}:
        port = next(port for port in output_ports.values() if port.id == port_id)
        occupants = {a.material_id for a in state.attachments if a.released_at_ms is None and a.kind == 'slot' and a.owner_id == port_id}
        post_kg = safe_total([m.weight_kg for m in state.materials if m.active and m.id in occupants - parent_ids] + [row.quantity_kg for row in request.outputs if row.destination_id == port_id])
        require(post_kg <= port.capacity_kg, 'post-batch support capacity exceeded')
    works = {row.id: row for row in state.work_orders}
    orders = {row.id: row for row in state.orders}
    output_work_ids = {row.work_order_id for row in request.outputs if row.work_order_id is not None}
    require(all(row.work_order_id in output_work_ids for row in parent_allocations), 'consumed allocated work must continue on an output')
    for work_id in output_work_ids:
        work = works.get(work_id)
        if work is None:
            raise ServiceError('not_found', 'output work order not found', 404)
        order = orders[work.order_id]
        assigned = tuple(row for row in request.outputs if row.work_order_id == work_id)
        require(work.status == 'RELEASED' and all(row.grade == order.grade for row in assigned), 'output work status/grade mismatch')
        allocation_kg = safe_total([row.quantity_kg for row in state.allocations if row.active and row.material_id not in parent_ids and row.work_order_id == work_id] + [row.quantity_kg for row in assigned])
        require(allocation_kg <= work.planned_kg, 'output exceeds work planned kg')
        require(safe_total(row.planned_kg for row in state.work_orders if row.order_id == order.id and row.status in ('RELEASED', 'COMPLETED')) <= order.quantity_kg, 'work plans exceed order quantity')
    source = 'completed-batch:' + request.command_id
    batch_id = identity(source, 'batch')
    common = {'run_id': state.run.id}
    output_rows = sorted(request.outputs, key=lambda row: row.material_id)
    all_material_ids = tuple(sorted((*parent_ids, *(row.material_id for row in output_rows))))
    context = c.EventContext(material_ids=all_material_ids, batch_id=batch_id, process_id=request.process_id)
    events: list[c.FactoryEvent] = []
    for attachment in sorted(released, key=lambda row: row.id):
        payload = context.model_copy(update={'from_attachment_id': attachment.id, 'from_owner_id': attachment.owner_id})
        events.append(event(state, source, len(events) + 1, 'ATTACHMENT_RELEASED', 'attachment', attachment.id, payload))
    completed = event(state, source, len(events) + 1, 'BATCH_COMPLETED', 'batch', batch_id, context)
    events.append(completed)
    transform_kind = 'MATERIAL_MERGED' if len(parents) >= 2 else 'MATERIAL_SPLIT' if len(output_rows) > 1 else 'MATERIAL_TRANSFORMED'
    transformed = event(state, source, len(events) + 1, transform_kind, 'batch', batch_id, context)
    events.append(transformed)
    output_materials: list[c.Material] = []
    output_versions: list[c.MaterialVersion] = []
    attachments: list[c.Attachment] = sorted(released, key=lambda row: row.id)
    allocations = [row.model_copy(update={'active': False}) for row in sorted(parent_allocations, key=lambda row: row.id)]
    for output in output_rows:
        version_id = identity(source, 'version:' + output.material_id)
        attachment_id = identity(source, 'attachment:' + output.material_id)
        port = output_ports[output.material_id]
        output_materials.append(c.Material(**common, id=output.material_id, grade=output.grade, form=output.form, dimensions=output.dimensions, weight_kg=output.quantity_kg, current_version_id=version_id, origin_stock_lot_id=None, production_lot_id=None, quality_status='PENDING', availability_status='WIP', active=True))
        output_versions.append(c.MaterialVersion(**common, id=version_id, material_id=output.material_id, ordinal=1, grade=output.grade, form=output.form, dimensions=output.dimensions, weight_kg=output.quantity_kg, cause_event_id=transformed.id))
        attachments.append(c.Attachment(**common, id=attachment_id, material_id=output.material_id, kind='slot', owner_id=EntityId(port.id), socket_id=EntityId(port.socket_id), acquired_at_ms=request.end_ms, released_at_ms=None))
        events.append(event(state, source, len(events) + 1, 'ATTACHMENT_ACQUIRED', 'attachment', attachment_id, context.model_copy(update={'material_ids': (output.material_id,), 'to_attachment_id': attachment_id, 'to_owner_id': EntityId(port.id)})))
        if output.work_order_id is not None:
            work = works[output.work_order_id]
            allocations.append(c.MaterialAllocation(**common, id=identity(source, 'allocation:' + output.material_id), material_id=output.material_id, order_id=work.order_id, work_order_id=work.id, quantity_kg=output.quantity_kg, active=True))
    for output in output_rows:
        if output.work_order_id is not None:
            work = works[output.work_order_id]
            events.append(event(state, source, len(events) + 1, 'MATERIAL_ALLOCATED', 'material', output.material_id, context.model_copy(update={'material_ids': (output.material_id,), 'order_id': work.order_id, 'work_order_id': work.id})))
    io: list[c.BatchIO] = []
    ledger: list[c.MassLedgerEntry] = []
    for role, physical_rows in (('INPUT', request.inputs), ('STOCK_ADDITION', request.stock_additions)):
        for row in sorted(physical_rows, key=lambda row: row.material_version_id):
            io.append(c.BatchIO(**common, id=identity(source, role + ':' + row.material_version_id), batch_id=batch_id, role=role, material_version_id=row.material_version_id, quantity_kg=row.quantity_kg, source_id=None))
    for row in output_materials:
        io.append(c.BatchIO(**common, id=identity(source, 'OUTPUT:' + row.id), batch_id=batch_id, role='OUTPUT', material_version_id=row.current_version_id, quantity_kg=row.weight_kg, source_id=None))
    for role, kind, accounting_rows in (('EXTERNAL_ADDITION', 'EXTERNAL_ADDITION', request.external_additions), ('BYPRODUCT', 'BYPRODUCT', request.byproducts), ('LOSS', 'IRRECOVERABLE_LOSS', request.losses)):
        for row in sorted(accounting_rows, key=lambda row: row.source_id):
            io.append(c.BatchIO(**common, id=identity(source, role + ':' + row.source_id), batch_id=batch_id, role=role, material_version_id=None, quantity_kg=row.quantity_kg, source_id=row.source_id))
            ledger.append(c.MassLedgerEntry(**common, id=identity(source, 'ledger:' + row.source_id), source_id=row.source_id, kind=kind, quantity_kg=row.quantity_kg, at_ms=request.end_ms, material_id=None, batch_id=batch_id, event_id=completed.id))
    version_ids = {row.material_id: row.id for row in output_versions}
    edges = tuple(c.VersionEdge(**common, id=identity(source, 'edge:' + str(index)), batch_id=batch_id, input_version_id=parent, output_version_id=version_ids[child], transferred_kg=Kilograms(kg)) for index, (parent, child, kg) in enumerate(edge_cells))
    consumed = tuple(row.model_copy(update={'active': False, 'availability_status': 'CONSUMED'}) for row in sorted(parents, key=lambda row: row.id))
    upserts = c.FactoryCollections(materials=(*consumed, *output_materials), material_versions=tuple(output_versions), version_edges=edges, allocations=tuple(allocations), attachments=tuple(attachments), process_batches=(c.ProcessBatch(**common, id=batch_id, process_id=request.process_id, recipe_id=request.recipe_id, status='COMPLETED', start_ms=request.start_ms, end_ms=request.end_ms),), batch_io=tuple(io), mass_ledger=tuple(ledger), events=tuple(events))
    plan = transition(state, upserts)
    validate_edges(request, plan)
    safe_total(row.quantity_kg for row in plan.state.mass_ledger if row.kind in ('OPENING_STOCK', 'EXTERNAL_RECEIPT', 'EXTERNAL_ADDITION'))
    safe_total(row.quantity_kg for row in plan.state.mass_ledger if row.kind in ('BYPRODUCT', 'IRRECOVERABLE_LOSS'))
    safe_total(row.weight_kg for row in plan.state.materials if row.active)
    return plan
