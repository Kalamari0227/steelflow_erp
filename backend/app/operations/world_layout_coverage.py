"""Exact identity, endpoint and source-function coverage against independent policies."""
from collections import Counter,defaultdict
from app.operations.world_contract import FactoryWorld
from app.operations.world_layout_requirements import LayoutRequirements,FLEET_REQUIRED,RECEIPT_FORMS
from app.operations.world_layout_paths import reachable,optional_exit_graph
from app.operations.world_types import require
from app.operations.world_spatial_types import SpatialCoverage
from app.operations.world_clearance import local
from tools.qa.coverage_expectations import PARTS
from app.operations.world_layout_policy import FUNCTION_SECTIONS,RECEIPT_ENTRIES,OPTIONAL_EXIT_BRANCHES


def validate_coverage(world: FactoryWorld, requirements: LayoutRequirements) -> tuple[tuple[str,int],...]:
    spatial=world.spatial
    require(spatial is not None,'spatial_required','world')
    groups=defaultdict(dict)
    for row in spatial.coverage:
        groups[row.kind].setdefault(row.source_id,[]).append(row)
    inventory=requirements.registry.observed_inventory
    required={'equipment':{r.id for r in inventory.equipment},'compiled_step':{r.id for r in inventory.compiled_steps},
              'connection':{r.id for r in inventory.compiled_connections},'source_function':requirements.source_functions,
              'hall':{r.id for r in requirements.campus.halls},'asset_kind':{r.id for r in requirements.assets.policies}}
    for kind,expected in required.items():
        require(expected<=groups[kind].keys(),'coverage_missing',kind+':'+','.join(sorted(expected-groups[kind].keys())))
    require({s.native_id for s in inventory.stages}<={z.id for z in spatial.zones},'stage_coverage','world')
    require({h.id for h in requirements.campus.halls}<={h.id for h in spatial.halls},'hall_coverage','world')
    for row in inventory.equipment:
        require(any(c.owner_id==row.native_id for c in groups['equipment'][row.id]),'equipment_placement',row.id)
    for row in inventory.compiled_steps:
        bindings=groups['compiled_step'][row.id]
        require(len(bindings)==1 and bindings[0].owner_id==row.equipment_id and bindings[0].product_ids==(row.product_id,),
                'step_placement',row.id)
    ports={p.id:p for p in world.ports};segments={s.id:s for s in world.segments}
    owners={o.id:o for o in world.owners}
    nodes={n.id:n for n in world.nodes}
    footprints={f.owner_id:f for f in world.footprints}
    def working_contact(binding: SpatialCoverage) -> None:
        owner=owners[binding.owner_id]
        expected='hold' if owner.kind=='ship' else 'work'
        actual=[ports[p] for p in binding.port_ids if ports[p].owner_id==owner.id and ports[p].socket_id==expected]
        require(binding.socket_id==expected and len(actual)==1,'working_port',binding.id)
        point=nodes[actual[0].node_id].position
        box=footprints[owner.id]
        position=local(point,box)
        require(all(abs(position[i])<=box.size_m[i]/2+.01 for i in range(3)),'work_outside_equipment',binding.id)
        require(any(actual[0].id in reach.pick_port_ids and actual[0].id in reach.drop_port_ids
            and any(ports[p].node_id!=actual[0].node_id and (ports[p].owner_id==owner.id or owner.kind=='ship')
                for p in (*reach.pick_port_ids,*reach.drop_port_ids))
            for reach in spatial.crane_reaches),'work_handoff',binding.id)
    for row in spatial.coverage:
        if row.kind in ('equipment','compiled_step') or (row.kind=='source_function' and row.source_id in requirements.source_functions):
            working_contact(row)
    for row in inventory.compiled_connections:
        bindings=groups['connection'][row.id]
        require(len(bindings)==1,'connection_duplicate',row.id)
        binding=bindings[0]
        require(len(binding.port_ids)==2,'connection_endpoints',row.id)
        a,b=(ports[p] for p in binding.port_ids)
        require((a.owner_id,b.owner_id)==(row.from_equipment_id,row.to_equipment_id),'connection_owner',row.id)
        adjacent=defaultdict(set)
        for sid in binding.segment_ids: adjacent[segments[sid].from_node_id].add(segments[sid].to_node_id)
        for crane in spatial.crane_reaches:
            for pick in crane.pick_port_ids:
                for drop in crane.drop_port_ids: adjacent[ports[pick].node_id].add(ports[drop].node_id)
        require(b.node_id in reachable(adjacent,a.node_id),'connection_path',row.id)
    for source in requirements.source_functions:
        bindings=groups['source_function'][source]
        expected=set(PARTS[source.removeprefix('src:')][0].split())
        require(Counter(p for binding in bindings for p in binding.product_ids)==Counter(expected),'function_placement_count',source)
        require(set(p for b in bindings for p in b.product_ids)==expected,'function_products',source)
        require(all(b.port_ids and b.segment_ids for b in bindings),'function_contact_path',source)
    function_owners=[]
    for source in requirements.source_functions:
        for binding in groups['source_function'][source]:
            require(len(binding.product_ids)==1,'function_product_placement',source)
            require(binding.owner_id not in {row.native_id for row in inventory.equipment},'function_legacy_alias',binding.id)
            function_owners.append(binding.owner_id)
            zone=next(z for z in spatial.zones if z.id==binding.product_ids[0])
            require(binding.owner_id in zone.owner_ids,'function_zone',binding.id)
    require(len(function_owners)==len(set(function_owners)),'function_alias','world')
    for source,product,before,after in FUNCTION_SECTIONS:
        binding=next(b for b in groups['source_function']['src:'+source] if b.product_ids==(product,))
        hall=next(h for h in spatial.halls if h.zone_id==product)
        box=next(f for f in world.footprints if f.id==hall.footprint_id)
        require(local(owners[before].pose.position,box)[0]<local(owners[binding.owner_id].pose.position,box)[0]<local(owners[after].pose.position,box)[0],
                'function_section_order',source+':'+product)
    for form,targets in RECEIPT_ENTRIES.items():
        bindings=groups['source_function'].get('scope:receipt:'+form,[])
        endpoints=set()
        for binding in bindings:
            require(len(binding.port_ids)==2,'receipt_entry_ports',form)
            start,end=(ports[identity] for identity in binding.port_ids)
            require(start.owner_id=='receipt:'+form and end.socket_id=='work','receipt_entry_ports',form)
            require(end.owner_id in targets,'receipt_entry_target',form+':'+end.owner_id)
            endpoints.add(end.owner_id)
            adjacent=defaultdict(set)
            for sid in binding.segment_ids:
                segment=segments[sid]
                adjacent[segment.from_node_id].add(segment.to_node_id)
            for reach in spatial.crane_reaches:
                for pick in reach.pick_port_ids:
                    for drop in reach.drop_port_ids:
                        adjacent[ports[pick].node_id].add(ports[drop].node_id)
            require(end.node_id in reachable(adjacent,start.node_id),'receipt_entry_path',form+':'+end.owner_id)
        require(endpoints==set(targets),'receipt_entry_coverage',form)
    warehouse=next(port.node_id for port in world.ports if port.owner_id=='WAREHOUSE' and port.socket_id=='work')
    for source,product,forbidden in OPTIONAL_EXIT_BRANCHES:
        binding=next(row for row in groups['source_function'][source] if row.product_ids==(product,))
        start=next(ports[p].node_id for p in binding.port_ids if ports[p].socket_id=='work')
        graph=optional_exit_graph(world,forbidden)
        require(warehouse in reachable(graph,start),'optional_exit_branch',source)
    scope_prefixes=('scope:receipt:','scope:raw-sea:','scope:receiving:','scope:road:','scope:rail:','scope:sea:','scope:quality:')
    for requirement in requirements.registry.approved_scope_requirements:
        if requirement.id.startswith(scope_prefixes):
            require(requirement.id in groups['source_function'],'scope_coverage',requirement.id)
            for binding in groups['source_function'][requirement.id]:
                require(bool(binding.port_ids) and bool(binding.segment_ids),'scope_physical_contact',requirement.id)
    required_modes={('BF-A','BOF-A'):'hot_metal',('BOF-A','LF-A'):'ladle',
       ('LF-A','CAST-SLAB'):'ladle',('LF-A','CAST-BLOOM'):'ladle',('LF-A','CAST-BILLET'):'ladle',
       ('ORE-SOURCE','CHARGE-A'):'conveyor',('SHIP','CUSTOMER'):'sea'}
    for item in inventory.compiled_connections:
        mode=required_modes.get((item.from_equipment_id,item.to_equipment_id))
        if mode:
            require(any(segments[s].mode==mode for s in groups['connection'][item.id][0].segment_ids),
                    'product_transport_mode',item.id)
    profile_kinds={p.id:p.kind for p in spatial.profiles}
    counts=Counter(profile_kinds[p.profile_id] for p in spatial.parking)
    for kind,amount in FLEET_REQUIRED: require(counts[kind]>=amount,'parking_capacity',kind)
    owners={o.id for o in world.owners}
    for form in RECEIPT_FORMS: require('receipt:'+form in owners,'receipt_port',form)
    require({s.mode for s in world.segments}=={'road','rail','hot_metal','ladle','roller','conveyor','sea'},'transport_modes','world')
    return tuple((kind,len(expected)) for kind,expected in required.items())
