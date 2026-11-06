"""Motion-owned syntax-first UTF-8/duplicate and strict numeric boundary."""

import json
from typing import Final, Literal, assert_never
from pydantic import JsonValue, TypeAdapter
from .motion_types import MotionError

SNAPSHOT_INTEGERS: Final = frozenset(
    {
        "seed",
        "elapsed_ms",
        "duration_ms",
        "revision",
        "event_sequence",
        "speed",
        "quantity_kg",
        "route_version",
        "planned_kg",
        "received_at_ms",
        "weight_kg",
        "ordinal",
        "transferred_kg",
        "start_ms",
        "end_ms",
        "ready_at_ms",
        "planned_duration_ms",
        "at_ms",
        "sequence",
        "capacity_kg",
        "available_at_ms",
        "acquired_at_ms",
        "released_at_ms",
        "eta_ms",
    }
)
MOTION_INTEGERS: Final = frozenset(
    {
        "schema_version",
        "revision",
        "confirmed_sim_ms",
        "phase_start_ms",
        "phase_end_ms",
        "effective_sim_ms",
        "at_ms",
    }
)
JSON_VALUE: Final = TypeAdapter(JsonValue)


def reject_constant(value: str) -> JsonValue:
    raise MotionError("json", value)


def unique_pairs(pairs: list[tuple[str, JsonValue]]) -> dict[str, JsonValue]:
    result: dict[str, JsonValue] = {}
    for key, value in pairs:
        if key in result:
            raise MotionError("duplicate", key)
        result[key] = value
    return result


def strict_integers(value: JsonValue, path: tuple[str, ...]) -> None:
    """Keep strict T5/motion scalars separate from T3 mathematical integers."""
    match value:
        case dict():
            for key, item in value.items():
                strict_integers(item, (*path, key))
        case list():
            for item in value:
                strict_integers(item, path)
        case float():
            snapshot = path[:2] == ("context", "snapshot")
            world = path[:2] == ("context", "world")
            keys = SNAPSHOT_INTEGERS if snapshot else MOTION_INTEGERS
            if not world and path and path[-1] in keys:
                raise MotionError("invalid_contract", ".".join(path))
        case str() | int() | bool() | None:
            pass
        case unreachable:
            assert_never(unreachable)


def motion_json(
    raw: str | bytes,
    scope: Literal["request", "envelope", "context", "registry"] = "request",
) -> JsonValue:
    """Complete syntax before inspecting any duplicate keys or strict scalars."""
    try:
        match raw:
            case bytes():
                text = raw.decode("utf-8-sig", errors="strict")
            case str():
                text = raw
            case unreachable:
                assert_never(unreachable)
        json.loads(text, parse_constant=reject_constant)
        value = JSON_VALUE.validate_python(
            json.loads(
                text, object_pairs_hook=unique_pairs, parse_constant=reject_constant
            )
        )
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError) as error:
        raise MotionError("json", "UTF-8/JSON") from error
    strict_integers(value, ("context",) if scope == "context" else ())
    return value
