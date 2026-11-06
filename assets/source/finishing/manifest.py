"""Map independently registered finishing requirements to actual authored artifacts."""
import hashlib
import json
import math
from pathlib import Path
from mathutils import Vector
import bpy
from geometry import CONVERSION, IDENTITY, PALETTE


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def artifact(root, relative):
    return {'status':'built','path':relative,'sha256':sha(root/relative)}


def write_json(path, value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,indent=2,ensure_ascii=False)+'\n')


def provenance(root, title):
    return {'origin':'self_created','creator':'SteelFlow original procedural authorship','title':title,'license':'project-owned','distribution_permission':'project-local','recipe':artifact(root,'assets/source/finishing/recipe.json'),'third_party_inputs':[]}


def asset_row(binding, coverage):
    variant=next(v for v in coverage['observed_inventory']['semantic_variants'] if v['id']==binding['variant'])
    rows=[v for v in coverage['observed_inventory']['equipment'] if v['id'] in binding['placement_ids']]
    requirements=sorted(set(binding['requirement_ids']+variant['requirement_ids']+sum((v['requirement_ids'] for v in rows),[])))
    qa=sorted(set(binding['qa_row_ids']+variant['qa_row_ids']+sum((v['qa_row_ids'] for v in rows),[])))
    refs=set()
    for r in coverage['source_requirements']+coverage['approved_scope_requirements']:
        if r['id'] in requirements:
            refs.update(r['source_ids'])
    sources=[{'id':s['id'],'uri':s['url'],'note':'Public function concept only. Dimensions, clearances, transmissions and speeds are original synthetic miniature design, not measured site specifications.'} for s in coverage['sources'] if s['id'] in refs and s['url']]
    sources.append({'id':binding['requirement_ids'][0],'uri':'.omo/plans/steelflow-uniform-fidelity-factory.md','note':'Approved synthetic asset family; authored dimensions and mechanical detail are design assumptions.'})
    return {'id':'steelflow:finishing:'+binding['variant'].split(':')[-1],'family':'finishing','category':'equipment','kind':binding['kind'],'variant':binding['variant'],'requirement_ids':requirements,'qa_row_ids':qa,'placement_ids':binding['placement_ids'],'source_refs':sources,'coordinate_system':{'length':'m','up':'+Y','forward':'+X','handedness':'right','angle':'rad'},'root_node_id':'root','lods':[]}


def bounds(objects):
    points=[CONVERSION@o.matrix_world@Vector(v) for o in objects if o.type=='MESH' for v in o.bound_box]
    lower=[min(v[i] for v in points) for i in range(3)]
    upper=[max(v[i] for v in points) for i in range(3)]
    return {'position_m':[(a+b)/2 for a,b in zip(lower,upper)],'rotation_xyzw':list(IDENTITY)},[b-a+.04 for a,b in zip(lower,upper)]


def complete_asset(asset, model, sockets, root):
    asset['nodes']=model.nodes
    if model.feed_spec is not None:asset['internal_feeds']=[model.feed_spec]
    asset['sockets']=sockets
    asset['moving_parts']=[]
    for spec in model.motions:
        pivot=next(n['transform']['position_m'] for n in model.nodes if n['id']==spec.name)
        asset['moving_parts'].append({'id':spec.name,'node_id':spec.name,'function':spec.name,'role':'operational','motion':spec.mode,'axis':list(spec.axis),'pivot_m':pivot,'range':{'min':spec.minimum,'max':spec.maximum,'rest':0,'unit':'m' if spec.mode=='translation' else 'rad'},'binding':{'type':'clip','clock':'server_sim','phase':spec.phase,'progress_source':'server_phase_progress','pause':'hold','fault':'hold','rest':'range_rest','clip_id':model.key+'.'+spec.name}})
    for follower in model.followers:
        driver=next(p for p in asset['moving_parts'] if p['id']==follower['driver'])
        endpoint=driver['range']['max']*follower['ratio']
        asset['moving_parts'].append({'id':follower['node_id'],'node_id':follower['node_id'],'function':driver['function'],'role':'operational','motion':'rotation','axis':follower['axis'],'pivot_m':follower['pivot_m'],'range':{'min':min(0,endpoint),'max':max(0,endpoint),'rest':0,'unit':'rad'},'binding':{'type':'mechanical_follower','driver_part_id':driver['id'],'ratio':follower['ratio']}})
    asset['fixed_parts']=[]
    for name in model.states:
        asset['fixed_parts'].append({'id':name,'node_id':name,'function':name,'reason':'Actual stationary treatment assembly; duty follows admitted canonical state.','binding':{'type':'operational_state','clock':'server_sim','phase':'work','progress_source':'server_phase_progress','pause':'hold','fault':'hold','rest':'inactive','state_id':name+'.state'}})
    asset['cutaway']={'roof_node_ids':model.roofs,'interior_node_ids':model.interior,'retained_socket_ids':[s['id'] for s in sockets] if model.roofs else []}
    asset['materials']=[{'id':name,'model':'metallic-roughness','base_color':list(color),'metallic':metallic,'roughness':roughness,'textures':[],'provenance':provenance(root,'Original '+name+' metal/paint finish')} for name,(color,metallic,roughness) in PALETTE.items()]
    asset['textures']=[]
    bpy.context.scene.frame_set(1)
    bpy.context.view_layer.update()
    pose,size=bounds(model.objects.values())
    asset['collision_proxies']=[{'id':'body','node_id':'root','shape':'box','transform':pose,'size_m':size,'purpose':'body','part_id':None,'contact_socket_ids':[s['id'] for s in sockets]}]
    for part in asset['moving_parts']:
        obj=model.objects[part['node_id']]
        points=[]
        for frame in range(1,bpy.context.scene.frame_end+1):
            bpy.context.scene.frame_set(frame)
            bpy.context.view_layer.update()
            points.extend(CONVERSION@o.matrix_world@Vector(v) for o in [obj,*obj.children_recursive] if o.type=='MESH' for v in o.bound_box)
        lo=[min(p[i] for p in points) for i in range(3)]
        hi=[max(p[i] for p in points) for i in range(3)]
        asset['collision_proxies'].append({'id':part['id']+'_sweep','node_id':'root','shape':'box','transform':{'position_m':[(a+b)/2 for a,b in zip(lo,hi)],'rotation_xyzw':list(IDENTITY)},'size_m':[b-a+.04 for a,b in zip(lo,hi)],'purpose':'moving_sweep','part_id':part['id'],'contact_socket_ids':['work']})
    bpy.context.scene.frame_set(1)
    bpy.context.view_layer.update()
    relative='assets/source/finishing/'+model.key+'.blend'
    bpy.ops.wm.save_as_mainfile(filepath=str(root/relative),check_existing=False,compress=True)
    asset['source']={'artifact':artifact(root,relative),'provenance':provenance(root,'Original editable '+model.key+' miniature')}
    asset['export']={'tool':'Blender','version':'4.5.15','tool_artifact':artifact(root,'assets/toolchain.json'),'recipe':artifact(root,'assets/source/finishing/build.py'),'settings':{'format':'GLB','y_up':True,'apply_transforms':True,'animations':True},'authoring_axes':{'up':'+Z','forward':'+X'},'conversion_rotation_xyzw':[-math.sqrt(.5),0,0,math.sqrt(.5)],'world_boundary':'yaw_root_full_quaternion_internal'}
