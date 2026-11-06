"""Closed transport hierarchy projection for T66's independent byte admission.

This verifies only the mechanism fields owned here. The caller must additionally
validate the complete asset manifest, retained artifacts and decoded GLB geometry.
No producer certificate or caller-selected registry path is accepted.
"""
from __future__ import annotations

from collections.abc import Mapping
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Final, Literal, TypeAlias, assert_never

from pydantic import BaseModel, ConfigDict, Field, JsonValue, ValidationError

from .motion_policy import load_policies
from .world_types import Number, Record, require

ROOT: Final = Path(__file__).resolve().parents[3]
Vector: TypeAlias = tuple[Number, Number, Number]
Rotation: TypeAlias = tuple[Number, Number, Number, Number]
Hash: TypeAlias = Annotated[str, Field(pattern=r'^[a-f0-9]{64}$')]


class Range(Record):
    min: Number
    max: Number
    rest: Number


class Part(Record):
    id: str
    function: str
    parent_id: str
    axis: Vector
    pivot_m: Vector
    range: Range
    ancestors: tuple[str, ...]
    motion: Literal['rotation', 'translation']


class CanonicalPart(Part):
    representation: Literal['canonical']
    driver_id: None


class FollowerPart(Part):
    representation: Literal['mechanical_follower']
    driver_id: str
    ratio: Number


RegisteredPart: TypeAlias = Annotated[CanonicalPart | FollowerPart, Field(discriminator='representation')]


class FixedRelation(Record):
    part_id: str
    parent_part_id: str
    parent_id: str
    ancestors: tuple[str, ...]


class Registration(Record):
    asset_id: str
    variant: str
    category: Literal['fleet']
    kind: str
    policy_id: str
    required_parts: tuple[RegisteredPart, ...]
    nested_followers: tuple[str, ...]
    relative_fixed_parts: tuple[FixedRelation, ...]
    follower_socket_descendants: tuple[str, ...]


class TransportRegistry(Record):
    schema_version: Literal[1]
    source_proposal_sha256: Hash
    source_sha256: Mapping[str, Hash]
    registrations: Annotated[tuple[Registration, ...], Field(min_length=7, max_length=7)]
    scope: str


class Transform(Record):
    position_m: Vector
    rotation_xyzw: Rotation


class Node(Record):
    id: str
    parent_id: str | None
    locator: str
    transform: Transform


class ClipBinding(Record):
    type: Literal['clip']
    clock: Literal['server_sim']
    phase: str
    progress_source: Literal['server_phase_progress']
    pause: Literal['hold']
    fault: Literal['hold']
    rest: Literal['range_rest']
    clip_id: str


class FollowerBinding(Record):
    type: Literal['mechanical_follower']
    driver_part_id: str
    ratio: Number


class MovingPart(Record):
    id: str
    node_id: str
    function: str
    role: Literal['operational', 'decorative']
    motion: Literal['rotation', 'translation']
    axis: Vector
    pivot_m: Vector
    range: RangeWithUnit
    binding: Annotated[ClipBinding | FollowerBinding, Field(discriminator='type')]


class RangeWithUnit(Range):
    unit: Literal['m', 'rad']


class FixedPart(Record):
    id: str
    node_id: str
    function: str
    reason: str
    binding: JsonValue
    fixed_to_part_id: str | None = None


class Socket(Record):
    id: str
    node_id: str
    role: str
    transform: Transform
    normal: Vector
    forms: tuple[str, ...]
    max_load_kg: int


class AssetProjection(BaseModel):
    """Full manifest admission stays with T66; owned nested fields remain strict."""
    model_config = ConfigDict(frozen=True, extra='ignore')
    id: str
    family: str
    category: str
    kind: str
    variant: str
    motion_policy_id: str | None = None
    nodes: tuple[Node, ...]
    moving_parts: tuple[MovingPart, ...]
    fixed_parts: tuple[FixedPart, ...]
    sockets: tuple[Socket, ...]


MovingPart.model_rebuild()


@lru_cache(maxsize=1)
def load_transport_registry() -> TransportRegistry:
    """Only the installed trusted table is an authority; source hashes are provenance."""
    table = TransportRegistry.model_validate_json((ROOT / 'shared/transport-mechanics.json').read_bytes())
    expected = {'steelflow:transport:' + key for key in ('truck-flatbed','truck-dump','slab-carrier','coil-carrier','forklift','torpedo','unloader')}
    require({r.asset_id for r in table.registrations} == expected, 'transport_mechanics', 'registry universe')
    require(len({r.variant for r in table.registrations}) == 7, 'transport_mechanics', 'registry variants')
    for row in table.registrations:
        ids = tuple(p.id for p in row.required_parts)
        require(len(set(ids)) == len(ids) and not row.follower_socket_descendants, 'transport_mechanics', row.asset_id)
        require(set(row.nested_followers) <= set(ids), 'transport_mechanics', row.asset_id + ':nested')
        for part in row.required_parts:
            require(part.range.min < part.range.max and part.range.min <= part.range.rest <= part.range.max, 'transport_mechanics', part.id)
            match part:
                case FollowerPart(): require(part.ratio != 0, 'transport_mechanics', part.id)
                case CanonicalPart(): pass
                case unreachable: assert_never(unreachable)
    return table


