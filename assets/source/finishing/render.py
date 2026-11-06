"""Four views of actual source geometry under one shared miniature studio."""
import bpy
from mathutils import Vector


def render(model,path):
    scene=bpy.context.scene
    target=Vector((0,0,2.0))
    bpy.ops.object.camera_add()
    camera=bpy.context.object;camera.name='proof_camera'
    camera.data.type='ORTHO';scene.camera=camera
    scene.world.color=(.7,.68,.61)
    for name,power,location,size in [('key',2200,(1,-5,12),8),('fill',1500,(-6,-1,7),7),('rim',1800,(5,8,9),6)]:
        bpy.ops.object.light_add(type='AREA',location=location)
        light=bpy.context.object;light.name='proof_'+name;light.data.energy=power;light.data.size=size
        light.rotation_euler=(target-light.location).to_track_quat('-Z','Y').to_euler()
    bpy.ops.mesh.primitive_plane_add(size=200)
    floor=bpy.context.object;floor.name='proof_floor';floor.location.z=-.03
    material=bpy.data.materials.new('proof_warm_background');material.diffuse_color=(.80,.76,.66,1);floor.data.materials.append(material)
    scene.render.engine='CYCLES';scene.cycles.samples=16;scene.cycles.use_denoising=True
    scene.render.resolution_x=1440;scene.render.resolution_y=1080;scene.render.resolution_percentage=100
    scene.view_settings.view_transform='AgX';scene.render.image_settings.file_format='PNG'
    for name,location in [('front',(13,-17,12)),('side',(0,-20,9)),('rear',(-13,17,12)),('close',(5,-7,5.5))]:
        camera.location=location;camera.rotation_euler=(target-camera.location).to_track_quat('-Z','Y').to_euler()
        camera.data.ortho_scale=5.0 if name=='close' else max(9.0,model.length*1.2)
        scene.render.filepath=str(path.with_name(path.stem+'-'+name+'.png'))
        bpy.ops.render.render(write_still=True)
    for obj in list(bpy.data.objects):
        if obj.name.startswith('proof_'):bpy.data.objects.remove(obj,do_unlink=True)
