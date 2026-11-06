"""Factory-v2 JSON boundary and graph consistency; no legacy layout imports."""
import json
from itertools import product
from math import dist
from typing import Self, TypeAlias, assert_never

from pydantic import SerializerFunctionWrapHandler, field_validator, model_serializer, model_validator

from .world_geometry import compose_pose, inside_envelope, transform_point
from .world_types import WorldContractError, WorldRecords, require
from .world_spatial_types import SpatialRecords, validate_spatial

JsonValue: TypeAlias = str | int | float | bool | None | list['JsonValue'] | dict[str, 'JsonValue']


def unique(values: tuple[str, ...], label: str) -> None:
    require(len(values) == len(set(values)), 'duplicate', label)


def json_pairs(pairs: list[tuple[str, JsonValue]]) -> dict[str, JsonValue]:
    """Reject duplicate members before JSON parsing can silently discard them."""
    unique(tuple(key for key, _ in pairs), 'JSON member')
    return dict(pairs)


def reject_constant(value: str) -> JsonValue:
    raise WorldContractError('json', value)


def read_json(raw: str | bytes) -> JsonValue:
    """Decode strict UTF-8 bytes with at most one BOM; preserve strict text grammar."""
    try:
        match raw:
            case bytes():
                text = raw.decode('utf-8-sig', errors='strict')
            case str():
                text = raw
            case unreachable:
                assert_never(unreachable)
        return json.loads(text, object_pairs_hook=json_pairs, parse_constant=reject_constant)
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        raise WorldContractError('json', str(error)) from error


class FactoryWorld(WorldRecords):
    spatial: SpatialRecords | None = None

    @field_validator("spatial", mode="before", json_schema_input_type=SpatialRecords)
    @classmethod
    def present_spatial(cls, value):
        require(value is not None, "spatial", "null")
        return value

    @model_serializer(mode='wrap')
    def serialize_world(self, handler: SerializerFunctionWrapHandler) -> dict[str, object]:
        result = handler(self)
        if self.spatial is None:
            result.pop('spatial', None)
        return result

    @model_validator(mode='after')
    def connected_world(self) -> Self:
        """Reject ambiguous ownership, disconnected paths and incompatible movement."""
        for rows in (self.nodes, self.segments, self.conflict_zones, self.owners,
                     self.slots, self.ports, self.footprints, self.allowed_interiors):
            unique(tuple(row.id for row in rows), 'record id')
        unique(tuple(row.id for rows in (self.nodes, self.slots, self.ports) for row in rows), 'location id')
        nodes = {row.id: row for row in self.nodes}
        owners = {row.id: row for row in self.owners}
        segments = {row.id: row for row in self.segments}
        zones = {row.id: row for row in self.conflict_zones}
        footprints = {row.id: row for row in self.footprints}
        for owner in self.owners:
            unique(tuple(socket.id for socket in owner.sockets), owner.id)
            unique(owner.modes, owner.id)
            compatible = {'ship': {'sea'}, 'railcar': {'rail', 'hot_metal', 'ladle'},
                          'vehicle': {'road', 'rail', 'hot_metal', 'ladle'},
                          'equipment': set(owner.modes), 'hook': set(owner.modes),
                          'customer': set(owner.modes)}
            require(set(owner.modes) <= compatible[owner.kind], 'mode', owner.id)
            require(any(row.owner_id == owner.id for row in self.footprints), 'reference', owner.id)
        for node in self.nodes:
            unique(node.modes, node.id)
        for segment in self.segments:
            require(segment.from_node_id in nodes and segment.to_node_id in nodes, 'reference', segment.id)
            source, target = nodes[segment.from_node_id], nodes[segment.to_node_id]
            require(source.id != target.id, 'endpoint', segment.id)
            require(segment.mode in source.modes and segment.mode in target.modes, 'mode', segment.id)
            require(dist(source.position, segment.points[0]) <= .01 and
                    dist(target.position, segment.points[-1]) <= .01, 'endpoint', segment.id)
            require(any(dist(segment.points[0], point) > 0 for point in segment.points[1:]), 'endpoint', segment.id)
            unique(segment.conflict_zone_ids, segment.id)
            for zone_id in segment.conflict_zone_ids:
                require(zone_id in zones and segment.id in zones[zone_id].segment_ids, 'reference', segment.id)
        for zone in self.conflict_zones:
            unique(zone.segment_ids, zone.id)
            for segment_id in zone.segment_ids:
                require(segment_id in segments and zone.id in segments[segment_id].conflict_zone_ids, 'reference', zone.id)
        for location in (*self.slots, *self.ports):
            require(location.owner_id in owners and location.node_id in nodes, 'reference', location.id)
            owner, node = owners[location.owner_id], nodes[location.node_id]
            sockets = {socket.id: socket for socket in owner.sockets}
            require(location.socket_id in sockets, 'reference', location.id)
            world_socket = compose_pose(sockets[location.socket_id].pose, owner.pose)
            require(dist(world_socket.position, node.position) <= .01, 'contact', location.id)
            require(set(node.modes) <= set(owner.modes), 'mode', location.id)
        for port in self.ports:
            unique(port.modes, port.id)
            require(set(port.modes) <= set(nodes[port.node_id].modes), 'mode', port.id)
        for footprint in self.footprints:
            require(footprint.owner_id in owners, 'reference', footprint.id)
        for envelope in self.allowed_interiors:
            require(envelope.footprint_id in footprints, 'reference', envelope.id)
            footprint = footprints[envelope.footprint_id]
            require(envelope.owner_id == footprint.owner_id, 'reference', envelope.id)
            for signs in product((-1, 1), repeat=3):
                corner = tuple(sign * size / 2 for sign, size in zip(signs, envelope.size_m, strict=True))
                require(inside_envelope(transform_point(corner, envelope.pose), footprint.pose, footprint.size_m), 'envelope', envelope.id)
        if self.spatial is not None:
            validate_spatial(self.spatial, self)
        return self


def parse_world(raw: str | bytes) -> FactoryWorld:
    return FactoryWorld.model_validate(read_json(raw))
