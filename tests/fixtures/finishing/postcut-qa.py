"""Cross both public motion CLIs using exact actual-child synthetic winding cases."""
# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
# Run with the project-authorized literal backend/.venv/bin/python.
from pathlib import Path
import argparse
import copy
import hashlib
import json
import os
import subprocess
import sys
import datetime

parser = argparse.ArgumentParser(description=__doc__)
for name in ['inputs', 'inputs-sha', 'runtime', 'node-cli', 'out']:
    parser.add_argument('--'+name, required=True)
args = parser.parse_args()
source = Path(args.inputs).resolve()
runtime = Path(args.runtime).resolve()
out = Path(args.out).resolve()
out.mkdir(exist_ok=False)
literal_python = str(Path(__file__).resolve().parents[3] / 'backend/.venv/bin/python')
node = '/Users/ethanlee/.local/share/mise/installs/node/lts/bin/node'
assert hashlib.sha256(source.read_bytes()).hexdigest() == args.inputs_sha
index = json.loads(source.read_text())
assert sorted(r['owner'] for r in index['cases']) == sorted(['CS-CR-04','CS-CR-09','CS-GI-09','CS-GA-10','CS-HGI-09','CS-EG-09','CS-GO-04','CS-GO-06','CS-GO-11','CS-NGO-04','CS-NGO-08'])
seal = json.loads((runtime.parent/'SourceSeal.json').read_text())
assert all(hashlib.sha256((runtime/p).read_bytes()).hexdigest()==v['sha256'] for p,v in seal['files'].items())
env = os.environ.copy()
env.update(PYTHONPATH=str(runtime/'backend'), PYTHONDONTWRITEBYTECODE='1')
results = []
for row in index['cases']:
    path = source.parent/row['file']
    assert hashlib.sha256(path.read_bytes()).hexdigest() == row['sha256']
    data = json.loads(path.read_text())
    cases = [(f['name'], {'envelope':f['request']['envelope'],'context':f['request']['context']}, True) for f in data['frames'] if f['name'] in ['start','half','blocked','paused','resumed','end-before','end-after']]
    if row['owner'] in ['CS-CR-04','CS-GO-06','CS-HGI-09']:
        for fault in ['no-input','stale-version','missing-retained','out-of-range','early-boundary','extra-field']:
            raw = copy.deepcopy(next(f['request'] for f in data['frames'] if f['name']=='end-after' if fault in ['missing-retained','early-boundary']) if fault in ['missing-retained','early-boundary'] else next(f['request'] for f in data['frames'] if f['name']=='half'))
            raw = {'envelope':raw['envelope'],'context':raw['context']}
            match fault:
                case 'no-input': raw['context']['snapshot']['batch_io'] = [io for io in raw['context']['snapshot']['batch_io'] if io['batch_id'] != 'synthetic:T21:postcut-winding:'+row['owner']+':batch']
                case 'stale-version': raw['envelope']['material']['material_version_id'] += ':stale'
                case 'missing-retained': raw['context']['snapshot']['attachments'] = [a for a in raw['context']['snapshot']['attachments'] if a['id'] != raw['envelope']['boundary']['released_attachment_id']]
                case 'out-of-range': next(c for c in raw['envelope']['channels'] if c['function_id']==data['winding_function'])['end_value'] += .001
                case 'early-boundary': raw['envelope']['boundary']['at_ms'] -= 1
                case 'extra-field': raw['envelope']['extra_untrusted'] = True
                case _: raise AssertionError(fault)
            raw['context']['authorizations'] = [copy.deepcopy(raw['envelope'])]
            cases.append(('negative-'+fault, raw, False))
    for name,request,accepted in cases:
        assert hashlib.sha256(source.read_bytes()).hexdigest() == args.inputs_sha
        request_path = out/(row['owner']+'-'+name+'.json')
        request_path.write_text(json.dumps(request,separators=(',',':'))+'\n')
        observed = []
        for language,command in [('python',[literal_python,'-m','app.operations.motion_cli']),('typescript',[node,str(Path(args.node_cli).resolve()),str(request_path)])]:
            completed = subprocess.run(command,cwd=runtime,env=env,input=request_path.read_bytes() if language=='python' else None,capture_output=True,timeout=40)
            prefix = out/(row['owner']+'-'+name+'.'+language)
            prefix.with_suffix(prefix.suffix+'.stdout.log').write_bytes(completed.stdout)
            prefix.with_suffix(prefix.suffix+'.stderr.log').write_bytes(completed.stderr)
            observed.append({'language':language,'argv':command,'exit':completed.returncode,'accepted':completed.returncode==0,'output':json.loads(completed.stdout) if completed.returncode==0 else None})
        passed = all(r['accepted']==accepted for r in observed)
        results.append({'owner':row['owner'],'name':name,'expected_accepted':accepted,'pass':passed,'request_sha256':hashlib.sha256(request_path.read_bytes()).hexdigest(),'results':observed})
        (out/'partial.json').write_text(json.dumps(results,indent=2)+'\n')
assert all(hashlib.sha256((runtime/p).read_bytes()).hexdigest()==v['sha256'] for p,v in seal['files'].items())
(out/'result.json').write_text(json.dumps({'at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'interpreter':literal_python,'source_unchanged':True,'synthetic_new_phase_history_not_production_writer':True,'results':results},indent=2)+'\n')
print(json.dumps({'cases':len(results),'failed':[(r['owner'],r['name']) for r in results if not r['pass']]}))
sys.exit(any(not r['pass'] for r in results))
