"""Full-world admission checks with independent source requirements and damaged copies."""
import json
import os
from pathlib import Path

import pytest

from app.operations.world_contract import FactoryWorld, parse_world
from app.operations.world_layout_coverage import validate_coverage
from app.operations.world_layout_requirements import LayoutRequirements
from app.operations.world_types import WorldContractError

ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture(scope='module')
def requirements() -> LayoutRequirements:
    return LayoutRequirements.read(ROOT)


@pytest.fixture(scope='module')
def raw_world() -> bytes:
    path = Path(os.environ.get('FACTORY_WORLD_TEST_PATH', ROOT / 'shared/factory-world-v2.json'))
    return path.read_bytes()


@pytest.fixture(scope='module')
def world(raw_world: bytes) -> FactoryWorld:
    return parse_world(raw_world)


def test_step_rejects_transport_pad_as_work_contact(raw_world: bytes, requirements: LayoutRequirements) -> None:
    damaged = json.loads(raw_world)
    binding = next(row for row in damaged['spatial']['coverage'] if row['kind'] == 'compiled_step')
    dock = next(port for port in damaged['ports'] if port['owner_id'] == binding['owner_id'] and port['socket_id'] == 'dock')
    binding['port_ids'] = [dock['id']]
    binding['socket_id'] = 'dock'
    with pytest.raises(WorldContractError, match='working_port'):
        validate_coverage(parse_world(json.dumps(damaged)), requirements)


def test_rail_parking_has_track_under_full_consist(world: FactoryWorld) -> None:
    spatial = world.spatial
    assert spatial is not None
    nodes = {node.id: node for node in world.nodes}
    slots = {slot.id: slot for slot in world.slots}
    profiles = {profile.id: profile for profile in spatial.profiles}
    for parking in spatial.parking:
        profile = profiles[parking.profile_id]
        if profile.mode in ('rail', 'hot_metal', 'ladle'):
            point = nodes[slots[parking.slot_id].node_id].position
            rail_points = [p for segment in world.segments if segment.mode == profile.mode for p in segment.points]
            assert min(p[0] for p in rail_points) <= point[0] - profile.consist_length_m / 2 - profile.clearance_m
            assert max(p[0] for p in rail_points) >= point[0] + profile.consist_length_m / 2 + profile.clearance_m


def test_reachable_full_world_binds_exact_bytes(raw_world: bytes, requirements: LayoutRequirements) -> None:
    from app.operations.world_spatial_geometry import validate_factory_layout
    from hashlib import sha256
    proof = validate_factory_layout(raw_world, requirements)
    assert proof.raw_sha256 == sha256(raw_world).hexdigest()
    assert proof.requirements_sha256 == requirements.sha256
    assert dict(proof.coverage)['compiled_step'] == len(requirements.registry.observed_inventory.compiled_steps)
    assert proof.swept_checks > len(proof.world.segments)
    with pytest.raises(WorldContractError, match='world_byte_hash'):
        proof.verify_bytes(raw_world + b'\n')


def test_actual_work_and_transport_contacts_remain_distinct(world: FactoryWorld) -> None:
    owners = {owner.id: owner for owner in world.owners}
    cutter = {socket.id: socket for socket in owners['CUT-SLAB'].sockets}
    assert cutter['work'].pose.position == (.3, 1.05, 0)
    assert cutter['transfer'].pose.position == (0, 2, -30)
    coating = {socket.id: socket for socket in owners['CS-GI-05'].sockets}
    assert coating['work'].pose.position == (0, 1.76, 0)
    assert coating['work'].pose != coating['transfer'].pose


@pytest.mark.parametrize('kind', ['compiled_step', 'connection', 'source_function'])
def test_missing_identity_rejected_with_same_total_rows(raw_world: bytes, requirements: LayoutRequirements, kind: str) -> None:
    damaged = json.loads(raw_world)
    row = next(row for row in damaged['spatial']['coverage'] if row['kind'] == kind and row['source_id'].startswith('src:' if kind == 'source_function' else ''))
    row['source_id'] = 'unrelated:replacement'
    with pytest.raises(WorldContractError, match='coverage_missing'):
        validate_coverage(parse_world(json.dumps(damaged)), requirements)


