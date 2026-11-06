"""Pure read projections over an admitted snapshot; no inferred production state."""
from collections.abc import Iterable
from typing import Final

from . import contracts_v3 as c
from .contracts_v3_core import ACTIVE_JOB_STATUSES, ContractViolation, EntityId, Kilograms, RunEntity
from .projection_v3_types import (
    FactoryCoils, FactoryCommandReply, FactoryEvents, FactoryKpis, FactoryMaterialDetail,
    FactoryOrderDetail, FactoryOrders, FactoryProduction, FactoryShipments, FactoryWorld,
)

COIL_FORMS: Final = frozenset({
    "HR_COIL", "CR_COIL", "GI_COIL", "GA_COIL", "HGI_COIL", "EG_COIL", "GO_COIL",
    "NGO_COIL", "WIRE_COIL", "STS_HR_COIL", "STS_CR_COIL", "TI_HR_COIL", "TI_CR_COIL",
})


def _ordered[T: RunEntity](rows: Iterable[T]) -> tuple[T, ...]:
    return tuple(sorted(rows, key=lambda row: row.id))


def project_kpis(state: c.FactorySnapshot) -> FactoryKpis:
    """Count physical stock once; accounting sources come only from the ledger."""
    active = tuple(row for row in state.materials if row.active)
    return FactoryKpis(
        run_id=state.run.id, revision=state.run.revision,
        active_material_count=len(active), active_kg=Kilograms(sum(r.weight_kg for r in active)),
        available_kg=Kilograms(sum(r.weight_kg for r in active if r.availability_status == "AVAILABLE")),
        allocated_kg=Kilograms(sum(r.quantity_kg for r in state.allocations if r.active)),
        shipped_kg=Kilograms(sum(r.weight_kg for r in active if r.availability_status == "SHIPPED")),
        opening_kg=Kilograms(sum(r.quantity_kg for r in state.mass_ledger if r.kind == "OPENING_STOCK")),
        received_kg=Kilograms(sum(r.quantity_kg for r in state.mass_ledger if r.kind == "EXTERNAL_RECEIPT")),
        additions_kg=Kilograms(sum(r.quantity_kg for r in state.mass_ledger if r.kind == "EXTERNAL_ADDITION")),
        byproduct_kg=Kilograms(sum(r.quantity_kg for r in state.mass_ledger if r.kind == "BYPRODUCT")),
        loss_kg=Kilograms(sum(r.quantity_kg for r in state.mass_ledger if r.kind == "IRRECOVERABLE_LOSS")),
    )


def project_world(state: c.FactorySnapshot) -> FactoryWorld:
    return FactoryWorld(**state.model_dump(), kpis=project_kpis(state))


def project_command_reply(state: c.FactorySnapshot, result: c.CommandResult) -> FactoryCommandReply:
    return FactoryCommandReply(**project_world(state).model_dump(), command_id=result.command_id,
                               replayed=result.replayed, applied_revision=result.run.revision,
                               applied_run_id=result.run.id)


