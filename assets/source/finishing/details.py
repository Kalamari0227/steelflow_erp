"""Physical frames, roller bearings, drives and exposed service detail."""
from __future__ import annotations

import math
from geometry import IDENTITY, Motion


def foundation(model):
    """Continuous load path from the machine frame into a shared plinth."""
    length=model.length
    model.box('foundation',(length+.8,.16,5.8),(0,.08,0),finish='ceramic')
    for z,side in [(-1.35,'near'),(1.35,'far')]:
        model.box(side+'_longitudinal_beam',(length,.26,.26),(0,.45,z),finish='blue')
        for i in range(max(3,round(length/2))):
            x=-length/2+.5+i*(length-1)/(max(3,round(length/2))-1)
            model.box(f'{side}_foot_{i}',(.58,.12,.55),(x,.22,z),finish='dark')
            model.box(f'{side}_leg_{i}',(.24,.42,.24),(x,.43,z),finish='teal')
            for dx in [-.16,.16]:
                model.cylinder(f'{side}_anchor_{i}_{dx}',.035,.07,(x+dx,.305,z),finish='steel',axis='y')
    model.box('operator_post',(.16,.9,.16),(length/2-.4,.65,-2.2),finish='teal')
    model.box('operator_console',(.56,.55,.3),(length/2-.4,1.35,-2.2),finish='blue')
    for i,finish in enumerate(['red','green','safety']):
        model.cylinder(f'operator_button_{i}',.045,.035,(length/2-.56+i*.16,1.4,-2.365),finish=finish)


def roller(model,name,x,y,radius=.2,width=1.6,parent='root',driver=None,ratio=1):
    """Actual barrel, shaft, index and independently supported bearing pair."""
    if parent=='root' and getattr(model,'line_spec',None) and (name==model.line_spec['driver'] or driver==model.line_spec['driver']):parent='line_feed_lift'
    lifted=parent=='line_feed_lift'
    model.node(name,parent,(x,y,0))
    segments=model.segments
    # Contact barrels retain sufficient actual facet normals at every LOD.
    model.segments=max(model.segments,(64,48,32)[model.level])
    model.cylinder(name+'_barrel',radius,width,parent=name)
    model.segments=segments
    model.roller_specs.append({'part_id':name,'surface_node_id':name+'_barrel','radius_m':radius,'width_m':width,'center_m':[x,y,0],'parent':parent})
    model.cylinder(name+'_shaft',radius*.30,width+(.30 if lifted else .65),parent=name,finish='dark')
    model.box(name+'_index',(.045,.04,.07),(radius,0,-width/2-.06),name,'safety',bevel=.006)
    for z,side in [(-width/2-(.1 if lifted else .20),'near'),(width/2+(.1 if lifted else .20),'far')]:
        model.ring(name+'_'+side+'_bearing',(radius*.32,radius*.65),.12 if lifted else .22,(x,y,z),parent,finish='teal')
        base=.78 if lifted else .58;h=max(.15,y-radius*.60-base)
        model.box(name+'_'+side+'_pedestal',(.34,h,.18 if lifted else .3),(x,base+h/2,z),parent,finish='blue')
    if driver:
        model.followers.append({'node_id':name,'driver':driver,'ratio':ratio,'axis':[0,0,-1],'pivot_m':[x,y,0]})


def driven_roll(model,name,x=0,y=None,radius=.2,maximum=None):
    height=model.datum if y is None else y
    roller(model,name,x,height-radius,radius)
    model.motion(Motion(name,'rotation',(0,0,-1),maximum or 4/radius))
    model.drive_radius=radius
    return name


def tables(model,start,end,prefix='table',driver=None,positions=None):
    """Roller table; each roller has a real support and rotation ratio."""
    xs=positions if positions is not None else [start+(end-start)*i/max(1,round((end-start)/.65)) for i in range(max(1,round((end-start)/.65))+1)]
    for i,x in enumerate(xs):
        roller(model,f'{prefix}_idler_{i}',x,model.datum-.16,.16,driver=driver,ratio=model.drive_radius/.16)
    return xs


