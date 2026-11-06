"""Closed finishing hardware registrations and same-host contact receipts."""
from __future__ import annotations

from dataclasses import dataclass
from math import dist, sqrt
from pathlib import Path
from typing import TYPE_CHECKING, Final

from .contracts_v3_core import Contract, Id, Text
from .motion_math import add, rotate
from .motion_types import ChannelValue, MotionEnvelope, Vector, require
from .motion_bindings import AssetBinding, InternalFeedBinding
from .world_types import Pose

if TYPE_CHECKING:
    from .motion_internal_feed import FeedProjection


class Subassembly(Contract):
    requirement_id: Text
    owner_id: Id
    section: Text
    moving_functions: tuple[Text, ...]
    state_functions: tuple[Text, ...]
    new_moving: tuple[Text, ...]
    new_state: tuple[Text, ...]
    stable_subassembly_id: Text


class InternalSequence(Contract):
    owner_id: Id
    source_recipe_id: Text
    policy_id: Text
    unwind_function_id: Text
    feed_function_id: Text
    lift_function_id: Text
    coil_socket_id: Text
    strip_socket_id: Text
    feed_socket_id: Text
    cold_entry_socket_id: Text | None
    added_moving_functions: tuple[Text, ...]


class SupportSocket(Contract):
    owner_id: Id
    source_recipe_id: Text
    policy_id: Text
    socket_id: Text
    role: Text
    family: Text
    motion_function_ids: tuple[Text, ...]


class Registration(Contract):
    schema_version: int
    rows: tuple[Subassembly, ...]
    source_internal_sequences: tuple[InternalSequence, ...]
    support_socket_registrations: tuple[SupportSocket, ...]


REGISTRATION: Final = Registration.model_validate_json(
    (Path(__file__).resolve().parents[3] / 'shared/finishing-subassemblies.json').read_bytes()
)


def sequence_for(binding: AssetBinding) -> InternalSequence | None:
    return next((s for s in REGISTRATION.source_internal_sequences
                 if (s.owner_id, s.policy_id) == (binding.owner_id, binding.policy_id)), None)


def validate_registered_sockets(binding: AssetBinding) -> None:
    """Reserved internal socket IDs are owner/policy/chain scoped at admission."""
    reserved = {s.socket_id for s in REGISTRATION.support_socket_registrations}
    for socket in binding.sockets:
        if socket.socket_id not in reserved and not socket.socket_id.startswith(('line_', 'cold_')):
            continue
        row = next((r for r in REGISTRATION.support_socket_registrations
                    if (r.owner_id, r.policy_id, r.socket_id) ==
                    (binding.owner_id, binding.policy_id, socket.socket_id)), None)
        require(row is not None and socket.family == row.family and
                socket.motion_function_ids == row.motion_function_ids, 'binding', socket.socket_id)


def validate_feed_lift(feed: InternalFeedBinding, binding: AssetBinding) -> None:
    """An omitted descriptor remains the original static roller contract."""
    lift_id = getattr(feed, 'support_lift_function_id', None)
    if lift_id is None:
        require(not any(f.function_id == 'line_feed_lift' for f in binding.functions), 'binding', feed.id)
        return
    sequence = sequence_for(binding)
    require(sequence is not None, 'binding', feed.id)
    if sequence is None:
        return
    require((lift_id, feed.driver_function_id, feed.custody_socket_id) ==
            (sequence.lift_function_id, sequence.feed_function_id, sequence.feed_socket_id), 'binding', feed.id)
    lift = next((f for f in binding.functions if f.function_id == lift_id), None)
    require(lift is not None and lift.kind == 'translation' and lift.axis == (0, 1, 0)
            and lift.min_value < 0 and lift.max_value == 0, 'binding', feed.id)


@dataclass(frozen=True, slots=True)
class ContactReceipt:
    kind: str
    previous_part_id: str
    current_part_id: str
    previous_m: Vector
    current_m: Vector
    distance_m: float


@dataclass(frozen=True, slots=True)
class FinishingBoundary:
    envelope: MotionEnvelope
    binding: AssetBinding
    root: Pose
    previous: FeedProjection
    current: FeedProjection
    channels: tuple[ChannelValue, ...]


def held(channels: tuple[ChannelValue, ...], function: str, value: float) -> bool:
    channel = next((c for c in channels if c.function_id == function), None)
    return channel is not None and channel.value == value


def same_world(boundary: FinishingBoundary) -> None:
    envelope, a, b = boundary.envelope, boundary.previous, boundary.current
    old, new = envelope.boundary.previous_material, envelope.material
    require((old.material_id, old.material_version_id, old.form, old.dimensions) ==
            (new.material_id, new.material_version_id, new.form, new.dimensions), 'feed_boundary', new.material_id)
    require(dist(a.position_m, b.position_m) <= 1e-6 and
            abs(sum(x*y for x, y in zip(a.orientation_xyzw, b.orientation_xyzw))) >= 1-1e-12,
            'feed_boundary', new.material_id)
    d = new.dimensions
    require(d.length_mm is not None and d.width_mm is not None and d.thickness_mm is not None, 'feed_boundary', new.material_id)
    for x in (-d.length_mm/2000, d.length_mm/2000):
        for y in (-d.thickness_mm/2000, d.thickness_mm/2000):
            for z in (-d.width_mm/2000, d.width_mm/2000):
                require(dist(add(a.position_m, rotate(a.orientation_xyzw, (x, y, z))),
                             add(b.position_m, rotate(b.orientation_xyzw, (x, y, z)))) <= 1e-6,
                        'feed_boundary', new.material_id)


