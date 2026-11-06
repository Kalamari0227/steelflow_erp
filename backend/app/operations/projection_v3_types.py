"""Read-only schema3 API projection types, distinct from legacy provenance."""
from typing import Literal

from . import contracts_v3 as c
from .contracts_v3_core import Contract, Id, Kg, NonNegative, RunKey


class ProjectionIdentity(Contract):
    schema_version: Literal[3] = 3
    run_id: RunKey
    revision: NonNegative


class FactoryKpis(ProjectionIdentity):
    active_material_count: NonNegative
    active_kg: Kg
    available_kg: Kg
    allocated_kg: Kg
    shipped_kg: Kg
    opening_kg: Kg
    received_kg: Kg
    additions_kg: Kg
    byproduct_kg: Kg
    loss_kg: Kg


class FactoryWorld(c.FactorySnapshot):
    kpis: FactoryKpis


class FactoryCommandReply(FactoryWorld):
    command_id: Id
    replayed: bool
    applied_revision: NonNegative
    applied_run_id: RunKey


class FactoryMaterialDetail(ProjectionIdentity):
    material: c.Material
    current_version: c.MaterialVersion
    versions: tuple[c.MaterialVersion, ...]
    lineage_materials: tuple[c.Material, ...]
    version_edges: tuple[c.VersionEdge, ...]
    process_batches: tuple[c.ProcessBatch, ...]
    batch_io: tuple[c.BatchIO, ...]
    allocations: tuple[c.MaterialAllocation, ...]
    current_allocation: c.MaterialAllocation | None
    order: c.FactoryOrder | None
    work_order: c.WorkOrder | None
    production_lot: c.ProductionLot | None
    origin_stock_lot: c.StockLot | None
    attachments: tuple[c.Attachment, ...]
    current_attachment: c.Attachment | None
    transport_jobs: tuple[c.TransportJob, ...]
    current_job: c.TransportJob | None
    shipments: tuple[c.Shipment, ...]
    shipment_legs: tuple[c.ShipmentLeg, ...]
    quality: tuple[c.QualityRecord, ...]
    events: tuple[c.FactoryEvent, ...]


class FactoryProduction(ProjectionIdentity):
    work_orders: tuple[c.WorkOrder, ...]
    production_lots: tuple[c.ProductionLot, ...]
    processes: tuple[c.ProcessExecution, ...]
    process_batches: tuple[c.ProcessBatch, ...]
    batch_io: tuple[c.BatchIO, ...]
    material_versions: tuple[c.MaterialVersion, ...]
    version_edges: tuple[c.VersionEdge, ...]


class FactoryOrders(ProjectionIdentity):
    orders: tuple[c.FactoryOrder, ...]
    work_orders: tuple[c.WorkOrder, ...]
    allocations: tuple[c.MaterialAllocation, ...]


class FactoryShipments(ProjectionIdentity):
    shipments: tuple[c.Shipment, ...]
    shipment_legs: tuple[c.ShipmentLeg, ...]
    shipment_materials: tuple[c.ShipmentMaterial, ...]


class FactoryCoils(ProjectionIdentity):
    materials: tuple[c.Material, ...]


class FactoryEvents(ProjectionIdentity):
    events: tuple[c.FactoryEvent, ...]


class FactoryOrderDetail(ProjectionIdentity):
    order: c.FactoryOrder
    work_orders: tuple[c.WorkOrder, ...]
    allocations: tuple[c.MaterialAllocation, ...]
    materials: tuple[c.Material, ...]
    shipments: tuple[c.Shipment, ...]
    shipment_legs: tuple[c.ShipmentLeg, ...]
