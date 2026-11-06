"""Mutable SQLAlchemy rows for the authoritative operations transaction.

The audit table remains app.models.OperationEvent. UTC timestamps use its ISO
string representation; the contract boundary parses them into aware datetimes.
All business references are scoped to a run. Deferred current-version keys allow
an atomic material/version insert or transformation with foreign keys enabled.
"""
# noqa: SIZE_OK -- the assigned persistence schema is one declarative registry.
from typing import Final, get_args

from sqlalchemy import JSON, CheckConstraint, ForeignKey, ForeignKeyConstraint, Index, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base, OperationEvent
from app.operations import contracts as c


def integer(column: str, minimum: int = 0) -> CheckConstraint:
    return CheckConstraint(f"typeof({column}) = 'integer' AND {column} BETWEEN {minimum} AND 9007199254740991")


def choices(column: str, values: tuple[str, ...]) -> CheckConstraint:
    return CheckConstraint(f"{column} IN ({','.join(repr(value) for value in values)})")


def reference(column: str, table: str) -> ForeignKeyConstraint:
    return ForeignKeyConstraint(["run_id", column], [f"{table}.run_id", f"{table}.id"], deferrable=True, initially="DEFERRED")


class RunRow:
    run_id: Mapped[str] = mapped_column(ForeignKey("operations_runs.id"), primary_key=True)
    id: Mapped[str] = mapped_column(primary_key=True)


class OperationsRun(Base):
    __tablename__ = "operations_runs"
    __table_args__ = (
        choices("scenario_id", get_args(c.ScenarioId)), CheckConstraint("fixture_version = 'erp-v1'"),
        integer("seed"), integer("elapsed_ms"), integer("duration_ms", 1), integer("revision"),
        integer("event_sequence"), integer("plan_revision"), CheckConstraint("playing IN (0,1)"),
        CheckConstraint("speed IN (1,2,4)"), CheckConstraint("elapsed_ms <= duration_ms"),
        CheckConstraint("epoch_at IN ('2026-10-30T00:00:00Z','2026-10-30T00:00:00+00:00')"),
    )
    id: Mapped[str] = mapped_column(primary_key=True)
    fixture_version: Mapped[str] = mapped_column(default="erp-v1")
    seed: Mapped[int] = mapped_column(default=30)
    scenario_id: Mapped[str]
    elapsed_ms: Mapped[int]
    duration_ms: Mapped[int]
    revision: Mapped[int]
    event_sequence: Mapped[int]
    playing: Mapped[bool]
    speed: Mapped[int]
    epoch_at: Mapped[str]
    started_at: Mapped[str]
    plan_revision: Mapped[int]


class CurrentRun(Base):
    __tablename__ = "operations_current_run"
    __table_args__ = (CheckConstraint("id = 1"),)
    id: Mapped[int] = mapped_column(primary_key=True, default=1)
    run_id: Mapped[str] = mapped_column(ForeignKey("operations_runs.id"))


class OperationsOrder(RunRow, Base):
    __tablename__ = "operations_orders"
    __table_args__ = (
        choices("product_id", get_args(c.ProductId)), integer("quantity_kg", 1),
        CheckConstraint("width_mm IS NULL OR (width_mm > 0 AND width_mm < 1e308)"),
        CheckConstraint("thickness_mm IS NULL OR (thickness_mm > 0 AND thickness_mm < 1e308)"),
    )
    customer_id: Mapped[str] = mapped_column(ForeignKey("customers.id"))
    product_id: Mapped[str]
    grade: Mapped[str]
    width_mm: Mapped[float | None]
    thickness_mm: Mapped[float | None]
    quantity_kg: Mapped[int]
    due_at: Mapped[str]


class WorkOrder(RunRow, Base):
    __tablename__ = "work_orders"
    __table_args__ = (reference("order_id", "operations_orders"), integer("route_version", 1), integer("planned_kg", 1),
                      choices("status", ("PLANNED", "RELEASED", "COMPLETED")), UniqueConstraint("run_id", "id", "order_id"))
    order_id: Mapped[str]
    route_id: Mapped[str]
    route_version: Mapped[int]
    planned_kg: Mapped[int]
    status: Mapped[str] = mapped_column(default="PLANNED")


class OperationsLot(RunRow, Base):
    __tablename__ = "operations_lots"
    __table_args__ = (reference("work_order_id", "work_orders"), integer("planned_kg", 1))
    work_order_id: Mapped[str]
    planned_kg: Mapped[int]


class Material(RunRow, Base):
    __tablename__ = "materials"
    __table_args__ = (
        reference("lot_id", "operations_lots"), integer("weight_kg", 1), choices("form", get_args(c.MaterialForm)),
        choices("quality_status", get_args(c.QualityStatus)), choices("availability_status", get_args(c.AvailabilityStatus)),
        CheckConstraint("active IN (0,1) AND active = (availability_status != 'CONSUMED')"),
        ForeignKeyConstraint(["run_id", "current_version_id", "id", "form", "weight_kg"],
                             ["material_versions.run_id", "material_versions.id", "material_versions.material_id", "material_versions.form", "material_versions.weight_kg"],
                             name="fk_material_current_version", deferrable=True, initially="DEFERRED"),
    )
    lot_id: Mapped[str]
    lineage_id: Mapped[str]
    current_version_id: Mapped[str]
    form: Mapped[str]
    weight_kg: Mapped[int]
    location_id: Mapped[str] = mapped_column(ForeignKey("locations.id"))
    quality_status: Mapped[str]
    availability_status: Mapped[str]
    active: Mapped[bool]


