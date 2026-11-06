"""Independent spatial acceptance checks for the non-grid fictional steelworks."""
import copy
import importlib.util
import json
import math
from pathlib import Path

import pytest

from app.operations.layout import LAYOUT_PATH, load_factory_layout, transform_point

ROOT = LAYOUT_PATH.parents[1]
CAMPUS = ROOT / 'shared/factory-campus.json'


def intersects_footprint(a, b, center, rotation, half_x, half_z):
    """Clip a world segment against an oriented equipment box, ignoring tangency."""
    c, s = math.cos(rotation), math.sin(rotation)
    def local(p):
        dx, dz = p[0] - center[0], p[2] - center[2]
        return c * dx - s * dz, s * dx + c * dz
    start, end = local(a), local(b)
    enter, leave = 0.0, 1.0
    for index, extent in enumerate((half_x - 1e-6, half_z - 1e-6)):
        delta = end[index] - start[index]
        if abs(delta) < 1e-10:
            if abs(start[index]) >= extent:
                return False
        else:
            cuts = sorted(((-extent - start[index]) / delta, (extent - start[index]) / delta))
            enter, leave = max(enter, cuts[0]), min(leave, cuts[1])
            if enter >= leave:
                return False
    return leave > 0 and enter < 1


@pytest.mark.parametrize('network', ['road', 'rail', 'roller'])
def test_all_segments_avoid_unrelated_rotated_equipment(network):
    layout = load_factory_layout()
    locations = {r.id: r for r in layout.locations}
    stages = {r.id: r for r in layout.stages}
    checked = 0
    for path in layout.paths:
        if path.network != network:
            continue
        targets = {locations[path.from_location_id].owner_id, locations[path.to_location_id].owner_id}
        for equipment in layout.equipment:
            if equipment.id in targets:
                continue
            stage = stages[equipment.stage_id]
            center = transform_point(equipment.position, stage)
            for a, b in zip(path.points, path.points[1:]):
                assert not intersects_footprint(a, b, center, equipment.rotation + stage.rotation, 3.2, 2.3), (path.id, equipment.id, a, b)
                checked += 1
    assert checked > 1000


def test_road_segments_use_loading_ends_without_cutting_unrelated_halls():
    layout = load_factory_layout()
    campus = json.loads(CAMPUS.read_text())
    locations = {r.id: r for r in layout.locations}
    equipment = {r.id: r for r in layout.equipment}
    for path in layout.paths:
        if path.network != 'road':
            continue
        source = equipment[locations[path.from_location_id].owner_id]
        destination = equipment[locations[path.to_location_id].owner_id]
        for hall in campus['halls']:
            def owns(e):
                return hall['id'] == f'facility-{e.id.lower()}' if e.stage_id in ('sources', 'logistics') else hall['stage_id'] == e.stage_id
            for index, (a, b) in enumerate(zip(path.points, path.points[1:])):
                if (index == 0 and owns(source)) or (index == len(path.points) - 2 and owns(destination)):
                    continue
                assert not intersects_footprint(a, b, hall['center'], hall['rotation'], hall['size'][0] / 2, hall['size'][2] / 2), (path.id, hall['id'], index)


def test_stages_are_inline_and_finishing_halls_turn_toward_logistics():
    layout = load_factory_layout()
    for stage in layout.stages:
        if stage.id in ('sources', 'logistics'):
            continue
        rows = [e for e in layout.equipment if e.stage_id == stage.id]
        assert all(e.position[2] == 0 and e.rotation == 0 for e in rows)
        assert [e.position[0] for e in rows] == sorted(e.position[0] for e in rows)
        assert all(b.position[0] - a.position[0] >= 8 for a, b in zip(rows, rows[1:]))
        assert stage.rotation == (-math.pi / 2 if stage.id in ('gi', 'ga', 'eg') else 0)


def test_campus_halls_are_separate_and_storage_has_fifty_unit_clearance():
    campus = json.loads(CAMPUS.read_text())
    assert campus['version'] == 1 and len(campus['districts']) == 5
    halls = campus['halls']
    assert len(halls) == 31
    for eid in ('ore-source', 'scrap-source', 'ti-source', 'warehouse', 'port', 'customer'):
        hall = next(h for h in halls if h['id'] == f'facility-{eid}')
        assert hall['size'][0] >= 50
        assert hall['size'][2] >= 28
    for index, a in enumerate(halls):
        for b in halls[index + 1:]:
            def extent(h):
                c, s = abs(math.cos(h['rotation'])), abs(math.sin(h['rotation']))
                return (c * h['size'][0] + s * h['size'][2]) / 2, (s * h['size'][0] + c * h['size'][2]) / 2
            ax, az = extent(a); bx, bz = extent(b)
            assert abs(a['center'][0] - b['center'][0]) >= ax + bx or abs(a['center'][2] - b['center'][2]) >= az + bz, (a['id'], b['id'])


