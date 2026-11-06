"""Separate outside roads, rail service corridors, approaches and actual fleet bays."""
from collections import defaultdict, deque
from dataclasses import dataclass
from math import dist
from app.operations.world_types import Slot, Footprint, Pose
from app.operations.world_spatial_types import (CraneReach,RailBlock,SpatialBerth,SpatialParking,SpatialStop,SpatialZone)
from tools.factory_world.builder import Builder, socket
from tools.factory_world.design import FLEET, Placement
from tools.factory_world.logistics import surface
from tools.factory_world.road_topology import make_roads


def make_parking(b: Builder) -> None:
    road_index=rail_index=0
    ids=[]
    for kind,count in FLEET.items():
        profile=next(p for p in b.profiles if p.id==kind)
        for i in range(count):
            match profile.mode:
                case 'road':
                    point=((road_index%18)*40,2,-1900-(road_index//18)*90); road_index+=1
                case 'rail':
                    point=(rail_index*110,3,4300); rail_index+=1
                case 'hot_metal': point=(i*80,4,-550)
                case 'ladle': point=(i*80,4,-350)
                case 'sea': point=(4100+(i%2)*500,15,-1100 if i<2 else 3550)
                case _: raise AssertionError(profile.mode)
            identity=f'bay:{kind}:{i+1:02}'
            # Concrete support slab occupies -0.2..0m; deck socket is above its support plane.
            b.owner(Placement(identity,'parking','fleet',(point[0],-.2,point[2]),(profile.size_m[0]+4,.2,profile.size_m[2]+4),profile.mode),
                    (socket('park',(0,point[1]+.2,0)),))
            port=b.port(identity,b.owners[-1].sockets[0],profile.mode)
            slot=Slot(id='v2:s:'+identity,owner_id=identity,socket_id='park',node_id=port.node_id,capacity_kg=500000)
            b.slots.append(slot)
            b.parking.append(SpatialParking(id='parking:'+identity,slot_id=slot.id,profile_id=profile.id,capacity_positions=1))
            b.stops.append(SpatialStop(id='stop:'+identity,node_id=port.node_id,kind='staging',profile_ids=(profile.id,)))
            ids.append(identity)
    b.zones.append(SpatialZone(id='fleet',name='Fleet parking and safe staging',owner_ids=tuple(ids)))


def rail_transfer(b: Builder, mode: str, point: tuple[float,float,float]) -> str:
    identity='transfer:'+mode
    # Deck outside rail swept envelope; socket at actual train/load centerline.
    b.owner(Placement(identity,'transfer','rail',(point[0],0,point[2]+(100 if mode=='rail' else 50)),(40,16,25),mode),
            (socket('rail',(0,point[1],-(100 if mode=='rail' else 50))),))
    port=b.port(identity,b.owners[-1].sockets[0],mode)
    nearby={'rail':'WAREHOUSE','hot_metal':'BF-A','ladle':'LF-A'}[mode]
    work=next(p for p in b.ports if p.owner_id==nearby and p.socket_id=='work')
    target=next(n for n in b.nodes if n.id==work.node_id).position
    crane='transfer-crane:'+mode
    center=((point[0]+target[0])/2,30,(point[2]+target[2])/2)
    b.owner(Placement(crane,'crane','rail',(center[0]+70,0,point[2]-60),(3,35,3),'road'),(socket('hook',(-70,30,center[2]-point[2]+60)),))
    b.cranes.append(CraneReach(id='reach:'+crane,owner_id=crane,socket_id='hook',
        pick_port_ids=(port.id,work.id),drop_port_ids=(port.id,work.id),
        max_radius_m=dist(point,target)/2+20,min_height_m=-40,max_height_m=10))
    return port.id


def make_other_networks(b: Builder) -> None:
    for mode,z,y,length in (('rail',4300,3,85),('hot_metal',-550,4,34),('ladle',-350,4,20)):
        rail_transfer(b,mode,(2200 if mode=='rail' else 450,y,z))
        if mode in ('hot_metal','ladle'):
            station_owners=('BOF-A',) if mode=='hot_metal' else ('BOF-A','CAST-SLAB','CAST-BLOOM','CAST-BILLET')
            for owner_id in station_owners: add_metal_station(b,(mode,z,y),owner_id)
        nodes=sorted((n for n in b.nodes if n.modes==(mode,)),key=lambda n:n.position[0])
        tail=destination_port(b,(mode,5000,y,z)).node_id if mode=='rail' else b.node(mode+':turnback',(2300,y,z),mode)
        lead=b.node(mode+':buffer-lead',(-150,y,z),mode)
        ids=[lead]+[n.id for n in nodes]+[tail]
        if mode=='rail': ids.append(b.node('rail:destination-buffer',(5300,y,z),mode))
        segments=[]
        for i,pair in enumerate(zip(ids,ids[1:])): segments.extend(b.both(f'{mode}:{i}',pair,mode))
        block='block:'+mode
        b.blocks.append(RailBlock(id=block,segment_ids=tuple(segments),usable_length_m=5000 if mode=='rail' else 2300,
                                  clearance_m=5,reverse_allowed=True))
        b.policies[:]=[p.model_copy(update={'rail_block_ids':(block,)}) if p.segment_id in segments else p for p in b.policies]
    for name,z in (('raw',-1100),('product',3550)):
        nodes=sorted((n for n in b.nodes if n.modes==('sea',) and n.position[2]==z),key=lambda n:n.position[0])
        hub=b.node('sea:coast:'+name,(5500,15,z),'sea')
        destination=destination_port(b,('sea',6000,15,z)).node_id
        ids=[n.id for n in nodes]+[hub,destination]
        segments=[]
        for i,pair in enumerate(zip(ids,ids[1:])): segments.extend(b.both(f'sea:{name}:{i}',pair,'sea'))
        berth='berth:'+name
        port=next(p for p in b.ports if p.owner_id==('SHIP' if name=='product' else 'RAW-SHIP'))
        b.berths.append(SpatialBerth(id=berth,segment_ids=tuple(segments),port_ids=(port.id,),usable_length_m=300,depth_m=30))
        b.policies[:]=[p.model_copy(update={'berth_ids':(berth,)}) if p.segment_id in segments else p for p in b.policies]
    channel=b.both('sea:coastal-channel',('v2:n:sea:coast:raw','v2:n:sea:coast:product'),'sea')
    b.berths[:]=[berth.model_copy(update={'segment_ids':berth.segment_ids+channel}) for berth in b.berths]
    b.policies[:]=[p.model_copy(update={'berth_ids':tuple(berth.id for berth in b.berths)})
        if p.segment_id in channel else p for p in b.policies]


def shortest(b: Builder, endpoints: tuple[str,str], profile: str) -> tuple[str,...]:
    policies={p.segment_id:p for p in b.policies}
    adjacent=defaultdict(list)
    for segment in b.segments:
        if profile in policies[segment.id].profile_ids: adjacent[segment.from_node_id].append(segment)
    queue=deque([(endpoints[0],())]);visited={endpoints[0]}
    while queue:
        node,path=queue.popleft()
        if node==endpoints[1]: return path
        for segment in adjacent[node]:
            if segment.to_node_id not in visited:
                visited.add(segment.to_node_id);queue.append((segment.to_node_id,path+(segment.id,)))
    raise AssertionError(('unreachable',endpoints,profile))


def access_routes(b: Builder) -> None:
    slots={s.id:s for s in b.slots}
    for parking in b.parking:
        start=slots[parking.slot_id].node_id
        profile=next(p for p in b.profiles if p.id==parking.profile_id)
        target=next(p.node_id for p in b.ports if p.owner_id=={
            'road':'WAREHOUSE','rail':'transfer:rail','hot_metal':'transfer:hot_metal',
            'ladle':'transfer:ladle','sea':'RAW-SHIP' if 'ship:01' in parking.id or 'ship:02' in parking.id else 'SHIP'}[profile.mode]
            and profile.mode in p.modes)
        forward=shortest(b,(start,target),profile.id)
        back=shortest(b,(target,start),profile.id)
        b.route('loaded:'+parking.id,profile.id,forward,'loaded')
        b.route('empty:'+parking.id,profile.id,back,'empty_return')
        b.route('holding:'+parking.id,profile.id,(back[-1],),'holding')


def add_metal_station(b: Builder, corridor: tuple[str,float,float], owner_id: str) -> None:
    mode,z,y=corridor
    work=next(p for p in b.ports if p.owner_id==owner_id and p.socket_id=='work')
    target=next(n for n in b.nodes if n.id==work.node_id).position
    identity='station:'+mode+':'+owner_id
    point=(target[0],y,z)
    b.owner(Placement(identity,'transfer','rail',(point[0],0,z-60),(10,16,10),mode),
            (socket('load',(0,y,60)),))
    port=b.port(identity,b.owners[-1].sockets[0],mode)
    crane='station-crane:'+mode+':'+owner_id
    center=(target[0],30,(z+target[2])/2)
    b.owner(Placement(crane,'crane','rail',(target[0]+65,0,z-60),(3,35,3),mode),
            (socket('hook',(-65,30,center[2]-(z-60))),))
    b.cranes.append(CraneReach(id='reach:'+crane,owner_id=crane,socket_id='hook',
        pick_port_ids=(work.id,port.id),drop_port_ids=(work.id,port.id),
        max_radius_m=abs(z-target[2])/2+5,min_height_m=-40,max_height_m=10))


def destination_port(b: Builder, route: tuple[str,float,float,float]):
    mode,x,y,z=route
    identity=f'destination:{mode}:{int(z)}'
    b.owner(Placement(identity,'customer','outer-customer',(x+200,0,z+120),(100,20,40),mode),
            (socket('unload',(-200,y,-120)),socket('road',(0,2,60))))
    b.owners[-1]=b.owners[-1].model_copy(update={'kind':'customer','modes':(mode,'road')})
    unload=b.port(identity,b.owners[-1].sockets[0],mode)
    road=b.port(identity,b.owners[-1].sockets[1],'road')
    crane='customer-crane:'+identity
    b.owner(Placement(crane,'crane','outer-customer',(x+100,0,z+90),(4,35,4),'road'),
            (socket('hook',(0,30,0)),))
    b.cranes.append(CraneReach(id='reach:'+crane,owner_id=crane,socket_id='hook',
        pick_port_ids=(unload.id,road.id),drop_port_ids=(unload.id,road.id),
        max_radius_m=220,min_height_m=-40,max_height_m=10))
    return unload
