import json
import subprocess
import time
from pathlib import Path

out = Path(__file__).parent
base = 'http://127.0.0.1:8001/api/v1/journey'
commands = []

def call(name, method, endpoint='', body=None, expected=200):
    args = ['curl', '-i', '-sS', '-X', method, base + endpoint]
    if body is not None:
        args += ['-H', 'Content-Type: application/json', '--data', json.dumps(body)]
    commands.append(args)
    result = subprocess.run(args, check=True, capture_output=True, text=True)
    (out / f'journey-http-{name}.txt').write_text(result.stdout)
    header, payload = result.stdout.split('\n\n', 1)
    assert header.startswith(f'HTTP/1.1 {expected}'), header
    return json.loads(payload)

catalog = call('catalog', 'GET', '/products')['products']
assert len(catalog) == 17 and len({item['family'] for item in catalog}) == 8
assert sum(len(item['steps']) for item in catalog) == 187
initial = call('initial', 'POST', '/select', {'product_id': 'hr'})
assert initial['material']['form'] == 'SLAB'
first = call('first-boundary', 'POST', '/step')
assert first['elapsed_ms'] == 4000 and first['material']['form'] == 'SLAB'
call('play', 'POST', '/play')
time.sleep(.25)
partial = call('partial-furnace', 'POST', '/pause')
assert 4000 < partial['elapsed_ms'] < 10000
assert partial['material']['form'] == 'SLAB' and len(partial['history']) == 2
second = call('furnace-boundary', 'POST', '/step')
assert second['elapsed_ms'] == 10000 and second['material']['form'] == 'HOT_SLAB'
assert second['material']['parent_version_id'] == first['material']['version_id']
for index in range(3, 10):
    final = call(f'boundary-{index}', 'POST', '/step')
assert final['completed'] and final['elapsed_ms'] == 45800
assert final['material']['form'] == 'HR_COIL' and final['material']['role'] == 'sale_product'
assert final['material']['mass_kg'] == 20000 and final['material']['lineage_id'] == 'MATERIAL-hr'
call('unknown-product', 'POST', '/select', {'product_id': 'unknown-route'}, 404)
call('invalid-speed', 'POST', '/speed', {'speed': 8}, 422)
unchanged = call('after-invalid', 'GET')
assert unchanged == final
reset = call('reset', 'POST', '/reset')
assert reset['material'] == initial['material'] and reset['history'] == initial['history']
assert reset['run_id'] != initial['run_id']
(out / 'journey-http-invocations.json').write_text(json.dumps(commands, indent=2))
(out / 'journey-http-verdict.json').write_text(json.dumps({'verdict': 'PASS', 'routes': 17, 'families': 8, 'steps': 187, 'partial_elapsed_ms': partial['elapsed_ms'], 'partial_form': partial['material']['form'], 'final_form': final['material']['form'], 'duration_ms': final['elapsed_ms'], 'invalid_requests_unchanged': True, 'reset_exact_material': True}, indent=2))
print('PASS:17routes/8families/187steps; no premature furnace transform; HR complete45800ms; invalid404/422 no mutation; reset material exact')
