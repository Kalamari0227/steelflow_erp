"""Functional block aprons and shared arterials with real split junction nodes."""
from collections import defaultdict
from dataclasses import dataclass, field

from app.operations.world_types import Point, require
from app.operations.world_spatial_types import SpatialStop
from tools.factory_world.builder import Builder
from tools.factory_world.design import STAGE_ORIGINS


@dataclass(frozen=True, slots=True)
class Span:
    start: Point
    end: Point

    @property
    def horizontal(self) -> bool:
        return self.start[2] == self.end[2]

    def contains(self, point: Point) -> bool:
        return (min(self.start[0], self.end[0]) <= point[0] <= max(self.start[0], self.end[0])
                and min(self.start[2], self.end[2]) <= point[2] <= max(self.start[2], self.end[2]))


@dataclass(slots=True)
class RoadPlan:
    """Mutable construction plan joins every road crossing before graph emission."""
    builder: Builder
    spans: list[Span] = field(default_factory=list)

    def add(self, span: Span) -> None:
        require(span.horizontal or span.start[0] == span.end[0], 'road_axis', str(span))
        if span.start != span.end:
            self.spans.append(span)

    def finish(self) -> None:
        b = self.builder
        terminals = {node.position: node.id for node in b.nodes if node.modes == ('road',)}
        points = set(terminals) | {point for span in self.spans for point in (span.start, span.end)}
        for index, left in enumerate(self.spans):
            for right in self.spans[index+1:]:
                if left.horizontal == right.horizontal:
                    continue
                horizontal, vertical = (left, right) if left.horizontal else (right, left)
                crossing = (vertical.start[0], 2, horizontal.start[2])
                if left.contains(crossing) and right.contains(crossing):
                    points.add(crossing)
        profiles = tuple(profile.id for profile in b.profiles if profile.mode == 'road')
        for index, point in enumerate(sorted(points)):
            if point not in terminals:
                identity = b.node(f'road:junction:{index}', point, 'road')
                terminals[point] = identity
                b.stops.append(SpatialStop(id='stop:'+identity, node_id=identity,
                                          kind='stop', profile_ids=profiles))
        emitted = set()
        for span in self.spans:
            ordered = sorted(point for point in points if span.contains(point))
            for left, right in zip(ordered, ordered[1:]):
                pair = (terminals[left], terminals[right])
                if pair not in emitted:
                    b.both(f'road:shared:{len(emitted)}', pair, 'road')
                    emitted.add(pair)


def make_roads(b: Builder) -> None:
    """Connect industrial blocks through a few shared service corridors."""
    plan = RoadPlan(b)
    # Receiving, central service and dispatch are the only full-width corridors.
    plan.add(Span((-250, 2, -2400), (-250, 2, 4120)))
    plan.add(Span((3050, 2, -1490), (3050, 2, 4120)))
    for z in (-1490, 1180, 3520):
        plan.add(Span((-250, 2, z), (3050, 2, z)))
    # Southern specialty works share a service spine, rather than full-width rows.
    plan.add(Span((1390, 2, 1180), (1390, 2, 3300)))
    owner_zones = {owner: zone.id for zone in b.zones for owner in zone.owner_ids}
    ports = {port.node_id: port for port in b.ports if port.modes == ('road',)}
    production = defaultdict(list)
    local_rows = defaultdict(list)
    remote_rows = defaultdict(list)
    for node in b.nodes:
        if node.modes != ('road',):
            continue
        x, _, z = node.position
        if x > 3050:
            remote_rows[z].append(node.position)
            continue
        zone = owner_zones.get(ports[node.id].owner_id, '')
        if zone in STAGE_ORIGINS:
            production[zone].append(node.position)
        else:
            # Raw berth belongs to the east apron; the three sources stay west.
            local_rows[(z, ports[node.id].owner_id == 'quay:raw')].append(node.position)
    for zone, points in production.items():
        if zone in ('go', 'ngo'):
            x = points[0][0]
            plan.add(Span((x, 2, 1220), (x, 2, 2600)))
            plan.add(Span((1390, 2, 1220), (x, 2, 1220)))
            plan.add(Span((1390, 2, 2600), (x, 2, 2600)))
        else:
            z = points[0][2]
            spine = -250 if z < 1180 else (1390 if max(p[0] for p in points) < 1390 else 3050)
            plan.add(Span((min(spine, min(p[0] for p in points)), 2, z),
                          (max(spine, max(p[0] for p in points)), 2, z)))
    for (z, raw_berth), points in local_rows.items():
        spine = 3050 if raw_berth or (z > 1180 and min(p[0] for p in points) > 1390) else -250
        plan.add(Span((min(spine, min(p[0] for p in points)), 2, z),
                      (max(spine, max(p[0] for p in points)), 2, z)))
    # The public highway goes around the inlet; destination roads stay landward.
    plan.add(Span((-250, 2, -2400), (6800, 2, -2400)))
    plan.add(Span((6800, 2, -2400), (6800, 2, max(remote_rows))))
    for z, points in remote_rows.items():
        plan.add(Span((min(p[0] for p in points), 2, z), (6800, 2, z)))
    plan.finish()