def test_canonical_road_paths_share_trunk_corridors_and_have_safe_curves():
    paths = [p for p in load_factory_layout().paths if p.network == 'road']
    assert sum(any(p[2] == -35 for p in path.points) for path in paths) >= 10
    assert sum(any(p[2] == 130 for p in path.points) for path in paths) >= 4
    assert sum(any(p[0] == 210 for p in path.points) for path in paths) >= 15
    assert any(any(a[0] != b[0] and a[2] != b[2] for a, b in zip(path.points, path.points[1:])) for path in paths)


def test_crane_vehicle_and_roller_custody_coordinates_remain_coincident():
    layout = load_factory_layout()
    locations = {r.id: r for r in layout.locations}
    for crane in layout.cranes:
        assert locations[crane.location_id].position == locations[crane.pick_location_id].position
    for vehicle in layout.vehicles:
        first = next(p for p in layout.paths if p.vehicle_id == vehicle.id)
        assert locations[vehicle.location_id].position == first.points[0]
    for path in layout.paths:
        if path.custody_location_id:
            assert locations[path.custody_location_id].position in path.points[1:-1]


def test_regeneration_is_deterministic_and_retains_nonspatial_contracts():
    spec = importlib.util.spec_from_file_location('factory_campus_builder', ROOT / 'tools/build_factory_campus.py')
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    before = json.loads(LAYOUT_PATH.read_text())
    after, campus = module.build(copy.deepcopy(before))
    assert after == before
    assert campus == json.loads(CAMPUS.read_text())
    assert after['routes'] == before['routes']
    assert after['source_bindings'] == before['source_bindings']
    assert after['vehicles'] == before['vehicles']
    assert after['cranes'] == before['cranes']


def test_paths_never_double_back_on_a_collinear_segment():
    for path in load_factory_layout().paths:
        for a, b, c in zip(path.points, path.points[1:], path.points[2:]):
            incoming = b[0] - a[0], b[2] - a[2]
            outgoing = c[0] - b[0], c[2] - b[2]
            cross = incoming[0] * outgoing[1] - incoming[1] * outgoing[0]
            dot = incoming[0] * outgoing[0] + incoming[1] * outgoing[1]
            assert abs(cross) > 1e-6 or dot >= 0, (path.id, a, b, c)


def test_rail_and_roller_depart_and_arrive_along_the_equipment_axis():
    layout = load_factory_layout()
    equipment = {e.id: e for e in layout.equipment}
    locations = {r.id: r for r in layout.locations}
    stages = {s.id: s for s in layout.stages}
    for path in layout.paths:
        if path.network not in ('rail', 'roller'):
            continue
        for location_id, origin, next_point in ((path.from_location_id, path.points[0], path.points[1]), (path.to_location_id, path.points[-1], path.points[-2])):
            e = equipment[locations[location_id].owner_id]
            anchor = next(a for a in e.anchors.values() if a.location_id == location_id)
            sign = -1 if anchor.position[0] < 0 else 1
            rotation = e.rotation + stages[e.stage_id].rotation
            direction = math.cos(rotation) * sign, -math.sin(rotation) * sign
            displacement = next_point[0] - origin[0], next_point[2] - origin[2]
            assert displacement[0] * direction[0] + displacement[1] * direction[1] > 0, path.id
            assert abs(displacement[0] * direction[1] - displacement[1] * direction[0]) < 1e-6, path.id


def test_every_nonzero_roller_has_a_unique_interior_custody_location():
    layout = load_factory_layout()
    locations = {row.id: row for row in layout.locations}
    rollers = [row for row in layout.paths if row.mode == 'roller']
    assert len(rollers) == 124
    assert len({row.custody_location_id for row in rollers}) == 124
    for row in rollers:
        assert row.custody_location_id is not None
        location = locations[row.custody_location_id]
        assert location.owner_id == row.id and location.position in row.points[1:-1]
        assert location.position not in (row.points[0], row.points[-1])
