"""Owned finishing geometry primitives, expressed in project metres.

These modelling primitives intentionally accept dimensions, frame, parent and finish:
those independent geometric properties mirror Blender's mesh authoring operations.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path

import bpy
from mathutils import Matrix, Quaternion, Vector

CONVERSION = Matrix.Rotation(-math.pi / 2, 4, 'X')
INVERSE = CONVERSION.inverted()
IDENTITY = (0.0, 0.0, 0.0, 1.0)
PALETTE = {
    'teal': ((.035, .235, .29, 1), .12, .72),
    'blue': ((.09, .19, .27, 1), .12, .72),
    'steel': ((.39, .47, .50, 1), .90, .38),
    'dark': ((.055, .079, .086, 1), .72, .55),
    'safety': ((.94, .48, .065, 1), .24, .39),
    'ceramic': ((.55, .48, .36, 1), .02, .85),
    'red': ((.73, .075, .04, 1), .15, .52),
    'green': ((.07, .50, .22, 1), .12, .44),
    'axisblue': ((.045, .17, .75, 1), .18, .42),
}


def pos(value):
    return INVERSE.to_3x3() @ Vector(value)


def quat(value):
    return (INVERSE @ Quaternion((value[3], *value[:3])).to_matrix().to_4x4() @ CONVERSION).to_quaternion()


@dataclass(frozen=True, slots=True)
class Motion:
    name: str
    mode: str
    axis: tuple[float, float, float]
    maximum: float
    phase: str = 'work'
    minimum: float = 0.0


class Model:
    """A mutable, single editable equipment model; no imported geometry."""
    def __init__(self, key: str, level: int):
        bpy.ops.object.select_all(action='SELECT')
        bpy.ops.object.delete(use_global=False)
        for blocks in (bpy.data.meshes, bpy.data.materials, bpy.data.actions):
            for block in list(blocks):
                if block.users == 0:
                    blocks.remove(block)
        self.key, self.level = key, level
        self.segments = (48, 32, 16)[level]
        self.nodes, self.objects, self.materials, self.motions = [], {}, {}, []
        self.roller_specs=[]
        self.feed_spec=None
        self.roofs, self.interior = [], []
        self.width, self.length = 3.0, 10.0
        bpy.context.scene.unit_settings.system = 'METRIC'
        bpy.context.scene.unit_settings.scale_length = 1
        bpy.context.scene.render.fps = 24
        bpy.context.scene.frame_start, bpy.context.scene.frame_end = 1, 73
        self.node('root', None)
        for name, (color, metallic, roughness) in PALETTE.items():
            material = bpy.data.materials.new(name)
            material.use_nodes = True
            material['semantic_id'] = name
            bsdf = material.node_tree.nodes.get('Principled BSDF')
            bsdf.inputs['Base Color'].default_value = color
            bsdf.inputs['Metallic'].default_value = metallic
            bsdf.inputs['Roughness'].default_value = roughness
            self.materials[name] = material

    def node(self, name, parent='root', position=(0, 0, 0), rotation=IDENTITY, mesh=None, finish='teal'):
        result = bpy.data.objects.new(name, mesh)
        bpy.context.collection.objects.link(result)
        if parent:
            result.parent = self.objects[parent]
        result.location = pos(position)
        result.rotation_mode = 'QUATERNION'
        result.rotation_quaternion = quat(rotation)
        result['semantic_id'] = name
        result['asset_kind'] = self.key
        locator = name if parent is None else self.objects[parent]['locator'] + '/' + name
        result['locator'] = locator
        self.nodes.append({'id': name, 'parent_id': parent, 'locator': locator, 'transform': {'position_m': list(position), 'rotation_xyzw': list(rotation)}})
        self.objects[name] = result
        if mesh:
            mesh.materials.append(self.materials[finish])
        return result

    def mesh(self, name, vertices, faces):
        result = bpy.data.meshes.new(name + '.mesh')
        result.from_pydata([pos(v) for v in vertices], [], faces)
        result.update()
        return result

    def box(self, name, size, position=(0, 0, 0), parent='root', finish='teal', bevel=.035):
        x, y, z = (v / 2 for v in size)
        vertices = [(-x,-y,-z),(x,-y,-z),(x,y,-z),(-x,y,-z),(-x,-y,z),(x,-y,z),(x,y,z),(-x,y,z)]
        faces = [(0,3,2,1),(4,5,6,7),(0,1,5,4),(3,7,6,2),(0,4,7,3),(1,2,6,5)]
        obj = self.node(name, parent, position, mesh=self.mesh(name, vertices, faces), finish=finish)
        if bevel > 0:
            mod = obj.modifiers.new('machined_edges', 'BEVEL')
            mod.width, mod.segments = min(bevel, min(size) / 4), (3, 2, 1)[self.level]
            bpy.context.view_layer.objects.active = obj
            obj.select_set(True)
            bpy.ops.object.modifier_apply(modifier=mod.name)
            obj.select_set(False)
        return obj

    def cylinder(self, name, radius, depth, position=(0, 0, 0), parent='root', finish='steel', axis='z'):
        n = self.segments
        vertices = [(radius*math.cos(i*math.tau/n+math.pi/2-math.pi/n), radius*math.sin(i*math.tau/n+math.pi/2-math.pi/n), z) for z in (-depth/2, depth/2) for i in range(n)]
        transform = {'z': lambda p:p, 'x':lambda p:(p[2],p[0],p[1]), 'y':lambda p:(p[0],p[2],-p[1])}[axis]
        vertices = [transform(v) for v in vertices]
        faces = [tuple(range(n-1,-1,-1)), tuple(range(n,2*n))] + [(i,(i+1)%n,(i+1)%n+n,i+n) for i in range(n)]
        obj = self.node(name, parent, position, mesh=self.mesh(name, vertices, faces), finish=finish)
        for polygon in obj.data.polygons[2:]:
            polygon.use_smooth = True
        return obj

    def ring(self, name, radii, depth, position=(0,0,0), parent='root', finish='steel', axis='z'):
        inner,outer=radii
        n=self.segments
        vertices=[(radius*math.cos(i*math.tau/n),radius*math.sin(i*math.tau/n),z) for z in (-depth/2,depth/2) for radius in (inner,outer) for i in range(n)]
        transform={'z':lambda p:p,'x':lambda p:(p[2],p[0],p[1]),'y':lambda p:(p[0],p[2],-p[1])}[axis]
        vertices=[transform(v) for v in vertices]
        faces=[]
        for i in range(n):
            j=(i+1)%n
            faces.extend([(i,j,n+j,n+i),(2*n+i,3*n+i,3*n+j,2*n+j),(n+i,n+j,3*n+j,3*n+i),(i,2*n+i,2*n+j,j)])
        return self.node(name,parent,position,mesh=self.mesh(name,vertices,faces),finish=finish)

    def tube(self, name, points, radius=.045, parent='root', finish='steel'):
        vertices, faces = [], []
        for i, point in enumerate(points):
            direction = Vector(points[min(i+1,len(points)-1)])-Vector(points[max(i-1,0)])
            direction.normalize()
            side = direction.cross(Vector((0,1,0)))
            if side.length < .01:
                side = direction.cross(Vector((1,0,0)))
            side.normalize()
            up = direction.cross(side).normalized()
            for j in range(self.segments):
                v = Vector(point) + radius*(math.cos(j*math.tau/self.segments+math.pi/self.segments)*side + math.sin(j*math.tau/self.segments+math.pi/self.segments)*up)
                vertices.append(v)
        for i in range(len(points)-1):
            for j in range(self.segments):
                a = i*self.segments+j
                b = i*self.segments+(j+1)%self.segments
                faces.append((a,b,b+self.segments,a+self.segments))
        faces += [tuple(range(self.segments-1,-1,-1)), tuple(range((len(points)-1)*self.segments,len(points)*self.segments))]
        return self.node(name,parent,mesh=self.mesh(name,vertices,faces),finish=finish)

    def motion(self, spec: Motion):
        self.motions.append(spec)
        obj = self.objects[spec.name]
        rest = obj.location.copy()
        rest_rotation=obj.rotation_quaternion.copy()
        for frame in range(1,bpy.context.scene.frame_end+1):
            progress = (frame-1)/(bpy.context.scene.frame_end-1)
            if spec.mode == 'translation':
                value=(1-abs(2*progress-1))*(spec.minimum if spec.minimum < 0 else spec.maximum)
                obj.location = rest + pos(spec.axis) * value
                obj.keyframe_insert(data_path='location', frame=frame)
            else:
                angle = progress * spec.maximum
                obj.rotation_quaternion = quat((*[v*math.sin(angle/2) for v in spec.axis],math.cos(angle/2))) @ rest_rotation
                obj.keyframe_insert(data_path='rotation_quaternion',frame=frame)
        action = obj.animation_data.action
        action.name = self.key + '.' + spec.name
        for slot in action.slots:
            for layer in action.layers:
                for strip in layer.strips:
                    bag = strip.channelbag(slot)
                    if bag:
                        for curve in bag.fcurves:
                            for point in curve.keyframe_points:
                                point.interpolation = 'LINEAR'
        bpy.context.scene.frame_set(1)
