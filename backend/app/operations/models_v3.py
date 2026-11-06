"""Mutable SQL rows for caller-owned, run-scoped factory transactions.

The legacy metadata remains untouched. Deferred composite keys allow material
and version changes to commit together, never as partially consistent state.
"""
# noqa: SIZE_OK -- one explicit persistence registry for the assigned factory schema.
from typing import Final, get_args

from pydantic import JsonValue
from sqlalchemy import JSON, CheckConstraint, ForeignKey, ForeignKeyConstraint, Index, LargeBinary, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base
from app.operations.contracts_v3_core import ACTIVE_JOB_STATUSES
from app.operations.contracts_v3_rows import EventType

PREFIX: Final = "factory_v3_"
FORMS: Final = "ORE HOT_METAL LIQUID_STEEL SCRAP SLAB BLOOM BILLET HOT_SLAB HOT_BLOOM HOT_BILLET HOT_STRIP HOT_PLATE STRIP THIN_STRIP COATED_STRIP HR_COIL CR_COIL GI_COIL GA_COIL HGI_COIL EG_COIL GO_COIL NGO_COIL WIRE WIRE_COIL PLATE STS_HR_COIL STS_CR_COIL STS_PLATE TI_INGOT TI_SLAB TI_HR_COIL TI_CR_COIL TI_SHEET TI_PLATE COKE COAL LIMESTONE ALLOY SLAG BYPRODUCT"


def integer(column: str, minimum: int = 0) -> CheckConstraint:
    maximum = 4193483039999 if column.endswith("_ms") else 9007199254740991
    return CheckConstraint(f"{column} IS NULL OR (typeof({column})='integer' AND {column} BETWEEN {minimum} AND {maximum})")


def choices(column: str, values: str) -> CheckConstraint:
    return CheckConstraint(f"{column} IN ({','.join(repr(value) for value in values.split())})")


def reference(column: str, table: str) -> ForeignKeyConstraint:
    return ForeignKeyConstraint(["run_id", column], [f"{PREFIX}{table}.run_id", f"{PREFIX}{table}.id"], deferrable=True, initially="DEFERRED")


def digest(column: str) -> CheckConstraint:
    return CheckConstraint(f"length({column})=64 AND {column} NOT GLOB '*[^0-9a-f]*'")


def interval(start: str = "start_ms", end: str = "end_ms") -> CheckConstraint:
    return CheckConstraint(f"{end} IS NULL OR ({start} IS NOT NULL AND {end} > {start})")


class RunRow:
    run_id: Mapped[str] = mapped_column(ForeignKey("factory_v3_runs.id", deferrable=True, initially="DEFERRED"), primary_key=True)
    id: Mapped[str] = mapped_column(primary_key=True)


class FactoryBundle(Base):
    __tablename__ = "factory_v3_bundles"
    __table_args__ = (digest("bundle_hash"), UniqueConstraint("id", "bundle_hash", "profile"), choices("profile", "v3_contract_test demo scale"))
    id: Mapped[str] = mapped_column(primary_key=True)
    bundle_hash: Mapped[str] = mapped_column(unique=True)
    profile: Mapped[str]
    manifest_bytes: Mapped[bytes] = mapped_column(LargeBinary)
    reader_version: Mapped[str]


class BundleArtifact(Base):
    __tablename__ = "factory_v3_bundle_artifacts"
    __table_args__ = (digest("sha256"),)
    bundle_id: Mapped[str] = mapped_column(ForeignKey("factory_v3_bundles.id", deferrable=True, initially="DEFERRED"), primary_key=True)
    path: Mapped[str] = mapped_column(primary_key=True)
    role: Mapped[str] = mapped_column(index=True)
    format_version: Mapped[str]
    sha256: Mapped[str]
    content: Mapped[bytes] = mapped_column(LargeBinary)


