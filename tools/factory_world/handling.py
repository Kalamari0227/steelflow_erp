"""Compile a distinct synthetic handling world from exact source bytes.

The generated bounds/receipts are source inputs, never physical admission tokens.
No source world/domain, live run, SQL, profile size or route is modified.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

SOURCE_WORLD_SHA = 'd6a9bcf08dc9ae773ec75a636f952ad8126896735b151e9e6310593275c268b5'
SOURCE_DOMAIN_SHA = '2bca834a7e9a3a63bd3fc606ca5c72b94c7ca95a600fecb91e8a64e42cbe70df'
STATIONS = ('source1', 'drop1', 'source2', 'drop2')
PARKED = (6.0, 0.0, 2.0)


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def encode(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n').encode()


def write_new(path: Path, raw: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('xb') as stream:
        stream.write(raw)


def trajectory(direction: str) -> list[dict[str, Any]]:
    """Explicit directed parked paths; no arbitrary automatic inverse permission."""
    if direction == 'unload':
        phases = (
            ('grip', ((6000, PARKED, (0., 0., 2.)), (4000, (0., 0., 2.), (0., 0., 0.)), (3200, (0., 0., 0.), (0., 1.6, 0.)))),
            ('lift', ((4000, (0., 1.6, 0.), (0., 1.6, 2.)),)),
            ('translate', ((6000, (0., 1.6, 2.), (6., 1.6, 2.)),)),
            ('lower', ((4000, (6., 1.6, 2.), (6., 1.6, 0.)),)),
            ('release', ((3200, (6., 1.6, 0.), (6., 0., 0.)), (4000, (6., 0., 0.), PARKED))),
        )
    elif direction == 'load':
        phases = (
            ('grip', ((4000, PARKED, (6., 0., 0.)), (3200, (6., 0., 0.), (6., 1.6, 0.)))),
            ('lift', ((4000, (6., 1.6, 0.), (6., 1.6, 2.)),)),
            ('translate', ((6000, (6., 1.6, 2.), (0., 1.6, 2.)),)),
            ('lower', ((4000, (0., 1.6, 2.), (0., 1.6, 0.)),)),
            ('release', ((3200, (0., 1.6, 0.), (0., 0., 0.)), (4000, (0., 0., 0.), (0., 0., 2.)), (6000, (0., 0., 2.), PARKED))),
        )
    else:
        raise ValueError('Only explicit load/unload source paths are supported')
    return [{'kind': kind, 'segments': [{'duration_ms': duration, 'start': list(start), 'end': list(end)} for duration, start, end in segments]} for kind, segments in phases]


def compile_world(args: argparse.Namespace) -> dict[str, Any]:
    sys.path.insert(0, str(args.contract_root / 'backend'))
    from app.operations.world_contract import parse_world, read_json
    from app.operations.fleet_handling import parse_handling_bytes
    from app.operations.fleet_handling_domain import InitialCradle, validate_initial_domain

    source_world_raw = args.source_world.read_bytes()
    source_domain_raw = args.source_domain.read_bytes()
    if digest(source_world_raw) != SOURCE_WORLD_SHA or digest(source_domain_raw) != SOURCE_DOMAIN_SHA:
        raise ValueError('Original source world/collections byte pin mismatch')
    source_world = read_json(source_world_raw)
    source_domain = read_json(source_domain_raw)
    if not isinstance(source_world, dict) or not isinstance(source_domain, dict):
        raise ValueError('Complete source objects required')
    parse_world(source_world_raw)
    geometry_raw = args.geometry.read_bytes()
    geometry = read_json(geometry_raw)
    if not isinstance(geometry, dict) or geometry['format'] != 'transport-decoded-handling-geometry-v1':
        raise ValueError('Actual decoded geometry input required')
    manifest_raw = (args.asset_root / 'public/assets/steelworks/transport/manifest.json').read_bytes()
    if digest(manifest_raw) != geometry['asset_manifest_sha256']:
        raise ValueError('Decoded geometry/manifest hash mismatch')
    manifest = read_json(manifest_raw)
    inventory = read_json((args.asset_root / 'assets/source/transport/solid-inventory.json').read_bytes())
    if not isinstance(manifest, dict) or not isinstance(inventory, dict):
        raise ValueError('Complete source asset inputs required')
    rows = geometry['rows']
    if len(rows) != 9:
        raise ValueError('Exact9 actual priority GLBs required')
    for row in rows:
        asset = next(a for a in manifest['assets'] if a['id'] == row['asset_id'])
        lod = next(l for l in asset['lods'] if l['level'] == row['lod'])
        if digest((args.asset_root / lod['artifact']['path']).read_bytes()) != row['glb_sha256']:
            raise ValueError('Decoded GLB hash mismatch')
    world = copy.deepcopy(source_world)
    profile = next(p for p in world['spatial']['profiles'] if p['id'] == 'truck')
    profile['handling_shape_id'] = 't28:shape:truck'
    new_ids: dict[str, list[str]] = {k: [] for k in ('owners', 'nodes', 'ports', 'footprints')}
    footprint_map: list[dict[str, Any]] = []
    station_rows = []
    for station in STATIONS:
        node = next(n for n in source_world['nodes'] if n['id'] == 'v2:t16:' + station)
        stop = node['position']
        handler_id = 't28:handler:' + station
        cradle_id = 't28:cradle:' + station
        port_id = 'v2:t28:cradle:' + station
        cradle_node = 'v2:t28:cradle-node:' + station
        for key, owner_id, shift in (('crane-yard', handler_id, [stop[0], 0., stop[2]]), ('receiving-cradle', cradle_id, [stop[0], 0., stop[2] + 6.])):
            subset = [r for r in rows if r['asset_id'] == 'steelflow:transport:' + key]
            if len(subset) != 3:
                raise ValueError('Every assembly needs all3 decoded LODs')
            first = next(r for r in subset if r['lod'] == 0)
            sockets = [{'id': s['id'], 'pose': {'position': s['position_m'], 'yaw_rad': 0.}} for s in first['frames']['rest']['sockets']]
            world['owners'].append({'id': owner_id, 'kind': 'equipment', 'modes': ['road'], 'pose': {'position': shift, 'yaw_rad': 0.}, 'sockets': sockets})
            new_ids['owners'].append(owner_id)
            names = [m['id'] for m in first['frames']['parked']['meshes'] if m['physical']]
            for row in subset:
                if [m['id'] for m in row['frames']['parked']['meshes'] if m['physical']] != names:
                    raise ValueError('LOD physical mesh universe mismatch')
            for name in names:
                meshes = [next(m for m in r['frames']['parked']['meshes'] if m['id'] == name) for r in subset]
                if len({m['moving'] for m in meshes}) != 1:
                    raise ValueError('Moving hierarchy differs across LODs')
                low = [min(m['min_m'][axis] for m in meshes) for axis in range(3)]
                high = [max(m['max_m'][axis] for m in meshes) for axis in range(3)]
                footprint_id = 'fp:t28:' + station + ':' + key + ':' + name
                size = [high[i] - low[i] for i in range(3)]
                if not all(s > 0 for s in size):
                    raise ValueError('Physical footprint must have positive volume')
                world['footprints'].append({'id': footprint_id, 'owner_id': owner_id, 'pose': {'position': [(low[i] + high[i]) / 2 + shift[i] for i in range(3)], 'yaw_rad': 0.}, 'size_m': size})
                new_ids['footprints'].append(footprint_id)
                footprint_map.append({'footprint_id': footprint_id, 'owner_id': owner_id, 'asset_id': first['asset_id'], 'mesh_node_ids': [name], 'moving': meshes[0]['moving'], 'parked_channels': list(PARKED) if key == 'crane-yard' else [], 'per_lod_glb_sha256': {str(r['lod']): r['glb_sha256'] for r in subset}, 'basis': 'Outward union of actual decoded per-mesh AABBs over3LODs; not a full swept envelope or admission certificate.'})
        world['nodes'].append({'id': cradle_node, 'modes': ['road'], 'position': [stop[0], 2., stop[2] + 6.]})
        world['ports'].append({'id': port_id, 'owner_id': cradle_id, 'socket_id': 'support', 'node_id': cradle_node, 'capacity_kg': 40000, 'modes': ['road']})
        new_ids['nodes'].append(cradle_node)
        new_ids['ports'].append(port_id)
        station_rows.append({'station': station, 'stop_node_id': node['id'], 'handler_owner_id': handler_id, 'cradle_owner_id': cradle_id, 'cradle_port_id': port_id, 'truck_root_m': [stop[0], 0., stop[2]], 'material_cradle_root_m': [stop[0], 2.6, stop[2] + 6.]})
    for key in ('nodes', 'owners', 'ports', 'footprints'):
        if world[key][:len(source_world[key])] != source_world[key]:
            raise ValueError('Old world identity/value changed')
    normalized = copy.deepcopy(world)
    del next(p for p in normalized['spatial']['profiles'] if p['id'] == 'truck')['handling_shape_id']
    for key in new_ids:
        normalized[key] = normalized[key][:len(source_world[key])]
    if normalized != source_world:
        raise ValueError('Unlisted world delta')
    world_raw = encode(world)
    typed_world = parse_world(world_raw)
    # Replace only the raw attachment array, retaining every MaterialVersion byte.
    domain = copy.deepcopy(source_domain)
    initial = []
    for number in (1, 2):
        station = 'source' + str(number)
        row = next(s for s in station_rows if s['station'] == station)
        attachment = next(a for a in domain['attachments'] if a['material_id'] == 't16:material:' + str(number))
        attachment['owner_id'] = row['cradle_port_id']
        initial.append(InitialCradle(attachment['material_id'], row['cradle_port_id'], row['cradle_owner_id'], 'support'))
    text = source_domain_raw.decode()
    match = re.search(r'"attachments"\s*:\s*', text)
    if match is None:
        raise ValueError('Source attachment array absent')
    _, length = json.JSONDecoder().raw_decode(text[match.end():])
    domain_raw = (text[:match.end()] + json.dumps(domain['attachments'], indent=2, allow_nan=False) + text[match.end()+length:]).encode()
    domain_delta = validate_initial_domain(source_domain_raw, domain_raw, typed_world, initial)
    args.out.mkdir(parents=True, exist_ok=False)
    write_new(args.out / 'source-world.json', source_world_raw)
    write_new(args.out / 'source-domain.json', source_domain_raw)
    write_new(args.out / 'world.json', world_raw)
    write_new(args.out / 'domain.json', domain_raw)
    write_new(args.out / 'asset-manifest.json', manifest_raw)
    structure_results = []
    for level in range(3):
        truck = next(r for r in rows if r['asset_id'] == 'steelflow:transport:truck-flatbed' and r['lod'] == level)
        handler = next(r for r in rows if r['asset_id'] == 'steelflow:transport:crane-yard' and r['lod'] == level)
        solid = next(r for r in inventory['assets'] if r['asset_id'] == truck['asset_id'] and r['lod'] == level)
        body = {'format': 'fleet-handling-body-shape-v1', 'id': 't28:shape:truck', 'profile_id': 'truck', 'asset_id': truck['asset_id'], 'glb_sha256': truck['glb_sha256'], 'source_body_mesh_nodes': solid['source_body_mesh_nodes'], 'boxes': solid['boxes'], 'load_support_socket_id': 'load', 'body_shape_frame': 'asset_root', 'route_frame': 'load_support'}
        body_path = f'lod{level}/body-shape.json'
        body_raw = encode(body)
        write_new(args.out / body_path, body_raw)
        children = {body_path: body_raw}
        references = []
        functions = handler['binding']['functions']
        if [f['function_id'] for f in functions] != ['bridge_travel', 'trolley_travel', 'hoist']:
            raise ValueError('Exact handler canonical function order changed')
        def values(scalars: list[float] | tuple[float, ...]) -> list[dict[str, Any]]:
            return [{k: f[k] for k in ('function_id', 'node_id', 'kind', 'axis', 'pivot_m')} | {'value': value} for f, value in zip(functions, scalars, strict=True)]
        def phases(direction: str, identity: str) -> list[dict[str, Any]]:
            output = []
            for phase in trajectory(direction):
                segments = []
                for index, segment in enumerate(phase['segments']):
                    channels = [{k: f[k] for k in ('function_id', 'node_id', 'kind', 'axis', 'pivot_m')} | {'window_id': direction, 'start_value': start, 'end_value': end} for f, start, end in zip(functions, segment['start'], segment['end'], strict=True)]
                    segments.append({'id': identity + ':' + phase['kind'] + ':' + str(index), 'duration_ms': segment['duration_ms'], 'channels': channels})
                output.append({'id': identity + ':' + phase['kind'], 'kind': phase['kind'], 'duration_ms': sum(s['duration_ms'] for s in segments), 'channel_ids': [f['function_id'] for f in functions], 'segments': segments})
            return output
        for station in station_rows:
            name = station['station']
            op_id = 't28:operation:' + name + ':unload'
            moving = [{'footprint_id': f['footprint_id'], 'mesh_node_ids': f['mesh_node_ids']} for f in footprint_map if f['owner_id'] == station['handler_owner_id'] and f['moving']]
            operation = {'format': 'fleet-handling-operation-v1', 'id': op_id, 'fleet_profile_id': 'truck', 'body_shape_id': body['id'], 'body_shape_sha256': digest(body_raw), 'stop_node_id': station['stop_node_id'], 'truck_load_socket_id': 'load', 'handler_owner_id': station['handler_owner_id'], 'handler_pick_socket_id': 'pick', 'handler_drop_socket_id': 'drop', 'destination_port_id': station['cradle_port_id'], 'destination_support_socket_id': 'support', 'recipe_id': 'motion:scope:internal:unload', 'allowed_forms': ['HR_COIL'], 'max_mass_kg': 40000, 'phases': phases('unload', op_id), 'reserved_resource_ids': [station['handler_owner_id'], station['cradle_port_id'], station['stop_node_id'], *[f['footprint_id'] for f in moving]], 'contacts': [{'id': op_id + ':' + socket, 'owner_id': station['handler_owner_id'], 'policy_id': 'policy:fleet:crane', 'socket_id': socket, 'kind': 'horizontal_coil_inner_top', 'surface_node_id': 'c_hook_load_arm', 'asset_manifest_sha256': digest(manifest_raw), 'glb_sha256': handler['glb_sha256'], 'motion_function_ids': [f['function_id'] for f in functions]} for socket in ('pick', 'drop')], 'handoffs': [{'id': op_id + ':acquire-handler', 'from_owner_id': 'fleet:truck:01', 'from_socket_id': 'load', 'from_contact_kind': 'legacy_outer_bottom', 'to_owner_id': station['handler_owner_id'], 'to_socket_id': 'pick', 'to_contact_kind': 'horizontal_coil_inner_top', 'endpoint_channels': values((0., 1.6, 0.))}, {'id': op_id + ':acquire-cradle', 'from_owner_id': station['handler_owner_id'], 'from_socket_id': 'drop', 'from_contact_kind': 'horizontal_coil_inner_top', 'to_owner_id': station['cradle_owner_id'], 'to_socket_id': 'support', 'to_contact_kind': 'legacy_outer_bottom', 'endpoint_channels': values((6., 1.6, 0.))}], 'parked_channels': values(PARKED), 'moving_footprints': moving}
            path = f'lod{level}/{name}-unload.json'
            raw = encode(operation)
            write_new(args.out / path, raw)
            children[path] = raw
            references.append({'id': op_id, 'path': path, 'sha256': digest(raw)})
            inverse = {'format': 'transport-explicit-inverse-source-v1', 'id': 't28:operation:' + name + ':load-source', 'canonical_unload_id': op_id, 'canonical_unload_sha256': digest(raw), 'qualification': 'Exact source trajectory only. Current sealed T66 parser cannot admit inverse handoff direction; no runtime authority.', 'recipe_id': 'motion:scope:internal:load', 'phases': phases('load', 't28:operation:' + name + ':load-source'), 'parked_channels': values(PARKED), 'handoffs': [operation['handoffs'][1] | {'from_owner_id': station['cradle_owner_id'], 'from_socket_id': 'support', 'from_contact_kind': 'legacy_outer_bottom', 'to_owner_id': station['handler_owner_id'], 'to_socket_id': 'pick', 'to_contact_kind': 'horizontal_coil_inner_top', 'endpoint_channels': values((6., 1.6, 0.))}, operation['handoffs'][0] | {'from_owner_id': station['handler_owner_id'], 'from_socket_id': 'drop', 'from_contact_kind': 'horizontal_coil_inner_top', 'to_owner_id': 'fleet:truck:01', 'to_socket_id': 'load', 'to_contact_kind': 'legacy_outer_bottom', 'endpoint_channels': values((0., 1.6, 0.))}]}
            write_new(args.out / f'lod{level}/{name}-load-source.json', encode(inverse))
        root = {'format': 'fleet-handling-v1', 'source_world_sha256': digest(source_world_raw), 'derived_world_sha256': digest(world_raw), 'asset_manifest_sha256': digest(manifest_raw), 'body_shapes': [{'id': body['id'], 'path': body_path, 'sha256': digest(body_raw)}], 'unload_operations': references}
        root_raw = encode(root)
        parsed = parse_handling_bytes(root_raw, children)
        write_new(args.out / f'handling-lod{level}.json', root_raw)
        structure_results.append({'lod': level, 'root_sha256': digest(root_raw), 'operations': len(parsed.operations), 'status': 'STRUCTURE_ONLY_NOT_PHYSICAL_ADMISSION'})
    receipt = {'format': 'transport-handling-source-generation-receipt-v1', 'status': 'SOURCE_COMPILED_PHYSICAL_ADMISSION_PENDING', 'source_world_sha256': digest(source_world_raw), 'derived_world_sha256': digest(world_raw), 'source_domain_sha256': digest(source_domain_raw), 'derived_domain_sha256': digest(domain_raw), 'asset_manifest_sha256': digest(manifest_raw), 'geometry_input_sha256': digest(geometry_raw), 'source_extension_ids': new_ids, 'changed_existing_world_paths': ['spatial/profiles/truck/handling_shape_id'], 'domain_changed_paths': list(domain_delta.changed_paths), 'source_material_versions_raw_unchanged': True, 'original_world_rows_and_routes_unchanged': True, 'original_profile_size_offsets_clearance_turn_radius_unchanged': True, 'stations': station_rows, 'footprints': footprint_map, 'structures': structure_results, 'inverse_admission': 'UNAVAILABLE_IN_CURRENT_SEALED_T66_PARSER', 'physical_admission': False, 'runtime_installed': False, 'actual_python_import': str(Path(sys.modules['app.operations.fleet_handling'].__file__).resolve())}
    write_new(args.out / 'generation-receipt.json', encode(receipt))
    return {'status': receipt['status'], 'world_sha256': receipt['derived_world_sha256'], 'owners_added': len(new_ids['owners']), 'footprints_added': len(new_ids['footprints']), 'operations': 12, 'inverse_source_paths': 12}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('source-world', 'source-domain', 'asset-root', 'geometry', 'contract-root', 'out'):
        parser.add_argument('--' + name, required=True, type=Path)
    args = parser.parse_args()
    for name in ('source_world', 'source_domain', 'asset_root', 'geometry', 'contract_root'):
        setattr(args, name, getattr(args, name).resolve(strict=True))
    args.out = args.out.absolute()
    if args.out.exists():
        raise ValueError('Output must be a new owned directory')
    print(json.dumps(compile_world(args), sort_keys=True))


if __name__ == '__main__':
    main()
