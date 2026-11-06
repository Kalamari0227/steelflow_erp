"""Continuous compound-box departure on unchanged real line/arc routes.

This is a source schedule and geometric bound, not T16/SQL execution authority.
All live actors remain; a separate occupied-park counterexample must stay blocked.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from dataclasses import asdict
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('world-root', 'geometry', 'contract-root', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError('New evidence output required')
    sys.path.insert(0, str(args.contract_root.resolve() / 'backend'))
    from app.operations.contracts_v3 import FactoryCollections
    from app.operations.contracts_v3_transport import MovementSegment
    from app.operations.world_contract import parse_world
    from app.operations.world_types import Footprint, Pose
    from app.operations.world_trajectory import Arc, Line, fillet_trajectory
    from app.operations.world_clearance import segment_box
    from app.operations.world_geometry import compose_pose, transform_point
    from app.operations.fleet import movement_pose, _at_distance
    from app.operations.fleet_handling import handling_body_root

    world_raw = (args.world_root / 'world.json').read_bytes()
    domain_raw = (args.world_root / 'domain.json').read_bytes()
    world = parse_world(world_raw)
    domain = FactoryCollections.model_validate_json(domain_raw)
    if world.spatial is None:
        raise ValueError('Actual spatial source required')
    profiles = {p.id: p for p in world.spatial.profiles}
    owners = {o.id: o for o in world.owners}
    fleets = {f.id: f for f in domain.fleet}
    states = {s.fleet_id: s for s in domain.vehicle_states}
    truck = fleets['fleet:truck:01']
    profile = profiles[truck.variant]
    support = next(s.pose for s in owners[truck.id].sockets if s.id == truck.load_socket_id)
    decoded = json.loads(args.geometry.read_bytes())
    truck_geometry = [r for r in decoded['rows'] if r['asset_id'] == 'steelflow:transport:truck-flatbed']
    for row in truck_geometry:
        actual_socket = next(s for s in row['frames']['rest']['sockets'] if s['id'] == 'load')
        if math.dist(actual_socket['position_m'], support.position) > 1e-6 or support.yaw_rad != 0:
            raise ValueError('Actual GLB and retained world support differ')
    static = [f for f in world.footprints if owners[f.owner_id].kind not in ('vehicle', 'railcar', 'ship')]
    # The old mobile world poses are not runtime positions. Replace every one with
    # its retained VehicleState-derived body, never delete an actor.
    def actors(vacated: bool) -> list[Footprint]:
        result = []
        for fleet_id, state in states.items():
            if fleet_id == truck.id:
                continue
            fleet = fleets[fleet_id]
            specification = profiles[fleet.variant]
            pose = Pose(position=state.position_m, yaw_rad=state.yaw_rad)
            if vacated and fleet_id == 'fleet:truck:02':
                pose = vacate_end
            socket = next(s.pose for s in owners[fleet_id].sockets if s.id == fleet.load_socket_id)
            load_point = compose_pose(socket, pose)
            center = transform_point(specification.body_offset_m, load_point)
            result.append(Footprint(id='source-live-body:' + fleet_id, owner_id=fleet_id, pose=Pose(position=center, yaw_rad=pose.yaw_rad), size_m=(max(specification.size_m[0], specification.consist_length_m), specification.size_m[1], specification.size_m[2])))
        return result
    escape = next(s for s in world.segments if s.id == 't16:edge:park:escape')
    second = fleets['fleet:truck:02']
    second_socket = next(s.pose for s in owners[second.id].sockets if s.id == second.load_socket_id)
    second_path = fillet_trajectory(escape.points, profiles[second.variant].min_turn_radius_m)
    vacate_duration = math.ceil(second_path.length / escape.speed_m_per_sim_s * 1000)
    vacate_row = MovementSegment(run_id=second.run_id, id='source:truck02:vacate', start_ms=0, end_ms=vacate_duration, job_id='source:setup:vacate', ordinal=0, segment_id=escape.id, from_position_m=states[second.id].position_m, to_position_m=(escape.points[-1][0], escape.points[-1][1] - second_socket.position[1], escape.points[-1][2]))
    vacate_start = movement_pose(world, second, (vacate_row, 0))
    vacate_end = movement_pose(world, second, (vacate_row, vacate_duration))
    if math.dist(vacate_start.position, states[second.id].position_m) > 1e-6 or abs(vacate_start.yaw_rad - states[second.id].yaw_rad) > 1e-6:
        raise ValueError('Proposed vacate must start at the unchanged real actor pose')
    scheduled_actors = actors(True)
    occupied_actors = actors(False)
    if len(scheduled_actors) != len(domain.fleet) - 1:
        raise ValueError('Live actor omitted')
    def cargo_boxes(stage: str, unsafe: bool = False) -> list[Footprint]:
        locations = ('drop1', 'source2') if stage == 'after-first' else ('drop1', 'drop2')
        result = []
        for index, location in enumerate(locations):
            node = next(n for n in world.nodes if n.id == 'v2:t16:' + location)
            result.append(Footprint(id='source-material:' + str(index + 1), owner_id='t16:material:' + str(index + 1), pose=Pose(position=(node.position[0], 2.6, node.position[2] + (0. if unsafe else 6.)), yaw_rad=0.), size_m=(1., 1.2, 1.2)))
        return result
    elapsed = 0
    timeline = []
    starts = {}
    for kind, identity in (('route','t16:edge:home:source1'),('load','source1'),('route','t16:edge:source1:drop1'),('unload','drop1'),('route','t16:edge:drop1:park'),('route','t16:edge:park:source2'),('load','source2'),('route','t16:edge:source2:drop2'),('unload','drop2'),('route','t16:edge:drop2:home')):
        if kind == 'route':
            edge = next(e for e in world.segments if e.id == identity)
            milliseconds = math.ceil(fillet_trajectory(edge.points,profile.min_turn_radius_m).length/edge.speed_m_per_sim_s*1000)
            starts[identity] = elapsed
        else:
            raw = json.loads((args.world_root/(f'lod0/{identity}-'+('load-source.json' if kind=='load' else 'unload.json'))).read_bytes())
            milliseconds = sum(s['duration_ms'] for p in raw['phases'] for s in p['segments'])
        timeline.append({'kind':kind,'id':identity,'start_ms':elapsed,'end_ms':elapsed+milliseconds})
        elapsed += milliseconds
    paths = [
        ('t16:edge:drop1:park', 'after-first', starts['t16:edge:drop1:park']),
        ('t16:edge:park:source2', 'after-first', starts['t16:edge:park:source2']),
        ('t16:edge:drop2:home', 'after-second', starts['t16:edge:drop2:home']),
    ]
    # In each arc interval the root lies within sagitta of its chord. A body's
    # rotation relative to midpoint heading is bounded by 2R*sin(deltaYaw/4).
    # This is a continuous outward bound, not temporal point sampling.
    def intervals(path):
        result = []
        distance = 0.
        for primitive in path.primitives:
            if isinstance(primitive, Line):
                _, yaw = _at_distance(path, distance + primitive.length / 2)
                result.append((primitive.start, primitive.end, yaw, 0., 0., 'line'))
            elif isinstance(primitive, Arc):
                count = max(1, math.ceil(abs(primitive.angle) / .01))
                delta = abs(primitive.angle) / count
                for index in range(count):
                    a = primitive.at(index / count)
                    b = primitive.at((index + 1) / count)
                    _, yaw = _at_distance(path, distance + primitive.length * (index + .5) / count)
                    result.append((a, b, yaw, delta, primitive.radius * (1 - math.cos(delta / 2)), 'arc-bound'))
            else:
                raise ValueError('Unsupported retained trajectory primitive')
            distance += primitive.length
        return result
    def hits_for(boxes, floor_y: float, path, obstacles):
        hits = []
        checks = 0
        floor_contacts = set()
        proof_intervals = intervals(path)
        radius = max(math.hypot(b['center_m'][0], b['center_m'][2]) + math.hypot(b['size_m'][0]/2, b['size_m'][2]/2) for b in boxes) + profile.clearance_m
        for a, b, yaw, delta, sagitta, kind in proof_intervals:
            candidates = []
            for obstacle in obstacles:
                diagonal = math.hypot(obstacle.size_m[0], obstacle.size_m[2]) / 2
                if obstacle.pose.position[0] + diagonal < min(a[0], b[0]) - radius or obstacle.pose.position[0] - diagonal > max(a[0], b[0]) + radius or obstacle.pose.position[2] + diagonal < min(a[2], b[2]) - radius or obstacle.pose.position[2] - diagonal > max(a[2], b[2]) + radius:
                    continue
                if obstacle.pose.position[1] + obstacle.size_m[1]/2 <= min(a[1], b[1]) - support.position[1] + floor_y + 1e-6:
                    floor_contacts.add(obstacle.id)
                    continue
                candidates.append(obstacle)
            for body in boxes:
                x, y, z = body['center_m']
                dx = math.cos(yaw)*x + math.sin(yaw)*z
                dz = -math.sin(yaw)*x + math.cos(yaw)*z
                center_line = Line((a[0]+dx, a[1]-support.position[1]+y+profile.clearance_m/2, a[2]+dz), (b[0]+dx, b[1]-support.position[1]+y+profile.clearance_m/2, b[2]+dz))
                rotation_error = 2*(math.hypot(x,z)+math.hypot(body['size_m'][0]/2,body['size_m'][2]/2))*math.sin(delta/4)
                for obstacle in candidates:
                    relative = yaw + body['yaw_rad'] - obstacle.pose.yaw_rad
                    hx, hy, hz = (v/2 for v in body['size_m'])
                    inflation = (abs(math.cos(relative))*hx+abs(math.sin(relative))*hz+profile.clearance_m+rotation_error+sagitta,hy+profile.clearance_m/2,abs(math.sin(relative))*hx+abs(math.cos(relative))*hz+profile.clearance_m+rotation_error+sagitta)
                    checks += 1
                    if segment_box(center_line, obstacle, inflation):
                        if len(hits) < 200:
                            hits.append({'body_box': body['id'], 'obstacle_id': obstacle.id, 'owner_id': obstacle.owner_id, 'primitive_kind': kind, 'support_start': a, 'support_end': b})
        return {'hits': hits, 'continuous_bound_intervals': len(proof_intervals), 'box_obstacle_checks': checks, 'nonpenetrating_support_plane_ids': sorted(floor_contacts)}
    rows = []
    frame_witnesses = []
    for level in range(3):
        body_raw = (args.world_root / f'lod{level}/body-shape.json').read_bytes()
        body = json.loads(body_raw)
        actual = next(r for r in truck_geometry if r['lod'] == level)
        physical = [m for m in actual['frames']['rest']['meshes'] if m['physical']]
        floor_y = min(m['min_m'][1] for m in physical)
        for segment_id, stage, start_ms in paths:
            segment = next(s for s in world.segments if s.id == segment_id)
            path = fillet_trajectory(segment.points, profile.min_turn_radius_m)
            duration = math.ceil(path.length / segment.speed_m_per_sim_s * 1000)
            row = MovementSegment(run_id=truck.run_id, id='source:' + segment_id, start_ms=start_ms, end_ms=start_ms+duration, job_id='source:empty-return', ordinal=0, segment_id=segment.id, from_position_m=(segment.points[0][0], segment.points[0][1]-support.position[1], segment.points[0][2]), to_position_m=(segment.points[-1][0], segment.points[-1][1]-support.position[1], segment.points[-1][2]))
            for fraction in (0., .25, .5, .75, 1.):
                at = row.start_ms + round(duration*fraction)
                root = movement_pose(world, truck, (row, at))
                direct = handling_body_root(root, support, 'asset_root')
                support_point = compose_pose(support, root)
                reconstructed = handling_body_root(support_point, support, 'load_support')
                if math.dist(root.position, reconstructed.position) > 1e-12 or direct != root:
                    raise ValueError('Socket inverse/double offset mismatch')
                frame_witnesses.append({'lod': level, 'segment_id': segment.id, 'at_ms': at, 'actual_movement_pose': root.model_dump(), 'reconstructed_root': reconstructed.model_dump(), 'support': support_point.model_dump()})
            obstacles = [*static, *scheduled_actors, *cargo_boxes(stage)]
            positive = hits_for(body['boxes'], floor_y, path, obstacles)
            occupied = hits_for(body['boxes'], floor_y, path, [*static, *occupied_actors, *cargo_boxes(stage)]) if segment_id.endswith('drop1:park') else None
            unsafe = hits_for(body['boxes'], floor_y, path, [*static, *scheduled_actors, *cargo_boxes(stage, True)]) if segment_id.endswith('drop1:park') else None
            rows.append({'lod': level, 'segment_id': segment.id, 'source_body_shape_sha256': hashlib.sha256(body_raw).hexdigest(), 'source_glb_sha256': body['glb_sha256'], 'actual_analytic_primitives': [asdict(p) | {'kind': type(p).__name__} for p in path.primitives], 'unchanged_turn_radius_m': profile.min_turn_radius_m, 'unchanged_clearance_m': profile.clearance_m, 'live_actors_other_than_self': len(scheduled_actors), 'cargo_obstacles': [f.model_dump() for f in cargo_boxes(stage)], 'positive_source_schedule': positive, 'occupied_park_negative': occupied, 'unsafe_old_stop_material_negative': unsafe})
    good = all(not row['positive_source_schedule']['hits'] for row in rows)
    negatives = all(row['occupied_park_negative']['hits'] and row['unsafe_old_stop_material_negative']['hits'] for row in rows if row['occupied_park_negative'] is not None)
    result = {'status': 'SOURCE_EMPTY_DEPARTURE_BOUND_PASS_RUNTIME_PENDING' if good and negatives else 'SOURCE_EMPTY_DEPARTURE_RED', 'authority': 'Conditional explicit source schedule, not T16 dispatch/SQL execution or independent physical admission.', 'world_sha256': hashlib.sha256(world_raw).hexdigest(), 'domain_sha256': hashlib.sha256(domain_raw).hexdigest(), 'source_schedule': {'truck02_vacate': vacate_row.model_dump(), 'actual_kernel_start': vacate_start.model_dump(), 'actual_kernel_end': vacate_end.model_dump(), 'vacate_complete_before_first_return': vacate_duration < paths[0][2], 'all_initial_fleet_rows_and_poses_preserved': True, 'timeline': timeline, 'source_time_semantics': 'Proposed pure-kernel route schedule; no event/attachment/writer mutation or claim of executed T16 receipts.'}, 'rows': rows, 'frame_witnesses': frame_witnesses, 'no_delivered_cargo_exclusion': True, 'no_downward_clearance_inflation': 'Existing nonpenetrating support-plane rule; actual decoded body floor, 1um representation tolerance only.', 'other_actors': 'Every retained live VehicleState projected through its actual support and original conservative body profile; no actor deleted. Full all-family actual mesh admission remains pending.', 'unmet': ['Actual T66 compound/runtime consumer and active parked-footprint replacement.', 'Authenticated original single-clock handling/traffic/other-actor movement receipts and SQL positive.', 'Independent current source classification/geometry gate and all-family material operations.', 'No Ackermann/no-slip or vehicle dynamics certification from this geometric bound.'], 'cleanup': {'database_used': False, 'server_started': False}}
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False)+'\n')
    print(json.dumps({'status': result['status'], 'routes': len(rows), 'positive_hits': sum(len(r['positive_source_schedule']['hits']) for r in rows), 'negative_cases_reject': bool(negatives)}))
    if not good or not negatives:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