class RunRegistry(Base):
    __tablename__ = "factory_v3_run_registry"
    __table_args__ = (
        choices("schema_version", "1 2 3"),
        CheckConstraint("(schema_version=3 AND fixture_version='factory-v2' AND bundle_id IS NOT NULL) OR (schema_version IN (1,2) AND fixture_version!='factory-v2')"),
        UniqueConstraint("run_id", "bundle_id", "fixture_version"),
    )
    run_id: Mapped[str] = mapped_column(primary_key=True)
    schema_version: Mapped[int]
    fixture_version: Mapped[str]
    bundle_id: Mapped[str | None] = mapped_column(ForeignKey("factory_v3_bundles.id", deferrable=True, initially="DEFERRED"))


class ActiveWriter(Base):
    __tablename__ = "factory_v3_active_writer"
    __table_args__ = (
        CheckConstraint("id=1"), choices("bootstrap_mode", "canonical legacy_fixture v3_contract_test"),
        integer("activation_generation", 1), CheckConstraint("legacy_write_locked IN (0,1)"),
        CheckConstraint("(legacy_write_locked=0 AND bootstrap_mode='legacy_fixture') OR (legacy_write_locked=1 AND bootstrap_mode!='legacy_fixture')"),
    )
    id: Mapped[int] = mapped_column(primary_key=True, default=1)
    run_id: Mapped[str] = mapped_column(ForeignKey("factory_v3_run_registry.run_id", deferrable=True, initially="DEFERRED"))
    bootstrap_mode: Mapped[str]
    activation_generation: Mapped[int]
    legacy_write_locked: Mapped[bool]


class FactoryRun(Base):
    __tablename__ = "factory_v3_runs"
    __table_args__ = (
        ForeignKeyConstraint(["id", "bundle_id", "fixture_version"], ["factory_v3_run_registry.run_id", "factory_v3_run_registry.bundle_id", "factory_v3_run_registry.fixture_version"], deferrable=True, initially="DEFERRED"),
        ForeignKeyConstraint(["bundle_id", "bundle_hash", "profile"], ["factory_v3_bundles.id", "factory_v3_bundles.bundle_hash", "factory_v3_bundles.profile"], deferrable=True, initially="DEFERRED"),
        CheckConstraint("fixture_version='factory-v2'"), choices("scenario_id", "NORMAL DELAY RECOVERY"),
        integer("seed"), integer("elapsed_ms"), integer("duration_ms", 1), integer("revision"), integer("event_sequence"),
        CheckConstraint("elapsed_ms<=duration_ms"), CheckConstraint("playing IN (0,1)"), choices("speed", "1 2 4"),
        CheckConstraint("epoch_at IN ('2026-10-30T00:00:00Z','2026-10-30T00:00:00.000Z','2026-10-30T00:00:00+00:00')"),
    )
    id: Mapped[str] = mapped_column(ForeignKey("factory_v3_run_registry.run_id", deferrable=True, initially="DEFERRED"), primary_key=True)
    fixture_version: Mapped[str]
    bundle_id: Mapped[str]
    bundle_hash: Mapped[str]
    profile: Mapped[str]
    scenario_id: Mapped[str]
    seed: Mapped[int]
    elapsed_ms: Mapped[int]
    duration_ms: Mapped[int]
    revision: Mapped[int]
    event_sequence: Mapped[int]
    playing: Mapped[bool]
    speed: Mapped[int]
    epoch_at: Mapped[str]
    started_at: Mapped[str]


class CommandReceipt(Base):
    __tablename__ = "factory_v3_command_receipts"
    __table_args__ = (digest("payload_digest"), integer("result_revision"), CheckConstraint("json_valid(reply_json)"))
    run_id: Mapped[str] = mapped_column(ForeignKey("factory_v3_run_registry.run_id", deferrable=True, initially="DEFERRED"), primary_key=True)
    command_id: Mapped[str] = mapped_column(primary_key=True)
    payload_digest: Mapped[str]
    result_run_id: Mapped[str] = mapped_column(ForeignKey("factory_v3_run_registry.run_id", deferrable=True, initially="DEFERRED"))
    result_revision: Mapped[int]
    reply_json: Mapped[JsonValue] = mapped_column(JSON)


