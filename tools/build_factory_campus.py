#!/usr/bin/env python3
"""Regenerate the fictional campus geometry without changing operational identities.

Run from any directory. Input and output are the existing canonical layout; all
non-spatial IDs, capabilities, route ordering and transport modes are preserved.
"""
from __future__ import annotations

import heapq
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STAGES = {
    'carbon-upstream': (-230, -100), 'casting-slab': (-135, -100),
    'casting-bloom': (-135, -130), 'casting-billet': (-135, -70),
    'hr': (-55, -100), 'plate': (-55, -55), 'wire': (-65, -160),
    'cr': (40, -105), 'gi': (120, -115), 'ga': (150, -110),
    'eg': (180, -115), 'hgi': (95, -170), 'go': (25, -20),
    'ngo': (130, -15), 'sts-hr': (-150, 55), 'sts-plate': (-150, 100),
    'sts-cr': (-30, 60), 'ti-hr': (-140, 160), 'ti-plate': (-140, 200),
    'ti-cr': (-35, 160), 'ti-sheet': (70, 160),
    'hot-rolling-reserve': (-50, -82), 'sources': (0, 0), 'logistics': (0, 0),
}
FACILITIES = {
    'ORE-SOURCE': (-305, -100), 'SCRAP-SOURCE': (-250, 65), 'TI-SOURCE': (-240, 175),
    'FINAL-INSPECTION': (220, -5), 'PACKAGING': (230, -5),
    'WAREHOUSE': (270, 10), 'PORT': (290, 80), 'SHIP': (330, 80), 'CUSTOMER': (395, 160),
}
Rect = tuple[float, float, float, float]
Point2 = tuple[float, float]


def point(x: float, y: float, z: float) -> list[float]:
    return [round(x, 6), round(y, 6), round(z, 6)]


def transform(p: list[float], pose: dict) -> list[float]:
    c, s = math.cos(pose['rotation']), math.sin(pose['rotation'])
    x, y, z = pose['position']
    return point(x + c * p[0] + s * p[2], y + p[1], z - s * p[0] + c * p[2])


def world_position(equipment: dict, stages: dict, local: list[float]) -> list[float]:
    return transform(transform(local, equipment), stages[equipment['stage_id']])


def bounds(center: list[float], width: float, depth: float, rotation: float, margin: float = 0) -> Rect:
    c, s = abs(math.cos(rotation)), abs(math.sin(rotation))
    dx, dz = (c * width + s * depth) / 2 + margin, (s * width + c * depth) / 2 + margin
    return tuple(round(v, 6) for v in (center[0] - dx, center[0] + dx, center[2] - dz, center[2] + dz))


def crosses(a: Point2, b: Point2, rect: Rect) -> bool:
    """Open-rectangle segment intersection; boundary tangencies are allowed."""
    low, high = 0.0, 1.0
    for origin, delta, lo, hi in ((a[0], b[0] - a[0], rect[0] + 1e-7, rect[1] - 1e-7), (a[1], b[1] - a[1], rect[2] + 1e-7, rect[3] - 1e-7)):
        if abs(delta) < 1e-10:
            if not lo < origin < hi:
                return False
        else:
            t1, t2 = sorted(((lo - origin) / delta, (hi - origin) / delta))
            low, high = max(low, t1), min(high, t2)
            if low >= high:
                return False
    return high > 0 and low < 1


def clear(a: Point2, b: Point2, obstacles: list[Rect]) -> bool:
    return not any(crosses(a, b, rect) for rect in obstacles)


def simplify(points: list[Point2]) -> list[Point2]:
    result: list[Point2] = []
    for p in points:
        if result and p == result[-1]:
            continue
        if len(result) >= 2:
            a, b = result[-2:]
            if abs((b[0] - a[0]) * (p[1] - b[1]) - (b[1] - a[1]) * (p[0] - b[0])) < 1e-8:
                result.pop()
        result.append(p)
    return result


