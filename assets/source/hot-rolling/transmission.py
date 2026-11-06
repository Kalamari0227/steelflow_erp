"""Explicit same-frame mechanical followers; no server channel or new clock."""
import math
import re
import bpy
from geometry import quat


def author_transmissions(model):
    rotations=[m for m in model.motions if m.mode=='rotation' and m.name!='coolant_valve']
    if rotations:
        driver=rotations[0]
        radius=getattr(model,'drive_radius',.22)
        for name,obj in model.objects.items():
            if re.fullmatch(r'(?:entry_table|exit_table|middle_table|table|feed_roller)_idler_\d+',name):
                pivot=next(n['transform']['position_m'] for n in model.nodes if n['id']==name)
                model.followers.append({'node_id':name,'driver':driver.name,'ratio':radius/.16,'axis':[0,0,-1],'pivot_m':pivot})
        if driver.name=='winding_mandrel':
            for i in range(3):
                name=f'wrapper_roll_{i}'
                pivot=next(n['transform']['position_m'] for n in model.nodes if n['id']==name)
                model.followers.append({'node_id':name,'driver':driver.name,'ratio':-.44/.18,'axis':[0,0,1],'pivot_m':pivot})
    for follower in model.followers:
        driver=next(m for m in model.motions if m.name==follower['driver'])
        action=model.objects[driver.name].animation_data.action
        obj=model.objects[follower['node_id']]
        data=obj.animation_data_create()
        data.action=action
        data.action_slot=action.slots.new(id_type='OBJECT',name=obj.name)
        for frame in range(1,bpy.context.scene.frame_end+1):
            angle=(frame-1)/(bpy.context.scene.frame_end-1)*driver.maximum*follower['ratio']
            obj.rotation_quaternion=quat((*[v*math.sin(angle/2) for v in follower['axis']],math.cos(angle/2)))
            obj.keyframe_insert(data_path='rotation_quaternion',frame=frame)
        for layer in action.layers:
            for strip in layer.strips:
                bag=strip.channelbag(data.action_slot)
                if bag:
                    for curve in bag.fcurves:
                        for key in curve.keyframe_points:
                            key.interpolation='LINEAR'
    bpy.context.scene.frame_set(1)
    bpy.context.view_layer.update()