def qualified_contact(boundary: FinishingBoundary) -> ContactReceipt | None:
    """Match physical support points without changing the public COM diagnostic."""
    envelope, binding = boundary.envelope, boundary.binding
    event = envelope.boundary
    sequence = sequence_for(binding)
    if event is None or sequence is None or event.previous_anchor.owner_id != binding.owner_id:
        return None
    old_feed = hasattr(event.previous_material, 'internal_feed')
    new_feed = hasattr(envelope.material, 'internal_feed')
    if old_feed == new_feed:
        return None
    feed_material = event.previous_material if old_feed else envelope.material
    feeds = getattr(binding, 'internal_feeds', ())
    feed = next((f for f in feeds if f.id == feed_material.internal_feed.feed_id), None)
    if feed is None or getattr(feed, 'support_lift_function_id', None) is None:
        return None
    require(envelope.recipe_id == sequence.source_recipe_id, 'binding', envelope.recipe_id)
    validate_feed_lift(feed, binding)
    same_world(boundary)
    for channels in (event.previous_channels, boundary.channels):
        require(held(channels, sequence.lift_function_id, 0) and held(channels, sequence.unwind_function_id, 0), 'binding', feed.id)
    driver = next(f for f in binding.functions if f.function_id == sequence.feed_function_id)
    if new_feed:
        require(event.previous_anchor.socket_id == sequence.strip_socket_id and envelope.anchor.socket_id == sequence.feed_socket_id, 'binding', feed.id)
        socket = next(s for s in binding.sockets if s.socket_id == sequence.strip_socket_id)
        require(socket.family == 'STRIP' and socket.motion_function_ids == (sequence.unwind_function_id,), 'binding', socket.socket_id)
        require(all(held(c, sequence.feed_function_id, driver.min_value) for c in (event.previous_channels, boundary.channels)), 'binding', feed.id)
        candidates = sorted(boundary.current.witnesses,
                            key=lambda w: (dist(boundary.previous.contact_m, w.position_m), w.part_id, w.position_m))
        require(bool(candidates), 'contact', feed.id)
        chosen = candidates[0]
        gap = dist(boundary.previous.contact_m, chosen.position_m)
        require(gap <= .01+1e-12, 'contact', feed.id)
        return ContactReceipt('clamp_to_feed', 'line_unwinding_mandrel_clamp_jaw', chosen.part_id,
                              boundary.previous.contact_m, chosen.position_m, gap)
    require(sequence.cold_entry_socket_id is not None and envelope.anchor.socket_id == sequence.cold_entry_socket_id
            and event.previous_anchor.socket_id == sequence.feed_socket_id, 'binding', feed.id)
    cold = next((f for f in binding.functions if f.function_id == 'cold_reduction_roll'), None)
    require(cold is not None and cold.kind == 'rotation' and cold.axis == (0, 0, -1), 'binding', feed.id)
    if cold is None:
        return None
    for channels in (event.previous_channels, boundary.channels):
        require(held(channels, sequence.feed_function_id, driver.max_value) and held(channels, cold.function_id, 0), 'binding', feed.id)
    material = event.previous_material
    require(material.form == 'STRIP' and material.dimensions.thickness_mm == 4
            and material.dimensions.length_mm == 4000 and material.dimensions.width_mm == 1200, 'feed_boundary', feed.id)
    radius, bite = .36, sqrt(.36**2-(.36-.001)**2)
    point = (cold.pivot_m[0]-bite, cold.pivot_m[1]+radius-.001, cold.pivot_m[2])
    from math import sin, cos
    orientation = (0, sin(boundary.root.yaw_rad/2), 0, cos(boundary.root.yaw_rad/2))
    world = add(boundary.root.position, rotate(orientation, point))
    # Raw-sheet lower face and the held machine barrel must both contain this point.
    center = boundary.previous.position_m
    local = rotate((0, -orientation[1], 0, orientation[3]), tuple(a-b for a, b in zip(world, center)))
    require(abs(local[0]-2) <= 1e-6 and abs(local[1]+.002) <= 1e-6 and abs(local[2]) <= .6,
            'contact', feed.id)
    socket = next(s for s in binding.sockets if s.socket_id == sequence.cold_entry_socket_id)
    require(socket.family == 'STRIP' and not socket.motion_function_ids and dist(socket.position_m, point) <= 1e-9, 'binding', socket.socket_id)
    gap = dist(world, boundary.current.contact_m)
    require(gap <= .01+1e-12, 'contact', feed.id)
    return ContactReceipt('feed_to_cold', 'cold_reduction_roll_barrel', 'cold_reduction_roll_barrel', world, boundary.current.contact_m, gap)