class FactoryLocation(RunRow, Base):
    __tablename__ = "factory_v3_locations"
    __table_args__ = (CheckConstraint("substr(id,1,3)='v2:'"),)
    kind: Mapped[str]
    x: Mapped[float]
    y: Mapped[float]
    z: Mapped[float]


class FactoryOrder(RunRow, Base):
    __tablename__ = "factory_v3_orders"
    __table_args__ = (integer("quantity_kg", 1), choices("product_id", "slab bloom billet hr plate wire cr gi ga hgi eg go ngo sts-hr sts-cr sts-plate ti-hr ti-cr ti-sheet ti-plate"))
    customer_id: Mapped[str]
    product_id: Mapped[str]
    grade: Mapped[str]
    quantity_kg: Mapped[int]
    due_at: Mapped[str]


class WorkOrder(RunRow, Base):
    __tablename__ = "factory_v3_work_orders"
    __table_args__ = (reference("order_id", "orders"), integer("route_version", 1), integer("planned_kg", 1), choices("status", "PLANNED RELEASED COMPLETED"), UniqueConstraint("run_id", "id", "order_id"))
    order_id: Mapped[str]
    route_id: Mapped[str]
    route_version: Mapped[int]
    planned_kg: Mapped[int]
    status: Mapped[str]


class ProductionLot(RunRow, Base):
    __tablename__ = "factory_v3_production_lots"
    __table_args__ = (reference("work_order_id", "work_orders"), integer("planned_kg", 1))
    work_order_id: Mapped[str]
    planned_kg: Mapped[int]


class StockLot(RunRow, Base):
    __tablename__ = "factory_v3_stock_lots"
    __table_args__ = (choices("source_kind", "OPENING PURCHASED RETURNED"), choices("form", FORMS), integer("quantity_kg", 1), integer("received_at_ms"))
    source_kind: Mapped[str]
    grade: Mapped[str]
    form: Mapped[str]
    quantity_kg: Mapped[int]
    received_at_ms: Mapped[int]


class StockReceipt(RunRow, Base):
    __tablename__ = "factory_v3_receipts"
    __table_args__ = (reference("stock_lot_id", "stock_lots"), reference("event_id", "events"), UniqueConstraint("run_id", "source_id"), integer("quantity_kg", 1), integer("received_at_ms"))
    stock_lot_id: Mapped[str]
    source_id: Mapped[str]
    quantity_kg: Mapped[int]
    received_at_ms: Mapped[int]
    event_id: Mapped[str | None]


class Material(RunRow, Base):
    __tablename__ = "factory_v3_materials"
    __table_args__ = (
        reference("origin_stock_lot_id", "stock_lots"), reference("production_lot_id", "production_lots"),
        ForeignKeyConstraint(["run_id", "current_version_id", "id", "grade", "form", "weight_kg", "dimensions"], ["factory_v3_material_versions.run_id", "factory_v3_material_versions.id", "factory_v3_material_versions.material_id", "factory_v3_material_versions.grade", "factory_v3_material_versions.form", "factory_v3_material_versions.weight_kg", "factory_v3_material_versions.dimensions"], deferrable=True, initially="DEFERRED"),
        choices("form", FORMS), integer("weight_kg", 1), CheckConstraint("json_valid(dimensions) AND json_type(dimensions)='object'"),
        choices("quality_status", "PENDING PASSED HOLD FAILED"), choices("availability_status", "WIP QUARANTINED AVAILABLE RESERVED SHIPPED CONSUMED"),
        CheckConstraint("active IN (0,1) AND ((active=0 AND availability_status='CONSUMED') OR (active=1 AND availability_status!='CONSUMED'))"),
    )
    grade: Mapped[str]
    form: Mapped[str]
    dimensions: Mapped[dict[str, float | None]] = mapped_column(JSON)
    weight_kg: Mapped[int]
    current_version_id: Mapped[str]
    origin_stock_lot_id: Mapped[str | None]
    production_lot_id: Mapped[str | None]
    quality_status: Mapped[str]
    availability_status: Mapped[str]
    active: Mapped[bool]


