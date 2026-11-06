"""Immutable spatial design metadata; physical admission is a separate boundary."""
from typing import Annotated, Literal

from pydantic import BeforeValidator, Field, StrictBool

from .world_types import (Id, LocationId, Mode, Number, PositiveInteger,
                          PositiveNumber, Record, Size, Point, WorldRecords, json_integer, require)

Ids = tuple[Id, ...]
NonEmptyIds = Annotated[Ids, Field(min_length=1)]
Locations = Annotated[tuple[LocationId, ...], Field(min_length=1)]
NonNegativeNumber = Annotated[Number, Field(ge=0)]
Label = Annotated[str, Field(strict=True, min_length=1)]


class SpatialZone(Record):
    id: Id
    name: Label
    owner_ids: Ids


class SpatialHall(Record):
    id: Id
    zone_id: Id
    footprint_id: Id


class SpatialOpening(Record):
    id: Id
    hall_id: Id
    interior_id: Id
    node_id: LocationId
    width_m: PositiveNumber
    height_m: PositiveNumber
    mode: Mode
    profile_ids: NonEmptyIds


class DesignProfile(Record):
    id: Id
    kind: Literal['truck', 'slab-carrier', 'coil-carrier', 'forklift', 'torpedo',
                  'ladle-car', 'locomotive', 'railcar', 'ship', 'conveyor', 'roller']
    mode: Mode
    size_m: Size
    load_size_m: Size
    body_offset_m: Point
    load_offset_m: Point
    clearance_m: NonNegativeNumber
    min_turn_radius_m: NonNegativeNumber
    consist_length_m: PositiveNumber
    reverse_allowed: StrictBool


class SegmentPolicy(Record):
    id: Id
    segment_id: Id
    width_m: PositiveNumber
    height_m: PositiveNumber
    profile_ids: NonEmptyIds
    stop_ids: Ids
    rail_block_ids: Ids
    berth_ids: Ids


class InteriorAccess(Record):
    id: Id
    interior_id: Id
    opening_ids: NonEmptyIds
    segment_ids: NonEmptyIds
    profile_ids: NonEmptyIds
    mode: Mode


class SpatialStop(Record):
    id: Id
    node_id: LocationId
    kind: Literal['stop', 'gate', 'staging', 'holding', 'loading', 'unloading']
    profile_ids: NonEmptyIds


class RailBlock(Record):
    id: Id
    segment_ids: NonEmptyIds
    usable_length_m: PositiveNumber
    clearance_m: NonNegativeNumber
    reverse_allowed: StrictBool


class SpatialBerth(Record):
    id: Id
    segment_ids: NonEmptyIds
    port_ids: Locations
    usable_length_m: PositiveNumber
    depth_m: PositiveNumber


class CraneReach(Record):
    id: Id
    owner_id: Id
    socket_id: Id
    pick_port_ids: Locations
    drop_port_ids: Locations
    max_radius_m: PositiveNumber
    min_height_m: Number
    max_height_m: Number


class SpatialParking(Record):
    id: Id
    slot_id: LocationId
    profile_id: Id
    capacity_positions: PositiveInteger


class SpatialCoverage(Record):
    id: Id
    kind: Literal['equipment', 'stage', 'hall', 'source_function', 'compiled_step',
                  'connection', 'asset_kind']
    source_id: Label
    product_ids: Ids
    owner_id: Id
    socket_id: Id
    port_ids: tuple[LocationId, ...]
    segment_ids: Ids


class SpatialRoute(Record):
    id: Id
    profile_id: Id
    kind: Literal['loaded', 'empty_return', 'holding']
    from_node_id: LocationId
    to_node_id: LocationId
    segment_ids: NonEmptyIds


class SpatialRecords(Record):
    schema_version: Annotated[Literal[1], BeforeValidator(json_integer)]
    zones: tuple[SpatialZone, ...]
    halls: tuple[SpatialHall, ...]
    openings: tuple[SpatialOpening, ...]
    profiles: tuple[DesignProfile, ...]
    segment_policies: tuple[SegmentPolicy, ...]
    interior_access: tuple[InteriorAccess, ...]
    stops: tuple[SpatialStop, ...]
    rail_blocks: tuple[RailBlock, ...]
    berths: tuple[SpatialBerth, ...]
    crane_reaches: tuple[CraneReach, ...]
    parking: tuple[SpatialParking, ...]
    coverage: tuple[SpatialCoverage, ...]
    routes: tuple[SpatialRoute, ...]


