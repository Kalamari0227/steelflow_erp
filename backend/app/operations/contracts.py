"""One authoritative operations world; immutable rows and explicit transition seams.

This intentionally central contract module is shared by independently owned domain
modules. SimulationModel is the mutable workspace; boundary rows/events stay frozen.
"""
# noqa: SIZE_OK -- T1 owns one shared contract file; explicit cross-domain schema declarations stay together.
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Annotated, Final, Literal, NewType, Protocol, Self

from pydantic import AfterValidator, AwareDatetime, BaseModel, ConfigDict, Field, StrictBool, model_validator

RunId = NewType("RunId", str)
EntityId = NewType("EntityId", str)
Kilograms = NewType("Kilograms", int)
Milliseconds = NewType("Milliseconds", int)
NonNegative = Annotated[int, Field(strict=True, ge=0, le=9007199254740991)]
Positive = Annotated[int, Field(strict=True, gt=0, le=9007199254740991)]
Kg = Annotated[Kilograms, Field(strict=True, ge=0, le=9007199254740991)]
PositiveKg = Annotated[Kilograms, Field(strict=True, gt=0, le=9007199254740991)]
Ms = Annotated[Milliseconds, Field(strict=True, ge=0, le=9007199254740991)]
Id = Annotated[EntityId, Field(min_length=1, strict=True)]
RunKey = Annotated[RunId, Field(min_length=1, strict=True)]
Dimension = Annotated[float, Field(gt=0, allow_inf_nan=False, strict=True)]
ScenarioId = Literal["NORMAL", "DELAY", "RECOVERY"]
ProductId = Literal["slab", "bloom", "billet", "hr", "plate", "wire", "cr", "gi", "ga", "hgi", "eg", "go", "ngo", "sts-hr", "sts-cr", "sts-plate", "ti-hr", "ti-cr", "ti-sheet", "ti-plate"]
MaterialForm = Literal["ORE", "HOT_METAL", "LIQUID_STEEL", "SCRAP", "SLAB", "BLOOM", "BILLET", "HOT_SLAB", "HOT_BLOOM", "HOT_BILLET", "HOT_STRIP", "HOT_PLATE", "STRIP", "THIN_STRIP", "COATED_STRIP", "HR_COIL", "CR_COIL", "GI_COIL", "GA_COIL", "HGI_COIL", "EG_COIL", "GO_COIL", "NGO_COIL", "WIRE", "WIRE_COIL", "PLATE", "STS_HR_COIL", "STS_CR_COIL", "STS_PLATE", "TI_INGOT", "TI_SLAB", "TI_HR_COIL", "TI_CR_COIL", "TI_SHEET", "TI_PLATE"]
ProcessStatus = Literal["QUEUED", "RUNNING", "BLOCKED", "COMPLETED"]
TransferStatus = Literal["WAITING", "LOADING", "IN_TRANSIT", "UNLOADING", "ARRIVED"]
TransferMode = Literal["roller", "flatbed", "hot_metal_car", "ladle_car"]
QualityStatus = Literal["PENDING", "PASSED", "HOLD", "FAILED"]
AvailabilityStatus = Literal["WIP", "QUARANTINED", "AVAILABLE", "RESERVED", "SHIPPED", "CONSUMED"]
ShipmentStatus = Literal["PLANNED", "ALLOCATED", "LOADING", "LOADED", "DISPATCHED", "AT_PORT", "IN_TRANSIT", "DELIVERED"]
OrderStatus = Literal["RECEIVED", "PLANNED", "IN_PRODUCTION", "READY", "PARTIALLY_DISPATCHED", "DISPATCHED", "PARTIALLY_DELIVERED", "DELIVERED"]
EventType = Literal["PLAN_RELEASED", "WORK_ORDER_RELEASED", "MATERIAL_ALLOCATED", "PROCESS_STARTED", "PROCESS_BLOCKED", "PROCESS_COMPLETED", "MATERIAL_TRANSFORMED", "MATERIAL_SPLIT", "TRANSFER_STARTED", "TRANSFER_LOADING", "TRANSFER_DEPARTED", "TRANSFER_UNLOADING", "TRANSFER_ARRIVED", "INSPECTION_STARTED", "INSPECTION_PASSED", "INSPECTION_HELD", "INSPECTION_FAILED", "PACKAGING_STARTED", "PACKAGING_COMPLETED", "MATERIAL_AVAILABLE", "SHIPMENT_ALLOCATED", "SHIPMENT_LOADING", "MATERIAL_LOADED", "SHIPMENT_LOADED", "SHIPMENT_DISPATCHED", "SHIPMENT_AT_PORT", "SHIPMENT_SAILING", "SHIPMENT_DELIVERED", "ORDER_DELIVERED", "RESOURCE_DOWN", "RESOURCE_RESTORED", "RECOVERY_ROUTED"]
EntityKind = Literal["run", "order", "work_order", "lot", "material", "process", "transfer", "inspection", "shipment", "resource"]
EPOCH_AT: Final = datetime.fromisoformat("2026-10-30T00:00:00+00:00")
STEP_MS: Final = 1000