def motor(model,prefix,x,z=-1.6,height=.9):
    model.box(prefix+'_drive_plinth',(1.3,.22,1.0),(x,.27,z),finish='dark')
    for xx,part in [(x-.4,'motor'),(x+.3,'gearbox')]:
        h=height-.28-.38
        if h>0:
            model.box(prefix+'_'+part+'_pedestal',(.42,h,.48),(xx,.38+h/2,z),finish='teal')
    model.cylinder(prefix+'_motor',.28,.75,(x-.4,height,z),finish='blue',axis='x')
    for i in range(6):
        model.box(prefix+f'_cooling_fin_{i}',(.035,.55,.53),(x-.7+i*.12,height,z),finish='teal',bevel=.008)
    model.box(prefix+'_gearbox',(.5,.6,.65),(x+.3,height,z),finish='teal')
    model.cylinder(prefix+'_coupling',.1,.35,(x,height,z),finish='steel',axis='x')


def linear_transport(model,spec):
    """Only rigid rectangular strip sections opt into the existing T62 profile."""
    drivers={'electrocleaning':'strip_feed','annealing':'anneal_feed','temper':'temper_roll','oiling':'oiling_feed','coating':'coating_roll','alloying':'induction_feed','leveler':'leveling_roll','electroplating':'plating_feed','decarburizing':'decarb_feed'}
    if spec['kind'] not in drivers or getattr(model,'line_spec',None):return
    driver=drivers[spec['kind']]
    motion=next(m for m in model.motions if m.name==driver)
    canonical={m.name for m in model.motions}
    lower=[r for r in model.roller_specs if r['parent']=='root' and abs(r['center_m'][1]+r['radius_m']-model.datum)<1e-9]
    for i,x in enumerate([-3.6,-2.9,-2.2,-1.5,-.8,0,.8,1.5,2.2,2.9,3.6]):
        if any(abs(r['center_m'][0]-x)<r['radius_m']+.22 for r in lower):continue
        roller(model,f'bridge_feed_{i}',x,model.datum-.16,.16)
        lower.append(model.roller_specs[-1])
    profile=[]
    driver_radius=next(r['radius_m'] for r in lower if r['part_id']==driver)
    for r in lower:
        name=r['part_id']
        if name in canonical and name!=driver:continue
        if name!=driver and not any(f['node_id']==name for f in model.followers):
            model.followers.append({'node_id':name,'driver':driver,'ratio':driver_radius/r['radius_m'],'axis':[0,0,-1],'pivot_m':r['center_m']})
        follower=next((f for f in model.followers if f['node_id']==name),None)
        if name!=driver and (follower is None or follower['driver']!=driver or follower['ratio']<=0):continue
        profile.append({k:r[k] for k in ['part_id','surface_node_id','radius_m','width_m']})
    if abs(motion.maximum*driver_radius-4)>1e-9:raise RuntimeError('Linear section must retain its actual four metre travel')
    model.feed_spec={'schema_version':1,'id':'finishing_strip_feed','kind':'linear_roller_feed','custody_socket_id':'work','driver_part_id':driver,'start_m':[-2,model.datum,0],'end_m':[2,model.datum,0],'rollers':profile}


def markers(model):
    model.box('axis_origin',(.05,.05,.05),finish='dark',bevel=0)
    vertices=[(-.08,-.025,-.025),(-.08,.025,-.025),(-.08,.025,.025),(-.08,-.025,.025),(.14,0,0)]
    model.node('axis_front',position=(1,0,0),mesh=model.mesh('axis_front',vertices,[(0,3,2,1),(0,1,4),(1,2,4),(2,3,4),(3,0,4)]),finish='red')
    model.box('axis_up',(.04,.16,.04),(0,1,0),finish='green',bevel=0)
    model.box('axis_side',(.04,.04,.12),(0,0,-1),finish='axisblue',bevel=0)


def socket(name,node,point,role,forms,normal=(0,1,0)):
    return {'id':name,'node_id':node,'role':role,'transform':{'position_m':list(point),'rotation_xyzw':list(IDENTITY)},'normal':list(normal),'forms':forms,'max_load_kg':60000}


