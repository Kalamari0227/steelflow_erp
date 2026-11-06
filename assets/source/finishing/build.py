"""Build the pinned finishing family into a new, explicitly owned root.

Blender --background --factory-startup --python-exit-code 1 --python
assets/source/finishing/build.py -- --out ROOT --inputs SEAL --inputs-sha256 SHA
[--only comma,separated,owner,IDs] [--render].
"""
from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path
import shutil
import sys

import bpy

SOURCE=Path(__file__).resolve().parent
REPO=SOURCE.parents[2]
sys.dont_write_bytecode=True
sys.path.insert(0,str(SOURCE))
from geometry import Model
from details import foundation,contacts,markers,roller,linear_transport
from uncoiling import coil_machine
from rolling import mill,leveler
from strip_treatment import pickling,cleaning,oiling
from thermal import continuous,bell
from coating import galvanizing,coating,electroplating
from electrical import domain_refinement
from subassemblies import supplements
from transmission import author_transmissions
from line_feeding import line_feeder
from manifest import artifact,asset_row,complete_asset,sha,write_json
from render import render


def shape(model,spec):
    model.followers=[]
    model.states=spec['states']
    model.datum=spec['datum_m']
    model.forming=None
    model.drive_radius=.2
    model.line_spec=spec.get('source_internal_sequence')
    if model.line_spec:model.node('line_feed_lift')
    model.length=16 if any('mandrel' in f for f in spec['moving'][1:]) else 13 if any('looper' in f for f in spec['moving']) else 11 if len(spec['moving'])>2 else 8
    model.width=3.0
    match spec['kind']:
        case 'uncoiler'|'coiler':coil_machine(model,spec)
        case 'cold_mill'|'temper':mill(model,spec)
        case 'leveler':leveler(model,spec)
        case 'pickling':pickling(model,spec)
        case 'electrocleaning':cleaning(model,spec)
        case 'oiling':oiling(model,spec)
        case 'annealing'|'alloying'|'decarburizing':continuous(model,spec)
        case 'heat_treatment':bell(model,spec)
        case 'galvanizing':galvanizing(model,spec)
        case 'coating':coating(model,spec)
        case 'electroplating':electroplating(model,spec)
        case 'inspection':domain_refinement(model,spec)
        case unknown:raise RuntimeError('Unregistered finishing kind: '+unknown)
    supplements(model,spec)
    if model.line_spec:line_feeder(model,spec)
    model.entry_x,model.exit_x=-model.length/2+.4,model.length/2-.4
    if spec['kind']=='uncoiler':model.entry_x,model.exit_x=model.exit_x,model.entry_x
    for role,x in [('entry',model.entry_x),('exit',model.exit_x)]:
        if not any(abs(r['center_m'][0]-x)<1e-9 and abs(r['center_m'][1]+r['radius_m']-model.datum)<1e-9 and r['parent']=='root' for r in model.roller_specs):
            roller(model,role+'_socket_roll',x,model.datum-.16,.16)
    linear_transport(model,spec)
    foundation(model);markers(model)
    author_transmissions(model)
    expected=set(spec['moving']);actual={m.name for m in model.motions}
    if expected!=actual or len(actual)!=len(model.motions):
        raise RuntimeError(f'Exact independent canonical functions mismatch {spec["key"]}: expected {expected}, actual {actual}')
    for state in model.states:
        if state not in model.objects:raise RuntimeError('Missing actual state assembly: '+state)
    return contacts(model,spec)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',required=True)
    parser.add_argument('--inputs',required=True)
    parser.add_argument('--inputs-sha256',required=True)
    parser.add_argument('--only')
    parser.add_argument('--render',action='store_true')
    args=parser.parse_args(sys.argv[sys.argv.index('--')+1:])
    out=Path(args.out).resolve()
    if out.exists() and any(out.iterdir()):raise RuntimeError('Output root must be new or empty; refusing overwrite')
    seal=Path(args.inputs).resolve()
    if sha(seal)!=args.inputs_sha256:raise RuntimeError('Independent input seal SHA mismatch')
    pinned=json.loads(seal.read_text())
    if pinned['family']!='finishing' or pinned['owner_count']!=58 or pinned['lod_count']!=174:raise RuntimeError('Wrong independent family input seal')
    authority=json.loads((SOURCE/'contracts/source-contracts.json').read_text())
    expected_owners=sorted(row['owner_id'] for row in authority['inventory']['rows'])
    if len(expected_owners)!=58 or len(set(expected_owners))!=58 or pinned.get('owner_ids')!=expected_owners:raise RuntimeError('Input seal must retain the exact independent 58-owner universe')
    expected_inputs={str(p.relative_to(REPO)) for p in SOURCE.rglob('*') if p.is_file() and p.suffix in {'.py','.mjs','.json','.txt','.md'} and p.name not in {'inventory.json','mechanics.json'}}
    expected_inputs.update({'scripts/assets/build.py','assets/toolchain.json','shared/asset-requirements.json','shared/coverage-registry.json'})
    paths=[row['path'] for row in pinned['inputs']]
    if len(paths)!=len(set(paths)) or set(paths)!=expected_inputs:raise RuntimeError('Input seal must cover every exact current required source path once')
    for row in pinned['inputs']:
        if sha(REPO/row['path'])!=row['sha256']:raise RuntimeError('Dirty or stale build input: '+row['path'])
    tool=json.loads((REPO/'assets/toolchain.json').read_text())
    if tuple(bpy.app.version)!=(4,5,15) or sha(bpy.app.binary_path)!=tool['executable_sha256']:raise RuntimeError('Pinned Blender executable/version mismatch')
    recipe=json.loads((SOURCE/'recipe.json').read_text())
    if sorted(row['key'] for row in recipe['models'])!=expected_owners:raise RuntimeError('Recipe owner universe differs from the sealed independent preparation')
    for row in recipe['models']:
        registered=next(r for r in authority['inventory']['rows'] if r['owner_id']==row['key'])
        if row['variant']!=registered['variant'] or row['kind']!=registered['kind']:raise RuntimeError('Recipe variant/kind differs from independent preparation: '+row['key'])
    requirements=json.loads((REPO/'shared/asset-requirements.json').read_text())
    coverage=json.loads((REPO/'shared/coverage-registry.json').read_text())
    selected=set(args.only.split(',')) if args.only else {s['key'] for s in recipe['models']}
    if not selected or not selected.issubset({s['key'] for s in recipe['models']}):raise RuntimeError('Unknown selected owner')
    target=out/'public/assets/steelworks/finishing';source_target=out/'assets/source/finishing'
    target.mkdir(parents=True);source_target.mkdir(parents=True)
    shutil.copyfile(REPO/'assets/toolchain.json',out/'assets/toolchain.json')
    for path in SOURCE.rglob('*'):
        if path.is_file() and path.suffix in {'.py','.mjs','.json','.txt','.md'} and path.name not in {'inventory.json','mechanics.json'}:
            destination=source_target/path.relative_to(SOURCE)
            destination.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(path,destination)
    shutil.copyfile(seal,source_target/'input-seal.json')
    contracts=source_target/'contracts'
    contracts.mkdir(exist_ok=True)
    for name in ['asset-requirements.json','coverage-registry.json']:
        shutil.copyfile(REPO/'shared'/name,contracts/name)
    result={'schema_version':1,'purpose':'production','assets':[]};mechanics=[]
    for spec in recipe['models']:
        if spec['key'] not in selected:continue
        binding=next(b for b in requirements['existing_bindings'] if b['variant']==spec['variant'])
        asset=asset_row(binding,coverage)
        for subassembly in spec['supplements']:
            requirement=next(r for r in coverage['source_requirements'] if r['id']==subassembly['requirement_id'])
            asset['requirement_ids']=sorted(set(asset['requirement_ids']+[requirement['id']]))
            asset['qa_row_ids']=sorted(set(asset['qa_row_ids']+requirement['qa_row_ids']))
            public=next(s for s in coverage['sources'] if s['id'] in requirement['source_ids'])
            if not any(r['id']==requirement['id'] for r in asset['source_refs']):
                asset['source_refs'].append({'id':requirement['id'],'uri':public['url'],'note':'Named mechanism from the sealed 29/52 host map. Geometry, axes and dimensions are original synthetic design; completion requires independent actual evidence.'})
        if spec['motion_policy_id'] is not None:asset['motion_policy_id']=spec['motion_policy_id']
        for level in range(3):
            model=Model(spec['key'],level);sockets=shape(model,spec)
            if level==0:
                complete_asset(asset,model,sockets,out)
                mechanics.append({'variant':spec['variant'],'owner_id':spec['key'],'canonical_parts':[s.name for s in model.motions],'followers':model.followers,'work_datum_m':spec['datum_m'],'forming':model.forming,'input_form':spec['input_form'],'output_form':spec['output_form'],'subassemblies':spec['supplements'],'dimension_basis':'original synthetic miniature; functional concept only'})
            relative=f'public/assets/steelworks/finishing/{spec["key"]}-lod{level}.glb'
            bpy.ops.object.select_all(action='DESELECT')
            for obj in model.objects.values():obj.select_set(True)
            bpy.ops.export_scene.gltf(filepath=str(out/relative),export_format='GLB',use_selection=True,export_yup=True,export_apply=True,export_extras=True,export_animations=True,export_animation_mode='ACTIONS',export_force_sampling=True,export_frame_range=True,export_anim_slide_to_zero=True,export_frame_step=1,export_cameras=False,export_lights=False)
            asset['lods'].append({'level':level,'artifact':artifact(out,relative),'semantic_geometry_sha256':None,'nodes':copy.deepcopy(model.nodes),'socket_ids':[s['id'] for s in sockets],'part_ids':[p['id'] for p in asset['moving_parts']+asset['fixed_parts']],'material_ids':[m['id'] for m in asset['materials']]})
            if args.render and level==0:render(model,target/(spec['key']+'-proof.png'))
        result['assets'].append(asset)
        print('FINISHING_BUILT '+spec['key'],flush=True)
    write_json(target/'manifest.json',result)
    mechanics_value={'schema_version':1,'authority':'Synthetic exact canonical functions and actual independently pivoted followers; live business integration not asserted.','models':mechanics}
    write_json(source_target/'mechanics.json',mechanics_value)
    write_json(target/'mechanics.json',mechanics_value)
    sources=[artifact(out,str(p.relative_to(out))) for p in source_target.rglob('*') if p.is_file() and p.suffix in {'.py','.mjs','.json','.txt','.md'} and p.name not in {'inventory.json','mechanics.json'}]
    write_json(source_target/'inventory.json',{'external_asset_count':0,'license':artifact(out,'assets/source/finishing/LICENSE.txt'),'inputs':sources,'authored_assets':[a['source']['artifact'] for a in result['assets']],'textures':[],'tool_license':{'path':tool['tool_license_path'],'sha256':tool['tool_license_sha256']},'limits':['Explicit synthetic family fixture; no live business scheduler integration asserted.']})
    print('STEELFLOW_FINISHING_BUILD_COMPLETE '+str(out),flush=True)


if __name__=='__main__':main()