class MaterialVersion(RunRow, Base):
    __tablename__ = "factory_v3_material_versions"
    __table_args__ = (
        reference("material_id", "materials"), reference("cause_event_id", "events"),
        UniqueConstraint("run_id", "material_id", "ordinal"), UniqueConstraint("run_id", "id", "material_id"),
        UniqueConstraint("run_id", "id", "material_id", "grade", "form", "weight_kg", "dimensions"),
        integer("ordinal", 1), integer("weight_kg", 1), choices("form", FORMS), CheckConstraint("json_valid(dimensions) AND json_type(dimensions)='object'"),
    )
    material_id: Mapped[str]
    ordinal: Mapped[int]
    grade: Mapped[str]
    form: Mapped[str]
    dimensions: Mapped[dict[str, float | None]] = mapped_column(JSON)
    weight_kg: Mapped[int]
    cause_event_id: Mapped[str | None]


class VersionEdge(RunRow, Base):
    __tablename__ = "factory_v3_version_edges"
    __table_args__ = (reference("batch_id", "process_batches"), reference("input_version_id", "material_versions"), reference("output_version_id", "material_versions"), integer("transferred_kg", 1), CheckConstraint("input_version_id!=output_version_id"), UniqueConstraint("run_id", "batch_id", "input_version_id", "output_version_id"))
    batch_id: Mapped[str]
    input_version_id: Mapped[str]
    output_version_id: Mapped[str]
    transferred_kg: Mapped[int]


class MaterialAllocation(RunRow, Base):
    __tablename__ = "factory_v3_allocations"
    __table_args__ = (
        reference("material_id", "materials"), reference("order_id", "orders"),
        ForeignKeyConstraint(["run_id", "work_order_id", "order_id"], ["factory_v3_work_orders.run_id", "factory_v3_work_orders.id", "factory_v3_work_orders.order_id"], deferrable=True, initially="DEFERRED"),
        integer("quantity_kg", 1), CheckConstraint("active IN (0,1)"), Index("factory_v3_one_active_allocation", "run_id", "material_id", unique=True, sqlite_where=text("active=1")),
    )
    material_id: Mapped[str]
    order_id: Mapped[str]
    work_order_id: Mapped[str]
    quantity_kg: Mapped[int]
    active: Mapped[bool]


class ProcessBatch(RunRow, Base):
    __tablename__ = "factory_v3_process_batches"
    __table_args__ = (reference("process_id", "processes"), choices("status", "QUEUED RUNNING BLOCKED COMPLETED"), integer("start_ms"), integer("end_ms"), interval(), CheckConstraint("status NOT IN ('RUNNING','COMPLETED') OR (start_ms IS NOT NULL AND end_ms IS NOT NULL)"))
    process_id: Mapped[str | None]
    recipe_id: Mapped[str]
    status: Mapped[str]
    start_ms: Mapped[int | None]
    end_ms: Mapped[int | None]


class BatchIO(RunRow, Base):
    __tablename__ = "factory_v3_batch_io"
    __table_args__ = (
        reference("batch_id", "process_batches"), reference("material_version_id", "material_versions"), integer("quantity_kg", 1),
        choices("role", "INPUT STOCK_ADDITION EXTERNAL_ADDITION OUTPUT BYPRODUCT LOSS"),
        CheckConstraint("material_version_id IS NOT NULL OR (role IN ('EXTERNAL_ADDITION','BYPRODUCT','LOSS') AND source_id IS NOT NULL)"),
        UniqueConstraint("run_id", "batch_id", "role", "material_version_id"), UniqueConstraint("run_id", "source_id"),
        Index("factory_v3_one_version_consumption", "run_id", "material_version_id", unique=True, sqlite_where=text("role IN ('INPUT','STOCK_ADDITION') AND material_version_id IS NOT NULL")),
    )
    batch_id: Mapped[str]
    role: Mapped[str]
    material_version_id: Mapped[str | None]
    quantity_kg: Mapped[int]
    source_id: Mapped[str | None]