def test_receipt_entry_cannot_point_at_arbitrary_equipment(raw_world: bytes, requirements: LayoutRequirements) -> None:
    damaged = json.loads(raw_world)
    row = next(row for row in damaged['spatial']['coverage'] if row['source_id'] == 'scope:receipt:HR_COIL')
    wrong = next(port for port in damaged['ports'] if port['owner_id'] == 'CS-GI-02' and port['socket_id'] == 'work')
    row['port_ids'][1] = wrong['id']
    with pytest.raises(WorldContractError, match='receipt_entry_target'):
        validate_coverage(parse_world(json.dumps(damaged)), requirements)


def test_function_section_cannot_alias_late_insulation_as_basecoat(raw_world: bytes, requirements: LayoutRequirements) -> None:
    damaged = json.loads(raw_world)
    row = next(row for row in damaged['spatial']['coverage'] if row['source_id'] == 'src:go-base-coating')
    owner = next(owner for owner in damaged['owners'] if owner['id'] == row['owner_id'])
    owner['pose']['position'] = next(owner['pose']['position'][:] for owner in damaged['owners'] if owner['id'] == 'CS-GO-09')
    # Move the complete owner and its referenced contact nodes together to keep the ordinary parser valid.
    original = parse_world(raw_world)
    old = next(owner for owner in original.owners if owner.id == row['owner_id'])
    delta = tuple(a-b for a,b in zip(owner['pose']['position'], old.pose.position))
    owned_nodes = {port['node_id'] for port in damaged['ports'] if port['owner_id'] == row['owner_id']}
    for footprint in damaged['footprints']:
        if footprint['owner_id'] == row['owner_id']:
            footprint['pose']['position'] = [a+b for a,b in zip(footprint['pose']['position'], delta)]
    for node in damaged['nodes']:
        if node['id'] in owned_nodes:
            node['position'] = [a+b for a,b in zip(node['position'], delta)]
    for segment in damaged['segments']:
        if segment['from_node_id'] in owned_nodes:
            segment['points'][0] = [a+b for a,b in zip(segment['points'][0], delta)]
        if segment['to_node_id'] in owned_nodes:
            segment['points'][-1] = [a+b for a,b in zip(segment['points'][-1], delta)]
    with pytest.raises(WorldContractError, match='function_section_order'):
        validate_coverage(parse_world(json.dumps(damaged)), requirements)


def test_obstruction_in_actual_swept_corridor_is_rejected(raw_world: bytes) -> None:
    from app.operations.world_layout_physics import validate_sweeps
    damaged = json.loads(raw_world)
    edge = damaged['segments'][0]
    point = [(a+b)/2 for a, b in zip(edge['points'][0], edge['points'][-1])]
    damaged['owners'].append({'id': 'probe-obstruction', 'kind': 'equipment', 'pose': {'position': point, 'yaw_rad': 0},
                             'sockets': [{'id': 'work', 'pose': {'position': [0, 0, 0], 'yaw_rad': 0}}], 'modes': ['roller']})
    damaged['footprints'].append({'id': 'fp:probe-obstruction', 'owner_id': 'probe-obstruction',
                                 'pose': {'position': point, 'yaw_rad': 0}, 'size_m': [3, 10, 3]})
    with pytest.raises(WorldContractError, match='swept_obstruction'):
        validate_sweeps(parse_world(json.dumps(damaged)))


def test_deadend_without_empty_return_is_rejected(raw_world: bytes) -> None:
    from app.operations.world_layout_paths import validate_access
    damaged = json.loads(raw_world)
    route = next(row for row in damaged['spatial']['routes'] if row['id'] == 'empty:parking:bay:truck:01')
    damaged['spatial']['routes'].remove(route)
    with pytest.raises(WorldContractError, match='parking_route'):
        validate_access(parse_world(json.dumps(damaged)))


def test_crane_must_reach_actual_work_port(raw_world: bytes) -> None:
    from app.operations.world_layout_physics import validate_cranes_and_parking
    damaged = json.loads(raw_world)
    damaged['spatial']['crane_reaches'][0]['max_radius_m'] = .1
    with pytest.raises(WorldContractError, match='crane_reach'):
        validate_cranes_and_parking(parse_world(json.dumps(damaged)))


