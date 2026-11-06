"""Elevated raw-yard conveyor with actual terminal/crane contact ports."""
from math import dist
from app.operations.world_spatial_types import CraneReach,SpatialZone
from tools.factory_world.builder import Builder,socket
from tools.factory_world.design import Placement


def make_raw_conveyor(b: Builder) -> None:
    points=((200,12,-950),(-300,12,-950),(-300,12,-750),(150,12,-750),(150,12,-520))
    nodes=[];ports=[]
    for i,point in enumerate(points):
        identity=f'raw-belt:{i}'
        b.owner(Placement(identity,'conveyor','raw-yard',(point[0],0,point[2]+20),(4,10,4),'conveyor'),
            (socket('belt',(0,12,-20)),))
        port=b.port(identity,b.owners[-1].sockets[0],'conveyor')
        ports.append(port);nodes.append(port.node_id)
    segments=[]
    for i,pair in enumerate(zip(nodes,nodes[1:])): segments.extend(b.both(f'conveyor:{i}',pair,'conveyor'))
    for name,port,owner_id in (('yard',ports[0],'ORE-SOURCE'),('feed',ports[-1],'CHARGE-A')):
        other=next(p for p in b.ports if p.owner_id==owner_id and p.socket_id=='work')
        a=next(n for n in b.nodes if n.id==port.node_id).position
        c=next(n for n in b.nodes if n.id==other.node_id).position
        center=((a[0]+c[0])/2,20,(a[2]+c[2])/2)
        identity='raw-'+name+'-reclaimer'
        b.owner(Placement(identity,'reclaimer','raw-yard',(center[0]+60,0,center[2]),(6,25,6),'conveyor'),
                (socket('hook',(-60,20,0)),))
        b.cranes.append(CraneReach(id='reach:'+identity,owner_id=identity,socket_id='hook',
            pick_port_ids=(port.id,other.id),drop_port_ids=(port.id,other.id),max_radius_m=dist(a,c)/2+10,
            min_height_m=-25,max_height_m=5))
    forward=tuple(s for s in segments if s.endswith(':out'))
    back=tuple(s for s in reversed(segments) if s.endswith(':back'))
    b.route('raw:loaded','conveyor',forward,'loaded')
    b.route('raw:empty','conveyor',back,'empty_return')
    b.route('raw:holding','conveyor',(forward[0],),'holding')
    b.zones.append(SpatialZone(id='raw-yard',name='Raw stockyard and elevated conveyor',
        owner_ids=tuple(p.owner_id for p in ports)+('raw-yard-reclaimer','raw-feed-reclaimer')))
