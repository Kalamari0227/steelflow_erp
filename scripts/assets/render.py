"""Render actual exported GLBs and reopen authored .blend files with pinned Blender."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import sys

import bpy
from mathutils import Matrix, Vector

REPO = Path(__file__).resolve().parents[2]
C = Matrix.Rotation(-math.pi/2,4,'X')

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def setup():
    scene=bpy.context.scene
    scene.render.engine='CYCLES';scene.cycles.samples=32;scene.cycles.use_denoising=True
    scene.render.resolution_x=1000;scene.render.resolution_y=800;scene.render.resolution_percentage=100
    scene.render.image_settings.file_format='PNG';scene.view_settings.view_transform='AgX';scene.world.color=(.8,.8,.8)
    target=Vector((0,0,1.15))
    for name,pos,power,size in [('key',(1,-4,7),1500,5),('fill',(-4,1,4),950,4)]:
        bpy.ops.object.light_add(type='AREA',location=pos);light=bpy.context.object;light.name='proof_'+name
        light.data.energy=power;light.data.shape='DISK';light.data.size=size
        light.rotation_euler=(target-light.location).to_track_quat('-Z','Y').to_euler()
    bpy.ops.mesh.primitive_plane_add(size=200);ground=bpy.context.object;ground.name='proof_ground';ground.location.z=-.055
    material=bpy.data.materials.new('proof_ground_material');material.diffuse_color=(.78,.75,.67,1);ground.data.materials.append(material)
    bpy.ops.object.camera_add();camera=bpy.context.object;camera.name='proof_camera';camera.data.type='ORTHO';camera.data.ortho_scale=7.6;scene.camera=camera
    return camera,target

def nodes():
    return {obj.get('semantic_id'):list(sum(([float(v) for v in row] for row in C @ obj.matrix_world @ C.inverted()),[])) for obj in bpy.data.objects if obj.get('semantic_id')}

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--root',required=True);parser.add_argument('--out',required=True)
    args=parser.parse_args(sys.argv[sys.argv.index('--')+1:]);root=Path(args.root).resolve();out=Path(args.out).resolve()
    if out.exists() and any(out.iterdir()):raise ValueError('Refuse overwrite of proof output')
    out.mkdir(parents=True,exist_ok=True)
    tool=json.loads((REPO/'assets/toolchain.json').read_text())
    assert bpy.app.version==(4,5,15) and digest(Path(bpy.app.binary_path))==tool['executable_sha256']
    manifest=json.loads((root/'public/assets/steelworks/manifest.json').read_text());receipt={'tool_sha256':tool['executable_sha256'],'assets':[],'boundary':'GLB authored clip sampling only; not server runtime or UI pause/resume proof'}
    for asset in manifest['assets']:
        key=asset['kind'];source=root/asset['source']['artifact']['path'];glb=root/asset['lods'][0]['artifact']['path']
        assert digest(source)==asset['source']['artifact']['sha256'] and digest(glb)==asset['lods'][0]['artifact']['sha256']
        bpy.ops.wm.open_mainfile(filepath=str(source),load_ui=False,use_scripts=False)
        source_nodes={obj.get('semantic_id') for obj in bpy.data.objects if obj.get('semantic_id')}
        assert source_nodes=={n['id'] for n in asset['nodes']}
        assert all(image.packed_file for image in bpy.data.images if image.name=='paint_color')
        bpy.ops.wm.read_factory_settings(use_empty=False)
        bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
        bpy.ops.import_scene.gltf(filepath=str(glb),import_pack_images=True,import_shading='NORMALS')
        camera,target=setup();captures=[];matrices={}
        for name,position,frame in [('front',(7,-9,6),0),('side',(8,1,4),0),('rear',(-7,9,6),0),('quarter',(7,-9,6),6),('midpoint',(7,-9,6),12),('three-quarter',(7,-9,6),18)]:
            bpy.context.scene.frame_set(frame);bpy.context.view_layer.update()
            camera.location=position;camera.rotation_euler=(target-camera.location).to_track_quat('-Z','Y').to_euler()
            path=out/f'{key}-{name}.png';bpy.context.scene.render.filepath=str(path);bpy.ops.render.render(write_still=True)
            matrices[name]=nodes();captures.append({'angle':name,'clip_frame':frame,'camera_blender_z_up':position,'image':str(path),'sha256':digest(path)})
        part=asset['moving_parts'][0]['node_id']
        assert matrices['front'][part]!=matrices['midpoint'][part]
        assert matrices['front'][part]!=matrices['quarter'][part]
        for fixed in asset['fixed_parts']:
            assert all(matrices['front'][fixed['node_id']]==pose[fixed['node_id']] for pose in matrices.values())
        bpy.context.scene.frame_set(12);bpy.context.view_layer.update();assert nodes()==matrices['midpoint']
        receipt['assets'].append({'id':asset['id'],'source_reopened':True,'packed_texture':True,'source_sha256':digest(source),'glb_sha256':digest(glb),'semantic_geometry_sha256':asset['lods'][0]['semantic_geometry_sha256'],'captures':captures,'matrices_project_y_up':matrices,'moving_part_changed':part,'fixed_parts_unchanged':[p['node_id'] for p in asset['fixed_parts']]})
        (out/'render-receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print('STEELFLOW_RENDER_PROOF_COMPLETE')

if __name__=='__main__':main()
