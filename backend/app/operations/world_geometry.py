"""Meter support-contact geometry and explicit simulation clock conversions."""
from math import cos, dist, sin
from typing import Final

from pydantic import TypeAdapter

from .world_types import NonNegativeInteger, Number, Point, Pose, PositiveNumber, require

EPOCH_MS: Final = 1793318400000
DATE_LIMIT_MS: Final = 8640000000000000
CONTACT_TOLERANCE_M: Final = 0.01
_POINT: Final = TypeAdapter(Point)
_NUMBER: Final = TypeAdapter(Number)
_MS: Final = TypeAdapter(NonNegativeInteger)
_DIMENSION: Final = TypeAdapter(PositiveNumber)


def transform_point(point: Point, pose: Pose) -> Point:
    point = _POINT.validate_python(point)
    c, s = cos(pose.yaw_rad), sin(pose.yaw_rad)
    return _POINT.validate_python((pose.position[0] + c * point[0] + s * point[2],
            pose.position[1] + point[1],
            pose.position[2] - s * point[0] + c * point[2]))


def compose_pose(local: Pose, parent: Pose) -> Pose:
    return Pose(position=transform_point(local.position, parent), yaw_rad=parent.yaw_rad + local.yaw_rad)


def mm_to_m(value: float) -> float:
    return _DIMENSION.validate_python(value) / 1000


def support_pose(socket_world: Point, local_support: Point, yaw_rad: float) -> Pose:
    """Place the material by its support point, allowing body center to change."""
    socket_world = _POINT.validate_python(socket_world)
    rotation = Pose(position=(0, 0, 0), yaw_rad=yaw_rad)
    offset = transform_point(local_support, rotation)
    return Pose(position=tuple(a - b for a, b in zip(socket_world, offset, strict=True)), yaw_rad=yaw_rad)


def contact_distance(material_pose: Pose, local_support: Point, socket_world: Point) -> float:
    return _NUMBER.validate_python(dist(transform_point(local_support, material_pose), _POINT.validate_python(socket_world)))


def contact_within_tolerance(material_pose: Pose, local_support: Point, socket_world: Point) -> bool:
    return contact_distance(material_pose, local_support, socket_world) <= CONTACT_TOLERANCE_M


def business_epoch_ms(sim_ms: int) -> int:
    """Numeric UTC epoch milliseconds through JS Date limit; not a datetime object.

    A future storage adapter must impose its own datetime/database year limit.
    This pure contract never silently narrows the numeric range to Python year9999.
    """
    result = EPOCH_MS + _MS.validate_python(sim_ms) * 60
    require(result <= DATE_LIMIT_MS, 'time_range', str(sim_ms))
    return result


def wall_to_sim_ms(wall_ms: int, speed: int) -> int:
    elapsed, factor = _MS.validate_python(wall_ms), _MS.validate_python(speed)
    require(factor in (1, 2, 4), 'speed', str(speed))
    return _MS.validate_python(elapsed * factor)


def phase_at(sim_ms: int, start_ms: int, end_ms: int) -> float:
    now, start, end = (_MS.validate_python(value) for value in (sim_ms, start_ms, end_ms))
    require(end > start, 'time_interval', f'{start}:{end}')
    return min(1.0, max(0.0, (now - start) / (end - start)))


def inside_envelope(point: Point, pose: Pose, size: Point) -> bool:
    """Inclusive oriented box containment, with no added collision tolerance."""
    delta = tuple(point[index] - pose.position[index] for index in range(3))
    local = transform_point(delta, Pose(position=(0, 0, 0), yaw_rad=-pose.yaw_rad))
    return all(abs(value) <= extent / 2 + 1e-12 for value, extent in zip(local, size, strict=True))