class MaterialVersion(RunRow, Base):
    __tablename__ = "material_versions"
    __table_args__ = (
        reference("material_id", "materials"), reference("cause_event_id", "operation_events"),
        reference("parent_version_id", "material_versions"),
        UniqueConstraint("run_id", "material_id", "ordinal"), UniqueConstraint("run_id", "id", "material_id"),
        UniqueConstraint("run_id", "id", "material_id", "form", "weight_kg"),
        integer("ordinal", 1), integer("weight_kg", 1), choices("form", get_args(c.MaterialForm)),
        CheckConstraint("parent_version_id IS NULL OR parent_version_id != id"),
    )
    material_id: Mapped[str]
    ordinal: Mapped[int]
    parent_version_id: Mapped[str | None]
    form: Mapped[str]
    weight_kg: Mapped[int]
    cause_event_id: Mapped[str | None]


class ProcessExecution(RunRow, Base):
    __tablename__ = "process_executions"
    __table_args__ = (
        reference("material_id", "materials"), reference("predecessor_id", "process_executions"),
        choices("status", get_args(c.ProcessStatus)), choices("input_form", get_args(c.MaterialForm)), choices("output_form", get_args(c.MaterialForm)),
        integer("step_ordinal"), integer("planned_duration_ms", 1), integer("ready_at_ms"),
        CheckConstraint("start_ms IS NULL OR (typeof(start_ms)='integer' AND start_ms >= 0)"),
        CheckConstraint("end_ms IS NULL OR (typeof(end_ms)='integer' AND end_ms >= 0)"),
        CheckConstraint("end_ms IS NULL OR start_ms IS NULL OR end_ms > start_ms"),
        CheckConstraint("status NOT IN ('RUNNING','COMPLETED') OR (start_ms IS NOT NULL AND end_ms IS NOT NULL)"),
        integer("additions_kg"), integer("loss_kg"), CheckConstraint("split_count IN (1,2)"),
        CheckConstraint("predecessor_id IS NULL OR predecessor_id != id"),
    )
    material_id: Mapped[str]
    route_step_id: Mapped[str]
    source_step_id: Mapped[str]
    step_ordinal: Mapped[int]
    equipment_id: Mapped[str]
    predecessor_id: Mapped[str | None]
    status: Mapped[str]
    planned_duration_ms: Mapped[int]
    ready_at_ms: Mapped[int] = mapped_column(default=0)
    start_ms: Mapped[int | None]
    end_ms: Mapped[int | None]
    input_form: Mapped[str]
    output_form: Mapped[str]
    additions_kg: Mapped[int] = mapped_column(default=0)
    loss_kg: Mapped[int] = mapped_column(default=0)
    split_count: Mapped[int] = mapped_column(default=1)
    blocked_reason: Mapped[str | None]


class MaterialLineageEdge(RunRow, Base):
    __tablename__ = "material_lineage_edges"
    __table_args__ = (
        reference("parent_material_id", "materials"), reference("child_material_id", "materials"), reference("process_id", "process_executions"),
        UniqueConstraint("run_id", "parent_material_id", "child_material_id"),
        CheckConstraint("parent_material_id != child_material_id"), integer("transferred_kg", 1),
    )
    parent_material_id: Mapped[str]
    child_material_id: Mapped[str]
    process_id: Mapped[str]
    transferred_kg: Mapped[int]


class MaterialAllocation(RunRow, Base):
    __tablename__ = "material_allocations"
    __table_args__ = (
        reference("order_id", "operations_orders"), reference("material_id", "materials"),
        ForeignKeyConstraint(["run_id", "work_order_id", "order_id"], ["work_orders.run_id", "work_orders.id", "work_orders.order_id"], deferrable=True, initially="DEFERRED"),
        integer("final_planned_kg", 1), CheckConstraint("active IN (0,1)"),
        Index("uq_material_active_allocation", "run_id", "material_id", unique=True, sqlite_where=text("active = 1")),
    )
    order_id: Mapped[str]
    work_order_id: Mapped[str]
    material_id: Mapped[str]
    final_planned_kg: Mapped[int]
    active: Mapped[bool]


