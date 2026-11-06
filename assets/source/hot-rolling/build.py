"""Rebuild original hot-rolling miniatures using the pinned Blender executable.

Invoked by Blender --background --factory-startup --python-exit-code 1
--python assets/source/hot-rolling/build.py -- --out NEW_ROOT [--only KEY] [--render].
Writes a family fragment only. The shared dispatcher owns top-level merging.
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
from details import base,contacts,markers
from mills import rolling,coiler,laying_head
from thermal import furnace,cooling,cooling_bed
from cutters import cutter
from manifest import artifact,asset_row,complete_asset,sha,write_json
from render import render
from transmission import author_transmissions


def shape(model, spec):
    model.followers=[]
    model.feed_spec=spec.get('internal_feed')
    model.roller_centers=spec.get('roller_centers_x_m')
    model.door_x=spec.get('door_assembly_x_m',-3.7)
    kind=spec['kind']
    wire=spec['stage']=='wire'
    match kind:
        case 'furnace': furnace(model,wire=wire,secondary=spec['key']=='CS-WIRE-06')
        case 'heat_treatment': furnace(model,treatment=True)
        case 'roughing'|'finishing_mill'|'bloom_mill'|'wire_mill'|'leveler': rolling(model,kind,wire=wire,plate=spec['stage']=='plate')
        case 'cooling': cooling(model,plate=spec['stage']=='plate')
        case 'cooling_bed': cooling_bed(model)
        case 'coiler': coiler(model)
        case 'laying_head': laying_head(model)
        case 'shear': cutter(model,gas=spec['stage']=='plate')
        case other: raise RuntimeError('Unregistered model kind: '+other)
    base(model)
    sockets=contacts(model,spec['forms'])
    markers(model)
    author_transmissions(model)
    return sockets


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',required=True)
    parser.add_argument('--only')
    parser.add_argument('--render',action='store_true')
    args=parser.parse_args(sys.argv[sys.argv.index('--')+1:])
    out=Path(args.out).resolve()
    target=out/'public/assets/steelworks/hot-rolling'
    source_target=out/'assets/source/hot-rolling'
    if target.exists() and any(target.iterdir()):
        raise RuntimeError('Family output must be new or empty; refusing overwrite')
    tool=json.loads((REPO/'assets/toolchain.json').read_text())
    if tuple(bpy.app.version)!=(4,5,15) or sha(bpy.app.binary_path)!=tool['executable_sha256']:
        raise RuntimeError('Pinned Blender executable/version mismatch')
    recipe=json.loads((SOURCE/'recipe.json').read_text())
    requirements=json.loads((REPO/'shared/asset-requirements.json').read_text())
    coverage=json.loads((REPO/'shared/coverage-registry.json').read_text())
    target.mkdir(parents=True,exist_ok=True)
    source_target.mkdir(parents=True,exist_ok=True)
    (out/'assets').mkdir(parents=True,exist_ok=True)
    shutil.copyfile(REPO/'assets/toolchain.json',out/'assets/toolchain.json')
    for path in SOURCE.iterdir():
        if path.suffix in {'.py','.mjs','.json','.txt','.md'} and path.name not in {'inventory.json','mechanics.json'}:
            shutil.copyfile(path,source_target/path.name)
    result={'schema_version':1,'purpose':'production','assets':[]}
    mechanics=[]
    for spec in recipe['models']:
        if args.only and spec['key']!=args.only:
            continue
        binding=next(b for b in requirements['existing_bindings'] if b['variant']==spec['variant'])
        asset=asset_row(binding,coverage)
        for level in range(3):
            model=Model(spec['key'],level)
            sockets=shape(model,spec)
            if level==0:
                complete_asset(asset,model,sockets,out)
                mechanics.append({'variant':spec['variant'],'canonical_parts':[s.name for s in model.motions],'followers':model.followers,'support_height_m':1.32,'dimension_basis':'original synthetic miniature; functional concept only'})
            relative=f'public/assets/steelworks/hot-rolling/{spec["key"]}-lod{level}.glb'
            bpy.ops.object.select_all(action='DESELECT')
            for obj in model.objects.values():
                obj.select_set(True)
            bpy.ops.export_scene.gltf(filepath=str(out/relative),export_format='GLB',use_selection=True,export_yup=True,export_apply=True,export_extras=True,export_animations=True,export_animation_mode='ACTIONS',export_force_sampling=True,export_frame_range=True,export_anim_slide_to_zero=True,export_frame_step=1,export_cameras=False,export_lights=False)
            asset['lods'].append({'level':level,'artifact':artifact(out,relative),'semantic_geometry_sha256':None,'nodes':copy.deepcopy(model.nodes),'socket_ids':[s['id'] for s in sockets],'part_ids':[p['id'] for p in asset['moving_parts']+asset['fixed_parts']],'material_ids':[m['id'] for m in asset['materials']]})
            if args.render and level==0:
                render(model,target/(spec['key']+'-proof.png'))
        result['assets'].append(asset)
        print('HOT_ROLLING_BUILT '+spec['key'],flush=True)
    write_json(target/'manifest.json',result)
    write_json(source_target/'mechanics.json',{'schema_version':1,'authority':'T61 mechanical_follower: original synthetic rotation ratio, independently pivoted authored tracks; no additional server function channels.','models':mechanics})
    sources=[artifact(out,'assets/source/hot-rolling/'+p.name) for p in SOURCE.iterdir() if p.suffix in {'.py','.mjs','.json','.txt','.md'} and p.name not in {'inventory.json','mechanics.json'}]
    write_json(source_target/'inventory.json',{'external_asset_count':0,'license':artifact(out,'assets/source/hot-rolling/LICENSE.txt'),'inputs':sources,'authored_assets':[a['source']['artifact'] for a in result['assets']],'textures':[],'tool_license':{'path':tool['tool_license_path'],'sha256':tool['tool_license_sha256']},'limits':['Explicit synthetic family fixtures; no live business scheduler integration asserted.']})
    print('STEELFLOW_HOT_ROLLING_BUILD_COMPLETE '+str(out),flush=True)


if __name__=='__main__':
    main()
