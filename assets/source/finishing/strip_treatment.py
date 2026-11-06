"""Acid pickling, electrolytic cleaning and oiling machinery."""
from __future__ import annotations

from details import driven_roll, roller, tables
from geometry import Motion


def open_cell(model,name,x,length=3.2,width=2.0,height=1.35,strip_slot=False,liquid_y=None,exact_height=False):
    """Visible lined tank with an open roof and non-overlapping wall slabs."""
    model.node(name,position=(x,0,0))
    height=height if exact_height else max(height,model.datum-.59)
    model.box(name+'_base',(length,.14,width),(0,.62,0),name,'dark')
    for z,side in [(-width/2,'near'),(width/2,'far')]:
        model.box(name+'_'+side+'_wall',(length,height,.16),(0,.69+height/2,z),name,'teal')
        model.box(name+'_'+side+'_liner',(length-.1,height-.12,.045),(0,.69+height/2,z+(.104 if z<0 else -.104)),name,'ceramic',bevel=0)
    for xx,side in [(-length/2,'inlet'),(length/2,'outlet')]:
        end=name+'_'+side+'_end'
        if strip_slot:
            model.node(end,name,(xx,0,0))
            bottom,top=model.datum-.05,model.datum+.05
            model.box(end+'_lower',(.14,bottom-.69,width-.16),(0,(bottom+.69)/2,0),end,'blue')
            cap=.69+height-top
            if cap>0:model.box(end+'_upper',(.14,cap,width-.16),(0,top+cap/2,0),end,'blue')
            cheek=(width-.16-1.4)/2
            for z,suffix in [(-(width-.16+1.4)/4,'near'),((width-.16+1.4)/4,'far')]:
                model.box(end+'_'+suffix+'_cheek',(.14,top-bottom,cheek),(0,(bottom+top)/2,z),end,'blue')
        else:model.box(end, (.14,height,width-.16),(xx,.69+height/2,0),name,'blue')
    solution=model.box(name+'_solution',(length-.22,.025,width-.26),(0,model.datum-.12 if liquid_y is None else liquid_y,0),name,'green',bevel=0)
    solution['process_medium']=True
    for z,side in [(-1.3,'near'),(1.3,'far')]:
        model.tube(name+'_'+side+'_circulation',[(x-length/2,.75,z),(x-length/2,1.3,z),(x+length/2,1.3,z),(x+length/2,.8,z)],.055,finish='steel')
    model.cylinder(name+'_pump',.22,.45,(x+length/2+.35,.65,1.3),finish='blue',axis='y')


def pickling(model,spec):
    """Compact bath cells with a C1 dipped path and exact 4m feed stroke."""
    driven_roll(model,'pickling_feed',radius=.24)
    count=3 if spec['stage']=='cr' else 2
    t=spec['thickness_m'];r=.24+t/2;s=.12+t/2;span=2*(r+s)
    for i in range(count):
        start=i*(span+.08);center=start+span/2
        open_cell(model,'acid_tank' if i==0 else f'acid_cell_{i}',center,length=span+.06,height=1.10,strip_slot=True)
        if i>0:roller(model,f'acid_entry_roll_{i}',start,model.datum-.24,.24,driver='pickling_feed',ratio=1)
        roller(model,f'acid_submerged_roll_{i}',start+r+s,model.datum-.30,.12,driver='pickling_feed',ratio=-2)
        roller(model,f'acid_exit_roll_{i}',start+span,model.datum-.24,.24,driver='pickling_feed',ratio=1)
        lid=f'acid_lid_{i}'
        model.box(lid,(span+.03,.12,2.2),(center,2.55,0),finish='blue')
        model.roofs.append(lid)
        model.tube(f'acid_exhaust_{i}',[(center,2.6,.65),(center,3.1,.65),(center,3.1,1.8)],.12,finish='dark')
    end=(count-1)*(span+.08)+span
    for i in range(count):
        cell='acid_tank' if i==0 else f'acid_cell_{i}'
        model.roofs.extend([cell+'_'+side+'_'+part for side in ['near','far'] for part in ['wall','liner']])
    model.interior.extend(['acid_tank','pickling_feed'])
    tables(model,-4,-.5,'entry_bridle','pickling_feed')
    tables(model,end+.15,end+1.05,'rinse_bridle','pickling_feed')
    for i in range(3):
        x=end+.2+i*.3
        model.tube(f'rinse_header_{i}',[(x,2.25,-.8),(x,2.25,.8)],.035,finish='steel')
    model.box('rinse_catch',(1.4,.10,1.8),(end+.55,1.65,0),finish='dark')
    model.forming={'mode':'finite-pickling-threading','driver':'pickling_feed','travel_m':4,'stock_length_m':4,'width_m':1.2,'thickness_m':t,'cells':count,'entry_radius_m':.24,'submerged_radius_m':.12,'drop_m':.06,'gap_m':.08,'work_path_coordinate_m':0,'material_interval_m':'[R*theta-4,R*theta]','whole_stock_external_completion':False}


