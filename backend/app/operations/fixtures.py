"""Pure received-order plans with future shipment membership kept outside inventory."""
from app.operations.catalog import load_catalog, route
from app.operations.contracts import (
    Contract, ContractViolation, EntityId, Id, Kilograms, Material, MaterialAllocation,
    MaterialVersion, OperationsLot, OperationsShipment, OrderPlan, PlanSeed, PositiveKg,
    ProcessExecution, ProductId, RunId, WorkOrder,
)
from app.operations.resources import GRADES, MasterSeed, build_masters, build_resources


class ShipmentMembership(Contract):
    order_id: Id
    shipment_id: Id
    material_id: Id
    final_planned_kg: PositiveKg


def shipment_memberships(product_id: ProductId) -> tuple[ShipmentMembership, ...]:
    """Plan whole final units, including future children; never allocate current stock."""
    recipe = route(product_id)
    final_kg = recipe.initial_kg + sum(step.additions_kg - step.loss_kg for step in recipe.steps)
    result = []
    for unit in range(1, 4 if product_id == 'ga' else 2):
        shipment = 2 if unit == 3 else 1
        suffixes = (':A', ':B') if recipe.split_step_id else ('',)
        for suffix in suffixes:
            result.append(ShipmentMembership(order_id=EntityId(f'ORD-{product_id}'), shipment_id=EntityId(f'SHIP-{product_id}-{shipment:02}'), material_id=EntityId(f'MAT-{product_id}-{unit:02}{suffix}'), final_planned_kg=Kilograms(final_kg // len(suffixes))))
    return tuple(result)


def build_fixture(seed: int = 30) -> PlanSeed:
    """Create an unpersisted deterministic plan; T10 supplies new run IDs and due dates."""
    run_id = RunId(f'OPS-RUN-erp-v1-{seed}')
    orders, works, lots, materials, versions, allocations, processes, shipments = [], [], [], [], [], [], [], []
    for recipe in load_catalog().routes:
        product = recipe.product_id
        memberships = shipment_memberships(product)
        family = 'titanium' if product.startswith('ti-') else 'stainless' if product.startswith('sts-') else 'carbon'
        flat = product not in ('slab', 'bloom', 'billet', 'wire')
        order_id = EntityId(f'ORD-{product}')
        orders.append(OrderPlan(run_id=run_id, id=order_id, customer_id=EntityId(f'OPS-CUSTOMER-{family.upper()}'), product_id=product, grade=GRADES[family], width_mm=1200.0 if flat else None, thickness_mm=2.0 if flat else None, quantity_kg=Kilograms(sum(row.final_planned_kg for row in memberships))))
        final_kg = recipe.initial_kg + sum(step.additions_kg - step.loss_kg for step in recipe.steps)
        for group in range(1, 3 if product == 'ga' else 2):
            units = (1, 2) if product == 'ga' and group == 1 else (3,) if product == 'ga' else (1,)
            work_id, lot_id = EntityId(f'WO-{product}-{group:02}'), EntityId(f'LOT-{product}-{group:02}')
            planned_kg = Kilograms(final_kg * len(units))
            works.append(WorkOrder(run_id=run_id, id=work_id, order_id=order_id, route_id=EntityId(recipe.id), route_version=1, planned_kg=planned_kg))
            lots.append(OperationsLot(run_id=run_id, id=lot_id, work_order_id=work_id, planned_kg=planned_kg))
            for unit in units:
                material_id = EntityId(f'MAT-{product}-{unit:02}')
                version_id = EntityId(f'{material_id}:V01')
                materials.append(Material(run_id=run_id, id=material_id, lot_id=lot_id, lineage_id=material_id, current_version_id=version_id, form=recipe.input_form, weight_kg=Kilograms(recipe.initial_kg), location_id=EntityId(recipe.source_location_id), quality_status='PENDING', availability_status='WIP', active=True))
                versions.append(MaterialVersion(run_id=run_id, id=version_id, material_id=material_id, ordinal=1, parent_version_id=None, form=recipe.input_form, weight_kg=Kilograms(recipe.initial_kg), cause_event_id=None))
                allocations.append(MaterialAllocation(run_id=run_id, id=EntityId(f'ALLOC-{material_id}'), order_id=order_id, work_order_id=work_id, material_id=material_id, final_planned_kg=Kilograms(final_kg), active=False))
                predecessor = None
                for step in recipe.steps:
                    process_id = EntityId(f'PROC-{material_id}-{step.key}')
                    processes.append(ProcessExecution(run_id=run_id, id=process_id, material_id=material_id, route_step_id=EntityId(step.key), source_step_id=EntityId(step.source_step_id), step_ordinal=step.ordinal, equipment_id=EntityId(step.equipment_id), predecessor_id=predecessor, status='QUEUED', planned_duration_ms=step.duration_ms, input_form=step.input_form, output_form=step.output_form, additions_kg=Kilograms(step.additions_kg), loss_kg=Kilograms(step.loss_kg), split_count=step.split_count))
                    predecessor = process_id
            shipment_id = EntityId(f'SHIP-{product}-{group:02}')
            shipments.append(OperationsShipment(run_id=run_id, id=shipment_id, order_id=order_id, status='PLANNED', location_id=EntityId(recipe.dispatch_location_id), capacity_kg=Kilograms(100000)))
    plan = PlanSeed(seed=seed, run_id=run_id, orders=tuple(orders), work_orders=tuple(works), lots=tuple(lots), materials=tuple(materials), material_versions=tuple(versions), allocations=tuple(allocations), processes=tuple(processes), shipments=tuple(shipments), resources=build_resources())
    return validate_fixture(plan)


def validate_fixture(plan: PlanSeed, masters: MasterSeed | None = None) -> PlanSeed:
    """Check initial plan relations before it enters a scheduler or persistence layer."""
    plan = PlanSeed.model_validate(plan.model_dump())
    master = build_masters() if masters is None else MasterSeed.model_validate(masters.model_dump())
    customers, locations = {row.id for row in master.customers}, {row.id for row in master.locations}
    recipes = {row.product_id: row for row in load_catalog().routes}
    orders, works = {row.id: row for row in plan.orders}, {row.id: row for row in plan.work_orders}
    lots, materials = {row.id: row for row in plan.lots}, {row.id: row for row in plan.materials}
    versions, processes = {row.id: row for row in plan.material_versions}, {row.id: row for row in plan.processes}
    resources = {row.id: row for row in plan.resources}
    if len(resources) != len(plan.resources):
        raise ContractViolation('duplicate_resource', 'resource IDs must be unique')
    if any(row.customer_id not in customers for row in plan.orders) or any(row.location_id not in locations for row in (*plan.materials, *plan.shipments, *plan.resources)):
        raise ContractViolation('master_reference', 'missing customer or location')
    if set(row.product_id for row in plan.orders) != set(recipes) or len(plan.orders) != 20:
        raise ContractViolation('product_coverage', 'exactly twenty product orders are required')
    for work in plan.work_orders:
        if work.order_id not in orders:
            raise ContractViolation('work_order_relation', work.id)
        recipe = recipes[orders[work.order_id].product_id]
        if (work.route_id, work.route_version) != (recipe.id, 1):
            raise ContractViolation('work_route', work.id)
    for lot in plan.lots:
        if lot.work_order_id not in works or lot.planned_kg != works[lot.work_order_id].planned_kg:
            raise ContractViolation('lot_relation', lot.id)
    for material in plan.materials:
        if material.lot_id not in lots or material.current_version_id not in versions:
            raise ContractViolation('material_relation', material.id)
        version = versions[material.current_version_id]
        if (version.material_id, version.form, version.weight_kg) != (material.id, material.form, material.weight_kg):
            raise ContractViolation('current_version', material.id)
        recipe = recipes[orders[works[lots[material.lot_id].work_order_id].order_id].product_id]
        if (material.form, material.weight_kg, material.location_id) != (recipe.input_form, recipe.initial_kg, recipe.source_location_id):
            raise ContractViolation('initial_material', material.id)
    if len(plan.material_versions) != len(materials) or any(row.material_id not in materials or row.ordinal != 1 or row.parent_version_id is not None or row.cause_event_id is not None for row in plan.material_versions):
        raise ContractViolation('initial_version', 'only initial physical versions are allowed')
    assigned: set[EntityId] = set()
    for allocation in plan.allocations:
        if allocation.material_id not in materials or allocation.work_order_id not in works or allocation.order_id not in orders:
            raise ContractViolation('allocation_relation', allocation.id)
        work = works[allocation.work_order_id]
        if work.order_id != allocation.order_id or lots[materials[allocation.material_id].lot_id].work_order_id != work.id:
            raise ContractViolation('allocation_relation', allocation.id)
        recipe = recipes[orders[allocation.order_id].product_id]
        final_kg = recipe.initial_kg + sum(step.additions_kg - step.loss_kg for step in recipe.steps)
        if allocation.final_planned_kg != final_kg or allocation.material_id in assigned:
            raise ContractViolation('allocation_quantity', allocation.id)
        assigned.add(allocation.material_id)
    if assigned != set(materials):
        raise ContractViolation('allocation_coverage', 'every initial material needs one plan allocation')
    for order in plan.orders:
        if sum(row.final_planned_kg for row in plan.allocations if row.order_id == order.id) != order.quantity_kg:
            raise ContractViolation('order_quantity', order.id)
    for work in plan.work_orders:
        if sum(row.final_planned_kg for row in plan.allocations if row.work_order_id == work.id) != work.planned_kg:
            raise ContractViolation('work_quantity', work.id)
    for process in plan.processes:
        if process.material_id not in materials or process.equipment_id not in resources:
            raise ContractViolation('process_relation', process.id)
        work = works[lots[materials[process.material_id].lot_id].work_order_id]
        steps = recipes[orders[work.order_id].product_id].steps
        if process.step_ordinal >= len(steps):
            raise ContractViolation('process_route', process.id)
        step = steps[process.step_ordinal]
        expected = (step.key, step.source_step_id, step.equipment_id, step.duration_ms, step.input_form, step.output_form, step.additions_kg, step.loss_kg, step.split_count)
        actual = (process.route_step_id, process.source_step_id, process.equipment_id, process.planned_duration_ms, process.input_form, process.output_form, process.additions_kg, process.loss_kg, process.split_count)
        predecessor = processes.get(process.predecessor_id) if process.predecessor_id else None
        if actual != expected or (process.step_ordinal == 0) != (predecessor is None) or (predecessor and (predecessor.material_id != process.material_id or predecessor.step_ordinal + 1 != process.step_ordinal)):
            raise ContractViolation('process_route', process.id)
    for material in plan.materials:
        work = works[lots[material.lot_id].work_order_id]
        expected_count = len(recipes[orders[work.order_id].product_id].steps)
        if sorted(row.step_ordinal for row in plan.processes if row.material_id == material.id) != list(range(expected_count)):
            raise ContractViolation('process_coverage', material.id)
    planned_shipments = {member.shipment_id: member.order_id for order in plan.orders for member in shipment_memberships(order.product_id)}
    for shipment in plan.shipments:
        if shipment.order_id not in orders:
            raise ContractViolation('shipment_relation', shipment.id)
        members = shipment_memberships(orders[shipment.order_id].product_id)
        if sum(row.final_planned_kg for row in members if row.shipment_id == shipment.id) > shipment.capacity_kg:
            raise ContractViolation('shipment_capacity', shipment.id)
    if {row.id: row.order_id for row in plan.shipments} != planned_shipments:
        raise ContractViolation('shipment_relation', 'shipments differ from whole-unit membership plan')
    if plan.transfers or plan.inspections or plan.lineage_edges or plan.shipment_materials or plan.mass_movements:
        raise ContractViolation('initial_credit', 'runtime rows must start empty')
    if any(row.active for row in plan.allocations) or any(row.status != 'PLANNED' for row in (*plan.work_orders, *plan.shipments)) or any(row.status != 'QUEUED' or row.start_ms is not None or row.end_ms is not None for row in plan.processes):
        raise ContractViolation('initial_release', 'no work is released before first step')
    if any(row.quality_status != 'PENDING' or row.availability_status != 'WIP' or not row.active for row in plan.materials):
        raise ContractViolation('initial_quality', 'source inventory has no sale credit')
    return plan
