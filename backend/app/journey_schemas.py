from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class JourneyModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", from_attributes=True)


class ProductStep(JourneyModel):
    id: str
    name: str
    equipment_kind: str
    duration_ms: int = Field(gt=0, multiple_of=100)
    input_form: str
    output_form: str
    description: str


class ProductDefinition(JourneyModel):
    id: str
    family: str
    name: str
    description: str
    source_url: str
    source_title: str
    input_form: str
    output_form: str
    mass_kg: int = Field(gt=0)
    steps: tuple[ProductStep, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def continuous_material(self) -> "ProductDefinition":
        ids = [step.id for step in self.steps]
        if len(ids) != len(set(ids)):
            raise InvalidProductRoute(self.id, "duplicate step IDs")
        forms = [self.input_form, *(step.output_form for step in self.steps)]
        if any(step.input_form != forms[index] for index, step in enumerate(self.steps)) or forms[-1] != self.output_form:
            raise InvalidProductRoute(self.id, "discontinuous material forms")
        return self


class InvalidProductRoute(ValueError):
    def __init__(self, product_id: str, reason: str) -> None:
        super().__init__(f"Invalid journey {product_id}: {reason}")


class Products(JourneyModel):
    products: tuple[ProductDefinition, ...]


class MaterialVersion(JourneyModel):
    version_id: str
    parent_version_id: str | None
    form: str
    step_id: str
    at_ms: int


class Material(JourneyModel):
    lineage_id: str
    version_id: str
    parent_version_id: str | None
    form: str
    role: Literal["feedstock", "sale_product"]
    location_id: str
    mass_kg: int


class JourneySnapshot(JourneyModel):
    data_scope: Literal["synthetic_product_journey"] = "synthetic_product_journey"
    run_id: str
    revision: int
    product_id: str
    playing: bool
    speed: Literal[1, 2, 4]
    elapsed_ms: int
    duration_ms: int
    active_step_id: str
    step_elapsed_ms: int
    step_duration_ms: int
    completed: bool
    material: Material
    history: tuple[MaterialVersion, ...]


class SelectRequest(JourneyModel):
    product_id: str = Field(min_length=1)


class SpeedRequest(JourneyModel):
    speed: Literal[1, 2, 4]


class JourneyEvent(JourneyModel):
    id: str
    run_id: str
    product_id: str
    sequence: int
    event_type: str
    step_id: str
    elapsed_ms: int
    occurred_at: str