def _ancestors(asset: AssetProjection, identity: str) -> tuple[str, ...]:
    nodes = {n.id:n for n in asset.nodes}
    require(identity in nodes, 'transport_mechanics', identity + ':node')
    result = []
    seen = {identity}
    cursor = nodes[identity].parent_id
    while cursor is not None:
        require(cursor in nodes and cursor not in seen, 'transport_mechanics', identity + ':ancestry')
        result.append(cursor)
        seen.add(cursor)
        cursor = nodes[cursor].parent_id
    return tuple(result)


def validate_transport_mechanics(raw: Mapping[str, JsonValue]) -> Registration | None:
    """Verify exact source hierarchy; old assets outside the closed opt-in return None."""
    row = next((r for r in load_transport_registry().registrations if r.asset_id == raw.get('id')), None)
    if row is None: return None
    try: asset = AssetProjection.model_validate(raw)
    except ValidationError as error:
        from .world_types import WorldContractError
        raise WorldContractError('transport_mechanics', row.asset_id + ':schema') from error
    require((asset.category,asset.kind,asset.variant,asset.family) == (row.category,row.kind,row.variant,'transport'), 'transport_mechanics', asset.id + ':identity')
    policies = [p for p in load_policies().policies if (p.category,p.kind) == (asset.category,asset.kind)]
    require(len(policies) == 1 and policies[0].id == row.policy_id and asset.motion_policy_id is None, 'transport_mechanics', asset.id + ':policy')
    require(len({n.id for n in asset.nodes}) == len(asset.nodes), 'transport_mechanics', asset.id + ':node-universe')
    parts = {p.id:p for p in asset.moving_parts}
    nodes = {n.id:n for n in asset.nodes}
    require(len(parts) == len(asset.moving_parts) and set(parts) == {p.id for p in row.required_parts}, 'transport_mechanics', asset.id + ':part-universe')
    for expected in row.required_parts:
        actual = parts[expected.id]
        require(actual.node_id == expected.id and actual.function == expected.function and actual.role == 'operational' and actual.motion == expected.motion, 'transport_mechanics', expected.id + ':function')
        require(expected.id in nodes and nodes[expected.id].parent_id == expected.parent_id and _ancestors(asset,expected.id) == expected.ancestors, 'transport_mechanics', expected.id + ':ancestry')
        require(actual.axis == expected.axis and actual.pivot_m == expected.pivot_m == nodes[expected.id].transform.position_m, 'transport_mechanics', expected.id + ':frame')
        require((actual.range.min,actual.range.max,actual.range.rest) == (expected.range.min,expected.range.max,expected.range.rest) and actual.range.unit == ('rad' if actual.motion == 'rotation' else 'm'), 'transport_mechanics', expected.id + ':range')
        match expected:
            case CanonicalPart():
                match actual.binding:
                    case ClipBinding(clip_id=clip): require(clip == asset.id.rsplit(':',1)[-1] + '.' + expected.id, 'transport_mechanics', expected.id + ':clip')
                    case FollowerBinding(): require(False, 'transport_mechanics', expected.id + ':clip')
                    case unreachable: assert_never(unreachable)
            case FollowerPart():
                match actual.binding:
                    case FollowerBinding(driver_part_id=driver,ratio=ratio): require(driver == expected.driver_id and ratio == expected.ratio and parts[driver].binding.type == 'clip', 'transport_mechanics', expected.id + ':driver')
                    case ClipBinding(): require(False, 'transport_mechanics', expected.id + ':driver')
                    case unreachable: assert_never(unreachable)
                require(not any(s.node_id == expected.id or expected.id in _ancestors(asset,s.node_id) for s in asset.sockets), 'transport_mechanics', expected.id + ':follower-socket')
            case unreachable: assert_never(unreachable)
        if expected.function == 'wheel_rotation':
            require(all(expected.id + suffix in nodes and nodes[expected.id + suffix].parent_id == expected.id for suffix in ('_tyre','_rim','_rotation_index')), 'transport_mechanics', expected.id + ':whole-wheel')
    for fixed in row.relative_fixed_parts:
        part = next((p for p in asset.fixed_parts if p.id == fixed.part_id),None)
        require(part is not None and part.id == part.node_id == part.function and part.binding is None and part.fixed_to_part_id == fixed.parent_part_id, 'transport_mechanics', fixed.part_id + ':relative-fixed')
        require(fixed.part_id in nodes and nodes[fixed.part_id].parent_id == fixed.parent_id and _ancestors(asset,fixed.part_id) == fixed.ancestors and parts[fixed.parent_part_id].binding.type == 'clip', 'transport_mechanics', fixed.part_id + ':fixed-parent')
        require(not any(n in parts for n in _ancestors(asset,fixed.parent_part_id)), 'transport_mechanics', fixed.part_id + ':fixed-parent-ancestors')
        descendants = {n.id for n in asset.nodes if n.id == fixed.part_id or fixed.part_id in _ancestors(asset,n.id)}
        require(not (descendants & set(parts)) and not any(s.node_id in descendants for s in asset.sockets) and not any(p.id != fixed.part_id and p.node_id in descendants for p in asset.fixed_parts), 'transport_mechanics', fixed.part_id + ':static-branch')
    return row
