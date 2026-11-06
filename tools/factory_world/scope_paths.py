"""Named real receiving/dispatch/customer paths for independent approved-scope IDs."""
from pathlib import Path
from tools.qa.coverage import parse_registry
from app.operations.world_spatial_types import SpatialCoverage
from tools.factory_world.builder import Builder
from tools.factory_world.coverage import path_between

SCOPE_OWNER = {
 'raw-sea':{'load-port':'destination:sea:-1100','bulk-voyage':'RAW-SHIP','berth':'quay:raw',
   'unload':'raw:unloader','yard-store':'ORE-SOURCE','process-feed':'CHARGE-A'},
 'receiving':{'arrival':'receiving:arrival-gate','inspection':'receiving:receiving-inspection',
   'weigh':'receiving:weighbridge','unload':'receiving:unload','store':'receipt:SLAB','downstream-feed':'CS-HR-02'},
 'road':{'dispatch':'road-dispatch:dispatch','wait':'road-dispatch:wait','load':'road-dispatch:load',
   'secure':'road-dispatch:secure','weigh':'road-dispatch:weigh','gate-out':'road-dispatch:gate-out',
   'travel':'CUSTOMER','customer-unload':'road-dispatch:customer-unload',
   'customer-accept':'road-dispatch:customer-accept','empty-return':'road-dispatch:wait'},
 'rail':{'consist':'transfer:rail','shunt':'transfer:rail','wagon-load':'transfer:rail','block-move':'destination:rail:4300',
   'destination-unload':'destination:rail:4300','destination-store':'destination:rail:4300',
   'last-mile':'CUSTOMER','customer-delivery':'CUSTOMER','empty-return':'transfer:rail'},
 'sea':{'quay-transfer':'quay:product','berth-wait':'SHIP','load-survey':'SHIP',
   'voyage':'destination:sea:3550','unload-survey':'destination:sea:3550','hub-store':'destination:sea:3550',
   'last-mile':'CUSTOMER','customer-delivery':'CUSTOMER','empty-return':'SHIP'},
 'quality':{name:'quality:'+name for name in ('inspect','quarantine','reinspect','package','store','custody')},
}
ENTRIES={
 'ORE':('CHARGE-A',),'COAL':('CHARGE-A',),'LIMESTONE':('CHARGE-A',),'NICKEL_ORE':('STS-HR-02',),
 'SCRAP':('STS-HR-02','STS-PLATE-02'),'TI_INGOT':('TI-HR-02','TI-PLATE-02'),
 'SLAB':('CS-HR-02','CS-PLATE-02'),'BLOOM':('CS-WIRE-02',),'BILLET':('CS-WIRE-06',),
 'HR_COIL':('CS-CR-02','CS-HGI-02','CS-GO-02','CS-NGO-02'),
 'CR_COIL':('CS-GI-02','CS-GA-02','CS-EG-02'),'STS_HR_COIL':('STS-CR-02',),
 'TI_HR_COIL':('TI-CR-02','TI-SHEET-02'),
}


def scope_coverage(b: Builder, root: Path) -> None:
    registry=parse_registry(root/'shared/coverage-registry.json')
    ports={o.id:tuple(p for p in b.ports if p.owner_id==o.id) for o in b.owners}
    for req in registry.approved_scope_requirements:
        pieces=req.id.split(':')
        if len(pieces)!=3: continue
        _,group,name=pieces
        if group=='receipt':
            identity='receipt:'+name
            for target in ENTRIES[name]:
                a,c=ports[identity][0],ports[target][0]
                segments=path_between(b,(a.node_id,c.node_id))
                b.coverage.append(SpatialCoverage(id='coverage:'+req.id+':'+target,kind='source_function',
                    source_id=req.id,product_ids=req.products,owner_id=identity,socket_id=a.socket_id,
                    port_ids=(a.id,c.id),segment_ids=tuple(dict.fromkeys(segments))))
        elif group in SCOPE_OWNER:
            identity=SCOPE_OWNER[group][name]
            a=ports[identity][0]
            incident=tuple(s.id for s in b.segments if s.from_node_id==a.node_id or s.to_node_id==a.node_id)
            if not incident:
                # Work contacts are joined by the actual crane to the transport node.
                connected={p.node_id for p in ports[identity]}
                incident=tuple(s.id for s in b.segments if s.from_node_id in connected or s.to_node_id in connected)
            b.coverage.append(SpatialCoverage(id='coverage:'+req.id,kind='source_function',source_id=req.id,
                product_ids=req.products,owner_id=identity,socket_id=a.socket_id,
                port_ids=tuple(p.id for p in ports[identity]),segment_ids=incident))
