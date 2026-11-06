"""Read-only typed views of a single operations revision."""
from dataclasses import asdict
from typing import Final

from app.operations import contracts as c
from app.operations.fulfillment import order_totals
from app.operations.lineage import mass_balance

COIL_FORMS: Final = frozenset(('HR_COIL', 'CR_COIL', 'GI_COIL', 'GA_COIL', 'HGI_COIL', 'EG_COIL', 'GO_COIL', 'NGO_COIL', 'WIRE_COIL', 'STS_HR_COIL', 'STS_CR_COIL', 'TI_HR_COIL', 'TI_CR_COIL'))


class OrderView(c.OperationsOrder):
    status: c.OrderStatus
    produced_kg: int
    dispatched_kg: int
    delivered_kg: int
    remaining_dispatch_kg: int
    remaining_delivery_kg: int
    work_order_ids: tuple[c.Id, ...]
    material_ids: tuple[c.Id, ...]
    shipment_ids: tuple[c.Id, ...]


class MaterialView(c.Contract):
    run_id: c.RunKey
    revision: c.NonNegative
    material: c.Material
    order: OrderView
    lot: c.OperationsLot
    work_order: c.WorkOrder
    versions: tuple[c.MaterialVersion, ...]
    lineage: tuple[c.MaterialLineageEdge, ...]
    processes: tuple[c.ProcessExecution, ...]
    transfers: tuple[c.Transfer, ...]
    inspections: tuple[c.Inspection, ...]
    shipments: tuple[c.OperationsShipment, ...]


class CoilView(c.Material):
    grade: str
    width_mm: c.Dimension | None
    thickness_mm: c.Dimension | None
    order_id: c.Id


class LotView(c.OperationsLot):
    order_id: c.Id
    actual_kg: c.Kg
    status: str


class Kpis(c.Contract):
    total_orders: int
    active_orders: int
    total_mass_kg: int
    produced_kg: int
    dispatched_kg: int
    in_transit_kg: int
    delivered_kg: int
    throughput_kg: int
    coil_count: int
    available_kg: int


class ProductionView(c.Contract):
    run_id: c.RunKey
    revision: c.NonNegative
    materials: tuple[c.Material, ...]
    processes: tuple[c.ProcessExecution, ...]
    transfers: tuple[c.Transfer, ...]
    lots: tuple[LotView, ...]
    orders: tuple[OrderView, ...]


def snapshot(model: c.SimulationModel) -> c.OperationsSnapshot:
    """Validate the complete material ledger without advancing the scheduler."""
    return c.OperationsSnapshot.model_validate({
        'run': model.run, 'mass_balance': mass_balance(model),
        **{name: tuple(getattr(model, name).values()) for name in c.TransitionDelta.model_fields if name != 'resources'},
    })


def order_views(model: c.SimulationModel) -> tuple[OrderView, ...]:
    return tuple(OrderView(**order.model_dump(), **asdict(order_totals(model, order.id)),
                          work_order_ids=tuple(row.id for row in model.work_orders.values() if row.order_id == order.id),
                          material_ids=tuple(row.id for row in model.materials.values() if model.work_orders[model.lots[row.lot_id].work_order_id].order_id == order.id),
                          shipment_ids=tuple(row.id for row in model.shipments.values() if row.order_id == order.id)) for order in model.orders.values())


def material_view(model: c.SimulationModel, material_id: c.EntityId) -> MaterialView:
    """Include historical parent/child identity and actual current-version inspection."""
    if material_id not in model.materials:
        raise c.ContractViolation('material_not_found', material_id)
    material = model.materials[material_id]
    lot = model.lots[material.lot_id]
    work = model.work_orders[lot.work_order_id]
    shipment_ids = {row.shipment_id for row in model.shipment_materials.values() if row.material_id == material_id}
    return MaterialView(run_id=model.run.id, revision=model.run.revision, material=material, lot=lot, work_order=work,
                        order=next(row for row in order_views(model) if row.id == work.order_id),
                        versions=tuple(sorted((row for row in model.material_versions.values() if row.material_id == material_id), key=lambda row: row.ordinal)),
                        lineage=tuple(row for row in model.lineage_edges.values() if material_id in (row.parent_material_id, row.child_material_id)),
                        processes=tuple(sorted((row for row in model.processes.values() if row.material_id == material_id), key=lambda row: row.step_ordinal)),
                        transfers=tuple(row for row in model.transfers.values() if row.material_id == material_id),
                        inspections=tuple(row for row in model.inspections.values() if row.material_id == material_id),
                        shipments=tuple(row for row in model.shipments.values() if row.id in shipment_ids))


def coil_views(model: c.SimulationModel) -> tuple[CoilView, ...]:
    result = []
    for material in model.materials.values():
        if material.active and material.form in COIL_FORMS:
            order = model.orders[model.work_orders[model.lots[material.lot_id].work_order_id].order_id]
            result.append(CoilView(**material.model_dump(), grade=order.grade, width_mm=order.width_mm, thickness_mm=order.thickness_mm, order_id=order.id))
    return tuple(result)


def coil_view(model: c.SimulationModel, material_id: c.EntityId) -> CoilView:
    result = next((row for row in coil_views(model) if row.id == material_id), None)
    if result is None:
        raise c.ContractViolation('coil_not_found', material_id)
    return result


def inventory_views(model: c.SimulationModel) -> tuple[c.Material, ...]:
    return tuple(row for row in model.materials.values() if row.active)


def lot_views(model: c.SimulationModel) -> tuple[LotView, ...]:
    passed = {row.material_id for row in model.inspections.values() if row.status == 'PASSED' and row.inspected_version_id == model.materials[row.material_id].current_version_id and row.end_ms is not None and row.end_ms <= model.run.elapsed_ms}
    return tuple(LotView(**lot.model_dump(), order_id=model.work_orders[lot.work_order_id].order_id,
                         actual_kg=c.Kilograms(sum(row.weight_kg for row in model.materials.values() if row.lot_id == lot.id and row.active and row.quality_status == 'PASSED' and row.id in passed)),
                         status=model.work_orders[lot.work_order_id].status) for lot in model.lots.values())


def kpis(model: c.SimulationModel) -> Kpis:
    totals = tuple(order_totals(model, row.id) for row in model.orders.values())
    dispatched, delivered = sum(row.dispatched_kg for row in totals), sum(row.delivered_kg for row in totals)
    return Kpis(total_orders=len(totals), active_orders=sum(row.status != 'DELIVERED' for row in totals),
                total_mass_kg=mass_balance(model).active_kg, produced_kg=sum(row.produced_kg for row in totals),
                dispatched_kg=dispatched, in_transit_kg=dispatched-delivered, delivered_kg=delivered,
                throughput_kg=dispatched, coil_count=len(coil_views(model)),
                available_kg=sum(row.weight_kg for row in model.materials.values() if row.active and row.availability_status == 'AVAILABLE'))


def production_view(model: c.SimulationModel) -> ProductionView:
    return ProductionView(run_id=model.run.id, revision=model.run.revision, materials=tuple(model.materials.values()),
                          processes=tuple(model.processes.values()), transfers=tuple(model.transfers.values()), lots=lot_views(model), orders=order_views(model))


def journey_view(model: c.SimulationModel, material_id: c.EntityId = c.EntityId('MAT-ga-01')) -> MaterialView:
    return material_view(model, material_id)
