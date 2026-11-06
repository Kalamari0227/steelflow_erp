"""Deterministic tangent line/circular-arc trajectories shared by admission and T15.

Circular arcs remain analytic primitives. Conservative chord bounds carry sagitta
into clearance tests; drawing samples are never the collision proof.
"""
from dataclasses import dataclass
from functools import lru_cache
from math import acos, atan2, ceil, cos, dist, hypot, pi, sin, tan
from typing import TypeAlias

from .world_types import Point, require


@dataclass(frozen=True, slots=True)
class Line:
    start: Point
    end: Point

    @property
    def length(self) -> float:
        return dist(self.start, self.end)


@dataclass(frozen=True, slots=True)
class Arc:
    start: Point
    end: Point
    center: Point
    radius: float
    angle: float

    @property
    def length(self) -> float:
        return self.radius * abs(self.angle)

    def at(self, fraction: float) -> Point:
        theta = atan2(self.start[2] - self.center[2], self.start[0] - self.center[0])
        theta += self.angle * fraction
        return (self.center[0] + self.radius * cos(theta), self.center[1],
                self.center[2] + self.radius * sin(theta))


Primitive: TypeAlias = Line | Arc


@dataclass(frozen=True, slots=True)
class Trajectory:
    primitives: tuple[Primitive, ...]
    radius_m: float

    @property
    def length(self) -> float:
        return sum(part.length for part in self.primitives)

    @lru_cache(maxsize=4096)
    def bounded_chords(self, error_m: float = .02) -> tuple[tuple[Line, float], ...]:
        """Every arc lies within error_m of chords, included in swept inflation."""
        require(error_m > 0, 'trajectory_error_bound', str(error_m))
        result: list[tuple[Line, float]] = []
        for part in self.primitives:
            match part:
                case Line():
                    result.append((part, 0.0))
                case Arc():
                    max_angle = 2 * acos(max(-1.0, 1 - error_m / part.radius))
                    count = max(1, ceil(abs(part.angle) / max_angle))
                    sagitta = part.radius * (1 - cos(abs(part.angle) / count / 2))
                    result.extend((Line(part.at(i / count), part.at((i + 1) / count)), sagitta)
                                  for i in range(count))
        return tuple(result)


def fillet_trajectory(points: tuple[Point, ...], radius_m: float) -> Trajectory:
    """Reject short tangents/U-turns; never fall back to an angular corner.

Call on concatenated route points to cover segment junctions as well as corners.
Reversals are separate stopped maneuvers and must be split by the caller.
"""
    require(radius_m >= 0, 'turn_radius', str(radius_m))
    clean = tuple(p for i, p in enumerate(points) if i == 0 or dist(p, points[i - 1]) > 1e-9)
    reduced: list[Point] = []
    for point in clean:
        while len(reduced) >= 2:
            a, b = reduced[-2:]
            u = tuple(b[i] - a[i] for i in range(3))
            v = tuple(point[i] - b[i] for i in range(3))
            collinear = dist(a, point) >= dist(a, b) + dist(b, point) - 1e-8
            if not collinear:
                break
            reduced.pop()
        reduced.append(point)
    clean = tuple(reduced)
    require(len(clean) >= 2, 'trajectory_points', str(len(clean)))
    turns: dict[int, Arc] = {}
    trims: dict[int, float] = {}
    for i in range(1, len(clean) - 1):
        a, b, c = clean[i - 1:i + 2]
        incoming = (b[0] - a[0], b[2] - a[2])
        outgoing = (c[0] - b[0], c[2] - b[2])
        la, lb = hypot(*incoming), hypot(*outgoing)
        require(la > 0 and lb > 0, 'vertical_trajectory', str(i))
        u, v = (incoming[0] / la, incoming[1] / la), (outgoing[0] / lb, outgoing[1] / lb)
        dot = max(-1., min(1., u[0] * v[0] + u[1] * v[1]))
        angle = acos(dot)
        if angle < 1e-8:
            continue
        require(abs(a[1] - b[1]) < 1e-8 and abs(c[1] - b[1]) < 1e-8,
                'graded_turn', str(i))
        require(angle < pi - 1e-6, 'turn_reversal', str(i))
        require(radius_m > 0, 'turn_radius', str(i))
        tangent = radius_m * tan(angle / 2)
        require(tangent <= min(la, lb) + 1e-8, 'turn_tangent', str(i))
        sign = 1 if u[0] * v[1] - u[1] * v[0] > 0 else -1
        start = (b[0] - u[0] * tangent, b[1], b[2] - u[1] * tangent)
        end = (b[0] + v[0] * tangent, b[1], b[2] + v[1] * tangent)
        center = (start[0] - u[1] * sign * radius_m, b[1], start[2] + u[0] * sign * radius_m)
        turns[i] = Arc(start, end, center, radius_m, sign * angle)
        trims[i] = tangent
    parts: list[Primitive] = []
    for i in range(len(clean) - 1):
        require(trims.get(i, 0) + trims.get(i + 1, 0) <= dist(clean[i], clean[i + 1]) + 1e-8,
                'adjacent_turn_tangents', str(i))
        start = turns[i].end if i in turns else clean[i]
        end = turns[i + 1].start if i + 1 in turns else clean[i + 1]
        if dist(start, end) > 1e-8:
            parts.append(Line(start, end))
        if i + 1 in turns:
            parts.append(turns[i + 1])
    return Trajectory(tuple(parts), radius_m)