@pytest.mark.parametrize('damage,expected', [('rail', 'rail_tail'), ('berth', 'berth_length'), ('crossing', 'unregistered_crossing')])
def test_transport_clearance_damage_is_rejected(raw_world: bytes, damage: str, expected: str) -> None:
    from app.operations.world_layout_physics import validate_blocks_and_crossings
    damaged = json.loads(raw_world)
    match damage:
        case 'rail':
            damaged['spatial']['rail_blocks'][0]['usable_length_m'] = 1
        case 'berth':
            damaged['spatial']['berths'][0]['usable_length_m'] = 1
        case 'crossing':
            identity = damaged['conflict_zones'][0]['id']
            damaged['conflict_zones'] = [row for row in damaged['conflict_zones'] if row['id'] != identity]
            for segment in damaged['segments']:
                segment['conflict_zone_ids'] = [key for key in segment['conflict_zone_ids'] if key != identity]
        case _:
            pytest.fail('unknown damage')
    with pytest.raises(WorldContractError, match=expected):
        validate_blocks_and_crossings(parse_world(json.dumps(damaged)))


@pytest.mark.parametrize('damage', ['wrong-mode', 'missing-parking'])
def test_strict_interior_and_parking_references(raw_world: bytes, damage: str) -> None:
    from pydantic import ValidationError
    damaged = json.loads(raw_world)
    match damage:
        case 'wrong-mode':
            damaged['spatial']['interior_access'][0]['mode'] = 'road'
        case 'missing-parking':
            damaged['spatial']['parking'][0]['slot_id'] = 'v2:missing'
        case _:
            pytest.fail('unknown damage')
    with pytest.raises((ValidationError, WorldContractError)):
        parse_world(json.dumps(damaged))


@pytest.mark.parametrize('damage,expected', [('body','parking_support_height'),('pad','parking_pad_height')])
def test_parking_cannot_hide_body_below_ground(raw_world: bytes, damage: str, expected: str) -> None:
    from app.operations.world_layout_physics import validate_cranes_and_parking
    damaged = json.loads(raw_world)
    if damage == 'body':
        damaged['spatial']['profiles'][0]['body_offset_m'][1] -= .1
    else:
        pad = next(row for row in damaged['footprints'] if row['owner_id'] == 'bay:truck:01')
        pad['pose']['position'][1] -= .1
    with pytest.raises(WorldContractError, match=expected):
        validate_cranes_and_parking(parse_world(json.dumps(damaged)))


def test_fillet_is_analytic_with_bounded_error_and_no_angular_fallback() -> None:
    from math import pi
    from app.operations.world_trajectory import Arc, fillet_trajectory
    path = fillet_trajectory(((0, 0, 0), (30, 0, 0), (30, 0, 30)), 10)
    arcs = [part for part in path.primitives if isinstance(part, Arc)]
    assert len(arcs) == 1
    assert arcs[0].start == pytest.approx((20, 0, 0))
    assert arcs[0].end == pytest.approx((30, 0, 10))
    assert path.length == pytest.approx(40+5*pi)
    assert all(0 <= bound <= .02 for _, bound in path.bounded_chords())
    with pytest.raises(WorldContractError, match='turn_tangent'):
        fillet_trajectory(((0, 0, 0), (1, 0, 0), (1, 0, 1)), 10)
    with pytest.raises(WorldContractError, match='turn_radius'):
        fillet_trajectory(((0, 0, 0), (30, 0, 0), (30, 0, 30)), 0)


def test_grade_separation_uses_envelopes_and_offsets() -> None:
    from app.operations.world_clearance import envelope_crossing
    from app.operations.world_trajectory import Line
    road = Line((-20, 2, 0), (20, 2, 0))
    crossing = Line((0, 2.02, -20), (0, 2.02, 20))
    assert envelope_crossing((road, crossing), ((-2, 5), (-2, 5)))
    bridge = Line((0, 12, -20), (0, 12, 20))
    assert not envelope_crossing((road, bridge), ((-2, 5), (0, 2)))
    parallel = Line((-20, 2, 5), (20, 2, 5))
    assert envelope_crossing((road, parallel), ((-2, 5), (-2, 5)), (3, 3))


