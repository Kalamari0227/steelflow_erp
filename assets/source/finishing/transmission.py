"""Explicit same-frame mechanical followers; no server channel or new clock."""
import math
import bpy
from geometry import quat


def author_transmissions(model):
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
