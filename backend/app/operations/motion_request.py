"""The public immutable request and staged authoritative motion input boundary."""

from pydantic import JsonValue, ValidationError
from .contracts_v3_core import Contract
from .motion_context import MotionContext, parse_context_value
from .motion_json import motion_json
from .motion_types import MotionEnvelope, MotionError


class MotionRequest(Contract):
    envelope: MotionEnvelope
    context: MotionContext


def parse_motion_request_value(value: JsonValue) -> MotionRequest:
    from .motion_structure import preflight

    preflight(value)
    if not isinstance(value, dict):
        raise MotionError("invalid_contract", "request")
    try:
        envelope = MotionEnvelope.model_validate(value["envelope"])
    except ValidationError as error:
        raise MotionError("invalid_contract", "envelope") from error
    context = parse_context_value(value["context"])
    return MotionRequest(envelope=envelope, context=context)


def parse_motion_request(raw: str | bytes) -> MotionRequest:
    return parse_motion_request_value(motion_json(raw))


def require_typed_model[T: Contract](value: T | JsonValue, expected: type[T]) -> None:
    """Guard direct Python callers without reparsing trusted model semantics."""
    if not isinstance(value, expected):
        raise MotionError("invalid_contract", expected.__name__)
