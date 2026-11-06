"""Immutable wire records for server-authored motion projection."""

from dataclasses import dataclass
from math import sqrt
from typing import Annotated, Literal, Self, override

from pydantic import (
    AfterValidator,
    BeforeValidator,
    Field,
    TypeAdapter,
    ConfigDict,
    model_validator,
)

from .contracts_v3_core import (
    Contract,
    Digest,
    Finite,
    Id,
    MaterialDimensions,
    MaterialForm,
    Ms,
    NonNegative,
    RunKey,
    Text,
)


@dataclass(slots=True)  # noqa: MUTABLE_OK
class MotionError(Exception):
    """Mutable traceback fields are required by Python exception propagation."""

    code: str
    reference: str

    @override
    def __str__(self) -> str:
        return f"{self.code}: {self.reference}"


def require(condition: bool, code: str, reference: str) -> None:
    if not condition:
        raise MotionError(code, reference)


def unit_quaternion(
    value: tuple[float, float, float, float],
) -> tuple[float, float, float, float]:
    require(
        abs(sqrt(sum(x * x for x in value)) - 1) <= 1e-6,
        "quaternion",
        "orientation_xyzw",
    )
    return value


Vector = tuple[Finite, Finite, Finite]
Quaternion = Annotated[
    tuple[Finite, Finite, Finite, Finite], AfterValidator(unit_quaternion)
]
Progress = Annotated[Finite, Field(ge=0, le=1)]
SchemaVersion = Annotated[
    Literal[1],
    BeforeValidator(TypeAdapter(int, config=ConfigDict(strict=True)).validate_python),
]
WindowName = Literal[
    "entry", "work", "exit", "approach", "load", "travel", "unload", "return", "hold"
]


class MotionWindow(Contract):
    id: WindowName
    start: Progress
    end: Progress

    @model_validator(mode="after")
    def ordered(self) -> Self:
        require(self.start < self.end, "window", self.id)
        return self


class FunctionNeed(Contract):
    function_id: Text
    kind: Literal["moving", "state", "unresolved"]
    window_id: WindowName
    policy_id: Text | None
    semantic_need: Text


class MotionRecipe(Contract):
    id: Text
    semantic_id: Text
    execution_kind: Literal["process", "transport", "logistics"]
    meaning: Text
    policy_ids: tuple[Text, ...]
    requirement_ids: tuple[Text, ...]
    source_step_ids: tuple[Text, ...]
    compiled_step_ids: tuple[Text, ...]
    windows: tuple[MotionWindow, ...]
    functions: tuple[FunctionNeed, ...]
    binding_status: Literal["pending_delivery"]

    @model_validator(mode="after")
    def unique_windows(self) -> Self:
        require(bool(self.windows), "window", self.id)
        require(
            len({w.id for w in self.windows}) == len(self.windows), "duplicate", self.id
        )
        require(
            all(a.end <= b.start for a, b in zip(self.windows, self.windows[1:])),
            "window_overlap",
            self.id,
        )
        require(
            len({(f.policy_id, f.function_id) for f in self.functions})
            == len(self.functions),
            "duplicate",
            self.id,
        )
        require(
            all(f.window_id in {w.id for w in self.windows} for f in self.functions),
            "window",
            self.id,
        )
        require(len(set(self.policy_ids)) == len(self.policy_ids), "duplicate", self.id)
        return self


class Applicability(Contract):
    kind: Literal["requirement", "connection", "disposition", "receipt", "fleet"]
    reference_id: Text
    recipe_ids: tuple[Text, ...]


class MotionRegistry(Contract):
    schema_version: SchemaVersion
    authority: Text
    recipes: tuple[MotionRecipe, ...]
    applicability: tuple[Applicability, ...]


class Anchor(Contract):
    owner_id: Id
    socket_id: Id
    position_m: Vector
    orientation_xyzw: Quaternion


class MaterialSupport(Contract):
    material_id: Id
    material_version_id: Id
    form: MaterialForm
    dimensions: MaterialDimensions
    support_local_mm: Vector
    orientation_xyzw: Quaternion


class InternalFeedReference(Contract):
    schema_version: SchemaVersion
    feed_id: Id


class InternalFeedMaterialSupport(MaterialSupport):
    internal_feed: InternalFeedReference


class BathPathReference(Contract):
    schema_version: SchemaVersion
    profile_id: Id


class BathPathMaterialSupport(MaterialSupport):
    bath_path: BathPathReference


MaterialSupportValue = BathPathMaterialSupport | InternalFeedMaterialSupport | MaterialSupport


class ChannelValue(Contract):
    function_id: Text
    node_id: Text
    kind: Literal["rotation", "translation", "state"]
    value: Finite
    axis: Vector
    pivot_m: Vector


class Boundary(Contract):
    released_attachment_id: Id
    acquired_attachment_id: Id
    at_ms: Ms
    previous_material: MaterialSupportValue
    previous_anchor: Anchor
    previous_channels: tuple[ChannelValue, ...]


class MechanicalChannel(Contract):
    function_id: Text
    node_id: Text
    kind: Literal["rotation", "translation", "state"]
    window_id: WindowName
    axis: Vector
    pivot_m: Vector
    start_value: Finite
    end_value: Finite


class MotionEnvelope(Contract):
    schema_version: SchemaVersion
    run_id: RunKey
    bundle_id: Id
    bundle_hash: Digest
    revision: NonNegative
    confirmed_sim_ms: Ms
    execution_id: Id
    execution_kind: Literal["process", "transport", "logistics"]
    recipe_id: Text
    phase_start_ms: Ms
    phase_end_ms: Ms
    effective_sim_ms: Ms
    frozen_progress: Progress | None
    clock_state: Literal["running", "paused", "stale", "blocked"]
    material: MaterialSupportValue
    attachment_id: Id
    anchor: Anchor
    channels: tuple[MechanicalChannel, ...]
    boundary: Boundary | None

    @model_validator(mode="after")
    def check_time(self) -> Self:
        require(self.phase_end_ms > self.phase_start_ms, "window", self.execution_id)
        require(
            self.effective_sim_ms <= self.confirmed_sim_ms,
            "future_time",
            self.execution_id,
        )
        require(
            self.clock_state == "running" or self.frozen_progress is not None,
            "held_progress_required",
            self.execution_id,
        )
        require(
            len({c.function_id for c in self.channels}) == len(self.channels),
            "duplicate",
            self.execution_id,
        )
        for channel in self.channels:
            require(
                abs(sum(x * x for x in channel.axis) - 1) <= 1e-6,
                "axis",
                channel.function_id,
            )
        return self


class MotionPose(Contract):
    run_id: RunKey
    revision: NonNegative
    execution_id: Id
    recipe_id: Text
    material: MaterialSupportValue
    attachment_id: Id
    owner_id: Id
    socket_id: Id
    position_m: Vector
    contact_m: Vector
    orientation_xyzw: Quaternion
    progress: Progress
    phase_complete: Literal[False] = False
    channels: tuple[ChannelValue, ...]
