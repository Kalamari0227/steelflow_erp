"""Source05 descriptor eligibility; no physical admission exists in contract stage A."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from hashlib import sha256
from math import isfinite
from pathlib import Path
from types import UnionType
from typing import TYPE_CHECKING, Annotated, Final, Never, Union, get_args, get_origin

from pydantic import AwareDatetime, BaseModel, JsonValue
from pydantic_core import PydanticSerializationError

from .contracts_v3_core import Contract, Digest, Id, Text
from .motion_bindings import AssetBinding, BathPathAssetBinding, BathPathBinding
from .motion_types import MotionEnvelope, MotionRegistry, Anchor, BathPathMaterialSupport, Boundary, MaterialSupport, MotionError, SchemaVersion, require
from .world_contract import FactoryWorld
from .world_types import Pose

if TYPE_CHECKING:
    from .motion_context import MotionContext
    from .motion_request import MotionRequest


class SourceArtifact(Contract):
    path: Text
    sha256: Digest


class BathSourceProfile(Contract):
    owner_id: Id
    owner_kind: Text
    owner_pose: Pose
    descriptor: BathPathBinding
    canonical_binding: AssetBinding
    source_inventory: JsonValue


class BathSourceTable(Contract):
    schema_version: SchemaVersion
    algorithm_id: Text
    descriptor_sha256: Digest
    artifacts: tuple[SourceArtifact, ...]
    profiles: tuple[BathSourceProfile, BathSourceProfile, BathSourceProfile]


SOURCE_TABLE: Final = BathSourceTable.model_validate_json(
    (Path(__file__).resolve().parents[3] / 'shared/finishing-bath-source05.json').read_bytes()
)


def validate_bath_binding(binding: BathPathAssetBinding, world: FactoryWorld) -> BathSourceProfile:
    """A matching descriptor narrows eligible inputs; it never admits a runtime."""
    row = next((p for p in SOURCE_TABLE.profiles if p.owner_id == binding.owner_id), None)
    if row is None:
        raise MotionError('binding', binding.owner_id)
    require(binding.bath_paths == (row.descriptor,), 'binding', row.descriptor.id)
    expected = row.canonical_binding.model_dump(mode='json')
    actual = binding.model_dump(mode='json', exclude={'bath_paths'})
    require(actual == expected, 'binding', binding.owner_id)
    owner = next((o for o in world.owners if o.id == binding.owner_id), None)
    require(owner is not None and owner.kind == row.owner_kind and owner.pose == row.owner_pose,
            'binding', binding.owner_id)
    if owner is None:
        raise MotionError('binding', binding.owner_id)
    for socket in binding.sockets:
        graph = next((s for s in owner.sockets if s.id == socket.socket_id), None)
        require(graph is not None and graph.pose.position == socket.position_m and graph.pose.yaw_rad == 0,
                'binding', binding.owner_id)
    return row


def validate_bath_support(anchor: Anchor, material: MaterialSupport, binding: AssetBinding) -> None:
    """Dispatch either half before legacy support; deletion cannot restore point support."""
    bath_material = isinstance(material, BathPathMaterialSupport)
    bath_binding = isinstance(binding, BathPathAssetBinding)
    if not (bath_material or bath_binding):
        return
    if not isinstance(material, BathPathMaterialSupport) or not isinstance(binding, BathPathAssetBinding):
        raise MotionError('binding', anchor.owner_id)
    descriptor = binding.bath_paths[0]
    reference = material.bath_path.profile_id
    require(reference == descriptor.id and anchor.owner_id == binding.owner_id and anchor.socket_id == 'work',
            'binding', reference)
    socket = binding.sockets[0]
    require(anchor.position_m == socket.position_m and anchor.orientation_xyzw == socket.orientation_xyzw,
            'binding', reference)
    d = material.dimensions
    require(d.length_mm == descriptor.stock_length_m * 1000 and d.width_mm == descriptor.width_m * 1000
            and d.thickness_mm == descriptor.thickness_m * 1000 and d.diameter_mm is None
            and d.inner_diameter_mm is None and material.orientation_xyzw == (0, 0, 0, 1)
            and material.support_local_mm == (0, -descriptor.thickness_m * 500, 0), 'binding', reference)


def reject_unqualified_bath(anchor: Anchor, material: MaterialSupport, binding: AssetBinding) -> None:
    validate_bath_support(anchor, material, binding)
    if isinstance(material, BathPathMaterialSupport) or isinstance(binding, BathPathAssetBinding):
        raise MotionError('bath_unqualified', anchor.owner_id)


def validate_bath_context(context: MotionContext) -> None:
    for binding in context.asset_bindings:
        if not isinstance(binding, BathPathAssetBinding):
            continue
        require(not any(f.id == binding.owner_id for f in context.snapshot.fleet)
                and not any(v.fleet_id == binding.owner_id for v in context.snapshot.vehicle_states),
                'binding', binding.owner_id)
    for envelope in context.authorizations:
        validate_bath_envelope(envelope, context)


def validate_bath_envelope(envelope: MotionEnvelope, context: MotionContext) -> None:
    pairs = [(envelope.anchor, envelope.material)]
    if envelope.boundary is not None:
        pairs.append((envelope.boundary.previous_anchor, envelope.boundary.previous_material))
    for anchor, material in pairs:
        if not isinstance(material, BathPathMaterialSupport):
            continue
        binding = next((b for b in context.asset_bindings if b.owner_id == anchor.owner_id), None)
        if binding is None:
            raise MotionError('binding', anchor.owner_id)
        validate_bath_support(anchor, material, binding)


def create_bath_runtime(source_bytes: Mapping[str, bytes], retained_world: FactoryWorld) -> Never:
    """Rehash the closed artifact map, then refuse the still-unimplemented physical proof."""
    expected = {a.path: a.sha256 for a in SOURCE_TABLE.artifacts}
    require(set(source_bytes) == set(expected), 'binding', SOURCE_TABLE.algorithm_id)
    for path, digest in expected.items():
        require(sha256(source_bytes[path]).hexdigest() == digest, 'binding', path)
    for row in SOURCE_TABLE.profiles:
        binding = BathPathAssetBinding(**row.canonical_binding.model_dump(), bath_paths=(row.descriptor,))
        validate_bath_binding(binding, retained_world)
    # No GLB decoding, complete interval proof or private capability registry exists yet.
    raise MotionError('bath_unqualified', SOURCE_TABLE.algorithm_id)


def evaluate_bath_motion(runtime: Never, request: MotionRequest, registry: MotionRegistry) -> Never:
    """No caller object, digest, or metadata result can manufacture stage-A admission."""
    raise MotionError('bath_unqualified', SOURCE_TABLE.algorithm_id)


def _bath_storage(value: BaseModel):
    """Establish ordinary storage and exact string names before any named lookup."""
    stored = object.__getattribute__(value, '__dict__')
    extra = object.__getattribute__(value, '__pydantic_extra__')
    require(type(stored) is dict and (extra is None or type(extra) is dict), 'invalid_contract', 'request')
    for names in (stored, extra):
        if names is not None:
            require(all(type(name) is str for name in dict.__iter__(names)), 'invalid_contract', 'request')
    return stored, extra


def _bath_marker(value: BaseModel, key: str, subtype: type[BaseModel]) -> bool:
    """Read marker storage only after its typed domain role has been established."""
    stored, extra = _bath_storage(value)
    return issubclass(type(value), subtype) or dict.__contains__(stored, key) or (extra is not None and dict.__contains__(extra, key))


def _slot_models(annotation) -> tuple[type[BaseModel], ...]:
    """Read model roles from existing field annotations, without rebuilding their schema."""
    origin = get_origin(annotation)
    if origin is Annotated:
        return _slot_models(get_args(annotation)[0])
    if origin in (Union, UnionType):
        return tuple(model for option in get_args(annotation) for model in _slot_models(option))
    if isinstance(annotation, type) and issubclass(annotation, BaseModel):
        return (annotation,)
    return ()


def _inspect_bath_value(value, annotation, active: set[int]) -> None:
    """Check actual types and trusted storage before touching caller values."""
    value_type = type(value)
    models = _slot_models(annotation)
    if models:
        require(issubclass(value_type, models) or (value is None and type(None) in get_args(annotation)),
                'invalid_contract', 'request')
    if value_type is datetime:
        require(annotation in (datetime, AwareDatetime)
                or any(option in (datetime, AwareDatetime) for option in get_args(annotation)),
                'invalid_contract', 'request')
        return
    if value_type in (str, int, float, bool) or value is None:
        require(value_type is not float or isfinite(value), 'invalid_contract', 'request')
        return
    is_model = issubclass(value_type, BaseModel)
    require(is_model or value_type in (tuple, list, dict), 'invalid_contract', 'request')
    require(id(value) not in active, 'invalid_contract', 'request')
    active.add(id(value))
    try:
        if is_model:
            require(bool(models), 'invalid_contract', 'request')
            fields = value_type.model_fields
            stored, extra = _bath_storage(value)
            required = {name for name, field in fields.items() if field.is_required()}
            require(required <= stored.keys() and stored.keys() <= fields.keys() and not extra,
                    'invalid_contract', 'request')
            for name, item in stored.items():
                _inspect_bath_value(item, fields[name].annotation, active)
        elif value_type in (tuple, list):
            args = get_args(annotation)
            for index, item in enumerate(value):
                item_type = args[0] if len(args) == 2 and args[1] is Ellipsis else args[index] if index < len(args) else None
                _inspect_bath_value(item, item_type, active)
        else:
            for key, item in value.items():
                require(type(key) is str, 'invalid_contract', 'request')
                _inspect_bath_value(item, None, active)
    finally:
        active.remove(id(value))


def guard_bath_request(envelope: MotionEnvelope, context: MotionContext) -> None:
    """One original-graph and canonical-parser boundary for both public bath calls."""
    from .motion_context import MotionContext

    require(issubclass(type(envelope), MotionEnvelope) and issubclass(type(context), MotionContext),
            'invalid_contract', 'request')
    envelope_fields, _ = _bath_storage(envelope)
    context_fields, _ = _bath_storage(context)
    material = dict.get(envelope_fields, 'material')
    require(issubclass(type(material), MaterialSupport) and dict.__contains__(envelope_fields, 'boundary'),
            'invalid_contract', 'request')
    boundary = dict.get(envelope_fields, 'boundary')
    require(boundary is None or issubclass(type(boundary), Boundary), 'invalid_contract', 'request')
    previous = None
    if boundary is not None:
        boundary_fields, _ = _bath_storage(boundary)
        previous = dict.get(boundary_fields, 'previous_material')
        require(issubclass(type(previous), MaterialSupport), 'invalid_contract', 'request')
    bindings = dict.get(context_fields, 'asset_bindings')
    require((type(bindings) is tuple or type(bindings) is list), 'invalid_contract', 'request')
    for binding in bindings:
        require(issubclass(type(binding), AssetBinding), 'invalid_contract', 'request')
    bath_binding = any(_bath_marker(binding, 'bath_paths', BathPathAssetBinding) for binding in bindings)
    if not (_bath_marker(material, 'bath_path', BathPathMaterialSupport)
            or (previous is not None and _bath_marker(previous, 'bath_path', BathPathMaterialSupport)) or bath_binding):
        return
    from .motion_json import strict_integers
    from .motion_request import parse_motion_request_value

    try:
        _inspect_bath_value(envelope, MotionEnvelope, set())
        _inspect_bath_value(context, MotionContext, set())
        projected: JsonValue = {
            'envelope': envelope.model_dump(mode='json', serialize_as_any=True),
            'context': context.model_dump(mode='json', serialize_as_any=True),
        }
    except (PydanticSerializationError, ValueError, RecursionError) as error:
        raise MotionError('invalid_contract', 'request') from error
    strict_integers(projected, ())
    parsed = parse_motion_request_value(projected)
    # parse_context_value already runs binding semantics and all authorizations.
    validate_bath_envelope(parsed.envelope, parsed.context)
    raise MotionError('bath_unqualified', parsed.envelope.anchor.owner_id)
