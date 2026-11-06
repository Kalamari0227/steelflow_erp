"""Validated authoritative snapshot, graph and execution projection context."""

from typing import Self
from pydantic import JsonValue, ValidationError, TypeAdapter, model_validator
from .contracts_v3 import FactorySnapshot
from .contracts_v3_core import Contract
from .world_contract import FactoryWorld
from .motion_bindings import AssetBindingValue
from .motion_types import MotionEnvelope, MotionError, require
from .world_types import WorldContractError


class MotionContext(Contract):
    snapshot: FactorySnapshot
    world: FactoryWorld
    authorizations: tuple[MotionEnvelope, ...]
    asset_bindings: tuple[AssetBindingValue, ...]

    @model_validator(mode="after")
    def unique(self) -> Self:
        require(
            len({b.owner_id for b in self.asset_bindings}) == len(self.asset_bindings),
            "duplicate",
            "bindings",
        )
        require(
            len({a.execution_id for a in self.authorizations})
            == len(self.authorizations),
            "duplicate",
            "authorizations",
        )
        from .motion_admission import validate_binding

        for binding in self.asset_bindings:
            validate_binding(binding, self.world)
        from .motion_bath_path import validate_bath_context
        validate_bath_context(self)
        return self


def parse_context_value(value: JsonValue) -> MotionContext:
    """Complete each actual semantic parser before advancing to the next sibling."""
    from .motion_structure import preflight

    preflight(value, "context")
    if not isinstance(value, dict):
        raise MotionError("invalid_contract", "context")
    try:
        snapshot = FactorySnapshot.model_validate(value["snapshot"])
    except ValidationError as error:
        raise MotionError("invalid_contract", "snapshot") from error
    try:
        world = FactoryWorld.model_validate(value["world"])
    except (ValidationError, WorldContractError) as error:
        raise MotionError("invalid_contract", "world") from error
    authorizations_raw, bindings_raw = value["authorizations"], value["asset_bindings"]
    if not isinstance(authorizations_raw, list) or not isinstance(bindings_raw, list):
        raise MotionError("invalid_contract", "context")
    try:
        authorizations = tuple(
            MotionEnvelope.model_validate(item) for item in authorizations_raw
        )
        bindings = tuple(TypeAdapter(AssetBindingValue).validate_python(item) for item in bindings_raw)
        return MotionContext(
            snapshot=snapshot,
            world=world,
            authorizations=authorizations,
            asset_bindings=bindings,
        )
    except ValidationError as error:
        raise MotionError("invalid_contract", "context") from error