class ProcessExecution(RunRow, Base):
    __tablename__ = "factory_v3_processes"
    __table_args__ = (reference("work_order_id", "work_orders"), choices("status", "QUEUED RUNNING BLOCKED COMPLETED"), integer("ready_at_ms"), integer("start_ms"), integer("end_ms"), integer("planned_duration_ms", 1), interval(), CheckConstraint("start_ms IS NULL OR start_ms>=ready_at_ms"), CheckConstraint("status NOT IN ('RUNNING','COMPLETED') OR (start_ms IS NOT NULL AND end_ms IS NOT NULL)"))
    work_order_id: Mapped[str | None]
    route_step_id: Mapped[str]
    equipment_id: Mapped[str]
    status: Mapped[str]
    ready_at_ms: Mapped[int]
    start_ms: Mapped[int | None]
    end_ms: Mapped[int | None]
    planned_duration_ms: Mapped[int]
    blocked_reason: Mapped[str | None]


class FleetAsset(RunRow, Base):
    __tablename__ = "factory_v3_fleet"
    __table_args__ = (choices("kind", "truck carrier forklift torpedo ladle locomotive railcar ship"), integer("capacity_kg", 1), choices("mode", "road rail hot_metal_rail water"), CheckConstraint("length_m>0 AND length_m<=1.7976931348623157e308"), CheckConstraint("turn_radius_m>=0 AND turn_radius_m<=1.7976931348623157e308"), CheckConstraint("json_valid(load_envelope_m) AND json_type(load_envelope_m)='array' AND json_array_length(load_envelope_m)=3"))
    kind: Mapped[str]
    variant: Mapped[str]
    capacity_kg: Mapped[int]
    length_m: Mapped[float]
    load_envelope_m: Mapped[list[float]] = mapped_column(JSON)
    turn_radius_m: Mapped[float]
    mode: Mapped[str]
    load_socket_id: Mapped[str]


class VehicleState(RunRow, Base):
    __tablename__ = "factory_v3_vehicle_states"
    __table_args__ = (reference("fleet_id", "fleet"), ForeignKeyConstraint(["run_id", "current_job_id", "fleet_id"], ["factory_v3_transport_jobs.run_id", "factory_v3_transport_jobs.id", "factory_v3_transport_jobs.fleet_id"], deferrable=True, initially="DEFERRED"), UniqueConstraint("run_id", "fleet_id"), integer("available_at_ms"), choices("status", "IDLE ASSIGNED EMPTY_APPROACH QUEUED LOADING MOVING UNLOADING RETURNING BLOCKED"), CheckConstraint("json_valid(position_m) AND json_type(position_m)='array' AND json_array_length(position_m)=3"), CheckConstraint("abs(yaw_rad)<=1.7976931348623157e308"))
    fleet_id: Mapped[str]
    status: Mapped[str]
    node_id: Mapped[str]
    position_m: Mapped[list[float]] = mapped_column(JSON)
    yaw_rad: Mapped[float]
    current_job_id: Mapped[str | None]
    available_at_ms: Mapped[int]