@dataclass(frozen=True, slots=True)
class ContractViolation(ValueError):
    code: str
    detail: str

    def __str__(self) -> str:
        return f"{self.code}: {self.detail}"


def utc_only(value: datetime) -> datetime:
    """Reject non-UTC offsets instead of silently mixing business and local time."""
    if value.utcoffset() != timedelta(0):
        raise ContractViolation("utc_required", value.isoformat())
    return value


UTCDateTime = Annotated[AwareDatetime, AfterValidator(utc_only)]


class Contract(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class RunEntity(Contract):
    run_id: RunKey
    id: Id


class OperationsRun(Contract):
    id: RunKey
    fixture_version: Literal["erp-v1"] = "erp-v1"
    seed: NonNegative = 30
    scenario_id: ScenarioId
    elapsed_ms: Ms
    duration_ms: Positive
    revision: NonNegative
    event_sequence: NonNegative
    playing: StrictBool
    speed: Literal[1, 2, 4]
    epoch_at: UTCDateTime
    started_at: UTCDateTime
    plan_revision: NonNegative

    @model_validator(mode="after")
    def check_clock(self) -> Self:
        if self.elapsed_ms > self.duration_ms or self.epoch_at != EPOCH_AT:
            raise ContractViolation("clock", "elapsed exceeds duration or epoch is not the fixed business epoch")
        return self


class CurrentRun(Contract):
    id: Literal[1] = 1
    run_id: RunKey


class OrderPlan(RunEntity):
    customer_id: Id
    product_id: ProductId
    grade: str
    width_mm: Dimension | None = None
    thickness_mm: Dimension | None = None
    quantity_kg: PositiveKg
    due_at: UTCDateTime | None = None


class OperationsOrder(OrderPlan):
    due_at: UTCDateTime


class WorkOrder(RunEntity):
    order_id: Id
    route_id: Id
    route_version: Positive
    planned_kg: PositiveKg
    status: Literal["PLANNED", "RELEASED", "COMPLETED"] = "PLANNED"


class OperationsLot(RunEntity):
    work_order_id: Id
    planned_kg: PositiveKg


class Material(RunEntity):
    lot_id: Id
    lineage_id: Id
    current_version_id: Id
    form: MaterialForm
    weight_kg: PositiveKg
    location_id: Id
    quality_status: QualityStatus
    availability_status: AvailabilityStatus
    active: StrictBool

    @model_validator(mode="after")
    def check_consumed(self) -> Self:
        if self.active == (self.availability_status == "CONSUMED"):
            raise ContractViolation("consumed", "only consumed materials are inactive")
        return self


class MaterialVersion(RunEntity):
    material_id: Id
    ordinal: Positive
    parent_version_id: Id | None
    form: MaterialForm
    weight_kg: PositiveKg
    cause_event_id: Id | None


class MaterialLineageEdge(RunEntity):
    parent_material_id: Id
    child_material_id: Id
    process_id: Id
    transferred_kg: PositiveKg


class MaterialAllocation(RunEntity):
    order_id: Id
    work_order_id: Id
    material_id: Id
    final_planned_kg: PositiveKg
    active: StrictBool


class ProcessExecution(RunEntity):
    material_id: Id
    route_step_id: Id
    source_step_id: Id
    step_ordinal: NonNegative
    equipment_id: Id
    predecessor_id: Id | None
    status: ProcessStatus
    planned_duration_ms: Positive
    ready_at_ms: Ms = Milliseconds(0)
    start_ms: Ms | None = None
    end_ms: Ms | None = None
    input_form: MaterialForm
    output_form: MaterialForm
    additions_kg: Kg = Kilograms(0)
    loss_kg: Kg = Kilograms(0)
    split_count: Literal[1, 2] = 1
    blocked_reason: str | None = None

    @model_validator(mode="after")
    def check_times(self) -> Self:
        if self.start_ms is not None and self.end_ms is not None and self.end_ms <= self.start_ms:
            raise ContractViolation("process_time", "end must follow start")
        if self.status in {"RUNNING", "COMPLETED"} and (self.start_ms is None or self.end_ms is None):
            raise ContractViolation("process_time", "running/completed process requires a time window")
        return self


class Transfer(RunEntity):
    material_id: Id
    from_location_id: Id
    to_location_id: Id
    mode: TransferMode
    vehicle_id: Id | None = None
    crane_id: Id | None = None
    status: TransferStatus
    phase_start_ms: Ms | None = None
    phase_end_ms: Ms | None = None
    capacity_kg: PositiveKg
    process_id: Id | None = None
    travel_duration_ms: Positive = 3000

    @model_validator(mode="after")
    def check_carrier(self) -> Self:
        if self.mode != "roller" and self.vehicle_id is None:
            raise ContractViolation("carrier_required", self.id)
        if self.phase_start_ms is not None and self.phase_end_ms is not None and self.phase_end_ms <= self.phase_start_ms:
            raise ContractViolation("transfer_time", "phase must have positive duration")
        return self


class Inspection(RunEntity):
    material_id: Id
    status: QualityStatus
    inspected_version_id: Id
    reason: str | None = None
    release_event_id: Id | None = None
    start_ms: Ms | None = None
    end_ms: Ms | None = None
    packaging_end_ms: Ms | None = None


class OperationsShipment(RunEntity):
    order_id: Id
    mode: Literal["SEA", "ROAD"] = "SEA"
    status: ShipmentStatus
    location_id: Id
    capacity_kg: PositiveKg
    etd_at: UTCDateTime | None = None
    eta_at: UTCDateTime | None = None
    phase_start_ms: Ms | None = None
    phase_end_ms: Ms | None = None
    delivered_at: UTCDateTime | None = None


class ShipmentMaterial(RunEntity):
    shipment_id: Id
    material_id: Id
    active: StrictBool = True
    loaded: StrictBool = False


class MassMovement(RunEntity):
    cause_event_id: Id
    process_id: Id
    input_material_ids: tuple[Id, ...]
    output_material_ids: tuple[Id, ...]
    input_kg: Kg
    output_kg: Kg
    additions_kg: Kg
    loss_kg: Kg

    @model_validator(mode="after")
    def check_balance(self) -> Self:
        if self.input_kg + self.additions_kg != self.output_kg + self.loss_kg:
            raise ContractViolation("mass_balance", self.id)
        return self


class OperationEvent(RunEntity):
    sequence: Positive
    event_type: EventType
    entity_type: EntityKind
    entity_id: Id
    at_ms: Ms
    occurred_at: UTCDateTime
    recorded_at: UTCDateTime | None = None
    material_id: Id | None = None
    order_id: Id | None = None
    process_id: Id | None = None
    from_location_id: Id | None = None
    to_location_id: Id | None = None
    reason: str | None = None


class MassBalance(Contract):
    initial_kg: Kg
    additions_kg: Kg
    active_kg: Kg
    loss_kg: Kg

    @model_validator(mode="after")
    def check_balance(self) -> Self:
        if self.initial_kg + self.additions_kg != self.active_kg + self.loss_kg:
            raise ContractViolation("mass_balance", "initial + additions != active + loss")
        return self


class OrderForecast(Contract):
    order_id: Id
    status: Literal["ON_TIME", "LATE", "BLOCKED"]
    eta_at: UTCDateTime | None
    completion_ms: Ms | None
    reason: str | None = None
    plan_revision: NonNegative


class ResourceSpec(Contract):
    id: Id
    location_id: Id
    capacity_kg: PositiveKg
    parallel_capacity: Positive = 1
    compatible_forms: tuple[MaterialForm, ...]
    compatible_grades: tuple[str, ...] = ()
    min_width_mm: Dimension | None = None
    max_width_mm: Dimension | None = None
    reserve: StrictBool = False
    available_at_ms: Ms = Milliseconds(0)
    unavailable_from_ms: Ms | None = None
    unavailable_until_ms: Ms | None = None
    reserved_by: Id | None = None


class RecoveryOrder(Contract):
    order_id: Id
    delay_eta_at: UTCDateTime | None
    recovery_eta_at: UTCDateTime | None
    delay_completion_ms: Ms | None
    recovery_completion_ms: Ms | None
    improvement_ms: Annotated[int, Field(strict=True)]

    @model_validator(mode='after')
    def check_comparison(self) -> Self:
        expected = self.delay_completion_ms-self.recovery_completion_ms if self.delay_completion_ms is not None and self.recovery_completion_ms is not None else 0
        if self.improvement_ms != expected:
            raise ContractViolation('recovery_difference', self.order_id)
        if (self.delay_eta_at is None) != (self.delay_completion_ms is None) or (self.recovery_eta_at is None) != (self.recovery_completion_ms is None):
            raise ContractViolation('recovery_eta', self.order_id)
        return self


class RecoveryComparison(Contract):
    basis: Literal['INITIAL_PLAN'] = 'INITIAL_PLAN'
    horizon_ms: Literal[3600000] = 3600000
    baseline_hash: str
    plan_revision: NonNegative
    orders: tuple[RecoveryOrder, ...]
    routed_material_ids: tuple[Id, ...]
    outage_ms: Ms | None
    roller_duration_ms: tuple[Ms, ...]
    current_available: StrictBool
    current_reason: str
    recommendation: Literal['NO_BENEFIT', 'UNAVAILABLE', 'REVIEW_BENEFIT']


class Collections(Contract):
    work_orders: tuple[WorkOrder, ...] = ()
    lots: tuple[OperationsLot, ...] = ()
    materials: tuple[Material, ...] = ()
    material_versions: tuple[MaterialVersion, ...] = ()
    lineage_edges: tuple[MaterialLineageEdge, ...] = ()
    allocations: tuple[MaterialAllocation, ...] = ()
    processes: tuple[ProcessExecution, ...] = ()
    transfers: tuple[Transfer, ...] = ()
    inspections: tuple[Inspection, ...] = ()
    shipments: tuple[OperationsShipment, ...] = ()
    shipment_materials: tuple[ShipmentMaterial, ...] = ()
    mass_movements: tuple[MassMovement, ...] = ()


class PlanSeed(Collections):
    """Pure fixture plan; nullable due dates never cross the persisted world boundary."""
    fixture_version: Literal["erp-v1"] = "erp-v1"
    seed: NonNegative = 30
    run_id: RunKey
    orders: tuple[OrderPlan, ...]
    resources: tuple[ResourceSpec, ...] = ()

    @model_validator(mode="after")
    def check_scope(self) -> Self:
        groups = (self.orders, self.work_orders, self.lots, self.materials, self.material_versions,
                  self.lineage_edges, self.allocations, self.processes, self.transfers, self.inspections,
                  self.shipments, self.shipment_materials, self.mass_movements)
        for group in groups:
            if any(row.run_id != self.run_id for row in group) or len({row.id for row in group}) != len(group):
                raise ContractViolation("plan_scope", "cross-run reference or duplicate ID")
        return self


class OperationsSnapshot(Collections):
    """Operations payload projected into the existing /api/v1/world by T11."""
    schema_version: Literal[2] = 2
    run: OperationsRun
    orders: tuple[OperationsOrder, ...]
    events: tuple[OperationEvent, ...] = ()
    mass_balance: MassBalance
    forecast: tuple[OrderForecast, ...] = ()

    @model_validator(mode="after")
    def check_relations(self) -> Self:
        """Validate run-scoped identity and the links that give a snapshot meaning."""
        groups = (self.orders, self.work_orders, self.lots, self.materials, self.material_versions,
                  self.lineage_edges, self.allocations, self.processes, self.transfers, self.inspections,
                  self.shipments, self.shipment_materials, self.mass_movements, self.events)
        for group in groups:
            if len({row.id for row in group}) != len(group):
                raise ContractViolation("duplicate_id", "duplicate in collection")
            if any(row.run_id != self.run.id for row in group):
                raise ContractViolation("cross_run", "every row must belong to snapshot run")
        orders = {row.id: row for row in self.orders}
        works = {row.id: row for row in self.work_orders}
        lots = {row.id: row for row in self.lots}
        materials = {row.id: row for row in self.materials}
        versions = {row.id: row for row in self.material_versions}
        processes = {row.id: row for row in self.processes}
        shipments = {row.id: row for row in self.shipments}
        events = {row.id: row for row in self.events}
        links = [(row.order_id, orders) for row in self.work_orders]
        links += [(row.work_order_id, works) for row in self.lots]
        links += [(row.lot_id, lots) for row in self.materials]
        links += [(row.current_version_id, versions) for row in self.materials]
        links += [(row.material_id, materials) for row in self.material_versions + self.processes + self.transfers + self.inspections]
        links += [(row.parent_version_id, versions) for row in self.material_versions if row.parent_version_id is not None]
        links += [(row.predecessor_id, processes) for row in self.processes if row.predecessor_id is not None]
        links += [(row.order_id, orders) for row in self.shipments]
        links += [(row.inspected_version_id, versions) for row in self.inspections]
        for row in self.allocations:
            links.extend(((row.order_id, orders), (row.work_order_id, works), (row.material_id, materials)))
        for row in self.shipment_materials:
            links.extend(((row.shipment_id, shipments), (row.material_id, materials)))
        for row in self.lineage_edges:
            links.extend(((row.parent_material_id, materials), (row.child_material_id, materials), (row.process_id, processes)))
        if any(key not in target for key, target in links):
            raise ContractViolation("missing_reference", "reference target is absent")
        for material in self.materials:
            version = versions[material.current_version_id]
            if (version.material_id, version.form, version.weight_kg) != (material.id, material.form, material.weight_kg):
                raise ContractViolation("current_version", material.id)
        ordinals = {(row.material_id, row.ordinal) for row in self.material_versions}
        if len(ordinals) != len(self.material_versions):
            raise ContractViolation("version_ordinal", "duplicate version ordinal")
        active_allocations = [row.material_id for row in self.allocations if row.active]
        active_transfers = [row.material_id for row in self.transfers if row.status != "ARRIVED"]
        active_shipments = [row.material_id for row in self.shipment_materials if row.active]
        if any(len(ids) != len(set(ids)) for ids in (active_allocations, active_transfers, active_shipments)):
            raise ContractViolation("active_assignment", "material has multiple active owners")
        for allocation in self.allocations:
            work = works[allocation.work_order_id]
            material = materials[allocation.material_id]
            if work.order_id != allocation.order_id or lots[material.lot_id].work_order_id != work.id:
                raise ContractViolation("allocation_order", allocation.id)
            if allocation.active and not material.active:
                raise ContractViolation("consumed_allocation", allocation.id)
        for assignment in self.shipment_materials:
            material = materials[assignment.material_id]
            order_id = works[lots[material.lot_id].work_order_id].order_id
            if shipments[assignment.shipment_id].order_id != order_id:
                raise ContractViolation("shipment_order", assignment.id)
        for inspection in self.inspections:
            if versions[inspection.inspected_version_id].material_id != inspection.material_id:
                raise ContractViolation("inspection_version", inspection.id)
        pairs = {(row.parent_material_id, row.child_material_id) for row in self.lineage_edges}
        if len(pairs) != len(self.lineage_edges):
            raise ContractViolation("lineage_duplicate", "duplicate parent-child edge")
        adjacency: dict[EntityId, set[EntityId]] = {}
        for edge in self.lineage_edges:
            adjacency.setdefault(edge.parent_material_id, set()).add(edge.child_material_id)
            if materials[edge.parent_material_id].active:
                raise ContractViolation("split_parent", edge.parent_material_id)
        for origin in adjacency:
            pending = list(adjacency[origin])
            visited: set[EntityId] = set()
            while pending:
                node = pending.pop()
                if node == origin:
                    raise ContractViolation("lineage_cycle", origin)
                if node not in visited:
                    visited.add(node)
                    pending.extend(adjacency.get(node, set()))
        for movement in self.mass_movements:
            if movement.process_id not in processes or movement.cause_event_id not in events or any(key not in materials for key in movement.input_material_ids + movement.output_material_ids):
                raise ContractViolation("mass_reference", movement.id)
        if len({row.process_id for row in self.mass_movements}) != len(self.mass_movements):
            raise ContractViolation("mass_process", "one mass movement per completed process")
        if sum(row.weight_kg for row in self.materials if row.active) != self.mass_balance.active_kg:
            raise ContractViolation("active_mass", "mass balance must count active materials exactly once")
        return self


class SimulationCommand(Contract):
    action: Literal["play", "pause", "reset", "step", "speed", "scenario"]
    run_id: RunKey | None = None
    expected_revision: NonNegative | None = None
    command_id: Id | None = None
    steps: Annotated[int, Field(strict=True, ge=1, le=48)] | None = None
    speed: Literal[1, 2, 4] | None = None
    scenario_id: ScenarioId | None = None

    @model_validator(mode="after")
    def check_action_payload(self) -> Self:
        present = (self.steps is not None, self.speed is not None, self.scenario_id is not None)
        allowed = {"step": (True, False, False), "speed": (False, True, False), "scenario": (False, False, True),
                   "play": (False, self.speed is not None, False), "pause": (False, False, False), "reset": (False, False, False)}
        if self.action == "step" and self.steps is None and present == (False, False, False):
            return self
        if present != allowed[self.action]:
            raise ContractViolation("command_payload", self.action)
        return self


class CommandReceipt(Contract):
    run_id: RunKey
    command_id: Id
    action: Literal["play", "pause", "reset", "step", "speed", "scenario"]
    payload_digest: Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
    applied_revision: NonNegative


class TransitionDelta(Collections):
    """Immutable upserts and append-only events from one boundary, applied atomically.

    Collections contain changed rows only. Consumed/retired rows are upserts, never
    deletions. Events are already ordered; the service supplies recorded_at on commit.
    """
    orders: tuple[OperationsOrder, ...] = ()
    events: tuple[OperationEvent, ...] = ()
    resources: tuple[ResourceSpec, ...] = ()


@dataclass(slots=True)  # noqa: MUTABLE_OK
class SimulationModel:
    """Owned mutable workspace: clone before advancing; replace frozen rows by ID.

    No database/session/clock dependency. Input models must never be mutated by a
    transition; only the returned clone may change. Resource reservations live here.
    """
    run: OperationsRun
    orders: dict[EntityId, OperationsOrder] = field(default_factory=dict)
    work_orders: dict[EntityId, WorkOrder] = field(default_factory=dict)
    lots: dict[EntityId, OperationsLot] = field(default_factory=dict)
    materials: dict[EntityId, Material] = field(default_factory=dict)
    material_versions: dict[EntityId, MaterialVersion] = field(default_factory=dict)
    lineage_edges: dict[EntityId, MaterialLineageEdge] = field(default_factory=dict)
    allocations: dict[EntityId, MaterialAllocation] = field(default_factory=dict)
    processes: dict[EntityId, ProcessExecution] = field(default_factory=dict)
    transfers: dict[EntityId, Transfer] = field(default_factory=dict)
    inspections: dict[EntityId, Inspection] = field(default_factory=dict)
    shipments: dict[EntityId, OperationsShipment] = field(default_factory=dict)
    shipment_materials: dict[EntityId, ShipmentMaterial] = field(default_factory=dict)
    mass_movements: dict[EntityId, MassMovement] = field(default_factory=dict)
    events: dict[EntityId, OperationEvent] = field(default_factory=dict)
    resources: dict[EntityId, ResourceSpec] = field(default_factory=dict)

    def clone(self) -> Self:
        """Copy mutable collections; sharing frozen row values is safe."""
        return type(self)(run=self.run, orders=self.orders.copy(), work_orders=self.work_orders.copy(),
                          lots=self.lots.copy(), materials=self.materials.copy(), material_versions=self.material_versions.copy(),
                          lineage_edges=self.lineage_edges.copy(), allocations=self.allocations.copy(), processes=self.processes.copy(),
                          transfers=self.transfers.copy(), inspections=self.inspections.copy(), shipments=self.shipments.copy(),
                          shipment_materials=self.shipment_materials.copy(), mass_movements=self.mass_movements.copy(),
                          events=self.events.copy(), resources=self.resources.copy())

    @classmethod
    def from_snapshot(cls, snapshot: OperationsSnapshot, resources: tuple[ResourceSpec, ...] = ()) -> Self:
        """Build a transition workspace from a validated boundary snapshot."""
        return cls(run=snapshot.run, orders={row.id: row for row in snapshot.orders},
                   work_orders={row.id: row for row in snapshot.work_orders}, lots={row.id: row for row in snapshot.lots},
                   materials={row.id: row for row in snapshot.materials}, material_versions={row.id: row for row in snapshot.material_versions},
                   lineage_edges={row.id: row for row in snapshot.lineage_edges}, allocations={row.id: row for row in snapshot.allocations},
                   processes={row.id: row for row in snapshot.processes}, transfers={row.id: row for row in snapshot.transfers},
                   inspections={row.id: row for row in snapshot.inspections}, shipments={row.id: row for row in snapshot.shipments},
                   shipment_materials={row.id: row for row in snapshot.shipment_materials}, mass_movements={row.id: row for row in snapshot.mass_movements},
                   events={row.id: row for row in snapshot.events}, resources={row.id: row for row in resources})


@dataclass(frozen=True, slots=True)
class TransitionResult:
    model: SimulationModel
    delta: TransitionDelta


class TransportTransition(Protocol):
    def __call__(self, model: SimulationModel, transfer_id: EntityId, at_ms: Milliseconds) -> TransitionResult: ...


class FulfillmentTransition(Protocol):
    def __call__(self, model: SimulationModel, entity_id: EntityId, at_ms: Milliseconds) -> TransitionResult: ...


class NextBoundary(Protocol):
    def __call__(self, model: SimulationModel) -> Milliseconds | None: ...


class ReadyTransfers(Protocol):
    def __call__(self, model: SimulationModel) -> tuple[EntityId, ...]: ...
