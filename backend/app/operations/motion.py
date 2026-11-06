"""Pure server-confirmed motion projection; never mutates business state or custody."""

from pydantic import JsonValue, ValidationError

from .motion_context import MotionContext
from .motion_custody import validate_authority, validate_boundary
from .motion_math import channel_values, progress
from .motion_internal_feed import project_support
from .motion_registry import parse_motion_registry as parse_motion_registry
from .motion_types import (
    MotionEnvelope,
    MotionError,
    MotionPose,
    MotionRegistry,
    require,
)
from .motion_validation import (
    root_pose,
    validate_anchor,
    validate_channel_values,
    validate_execution,
)
from .motion_json import motion_json, strict_integers
from .motion_structure import preflight
from .motion_context import parse_context_value
from .world_types import WorldContractError


def parse_motion_envelope(raw: str | bytes) -> MotionEnvelope:
    """Reject duplicate JSON keys, nonfinite/coerced values and incomplete fields."""
    try:
        value = motion_json(raw, "envelope")
        preflight(value, "envelope")
        return MotionEnvelope.model_validate(value)
    except WorldContractError as error:
        raise MotionError(error.code, error.reference) from error
    except ValidationError as error:
        raise MotionError("invalid_contract", "envelope") from error


def parse_motion_context(raw: str | bytes) -> MotionContext:
    """Parse authoritative server inputs through actual T3/T5 contracts."""
    try:
        return parse_context_value(motion_json(raw, "context"))
    except WorldContractError as error:
        raise MotionError(error.code, error.reference) from error
    except ValidationError as error:
        raise MotionError("invalid_contract", "context") from error


def evaluate_motion(
    envelope: MotionEnvelope, context: MotionContext, registry: MotionRegistry
) -> MotionPose:
    """Reject nonfinite intermediate geometry without emitting a partial result."""
    from pydantic_core import PydanticSerializationError
    from .motion_request import require_typed_model
    from .motion_bath_path import guard_bath_request

    guard_bath_request(envelope, context)
    try:
        require_typed_model(envelope, MotionEnvelope)
        require_typed_model(context, MotionContext)
        # Validation-only projection preserves runtime scalar types; canonical wire
        # serialization still uses the normal model serializers.
        projected: JsonValue = {
            "envelope": envelope.model_dump(mode="json", serialize_as_any=True),
            "context": context.model_dump(mode="json", serialize_as_any=True),
        }
        strict_integers(projected, ())
        preflight(projected)
        return project_motion(envelope, context, registry)
    except (
        ValidationError,
        PydanticSerializationError,
        OverflowError,
        ZeroDivisionError,
    ) as error:
        raise MotionError("invalid_contract", "pose") from error


def project_motion(
    envelope: MotionEnvelope, context: MotionContext, registry: MotionRegistry
) -> MotionPose:
    """Evaluate an explicitly authorized immutable phase against current server state."""
    from .motion_bath_path import guard_bath_request
    guard_bath_request(envelope, context)
    recipe = next((r for r in registry.recipes if r.id == envelope.recipe_id), None)
    if recipe is None:
        raise MotionError("unknown_recipe", envelope.recipe_id)
    require(
        recipe.execution_kind == envelope.execution_kind,
        "execution",
        envelope.execution_id,
    )
    _ = validate_authority(envelope, context)
    validate_execution(envelope, context, recipe)
    binding = validate_anchor(envelope.anchor, envelope.material, context)
    require(binding.policy_id in recipe.policy_ids, "binding", binding.policy_id)
    selected = tuple(f for f in recipe.functions if f.policy_id == binding.policy_id)
    needs = {f.function_id: f for f in selected}
    require(
        {c.function_id for c in envelope.channels}
        == {f.function_id for f in selected if f.kind != "unresolved"},
        "unknown_function",
        recipe.id,
    )
    for channel in envelope.channels:
        need = needs.get(channel.function_id)
        require(need is not None, "unknown_function", channel.function_id)
        if need is None:
            raise MotionError("unknown_function", channel.function_id)
        require(
            need.policy_id == binding.policy_id and need.kind != "unresolved",
            "unknown_function",
            channel.function_id,
        )
        require(
            (need.kind == "state") == (channel.kind == "state")
            and need.window_id == channel.window_id,
            "binding",
            channel.function_id,
        )
    values = channel_values(envelope, recipe)
    validate_channel_values(values, binding)
    for channel in envelope.channels:
        descriptor = next(
            f for f in binding.functions if f.function_id == channel.function_id
        )
        require(
            descriptor.min_value
            <= min(channel.start_value, channel.end_value)
            <= max(channel.start_value, channel.end_value)
            <= descriptor.max_value,
            "binding",
            channel.function_id,
        )
    anchor = envelope.anchor
    projection = project_support(anchor,envelope.material,values,binding,root_pose(anchor.owner_id,context))
    position, contact, orientation = projection.position_m, projection.contact_m, projection.orientation_xyzw
    validate_boundary(envelope,context,contact,projection,values)
    return MotionPose(
        run_id=envelope.run_id,
        revision=envelope.revision,
        execution_id=envelope.execution_id,
        recipe_id=envelope.recipe_id,
        material=envelope.material,
        attachment_id=envelope.attachment_id,
        owner_id=anchor.owner_id,
        socket_id=anchor.socket_id,
        position_m=position,
        contact_m=contact,
        orientation_xyzw=orientation,
        progress=progress(envelope),
        channels=values,
    )