def contacts(model,spec):
    """Every support socket refers to an authored surface, never a display proxy."""
    result=[]
    form='COIL' if spec['kind'] in {'uncoiler','heat_treatment'} else 'STRIP'
    if spec['kind'] in {'coiler','uncoiler'}:
        name='winding_mandrel' if spec['kind']=='coiler' else 'unwinding_mandrel'
        for role in ['work','support']:
            result.append(socket(role,name,(0,.44,0),role,[form]))
        result.append(socket('coil_support' if form=='STRIP' else 'strip_support',name,(0,.44,0),'support',['COIL' if form=='STRIP' else 'STRIP']))
    elif spec['kind']=='heat_treatment':
        for role in ['work','support']:
            result.append(socket(role,'treatment_feed',(0,0,0),role,['COIL']))
        result.append(socket('batch_base','batch_base',(0,.10,0),'support',['COIL']))
    else:
        for role in ['work','support']:
            result.append(socket(role,'root',(0,model.datum,0),role,['STRIP']))
    for role,x in [('entry',model.entry_x),('exit',model.exit_x)]:
        result.append(socket(role,'root',(x,model.datum,0),role,['STRIP']))
    if spec['kind']=='cold_mill':
        cold=spec['cold_reduction'];b=cold['bite_m'];r=.36;theta=cold['entry_handoff_rad'];nip=cold['nip_x_m']
        result.append(socket('cold_entry_support','root',(nip-b,model.datum-.001,0),'support',['STRIP'],(-b/r,(r-.001)/r,0)))
        x=-b*math.cos(theta)-(r-.001)*math.sin(theta);y=-b*math.sin(theta)+(r-.001)*math.cos(theta)
        result.append(socket('cold_bite_roll_support','cold_reduction_roll',(x,y,0),'support',['STRIP'],(x/r,y/r,0)))
        result.append(socket('cold_nip_support','root',(nip,model.datum,0),'support',['STRIP']))
    if getattr(model,'line_spec',None):
        cfg=model.line_spec;t=cfg['thickness_m'];r0=.44+t/2;k=(t+.0002)/(2*math.pi);norm=math.hypot(r0,k);nx,ny=k/norm,r0/norm;point=(-t*nx/2,r0-t*ny/2,0)
        result.append(socket('line_coil_support','line_unwinding_mandrel',point,'support',['COIL'],(nx,ny,0)))
        result.append(socket('line_strip_support','line_unwinding_mandrel',point,'support',['STRIP'],(nx,ny,0)))
    # Source-bound subassembly supports remain distinct from canonical work.
    if 'output_cutter' in spec['moving']:
        for side in ['in','out']:
            result.append(socket('cutter_'+side+'_support','output_cutter_fixed_anvil_'+side,(0,.06,0),'support',['STRIP']))
    if 'strip_clamp' in spec['moving']:
        for side in ['in','out']:
            result.append(socket('weld_'+side+'_support',side+'_clamp_anvil',(0,.05,0),'support',['STRIP']))
    for role in ['entry','exit']:
        if role+'_looper_lift' in spec['moving']:
            roll=next(r for r in model.roller_specs if r['part_id']==role+'_looper_lift_fixed_roll_0')
            x,y,z=roll['center_m']
            result.append(socket(role+'_looper_support','root',(x,y+roll['radius_m'],z),'support',['STRIP']))
    if 'intermediate_winding_mandrel' in spec['moving']:
        for ident,family in [('intermediate_strip_support','STRIP'),('intermediate_coil_support','COIL')]:
            result.append(socket(ident,'intermediate_winding_mandrel',(0,.44,0),'support',[family]))
    q=(math.sin(.23),0,0,math.cos(.23))
    x,z=-model.length/2+.5,2.2
    model.box('service_post',(.16,.55,.16),(x,.435,z),finish='dark')
    model.node('service_bracket',position=(x,.76,z),rotation=q)
    model.box('service_pad',(.4,.12,.4),parent='service_bracket',finish='safety')
    result.append(socket('service_support','service_pad',(0,.06,0),'support',['PACKAGED']))
    return result
