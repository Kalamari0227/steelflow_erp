"""Functional production halls with external loading aprons and crane handoffs."""
from dataclasses import dataclass
from math import pi
from typing import Final
from app.operations.layout import load_factory_layout
from app.operations.world_types import AllowedInteriorEnvelope, Owner, Pose
from app.operations.world_spatial_types import CraneReach, InteriorAccess, SpatialCoverage, SpatialHall, SpatialOpening, SpatialZone
from tools.factory_world.builder import Builder, socket
from tools.factory_world.design import FUNCTIONS, SIZES, STAGE_ORIGINS, Placement


@dataclass(frozen=True, slots=True)
class Machine:
    id: str
    kind: str
    source: str = ''


@dataclass(frozen=True, slots=True)
class HallLine:
    id: str
    zone: str
    origin: tuple[float,float,float]
    machines: tuple[Machine,...]


def lines() -> tuple[HallLine,...]:
    layout=load_factory_layout()
    result=[]
    for stage,origin in STAGE_ORIGINS.items():
        rows=[Machine(e.id,e.kind) for e in layout.equipment if e.stage_id==stage]
        for name,product,anchor,kind in FUNCTIONS:
            if product!=stage:
                continue
            index=next(i for i,m in enumerate(rows) if m.id==anchor)
            rows.insert(index+1,Machine('func-'+name+'-'+product,kind,'src:'+name))
        result.append(HallLine('hall-'+stage,stage,origin,tuple(rows)))
    return tuple(result)


def make_hall(b: Builder, hall: HallLine) -> None:
    x,_,z=hall.origin
    length=sum(SIZES[m.kind][0]+24 for m in hall.machines)+80
    height=max(SIZES[m.kind][1] for m in hall.machines)+12
    center=(x+length/2,0,z)
    hall_placement=Placement(hall.id,'hall',hall.zone,center,(length,height,120))
    b.owner(hall_placement,(socket('entry',(-length/2,2,-20)),socket('exit',(length/2,2,-20))))
    b.halls.append(SpatialHall(id=hall.id,zone_id=hall.zone,footprint_id='fp:'+hall.id))
    interior='interior:'+hall.id
    b.interiors.append(AllowedInteriorEnvelope(id=interior,owner_id=hall.id,
       footprint_id='fp:'+hall.id,pose=Pose(position=(center[0],height/2,z),yaw_rad=0),size_m=(length,height,120)))
    hall_owner=b.owners[-1]
    entry=b.port(hall.id,hall_owner.sockets[0],'roller')
    exit_port=b.port(hall.id,hall_owner.sockets[1],'roller')
    ports=[entry]
    owner_ids=[hall.id]
    cursor=x+40
    for machine in hall.machines:
        size=SIZES[machine.kind]
        px=cursor+size[0]/2
        p=Placement(machine.id,machine.kind,hall.zone,(px,0,z+10),size)
        actual_work=(.3,1.05,0) if machine.id=='CUT-SLAB' else ((0,1.76,0) if machine.kind=='galvanizing' else (0,2,0))
        sockets=(socket('work',actual_work),socket('transfer',(0,2,-30)),socket('dock',(0,2,100)))
        b.owner(p,sockets)
        owner=b.owners[-1]
        b.owners[-1]=owner.model_copy(update={'modes':('roller','road')})
        work=b.port(machine.id,sockets[0],'roller')
        transfer=b.port(machine.id,sockets[1],'roller')
        dock=b.port(machine.id,sockets[2],'road')
        ports.append(transfer)
        crane_id='gantry:'+machine.id
        b.owner(Placement(crane_id,'crane',hall.zone,(px+size[0]/2+8,0,z+60),(3,22,3)),
                (socket('hook',(-size[0]/2-8,20,0)),))
        b.cranes.append(CraneReach(id='reach:'+machine.id,owner_id=crane_id,socket_id='hook',
            pick_port_ids=(work.id,transfer.id,dock.id),drop_port_ids=(work.id,transfer.id,dock.id),
            max_radius_m=150,min_height_m=-25,max_height_m=10))
        owner_ids.extend((machine.id,crane_id))
        if machine.source:
            b.coverage.append(SpatialCoverage(id='coverage:'+machine.id,kind='source_function',
                source_id=machine.source,product_ids=(hall.zone,),owner_id=machine.id,socket_id='work',
                port_ids=(work.id,transfer.id,dock.id),segment_ids=()))
        cursor+=size[0]+24
    ports.append(exit_port)
    segment_ids=[]
    for i,(left,right) in enumerate(zip(ports,ports[1:])):
        segment_ids.extend(b.both(f'line:{hall.id}:{i}',(left.node_id,right.node_id),'roller'))
    opening_ids=[]
    for name,port in (('entry',entry),('exit',exit_port)):
        identity='opening:'+hall.id+':'+name
        opening_ids.append(identity)
        b.openings.append(SpatialOpening(id=identity,hall_id=hall.id,interior_id=interior,
            node_id=port.node_id,width_m=20,height_m=8,mode='roller',profile_ids=('roller',)))
    b.accesses.append(InteriorAccess(id='access:'+hall.id,interior_id=interior,
        opening_ids=tuple(opening_ids),segment_ids=tuple(segment_ids),profile_ids=('roller',),mode='roller'))
    b.zones.append(SpatialZone(id=hall.zone,name=hall.zone.replace('-',' ').title(),owner_ids=tuple(owner_ids)))
    forward=tuple(s for s in segment_ids if s.endswith(':out'))
    reverse=tuple(s for s in reversed(segment_ids) if s.endswith(':back'))
    b.route('loaded:'+hall.id,'roller',forward,'loaded')
    b.route('empty:'+hall.id,'roller',reverse,'empty_return')
    b.route('holding:'+hall.id,'roller',(forward[0],),'holding')
    if hall.zone in ('go', 'ngo'):
        turn_hall_south(b, hall)


def turn_hall_south(b: Builder, hall: HallLine) -> None:
    """Orient the electrical block as complete halls, preserving local sockets."""
    owned = set(b.zones[-1].owner_ids)
    node_ids = {port.node_id for port in b.ports if port.owner_id in owned}
    ox, _, oz = hall.origin

    def point(position: tuple[float, float, float]) -> tuple[float, float, float]:
        x, y, z = position
        return (ox - (z - oz), y, oz + (x - ox))

    def pose(original: Pose) -> Pose:
        return Pose(position=point(original.position), yaw_rad=original.yaw_rad-pi/2)

    b.owners[:] = [owner.model_copy(update={'pose': pose(owner.pose)})
                   if owner.id in owned else owner for owner in b.owners]
    b.footprints[:] = [box.model_copy(update={'pose': pose(box.pose)})
                       if box.owner_id in owned else box for box in b.footprints]
    b.nodes[:] = [node.model_copy(update={'position': point(node.position)})
                  if node.id in node_ids else node for node in b.nodes]
    b.interiors[:] = [interior.model_copy(update={'pose': pose(interior.pose)})
                      if interior.owner_id == hall.id else interior for interior in b.interiors]
    b.segments[:] = [segment.model_copy(update={'points': tuple(point(p) for p in segment.points)})
                     if segment.id.startswith('line:'+hall.id+':') else segment for segment in b.segments]
