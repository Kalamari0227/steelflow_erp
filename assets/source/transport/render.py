"""Source geometry views in the approved warm miniature studio."""
import bpy
from mathutils import Vector
from geometry import Model


def render(model: Model,path) -> None:
    scene=bpy.context.scene;target=Vector((0.,0.,2.7))
    bpy.ops.object.camera_add();camera=bpy.context.object;camera.name='proof_camera';camera.data.type='ORTHO';scene.camera=camera
    scene.world.color=(.7,.68,.61)
    for name,power,location,size in [('key',2800,(5,-8,15),10),('fill',1800,(-8,-2,9),8),('rim',2000,(6,10,13),8)]:
        bpy.ops.object.light_add(type='AREA',location=location);light=bpy.context.object;light.name='proof_'+name;light.data.energy=power;light.data.size=size;light.rotation_euler=(target-light.location).to_track_quat('-Z','Y').to_euler()
    bpy.ops.mesh.primitive_plane_add(size=300);floor=bpy.context.object;floor.name='proof_floor';floor.location.z=-.03
    mat=bpy.data.materials.new('proof_warm_ground');mat.diffuse_color=(.80,.76,.66,1);floor.data.materials.append(mat)
    scene.render.engine='CYCLES';scene.cycles.samples=16;scene.cycles.use_denoising=True
    scene.render.resolution_x=1280;scene.render.resolution_y=960;scene.render.resolution_percentage=100
    scene.view_settings.view_transform='AgX';scene.render.image_settings.file_format='PNG'
    for name,location in [('front',(19,-23,16)),('side',(0,-26,12)),('rear',(-19,23,16)),('close',(7,-10,8))]:
        camera.location=location;camera.rotation_euler=(target-camera.location).to_track_quat('-Z','Y').to_euler();camera.data.ortho_scale=6. if name=='close' else max(4.,model.length*1.2)
        scene.render.filepath=str(path.with_name(path.stem+'-'+name+'.png'));bpy.ops.render.render(write_still=True)
    for obj in list(bpy.data.objects):
        if obj.name.startswith('proof_'):bpy.data.objects.remove(obj,do_unlink=True)
