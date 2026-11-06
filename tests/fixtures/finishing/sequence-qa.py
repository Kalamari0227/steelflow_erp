"""Exact private T65 source + actual asset-root preflight and public CLI parity."""
from pathlib import Path
import argparse
import hashlib
import json
import os
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[3]
parser=argparse.ArgumentParser(description=__doc__)
for name in ['inputs','inputs-sha','root','manifest-sha','runtime','out','cli']:parser.add_argument('--'+name,required=True)
args=parser.parse_args();source=Path(args.inputs).resolve();runtime=Path(args.runtime).resolve();assetroot=Path(args.root).resolve();out=Path(args.out).resolve();assert not out.exists();out.mkdir(parents=True)
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
assert sha(source)==args.inputs_sha
manifest=assetroot/'public/assets/steelworks/finishing/manifest.json';assert sha(manifest)==args.manifest_sha
assets=json.loads(manifest.read_text())['assets'];assert sorted(a['placement_ids'][0][10:] for a in assets)==['CS-CR-05','CS-GO-05','CS-GO-08','CS-NGO-05']
for a in assets:
    assert a['family']=='finishing' and len(a['lods'])==3
    for lod in a['lods']:assert sha(assetroot/lod['artifact']['path'])==lod['artifact']['sha256']
sealpath=runtime.parent/'T65-SourceSeal.json';assert sha(sealpath)=='47a575446d6f302428fccfc71bdbe427a0bd43e2c3f0a556e049352bc317edc1';seal=json.loads(sealpath.read_text());assert all(sha(runtime/p)==h for p,h in seal['candidate_sha256'].items())
python=str(ROOT/'backend/.venv/bin/python')
env=os.environ.copy();env.update(PYTHONPATH=str(runtime/'backend'),PYTHONDONTWRITEBYTECODE='1')
pre=subprocess.run([python,'-c','import sys,pydantic,os,json;print(json.dumps({"sys_executable":sys.executable,"prefix":sys.prefix,"pydantic":pydantic.__version__,"cwd":os.getcwd()}))'],cwd=runtime,env=env,capture_output=True,check=True)
(out/'preflight.json').write_text(json.dumps({'python_probe':json.loads(pre.stdout),'interpreter_argv':python,'input_root':str(assetroot),'manifest_sha256':args.manifest_sha,'inputs_sha256':args.inputs_sha,'runtime':str(runtime),'T65_source_seal_sha256':sha(sealpath),'cli_sha256':sha(args.cli)},indent=2)+'\n')
results=[]
for case in json.loads(source.read_text())['cases']:
    path=out/(case['name']+'.json');path.write_text(json.dumps(case['request'],indent=2)+'\n');row={'name':case['name'],'input_sha256':sha(path),'results':[]}
    for language,cmd in [('python',[python,'-m','app.operations.motion_cli']),('typescript',['/Users/ethanlee/.local/share/mise/installs/node/lts/bin/node',str(Path(args.cli).resolve()),str(path)])]:
        r=subprocess.run(cmd,cwd=runtime,env=env,input=path.read_bytes() if language=='python' else None,capture_output=True,timeout=25)
        (out/(case['name']+'.'+language+'.stdout.log')).write_bytes(r.stdout);(out/(case['name']+'.'+language+'.stderr.log')).write_bytes(r.stderr)
        row['results'].append({'language':language,'argv':cmd,'exit_code':r.returncode,'response':json.loads(r.stdout) if r.stdout else None})
    results.append(row);(out/'partial.json').write_text(json.dumps(results,indent=2)+'\n')
assert sha(source)==args.inputs_sha and sha(manifest)==args.manifest_sha and all(sha(runtime/p)==h for p,h in seal['candidate_sha256'].items())
failed=[r for r in results if any(v['exit_code'] for v in r['results'])]
(out/'result.json').write_text(json.dumps({'status':'FAIL' if failed else 'PASS_TYPED_SEQUENCE_ONLY_NOT_PHYSICAL_COMPLETION','source_unchanged':True,'all_children_exited':True,'results':results},indent=2)+'\n')
print(json.dumps({'cases':len(results),'failed':[{'name':r['name'],'errors':[v['response'].get('error') if v['response'] else None for v in r['results']]} for r in failed]}));sys.exit(bool(failed))