def cleaning(model,spec,prefix=''):
    brush=prefix+'cleaning_brush'
    feed='cleaning_strip_feed' if prefix else 'strip_feed'
    driven_roll(model,feed,x=0,radius=.20)
    model.node(brush,position=(-.65,model.datum+spec['thickness_m']+.19,0))
    model.cylinder(brush+'_bristles',.185,1.42,parent=brush,finish='dark')
    for i in range(12):
        model.ring(brush+f'_brush_band_{i}',(.17,.19),.045,(0,0,(i-5.5)*.11),brush,finish='safety')
    model.cylinder(brush+'_shaft',.075,2.0,parent=brush)
    for z,side in [(-.9,'near'),(.9,'far')]:
        model.box(brush+'_'+side+'_arm',(.32,.55,.25),(-.65,model.datum+.5,z),finish='teal')
    model.motion(Motion(brush,'rotation',(0,0,1),24))
    name='cleaning_electrodes' if prefix else 'electrolytic_cell'
    model.node(name,position=(1.25,0,0))
    for i in range(5):
        model.box(name+f'_electrode_{i}',(.18,.025,1.45),((i-2)*.25,model.datum+.075,0),name,'steel',bevel=.005)
    model.tube(name+'_bus',[(.55,model.datum+.4,-1.0),(1.95,model.datum+.4,-1.0)],.06,finish='safety')
    model.box('cleaning_drain',(3.2,.1,1.95),(.2,model.datum-.55,0),finish='blue')
    for i in range(4):
        model.tube(f'cleaning_spray_{i}',[(-1.2+i*.8,model.datum+.35,-.8),(-1.2+i*.8,model.datum+.35,.8)],.035,finish='steel')
    tables(model,-3,-1.8,'cleaning_entry',feed)
    tables(model,2.2,3,'cleaning_exit',feed)


def oiling(model,spec):
    driven_roll(model,'oiling_feed',radius=.18)
    model.node('spray_header',position=(0,model.datum+.42,0))
    for x,side in [(-.3,'entry'),(.3,'exit')]:
        model.tube('spray_header_'+side,[(x,0,-.85),(x,0,.85)],.05,'spray_header','steel')
        for i in range(7):
            model.cylinder(f'{side}_oil_nozzle_{i}',.035,.07,(x,-.05,(i-3)*.24),'spray_header',finish='safety',axis='y')
    model.box('oil_catch',(2.0,.12,1.95),(0,model.datum-.45,0),finish='dark')
    for z,side in [(-1.04,'near'),(1.04,'far')]:
        model.box(side+'_mist_wall',(2.1,.8,.1),(0,model.datum+.1,z),finish='blue')
    model.box('mist_hood',(2.2,.12,2.2),(0,model.datum+.85,0),finish='teal')
    model.roofs.append('mist_hood');model.interior.extend(['spray_header','oiling_feed'])
    model.cylinder('oil_reservoir',.35,1.1,(1.1,.8,1.8),finish='blue',axis='y')
    model.cylinder('oil_reservoir_pedestal',.3,.09,(1.1,.205,1.8),finish='teal',axis='y')
    model.tube('oil_supply',[(1.1,1.3,1.8),(1.1,2.55,1.8),(0,2.55,.85)],.04,finish='steel')
    tables(model,-3,-1.1,'oiling_entry','oiling_feed');tables(model,1.1,3,'oiling_exit','oiling_feed')
