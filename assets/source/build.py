"""Build original, metre-scale SteelFlow demonstrators with pinned Blender 4.5.15.

Run through Blender --background --factory-startup --python-exit-code 1.
Only the explicit, previously registered output directory is written.
"""
import argparse
import copy
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys

import bpy
from mathutils import Matrix, Quaternion, Vector

REPO = Path(__file__).resolve().parents[2]
CONVERSION = Matrix.Rotation(-math.pi / 2, 4, 'X')
INVERSE = CONVERSION.inverted()
IDENTITY = [0, 0, 0, 1]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_json(path, value):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')


def artifact(root, relative):
    return {'status': 'built', 'path': relative, 'sha256': sha(root / relative)}


def quat_blender(q):
    return (INVERSE @ Quaternion((q[3], *q[:3])).to_matrix().to_4x4() @ CONVERSION).to_quaternion()


def pos_blender(p):
    return INVERSE.to_3x3() @ Vector(p)


def quat_product(a, b):
    q = Quaternion((a[3], *a[:3])) @ Quaternion((b[3], *b[:3]))
    q.normalize()
    values = [q.x, q.y, q.z, q.w]
    norm = math.sqrt(sum(v*v for v in values))
    return [v/norm for v in values]


class Model:
    def __init__(self, key, lod, recipe, output):
        self.key, self.lod, self.recipe, self.output = key, lod, recipe, output
        self.nodes, self.objects, self.materials = [], {}, {}
        self.segments = recipe['lod_cylinder_segments'][lod]
        bpy.ops.object.select_all(action='SELECT')
        bpy.ops.object.delete(use_global=False)
        for collection in (bpy.data.meshes, bpy.data.materials, bpy.data.actions, bpy.data.images):
            for block in list(collection):
                if block.users == 0:
                    collection.remove(block)
        bpy.context.scene.unit_settings.system = 'METRIC'
        bpy.context.scene.unit_settings.scale_length = 1.0
        bpy.context.scene.render.fps = 24
        bpy.context.scene.frame_start, bpy.context.scene.frame_end = 1, 25
        self.node('root', None)
        self.make_materials()

    def node(self, name, parent='root', position=(0, 0, 0), rotation=IDENTITY, mesh=None, material=None):
        obj = bpy.data.objects.new(name, mesh)
        bpy.context.collection.objects.link(obj)
        if parent:
            obj.parent = self.objects[parent]
        obj.location = pos_blender(position)
        obj.rotation_mode = 'QUATERNION'
        obj.rotation_quaternion = quat_blender(rotation)
        obj['semantic_id'] = name
        obj['asset_kind'] = self.key
        locator = name if parent is None else next(n['locator'] for n in self.nodes if n['id'] == parent) + '/' + name
        self.nodes.append({'id': name, 'parent_id': parent, 'locator': locator, 'transform': {'position_m': list(position), 'rotation_xyzw': list(rotation)}})
        self.objects[name] = obj
        if material:
            obj.data.materials.append(self.materials[material])
        return obj

    def mesh(self, name, vertices, faces):
        mesh = bpy.data.meshes.new(name + '.mesh')
        mesh.from_pydata([pos_blender(v) for v in vertices], [], faces)
        mesh.update()
        uv = mesh.uv_layers.new(name='UVMap')
        for poly in mesh.polygons:
            for loop_index in poly.loop_indices:
                p = mesh.vertices[mesh.loops[loop_index].vertex_index].co
                uv.data[loop_index].uv = (p.x * 0.5 + 0.5, p.z * 0.5 + 0.5)
        return mesh

    def box(self, name, size, position=(0, 0, 0), parent='root', material='structure', rotation=IDENTITY, bevel=0):
        x, y, z = [v / 2 for v in size]
        vertices = [(-x,-y,-z), (x,-y,-z), (x,y,-z), (-x,y,-z), (-x,-y,z), (x,-y,z), (x,y,z), (-x,y,z)]
        faces = [(0,3,2,1), (4,5,6,7), (0,1,5,4), (3,7,6,2), (0,4,7,3), (1,2,6,5)]
        obj = self.node(name, parent, position, rotation, self.mesh(name, vertices, faces), material)
        if bevel:
            mod = obj.modifiers.new('authored_edge_bevel', 'BEVEL')
            mod.width = bevel
            mod.segments = self.recipe['lod_bevel_segments'][self.lod]
            bpy.context.view_layer.objects.active = obj
            obj.select_set(True)
            bpy.ops.object.modifier_apply(modifier=mod.name)
            # Reproject from final vertex positions: bevel's interpolated UV
            # accumulation order can vary by process at float32 precision.
            uv = obj.data.uv_layers.active
            for loop in obj.data.loops:
                p = obj.data.vertices[loop.vertex_index].co
                uv.data[loop.index].uv = (p.x * 0.5 + 0.5, p.z * 0.5 + 0.5)
            obj.select_set(False)
        return obj

    def cylinder(self, name, radius, depth, position=(0, 0, 0), parent='root', material='exposed', rotation=IDENTITY):
        # Project Z shaft. Distinct indexed strip on the circumference shows actual rotation.
        n = self.segments
        vertices = [(radius * math.cos(i*2*math.pi/n), radius * math.sin(i*2*math.pi/n), z) for z in [-depth/2, depth/2] for i in range(n)]
        faces = [tuple(range(n-1,-1,-1)), tuple(range(n,2*n))]
        faces += [(i, (i+1)%n, (i+1)%n+n, i+n) for i in range(n)]
        return self.node(name, parent, position, rotation, self.mesh(name, vertices, faces), material)

    def make_materials(self):
        palette = {
            'paint': ([0.19,0.31,0.38,1],0.12,0.72),
            'structure': ([0.097,0.13,0.15,1],0.72,0.55),
            'exposed': ([0.42,0.48,0.50,1],0.90,0.38),
            'safety': ([0.62,0.26,0.045,1],0.25,0.58),
            'marker_red': ([0.65,0.04,0.02,1],0.0,0.8),
            'marker_green': ([0.05,0.40,0.12,1],0.0,0.8),
            'marker_blue': ([0.025,0.12,0.65,1],0.0,0.8),
        }
        self.material_specs = []
        for name, (color, metallic, roughness) in palette.items():
            mat = bpy.data.materials.new(name); mat.use_nodes = True
            mat['semantic_id'] = name
            principled = mat.node_tree.nodes.get('Principled BSDF')
            principled.inputs['Base Color'].default_value = color
            principled.inputs['Metallic'].default_value = metallic
            principled.inputs['Roughness'].default_value = roughness
            slots = []
            if name == 'paint':
                image = bpy.data.images.new('paint_color', width=32, height=32, alpha=True)
                image.colorspace_settings.name = 'sRGB'
                pixels = []
                for y in range(32):
                    for x in range(32):
                        variation = 0.94 + (((x*17+y*31+self.recipe['seed']) % 11) / 100)
                        pixels.extend([variation,variation,variation,1])
                image.pixels[:] = pixels
                image.filepath_raw = str(self.output / 'assets/source/paint.png')
                image.file_format = 'PNG'; image.save()
                tex = mat.node_tree.nodes.new('ShaderNodeTexImage'); tex.image = image
                # The generated neutral coating texture modulates the paint colour.
                mix = mat.node_tree.nodes.new('ShaderNodeMixRGB'); mix.blend_type = 'MULTIPLY'
                mix.inputs[0].default_value = 1; mix.inputs[2].default_value = color
                mat.node_tree.links.new(tex.outputs['Color'], mix.inputs[1])
                # glTF supports a texture times a base factor directly; use texture
                # with the authored tint baked into its pixels for exact material export.
                tinted = []
                for i in range(0,len(pixels),4):
                    tinted.extend([pixels[i+j]*color[j] for j in range(3)] + [1])
                image.pixels[:] = tinted; image.save(); image.pack()
                mat.node_tree.links.new(tex.outputs['Color'], principled.inputs['Base Color'])
                slots = [{'slot':'baseColor','texture_id':'paint_color'}]
                color = [1,1,1,1]
            self.materials[name] = mat
            self.material_specs.append({'id':name,'model':'metallic-roughness','base_color':color,'metallic':metallic,'roughness':roughness,'textures':slots})

    def axes(self):
        self.box('axis_origin',[0.06,0.06,0.06],material='structure')
        vertices=[(-.08,-.025,-.025),(-.08,.025,-.025),(-.08,.025,.025),(-.08,-.025,.025),(.14,0,0)]
        self.node('axis_front','root',(1,0,0),mesh=self.mesh('axis_front',vertices,[(0,3,2,1),(0,1,4),(1,2,4),(2,3,4),(3,0,4)]),material='marker_red')
        self.box('axis_up',[.04,.16,.04],(0,1,0),material='marker_green')
        self.box('axis_side',[.04,.04,.12],(0,0,-1),material='marker_blue')

    def service_pad(self):
        q = quat_product([math.sin(.23),0,0,math.cos(.23)], [0,math.sin(.17),0,math.cos(.17)])
        self.box('service_pedestal',[.18,1.55,.18],(-1.5,.775,-1.2),material='structure')
        self.node('service_bracket',position=(-1.5,1.6,-1.2),rotation=q)
        self.box('service_brace',[.12,.35,.12],(0,-.12,0),'service_bracket','structure')
        self.box('service_pad',[.4,.16,.4],(.12,0,.08),'service_bracket','safety')
        return {'id':'service_support','node_id':'service_pad','role':'support','transform':{'position_m':[0,.08,0],'rotation_xyzw':IDENTITY},'normal':[0,1,0],'forms':['PACKAGED'],'max_load_kg':50}

    def animate(self, name, motion):
        obj=self.objects[name]
        if motion=='translation':
            rest = obj.location.copy()
            for frame, distance in [(1,0),(13,.48),(25,0)]:
                obj.location=rest+pos_blender((0,-distance,0));obj.keyframe_insert(data_path='location',frame=frame)
        else:
            for frame, angle in [(frame, (frame-1)*math.pi/12) for frame in range(1,26)]:
                obj.rotation_quaternion=quat_blender([0,0,math.sin(angle/2),math.cos(angle/2)])
                obj.keyframe_insert(data_path='rotation_quaternion',frame=frame)
        action=obj.animation_data.action;action.name=self.key+'.'+name
        for slot in action.slots:
            for layer in action.layers:
                for strip in layer.strips:
                    bag=strip.channelbag(slot)
                    if bag:
                        for curve in bag.fcurves:
                            for point in curve.keyframe_points: point.interpolation='LINEAR'
        bpy.context.scene.frame_set(1)
        return action.name

    def shear(self):
        self.node('support_bed',position=(0,.94,0))
        self.box('entry_table',[2.4,.22,1.6],(-1.3,0,0),'support_bed','exposed')
        self.box('exit_table',[2.4,.22,1.6],(1.3,0,0),'support_bed','exposed')
        for x,label in [(-2,'entry'),(2,'exit')]:
            for z,side in [(-.65,'left'),(.65,'right')]:
                self.box(label+'_'+side+'_leg',[.22,.83,.22],(x,.415,z),material='paint',bevel=.025)
                self.box(label+'_'+side+'_foot',[.52,.08,.45],(x,.04,z),bevel=.015)
        for z,side in [(-1,'left'),(1,'right')]:
            self.box(side+'_column',[.65,2.9,.42],(0,1.45,z),material='paint',bevel=.055)
            self.box(side+'_guide',[.18,1.35,.12],(.34,1.9,z),material='exposed')
        self.box('head_beam',[.9,.42,2.5],(0,2.8,0),material='paint',bevel=.05)
        self.box('cutting_tool',[.18,.55,1.78],(0,1.8,0),material='exposed',bevel=.008)
        self.box('blade_carriage',[.5,.2,1.85],(0,.28,0),'cutting_tool','safety',bevel=.025)
        self.box('blade_edge',[.08,.1,1.78],(.045,-.29,0),'cutting_tool','structure')
        self.box('hydraulic_body',[.45,.45,.45],(0,2.42,0),material='structure',bevel=.05)
        self.box('rod',[.11,.95,.11],(0,.73,0),'cutting_tool','exposed')
        self.box('front_control',[.3,.45,.3],(.5,1.3,-1.2),material='safety',bevel=.025)
        return 'cutting_tool','translation',self.animate('cutting_tool','translation')

    def galvanizing(self):
        self.box('support_bed',[4,.25,2.8],(0,.125,0),material='structure')
        for z,side in [(-1.2,'left'),(1.2,'right')]:
            self.box(side+'_bath_wall',[3.8,1.25,.2],(0,.86,z),material='paint',bevel=.04)
            self.box(side+'_rim',[4,.12,.34],(0,1.53,z),material='exposed')
        for x,side in [(-1.85,'entry'),(1.85,'exit')]:
            self.box(side+'_bath_wall',[.2,1.25,2.25],(x,.86,0),material='paint',bevel=.04)
        self.box('bath_lining',[3.5,.08,2.1],(0,.31,0),material='exposed')
        self.node('sink_roll',position=(0,.85,0))
        self.cylinder('sink_roll_surface',.45,1.65,parent='sink_roll')
        self.box('roll_index',[.035,.06,1.62],(.45,0,0),'sink_roll','safety')
        self.cylinder('shaft',.11,2.7,parent='sink_roll',material='structure')
        for z,side in [(-1.35,'left'),(1.35,'right')]:
            self.box(side+'_bearing',[.45,.45,.25],(0,.85,z),material='safety',bevel=.04)
        self.node('air_knife',position=(.7,2.05,0))
        for x,label in [(-.17,'inlet'),(.17,'outlet')]:
            self.box(label+'_nozzle',[.16,.18,1.85],(x,0,0),'air_knife','exposed',bevel=.015)
            self.box(label+'_nozzle_slot',[.015,.025,1.72],(x+(.085 if x<0 else -.085),0,0),'air_knife','structure')
        for z,label in [(-1.1,'left'),(1.1,'right')]:
            self.box(label+'_knife_stand',[.18,2.35,.18],(.7,1.175,z),material='paint',bevel=.02)
            self.box(label+'_gas_manifold',[.25,.3,.25],(.7,1.8,z),'root','safety',bevel=.02)
        # Discrete planar strip support pads at the actual entry/work/exit contacts.
        for x,label in [(-1.4,'entry'),(0,'work'),(1.4,'exit')]:
            self.box(label+'_crossbar',[.25,.11,2.5],(x,1.585,0),material='structure')
            self.box(label+'_support',[.4,.12,.9],(x,1.7,0),material='exposed')
        for z,label in [(-1.02,'left'),(1.02,'right')]:
            self.box(label+'_knife_mount',[.6,.2,.3],(0,0,z),'air_knife','safety',bevel=.015)
        return 'sink_roll','rotation',self.animate('sink_roll','rotation')

    def collision_bounds(self, part):
        def collect(objects):
            points = []
            for obj in objects:
                if obj.type == 'MESH':
                    points.extend(CONVERSION @ obj.matrix_world @ Vector(corner) for corner in obj.bound_box)
            return points
        bpy.context.scene.frame_set(1); bpy.context.view_layer.update()
        body_points = collect(self.objects.values())
        moving = self.objects[part]
        moving_objects = [moving, *moving.children_recursive]
        sweep_points = []
        for frame in range(1,26):
            bpy.context.scene.frame_set(frame); bpy.context.view_layer.update()
            sweep_points.extend(collect(moving_objects))
        bpy.context.scene.frame_set(1); bpy.context.view_layer.update()
        def bounds(points):
            lower = [min(p[i] for p in points) for i in range(3)]
            upper = [max(p[i] for p in points) for i in range(3)]
            return {'position_m':[round((a+b)/2,6) for a,b in zip(lower,upper)], 'size_m':[round(b-a+.02,6) for a,b in zip(lower,upper)]}
        return bounds(body_points), bounds(sweep_points)

    def render(self, output_path):
        scene=bpy.context.scene
        bpy.ops.object.camera_add(location=(7,-9,6))
        camera=bpy.context.object; camera.name='proof_camera'
        target=Vector((0,0,1.15));camera.rotation_euler=(target-camera.location).to_track_quat('-Z','Y').to_euler()
        camera.data.type='ORTHO';camera.data.ortho_scale=7.6;scene.camera=camera
        scene.world.color=(.8,.8,.8)
        for name,pos,power,size in [('key',(1,-4,7),1500,5),('fill',(-4,1,4),950,4)]:
            bpy.ops.object.light_add(type='AREA',location=pos);light=bpy.context.object;light.name='proof_'+name
            light.data.energy=power;light.data.shape='DISK';light.data.size=size
            light.rotation_euler=(target-light.location).to_track_quat('-Z','Y').to_euler()
        bpy.ops.mesh.primitive_plane_add(size=200)
        ground=bpy.context.object;ground.name='proof_ground';ground.location.z=-.055
        material=bpy.data.materials.new('proof_ground_material');material.diffuse_color=(.78,.75,.67,1);ground.data.materials.append(material)
        scene.render.engine='CYCLES';scene.cycles.samples=32;scene.cycles.use_denoising=True
        scene.render.resolution_x=1000;scene.render.resolution_y=800;scene.render.resolution_percentage=100
        scene.view_settings.view_transform='AgX';scene.render.image_settings.file_format='PNG';scene.render.filepath=str(output_path)
        bpy.ops.render.render(write_still=True)
        for obj in [o for o in bpy.data.objects if o.name.startswith('proof_')]:
            bpy.data.objects.remove(obj,do_unlink=True)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--out',required=True);parser.add_argument('--render',action='store_true')
    args=parser.parse_args(sys.argv[sys.argv.index('--')+1:])
    out=Path(args.out).resolve()
    if out.exists() and any(out.iterdir()): raise ValueError('Output must be new or empty; refuse overwrite')
    tool=json.loads((REPO/'assets/toolchain.json').read_text())
    if tuple(bpy.app.version)!=(4,5,15) or sha(bpy.app.binary_path)!=tool['executable_sha256']:
        raise ValueError('Pinned Blender version/executable mismatch')
    recipe=json.loads((REPO/'assets/source/recipe.json').read_text())
    (out/'assets/source').mkdir(parents=True,exist_ok=True)
    (out/'public/assets/steelworks').mkdir(parents=True,exist_ok=True)
    for source,dest in [('assets/toolchain.json','assets/toolchain.json'),('assets/source/recipe.json','assets/source/recipe.json'),('assets/source/LICENSE.txt','assets/source/LICENSE.txt'),('scripts/assets/build.py','assets/source/build.py')]:
        shutil.copyfile(REPO/source,out/dest)
    contract_artifacts = []
    (out/'assets/source/contracts').mkdir()
    for spec in recipe['models']:
        relative = 'assets/source/contracts/' + Path(spec['fixture']).name
        shutil.copyfile(REPO/spec['fixture'], out/relative)
        contract_artifacts.append(artifact(out, relative))
    recipe_artifact=artifact(out,'assets/source/recipe.json')
    def provenance(title):
        return {'origin':'self_created','creator':recipe['author'],'title':title,'license':'project-owned','distribution_permission':'project-local','recipe':recipe_artifact,'third_party_inputs':[]}
    manifest={'schema_version':1,'purpose':'production','assets':[]}
    for spec in recipe['models']:
        asset=copy.deepcopy(json.loads((REPO/spec['fixture']).read_text())['assets'][0])
        asset['id']='steelflow:'+spec['kind']+':'+spec['variant'].split(':')[-1]
        asset['source_refs'][0]['note']='Original synthetic demonstrator dimensions; source supports function concept only. Actual GLB clips verified by T12; operational runtime integration pending T6/T13.'
        asset['lods']=[]
        for lod in range(3):
            model=Model(spec['key'],lod,recipe,out)
            part,motion,clip=getattr(model,spec['key'])()
            service=model.service_pad();model.axes()
            if lod==0:
                asset['nodes']=model.nodes
                asset['moving_parts'][0].update({'node_id':part,'motion':motion,'axis':[0,-1,0] if motion=='translation' else [0,0,1], 'pivot_m':next(n['transform']['position_m'] for n in model.nodes if n['id']==part),'range':{'min':0,'max':.48 if motion=='translation' else math.pi*2,'rest':0,'unit':'m' if motion=='translation' else 'rad'}})
                binding=asset['moving_parts'][0]['binding'];binding.pop('procedure_id',None);binding.update({'type':'clip','clip_id':clip})
                height=1.05 if spec['key']=='shear' else 1.76
                for socket in asset['sockets']:
                    x={'entry':-1.4,'exit':1.4,'support':-1.3,'work':.3}.get(socket['id'],0)
                    socket['node_id']='support_bed' if spec['key']=='shear' else ('work_support' if socket['id']=='support' else socket['id']+'_support')
                    socket['transform']['position_m']=[x,.11,0] if spec['key']=='shear' else [0,.06,0]
                asset['sockets'].append(service)
                asset['materials']=[{**m,'provenance':provenance('Original '+m['id']+' PBR material')} for m in model.material_specs]
                asset['textures']=[{'id':'paint_color','artifact':artifact(out,'assets/source/paint.png'),'color_space':'srgb','provenance':provenance('Original deterministic procedural coating texture')}]
                body_bounds, sweep_bounds = model.collision_bounds(part)
                asset['collision_proxies']=[{'id':'body','node_id':'root','shape':'box','transform':{'position_m':body_bounds['position_m'],'rotation_xyzw':IDENTITY},'size_m':body_bounds['size_m'],'purpose':'body','part_id':None,'contact_socket_ids':[s['id'] for s in asset['sockets']]}, {'id':'tool_sweep','node_id':'root','shape':'box','transform':{'position_m':sweep_bounds['position_m'],'rotation_xyzw':IDENTITY},'size_m':sweep_bounds['size_m'],'purpose':'moving_sweep','part_id':part,'contact_socket_ids':['work']}]
                source_path='assets/source/'+spec['key']+'.blend'
                bpy.ops.wm.save_as_mainfile(filepath=str(out/source_path),check_existing=False,compress=True)
                asset['source']={'artifact':artifact(out,source_path),'provenance':provenance('Original editable '+spec['key']+' source')}
                asset['export']['tool_artifact']=artifact(out,'assets/toolchain.json')
                asset['export']['recipe']=artifact(out,'assets/source/build.py')
            relative='public/assets/steelworks/'+spec['key']+'-lod'+str(lod)+'.glb'
            bpy.ops.object.select_all(action='DESELECT')
            for obj in model.objects.values():obj.select_set(True)
            bpy.ops.export_scene.gltf(filepath=str(out/relative),export_format='GLB',use_selection=True,export_yup=True,export_apply=True,export_extras=True,export_animations=True,export_animation_mode='ACTIONS',export_force_sampling=True,export_frame_range=True,export_anim_slide_to_zero=True,export_frame_step=1,export_cameras=False,export_lights=False)
            asset['lods'].append({'level':lod,'artifact':artifact(out,relative),'semantic_geometry_sha256':None,'nodes':copy.deepcopy(model.nodes),'socket_ids':[s['id'] for s in asset['sockets']],'part_ids':[p['id'] for p in asset['moving_parts']+asset['fixed_parts']],'material_ids':[m['id'] for m in asset['materials']]})
            if args.render and lod==0:model.render(out/'public/assets/steelworks'/f'{spec["key"]}-proof.png')
        manifest['assets'].append(asset)
    write_json(out/'public/assets/steelworks/manifest.json',manifest)
    inventory={'external_asset_count':0,'license':artifact(out,'assets/source/LICENSE.txt'),'inputs':[artifact(out,p) for p in ['assets/source/recipe.json','assets/source/build.py','assets/toolchain.json']] + contract_artifacts,'authored_assets':[artifact(out,'assets/source/'+m['key']+'.blend') for m in recipe['models']],'textures':[artifact(out,'assets/source/paint.png')],'tool_license':{'path':tool['tool_license_path'],'sha256':tool['tool_license_sha256']},'limitations':recipe['runtime_limit']}
    write_json(out/'assets/source/inventory.json',inventory)
    completed=subprocess.run(['node',str(REPO/'scripts/assets/stamp.mjs'),'--root',str(out)],check=False,text=True,capture_output=True,timeout=60)
    print(completed.stdout);print(completed.stderr,file=sys.stderr)
    if completed.returncode:raise RuntimeError('GLB semantic stamping failed')
    print('STEELFLOW_BUILD_COMPLETE '+str(out))


if __name__=='__main__':main()
