"""Exact per-owner supplemental mechanisms from the sealed 29/52 map."""
from __future__ import annotations

from details import driven_roll, roller, tables
from geometry import Motion
from coating import applicator
from uncoiling import mandrel


def looper(model,name,x):
    model.node(name,position=(x,model.datum-.65,0))
    model.cylinder(name+'_moving_roll',.22,1.5,parent=name)
    model.cylinder(name+'_axle',.07,2.25,parent=name,finish='dark')
    for z,side in [(-1.0,'near'),(1.0,'far')]:
        model.box(name+'_'+side+'_slide',(.3,.45,.3),(0,0,z),name,'safety')
        model.box(name+'_'+side+'_tower',(.25,3.3,.25),(x,1.81,z),finish='teal')
        model.cylinder(name+'_'+side+'_guide',.045,2.5,(x,2.0,z+.18),finish='steel',axis='y')
    for i,dx in enumerate([-.6,.6]):
        roller(model,name+f'_fixed_roll_{i}',x+dx,model.datum-.22,.22)
    model.box(name+'_crosshead',(.28,.2,2.45),(0,.35,0),name,'blue')
    model.motion(Motion(name,'translation',(0,1,0),.6))


def cutter(model,name,x):
    model.node(name,position=(x,model.datum+.45,0))
    model.box(name+'_blade',(.08,.32,1.5),(0,-.12,0),name,'steel',bevel=.005)
    model.box(name+'_carriage',(.34,.25,1.9),(0,.16,0),name,'safety')
    for z,side in [(-1.1,'near'),(1.1,'far')]:
        model.box(name+'_'+side+'_column',(.4,3.0,.32),(x,1.66,z),finish='teal')
        model.box(name+'_'+side+'_guide',(.08,.8,.12),(x+.23,model.datum+.35,z),finish='steel')
    model.box(name+'_top',(.6,.3,2.5),(x,3.35,0),finish='blue')
    for dx,side in [(-.15,'in'),(.15,'out')]:
        model.box(name+'_fixed_anvil_'+side,(.20,.12,1.55),(x+dx,model.datum-.06,0),finish='steel',bevel=.005)
    model.cylinder(name+'_hydraulic_ram',.12,.8,(0,.7,0),name,'steel',axis='y')
    model.motion(Motion(name,'translation',(0,-1,0),.45))


def welder(model,spec):
    x=-3.25
    model.length=max(model.length,17.5)
    tables(model,-7.25,-3.65,'weld_infeed')
    model.node('strip_clamp',position=(x,model.datum+.12,0))
    for dx,side in [(-.3,'in'),(.3,'out')]:
        model.box(side+'_clamp_jaw',(.18,.10,1.45),(dx,0,0),'strip_clamp','steel',bevel=.008)
        model.box(side+'_clamp_anvil',(.22,.10,1.5),(x+dx,model.datum-.05,0),finish='steel',bevel=.008)
        for z,edge in [(-.85,'near'),(.85,'far')]:
            model.cylinder(side+'_'+edge+'_clamp_cylinder',.085,.45,(x+dx,model.datum+.40,z),finish='blue',axis='y')
    model.motion(Motion('strip_clamp','translation',(0,-1,0),.070-spec['thickness_m']))
    model.node('weld_head',position=(x,model.datum+spec['thickness_m']+.17,-.8))
    model.box('weld_head_carriage',(.24,.18,.22),parent='weld_head',finish='safety')
    model.cylinder('weld_electrode',.035,.12,(0,-.11,0),'weld_head','steel',axis='y')
    model.motion(Motion('weld_head','translation',(0,0,1),1.6))
    model.node('weld_power',position=(x,.8,1.65))
    model.box('weld_transformer',(.7,1.1,.6),parent='weld_power',finish='blue')
    model.box('weld_transformer_plinth',(.76,.09,.66),(x,.205,1.65),finish='dark')
    model.tube('weld_power_lead',[(x,1.3,1.65),(x,2.65,1.65),(x,2.65,.8)],.035,finish='dark')
    model.box('weld_cross_rail',(.18,.14,2.0),(x,model.datum+.45,0),finish='blue')


def header(model,name,x,oven=False):
    model.node(name,position=(x,model.datum+.55,0))
    for dx,side in [(-.3,'in'),(.3,'out')]:
        model.tube(name+'_'+side,[(dx,0,-.85),(dx,0,.85)],.055,name,'steel')
        for i in range(6):
            model.cylinder(name+f'_{side}_nozzle_{i}',.04,.07,(dx,-.05,(i-2.5)*.27),name,'safety',axis='y')
    for z,side in [(-1.1,'near'),(1.1,'far')]:
        model.box(name+'_'+side+'_post',(.16,model.datum+.7,.16),(x,(model.datum+.7)/2,z),finish='teal')
    if oven:
        for z,side in [(-1.0,'near'),(1.0,'far')]:
            model.box(name+'_'+side+'_oven_wall',(1.7,1.15,.12),(x,model.datum+.2,z),finish='blue')
        model.box(name+'_roof',(1.8,.12,2.1),(x,model.datum+.85,0),finish='teal')
        model.roofs.append(name+'_roof');model.interior.append(name)


