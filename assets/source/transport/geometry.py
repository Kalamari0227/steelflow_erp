"""Original transport meshes in project metres; Blender stores the inverse Y-up frame.

Geometric primitives take independent shape, placement and finish properties because
those values are the actual editing controls retained in the .blend source.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Final, Literal

import bpy
from mathutils import Matrix, Quaternion, Vector

Vec = tuple[float, float, float]
Quat = tuple[float, float, float, float]
IDENTITY: Final[Quat] = (0., 0., 0., 1.)
CONVERSION: Final = Matrix.Rotation(-math.pi / 2, 4, 'X')
INVERSE: Final = CONVERSION.inverted()
PALETTE: Final = {
 'teal': ((.035,.235,.29,1.),.15,.62),
 'blue': ((.09,.19,.27,1.),.2,.58),
 'steel': ((.42,.49,.51,1.),.88,.35),
 'dark': ((.045,.065,.072,1.),.55,.6),
 'rubber': ((.022,.027,.029,1.),0.,.88),
 'safety': ((.94,.48,.065,1.),.22,.45),
 'glass': ((.065,.17,.21,1.),.45,.2),
 'red': ((.75,.06,.025,1.),.05,.5),
 'white': ((.88,.88,.8,1.),.05,.65),
 'axisgreen': ((.04,.5,.15,1.),0.,.6),
 'axisblue': ((.04,.15,.7,1.),0.,.6),
}


def pos(value: Vec) -> Vector:
    return INVERSE.to_3x3() @ Vector(value)


def quat(value: Quat) -> Quaternion:
    return (INVERSE @ Quaternion((value[3],*value[:3])).to_matrix().to_4x4() @ CONVERSION).to_quaternion()


@dataclass(frozen=True, slots=True)
class Motion:
    name: str
    mode: Literal['translation','rotation']
    axis: Vec
    maximum: float
    phase: str = 'work'
    minimum: float = 0.
    rest: float = 0.


class Model:
    """Mutable authored scene with an exhaustive physical-mesh classification."""
    def __init__(self, key: str, lod: int) -> None:
        bpy.ops.object.select_all(action='SELECT')
        bpy.ops.object.delete(use_global=False)
        for blocks in (bpy.data.meshes,bpy.data.materials,bpy.data.actions):
            for block in list(blocks):
                if block.users == 0: blocks.remove(block)
        self.key,self.lod=key,lod
        self.segments=(48,32,24)[lod]
        self.objects: dict[str,bpy.types.Object]={}
        self.nodes=[]
        self.motions: list[Motion]=[]
        self.fixed: list[str]=[]
        self.sockets=[]
        self.excluded: dict[str,str]={}
        self.pending=[]
        self.followers=[]
        self.relative_fixed={}
        self.materials: dict[str,bpy.types.Material]={}
        self.length=18.
        self.ground=-2.
        scene=bpy.context.scene
        scene.unit_settings.system='METRIC';scene.unit_settings.scale_length=1
        scene.render.fps=24;scene.frame_start=1;scene.frame_end=73
        self.node('root',parent=None)
        for name,(color,metallic,roughness) in PALETTE.items():
            mat=bpy.data.materials.new(name);mat.use_nodes=True;mat['semantic_id']=name
            bsdf=mat.node_tree.nodes.get('Principled BSDF')
            bsdf.inputs['Base Color'].default_value=color
            bsdf.inputs['Metallic'].default_value=metallic
            bsdf.inputs['Roughness'].default_value=roughness
            self.materials[name]=mat

    def node(self, name: str, position: Vec=(0.,0.,0.), parent: str|None='root', rotation: Quat=IDENTITY, mesh: bpy.types.Mesh|None=None, finish: str='teal') -> bpy.types.Object:
        obj=bpy.data.objects.new(name,mesh);bpy.context.collection.objects.link(obj)
        if parent is not None:obj.parent=self.objects[parent]
        obj.location=pos(position);obj.rotation_mode='QUATERNION';obj.rotation_quaternion=quat(rotation)
        obj['semantic_id']=name;obj['asset_kind']=self.key
        locator=name if parent is None else self.objects[parent]['locator']+'/'+name
        obj['locator']=locator
        self.nodes.append({'id':name,'parent_id':parent,'locator':locator,'transform':{'position_m':list(position),'rotation_xyzw':list(rotation)}})
        self.objects[name]=obj
        if mesh is not None:mesh.materials.append(self.materials[finish])
        return obj

    def mesh(self,name: str,vertices: list[Vec],faces: list[tuple[int,...]]) -> bpy.types.Mesh:
        mesh=bpy.data.meshes.new(name+'.mesh');mesh.from_pydata([pos(p) for p in vertices],[],faces)
        if mesh.validate():raise RuntimeError('Authored invalid mesh '+name)
        mesh.update();return mesh

    def box(self,name: str,size: Vec,position: Vec=(0.,0.,0.),parent: str='root',finish: str='teal',bevel: float=.025) -> bpy.types.Object:
        x,y,z=(v/2 for v in size)
        vertices=[(-x,-y,-z),(x,-y,-z),(x,y,-z),(-x,y,-z),(-x,-y,z),(x,-y,z),(x,y,z),(-x,y,z)]
        faces=[(0,3,2,1),(4,5,6,7),(0,1,5,4),(3,7,6,2),(0,4,7,3),(1,2,6,5)]
        obj=self.node(name,position,parent,mesh=self.mesh(name,vertices,faces),finish=finish)
        if bevel>0:
            mod=obj.modifiers.new('machined_edges','BEVEL');mod.width=min(bevel,min(size)/5);mod.segments=(3,2,1)[self.lod]
            bpy.context.view_layer.objects.active=obj;obj.select_set(True);bpy.ops.object.modifier_apply(modifier=mod.name);obj.select_set(False)
        return obj

    def cylinder(self,name: str,radius: float,depth: float,position: Vec=(0.,0.,0.),parent: str='root',finish: str='steel',axis: Literal['x','y','z']='z') -> bpy.types.Object:
        vertices=[];n=self.segments
        for d in (-depth/2,depth/2):
            for i in range(n):
                a=math.tau*i/n;u,v=radius*math.cos(a),radius*math.sin(a)
                match axis:
                    case 'x':p=(d,u,v)
                    case 'y':p=(u,d,-v)
                    case 'z':p=(u,v,d)
                vertices.append(p)
        faces=[tuple(range(n-1,-1,-1)),tuple(range(n,2*n))]+[(i,(i+1)%n,(i+1)%n+n,i+n) for i in range(n)]
        return self.node(name,position,parent,mesh=self.mesh(name,vertices,faces),finish=finish)

    def ring(self,name: str,radii: tuple[float,float],depth: float,position: Vec=(0.,0.,0.),parent: str='root',finish: str='steel') -> bpy.types.Object:
        inner,outer=radii;n=self.segments;vertices=[];faces=[]
        for x in (-depth/2,depth/2):
            for radius in (inner,outer):
                for i in range(n):vertices.append((x,radius*math.cos(math.tau*i/n),radius*math.sin(math.tau*i/n)))
        for i in range(n):
            j=(i+1)%n
            faces.extend([(i,j,n+j,n+i),(2*n+i,3*n+i,3*n+j,2*n+j),(n+i,n+j,3*n+j,3*n+i),(i,2*n+i,2*n+j,j)])
        return self.node(name,position,parent,mesh=self.mesh(name,vertices,faces),finish=finish)

    def beam(self,name: str,start: Vec,end: Vec,width: float=.08,parent: str='root',finish: str='steel') -> bpy.types.Object:
        delta=Vector(end)-Vector(start);center=(Vector(start)+Vector(end))/2
        q=Vector((0,1,0)).rotation_difference(delta.normalized())
        obj=self.box(name,(width,delta.length,width),tuple(center),parent,finish,bevel=.008)
        values=[q.x,q.y,q.z,q.w]
        norm=math.sqrt(sum(v*v for v in values));values=[v/norm for v in values]
        obj.rotation_quaternion=quat(tuple(values))
        self.nodes[-1]['transform']['rotation_xyzw']=values
        return obj

    def socket(self,name: str,node: str,position: Vec=(0.,0.,0.),role: str|None=None,forms: tuple[str,...]=('COIL','PACKAGED'),capacity: int=40000) -> None:
        self.sockets.append({'id':name,'node_id':node,'role':role or name,'transform':{'position_m':list(position),'rotation_xyzw':list(IDENTITY)},'normal':[0,1,0],'forms':list(forms),'max_load_kg':capacity})

    def motion(self,spec: Motion) -> None:
        self.motions.append(spec);obj=self.objects[spec.name];base=obj.location.copy();rotation=obj.rotation_quaternion.copy()
        for frame in range(1,74):
            progress=(frame-1)/72
            match spec.mode:
                case 'translation':
                    scalar=spec.maximum*(1-abs(2*progress-1))
                    obj.location=base+pos(spec.axis)*scalar
                    obj.keyframe_insert(data_path='location',frame=frame)
                case 'rotation':
                    scalar=(spec.minimum+(spec.maximum-spec.minimum)*progress)-spec.rest
                    obj.rotation_quaternion=quat(tuple(v*math.sin(scalar/2) for v in spec.axis)+(math.cos(scalar/2),))@rotation
                    obj.keyframe_insert(data_path='rotation_quaternion',frame=frame)
        action=obj.animation_data.action;action.name=self.key+'.'+spec.name
        for slot in action.slots:
            for layer in action.layers:
                for strip in layer.strips:
                    bag=strip.channelbag(slot)
                    if bag:
                        for curve in bag.fcurves:
                            for point in curve.keyframe_points:point.interpolation='LINEAR'
        bpy.context.scene.frame_set(1)

    def markers(self) -> None:
        self.box('axis_origin',(.03,.03,.03),finish='dark',bevel=0)
        self.node('axis_front',(1.,0.,0.),mesh=self.mesh('axis_front',[(-.08,-.025,-.025),(-.08,.025,-.025),(-.08,.025,.025),(-.08,-.025,.025),(.14,0.,0.)],[(0,3,2,1),(0,1,4),(1,2,4),(2,3,4),(3,0,4)]),finish='red')
        self.box('axis_up',(.025,.12,.025),(0.,1.,0.),finish='axisgreen',bevel=0)
        self.box('axis_side',(.025,.025,.1),(0.,0.,-1.),finish='axisblue',bevel=0)
        for name in ('axis_origin','axis_front','axis_up','axis_side'):
            self.excluded[name]='Project coordinate diagnostic marker only; no physical equipment role; requires independent classification approval.'
