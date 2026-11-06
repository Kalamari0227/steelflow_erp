"""Read-only structural preflight for the generated motion schema's closed profile."""

from __future__ import annotations

from functools import lru_cache
from math import isfinite
from pathlib import Path
import re
from typing import ClassVar, Final, Literal, assert_never

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    TypeAdapter,
    ValidationError,
)

from .motion_types import MotionError

Scope = Literal["request", "envelope", "context"]
PATTERNS: Final = frozenset(
    {
        r"^[A-Za-z0-9][A-Za-z0-9_.:-]*$",
        r"^v2:[A-Za-z0-9][A-Za-z0-9_.:-]*$",
        r"^[0-9a-f]{64}$",
        r"^(?!0000)[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(?:\.[0-9]{1,3}0{0,3})?(?:Z|\+00:00)(?![\s\S])",
    }
)


class SchemaNode(BaseModel):
    """Only keywords emitted by our pinned public validation model are admitted."""

    model_config: ClassVar[ConfigDict] = ConfigDict(
        extra="forbid", frozen=True, populate_by_name=False
    )
    definitions: dict[str, "SchemaNode"] = Field(default_factory=dict, alias="$defs")
    ref: str | None = Field(default=None, alias="$ref")
    kind: (
        Literal["object", "array", "string", "null", "boolean", "number", "integer"]
        | None
    ) = Field(default=None, alias="type")
    properties: dict[str, "SchemaNode"] = Field(default_factory=dict)
    required: tuple[str, ...] = ()
    additional: bool | SchemaNode | None = Field(
        default=None, alias="additionalProperties"
    )
    items: "SchemaNode | None" = None
    prefix: tuple["SchemaNode", ...] = Field(default=(), alias="prefixItems")
    alternatives: tuple["SchemaNode", ...] = Field(default=(), alias="anyOf")
    const: JsonValue = None
    enum: tuple[JsonValue, ...] | None = None
    min_items: int = Field(default=0, alias="minItems")
    max_items: int | None = Field(default=None, alias="maxItems")
    min_length: int = Field(default=0, alias="minLength")
    minimum: float | None = None
    maximum: float | None = None
    exclusive_minimum: float | None = Field(default=None, alias="exclusiveMinimum")
    gt: float | None = None
    le: float | None = None
    pattern: str | None = None
    title: str | None = None
    default: JsonValue = None
    format: Literal["date-time"] | None = None


def admit_profile(raw: JsonValue) -> SchemaNode:
    """Fail closed on new keywords, patterns, nonlocal, missing or cyclic references."""
    try:
        schema = SchemaNode.model_validate(raw)
    except ValidationError as error:
        raise MotionError(
            "invalid_contract", "unsupported motion schema profile"
        ) from error

    def visit(node: SchemaNode, refs: frozenset[str]) -> None:
        if node.additional is True:
            raise MotionError("invalid_contract", "open motion schema object")
        if node.pattern is not None and node.pattern not in PATTERNS:
            raise MotionError("invalid_contract", "unsupported motion schema pattern")
        if node.ref is not None:
            if not node.ref.startswith("#/$defs/") or node.ref in refs:
                raise MotionError(
                    "invalid_contract", "nonlocal or cyclic motion schema"
                )
            target = schema.definitions.get(node.ref.removeprefix("#/$defs/"))
            if target is None:
                raise MotionError("invalid_contract", "missing motion schema reference")
            visit(target, refs | {node.ref})
        for child in (
            *node.properties.values(),
            *node.definitions.values(),
            *node.prefix,
            *node.alternatives,
        ):
            visit(child, refs)
        if node.items is not None:
            visit(node.items, refs)
        if isinstance(node.additional, SchemaNode):
            visit(node.additional, refs)

    visit(schema, frozenset())
    return schema


@lru_cache(maxsize=1)
def request_schema() -> SchemaNode:
    """Load the checked generated document without mutating or resolving remote data."""
    path = Path(__file__).resolve().parents[3] / "shared/motion-request.schema.json"
    return admit_profile(JsonValueAdapter.validate_json(path.read_bytes()))


# JsonValue's recursive public adapter rejects arbitrary Python runtime objects.
JsonValueAdapter: Final = TypeAdapter(JsonValue)


def same_primitive(left: JsonValue, right: JsonValue) -> bool:
    if isinstance(left, bool) or isinstance(right, bool):
        return type(left) is type(right) and left == right
    return left == right


def matches(value: JsonValue, node: SchemaNode, schema: SchemaNode) -> bool:
    """Inspect shape/scalars only; domain validators and defaults never run here."""
    if node.ref is not None and not matches(
        value, schema.definitions[node.ref.removeprefix("#/$defs/")], schema
    ):
        return False
    if node.alternatives and not any(
        matches(value, child, schema) for child in node.alternatives
    ):
        return False
    numeric = False
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        try:
            numeric = isfinite(value)
        except OverflowError:
            numeric = False
    match node.kind:
        case "object":
            valid_type = isinstance(value, dict)
        case "array":
            valid_type = isinstance(value, list)
        case "string":
            valid_type = isinstance(value, str)
        case "null":
            valid_type = value is None
        case "boolean":
            valid_type = type(value) is bool
        case "number":
            valid_type = numeric
        case "integer":
            valid_type = (
                numeric and isinstance(value, (int, float)) and value == int(value)
            )
        case None:
            valid_type = True
        case unreachable:
            assert_never(unreachable)
    if not valid_type:
        return False
    if "const" in node.model_fields_set and not same_primitive(value, node.const):
        return False
    if node.enum is not None and not any(
        same_primitive(value, option) for option in node.enum
    ):
        return False
    match value:
        case dict():
            if not set(node.required) <= value.keys():
                return False
            for key, item in value.items():
                child = node.properties.get(key)
                if child is not None:
                    if not matches(item, child, schema):
                        return False
                elif node.additional is False:
                    return False
                elif isinstance(node.additional, SchemaNode) and not matches(
                    item, node.additional, schema
                ):
                    return False
        case list():
            if len(value) < node.min_items or (
                node.max_items is not None and len(value) > node.max_items
            ):
                return False
            for index, item in enumerate(value):
                child = node.prefix[index] if index < len(node.prefix) else node.items
                if child is not None and not matches(item, child, schema):
                    return False
        case str():
            if len(value) < node.min_length or (
                node.pattern is not None
                and re.search(node.pattern, value, re.ASCII) is None
            ):
                return False
        case int() | float() | bool() | None:
            pass
        case unreachable:
            assert_never(unreachable)
    if numeric and isinstance(value, (int, float)):
        if node.minimum is not None and value < node.minimum:
            return False
        if node.maximum is not None and value > node.maximum:
            return False
        if node.exclusive_minimum is not None and value <= node.exclusive_minimum:
            return False
        if node.gt is not None and value <= node.gt:
            return False
        if node.le is not None and value > node.le:
            return False
    return True


def preflight(value: JsonValue, scope: Scope = "request") -> None:
    schema = request_schema()
    node = schema if scope == "request" else schema.properties[scope]
    if not matches(value, node, schema):
        raise MotionError("invalid_contract", scope)
