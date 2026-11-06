"""Bind actual spatial paths to the independent T2 identities and T4 policies."""
from collections import defaultdict, deque
from pathlib import Path
from app.operations.world_spatial_types import SpatialCoverage
from tools.qa.coverage import parse_registry
from tools.factory_world.builder import Builder


def path_between(b: Builder, endpoints: tuple[str,str], required_mode: str | None = None) -> tuple[str,...]:
    adjacent=defaultdict(list)
    for s in b.segments: adjacent[s.from_node_id].append((s.to_node_id,s.id))
    ports={p.id:p for p in b.ports}
    for crane in b.cranes:
        for pick in crane.pick_port_ids:
            for drop in crane.drop_port_ids:
                adjacent[ports[pick].node_id].append((ports[drop].node_id,''))
    modes={s.id:s.mode for s in b.segments}
    queue=deque([(endpoints[0],(),required_mode is None)]);visited={(endpoints[0],required_mode is None)}
    while queue:
        node,path,used=queue.popleft()
        if node==endpoints[1] and used: return path
        for target,segment in adjacent[node]:
            state=(target,used or modes.get(segment)==required_mode)
            if state not in visited:
                visited.add(state);queue.append((target,path+((segment,) if segment else ()),state[1]))
    raise AssertionError(('product path missing',endpoints))


def add_coverage(b: Builder, root: Path) -> None:
    registry=parse_registry(root/'shared/coverage-registry.json')
    ports=defaultdict(list)
    for p in b.ports: ports[p.owner_id].append(p)
    for item in registry.observed_inventory.equipment:
        actual=ports[item.native_id]
        b.coverage.append(SpatialCoverage(id='coverage:'+item.id,kind='equipment',source_id=item.id,
            product_ids=(),owner_id=item.native_id,socket_id=actual[0].socket_id,
            port_ids=tuple(p.id for p in actual),segment_ids=()))
    for item in registry.observed_inventory.compiled_steps:
        actual=ports[item.equipment_id]
        b.coverage.append(SpatialCoverage(id='coverage:'+item.id,kind='compiled_step',source_id=item.id,
            product_ids=(item.product_id,),owner_id=item.equipment_id,socket_id=actual[0].socket_id,
            port_ids=(actual[0].id,),segment_ids=()))
    for item in registry.observed_inventory.compiled_connections:
        a,c=ports[item.from_equipment_id][0],ports[item.to_equipment_id][0]
        pair=(item.from_equipment_id,item.to_equipment_id)
        preferred={('BF-A','BOF-A'):'hot_metal',('BOF-A','LF-A'):'ladle',
            ('LF-A','CAST-SLAB'):'ladle',('LF-A','CAST-BLOOM'):'ladle',('LF-A','CAST-BILLET'):'ladle',
            ('ORE-SOURCE','CHARGE-A'):'conveyor',('SHIP','CUSTOMER'):'sea'}.get(pair)
        segments=path_between(b,(a.node_id,c.node_id),preferred)
        b.coverage.append(SpatialCoverage(id='coverage:'+item.id,kind='connection',source_id=item.id,
            product_ids=(item.product_id,),owner_id=item.from_equipment_id,socket_id=a.socket_id,
            port_ids=(a.id,c.id),segment_ids=tuple(dict.fromkeys(segments))))
    for zone in b.zones:
        owner=next(o for o in b.owners if o.id==zone.owner_ids[0])
        b.coverage.append(SpatialCoverage(id='coverage:stage:'+zone.id,kind='stage',source_id='stage:'+zone.id,
            product_ids=(),owner_id=owner.id,socket_id=owner.sockets[0].id,port_ids=(),segment_ids=()))
    for hall in b.halls:
        owner=next(o for o in b.owners if o.id==hall.id)
        b.coverage.append(SpatialCoverage(id='coverage:hall:'+hall.id,kind='hall',source_id=hall.id,
            product_ids=(),owner_id=owner.id,socket_id=owner.sockets[0].id,port_ids=(),segment_ids=()))
    # Actual incoming/outgoing support segments, independently checked at admission.
    for i,binding in enumerate(b.coverage):
        if binding.kind=='source_function':
            node_ids={p.node_id for p in b.ports if p.id in binding.port_ids}
            incident=tuple(s.id for s in b.segments if s.from_node_id in node_ids or s.to_node_id in node_ids)
            b.coverage[i]=binding.model_copy(update={'segment_ids':incident})
    from app.operations.world_layout_requirements import LayoutRequirements
    requirements=LayoutRequirements.read(root)
    planned={'crane':'gantry:BF-A','unloader':'raw:unloader','stacker':'raw:stacker',
       'reclaimer':'raw-yard-reclaimer','conveyor':'raw-belt:0','hall':'hall-hr',
       'receiving-inspection':'receiving:receiving-inspection','weighbridge':'receiving:weighbridge',
       'gate':'receiving:arrival-gate','raw-yard':'ORE-SOURCE','warehouse':'WAREHOUSE',
       'berth':'quay:raw','customer-dock':'CUSTOMER'}
    from tools.factory_world.design import FLEET
    for policy in requirements.assets.policies:
        if policy.category=='equipment':
            identity=next(e.native_id for e in registry.observed_inventory.equipment if e.kind==policy.kind)
        elif policy.kind in FLEET: identity='bay:'+policy.kind+':01'
        else: identity=planned[policy.kind]
        owner=next(o for o in b.owners if o.id==identity)
        b.coverage.append(SpatialCoverage(id='coverage:'+policy.id,kind='asset_kind',source_id=policy.id,
            product_ids=(),owner_id=identity,socket_id=owner.sockets[0].id,
            port_ids=tuple(p.id for p in ports[identity]),segment_ids=()))
