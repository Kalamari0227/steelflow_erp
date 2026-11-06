"""Reopen actual sealed editable sources and re-export their true LOD0 geometry."""
from pathlib import Path
import argparse
import hashlib
import json
import sys
import bpy

def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--root',required=True);parser.add_argument('--expected-sha',required=True);parser.add_argument('--out',required=True)
args=parser.parse_args(sys.argv[sys.argv.index('--')+1:]);root=Path(args.root).resolve();out=Path(args.out).resolve();assert not out.exists();out.mkdir(parents=True)
manifest=root/'public/assets/steelworks/finishing/manifest.json';assert digest(manifest)==args.expected_sha
raw=json.loads(manifest.read_text());seal=json.loads((root/'assets/source/finishing/input-seal.json').read_text());assert len(raw['assets'])==58 and seal['owner_count']==58 and sorted(a['placement_ids'][0][10:] for a in raw['assets'])==seal['owner_ids']
tool=json.loads((root/'assets/toolchain.json').read_text());assert tuple(bpy.app.version)==(4,5,15) and digest(bpy.app.binary_path)==tool['executable_sha256']
rows=[]
for asset in raw['assets']:
    source=asset['source']['artifact'];assert digest(root/source['path'])==source['sha256']
    lod=asset['lods'][0];assert digest(root/lod['artifact']['path'])==lod['artifact']['sha256']
    bpy.ops.wm.open_mainfile(filepath=str(root/source['path']))
    bpy.ops.object.select_all(action='SELECT');target=out/(asset['placement_ids'][0].replace('equipment:','')+'.glb')
    bpy.ops.export_scene.gltf(filepath=str(target),export_format='GLB',use_selection=True,export_yup=True,export_apply=True,export_extras=True,export_animations=True,export_animation_mode='ACTIONS',export_force_sampling=True,export_frame_range=True,export_anim_slide_to_zero=True,export_frame_step=1,export_cameras=False,export_lights=False)
    rows.append({'asset_id':asset['id'],'source':source,'original_lod':lod['artifact'],'original_semantic_sha256':lod['semantic_geometry_sha256'],'reopened_glb':str(target),'reopened_sha256':digest(target)})
    print('ACTUAL_SOURCE_REOPEN_EXPORTED '+asset['id'],flush=True)
(out/'receipt.json').write_text(json.dumps({'manifest_sha256':args.expected_sha,'actual_sources':len(rows),'actual_exported_glbs':len(rows),'rows':rows},indent=2)+'\n')