def route(start: Point2, end: Point2, obstacles: list[Rect], arterial: bool) -> list[Point2]:
    if not arterial and clear(start, end, obstacles):
        return [start, end]
    xs = sorted({start[0], end[0], -330, -215, 210, 305, *(v for r in obstacles for v in r[:2])})
    zs = sorted({start[1], end[1], -195, -35, 130, 230, *(v for r in obstacles for v in r[2:])})
    first, last = (xs.index(start[0]), zs.index(start[1])), (xs.index(end[0]), zs.index(end[1]))
    distances = {(first, -1): 0.0}
    previous = {}
    queue = [(0.0, 0.0, first, -1)]
    edges: dict[tuple[tuple[int, int], tuple[int, int]], bool] = {}
    while queue:
        _, cost, node, direction = heapq.heappop(queue)
        if cost != distances.get((node, direction)):
            continue
        if node == last:
            path = [node]
            key = (node, direction)
            while key in previous:
                key = previous[key]
                path.append(key[0])
            return simplify([(xs[i], zs[j]) for i, j in reversed(path)])
        i, j = node
        for ni, nj, axis in ((i - 1, j, 0), (i + 1, j, 0), (i, j - 1, 1), (i, j + 1, 1)):
            if not (0 <= ni < len(xs) and 0 <= nj < len(zs)):
                continue
            neighbor = ni, nj
            a, b = (xs[i], zs[j]), (xs[ni], zs[nj])
            edge = tuple(sorted((node, neighbor)))
            if edge not in edges:
                edges[edge] = clear(a, b, obstacles)
            if not edges[edge]:
                continue
            on_arterial = arterial and ((axis == 0 and zs[j] in (-195, -35, 130, 230)) or (axis == 1 and xs[i] in (-330, -215, 210, 305)))
            weight = 0.55 if on_arterial else 1.0
            next_cost = cost + math.dist(a, b) * weight + (2 if direction not in (-1, axis) else 0)
            key = (neighbor, axis)
            if next_cost < distances.get(key, math.inf):
                distances[key] = next_cost
                previous[key] = node, direction
                heuristic = 0.55 * (abs(b[0] - end[0]) + abs(b[1] - end[1]))
                heapq.heappush(queue, (next_cost + heuristic, next_cost, neighbor, axis))
    raise ValueError(f'No safe path: {start} -> {end}')


def soften(points: list[Point2], obstacles: list[Rect]) -> list[Point2]:
    result = [points[0]]
    for a, b, c in zip(points, points[1:], points[2:]):
        radius = min(3.0, math.dist(a, b) / 4, math.dist(b, c) / 4)
        if radius < 1:
            result.append(b)
            continue
        before = tuple(b[i] + (a[i] - b[i]) * radius / math.dist(a, b) for i in (0, 1))
        after = tuple(b[i] + (c[i] - b[i]) * radius / math.dist(b, c) for i in (0, 1))
        curve = [tuple(round((1 - t) ** 2 * before[i] + 2 * t * (1 - t) * b[i] + t ** 2 * after[i], 6) for i in (0, 1)) for t in (0, .25, .5, .75, 1)]
        if all(clear(p, q, obstacles) for p, q in zip(curve, curve[1:])):
            result.extend(curve)
        else:
            result.append(b)
    result.append(points[-1])
    return result


