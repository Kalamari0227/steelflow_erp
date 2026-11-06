"""Shared physical layout boundary, independent of simulation and rendering state."""
from math import cos, dist, sin
from pathlib import Path
from typing import Annotated, Final, Literal, Self, assert_never

from pydantic import BaseModel, ConfigDict, Field, model_validator

Point = tuple[float, float, float]
Identifier = Annotated[str, Field(min_length=1)]
PositiveInt = Annotated[int, Field(gt=0, strict=True)]
Mode = Literal['flatbed', 'hot_metal_car', 'ladle_car', 'roller', 'ship']
Network = Literal['road', 'rail', 'roller', 'sea']
NETWORKS: Final = {'flatbed': 'road', 'hot_metal_car': 'rail', 'ladle_car': 'rail', 'roller': 'roller', 'ship': 'sea'}
ENDPOINT_TOLERANCE: Final = 0.01
LAYOUT_PATH: Final = Path(__file__).resolve().parents[3] / 'shared' / 'factory-layout.json'


class LayoutError(ValueError):
    def __init__(self, code: str, reference: str) -> None:
        self.code, self.reference = code, reference
        super().__init__(f'{code}: {reference}')


class LayoutRecord(BaseModel):
    model_config = ConfigDict(frozen=True, extra='forbid', allow_inf_nan=False)


class Transform(LayoutRecord):
    position: Point
    rotation: float


class Stage(Transform):
    id: Identifier


class Anchor(LayoutRecord):
    location_id: Identifier
    position: Point


class Anchors(LayoutRecord):
    entry: Anchor
    work: Anchor
    exit: Anchor
    buffer: Anchor

    def values(self) -> tuple[Anchor, ...]:
        return self.entry, self.work, self.exit, self.buffer


class Capability(LayoutRecord):
    input_forms: Annotated[tuple[Identifier, ...], Field(min_length=1)]
    output_forms: Annotated[tuple[Identifier, ...], Field(min_length=1)]
    material_family: Literal['carbon', 'stainless', 'titanium']
    grade_scope: Literal['fixture']
    width_mm: tuple[Annotated[float, Field(ge=0)], Annotated[float, Field(gt=0)]]


class Equipment(Transform):
    id: Identifier
    stage_id: Identifier
    kind: Identifier
    anchors: Anchors
    capacity_kg: PositiveInt
    concurrency: Literal[1]
    reserve: bool
    capability: Capability


class Location(LayoutRecord):
    id: Identifier
    position: Point
    owner_id: Identifier


class Crane(LayoutRecord):
    id: Identifier
    location_id: Identifier
    pick_location_id: Identifier
    drop_location_id: Identifier
    capacity_kg: PositiveInt


class Vehicle(LayoutRecord):
    id: Identifier
    mode: Mode
    network: Network
    capacity_kg: PositiveInt
    cargo_anchor: Point
    location_id: Identifier


class TransferPath(LayoutRecord):
    id: Identifier
    from_location_id: Identifier
    to_location_id: Identifier
    mode: Mode
    network: Network
    vehicle_id: Identifier | None
    pickup_crane_id: Identifier | None
    drop_crane_id: Identifier | None
    custody_location_id: Identifier | None = None
    points: Annotated[tuple[Point, ...], Field(min_length=2)]


class SourceBinding(LayoutRecord):
    source_step_id: Identifier
    equipment_id: Identifier


class SpatialRoute(LayoutRecord):
    product_id: Identifier
    equipment_ids: Annotated[tuple[Identifier, ...], Field(min_length=2)]
    path_ids: Annotated[tuple[Identifier, ...], Field(min_length=1)]


def transform_point(point: Point, pose: Transform) -> Point:
    c, s = cos(pose.rotation), sin(pose.rotation)
    return (pose.position[0] + c * point[0] + s * point[2], pose.position[1] + point[1], pose.position[2] - s * point[0] + c * point[2])


def require(condition: bool, code: str, reference: str) -> None:
    if not condition:
        raise LayoutError(code, reference)


def unique(values: tuple[str, ...], label: str) -> None:
    require(len(values) == len(set(values)), 'duplicate', label)


