"""Reproducible transport build, refusing dirty inputs or an occupied output root."""
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
from road import truck,carrier,forklift
from handling import gantry,cradle
from manifest import artifact,complete,inventory,row,sha,write_json
from rail import rail_vehicle
from ships import ship
from bulk import bulk_machine,harbour_crane
from transmission import author_transmissions


def shape(model: Model,spec) -> None:
    match spec['key']:
        case 'truck-flatbed':truck(model)
        case 'truck-dump':truck(model,True)
        case 'crane-yard':gantry(model)
        case 'crane-overhead':gantry(model,True)
        case 'receiving-cradle':cradle(model)
        case 'slab-carrier'|'coil-carrier':carrier(model,spec['kind'])
        case 'forklift':forklift(model)
        case 'torpedo'|'ladle-car'|'locomotive'|'railcar'|'railcar-coil'|'railcar-bulk':
            rail_vehicle(model,spec['kind'])
            if spec['key']=='railcar-coil':
                for x in (-6.,0.,6.):
                    for z in (-.7,.7):model.box('coil_chock_'+str(x)+'_'+str(z),(2.,.55,.25),(x,2.4,z),finish='safety')
            if spec['key']=='railcar-bulk':
                for z in (-1.8,1.8):model.box('gondola_side_'+str(z),(18.5,1.7,.16),(0.,3.0,z),finish='safety')
                for x in (-9.2,9.2):model.box('gondola_end_'+str(x),(.16,1.7,3.6),(x,3.0,0.),finish='safety')
        case 'ship-product'|'ship-existing':ship(model)
        case 'ship-bulk':ship(model,True)
        case 'crane-port':harbour_crane(model)
        case 'unloader'|'stacker'|'reclaimer'|'conveyor':bulk_machine(model,spec['kind'])
        case unknown:raise RuntimeError('Asset authoring not yet implemented: '+unknown)
    author_transmissions(model)
    model.markers()


def main() -> None:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',required=True);parser.add_argument('--only');parser.add_argument('--render',action='store_true');parser.add_argument('--contracts-root')
    args=parser.parse_args(sys.argv[sys.argv.index('--')+1:])
    out=Path(args.out).absolute()
    if out.exists() and any(out.iterdir()):raise RuntimeError('Refusing occupied output root')
    tool=json.loads((REPO/'assets/toolchain.json').read_text())
    if tuple(bpy.app.version)!=(4,5,15) or sha(Path(bpy.app.binary_path))!=tool['executable_sha256']:raise RuntimeError('Pinned Blender mismatch')
    recipe=json.loads((SOURCE/'recipe.json').read_text())
    selected=set(args.only.split(',')) if args.only else {s['key'] for s in recipe['models']}
    if not selected or not selected.issubset({s['key'] for s in recipe['models']}):raise RuntimeError('Unknown model selection')
    target=out/'public/assets/steelworks/transport';source=out/'assets/source/transport'
    target.mkdir(parents=True);source.mkdir(parents=True)
    shutil.copyfile(REPO/'assets/toolchain.json',out/'assets/toolchain.json')
    inputs=[]
    for path in sorted(SOURCE.rglob('*')):
        if path.is_file() and path.suffix in {'.py','.json','.md','.txt','.mjs'}:
            relative='assets/source/transport/'+str(path.relative_to(SOURCE));destination=out/relative;destination.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(path,destination);inputs.append(artifact(out,relative))
    contract_root=Path(args.contracts_root).absolute() if args.contracts_root else REPO
    if contract_root!=REPO and not contract_root.is_relative_to(REPO/'.omo/evidence/uniform-fidelity/uf-20261030-resume06/task-28/implementation'):raise RuntimeError('Private contract root must be owned T28 evidence')
    for name in ('asset-requirements.json','coverage-registry.json','asset-manifest.schema.json'):
        destination=source/'contracts'/name;destination.parent.mkdir(exist_ok=True);shutil.copyfile(contract_root/'shared'/name,destination)
        inputs.append(artifact(out,str(destination.relative_to(out))))
    requirements=json.loads((contract_root/'shared/asset-requirements.json').read_text());coverage=json.loads((contract_root/'shared/coverage-registry.json').read_text())
    result={'schema_version':1,'purpose':'production','assets':[]};registered={'schema_version':1,'purpose':'production','assets':[]};solids=[]
    for spec in recipe['models']:
        if spec['key'] not in selected:continue
        asset=row(spec,requirements,coverage)
        for level in range(3):
            model=Model(spec['key'],level);shape(model,spec)
            if level==0:complete(asset,model,out)
            relative=f'public/assets/steelworks/transport/{spec["key"]}-lod{level}.glb'
            bpy.ops.object.select_all(action='DESELECT')
            for obj in model.objects.values():obj.select_set(True)
            bpy.ops.export_scene.gltf(filepath=str(out/relative),export_format='GLB',use_selection=True,export_yup=True,export_apply=True,export_extras=True,export_animations=True,export_animation_mode='ACTIONS',export_force_sampling=True,export_frame_range=True,export_anim_slide_to_zero=True,export_frame_step=1,export_cameras=False,export_lights=False)
            asset['lods'].append({'level':level,'artifact':artifact(out,relative),'semantic_geometry_sha256':None,'nodes':copy.deepcopy(model.nodes),'socket_ids':[s['id'] for s in model.sockets],'part_ids':[p['id'] for p in asset['moving_parts']+asset['fixed_parts']],'material_ids':[m['id'] for m in asset['materials']]})
            solid=inventory(model,asset['id']);solid['glb_sha256']=sha(out/relative);solids.append(solid)
            if args.render and level==0:
                from render import render
                render(model,target/(model.key+'-proof.png'))
        result['assets'].append(asset)
        if any(b['variant']==spec['variant'] and b['kind']==spec['kind'] for b in requirements['planned_bindings']+requirements['existing_bindings']):registered['assets'].append(asset)
        print('TRANSPORT_BUILT '+spec['key'],flush=True)
    write_json(target/'manifest-candidate.json',result)
    write_json(target/'manifest.json',registered)
    write_json(source/'solid-inventory.json',{'format':'transport-source-solids-v1','classification_approval':'PENDING_INDEPENDENT_REVIEW','assets':solids})
    write_json(source/'inventory.json',{'external_asset_count':0,'license':artifact(out,'assets/source/transport/LICENSE.txt'),'inputs':inputs,'authored_assets':[a['source']['artifact'] for a in result['assets']],'textures':[],'tool_license':{'path':tool['tool_license_path'],'sha256':tool['tool_license_sha256']},'limits':['Source geometry candidate; unregistered variants and material support datum need Astra admission. Full T28 not complete.']})
    print('STEELFLOW_TRANSPORT_BUILD_COMPLETE '+str(out),flush=True)


if __name__=='__main__':main()