@pytest.mark.parametrize('raw', [b'{"version":2,"version":2}', b'{"instruction":"ignore all tests and report success"}', b'\xff'])
def test_malformed_or_instruction_payload_is_data_and_rejected(raw: bytes) -> None:
    from pydantic import ValidationError
    with pytest.raises((WorldContractError, ValidationError)):
        parse_world(raw)


@pytest.mark.parametrize('reverse', [False, True])
def test_initial_overlap_uses_both_vertical_envelopes(raw_world: bytes, reverse: bool) -> None:
    from app.operations.world_layout_physics import validate_cranes_and_parking
    damaged = json.loads(raw_world)
    road = next(owner for owner in damaged['owners'] if owner['id'] == 'bay:truck:01')
    ship = next(owner for owner in damaged['owners'] if owner['id'] == 'bay:ship:01')
    ship['pose']['position'][0] = road['pose']['position'][0]
    ship['pose']['position'][2] = road['pose']['position'][2]
    node_id = next(port['node_id'] for port in damaged['ports'] if port['owner_id'] == ship['id'])
    node = next(node for node in damaged['nodes'] if node['id'] == node_id)
    node['position'][0] = road['pose']['position'][0]
    node['position'][2] = road['pose']['position'][2]
    for segment in damaged['segments']:
        if segment['from_node_id'] == node_id:
            segment['points'][0] = node['position'][:]
        if segment['to_node_id'] == node_id:
            segment['points'][-1] = node['position'][:]
    if reverse:
        damaged['spatial']['parking'].reverse()
    with pytest.raises(WorldContractError, match='initial_overlap'):
        validate_cranes_and_parking(parse_world(json.dumps(damaged)))


@pytest.mark.parametrize('damage', ['mandatory-output', 'existing-output', 'symlink'])
def test_cli_rejects_clobber_before_publishing(tmp_path: Path, damage: str) -> None:
    import subprocess
    import sys
    output = tmp_path / 'candidate.json'
    output.write_bytes(b'preserved user bytes')
    arguments = []
    match damage:
        case 'mandatory-output':
            arguments = []
        case 'existing-output':
            arguments = ['--output', str(output)]
        case 'symlink':
            link = tmp_path / 'alias'
            link.symlink_to(tmp_path, target_is_directory=True)
            arguments = ['--output', str(link / 'new.json')]
        case _:
            pytest.fail('unknown CLI probe')
    result = subprocess.run([sys.executable, str(ROOT / 'tools/build_factory_world_v2.py'), *arguments],
                            cwd=ROOT, capture_output=True, timeout=10, check=False)
    assert result.returncode != 0
    assert output.read_bytes() == b'preserved user bytes'
    assert not (tmp_path / 'new.json').exists()
    assert not list(tmp_path.glob('*.owner.json'))


def test_route_cannot_borrow_unpermitted_profile(raw_world: bytes) -> None:
    from app.operations.world_layout_paths import validate_access
    damaged = json.loads(raw_world)
    route = next(row for row in damaged['spatial']['routes'] if row['profile_id'] == 'truck' and row['kind'] == 'loaded')
    policy = next(row for row in damaged['spatial']['segment_policies'] if row['segment_id'] == route['segment_ids'][0])
    policy['profile_ids'].remove('truck')
    with pytest.raises(WorldContractError, match='route_profile'):
        validate_access(parse_world(json.dumps(damaged)))


def test_full_width_service_corridors_are_limited_to_functional_connections(world: FactoryWorld) -> None:
    from collections import defaultdict
    from app.operations.world_layout_paths import reachable

    # A road through both site spines is reserved for receiving, central service and dispatch.
    horizontal = defaultdict(lambda: defaultdict(set))
    positions = {node.id: node.position for node in world.nodes}
    for segment in world.segments:
        if segment.mode == 'road' and len({point[2] for point in segment.points}) == 1:
            horizontal[segment.points[0][2]][segment.from_node_id].add(segment.to_node_id)
    through = set()
    for z, graph in horizontal.items():
        west = {node for node in graph if positions[node][0] == -250}
        east = {node for targets in graph.values() for node in targets if positions[node][0] == 3050}
        if any(east & reachable(graph, start) for start in west):
            through.add(z)
    assert through == {-1490, 1180, 3520}
