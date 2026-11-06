"""Production, stock and accounting rows; storage shapes do not execute processes."""
from typing import Literal, Self

from pydantic import ConfigDict, Field, StrictBool, model_validator

from .contracts_v3_core import (
    AvailabilityStatus, Contract, ContractViolation, Duration, EntityKind, Id, MaterialDimensions,
    MaterialForm, Ms, Positive, ProductId, PositiveKg, ProcessStatus, QualityStatus,
    RunEntity, Text, UTCDateTime,
)


class FactoryOrder(RunEntity):
    customer_id: Id
    product_id: ProductId
    grade: Text
    quantity_kg: PositiveKg
    due_at: UTCDateTime


class WorkOrder(RunEntity):
    order_id: Id
    route_id: Id
    route_version: Positive
    planned_kg: PositiveKg
    status: Literal["PLANNED", "RELEASED", "COMPLETED"]


class ProductionLot(RunEntity):
    work_order_id: Id
    planned_kg: PositiveKg


class StockLot(RunEntity):
    source_kind: Literal["OPENING", "PURCHASED", "RETURNED"]
    grade: Text
    form: MaterialForm
    quantity_kg: PositiveKg
    received_at_ms: Ms


class StockReceipt(RunEntity):
    stock_lot_id: Id
    source_id: Id
    quantity_kg: PositiveKg
    received_at_ms: Ms
    event_id: Id | None


class Material(RunEntity):
    grade: Text
    form: MaterialForm
    dimensions: MaterialDimensions
    weight_kg: PositiveKg
    current_version_id: Id
    origin_stock_lot_id: Id | None
    production_lot_id: Id | None
    quality_status: QualityStatus
    availability_status: AvailabilityStatus
    active: StrictBool

    @model_validator(mode="after")
    def check_activity(self) -> Self:
        if self.active == (self.availability_status == "CONSUMED"):
            raise ContractViolation("invalid_contract", "only consumed material is inactive")
        return self


class MaterialVersion(RunEntity):
    material_id: Id
    ordinal: Positive
    grade: Text
    form: MaterialForm
    dimensions: MaterialDimensions
    weight_kg: PositiveKg
    cause_event_id: Id | None


class VersionEdge(RunEntity):
    batch_id: Id
    input_version_id: Id
    output_version_id: Id
    transferred_kg: PositiveKg


class MaterialAllocation(RunEntity):
    material_id: Id
    order_id: Id
    work_order_id: Id
    quantity_kg: PositiveKg
    active: StrictBool


class ProcessBatch(RunEntity):
    process_id: Id | None
    recipe_id: Id
    status: ProcessStatus
    start_ms: Ms | None
    end_ms: Ms | None

    @model_validator(mode="after")
    def check_window(self) -> Self:
        check_process_window(self.status, self.start_ms, self.end_ms)
        return self


BatchRole = Literal["INPUT", "STOCK_ADDITION", "EXTERNAL_ADDITION", "OUTPUT", "BYPRODUCT", "LOSS"]


class BatchIO(RunEntity):
    batch_id: Id
    role: BatchRole
    material_version_id: Id | None
    quantity_kg: PositiveKg
    source_id: Id | None

    @model_validator(mode="after")
    def check_source(self) -> Self:
        if self.material_version_id is None and (self.role in {"INPUT", "STOCK_ADDITION", "OUTPUT"} or self.source_id is None):
            raise ContractViolation("invalid_contract", "batch IO requires physical version or explicit external/loss source")
        return self


def check_process_window(status: ProcessStatus, start: int | None, end: int | None) -> None:
    if end is not None and (start is None or end <= start):
        raise ContractViolation("invalid_contract", "end must follow start")
    if status in {"RUNNING", "COMPLETED"} and (start is None or end is None):
        raise ContractViolation("invalid_contract", "running/completed requires time window")


