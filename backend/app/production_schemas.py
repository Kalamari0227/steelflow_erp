"""Read-only production contracts; masses are separate from logistics fixtures."""
from typing import Literal

from pydantic import BaseModel, ConfigDict
from .operations import contracts as c
from .operations.projection import ProductionView

StageId = Literal["ironmaking", "steelmaking", "casting", "hot_rolling", "cold_rolling", "coating", "finishing", "stock"]
Product = Literal["SLAB", "BLOOM", "BILLET", "HR", "CR", "GI", "GA", "EG", "HGI"]
Status = Literal["queued", "running", "completed"]
VehicleKind = Literal["flatbed_truck", "hot_metal_car", "ladle_car"]


class ProductionRecord(BaseModel):
    model_config = ConfigDict(frozen=True)


class ProductionStep(ProductionRecord):
    id: str
    stage_id: StageId
    name: str
    equipment_id: str
    start_tick: int
    end_tick: int
    status: Status


class MaterialVersion(ProductionRecord):
    id: str
    parent_id: str | None
    form: str
    role: Literal["feedstock", "sale_product"]
    stage_id: StageId
    created_tick: int


class ProductionTransport(ProductionRecord):
    id: str
    batch_id: str
    vehicle_id: str
    vehicle_kind: VehicleKind
    material_id: str
    material_form: str
    mass_kg: int
    from_stage: StageId
    to_stage: StageId
    start_tick: int
    end_tick: int
    status: Literal["queued", "in_transit", "completed"]


class ProductionBatch(ProductionRecord):
    id: str
    source_fixture_id: str
    product: Product
    mass_kg: int
    material_id: str
    parent_material_id: str | None = None
    material_history: list[MaterialVersion]
    material_form: str
    material_role: Literal["feedstock", "sale_product"]
    current_stage: StageId
    current_location_id: str
    active_transport_id: str | None
    current_step: str
    equipment_id: str
    status: Literal["queued", "running", "in_transit", "completed"]
    route: list[StageId]
    route_progress: float
    steps: list[ProductionStep]


class ProductionStage(ProductionRecord):
    id: StageId
    name: str
    equipment_ids: list[str]
    substeps: list[str]
    queued_count: int
    running_count: int
    completed_count: int
    queued_mass_kg: int
    running_mass_kg: int
    completed_mass_kg: int
    batch_ids: list[str]


class ProductionSnapshot(ProductionRecord):
    tick: int
    scenario_id: Literal["NORMAL", "DELAY", "RECOVERY"]
    data_scope: Literal["synthetic_production_only"] = "synthetic_production_only"
    total_mass_kg: int
    completed_mass_kg: int
    batches: list[ProductionBatch]
    stages: list[ProductionStage]
    transports: list[ProductionTransport]


class ProductionStageDetail(ProductionRecord):
    stage: ProductionStage
    batches: list[ProductionBatch]


class OperationsBatch(c.Contract):
    id: c.Id
    run_id: c.RunKey
    order_id: c.Id
    work_order_id: c.Id
    lot_id: c.Id
    product: c.ProductId
    material_id: c.Id
    mass_kg: c.PositiveKg
    material_form: c.MaterialForm
    current_location_id: c.Id
    route: tuple[str, ...]
    steps: tuple[c.ProcessExecution, ...]


class OperationsStage(c.Contract):
    id: str
    equipment_ids: tuple[str, ...]
    process_ids: tuple[c.Id, ...]
    batch_ids: tuple[c.Id, ...]


class OperationsProduction(ProductionView):
    batches: tuple[OperationsBatch, ...]
    stages: tuple[OperationsStage, ...]


class OperationsStageDetail(c.Contract):
    stage: OperationsStage
    batches: tuple[OperationsBatch, ...]