def material_detail(state: c.FactorySnapshot, material_id: EntityId) -> FactoryMaterialDetail:
    """Keep the connected batch hypergraph, including sibling inputs and outputs."""
    material = next((r for r in state.materials if r.id == material_id), None)
    if material is None:
        raise ContractViolation("not_found", f"material {material_id}")
    version_ids = {r.id for r in state.material_versions if r.material_id == material_id}
    batch_ids: set[EntityId] = set()
    while True:
        connected_batches = {r.batch_id for r in state.batch_io if r.material_version_id in version_ids}
        connected_versions = {r.material_version_id for r in state.batch_io
                              if r.batch_id in connected_batches and r.material_version_id is not None}
        if connected_batches <= batch_ids and connected_versions <= version_ids:
            break
        batch_ids.update(connected_batches)
        version_ids.update(connected_versions)
    versions = _ordered(r for r in state.material_versions if r.id in version_ids)
    related_material_ids = {r.material_id for r in versions}
    allocations = _ordered(r for r in state.allocations if r.material_id == material_id)
    allocation = next((r for r in allocations if r.active), None)
    attachments = _ordered(r for r in state.attachments if r.material_id == material_id)
    jobs = _ordered(r for r in state.transport_jobs if r.material_id == material_id)
    shipment_ids = {r.shipment_id for r in state.shipment_materials if r.material_id == material_id}
    leg_ids = {r.shipment_leg_id for r in jobs if r.shipment_leg_id is not None}
    shipment_ids.update(r.shipment_id for r in state.shipment_legs if r.id in leg_ids)
    event_ids = {r.cause_event_id for r in versions if r.cause_event_id is not None}
    return FactoryMaterialDetail(
        run_id=state.run.id, revision=state.run.revision, material=material,
        current_version=next(r for r in versions if r.id == material.current_version_id),
        versions=versions, lineage_materials=_ordered(r for r in state.materials if r.id in related_material_ids),
        version_edges=_ordered(r for r in state.version_edges if r.batch_id in batch_ids),
        process_batches=_ordered(r for r in state.process_batches if r.id in batch_ids),
        batch_io=_ordered(r for r in state.batch_io if r.batch_id in batch_ids),
        allocations=allocations, current_allocation=allocation,
        order=next((r for r in state.orders if allocation is not None and r.id == allocation.order_id), None),
        work_order=next((r for r in state.work_orders if allocation is not None and r.id == allocation.work_order_id), None),
        production_lot=next((r for r in state.production_lots if r.id == material.production_lot_id), None),
        origin_stock_lot=next((r for r in state.stock_lots if r.id == material.origin_stock_lot_id), None),
        attachments=attachments, current_attachment=next((r for r in attachments if r.released_at_ms is None), None),
        transport_jobs=jobs, current_job=next((r for r in jobs if r.status in ACTIVE_JOB_STATUSES), None),
        shipments=_ordered(r for r in state.shipments if r.id in shipment_ids),
        shipment_legs=_ordered(r for r in state.shipment_legs if r.shipment_id in shipment_ids),
        quality=_ordered(r for r in state.quality if r.material_id == material_id),
        events=_ordered(r for r in state.events if r.id in event_ids or
                     (r.entity_type == "material" and r.entity_id == material_id) or
                     material_id in r.payload.material_ids or r.payload.batch_id in batch_ids),
    )


def coil_detail(state: c.FactorySnapshot, material_id: EntityId) -> FactoryMaterialDetail:
    if not any(r.id == material_id and r.form in COIL_FORMS for r in state.materials):
        raise ContractViolation("not_found", f"coil {material_id}")
    return material_detail(state, material_id)


def project_coils(state: c.FactorySnapshot) -> FactoryCoils:
    return FactoryCoils(run_id=state.run.id, revision=state.run.revision,
                        materials=_ordered(r for r in state.materials if r.form in COIL_FORMS))


def project_production(state: c.FactorySnapshot) -> FactoryProduction:
    return FactoryProduction(run_id=state.run.id, revision=state.run.revision,
                             work_orders=state.work_orders, production_lots=state.production_lots,
                             processes=state.processes, process_batches=state.process_batches,
                             batch_io=state.batch_io, material_versions=state.material_versions,
                             version_edges=state.version_edges)


def project_orders(state: c.FactorySnapshot) -> FactoryOrders:
    return FactoryOrders(run_id=state.run.id, revision=state.run.revision, orders=state.orders,
                         work_orders=state.work_orders, allocations=state.allocations)


def project_shipments(state: c.FactorySnapshot) -> FactoryShipments:
    return FactoryShipments(run_id=state.run.id, revision=state.run.revision, shipments=state.shipments,
                            shipment_legs=state.shipment_legs, shipment_materials=state.shipment_materials)


def project_events(state: c.FactorySnapshot) -> FactoryEvents:
    return FactoryEvents(run_id=state.run.id, revision=state.run.revision,
                         events=tuple(sorted(state.events, key=lambda r: r.sequence)))


def order_detail(state: c.FactorySnapshot, order_id: EntityId) -> FactoryOrderDetail:
    order = next((r for r in state.orders if r.id == order_id), None)
    if order is None:
        raise ContractViolation("not_found", f"order {order_id}")
    allocations = _ordered(r for r in state.allocations if r.order_id == order_id)
    material_ids = {r.material_id for r in allocations}
    shipments = _ordered(r for r in state.shipments if r.order_id == order_id)
    shipment_ids = {r.id for r in shipments}
    return FactoryOrderDetail(run_id=state.run.id, revision=state.run.revision, order=order,
                              work_orders=_ordered(r for r in state.work_orders if r.order_id == order_id),
                              allocations=allocations, materials=_ordered(r for r in state.materials if r.id in material_ids),
                              shipments=shipments, shipment_legs=_ordered(r for r in state.shipment_legs if r.shipment_id in shipment_ids))