class ProcessExecution(RunEntity):
    work_order_id: Id | None
    route_step_id: Id
    equipment_id: Id
    status: ProcessStatus
    ready_at_ms: Ms
    start_ms: Ms | None
    end_ms: Ms | None
    planned_duration_ms: Duration
    blocked_reason: Text | None

    @model_validator(mode="after")
    def check_window(self) -> Self:
        check_process_window(self.status, self.start_ms, self.end_ms)
        if self.start_ms is not None and self.start_ms < self.ready_at_ms:
            raise ContractViolation("invalid_contract", "process begins before ready")
        return self


class QualityRecord(RunEntity):
    material_id: Id
    material_version_id: Id
    status: QualityStatus
    at_ms: Ms
    event_id: Id | None


EventType = Literal["RUN_CREATED", "CLOCK_ADVANCED", "PLAYING_CHANGED", "SPEED_CHANGED", "STOCK_RECEIVED", "MATERIAL_ALLOCATED", "BATCH_STARTED", "BATCH_COMPLETED", "ATTACHMENT_ACQUIRED", "ATTACHMENT_RELEASED", "JOB_ASSIGNED", "JOB_EMPTY_APPROACH", "JOB_QUEUED", "JOB_LOADING", "JOB_DISPATCHED", "JOB_UNLOADING", "JOB_RETURNING", "JOB_IDLE", "JOB_BLOCKED", "JOB_COMPLETED", "RESERVATION_ACQUIRED", "RESERVATION_RELEASED", "MOTION_PHASE_STARTED", "MOTION_PHASE_COMPLETED", "QUALITY_RECORDED", "PLAN_RELEASED", "WORK_ORDER_RELEASED", "PROCESS_STARTED", "PROCESS_BLOCKED", "PROCESS_COMPLETED", "MATERIAL_TRANSFORMED", "MATERIAL_SPLIT", "MATERIAL_MERGED", "TRANSFER_STARTED", "TRANSFER_LOADING", "TRANSFER_DEPARTED", "TRANSFER_UNLOADING", "TRANSFER_ARRIVED", "INSPECTION_STARTED", "INSPECTION_PASSED", "INSPECTION_HELD", "INSPECTION_FAILED", "PACKAGING_STARTED", "PACKAGING_COMPLETED", "MATERIAL_AVAILABLE", "SHIPMENT_ALLOCATED", "SHIPMENT_LOADING", "MATERIAL_LOADED", "SHIPMENT_LOADED", "SHIPMENT_DISPATCHED", "SHIPMENT_AT_PORT", "SHIPMENT_SAILING", "SHIPMENT_DELIVERED", "ORDER_DELIVERED", "RESOURCE_DOWN", "RESOURCE_RESTORED", "RECOVERY_ROUTED"]


class EventContext(Contract):
    model_config = ConfigDict(json_schema_serialization_defaults_required=True)
    reason_code: Text | None = None
    reason: Text | None = None
    material_ids: tuple[Id, ...] = ()
    order_id: Id | None = None
    work_order_id: Id | None = None
    process_id: Id | None = None
    batch_id: Id | None = None
    job_id: Id | None = None
    shipment_leg_id: Id | None = None
    resource_id: Id | None = None
    reservation_id: Id | None = None
    from_attachment_id: Id | None = None
    to_attachment_id: Id | None = None
    from_owner_id: Id | None = None
    to_owner_id: Id | None = None


class FactoryEvent(RunEntity):
    model_config = ConfigDict(json_schema_serialization_defaults_required=True)
    sequence: Positive
    event_type: EventType
    entity_type: EntityKind
    entity_id: Id
    at_ms: Ms
    occurred_at: UTCDateTime
    source_id: Id
    payload: EventContext = Field(default_factory=EventContext)


class MassLedgerEntry(RunEntity):
    source_id: Id
    kind: Literal["OPENING_STOCK", "EXTERNAL_RECEIPT", "EXTERNAL_ADDITION", "BYPRODUCT", "IRRECOVERABLE_LOSS"]
    quantity_kg: PositiveKg
    at_ms: Ms
    material_id: Id | None
    batch_id: Id | None
    event_id: Id | None