def build(layout: dict) -> tuple[dict, dict]:
    stages = {row['id']: row for row in layout['stages']}
    for sid, (x, z) in STAGES.items():
        stages[sid].update(position=[x, 0, z], rotation=-math.pi / 2 if sid in ('gi', 'ga', 'eg') else 0)
    equipment = {row['id']: row for row in layout['equipment']}
    halls = []
    hall_for = {}
    for sid, stage in stages.items():
        rows = [e for e in layout['equipment'] if e['stage_id'] == sid]
        spacing = 24 if sid == 'carbon-upstream' else 10 if sid.startswith('casting-') else 9 if sid in ('hr', 'plate', 'wire') else 8
        for index, e in enumerate(rows):
            e.update(position=[(index - (len(rows) - 1) / 2) * spacing, 0, 0], rotation=0)
            if e['id'] in FACILITIES:
                x, z = FACILITIES[e['id']]
                e['position'] = [x, 0, z]
        if sid in ('sources', 'logistics'):
            for e in rows:
                storage = e['id'] in ('ORE-SOURCE', 'SCRAP-SOURCE', 'TI-SOURCE', 'WAREHOUSE', 'PORT', 'CUSTOMER')
                width, depth = (58, 28) if storage else (8, 12)
                kind = 'warehouse' if e['id'] == 'WAREHOUSE' else 'yard'
                hall = dict(id=f"facility-{e['id'].lower()}", stage_id=sid, center=world_position(e, stages, [0, 0, 0]), size=[width, 6 if kind == 'warehouse' else 1, depth], rotation=0, kind=kind)
                if storage:
                    hall['center'][2] += 7
                halls.append(hall); hall_for[e['id']] = hall
        else:
            kind = 'hot' if sid == 'carbon-upstream' or sid.startswith('casting-') else 'specialty' if sid.startswith(('sts-', 'ti-')) else 'finishing' if sid in ('gi', 'ga', 'eg', 'hgi', 'go', 'ngo') else 'rolling'
            hall = dict(id=f'hall-{sid}', stage_id=sid, center=list(stage['position']), size=[(len(rows) - 1) * spacing + 12, 9 if kind == 'hot' else 7, 14], rotation=stage['rotation'], kind=kind)
            halls.append(hall)
            for e in rows:
                hall_for[e['id']] = hall
    outbound = next(path for path in layout['paths'] if path['id'] == 'PATH-PACKAGING--WAREHOUSE')
    old_custody = outbound.get('custody_location_id')
    if old_custody:
        layout['locations'] = [row for row in layout['locations'] if row['id'] != old_custody]
    outbound.update(from_location_id='OPS-PACKAGING-BUFFER', mode='flatbed', network='road', vehicle_id='FLATBED-A', pickup_crane_id='CRANE-PACKAGING', drop_crane_id='CRANE-WAREHOUSE', custody_location_id=None)
    locations = {row['id']: row for row in layout['locations']}
    for e in equipment.values():
        for anchor in e['anchors'].values():
            locations[anchor['location_id']]['position'] = world_position(e, stages, anchor['position'])
    for crane in layout['cranes']:
        locations[crane['location_id']]['position'] = list(locations[crane['pick_location_id']]['position'])
    eq_rects = {eid: bounds(world_position(e, stages, [0, 0, 0]), 6.8, 5.6, stages[e['stage_id']]['rotation']) for eid, e in equipment.items()}
    hall_rects = [bounds(h['center'], h['size'][0], h['size'][2], h['rotation'], 1) for h in halls]

    def apron(e: dict, anchor: list[float], outgoing: bool) -> Point2:
        h = hall_for[e['id']]
        sign = 1 if outgoing else -1
        rotation = stages[e['stage_id']]['rotation']
        center = h['center']
        direction = math.cos(rotation), -math.sin(rotation)
        along = (anchor[0] - center[0]) * direction[0] + (anchor[2] - center[2]) * direction[1]
        extension = sign * (h['size'][0] / 2 + 2.2) - along
        return round(anchor[0] + direction[0] * extension, 6), round(anchor[2] + direction[1] * extension, 6)

    for path in layout['paths']:
        source, destination = locations[path['from_location_id']], locations[path['to_location_id']]
        a, b = source['position'], destination['position']
        start, end = (a[0], a[2]), (b[0], b[2])
        obstacles = [rect for eid, rect in eq_rects.items() if eid not in (source['owner_id'], destination['owner_id'])]
        if path['network'] == 'road':
            exit_apron = apron(equipment[source['owner_id']], a, True)
            entry_apron = apron(equipment[destination['owner_id']], b, False)
            middle = route(exit_apron, entry_apron, hall_rects, True)
            middle = soften(middle, hall_rects)
            points = simplify([start, *middle, end])
        elif path['network'] == 'sea':
            points = [start, (350, start[1]), (380, end[1]), end]
        else:
            def end_clearance(owner_id: str, location_id: str) -> Point2:
                e = equipment[owner_id]
                anchor = next(value for value in e['anchors'].values() if value['location_id'] == location_id)
                sign = -1 if anchor['position'][0] < 0 else 1
                tip = world_position(e, stages, [sign * 3.8, anchor['position'][1], anchor['position'][2]])
                return tip[0], tip[2]
            departure = end_clearance(source['owner_id'], source['id'])
            arrival = end_clearance(destination['owner_id'], destination['id'])
            all_equipment = list(eq_rects.values())
            middle = route(departure, arrival, all_equipment, False)
            if path['network'] == 'rail':
                middle = soften(middle, all_equipment)
            points = simplify([start, *middle, end])
        if path['network'] != 'sea' and not all(clear(p, q, obstacles) for p, q in zip(points, points[1:])):
            raise ValueError(f"Equipment intersection: {path['id']}")
        if path['network'] == 'roller':
            if not path.get('custody_location_id'):
                path['custody_location_id'] = f"OPS-ROLLER-{path['id'].removeprefix('PATH-')}"
            if len(points) == 2:
                points.insert(1, ((start[0] + end[0]) / 2, (start[1] + end[1]) / 2))
            custody_id = path['custody_location_id']
            if custody_id not in locations:
                record = dict(id=custody_id, owner_id=path['id'], position=[0, 0, 0])
                locations[custody_id] = record
                layout['locations'].append(record)
            locations[custody_id]['position'] = point(points[1][0], a[1], points[1][1])
        path['points'] = [point(x, a[1] + (b[1] - a[1]) * i / (len(points) - 1), z) for i, (x, z) in enumerate(points)]
    for vehicle in layout['vehicles']:
        first = next(p for p in layout['paths'] if p['vehicle_id'] == vehicle['id'])
        locations[vehicle['location_id']]['position'] = list(first['points'][0])
    campus = dict(version=1, land=dict(center=[-10, -2, 20], size=[680, 1, 460]), water=dict(center=[385, -1.9, 85], size=[150, .2, 300]), halls=halls, roads=[], districts=[
        dict(id='carbon', label='탄소강 제선·연주·압연', position=[-205, 0, -150]),
        dict(id='finishing', label='냉연·도금·전기강판', position=[110, 0, -45]),
        dict(id='stainless', label='스테인리스 제강·압연', position=[-150, 0, 30]),
        dict(id='titanium', label='티타늄 압연·정정', position=[-120, 0, 135]),
        dict(id='logistics', label='검사·포장·항만 출하', position=[245, 0, 45]),
    ])
    return layout, campus


def main() -> None:
    path = ROOT / 'shared/factory-layout.json'
    layout, campus = build(json.loads(path.read_text()))
    path.write_text(json.dumps(layout, ensure_ascii=False, indent=2) + '\n')
    (ROOT / 'shared/factory-campus.json').write_text(json.dumps(campus, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'equipment': len(layout['equipment']), 'paths': len(layout['paths']), 'halls': len(campus['halls']), 'status': 'geometry generated and non-target equipment intersections rejected'}))


if __name__ == '__main__':
    main()
