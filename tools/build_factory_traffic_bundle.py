# /// script
# requires-python = ">=3.12"
# dependencies = ["pydantic>=2", "sqlalchemy>=2"]
# ///
# ─── How to run ───
# backend/.venv/bin/python tools/build_factory_traffic_bundle.py NEW_OUTPUT_DIRECTORY
"""Build exact, provenance-bound traffic corridors in an exclusively owned bundle."""
from __future__ import annotations

from hashlib import sha256
import json
from math import dist
from pathlib import Path
import sys

ROOT=Path(__file__).absolute().parents[1]
if str(ROOT/'backend') not in sys.path: sys.path.insert(0,str(ROOT/'backend'))
from app.operations import contracts_v3 as c
from app.operations.bundle_registry import ContractTestBundle, admit_contract_test
from app.operations.fleet import derive_fleet, approved_specification, FleetBootstrap, validate_initial_geometry
from app.operations.traffic_world import SOURCE_SHA, corridor_identity, admitted_corridors
from app.operations.world_clearance import envelope_crossing,sweep_radius,vertical_interval
from app.operations.world_trajectory import Line, fillet_trajectory
from app.operations.world_contract import parse_world
from app.operations.world_types import require
from app.operations.time_adapter_v3 import EPOCH_AT


def build_bundle(output: Path, *, full_admission: bool = True, east_buffer_m: float = 100.) -> ContractTestBundle:
    """Preserve canonical bytes and all original physical records in a derived copy."""
    output.mkdir(parents=True,exist_ok=False)
    source=(ROOT/'shared/factory-world-v2.json').read_bytes()
    bootstrap=derive_fleet(source,approved_specification('TRAFFIC-TEMPLATE',SOURCE_SHA))
    raw=bootstrap.world.model_dump(mode='json'); spatial=raw['spatial']; canonical=json.loads(source)
    sources={s['id']:s for s in raw['segments']}; policies={p['segment_id']:p for p in spatial['segment_policies']}
    paths=[]
    # Exact connected fourth arm, with actual ground support and reached safe slot.
    junction='v2:n:road:junction:4'; west='v2:traffic:v1:road:west'
    raw['nodes'].append({'id':west,'position':[-650.,2.,-1900.],'modes':['road']})
    spatial['stops'].append({'id':'traffic:v1:stop:west','node_id':west,'kind':'holding','profile_ids':['truck','slab-carrier','coil-carrier','forklift']})
    raw['owners'].append({'id':'traffic:v1:pad:west','kind':'equipment','pose':{'position':[-650.,0.,-1900.],'yaw_rad':0.},'sockets':[{'id':'support','pose':{'position':[0.,2.,0.],'yaw_rad':0.}}],'modes':['road']})
    raw['footprints'].append({'id':'traffic:v1:footprint:west','owner_id':'traffic:v1:pad:west','pose':{'position':[-650.,-1.,-1900.],'yaw_rad':0.},'size_m':[40.,2.,40.]})
    raw['slots'].append({'id':'v2:traffic:v1:slot:west','owner_id':'traffic:v1:pad:west','socket_id':'support','node_id':west,'capacity_kg':100000})
    for suffix,a,b,points in [('out',junction,west,[[-250.,2.,-1900.],[-650.,2.,-1900.]]),('back',west,junction,[[-650.,2.,-1900.],[-250.,2.,-1900.]])]:
        sid='traffic:v1:west:'+suffix
        s={'id':sid,'from_node_id':a,'to_node_id':b,'mode':'road','points':points,'conflict_zone_ids':[],'speed_m_per_sim_s':5.}
        p={'id':'policy:'+sid,'segment_id':sid,'width_m':30.,'height_m':15.,'profile_ids':['truck','slab-carrier','coil-carrier','forklift'],'stop_ids':['traffic:v1:stop:west','stop:'+junction],'rail_block_ids':[],'berth_ids':[]}
        raw['segments'].append(s);spatial['segment_policies'].append(p);sources[sid]=s;policies[sid]=p
    incoming=['road:shared:3:out','road:shared:4:back','road:shared:297:back','traffic:v1:west:back']
    outgoing=['road:shared:3:back','road:shared:4:out','road:shared:297:out','traffic:v1:west:out']
    for a in incoming:
        for b in outgoing:
            if sources[a]['from_node_id'] != sources[b]['to_node_id']: paths.append(('truck',(a,b),'holding'))
    # Off-line reached exits let four inbound actors finish without parking in
    # another actor's single-lane approach. Every turn remains real geometry.
    exits=[('north',[[-250.,2.,-1900.],[-250.,2.,-1980.],[-190.,2.,-1980.]],'road:shared:3:out'),('east',[[-250.,2.,-1900.],[-170.,2.,-1900.],[-170.,2.,-1840.]],'road:shared:297:back'),('south',[[-250.,2.,-1900.],[-250.,2.,-1820.],[-310.,2.,-1820.]],'road:shared:4:back'),('west',[[-250.,2.,-1900.],[-330.,2.,-1900.],[-330.,2.,-1960.]],'traffic:v1:west:back')]
    for label,points,opposite in exits:
        node='v2:traffic:v1:exit:'+label; sid='traffic:v1:exit:'+label; stop='traffic:v1:stop:exit:'+label;owner='traffic:v1:pad:exit:'+label
        x,y,z=points[-1]
        raw['nodes'].append({'id':node,'position':points[-1],'modes':['road']})
        spatial['stops'].append({'id':stop,'node_id':node,'kind':'holding','profile_ids':['truck']})
        raw['owners'].append({'id':owner,'kind':'equipment','pose':{'position':[x,0.,z],'yaw_rad':0.},'sockets':[{'id':'support','pose':{'position':[0.,2.,0.],'yaw_rad':0.}}],'modes':['road']})
        raw['footprints'].append({'id':'footprint:'+owner,'owner_id':owner,'pose':{'position':[x,-1.,z],'yaw_rad':0.},'size_m':[30.,2.,30.]})
        raw['slots'].append({'id':'v2:traffic:v1:slot:exit:'+label,'owner_id':owner,'socket_id':'support','node_id':node,'capacity_kg':100000})
        source={'id':sid,'from_node_id':junction,'to_node_id':node,'mode':'road','points':points,'conflict_zone_ids':[],'speed_m_per_sim_s':5.}
        policy={'id':'policy:'+sid,'segment_id':sid,'width_m':30.,'height_m':15.,'profile_ids':['truck'],'stop_ids':[stop],'rail_block_ids':[],'berth_ids':[]}
        raw['segments'].append(source);spatial['segment_policies'].append(policy);sources[sid]=source;policies[sid]=policy
        for approach in incoming:
            if approach != opposite: paths.append(('truck',(approach,sid),'holding'))

    # A road-mode port is required to be reachable by every road design profile.
    east_profiles=['truck','slab-carrier','coil-carrier','forklift']
    policies['traffic:v1:exit:east']['profile_ids']=east_profiles
    next(st for st in spatial['stops'] if st['id']=='traffic:v1:stop:exit:east')['profile_ids']=east_profiles
    east_exit=sources['traffic:v1:exit:east']
    reverse={**east_exit,'id':'traffic:v1:exit:east:back','from_node_id':east_exit['to_node_id'],'to_node_id':east_exit['from_node_id'],'points':list(reversed(east_exit['points'])),'conflict_zone_ids':[]}
    raw['segments'].append(reverse);sources[reverse['id']]=reverse
    reverse_policy={**policies[east_exit['id']],'id':'policy:'+reverse['id'],'segment_id':reverse['id']}
    spatial['segment_policies'].append(reverse_policy);policies[reverse['id']]=reverse_policy
    paths.append(('truck',(reverse['id'],'traffic:v1:west:out'),'holding'))
    raw['ports'].append({'id':'v2:traffic:v1:dock:east','owner_id':'traffic:v1:pad:exit:east','socket_id':'support','node_id':'v2:traffic:v1:exit:east','capacity_kg':100000,'modes':['road']})
    paths.append(('truck',('road:shared:100:out',),'holding'))
    for route in spatial['routes']:
        if route['id'] in ('loaded:parking:bay:truck:01','empty:parking:bay:truck:01'):
            paths.append((route['profile_id'],tuple(route['segment_ids']),route['kind']))
    # Connected real passing siding; split only at a tangent-continuous safe center.
    left='v2:n:transfer:rail:rail'; right='v2:n:destination:rail:4300:unload'; middle='v2:traffic:v1:rail:siding'
    raw['nodes'].append({'id':middle,'position':[3600.,3.,4700.],'modes':['rail']})
    spatial['stops'].append({'id':'traffic:v1:stop:siding','node_id':middle,'kind':'holding','profile_ids':['locomotive','railcar']})
    railparts=[('siding:left',left,middle,[[2200.,3.,4300.],[2500.,3.,4300.],[2800.,3.,4700.],[3600.,3.,4700.]]),('siding:right',middle,right,[[3600.,3.,4700.],[4400.,3.,4700.],[4700.,3.,4300.],[5000.,3.,4300.]])]
    for name,a,b,points in railparts:
        for suffix,start,end,ps in [('out',a,b,points),('back',b,a,list(reversed(points)))]:
            sid='traffic:v1:rail:'+name+':'+suffix; block='traffic:v1:block:'+name
            s={'id':sid,'from_node_id':start,'to_node_id':end,'mode':'rail','points':ps,'conflict_zone_ids':[],'speed_m_per_sim_s':5.}
            stops=[st['id'] for st in spatial['stops'] if st['node_id'] in (start,end) and set(['locomotive','railcar']) <= set(st['profile_ids'])]
            p={'id':'policy:'+sid,'segment_id':sid,'width_m':100.,'height_m':40.,'profile_ids':['locomotive','railcar'],'stop_ids':stops,'rail_block_ids':[block],'berth_ids':[]}
            raw['segments'].append(s);spatial['segment_policies'].append(p);sources[sid]=s;policies[sid]=p
            for profile in ('locomotive','railcar'): paths.append((profile,(sid,),'holding'))
        spatial['rail_blocks'].append({'id':'traffic:v1:block:'+name,'segment_ids':['traffic:v1:rail:'+name+':out','traffic:v1:rail:'+name+':back'],'usable_length_m':1400.,'clearance_m':5.,'reverse_allowed':True})
    # Real collinear buffers make each section contain the entire terminal body.
    # Copies of original main geometry keep exact points; only block metadata changes.
    for label,point in [('west-hold',[2000.,3.,4300.]),('west-buffer',[1800.,3.,4300.]),('switch-west-buffer',[2100.,3.,4300.]),('old-east-buffer',[2300.,3.,4300.]),('siding-left-buffer',[3500.,3.,4700.]),('siding-right-buffer',[3700.,3.,4700.])]:
        raw['nodes'].append({'id':'v2:traffic:v1:rail:'+label,'position':point,'modes':['rail']})
    buffers=[('west-hold','west-buffer','west-hold',[[1800.,3.,4300.],[2000.,3.,4300.]]),('west-approach','west-hold','left',[[2000.,3.,4300.],[2200.,3.,4300.]]),('switch-west','switch-west-buffer','left',[[2100.,3.,4300.],[2200.,3.,4300.]]),('old-east','left','old-east-buffer',[[2200.,3.,4300.],[2300.,3.,4300.]]),('siding-left','siding-left-buffer','middle',[[3500.,3.,4700.],[3600.,3.,4700.]]),('siding-right','middle','siding-right-buffer',[[3600.,3.,4700.],[3700.,3.,4700.]])]
    def rail_node(label):
        return {'left':left,'middle':middle}.get(label,'v2:traffic:v1:rail:'+label)
    for name,a,b,points in buffers:
        for suffix,start,end,ps in [('out',a,b,points),('back',b,a,list(reversed(points)))]:
            sid='traffic:v1:rail:buffer:'+name+':'+suffix
            source={'id':sid,'from_node_id':rail_node(start),'to_node_id':rail_node(end),'mode':'rail','points':ps,'conflict_zone_ids':[],'speed_m_per_sim_s':5.}
            policy={'id':'policy:'+sid,'segment_id':sid,'width_m':100.,'height_m':40.,'profile_ids':['locomotive','railcar'],'stop_ids':[],'rail_block_ids':[],'berth_ids':[]}
            raw['segments'].append(source);spatial['segment_policies'].append(policy);sources[sid]=source;policies[sid]=policy
    def buffer_ids(name):
        return ['traffic:v1:rail:buffer:'+name+':out','traffic:v1:rail:buffer:'+name+':back']
    old=next(b for b in spatial['rail_blocks'] if b['id']=='block:rail')
    moved=['rail:17:out','rail:17:back','rail:18:out','rail:18:back']
    old['segment_ids']=[x for x in old['segment_ids'] if x not in moved]+buffer_ids('old-east')
    section_sets={
        'traffic:v1:block:main':['rail:17:out','rail:17:back',*buffer_ids('switch-west'),'rail:18:out','rail:18:back'],
        'traffic:v1:block:siding:left':[*buffer_ids('switch-west'),*buffer_ids('siding-right')],
        'traffic:v1:block:siding:right':[*buffer_ids('siding-left'),'rail:18:out','rail:18:back'],
        'traffic:v1:block:west':[*buffer_ids('west-hold'),*buffer_ids('west-approach'),*buffer_ids('old-east')],
    }
    for identity,ids in section_sets.items():
        block=next((b for b in spatial['rail_blocks'] if b['id']==identity),None)
        if block is None:
            spatial['rail_blocks'].append({'id':identity,'segment_ids':ids,'usable_length_m':400. if identity.endswith(':west') else 2800.,'clearance_m':5.,'reverse_allowed':True})
        else: block['segment_ids'].extend(ids)
    for block in spatial['rail_blocks']:
        edges={tuple(sorted((sources[key]['from_node_id'],sources[key]['to_node_id']))):sum(dist(a,b) for a,b in zip(sources[key]['points'],sources[key]['points'][1:])) for key in block['segment_ids']}
        block['usable_length_m']=min(block['usable_length_m'],sum(edges.values()))
    for policy in spatial['segment_policies']:
        policy['rail_block_ids']=[b['id'] for b in spatial['rail_blocks'] if policy['segment_id'] in b['segment_ids']]
    for node_id in ('v2:traffic:v1:rail:west-hold','v2:n:rail:destination-buffer'):
        spatial['stops'].append({'id':'traffic:v1:stop:'+node_id.split(':')[-1],'node_id':node_id,'kind':'holding','profile_ids':['locomotive','railcar']})
    for profile in ('locomotive','railcar'):
        for sid in ('rail:17:out','rail:17:back','rail:18:out','rail:18:back',*buffer_ids('west-approach')):
            paths.append((profile,(sid,),'holding'))

    # A real eastern terminal beyond the opposing approach; the siding body is
    # wholly off the mainline, and both stopped consists have supported tails.
    for label,point in [('east-terminal',[5500.,3.,4300.]),('east-buffer',[5600.,3.,4300.])]:
        raw['nodes'].append({'id':'v2:traffic:v1:rail:'+label,'position':point,'modes':['rail']})
    east='v2:traffic:v1:rail:east-terminal'; buffer='v2:traffic:v1:rail:east-buffer'
    for label,node,point in [('siding',middle,[3600.,3.,4700.]),('east-terminal',east,[5500.,3.,4300.])]:
        owner='traffic:v1:pad:rail:'+label; stop='traffic:v1:stop:rail:'+label
        spatial['stops'].append({'id':stop,'node_id':node,'kind':'holding','profile_ids':['locomotive','railcar']})
        raw['owners'].append({'id':owner,'kind':'equipment','pose':{'position':[point[0],0.,point[2]],'yaw_rad':0.},'sockets':[{'id':'support','pose':{'position':[0.,3.,0.],'yaw_rad':0.}}],'modes':['rail']})
        raw['footprints'].append({'id':'footprint:'+owner,'owner_id':owner,'pose':{'position':[point[0],-1.,point[2]],'yaw_rad':0.},'size_m':[120.,2.,100.]})
        raw['slots'].append({'id':'v2:traffic:v1:slot:rail:'+label,'owner_id':owner,'socket_id':'support','node_id':node,'capacity_kg':200000})
    east_block={'id':'traffic:v1:block:east','segment_ids':['rail:18:out','rail:18:back'],'usable_length_m':600.,'clearance_m':5.,'reverse_allowed':True}
    for label,a,b,points in [('east-terminal','v2:n:rail:destination-buffer',east,[[5300.,3.,4300.],[5500.,3.,4300.]]),('east-tail',east,buffer,[[5500.,3.,4300.],[5600.,3.,4300.]])]:
        for suffix,start,end,ps in [('out',a,b,points),('back',b,a,list(reversed(points)))]:
            sid='traffic:v1:rail:'+label+':'+suffix
            source={'id':sid,'from_node_id':start,'to_node_id':end,'mode':'rail','points':ps,'conflict_zone_ids':[],'speed_m_per_sim_s':5.}
            policy={'id':'policy:'+sid,'segment_id':sid,'width_m':100.,'height_m':40.,'profile_ids':['locomotive','railcar'],'stop_ids':[],'rail_block_ids':[east_block['id']],'berth_ids':[]}
            raw['segments'].append(source);spatial['segment_policies'].append(policy);sources[sid]=source;policies[sid]=policy;east_block['segment_ids'].append(sid)
    tail_node='v2:traffic:v1:rail:east-inner-buffer'
    raw['nodes'].append({'id':tail_node,'position':[5000.-east_buffer_m,3.,4300.],'modes':['rail']})
    for suffix,a,b,points in [('out',tail_node,right,[[5000.-east_buffer_m,3.,4300.],[5000.,3.,4300.]]),('back',right,tail_node,[[5000.,3.,4300.],[5000.-east_buffer_m,3.,4300.]])]:
        sid='traffic:v1:rail:east-inner-buffer:'+suffix
        source={'id':sid,'from_node_id':a,'to_node_id':b,'mode':'rail','points':points,'conflict_zone_ids':[],'speed_m_per_sim_s':5.}
        policy={'id':'policy:'+sid,'segment_id':sid,'width_m':100.,'height_m':40.,'profile_ids':['locomotive','railcar'],'stop_ids':[],'rail_block_ids':[east_block['id']],'berth_ids':[]}
        raw['segments'].append(source);spatial['segment_policies'].append(policy);sources[sid]=source;policies[sid]=policy;east_block['segment_ids'].append(sid)
    spatial['rail_blocks'].append(east_block)
    for sid in ('rail:18:out','rail:18:back'): policies[sid]['rail_block_ids'].append(east_block['id'])
    for profile in ('locomotive','railcar'):
        paths.extend([(profile,('traffic:v1:rail:buffer:west-approach:out','traffic:v1:rail:siding:left:out'),'holding'),(profile,('rail:18:back','rail:17:back','traffic:v1:rail:buffer:west-approach:back'),'holding'),(profile,('traffic:v1:rail:siding:right:out','rail:18:out','traffic:v1:rail:east-terminal:out'),'holding')])

    # The middle 200m is a real separate siding section: an 85m stopped body
    # clears both switches, rather than retaining a switch block through its stop.
    left_buffer='v2:traffic:v1:rail:siding-left-buffer';right_buffer='v2:traffic:v1:rail:siding-right-buffer'
    for sid in ('traffic:v1:rail:siding:left:out','traffic:v1:rail:siding:left:back'):
        source=sources[sid]
        if sid.endswith(':out'): source['to_node_id']=left_buffer;source['points'][-1]=[3500.,3.,4700.]
        else: source['from_node_id']=left_buffer;source['points'][0]=[3500.,3.,4700.]
    for sid in ('traffic:v1:rail:siding:right:out','traffic:v1:rail:siding:right:back'):
        source=sources[sid]
        if sid.endswith(':out'): source['from_node_id']=right_buffer;source['points'][0]=[3700.,3.,4700.]
        else: source['to_node_id']=right_buffer;source['points'][-1]=[3700.,3.,4700.]
    middle_ids=buffer_ids('siding-left')+buffer_ids('siding-right')
    for block in spatial['rail_blocks']:
        block['segment_ids']=[key for key in block['segment_ids'] if key not in middle_ids]
    spatial['rail_blocks'].append({'id':'traffic:v1:block:siding:hold','segment_ids':middle_ids,'usable_length_m':200.,'clearance_m':5.,'reverse_allowed':True})
    expansion={
        'traffic:v1:rail:siding:left:out':('traffic:v1:rail:siding:left:out','traffic:v1:rail:buffer:siding-left:out'),
        'traffic:v1:rail:siding:left:back':('traffic:v1:rail:buffer:siding-left:back','traffic:v1:rail:siding:left:back'),
        'traffic:v1:rail:siding:right:out':('traffic:v1:rail:buffer:siding-right:out','traffic:v1:rail:siding:right:out'),
        'traffic:v1:rail:siding:right:back':('traffic:v1:rail:siding:right:back','traffic:v1:rail:buffer:siding-right:back'),
    }
    paths=[(profile,tuple(part for key in keys for part in expansion.get(key,(key,))),kind) for profile,keys,kind in paths]
    for policy in spatial['segment_policies']:
        sid=policy['segment_id']
        if sid.startswith('traffic:v1:rail:'):
            policy['rail_block_ids']=[b['id'] for b in spatial['rail_blocks'] if sid in b['segment_ids']]
            policy['stop_ids']=[st['id'] for st in spatial['stops'] if st['node_id'] in (sources[sid]['from_node_id'],sources[sid]['to_node_id']) and set(policy['profile_ids']) <= set(st['profile_ids'])]
    for block in spatial['rail_blocks']:
        lengths={tuple(sorted((sources[key]['from_node_id'],sources[key]['to_node_id']))):sum(dist(a,b) for a,b in zip(sources[key]['points'],sources[key]['points'][1:])) for key in block['segment_ids']}
        block['usable_length_m']=min(block['usable_length_m'],sum(lengths.values()))

    # Register each macro and exact ordered source route in their existing collections.
    metadata=[]
    for pid,sids,kind in paths:
        sid=corridor_identity(pid,sids,kind); source_rows=[sources[key] for key in sids]; points=[p for i,s in enumerate(source_rows) for p in (s['points'] if i==0 else s['points'][1:])]
        profile=next(p for p in spatial['profiles'] if p['id']==pid)
        fillet_trajectory(tuple(tuple(p) for p in points),profile['min_turn_radius_m'])
        blocks=sorted({x for key in sids for x in policies[key]['rail_block_ids']});berths=sorted({x for key in sids for x in policies[key]['berth_ids']})
        a,b=source_rows[0]['from_node_id'],source_rows[-1]['to_node_id']
        source_stops=sorted({x for key in sids for x in policies[key]['stop_ids']})
        stops=[st['id'] for st in spatial['stops'] if st['id'] in source_stops and st['node_id'] in (a,b)]
        s={'id':sid,'from_node_id':a,'to_node_id':b,'mode':source_rows[0]['mode'],'points':points,'conflict_zone_ids':[],'speed_m_per_sim_s':min(s['speed_m_per_sim_s'] for s in source_rows)}
        p={'id':'policy:'+sid,'segment_id':sid,'width_m':min(policies[k]['width_m'] for k in sids),'height_m':min(policies[k]['height_m'] for k in sids),'profile_ids':[pid],'stop_ids':stops,'rail_block_ids':blocks,'berth_ids':berths}
        raw['segments'].append(s);spatial['segment_policies'].append(p);sources[sid]=s;policies[sid]=p
        spatial['routes'].append({'id':sid,'profile_id':pid,'kind':kind,'from_node_id':a,'to_node_id':b,'segment_ids':list(sids)})
        for block in spatial['rail_blocks']:
            if block['id'] in blocks: block['segment_ids'].append(sid)
        for berth in spatial['berths']:
            if berth['id'] in berths: berth['segment_ids'].append(sid)
        for access in spatial['interior_access']:
            if pid in access['profile_ids'] and set(sids) <= set(access['segment_ids']): access['segment_ids'].append(sid)
        metadata.append({'macro_id':sid,'profile_id':pid,'ordered_source_segment_ids':list(sids),'source_stop_ids':source_stops,'policy_endpoint_stop_ids':stops})
    # Monotone pair-specific conflicts required by the same full-layout validator.
    world=parse_world(json.dumps(raw)); profiles={p.id:p for p in world.spatial.profiles}; pol={p.segment_id:p for p in world.spatial.segment_policies}
    original={s['id'] for s in canonical['segments']}; new=[s for s in world.segments if s.id not in original]
    deltas=[]
    for a in new:
        pa=[profiles[p] for p in pol[a.id].profile_ids]; ai=(min(vertical_interval(p)[0] for p in pa),max(vertical_interval(p)[1] for p in pa));ar=max(sweep_radius(p)+p.min_turn_radius_m for p in pa)
        for b in world.segments:
            if a.id == b.id or b.id not in original and a.id > b.id: continue
            pb=[profiles[p] for p in pol[b.id].profile_ids];bi=(min(vertical_interval(p)[0] for p in pb),max(vertical_interval(p)[1] for p in pb));br=max(sweep_radius(p)+p.min_turn_radius_m for p in pb)
            if not any(envelope_crossing((Line(x,y),Line(u,v)),(ai,bi),(ar,br)) for x,y in zip(a.points,a.points[1:]) for u,v in zip(b.points,b.points[1:])): continue
            zone='traffic:v1:cross:'+sha256((min(a.id,b.id)+'|'+max(a.id,b.id)).encode()).hexdigest()
            raw['conflict_zones'].append({'id':zone,'segment_ids':[a.id,b.id]});sources[a.id]['conflict_zone_ids'].append(zone);sources[b.id]['conflict_zone_ids'].append(zone)
            deltas.append({'zone_id':zone,'segment_ids':[a.id,b.id]})
    world_bytes=json.dumps(raw,sort_keys=True,indent=2).encode();world=parse_world(world_bytes)
    require(world.model_dump(mode='json')['owners'][:len(canonical['owners'])] == canonical['owners'],'source_owner_records','traffic')
    require(world.model_dump(mode='json')['footprints'][:len(canonical['footprints'])] == canonical['footprints'],'source_footprint_records','traffic')
    (output/'world.json').write_bytes(world_bytes)
    (output/'candidate-provenance.json').write_text(json.dumps({'source_sha256':SOURCE_SHA,'world_sha256':sha256(world_bytes).hexdigest(),'east_buffer_m':east_buffer_m,'macros':metadata,'monotone_conflict_deltas':deltas},indent=2))
    for old in canonical['segments']:
        current=sources[old['id']]
        require(all(current[key] == old[key] for key in ('from_node_id','to_node_id','mode','points','speed_m_per_sim_s')),'source_segment_geometry',old['id'])
    corridors=admitted_corridors(world)
    validate_initial_geometry(FleetBootstrap(world_bytes,world,bootstrap.fleet,bootstrap.vehicle_states,bootstrap.registrations))
    admission=None
    if full_admission:
        from app.operations.world_spatial_geometry import validate_factory_layout
        from app.operations.world_layout_requirements import LayoutRequirements
        proof=validate_factory_layout(world_bytes,LayoutRequirements.read(ROOT))
        admission={'raw_sha256':proof.raw_sha256,'swept_checks':proof.swept_checks,'registered_crossings':proof.registered_crossings,'coverage':proof.coverage}
    domain=c.FactoryCollections(fleet=bootstrap.fleet,vehicle_states=bootstrap.vehicle_states)
    artifacts={'collections.json':domain.model_dump_json().encode(),'world.json':world_bytes,'schema.json':json.dumps({'format':'factory-contract-test-schema-v1','schema_version':3,'fixture_version':'factory-v2','profile':'v3_contract_test','purpose':'T15 traffic fixed-intent test'}).encode(),'reader.json':json.dumps({'format':'factory-contract-test-reader-v1','schema_version':3,'reader':'app.operations.contracts_v3.FactorySnapshot','purpose':'T15 trusted traffic boundary'}).encode()}
    descriptors=[('domain','collections.json','factory-contract-test-collections-v1'),('world','world.json','factory-world-v2'),('schema','schema.json','factory-contract-test-schema-v1'),('reader','reader.json','factory-contract-test-reader-v1')]
    bid='T15-TRAFFIC-'+sha256(world_bytes).hexdigest()[:20]
    manifest=json.dumps({'format':'factory-contract-test-bundle-v1','bundle_id':bid,'profile':'v3_contract_test','schema_version':3,'fixture_version':'factory-v2','artifacts':[{'role':role,'path':path,'format':fmt,'sha256':sha256(artifacts[path]).hexdigest()} for role,path,fmt in descriptors]},sort_keys=True,indent=2).encode()
    run=c.FactoryRun.model_validate({'id':'TRAFFIC-TEMPLATE','bundle_id':bid,'bundle_hash':sha256(manifest).hexdigest(),'profile':'v3_contract_test','scenario_id':'NORMAL','seed':15,'elapsed_ms':0,'duration_ms':10800000,'revision':0,'event_sequence':0,'playing':False,'speed':1,'epoch_at':EPOCH_AT,'started_at':EPOCH_AT})
    state=c.FactorySnapshot.model_validate({**domain.model_dump(),'run':run});bundle=admit_contract_test(manifest,artifacts,state)
    for name,content in artifacts.items(): (output/name).write_bytes(content)
    (output/'bundle.json').write_bytes(manifest);(output/'domain.json').write_text(state.model_dump_json())
    (output/'provenance.json').write_text(json.dumps({'source_sha256':SOURCE_SHA,'compiler':'traffic-v1','macros':metadata,'monotone_conflict_deltas':deltas,'original_owners':len(canonical['owners']),'original_footprints':len(canonical['footprints']),'corridors':len(corridors),'admission':admission},indent=2))
    return bundle


if __name__ == '__main__':
    result=build_bundle(Path(sys.argv[1]))
    print(json.dumps({'bundle_id':result.verified.manifest.bundle_id,'bundle_hash':result.verified.bundle_hash}))