class TransportJob(RunRow, Base):
    __tablename__ = "factory_v3_transport_jobs"
    __table_args__ = (
        reference("fleet_id", "fleet"), reference("material_id", "materials"), reference("shipment_leg_id", "shipment_legs"),
        choices("status", "IDLE ASSIGNED EMPTY_APPROACH QUEUED LOADING MOVING UNLOADING RETURNING BLOCKED COMPLETED STRUCTURAL_BLOCKED"), integer("ready_at_ms"), integer("start_ms"), integer("end_ms"), interval(),
        CheckConstraint("fleet_id IS NULL OR equipment_id IS NULL"),
        CheckConstraint("start_ms IS NULL OR start_ms>=ready_at_ms"), CheckConstraint("status!='STRUCTURAL_BLOCKED' OR blocked_resource_id IS NOT NULL"),
        UniqueConstraint("run_id", "id", "fleet_id"),
        CheckConstraint(f"status NOT IN ({','.join(repr(value) for value in sorted(ACTIVE_JOB_STATUSES))}) OR fleet_id IS NOT NULL OR equipment_id IS NOT NULL"),
        Index("factory_v3_one_fleet_job", "run_id", "fleet_id", unique=True, sqlite_where=text(f"status IN ({','.join(repr(value) for value in sorted(ACTIVE_JOB_STATUSES))}) AND fleet_id IS NOT NULL")),
        Index("factory_v3_one_equipment_job", "run_id", "equipment_id", unique=True, sqlite_where=text(f"status IN ({','.join(repr(value) for value in sorted(ACTIVE_JOB_STATUSES))}) AND equipment_id IS NOT NULL")),
        Index("factory_v3_one_material_job", "run_id", "material_id", unique=True, sqlite_where=text(f"status IN ({','.join(repr(value) for value in sorted(ACTIVE_JOB_STATUSES))}) AND material_id IS NOT NULL")),
    )
    fleet_id: Mapped[str | None]
    material_id: Mapped[str | None]
    shipment_leg_id: Mapped[str | None]
    from_node_id: Mapped[str]
    to_node_id: Mapped[str]
    status: Mapped[str]
    ready_at_ms: Mapped[int]
    start_ms: Mapped[int | None]
    end_ms: Mapped[int | None]
    blocked_resource_id: Mapped[str | None]
    equipment_id: Mapped[str | None]


class MovementSegment(RunRow, Base):
    __tablename__ = "factory_v3_movement_segments"
    __table_args__ = (reference("job_id", "transport_jobs"), UniqueConstraint("run_id", "job_id", "ordinal"), integer("ordinal"), integer("start_ms"), integer("end_ms"), interval(), CheckConstraint("json_valid(from_position_m) AND json_array_length(from_position_m)=3"), CheckConstraint("json_valid(to_position_m) AND json_array_length(to_position_m)=3"))
    job_id: Mapped[str]
    ordinal: Mapped[int]
    segment_id: Mapped[str]
    start_ms: Mapped[int]
    end_ms: Mapped[int]
    from_position_m: Mapped[list[float]] = mapped_column(JSON)
    to_position_m: Mapped[list[float]] = mapped_column(JSON)


class ResourceReservation(RunRow, Base):
    __tablename__ = "factory_v3_reservations"
    __table_args__ = (reference("job_id", "transport_jobs"), integer("start_ms"), integer("end_ms"), integer("released_at_ms"), interval())
    resource_id: Mapped[str]
    job_id: Mapped[str]
    start_ms: Mapped[int]
    end_ms: Mapped[int]
    released_at_ms: Mapped[int | None]


class Consist(RunRow, Base):
    __tablename__ = "factory_v3_consists"
    __table_args__ = (reference("locomotive_id", "fleet"), UniqueConstraint("run_id", "locomotive_id"), choices("status", "IDLE MOVING BLOCKED"))
    locomotive_id: Mapped[str]
    status: Mapped[str]


class ConsistMember(RunRow, Base):
    __tablename__ = "factory_v3_consist_members"
    __table_args__ = (reference("consist_id", "consists"), reference("fleet_id", "fleet"), UniqueConstraint("run_id", "fleet_id"), UniqueConstraint("run_id", "consist_id", "ordinal"), integer("ordinal"), CheckConstraint("coupler_distance_m>=0 AND coupler_distance_m<1e308"))
    consist_id: Mapped[str]
    fleet_id: Mapped[str]
    ordinal: Mapped[int]
    coupler_distance_m: Mapped[float]


class Attachment(RunRow, Base):
    __tablename__ = "factory_v3_attachments"
    __table_args__ = (reference("material_id", "materials"), choices("kind", "slot equipment hook vehicle railcar ship customer"), integer("acquired_at_ms"), integer("released_at_ms"), CheckConstraint("released_at_ms IS NULL OR released_at_ms>=acquired_at_ms"), Index("factory_v3_one_current_attachment", "run_id", "material_id", unique=True, sqlite_where=text("released_at_ms IS NULL")))
    material_id: Mapped[str]
    kind: Mapped[str]
    owner_id: Mapped[str]
    socket_id: Mapped[str]
    acquired_at_ms: Mapped[int]
    released_at_ms: Mapped[int | None]


