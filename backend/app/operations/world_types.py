"""Strict, immutable factory-v2 spatial records; independent of legacy scene units."""
from dataclasses import FrozenInstanceError, dataclass
from math import isfinite
from typing import Annotated, Final, Literal, NewType

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field
from pydantic_core import PydanticCustomError

SAFE_INTEGER: Final = 9007199254740991
EntityId = NewType('EntityId', str)
Meters = NewType('Meters', float)
Kilograms = NewType('Kilograms', int)
SimMilliseconds = NewType('SimMilliseconds', int)


@dataclass(slots=True, unsafe_hash=True)  # noqa: MUTABLE_OK
class WorldContractError(ValueError):
    """Keep payload immutable while allowing Python exception state to change."""
    code: str
    reference: str

    def __setattr__[T](self, name: str, value: T) -> None:
        if name in ('code', 'reference') and hasattr(self, name):
            raise FrozenInstanceError(f'cannot assign to field {name!r}')
        ValueError.__setattr__(self, name, value)

    def __delattr__(self, name: str) -> None:
        if name in ('code', 'reference'):
            raise FrozenInstanceError(f'cannot delete field {name!r}')
        ValueError.__delattr__(self, name)

    def __str__(self) -> str:
        return f'{self.code}: {self.reference}'


def require(condition: bool, code: str, reference: str) -> None:
    if not condition:
        raise WorldContractError(code, reference)


def json_integer(value: int | float | str | bool | None) -> int:
    """Match JSON/JS integral numbers, including 2.0, without coercing bool/string."""
    if type(value) not in (int, float):
        raise PydanticCustomError('safe_integer', 'Expected a safe integral JSON number')
    if abs(value) > SAFE_INTEGER or not isfinite(value) or value != int(value):
        raise PydanticCustomError('safe_integer', 'Expected a safe integral JSON number')
    return int(value)


Integer = Annotated[int, BeforeValidator(json_integer)]
PositiveInteger = Annotated[Integer, Field(gt=0, le=SAFE_INTEGER)]
NonNegativeInteger = Annotated[Integer, Field(ge=0, le=SAFE_INTEGER)]
Number = Annotated[float, Field(strict=True, allow_inf_nan=False)]
PositiveNumber = Annotated[Number, Field(gt=0)]
Id = Annotated[EntityId, Field(strict=True, pattern=r'^[A-Za-z0-9][A-Za-z0-9_.:-]*$')]
LocationId = Annotated[EntityId, Field(strict=True, pattern=r'^v2:[A-Za-z0-9][A-Za-z0-9_.:-]*$')]
Point = tuple[Number, Number, Number]
Size = tuple[PositiveNumber, PositiveNumber, PositiveNumber]
Mode = Literal['road', 'rail', 'hot_metal', 'ladle', 'roller', 'conveyor', 'sea']
Modes = Annotated[tuple[Mode, ...], Field(min_length=1)]


class Record(BaseModel):
    model_config = ConfigDict(frozen=True, extra='forbid', allow_inf_nan=False)


class Pose(Record):
    position: Point
    yaw_rad: Number


class Socket(Record):
    id: Id
    pose: Pose


class Owner(Record):
    id: Id
    kind: Literal['equipment', 'vehicle', 'railcar', 'ship', 'hook', 'customer']
    pose: Pose
    sockets: Annotated[tuple[Socket, ...], Field(min_length=1)]
    modes: Modes


class Node(Record):
    id: LocationId
    position: Point
    modes: Modes


class Segment(Record):
    id: Id
    from_node_id: LocationId
    to_node_id: LocationId
    mode: Mode
    points: Annotated[tuple[Point, ...], Field(min_length=2)]
    conflict_zone_ids: tuple[Id, ...]
    speed_m_per_sim_s: PositiveNumber


class ConflictZone(Record):
    id: Id
    segment_ids: Annotated[tuple[Id, ...], Field(min_length=1)]


class Slot(Record):
    id: LocationId
    owner_id: Id
    socket_id: Id
    node_id: LocationId
    capacity_kg: Annotated[Kilograms, BeforeValidator(json_integer), Field(gt=0, le=SAFE_INTEGER)]


class Port(Slot):
    modes: Modes


class Footprint(Record):
    id: Id
    owner_id: Id
    pose: Pose
    size_m: Size


class AllowedInteriorEnvelope(Footprint):
    footprint_id: Id


class WorldRecords(Record):
    version: Annotated[Literal[2], BeforeValidator(json_integer)]
    units: Literal['m']
    up_axis: Literal['Y']
    forward_axis: Literal['+X']
    yaw_unit: Literal['rad']
    nodes: Annotated[tuple[Node, ...], Field(min_length=1)]
    segments: tuple[Segment, ...]
    conflict_zones: tuple[ConflictZone, ...]
    owners: Annotated[tuple[Owner, ...], Field(min_length=1)]
    slots: tuple[Slot, ...]
    ports: tuple[Port, ...]
    footprints: Annotated[tuple[Footprint, ...], Field(min_length=1)]
    allowed_interiors: tuple[AllowedInteriorEnvelope, ...]