class FactoryLayout(LayoutRecord):
    version: Literal[1]
    units: Literal['scene']
    stages: Annotated[tuple[Stage, ...], Field(min_length=1)]
    equipment: Annotated[tuple[Equipment, ...], Field(min_length=1)]
    locations: Annotated[tuple[Location, ...], Field(min_length=1)]
    cranes: tuple[Crane, ...]
    vehicles: tuple[Vehicle, ...]
    paths: tuple[TransferPath, ...]
    source_bindings: tuple[SourceBinding, ...]
    routes: Annotated[tuple[SpatialRoute, ...], Field(min_length=1)]

    @model_validator(mode='after')
    def connected_layout(self) -> Self:
        """Reject broken references and physical handoffs at the JSON boundary."""
        for label in ('stages', 'equipment', 'locations', 'cranes', 'vehicles', 'paths'):
            unique(tuple(item.id for item in getattr(self, label)), label)
        unique(tuple(item.source_step_id for item in self.source_bindings), 'source_step_id')
        unique(tuple(item.product_id for item in self.routes), 'product_id')
        stages = {item.id: item for item in self.stages}
        equipment = {item.id: item for item in self.equipment}
        locations = {item.id: item for item in self.locations}
        vehicles = {item.id: item for item in self.vehicles}
        cranes = {item.id: item for item in self.cranes}
        paths = {item.id: item for item in self.paths}
        anchor_ids: list[str] = []
        for item in self.equipment:
            require(item.stage_id in stages, 'missing stage', item.id)
            require(item.capability.width_mm[0] < item.capability.width_mm[1], 'invalid width range', item.id)
            for anchor in item.anchors.values():
                anchor_ids.append(anchor.location_id)
                location = locations.get(anchor.location_id)
                expected = transform_point(transform_point(anchor.position, item), stages[item.stage_id])
                require(location is not None and location.owner_id == item.id and dist(location.position, expected) < ENDPOINT_TOLERANCE, 'invalid anchor', item.id)
        unique(tuple(anchor_ids), 'anchor location')
        for item in self.locations:
            path = paths.get(item.owner_id)
            require(item.owner_id in equipment or item.owner_id in vehicles or item.owner_id in cranes or (path is not None and path.mode == 'roller' and path.custody_location_id == item.id), 'missing location owner', item.id)
        for binding in self.source_bindings:
            require(binding.equipment_id in equipment, 'missing source equipment', binding.source_step_id)
        for crane in self.cranes:
            location = locations.get(crane.location_id)
            require(crane.pick_location_id in locations and crane.drop_location_id in locations and location is not None and location.owner_id == crane.id, 'missing crane anchor', crane.id)
        for vehicle in self.vehicles:
            location = locations.get(vehicle.location_id)
            require(location is not None and location.owner_id == vehicle.id and vehicle.mode != 'roller' and NETWORKS[vehicle.mode] == vehicle.network, 'invalid vehicle', vehicle.id)
        for path in self.paths:
            source, destination = locations.get(path.from_location_id), locations.get(path.to_location_id)
            require(source is not None and destination is not None and dist(path.points[0], source.position) < ENDPOINT_TOLERANCE and dist(path.points[-1], destination.position) < ENDPOINT_TOLERANCE, 'disconnected path', path.id)
            require(any(dist(point, path.points[0]) >= ENDPOINT_TOLERANCE for point in path.points), 'zero length path', path.id)
            require(NETWORKS[path.mode] == path.network, 'invalid path network', path.id)
            if path.custody_location_id is not None:
                custody = locations.get(path.custody_location_id)
                require(path.mode == 'roller' and custody is not None and custody.owner_id == path.id and any(dist(custody.position, point) < ENDPOINT_TOLERANCE for point in path.points[1:-1]), 'invalid roller custody', path.id)
            producer = equipment.get(source.owner_id) if source else None
            forms = producer.capability.output_forms if producer else ()
            require(('HOT_METAL' not in forms or path.mode == 'hot_metal_car') and ('LIQUID_STEEL' not in forms or path.mode == 'ladle_car'), 'molten material requires rail carrier', path.id)
            match path.mode:
                case 'roller':
                    require(path.vehicle_id is None and path.pickup_crane_id is None and path.drop_crane_id is None, 'roller cannot use vehicle/crane', path.id)
                case 'flatbed' | 'hot_metal_car' | 'ladle_car' | 'ship':
                    vehicle = vehicles.get(path.vehicle_id or '')
                    pick, drop = cranes.get(path.pickup_crane_id or ''), cranes.get(path.drop_crane_id or '')
                    require(vehicle is not None and vehicle.mode == path.mode and vehicle.network == path.network, 'invalid vehicle path', path.id)
                    require(pick is not None and drop is not None and pick.pick_location_id == path.from_location_id and drop.drop_location_id == path.to_location_id, 'invalid crane handoff', path.id)
                    producer = equipment.get(source.owner_id) if source else None
                    require(producer is None or (vehicle is not None and pick is not None and drop is not None and min(vehicle.capacity_kg, pick.capacity_kg, drop.capacity_kg) >= producer.capacity_kg), 'insufficient transfer capacity', path.id)
                    require(producer is None or not set(producer.capability.output_forms).intersection(('HOT_STRIP', 'STRIP', 'THIN_STRIP', 'COATED_STRIP', 'WIRE')), 'strip requires roller', path.id)
                case unreachable:
                    assert_never(unreachable)
        for route in self.routes:
            require(len(route.path_ids) == len(route.equipment_ids) - 1, 'incomplete route', route.product_id)
            require(all(eid in equipment for eid in route.equipment_ids), 'missing route equipment', route.product_id)
            for a, b, pid in zip(route.equipment_ids, route.equipment_ids[1:], route.path_ids, strict=False):
                path = paths.get(pid)
                require(path is not None and path.from_location_id in (equipment[a].anchors.exit.location_id, equipment[a].anchors.buffer.location_id) and path.to_location_id == equipment[b].anchors.entry.location_id, 'disconnected route', route.product_id)
        return self


def load_factory_layout(path: Path = LAYOUT_PATH) -> FactoryLayout:
    return FactoryLayout.model_validate_json(path.read_text(encoding='utf-8'))