def supplements(model,spec):
    names=set(spec['moving'])|set(spec['states'])
    if 'cleaning_brush' in names and 'cleaning_brush' not in model.objects:
        driven_roll(model,'cleaning_strip_feed',x=-3.1,radius=.18)
        model.node('cleaning_brush',position=(-3.1,model.datum+spec['thickness_m']+.18,0))
        model.cylinder('ngo_brush_barrel',.176,1.5,parent='cleaning_brush',finish='dark')
        for i in range(12):
            model.ring(f'ngo_brush_band_{i}',(.165,.18),.04,(0,0,(i-5.5)*.12),'cleaning_brush','safety')
        model.motion(Motion('cleaning_brush','rotation',(0,0,1),24))
        model.node('cleaning_electrodes',position=(-3.1,model.datum+.12,0))
        for i in range(4):
            model.box(f'ngo_clean_electrode_{i}',(.14,.025,1.45),((i-1.5)*.25,0,0),'cleaning_electrodes','steel',bevel=.003)
    if 'strip_clamp' in names:
        welder(model,spec)
    for name,x in [('entry_looper_lift',-4.8),('exit_looper_lift',4.8)]:
        if name in names:
            looper(model,name,x)
    if 'scale_breaker_roll' in names:
        driven_roll(model,'scale_breaker_roll',x=-4,radius=.17)
        roller(model,'scale_breaker_upper',-4,model.datum+.174,.17,driver='scale_breaker_roll',ratio=-1)
    if 'shot_wheel' in names:
        model.node('shot_wheel',position=(-3.5,model.datum+.6,0))
        model.cylinder('shot_wheel_disc',.35,.4,parent='shot_wheel',finish='dark')
        import math
        for i in range(8):
            a=i*math.tau/8
            model.tube(f'shot_vane_{i}',[(.10*math.cos(a),.10*math.sin(a),0),(.31*math.cos(a),.31*math.sin(a),0)],.04,'shot_wheel','steel')
        model.motion(Motion('shot_wheel','rotation',(0,0,1),30))
        model.box('shot_shroud',(1.1,.15,2.0),(-3.5,model.datum+1.1,0),finish='blue')
        model.box('shot_recovery',(1.1,.2,1.9),(-3.5,model.datum-.6,0),finish='dark')
    if 'base_coating_roll' in names:
        applicator(model,'base_coating_roll',x=3.4,variant='base-coating')
    for name,x in [('line_unwinding_mandrel',-7.0),('intermediate_winding_mandrel',9.8)]:
        if name in names:
            t=.004 if spec['key'] in {'CS-GO-04','CS-NGO-04','CS-GO-05','CS-NGO-05'} else .002
            if name=='intermediate_winding_mandrel':model.length=max(model.length,22)
            mandrel(model,name,x=x,thickness=t,line=model.line_spec if name=='line_unwinding_mandrel' else None,flat_start=name=='intermediate_winding_mandrel')
            if name=='intermediate_winding_mandrel':tables(model,5.95,9.05,'intermediate_runout',name)
    if 'output_cutter' in names:
        if spec['kind']=='coiler':
            model.length=max(model.length,17.5)
            tables(model,-8,-4.4,'cutter_infeed')
        cutter(model,'output_cutter',5.8 if 'intermediate_winding_mandrel' in names else -4.0 if spec['kind']=='coiler' else 4.0)
    if 'surface_scan' in names:
        model.node('surface_scan',position=(-3.6,model.datum+.35,-.65))
        model.box('surface_scanner_head',(.30,.20,.25),parent='surface_scan',finish='safety')
        model.box('surface_scanner_bridge',(.35,.16,2.2),(-3.6,model.datum+.65,0),finish='teal')
        for z,side in [(-1.05,'near'),(1.05,'far')]:
            model.box('scanner_'+side+'_post',(.16,2.65,.16),(-3.6,1.49,z),finish='teal')
        model.motion(Motion('surface_scan','translation',(0,0,1),1.3))
    if 'oven_feed' in names:
        driven_roll(model,'oven_feed',x=1.2,radius=.18)
    for name,x,oven in [('coating_cooling',3.6,False),('cooling_header',3.2,False),('curing_oven',1.2,True),('drying_header',2.8,True)]:
        if name in names:
            if name=='coating_cooling' and spec['kind']=='galvanizing':
                t=spec['thickness_m'];xx=.22+t/2+2*(.42+t/2)
                model.node(name,position=(xx,2.85,0))
                for side,sign in [('in',-1),('out',1)]:
                    model.tube(name+'_'+side,[(sign*.20,0,-.8),(sign*.20,0,.8)],.045,name,'steel')
                    for i in range(7):model.cylinder(name+f'_{side}_nozzle_{i}',.025,.10,(sign*.13,0,(i-3)*.24),name,'safety',axis='x')
                model.forming['cooling_m']=[xx,2.85,0]
            else:header(model,name,x,oven)
