"""Deterministic demonstration travel time owned by the simulation clock.

Scene units and simulated milliseconds are illustrative scale units, not metres,
real vehicle speeds, or a claim about an operating steelworks. Longer polylines
increase duration; no upper duration cap can make a long trip move faster.
"""
from math import ceil, dist
from typing import Literal

from app.operations import contracts as c
from app.operations.layout import FactoryLayout, Point, TransferPath


def path_length(points: tuple[Point, ...]) -> float:
    return sum(dist(a, b) for a, b in zip(points, points[1:]))


def travel_duration_ms(path: TransferPath, *, tail: Point | None = None) -> c.Milliseconds:
    """Round up to a 100ms boundary, with a three-second minimum carrier leg."""
    if path.mode == 'roller':
        # Every nonzero roller gap has timed exclusive custody. Preserve the
        # reserve branch's explicit five-second routing contract.
        return c.Milliseconds(5000 if path.id == 'PATH-HSM-A--HSM-B' else max(1000, ceil(path_length(path.points) / 20 * 10) * 100))
    speed = {'flatbed': 20, 'hot_metal_car': 8, 'ladle_car': 8, 'ship': 10}[path.mode]
    points = path.points + (tail,) if tail is not None else path.points
    return c.Milliseconds(max(3000, ceil(path_length(points) * 10 / speed) * 100))


def shipment_duration_ms(layout: FactoryLayout, leg: Literal['road', 'sea']) -> c.Milliseconds:
    path_id = 'PATH-WAREHOUSE--PORT' if leg == 'road' else 'PATH-SHIP--CUSTOMER'
    path = next(row for row in layout.paths if row.id == path_id)
    # The displayed truck continues from PORT-ENTRY to the authoritative port
    # buffer before custody changes, so that final movement also costs time.
    tail = next(row.position for row in layout.locations if row.id == 'OPS-PORT-BUFFER') if leg == 'road' else None
    return travel_duration_ms(path, tail=tail)
