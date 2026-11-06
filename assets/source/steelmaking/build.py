"""Rebuild editable steelmaking or four stainless EAF/AOD originals with pinned Blender.

Blender --background --factory-startup --python-exit-code 1 --python
assets/source/steelmaking/build.py -- --out NEW_ROOT [--only KEY] [--render].
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
sys.path.insert(0,str(SOURCE))
from geometry import Model
from details import foundation,contacts
from upstream import charge,blast
from vessels import converter,eaf,ladle_furnace
from casting import caster,cutter
from manifest import artifact,asset_row,complete_asset,sha,write_json
from transmission import author_transmissions
from render import render


def shape(model,spec):
    """Dispatch only registered machine kinds; independent geometry stays family-local."""
    model.followers=[]
    match spec['kind']:
        case 'charge': contact=charge(model)
        case 'blast_furnace': contact=blast(model)
        case 'bof'|'aod': contact=converter(model,spec['kind'],spec['key']=='STS-PLATE-03')
        case 'ladle_furnace': contact=ladle_furnace(model)
        case 'eaf': contact=eaf(model,spec['key']=='STS-PLATE-02')
        case 'caster': contact=caster(model,spec['forms'][1])
        case 'shear': contact=cutter(model,spec['forms'][0])
        case other: raise RuntimeError('Unregistered steelmaking kind: '+other)
    if not model.roofs:model.interior=[]
    foundation(model)
    sockets=contacts(model,contact)
    author_transmissions(model)
    return sockets


def main(family='steelmaking'):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',required=True)
    parser.add_argument('--only')
    parser.add_argument('--render',action='store_true')
    args=parser.parse_args(sys.argv[sys.argv.index('--')+1:])
    out=Path(args.out).resolve()
    if out.exists() and any(out.iterdir()):raise RuntimeError('Output must be new or empty; refusing overwrite')
    tool=json.loads((REPO/'assets/toolchain.json').read_text())
    if tuple(bpy.app.version)!=(4,5,15) or sha(bpy.app.binary_path)!=tool['executable_sha256']:raise RuntimeError('Pinned Blender executable/version mismatch')
    recipe=json.loads((REPO/'assets/source'/family/'recipe.json').read_text())
    requirements=json.loads((REPO/'shared/asset-requirements.json').read_text())
    coverage=json.loads((REPO/'shared/coverage-registry.json').read_text())
    target=out/'public/assets/steelworks'/family
    source_target=out/'assets/source'/family
    target.mkdir(parents=True);source_target.mkdir(parents=True)
    shutil.copyfile(REPO/'assets/toolchain.json',out/'assets/toolchain.json')
    sources=[]
    for source_family in sorted({'steelmaking',family}):
        destination=out/'assets/source'/source_family;destination.mkdir(parents=True,exist_ok=True)
        for path in (REPO/'assets/source'/source_family).iterdir():
            if path.suffix in {'.py','.mjs','.json','.txt','.md'} and path.name not in {'inventory.json','mechanics.json'}:
                shutil.copyfile(path,destination/path.name);sources.append(artifact(out,f'assets/source/{source_family}/{path.name}'))
    motion=json.loads((REPO/'shared/motion-recipes.json').read_text())
    contract_target=source_target/'contracts';contract_target.mkdir()
    selected_variants={s['variant'] for s in recipe['models']}
    selected_bindings=[b for b in requirements['existing_bindings'] if b['variant'] in selected_variants]
    selected_policies={b['policy_group_id'] for b in selected_bindings}
    snapshot={'schema_version':1,'requirements_source_sha256':sha(REPO/'shared/asset-requirements.json'),'motion_source_sha256':sha(REPO/'shared/motion-recipes.json'),'bindings':selected_bindings,'policies':[p for p in requirements['policies'] if p['id'] in selected_policies],'motion_recipes':[r for r in motion['recipes'] if r['id'] in {s['motion_recipe'] for s in recipe['models']}]}
    write_json(contract_target/'source-contracts.json',snapshot)
    sources.append(artifact(out,f'assets/source/{family}/contracts/source-contracts.json'))
    result={'schema_version':1,'purpose':'production','assets':[]};mechanics=[]
    selected=[s for s in recipe['models'] if not args.only or s['key']==args.only]
    if not selected:raise RuntimeError('Unknown --only variant')
    for spec in selected:
        binding=next(b for b in requirements['existing_bindings'] if b['variant']==spec['variant'])
        asset=asset_row(binding,coverage,family)
        for level in range(3):
            model=Model(spec['key'],level);sockets=shape(model,spec)
            if level==0:
                complete_asset(asset,model,sockets,out)
                mechanics.append({'variant':spec['variant'],'canonical_parts':[s.name for s in model.motions],'followers':model.followers,'contacts':sockets,'dimension_basis':'Original synthetic miniature; public functional concept only.'})
            relative=f'public/assets/steelworks/{family}/{spec["key"]}-lod{level}.glb'
            bpy.ops.object.select_all(action='DESELECT')
            for obj in model.objects.values():obj.select_set(True)
            bpy.ops.export_scene.gltf(filepath=str(out/relative),export_format='GLB',use_selection=True,export_yup=True,export_apply=True,export_extras=True,export_animations=True,export_animation_mode='ACTIONS',export_force_sampling=True,export_frame_range=True,export_anim_slide_to_zero=True,export_frame_step=1,export_cameras=False,export_lights=False)
            asset['lods'].append({'level':level,'artifact':artifact(out,relative),'semantic_geometry_sha256':None,'nodes':copy.deepcopy(model.nodes),'socket_ids':[s['id'] for s in sockets],'part_ids':[p['id'] for p in asset['moving_parts']+asset['fixed_parts']],'material_ids':[m['id'] for m in asset['materials']]})
            if args.render and level==0:render(model,target/(spec['key']+'-proof.png'))
        result['assets'].append(asset);print('STEELMAKING_BUILT '+spec['key'],flush=True)
    write_json(target/'manifest.json',result)
    write_json(source_target/'mechanics.json',{'schema_version':1,'models':mechanics})
    inventory={'external_asset_count':0,'license':artifact(out,f'assets/source/{family}/LICENSE.txt'),'inputs':sources,'authored_assets':[a['source']['artifact'] for a in result['assets']],'textures':[],'tool_license':{'path':tool['tool_license_path'],'sha256':tool['tool_license_sha256']},'limitations':recipe['runtime_limit']}
    write_json(source_target/'inventory.json',inventory)
    # Isolated compatibility wrapper for the existing T12 stamp/verify oracle only.
    write_json(out/'public/assets/steelworks/manifest.json',result)
    write_json(out/'assets/source/recipe.json',recipe)
    write_json(out/'assets/source/inventory.json',inventory)
    print('STEELFLOW_STEELMAKING_BUILD_COMPLETE '+str(out),flush=True)


if __name__=='__main__':main()
