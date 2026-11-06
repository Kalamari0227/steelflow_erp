from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, JsonValue, model_validator

from .production_schemas import ProductionSnapshot
from .operations import contracts as operations, projection
from .operations.contracts_v3_core import Speed as CommandSpeed
from .production_schemas import OperationsProduction
from .qa_identity import QAIdentity

ScenarioId = Literal["NORMAL", "DELAY", "RECOVERY"]
Speed = Literal[1, 2, 4]


class Record(BaseModel):
    model_config = ConfigDict(from_attributes=True, frozen=True)


class Customer(Record):
    id: str
    name: str
    country: str


class Order(Record):
    id: str
    customer_id: str
    grade: str
    quantity_kg: int
    due_at: str
    status: str


class Lot(Record):
    id: str
    order_id: str
    line_id: str
    planned_kg: int
    actual_kg: int
    status: str


class Coil(Record):
    id: str
    lot_id: str
    grade: str
    width_mm: int
    thickness_mm: float
    weight_kg: int
    status: str


class Location(Record):
    id: str
    type: str
    name: str
    x: float
    y: float
    z: float


class Inventory(Record):
    coil_id: str
    location_id: str
    availability_status: str


class Shipment(Record):
    id: str
    order_id: str
    mode: str
    etd: str
    eta: str
    status: str


class ShipmentCoil(Record):
    shipment_id: str
    coil_id: str


class OperationEvent(Record):
    id: str
    scenario_id: ScenarioId
    run_id: str
    sequence: int
    entity_type: str
    entity_id: str
    event_type: str
    occurred_at: str
    payload: dict[str, JsonValue]


class Simulation(Record):
    scenario_id: ScenarioId
    run_id: str
    tick: int
    max_tick: int
    simulated_at: str
    playing: bool
    speed: Speed
    tick_seconds: float = Field(default=1, gt=0, allow_inf_nan=False)
    elapsed_ms: int = Field(default=0, ge=0)
    revision: int = Field(default=0, ge=0)
    step_ms: Literal[1000] = 1000


class Kpis(Record):
    total_orders: int
    active_orders: int
    total_mass_kg: int
    produced_kg: int
    in_transit_kg: int
    delivered_kg: int
    at_risk_orders: int
    on_time_percent: float
    throughput_kg: int


class Risk(Record):
    id: str
    order_id: str
    severity: Literal["warning", "critical", "resolved"]
    reason: str
    rule: str
    recommendation: str
    delay_hours: float
    recovered_hours: float


class Scenario(Record):
    id: ScenarioId
    name: str
    description: str


class AIStatus(Record):
    enabled: bool
    available: bool
    provider: str


class LegacyWorld(Record):
    production: ProductionSnapshot
    simulation: Simulation
    kpis: Kpis
    customers: list[Customer]
    orders: list[Order]
    lots: list[Lot]
    coils: list[Coil]
    locations: list[Location]
    inventory: list[Inventory]
    shipments: list[Shipment]
    shipment_coils: list[ShipmentCoil]
    events: list[OperationEvent]
    risks: list[Risk]
    ai: AIStatus


class World(operations.Contract):
    schema_version: Literal[2] = 2
    run: operations.OperationsRun
    work_orders: tuple[operations.WorkOrder, ...]
    materials: tuple[operations.Material, ...]
    material_versions: tuple[operations.MaterialVersion, ...]
    lineage_edges: tuple[operations.MaterialLineageEdge, ...]
    allocations: tuple[operations.MaterialAllocation, ...]
    processes: tuple[operations.ProcessExecution, ...]
    transfers: tuple[operations.Transfer, ...]
    inspections: tuple[operations.Inspection, ...]
    shipments: tuple[operations.OperationsShipment, ...]
    shipment_materials: tuple[operations.ShipmentMaterial, ...]
    mass_movements: tuple[operations.MassMovement, ...]
    events: tuple[operations.OperationEvent, ...]
    mass_balance: operations.MassBalance
    forecast: tuple[operations.OrderForecast, ...]
    recovery: operations.RecoveryComparison | None = None
    orders: tuple[projection.OrderView, ...]
    lots: tuple[projection.LotView, ...]
    production: OperationsProduction
    simulation: Simulation
    kpis: projection.Kpis
    customers: tuple[Customer, ...]
    coils: tuple[projection.CoilView, ...]
    locations: tuple[Location, ...]
    inventory: tuple[Inventory, ...]
    inventory_materials: tuple[operations.Material, ...]
    shipment_coils: tuple[ShipmentCoil, ...]
    risks: tuple[Risk, ...] = ()
    ai: AIStatus

    @model_validator(mode='after')
    def check_operations(self) -> Self:
        data = self.model_dump(include=set(operations.OperationsSnapshot.model_fields))
        data['orders'] = [row.model_dump(include=set(operations.OperationsOrder.model_fields)) for row in self.orders]
        data['lots'] = [row.model_dump(include=set(operations.OperationsLot.model_fields)) for row in self.lots]
        operations.OperationsSnapshot.model_validate(data)
        return self


class CommandWorld(World):
    applied_revision: int
    replayed: bool


class CommandRequest(operations.Contract):
    run_id: operations.RunKey | None = None
    expected_revision: operations.NonNegative | None = None
    command_id: operations.Id | None = None
    steps: int | None = Field(default=None, ge=1, le=48, strict=True)
    speed: CommandSpeed | None = None


class MaterialDetail(projection.MaterialView):
    location: Location


class OrderDetail(Record):
    order: projection.OrderView
    customer: Customer
    lots: list[projection.LotView]
    coils: list[projection.CoilView]
    shipments: list[operations.OperationsShipment]
    work_orders: list[operations.WorkOrder]
    materials: list[operations.Material]


class CoilDetail(Record):
    coil: projection.CoilView
    lot: projection.LotView
    order: projection.OrderView
    customer: Customer
    location: Location
    shipment: operations.OperationsShipment | None


class PlayRequest(Record):
    speed: Speed = 1


class StepRequest(Record):
    steps: int = Field(default=1, ge=1, le=48, strict=True)


class Health(Record):
    status: Literal["ok"] = "ok"
    data: Literal["synthetic"] = "synthetic"
    qa: QAIdentity | None = None
