"""Reopen every original Blender source, inspect true semantic pivots and editable geometry.

Pinned Blender --background --factory-startup --python-exit-code 1 --python
assets/source/steelmaking/reopen.py -- --root OUTPUT --family steelmaking|stainless.
"""
import argparse
import json
from pathlib import Path
import sys
import bpy


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--root',required=True);parser.add_argument('--family',choices=['steelmaking','stainless'],required=True)
    args=parser.parse_args(sys.argv[sys.argv.index('--')+1:]);root=Path(args.root).resolve()
    manifest=json.loads((root/'public/assets/steelworks'/args.family/'manifest.json').read_text());rows=[]
    for asset in manifest['assets']:
        path=root/asset['source']['artifact']['path'];bpy.ops.wm.open_mainfile(filepath=str(path))
        meshes=[o for o in bpy.data.objects if o.type=='MESH'];parts=asset['moving_parts']+asset['fixed_parts'];observed=[]
        for part in parts:
            obj=bpy.data.objects.get(part['node_id'])
            if obj is None:raise RuntimeError('Editable part missing: '+part['node_id'])
            expected=next(n for n in asset['nodes'] if n['id']==part['node_id'])
            actual=[obj.location.x,obj.location.z,-obj.location.y]
            if any(abs(a-b)>1e-5 for a,b in zip(actual,expected['transform']['position_m'])):raise RuntimeError('Original pivot differs: '+part['node_id'])
            observed.append({'id':part['id'],'parent':obj.parent.name if obj.parent else None,'semantic_id':obj['semantic_id'],'editable_mesh_descendants':sum(o.type=='MESH' for o in [obj,*obj.children_recursive]),'has_own_action':obj.animation_data is not None})
        if len(meshes)<15:raise RuntimeError('Source geometry unexpectedly sparse')
        rows.append({'id':asset['id'],'path':str(path),'meshes':len(meshes),'vertices':sum(len(o.data.vertices) for o in meshes),'parts':observed})
    print(json.dumps({'status':'PASS','family':args.family,'reopened_sources':len(rows),'assets':rows},indent=2))


if __name__=='__main__':main()
