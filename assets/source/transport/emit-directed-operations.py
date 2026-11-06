"""Emit explicit D3 load bytes from the retained complete directed source path.

This compiler grants no physical/runtime authority and does not reverse arbitrary
recipes. It accepts only this exact five-phase authored parked source witness.
"""
import argparse
import copy
import hashlib
import json
import shutil
from pathlib import Path


def encode(value: object) -> bytes:
    return (json.dumps(value, indent=2, allow_nan=False) + '\n').encode()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError('New output directory required')
    args.output.mkdir(parents=True)
    for source in args.input.rglob('*'):
        if source.is_file():
            destination = args.output / source.relative_to(args.input)
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, destination)
    records = []
    for level in range(3):
        root_path = args.output / f'handling-lod{level}.json'
        root = json.loads(root_path.read_bytes())
        load_refs = []
        for station in ('source1', 'drop1', 'source2', 'drop2'):
            canonical_path = args.input / f'lod{level}/{station}-unload.json'
            source_path = args.input / f'lod{level}/{station}-load-source.json'
            canonical = json.loads(canonical_path.read_bytes())
            inverse = json.loads(source_path.read_bytes())
            if inverse['format'] != 'transport-explicit-inverse-source-v1' or inverse['canonical_unload_sha256'] != hashlib.sha256(canonical_path.read_bytes()).hexdigest():
                raise ValueError('Exact retained source witness required')
            if canonical['recipe_id'] != 'motion:scope:internal:unload' or inverse['recipe_id'] != 'motion:scope:internal:load':
                raise ValueError('Only the two sealed D3 recipe literals are supported')
            load = copy.deepcopy(canonical)
            load_id = f't28:operation:{station}:load'
            load['id'] = load_id
            load['recipe_id'] = 'motion:scope:internal:load'
            load['phases'] = copy.deepcopy(inverse['phases'])
            for phase in load['phases']:
                phase['id'] = load_id + ':' + phase['kind']
                for index, segment in enumerate(phase['segments']):
                    segment['id'] = phase['id'] + ':' + str(index)
                    if not all(c['window_id'] == 'load' for c in segment['channels']):
                        raise ValueError('Load window mismatch')
            load['handoffs'] = copy.deepcopy(inverse['handoffs'])
            load['handoffs'][0]['id'] = load_id + ':acquire-handler'
            load['handoffs'][1]['id'] = load_id + ':acquire-fleet'
            for contact in load['contacts']:
                contact['id'] = load_id + ':' + contact['socket_id']
            if [p['kind'] for p in load['phases']] != ['grip','lift','translate','lower','release']:
                raise ValueError('Complete physical phase sequence required')
            previous = [c['value'] for c in load['parked_channels']]
            for phase in load['phases']:
                for segment in phase['segments']:
                    if [c['start_value'] for c in segment['channels']] != previous:
                        raise ValueError('Parked source continuity mismatch')
                    previous = [c['end_value'] for c in segment['channels']]
            if previous != [c['value'] for c in load['parked_channels']]:
                raise ValueError('Empty handler did not restore parked state')
            relative = f'lod{level}/{station}-load.json'
            raw = encode(load)
            target = args.output / relative
            target.write_bytes(raw)
            reference = {'id': load_id, 'path': relative, 'sha256': hashlib.sha256(raw).hexdigest()}
            load_refs.append(reference)
            records.append(reference | {'lod': level, 'source_witness_sha256': hashlib.sha256(source_path.read_bytes()).hexdigest(), 'destination_port_id_means': 'Exact nonfleet material source endpoint under D3', 'source_location_id': load['destination_port_id'], 'truck_stop_id': load['stop_node_id']})
        root['load_operations'] = load_refs
        root_path.write_bytes(encode(root))
    receipt = {'status': 'D3_FULL_DIRECTED_LOAD_SOURCE_EMITTED_PRODUCT_PARSE_AND_PHYSICAL_ADMISSION_PENDING', 'canonical_unloads_unchanged': True, 'world_and_domain_raw_bytes_unchanged': True, 'full_loads': records, 'qualification': 'New full operation bytes; original inverse witness is not admitted directly. No runtime or SQL authority.'}
    (args.output / 'directed-load-generation.json').write_bytes(encode(receipt))
    print(json.dumps({'status': receipt['status'], 'full_loads': len(records)}))


if __name__ == '__main__':
    main()
