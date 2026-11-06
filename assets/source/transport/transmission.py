"""Finite source clips for independently pivoted wheels and coupled mechanisms."""
import math
import bpy
from geometry import Model,quat


def author_transmissions(model: Model) -> None:
    """Follower clips share the canonical action and clock; no independent timer."""
    for follower in model.followers:
        driver=next(m for m in model.motions if m.name==follower['driver'])
        action=model.objects[driver.name].animation_data.action
        obj=model.objects[follower['node_id']];rest=obj.rotation_quaternion.copy()
        animation=obj.animation_data_create();animation.action=action
        animation.action_slot=action.slots.new(id_type='OBJECT',name=obj.name)
        for frame in range(1,bpy.context.scene.frame_end+1):
            scalar=(frame-1)/(bpy.context.scene.frame_end-1)*(driver.maximum-driver.minimum)
            angle=scalar*follower['ratio'];axis=follower['axis']
            obj.rotation_quaternion=quat(tuple(v*math.sin(angle/2) for v in axis)+(math.cos(angle/2),))@rest
            obj.keyframe_insert(data_path='rotation_quaternion',frame=frame)
        for layer in action.layers:
            for strip in layer.strips:
                bag=strip.channelbag(animation.action_slot)
                if bag:
                    for curve in bag.fcurves:
                        for key in curve.keyframe_points:key.interpolation='LINEAR'
    bpy.context.scene.frame_set(1);bpy.context.view_layer.update()
