"""Run faithful curl -i snapshots against the local QA backend."""
import json
import subprocess
from pathlib import Path

out = Path(__file__).parent
base = 'http://127.0.0.1:8001/api/v1'
commands = []

def call(name, method, endpoint):
    args = ['curl', '-i', '-sS', '-X', method, f'{base}/{endpoint}']
    commands.append(' '.join(args))
    result = subprocess.run(args, check=True, capture_output=True, text=True)
    (out / f'transport-http-{name}.txt').write_text(result.stdout)
    header, body = result.stdout.split('\n\n', 1)
    assert '200 OK' in header, header
    return json.loads(body)

initial = call('initial', 'POST', 'scenarios/NORMAL/activate')
states = [initial]
for tick in range(1, 8):
    value = call(f'tick{tick}', 'POST', 'simulation/step')
    assert value['simulation']['tick'] == tick
    states.append(value)

p6 = states[6]['production']
p7 = states[7]['production']
b6 = next(batch for batch in p6['batches'] if batch['id'] == 'PROD-GI')
b7 = next(batch for batch in p7['batches'] if batch['id'] == 'PROD-GI')
t6 = next(leg for leg in p6['transports'] if leg['id'] == b6['active_transport_id'])
assert [t6[key] for key in ['from_stage', 'to_stage', 'start_tick', 'end_tick', 'material_form', 'mass_kg']] == ['hot_rolling', 'cold_rolling', 6, 7, 'HR', 23000]
assert b6['status'] == 'in_transit'
assert not any(b6['id'] in stage['batch_ids'] for stage in p6['stages'])
assert [b7[key] for key in ['status', 'current_location_id', 'equipment_id']] == ['running', 'cold_rolling', 'PICKLE-01']
assert next(leg for leg in p7['transports'] if leg['id'] == t6['id'])['status'] == 'completed'
reset = call('reset', 'POST', 'simulation/reset')
assert reset['production'] == initial['production']
(out / 'transport-http-invocations.txt').write_text('\n'.join(commands) + '\n')
(out / 'transport-http-verdict.json').write_text(json.dumps({'status': 'PASS', 'departure': {'tick': 6, 'vehicle': b6['current_location_id'], 'mass': b6['mass_kg']}, 'arrival': {'tick': 7, 'equipment': b7['equipment_id']}, 'resetExact': True}, indent=2) + '\n')
print('PASS: curl HTTP snapshots, tick6 departure, tick7 arrival, reset exact equality')