class Transfer(RunRow, Base):
    __tablename__ = "transfers"
    __table_args__ = (
        reference("material_id", "materials"), reference("process_id", "process_executions"),
        choices("mode", get_args(c.TransferMode)), choices("status", get_args(c.TransferStatus)),
        CheckConstraint("mode = 'roller' OR vehicle_id IS NOT NULL"), integer("capacity_kg", 1), integer("travel_duration_ms", 1),
        CheckConstraint("phase_start_ms IS NULL OR (typeof(phase_start_ms)='integer' AND phase_start_ms >= 0)"),
        CheckConstraint("phase_end_ms IS NULL OR (typeof(phase_end_ms)='integer' AND phase_end_ms >= 0)"),
        CheckConstraint("phase_start_ms IS NULL OR phase_end_ms IS NULL OR phase_end_ms > phase_start_ms"),
        Index("uq_material_active_transfer", "run_id", "material_id", unique=True, sqlite_where=text("status != 'ARRIVED'")),
    )
    material_id: Mapped[str]
    from_location_id: Mapped[str] = mapped_column(ForeignKey("locations.id"))
    to_location_id: Mapped[str] = mapped_column(ForeignKey("locations.id"))
    mode: Mapped[str]
    vehicle_id: Mapped[str | None]
    crane_id: Mapped[str | None]
    status: Mapped[str]
    phase_start_ms: Mapped[int | None]
    phase_end_ms: Mapped[int | None]
    capacity_kg: Mapped[int]
    process_id: Mapped[str | None]
    travel_duration_ms: Mapped[int] = mapped_column(default=3000)


class Inspection(RunRow, Base):
    __tablename__ = "inspections"
    __table_args__ = (
        reference("material_id", "materials"), reference("release_event_id", "operation_events"),
        ForeignKeyConstraint(["run_id", "inspected_version_id", "material_id"], ["material_versions.run_id", "material_versions.id", "material_versions.material_id"], deferrable=True, initially="DEFERRED"),
        choices("status", get_args(c.QualityStatus)),
    )
    material_id: Mapped[str]
    status: Mapped[str]
    inspected_version_id: Mapped[str]
    reason: Mapped[str | None]
    release_event_id: Mapped[str | None]
    start_ms: Mapped[int | None]
    end_ms: Mapped[int | None]
    packaging_end_ms: Mapped[int | None]


class OperationsShipment(RunRow, Base):
    __tablename__ = "operations_shipments"
    __table_args__ = (reference("order_id", "operations_orders"), choices("mode", ("SEA", "ROAD")),
                      choices("status", get_args(c.ShipmentStatus)), integer("capacity_kg", 1))
    order_id: Mapped[str]
    mode: Mapped[str] = mapped_column(default="SEA")
    status: Mapped[str]
    location_id: Mapped[str] = mapped_column(ForeignKey("locations.id"))
    capacity_kg: Mapped[int]
    etd_at: Mapped[str | None]
    eta_at: Mapped[str | None]
    phase_start_ms: Mapped[int | None]
    phase_end_ms: Mapped[int | None]
    delivered_at: Mapped[str | None]


class ShipmentMaterial(RunRow, Base):
    __tablename__ = "shipment_materials"
    __table_args__ = (
        reference("shipment_id", "operations_shipments"), reference("material_id", "materials"),
        CheckConstraint("active IN (0,1)"), CheckConstraint("loaded IN (0,1)"),
        Index("uq_material_active_shipment", "run_id", "material_id", unique=True, sqlite_where=text("active = 1")),
    )
    shipment_id: Mapped[str]
    material_id: Mapped[str]
    active: Mapped[bool] = mapped_column(default=True)
    loaded: Mapped[bool] = mapped_column(default=False)


class MassMovement(RunRow, Base):
    __tablename__ = "mass_movements"
    __table_args__ = (
        reference("cause_event_id", "operation_events"), reference("process_id", "process_executions"),
        UniqueConstraint("run_id", "process_id"), integer("input_kg"), integer("output_kg"), integer("additions_kg"), integer("loss_kg"),
        CheckConstraint("input_kg + additions_kg = output_kg + loss_kg"),
        CheckConstraint("json_valid(input_material_ids) AND json_type(input_material_ids) = 'array'"),
        CheckConstraint("json_valid(output_material_ids) AND json_type(output_material_ids) = 'array'"),
    )
    cause_event_id: Mapped[str]
    process_id: Mapped[str]
    input_material_ids: Mapped[list[str]] = mapped_column(JSON)
    output_material_ids: Mapped[list[str]] = mapped_column(JSON)
    input_kg: Mapped[int]
    output_kg: Mapped[int]
    additions_kg: Mapped[int]
    loss_kg: Mapped[int]


class CommandReceipt(Base):
    __tablename__ = "command_receipts"
    __table_args__ = (choices("action", ("play", "pause", "reset", "step", "speed", "scenario")), integer("applied_revision"),
                      CheckConstraint("length(payload_digest) = 64 AND payload_digest NOT GLOB '*[^0-9a-f]*'"))
    run_id: Mapped[str] = mapped_column(ForeignKey("operations_runs.id"), primary_key=True)
    command_id: Mapped[str] = mapped_column(primary_key=True)
    action: Mapped[str]
    payload_digest: Mapped[str]
    applied_revision: Mapped[int]


# The global event id remains unchanged; the extra index permits same-run FKs.
EVENT_RUN_INDEX: Final = Index("uq_operation_event_run_id", OperationEvent.run_id, OperationEvent.id, unique=True)