class Shipment(RunRow, Base):
    __tablename__ = "factory_v3_shipments"
    __table_args__ = (reference("order_id", "orders"), choices("mode", "ROAD RAIL SEA"), choices("status", "PLANNED ALLOCATED LOADING DISPATCHED IN_TRANSIT DELIVERED"), integer("capacity_kg", 1))
    order_id: Mapped[str]
    mode: Mapped[str]
    status: Mapped[str]
    capacity_kg: Mapped[int]


class ShipmentLeg(RunRow, Base):
    __tablename__ = "factory_v3_shipment_legs"
    __table_args__ = (reference("shipment_id", "shipments"), UniqueConstraint("run_id", "shipment_id", "ordinal"), integer("ordinal"), choices("mode", "ROAD RAIL SEA"), choices("status", "PLANNED LOADING IN_TRANSIT UNLOADING DELIVERED"), integer("eta_ms"), integer("start_ms"), integer("end_ms"), interval())
    shipment_id: Mapped[str]
    ordinal: Mapped[int]
    mode: Mapped[str]
    from_node_id: Mapped[str]
    to_node_id: Mapped[str]
    status: Mapped[str]
    eta_ms: Mapped[int | None]
    start_ms: Mapped[int | None]
    end_ms: Mapped[int | None]


class ShipmentMaterial(RunRow, Base):
    __tablename__ = "factory_v3_shipment_materials"
    __table_args__ = (reference("shipment_id", "shipments"), reference("material_id", "materials"), CheckConstraint("active IN (0,1)"), Index("factory_v3_one_active_shipment", "run_id", "material_id", unique=True, sqlite_where=text("active=1")))
    shipment_id: Mapped[str]
    material_id: Mapped[str]
    active: Mapped[bool]


class QualityRecord(RunRow, Base):
    __tablename__ = "factory_v3_quality"
    __table_args__ = (reference("material_id", "materials"), reference("event_id", "events"), ForeignKeyConstraint(["run_id", "material_version_id", "material_id"], ["factory_v3_material_versions.run_id", "factory_v3_material_versions.id", "factory_v3_material_versions.material_id"], deferrable=True, initially="DEFERRED"), integer("at_ms"), choices("status", "PENDING PASSED HOLD FAILED"))
    material_id: Mapped[str]
    material_version_id: Mapped[str]
    status: Mapped[str]
    at_ms: Mapped[int]
    event_id: Mapped[str | None]


class FactoryEvent(RunRow, Base):
    __tablename__ = "factory_v3_events"
    __table_args__ = (
        UniqueConstraint("run_id", "sequence"), UniqueConstraint("run_id", "source_id"), integer("sequence", 1), integer("at_ms"),
        choices("event_type", " ".join(get_args(EventType))), CheckConstraint("json_valid(payload) AND json_type(payload)='object'"),
        choices("entity_type", "run order work_order production_lot stock_lot receipt material material_version batch process fleet job attachment shipment shipment_leg quality"),
    )
    sequence: Mapped[int]
    event_type: Mapped[str]
    entity_type: Mapped[str]
    entity_id: Mapped[str]
    at_ms: Mapped[int]
    occurred_at: Mapped[str]
    source_id: Mapped[str]
    payload: Mapped[JsonValue] = mapped_column(JSON, default=dict)


class MassLedgerEntry(RunRow, Base):
    __tablename__ = "factory_v3_mass_ledger"
    __table_args__ = (reference("material_id", "materials"), reference("batch_id", "process_batches"), reference("event_id", "events"), UniqueConstraint("run_id", "source_id"), choices("kind", "OPENING_STOCK EXTERNAL_RECEIPT EXTERNAL_ADDITION BYPRODUCT IRRECOVERABLE_LOSS"), integer("quantity_kg", 1), integer("at_ms"))
    source_id: Mapped[str]
    kind: Mapped[str]
    quantity_kg: Mapped[int]
    at_ms: Mapped[int]
    material_id: Mapped[str | None]
    batch_id: Mapped[str | None]
    event_id: Mapped[str | None]
