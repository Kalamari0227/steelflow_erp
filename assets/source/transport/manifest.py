"""Build strict asset records and source-bound solid-node inventories."""
import hashlib
import json
import math
from pathlib import Path

import bpy
from mathutils import Vector
from geometry import CONVERSION, IDENTITY, PALETTE, Model
from body_shapes import body_boxes


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path,value) -> None:
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,indent=2,ensure_ascii=False)+'\n')


def artifact(root: Path,path: str):
    return {'status':'built','path':path,'sha256':sha(root/path)}


def provenance(root: Path,title: str):
    return {'origin':'self_created','creator':'SteelFlow original procedural authorship','title':title,'license':'project-owned','distribution_permission':'project-local','recipe':artifact(root,'assets/source/transport/recipe.json'),'third_party_inputs':[]}


def row(spec,requirements,coverage):
    bindings=requirements['existing_bindings'] if spec['category']=='equipment' else requirements['planned_bindings']
    binding=next((b for b in bindings if b['variant']==spec['variant']),None)
    if binding is None:
        req=['scope:fleet:'+spec['kind']] if spec['kind']!='receiving-cradle' else ['scope:handling:receiving-cradle']
        placements=['proposed:'+spec['key']];qa=['qa:scope:handling:receiving-cradle'] if spec['kind']=='receiving-cradle' else ['qa:scope:fleet:'+spec['kind']]
    else:
        req=binding['requirement_ids'];placements=binding['placement_ids'];qa=binding['qa_row_ids']
        if spec['category']=='equipment':
            variant=next(v for v in coverage['observed_inventory']['semantic_variants'] if v['id']==spec['variant'])
            req=sorted(set(req+variant['requirement_ids']));qa=sorted(set(qa+variant['qa_row_ids']))
            for place in coverage['observed_inventory']['equipment']:
                if place['id'] in placements:req=sorted(set(req+place['requirement_ids']));qa=sorted(set(qa+place['qa_row_ids']))
    source_ids=set()
    for r in coverage['source_requirements']+coverage['approved_scope_requirements']:
        if r['id'] in req:source_ids.update(r['source_ids'])
    refs=[{'id':s['id'],'uri':s['url'],'note':'Public function concept only; dimensions/clearances/capacity are original synthetic miniature assumptions.'} for s in coverage['sources'] if s['id'] in source_ids and s['url']]
    if req:refs.append({'id':req[0],'uri':'.omo/plans/steelflow-uniform-fidelity-factory.md','note':'Original authored source; no site or load-rating certification. Exact variants pending independent admission where marked.'})
    return {'id':'steelflow:transport:'+spec['key'],'family':'transport','category':spec['category'],'kind':spec['kind'],'variant':spec['variant'],'requirement_ids':req,'qa_row_ids':qa,'placement_ids':placements,'source_refs':refs,'coordinate_system':{'length':'m','up':'+Y','forward':'+X','handedness':'right','angle':'rad'},'root_node_id':'root','lods':[]}


def mesh_box(model: Model,name: str):
    """Enclose actual evaluated mesh vertices in the exact vehicle local frame."""
    obj=model.objects[name]
    points=[CONVERSION@obj.matrix_world@v.co for v in obj.data.vertices]
    lo=[min(p[i] for p in points) for i in range(3)]
    hi=[max(p[i] for p in points) for i in range(3)]
    return {'id':'box:'+name,'mesh_node_ids':[name],'center_m':[(a+b)/2 for a,b in zip(lo,hi)],'size_m':[max(b-a+.00002,.00002) for a,b in zip(lo,hi)],'yaw_rad':0.}


def inventory(model: Model,asset_id: str):
    bpy.context.scene.frame_set(1);bpy.context.view_layer.update()
    solids=sorted(name for name,obj in model.objects.items() if obj.type=='MESH' and name not in model.excluded)
    return {'asset_id':asset_id,'lod':model.lod,'source_body_mesh_nodes':solids,'boxes':body_boxes(model,solids,[mesh_box(model,name) for name in solids]),'excluded_mesh_nodes':[{'node_id':name,'reason':reason,'approval':'PENDING_INDEPENDENT_REVIEW'} for name,reason in sorted(model.excluded.items())],'all_mesh_nodes':sorted(name for name,obj in model.objects.items() if obj.type=='MESH'),'moving_assemblies':[{'part_id':m.name,'axis':m.axis,'min':m.minimum,'max':m.maximum,'frame':'parent-local','classification':'phase geometry must be checked; inventory at authored rest only'} for m in model.motions],'pending_physical_functions':model.pending,'followers':model.followers,'relative_fixed':model.relative_fixed,'coverage_basis':'All actual authored MESH nodes are physical solids except explicitly listed project diagnostic markers. Producer inventory is not an admission certificate.'}


