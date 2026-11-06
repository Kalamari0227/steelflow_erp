"""Receiving, inspection, storage and customer surfaces independent of production."""
from app.operations.world_types import Pose, Owner
from app.operations.world_spatial_types import CraneReach, SpatialCoverage, SpatialZone
from tools.factory_world.builder import Builder, socket
from tools.factory_world.design import Placement
from tools.factory_world.production import HallLine, Machine, make_hall

RECEIPTS = ('ORE','SCRAP','TI_INGOT','SLAB','BLOOM','BILLET','HR_COIL','CR_COIL',
            'STS_HR_COIL','TI_HR_COIL','COAL','LIMESTONE','NICKEL_ORE')


def surface(b: Builder, placement: Placement) -> str:
    """Dock center stays outside equipment mass; named socket is actual custody point."""
    b.owner(placement,(socket('work',(0,2,-placement.size[2]/2-20)),))
    return b.port(placement.id,b.owners[-1].sockets[0],placement.mode).id


def make_logistics(b: Builder) -> None:
    facilities=(
      ('final-inspection','FINAL-INSPECTION','inspection',(100,0,3410)),
      ('packaging','PACKAGING','packaging',(600,0,3410)),
      ('warehouse','WAREHOUSE','stock',(1150,0,3410)),
      ('port','PORT','port',(2350,0,3410)),
      ('ship','SHIP-TERMINAL','stock',(2350,0,3750)),
      ('customer','CUSTOMER','delivery',(6200,0,3410)),
      ('ore-source','ORE-SOURCE','stock',(100,0,-1100)),
      ('scrap-source','SCRAP-SOURCE','stock',(650,0,-1100)),
      ('ti-source','TI-SOURCE','stock',(1200,0,-1100)),
    )
    for name,identity,kind,origin in facilities:
        zone='sources' if name.endswith('source') else 'logistics'
        make_hall(b,HallLine('facility-'+name,zone,origin,(Machine(identity,kind),)))
    # Merge the two genuinely shared zones without duplicate hall placements.
    merged={}
    for zone in b.zones:
        merged.setdefault(zone.id,[]).extend(zone.owner_ids)
    b.zones[:]=[SpatialZone(id=key,name=key.replace('-',' ').title(),owner_ids=tuple(value))
                 for key,value in merged.items()]
    ids=[]
    for i,form in enumerate(RECEIPTS):
        identity='receipt:'+form
        surface(b,Placement(identity,'receiving','receiving',(i*150-100,0,-1450),(65,12,40),'road'))
        ids.append(identity)
    for i,name in enumerate(('arrival-gate','weighbridge','receiving-inspection','unload','quarantine','reinspect')):
        identity='receiving:'+name
        surface(b,Placement(identity,name,'receiving',(i*230-100,0,-1700),(60,12,35),'road'))
        ids.append(identity)
    for name,x in (('unloader',2350),('stacker',2100)):
        identity='raw:'+name
        surface(b,Placement(identity,name,'receiving',(x,0,-1450),(70,35,25),'road'))
        ids.append(identity)
    b.zones.append(SpatialZone(id='receiving',name='North receiving and purchased stock',owner_ids=tuple(ids)))
    for zone,items,z in (
      ('quality',('inspect','quarantine','reinspect','package','store','custody'),3700),
      ('road-dispatch',('dispatch','wait','load','secure','weigh','gate-out','customer-unload','customer-accept'),4000)):
        zone_ids=[]
        for i,name in enumerate(items):
            identity=zone+':'+name
            surface(b,Placement(identity,name,zone,(i*230-100,0,z),(65,12,35),'road'))
            zone_ids.append(identity)
        b.zones.append(SpatialZone(id=zone,name=zone.replace('-',' ').title(),owner_ids=tuple(zone_ids)))


def make_sea_ports(b: Builder) -> None:
    for name,z in (('raw',-1100),('product',3550)):
        quay='quay:'+name
        quay_port=surface(b,Placement(quay,'berth','berths',(2850,0,z+145),(100,20,30),'road'))
        # Vessel is a mobile owner; only the dock and crane are static forbidden masses.
        vessel='SHIP' if name=='product' else 'RAW-SHIP'
        b.owner(Placement(vessel,'ship','berths',(3250,0,z),(150,25,30),'sea'),(socket('hold',(0,15,0)),))
        b.owners[-1]=b.owners[-1].model_copy(update={'kind':'ship'})
        hold=b.port(vessel,b.owners[-1].sockets[0],'sea')
        crane='port-crane:'+name
        b.owner(Placement(crane,'crane','berths',(3000,0,z+70),(10,45,10),'road'),(socket('hook',(0,35,-70)),))
        b.cranes.append(CraneReach(id='reach:'+crane,owner_id=crane,socket_id='hook',
           pick_port_ids=(quay_port,hold.id),drop_port_ids=(quay_port,hold.id),max_radius_m=280,
           min_height_m=-40,max_height_m=5))
        b.zones.append(SpatialZone(id='berth-'+name,name=name.title()+' berth',owner_ids=(quay,vessel,crane)))
