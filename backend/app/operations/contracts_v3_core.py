"""Strict shared scalar contracts for schema three, independent of legacy runtime."""
from dataclasses import dataclass
from datetime import datetime
import re
from typing import Annotated, Final, Literal, NewType

from pydantic import AfterValidator, AwareDatetime, BaseModel, BeforeValidator, ConfigDict, Field, JsonValue, PlainSerializer, WithJsonSchema
from pydantic_core import PydanticCustomError

from .time_adapter_v3 import MAX_SIM_MS, canonical_utc, utc_only

MAX_SAFE_INTEGER: Final = 9007199254740991
RunId = NewType("RunId", str)
EntityId = NewType("EntityId", str)
Kilograms = NewType("Kilograms", int)
Milliseconds = NewType("Milliseconds", int)
Id = Annotated[EntityId, Field(strict=True, min_length=1)]
RunKey = Annotated[RunId, Field(strict=True, min_length=1)]
NonNegative = Annotated[int, Field(strict=True, ge=0, le=MAX_SAFE_INTEGER)]
Positive = Annotated[int, Field(strict=True, gt=0, le=MAX_SAFE_INTEGER)]
Kg = Annotated[Kilograms, Field(strict=True, ge=0, le=MAX_SAFE_INTEGER)]
PositiveKg = Annotated[Kilograms, Field(strict=True, gt=0, le=MAX_SAFE_INTEGER)]
Ms = Annotated[Milliseconds, Field(strict=True, ge=0, le=MAX_SIM_MS)]
Duration = Annotated[Milliseconds, Field(strict=True, gt=0, le=MAX_SIM_MS)]
Dimension = Annotated[float, Field(strict=True, gt=0, allow_inf_nan=False)]
Finite = Annotated[float, Field(strict=True, allow_inf_nan=False)]
Distance = Annotated[float, Field(strict=True, ge=0, allow_inf_nan=False)]
Digest = Annotated[str, Field(strict=True, pattern=r"^[0-9a-f]{64}$")]
Text = Annotated[str, Field(strict=True, min_length=1)]
UTC_INPUT_PATTERN: Final = r"^(?!0000)[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(?:\.[0-9]{1,3}0{0,3})?(?:Z|\+00:00)(?![\s\S])"
UTC_OUTPUT_PATTERN: Final = r"^(?!0000)[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}\.[0-9]{3}Z(?![\s\S])"


def utc_input(value: JsonValue | datetime) -> str | datetime:
    """Reject lossy coercions before datetime parsing while retaining internal values."""
    match value:
        case datetime():
            return value
        case str() if re.fullmatch(UTC_INPUT_PATTERN, value):
            return value
        case _:
            # This open input boundary rejects unsupported Python objects as well as JSON.
            raise PydanticCustomError("utc_input", "UTC string with exact millisecond precision required")


UTCDateTime = Annotated[
    AwareDatetime, BeforeValidator(utc_input), AfterValidator(utc_only),
    PlainSerializer(canonical_utc, return_type=str, when_used="json"),
    WithJsonSchema({"type": "string", "format": "date-time", "pattern": UTC_INPUT_PATTERN}, mode="validation"),
    WithJsonSchema({"type": "string", "format": "date-time", "pattern": UTC_OUTPUT_PATTERN}, mode="serialization"),
]
ScenarioId = Literal["NORMAL", "DELAY", "RECOVERY"]
ProductId = Literal["slab", "bloom", "billet", "hr", "plate", "wire", "cr", "gi", "ga", "hgi", "eg", "go", "ngo", "sts-hr", "sts-cr", "sts-plate", "ti-hr", "ti-cr", "ti-sheet", "ti-plate"]
FleetKind = Literal["truck", "carrier", "forklift", "torpedo", "ladle", "locomotive", "railcar", "ship"]
FleetMode = Literal["road", "rail", "hot_metal_rail", "water"]
VehicleStatus = Literal["IDLE", "ASSIGNED", "EMPTY_APPROACH", "QUEUED", "LOADING", "MOVING", "UNLOADING", "RETURNING", "BLOCKED"]
JobStatus = Literal["IDLE", "ASSIGNED", "EMPTY_APPROACH", "QUEUED", "LOADING", "MOVING", "UNLOADING", "RETURNING", "BLOCKED", "COMPLETED", "STRUCTURAL_BLOCKED"]
ACTIVE_JOB_STATUSES: Final = frozenset({"ASSIGNED", "EMPTY_APPROACH", "QUEUED", "LOADING", "MOVING", "UNLOADING", "RETURNING", "BLOCKED"})
Profile = Literal["v3_contract_test", "demo", "scale"]
MaterialForm = Literal["ORE", "HOT_METAL", "LIQUID_STEEL", "SCRAP", "SLAB", "BLOOM", "BILLET", "HOT_SLAB", "HOT_BLOOM", "HOT_BILLET", "HOT_STRIP", "HOT_PLATE", "STRIP", "THIN_STRIP", "COATED_STRIP", "HR_COIL", "CR_COIL", "GI_COIL", "GA_COIL", "HGI_COIL", "EG_COIL", "GO_COIL", "NGO_COIL", "WIRE", "WIRE_COIL", "PLATE", "STS_HR_COIL", "STS_CR_COIL", "STS_PLATE", "TI_INGOT", "TI_SLAB", "TI_HR_COIL", "TI_CR_COIL", "TI_SHEET", "TI_PLATE", "COKE", "COAL", "LIMESTONE", "ALLOY", "SLAG", "BYPRODUCT"]
ProcessStatus = Literal["QUEUED", "RUNNING", "BLOCKED", "COMPLETED"]
QualityStatus = Literal["PENDING", "PASSED", "HOLD", "FAILED"]
AvailabilityStatus = Literal["WIP", "QUARANTINED", "AVAILABLE", "RESERVED", "SHIPPED", "CONSUMED"]
TransportMode = Literal["ROAD", "RAIL", "SEA"]
EntityKind = Literal["run", "order", "work_order", "production_lot", "stock_lot", "receipt", "material", "material_version", "batch", "process", "fleet", "job", "attachment", "shipment", "shipment_leg", "quality"]
ErrorCode = Literal["canonical_bundle_unavailable", "unsupported_bundle", "unsupported_archive", "stale_run", "stale_revision", "idempotency_conflict", "legacy_write_forbidden", "utc_required", "time_out_of_range", "invalid_contract", "not_found", "resync_required"]


@dataclass(slots=True)  # noqa: MUTABLE_OK
class ContractViolation(ValueError):
    """Exception traceback fields remain mutable across context-manager boundaries."""
    code: str
    detail: str

    def __str__(self) -> str:
        return f"{self.code}: {self.detail}"


def valid_speed(value: int) -> int:
    if value not in (1, 2, 4):
        raise ContractViolation("invalid_contract", "speed must be 1, 2 or 4")
    return value


Speed = Annotated[int, Field(strict=True), AfterValidator(valid_speed)]


class Contract(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", validate_default=True)


class RunEntity(Contract):
    run_id: RunKey
    id: Id


class MaterialDimensions(Contract):
    length_mm: Dimension | None = None
    width_mm: Dimension | None = None
    thickness_mm: Dimension | None = None
    diameter_mm: Dimension | None = None
    inner_diameter_mm: Dimension | None = None