def complete(asset,model: Model,root: Path) -> None:
    asset['nodes']=model.nodes;asset['sockets']=model.sockets
    asset['moving_parts']=[]
    for motion in model.motions:
        pivot=next(n['transform']['position_m'] for n in model.nodes if n['id']==motion.name)
        asset['moving_parts'].append({'id':motion.name,'node_id':motion.name,'function':motion.name,'role':'operational','motion':motion.mode,'axis':list(motion.axis),'pivot_m':pivot,'range':{'min':motion.minimum,'max':motion.maximum,'rest':motion.rest,'unit':'m' if motion.mode=='translation' else 'rad'},'binding':{'type':'clip','clock':'server_sim','phase':motion.phase,'progress_source':'server_phase_progress','pause':'hold','fault':'hold','rest':'range_rest','clip_id':model.key+'.'+motion.name}})
    for follower in model.followers:
        driver=next(m for m in model.motions if m.name==follower['driver'])
        pivot=next(n['transform']['position_m'] for n in model.nodes if n['id']==follower['node_id'])
        lo=(driver.minimum-driver.rest)*follower['ratio'];hi=(driver.maximum-driver.rest)*follower['ratio']
        asset['moving_parts'].append({'id':follower['node_id'],'node_id':follower['node_id'],'function':driver.name,'role':'operational','motion':'rotation','axis':list(follower['axis']),'pivot_m':pivot,'range':{'min':min(lo,hi),'max':max(lo,hi),'rest':0.,'unit':'rad'},'binding':{'type':'mechanical_follower','driver_part_id':driver.name,'ratio':follower['ratio']}})
    asset['fixed_parts']=[{'id':name,'node_id':name,'function':name,'reason':'Actual stationary load-bearing assembly in the authored miniature.','binding':None,**({'fixed_to_part_id':model.relative_fixed[name]} if name in model.relative_fixed else {})} for name in model.fixed]
    asset['cutaway']={'roof_node_ids':[],'interior_node_ids':[],'retained_socket_ids':[]}
    used={slot.name for obj in model.objects.values() if obj.type=='MESH' for slot in obj.data.materials}
    asset['materials']=[{'id':name,'model':'metallic-roughness','base_color':list(color),'metallic':metallic,'roughness':roughness,'textures':[],'provenance':provenance(root,'Original '+name+' transport finish')} for name,(color,metallic,roughness) in PALETTE.items() if name in used]
    asset['textures']=[]
    bpy.context.scene.frame_set(1);bpy.context.view_layer.update()
    boxes=[mesh_box(model,name) for name,obj in model.objects.items() if obj.type=='MESH']
    lo=[min(b['center_m'][i]-b['size_m'][i]/2 for b in boxes) for i in range(3)];hi=[max(b['center_m'][i]+b['size_m'][i]/2 for b in boxes) for i in range(3)]
    asset['collision_proxies']=[{'id':'body','node_id':'root','shape':'box','transform':{'position_m':[(a+b)/2 for a,b in zip(lo,hi)],'rotation_xyzw':list(IDENTITY)},'size_m':[b-a+.04 for a,b in zip(lo,hi)],'purpose':'body','part_id':None,'contact_socket_ids':[s['id'] for s in model.sockets]}]
    for part in asset['moving_parts']:
        moving=model.objects[part['node_id']];meshes=[o for o in [moving,*moving.children_recursive] if o.type=='MESH'];points=[]
        for frame in range(1,74):
            bpy.context.scene.frame_set(frame);bpy.context.view_layer.update()
            points.extend(CONVERSION@obj.matrix_world@v.co for obj in meshes for v in obj.data.vertices)
        lower=[min(p[i] for p in points) for i in range(3)];upper=[max(p[i] for p in points) for i in range(3)]
        asset['collision_proxies'].append({'id':part['id']+'_sweep','node_id':'root','shape':'box','transform':{'position_m':[(a+b)/2 for a,b in zip(lower,upper)],'rotation_xyzw':list(IDENTITY)},'size_m':[b-a+.04 for a,b in zip(lower,upper)],'purpose':'moving_sweep','part_id':part['id'],'contact_socket_ids':[s['id'] for s in model.sockets]})
    bpy.context.scene.frame_set(1);bpy.context.view_layer.update()
    path='assets/source/transport/'+model.key+'.blend'
    bpy.ops.wm.save_as_mainfile(filepath=str(root/path),check_existing=False,compress=True)
    asset['source']={'artifact':artifact(root,path),'provenance':provenance(root,'Original editable '+model.key)}
    asset['export']={'tool':'Blender','version':'4.5.15','tool_artifact':artifact(root,'assets/toolchain.json'),'recipe':artifact(root,'assets/source/transport/build.py'),'settings':{'format':'GLB','y_up':True,'apply_transforms':True,'animations':True},'authoring_axes':{'up':'+Z','forward':'+X'},'conversion_rotation_xyzw':[-math.sqrt(.5),0,0,math.sqrt(.5)],'world_boundary':'yaw_root_full_quaternion_internal'}