def validate_spatial(spatial: SpatialRecords, world: WorldRecords) -> None:
    """Check references and movement semantics without claiming geometric clearance."""
    def unique(values: tuple[str, ...], label: str) -> None:
        require(len(set(values)) == len(values), 'duplicate', label)

    def index(rows):
        unique(tuple(row.id for row in rows), 'spatial record id')
        return {row.id: row for row in rows}

    def get(rows, key):
        require(key in rows, 'reference', key)
        return rows[key]

    nodes, owners, segments = index(world.nodes), index(world.owners), index(world.segments)
    footprints, interiors = index(world.footprints), index(world.allowed_interiors)
    slots, ports = index(world.slots), index(world.ports)
    zones, halls, openings = index(spatial.zones), index(spatial.halls), index(spatial.openings)
    profiles, stops = index(spatial.profiles), index(spatial.stops)
    blocks, berths = index(spatial.rail_blocks), index(spatial.berths)
    for name in type(spatial).model_fields:
        if name == 'schema_version':
            continue
        rows = getattr(spatial, name)
        index(rows)
        for row in rows:
            for field in type(row).model_fields:
                values = getattr(row, field)
                if field.endswith('_ids') and not (name == 'routes' and field == 'segment_ids'):
                    unique(values, row.id)
    expected_modes = {'truck': 'road', 'slab-carrier': 'road', 'coil-carrier': 'road',
                      'forklift': 'road', 'torpedo': 'hot_metal', 'ladle-car': 'ladle',
                      'locomotive': 'rail', 'railcar': 'rail', 'ship': 'sea',
                      'conveyor': 'conveyor', 'roller': 'roller'}
    for profile in spatial.profiles:
        require(profile.mode == expected_modes[profile.kind], 'mode', profile.id)
        require(profile.consist_length_m >= profile.size_m[0], 'dimension', profile.id)
    for zone in spatial.zones:
        for owner_id in zone.owner_ids:
            get(owners, owner_id)
    unique(tuple(hall.footprint_id for hall in spatial.halls), 'hall footprint')
    for hall in spatial.halls:
        zone, footprint = get(zones, hall.zone_id), get(footprints, hall.footprint_id)
        require(footprint.owner_id in zone.owner_ids, 'reference', hall.id)
    for opening in spatial.openings:
        hall, interior = get(halls, opening.hall_id), get(interiors, opening.interior_id)
        require(interior.footprint_id == hall.footprint_id, 'reference', opening.id)
        require(opening.mode in get(nodes, opening.node_id).modes, 'mode', opening.id)
        for profile_id in opening.profile_ids:
            require(get(profiles, profile_id).mode == opening.mode, 'mode', opening.id)
    for stop in spatial.stops:
        node = get(nodes, stop.node_id)
        for profile_id in stop.profile_ids:
            require(get(profiles, profile_id).mode in node.modes, 'mode', stop.id)
    for block in spatial.rail_blocks:
        modes = {get(segments, key).mode for key in block.segment_ids}
        require(len(modes) == 1 and modes <= {'rail', 'hot_metal', 'ladle'}, 'mode', block.id)
    for berth in spatial.berths:
        for key in berth.segment_ids:
            require(get(segments, key).mode == 'sea', 'mode', berth.id)
        for key in berth.port_ids:
            require('sea' in get(ports, key).modes, 'mode', berth.id)
    unique(tuple(policy.segment_id for policy in spatial.segment_policies), 'segment policy')
    for policy in spatial.segment_policies:
        segment = get(segments, policy.segment_id)
        for key in policy.profile_ids:
            require(get(profiles, key).mode == segment.mode, 'mode', policy.id)
        for key in policy.stop_ids:
            stop = get(stops, key)
            require(stop.node_id in (segment.from_node_id, segment.to_node_id), 'reference', policy.id)
            require(set(policy.profile_ids) <= set(stop.profile_ids), 'reference', policy.id)
        for key in policy.rail_block_ids:
            require(segment.id in get(blocks, key).segment_ids, 'reference', policy.id)
        for key in policy.berth_ids:
            require(segment.id in get(berths, key).segment_ids, 'reference', policy.id)
    for access in spatial.interior_access:
        get(interiors, access.interior_id)
        endpoints = set()
        for key in access.segment_ids:
            segment = get(segments, key)
            require(segment.mode == access.mode, 'mode', access.id)
            endpoints.update((segment.from_node_id, segment.to_node_id))
        for key in access.profile_ids:
            require(get(profiles, key).mode == access.mode, 'mode', access.id)
        for key in access.opening_ids:
            opening = get(openings, key)
            require(opening.interior_id == access.interior_id and opening.node_id in endpoints, 'reference', access.id)
            require(opening.mode == access.mode, 'mode', access.id)
            require(set(access.profile_ids) <= set(opening.profile_ids), 'reference', access.id)
    for reach in spatial.crane_reaches:
        owner = get(owners, reach.owner_id)
        require(owner.kind in ('equipment', 'hook'), 'reference', reach.id)
        get(index(owner.sockets), reach.socket_id)
        require(reach.max_height_m >= reach.min_height_m, 'dimension', reach.id)
        for key in (*reach.pick_port_ids, *reach.drop_port_ids):
            get(ports, key)
    unique(tuple(parking.slot_id for parking in spatial.parking), 'parking slot')
    for parking in spatial.parking:
        slot, profile = get(slots, parking.slot_id), get(profiles, parking.profile_id)
        require(profile.mode in get(nodes, slot.node_id).modes, 'mode', parking.id)
    for coverage in spatial.coverage:
        owner = get(owners, coverage.owner_id)
        get(index(owner.sockets), coverage.socket_id)
        for key in coverage.port_ids:
            get(ports, key)
        for key in coverage.segment_ids:
            get(segments, key)
    for route in spatial.routes:
        profile = get(profiles, route.profile_id)
        require(profile.mode in get(nodes, route.from_node_id).modes and
                profile.mode in get(nodes, route.to_node_id).modes, 'mode', route.id)
        current = route.from_node_id
        for key in route.segment_ids:
            segment = get(segments, key)
            require(segment.mode == profile.mode, 'mode', route.id)
            require(segment.from_node_id == current, 'endpoint', route.id)
            current = segment.to_node_id
        require(current == route.to_node_id, 'endpoint', route.id)
