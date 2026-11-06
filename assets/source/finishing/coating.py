"""Zinc bath, phosphate, passivation and electrical insulation applicators."""
from __future__ import annotations

from details import driven_roll, roller, tables
from geometry import Motion
from strip_treatment import open_cell


def galvanizing(model,spec):
    """Fully immersed lower sink roll, rising strip and a real two-sided wipe."""
    t=spec['thickness_m'];r=.22+t/2;s=.42+t/2;sink_x=r+s;exit_x=r+2*s
    open_cell(model,'zinc_pot',sink_x,length=3.8,width=2.6,height=1.0,liquid_y=1.64,exact_height=True)
    # The unchanged canonical work datum is the entry guide's actual top surface.
    roller(model,'sink_roll',sink_x,1.15,.42)
    model.motion(Motion('sink_roll','rotation',(0,0,1),4/.42))
    model.drive_radius=.42
    roller(model,'bath_entry_turn_roll',0,1.54,.22,driver='sink_roll',ratio=.42/.22)
    for z,side in [(-1.5,'near'),(1.5,'far')]:
        model.box(side+'_sink_support',(.45,1.3,.35),(sink_x,.81,z),finish='teal')
        model.tube(side+'_snout',[(-1.3,2.35,z*.36),(-.6,2.35,z*.36),(-.2,2.05,z*.36)],.12,finish='dark')
    model.node('air_knife',position=(exit_x,2.45,0))
    for x,side in [(-.12,'front'),(.12,'rear')]:
        model.box(side+'_knife_body',(.12,.14,1.75),(x,0,0),'air_knife','steel',bevel=.012)
        model.box(side+'_knife_slot',(.014,.025,1.6),(x+(.067 if x<0 else -.067),0,0),'air_knife','dark',bevel=0)
    for z,side in [(-1.08,'near'),(1.08,'far')]:
        model.box(side+'_knife_tower',(.20,3.4,.20),(exit_x,1.86,z),finish='teal')
        model.tube(side+'_knife_gas',[(exit_x,.6,z),(exit_x,2.45,z),(exit_x,2.45,z*.65)],.06,finish='steel')
    roller(model,'upper_turn_roll',exit_x+.26+t/2,3.35,.26,driver='sink_roll',ratio=.42/.26)
    roller(model,'exit_turn_roll',2.85,3.35,.26,driver='sink_roll',ratio=.42/.26)
    tables(model,-4,-.5,'bath_entry','sink_roll');tables(model,3.1,3.4,'bath_exit','sink_roll')
    model.roofs.extend(['zinc_pot_'+side+'_'+part for side in ['near','far'] for part in ['wall','liner']])
    model.interior.extend(['zinc_pot','sink_roll','bath_entry_turn_roll'])
    model.forming={'mode':'finite-bath-threading','driver':'sink_roll','travel_m':4,'stock_length_m':4,'width_m':1.2,'thickness_m':t,'sink_radius_m':.42,'sink_center_m':[sink_x,1.15,0],'air_knife_m':[exit_x,2.45,0],'work_path_coordinate_m':0,'material_interval_m':'[R*theta-4,R*theta]','whole_stock_external_completion':False}


def applicator(model,name,x=0,variant='passivation',thickness=.002):
    """Actual roll pair over a catch tray; variant changes process machinery."""
    driven_roll(model,name,x=x,radius=.18)
    roller(model,name+'_upper',x,model.datum+thickness+.18,.18,driver=name,ratio=-1)
    model.box(name+'_tray',(1.5,.12,1.9),(x,model.datum-.5,0),finish='dark')
    model.cylinder(name+'_supply_tank',.3,.95,(x+.55,.85,1.8),finish='blue',axis='y')
    model.cylinder(name+'_tank_pedestal',.25,.215,(x+.55,.2675,1.8),finish='teal',axis='y')
    model.tube(name+'_supply',[(x+.55,1.3,1.8),(x+.55,2.4,1.8),(x,2.4,.75)],.035,finish='steel')
    if variant in {'insulation','base-coating'}:
        for z,side in [(-.95,'near'),(.95,'far')]:
            model.box(name+'_'+side+'_metering_screw',(.12,.5,.15),(x,model.datum+.45,z),finish='steel')
        model.box(name+'_doctor_beam',(.14,.1,1.7),(x+.22,model.datum+.28,0),finish='safety')
    if variant=='phosphate':
        for i in range(4):
            model.tube(name+f'_phosphate_header_{i}',[(x-.7+i*.45,model.datum+.45,-.8),(x-.7+i*.45,model.datum+.45,.8)],.04,finish='steel')
        model.box(name+'_reaction_cell',(2.0,.3,2.0),(x,model.datum-.6,0),finish='teal')
    if variant=='anti-fingerprint':
        model.box(name+'_film_metering_head',(.42,.22,1.7),(x,model.datum+.35,0),finish='blue')
        model.cylinder(name+'_precision_pump',.16,.5,(x+.8,.85,1.8),finish='safety',axis='y')


def coating(model,spec):
    variant='phosphate' if spec['key']=='CS-EG-06' else 'anti-fingerprint' if spec['key']=='CS-EG-07' else 'insulation' if spec['stage'] in {'go','ngo'} else 'passivation'
    applicator(model,'coating_roll',variant=variant,thickness=spec['thickness_m'])
    tables(model,-3,-1.2,'coating_entry','coating_roll');tables(model,1.2,3,'coating_exit','coating_roll')
    if variant=='insulation':
        # Insulation cure tower and refractory box distinguish it from EG's wet cell.
        for z,side in [(-1.0,'near'),(1.0,'far')]:
            model.box('insulation_'+side+'_cure_wall',(1.4,1.1,.14),(1.8,model.datum+.3,z),finish='blue')
        model.box('insulation_cure_roof',(1.5,.12,2.1),(1.8,model.datum+.95,0),finish='teal')
        model.roofs.append('insulation_cure_roof');model.interior.append('coating_roll')


def electroplating(model,spec):
    driven_roll(model,'plating_feed',radius=.23)
    model.node('electrode_bank')
    for i in range(3):
        x=(i-1)*1.65
        open_cell(model,f'plating_solution_cell_{i}',x,length=1.5,height=1.1,strip_slot=True)
        for side,y in [('upper',model.datum+.11),('lower',model.datum-.11)]:
            for j in range(3):
                model.box(f'electrode_{i}_{side}_{j}',(.28,.035,1.45),(x+(j-1)*.4,y,0),'electrode_bank','steel',bevel=.005)
        model.tube(f'cell_{i}_power_bus',[(x-.55,2.55,-1.25),(x+.55,2.55,-1.25)],.07,finish='safety')
        model.box(f'cell_{i}_rectifier',(.8,1.3,.65),(x,.92,-2.0),finish='blue')
        for j in range(4):
            model.box(f'cell_{i}_rectifier_vent_{j}',(.6,.035,.03),(x,.65+j*.16,-2.34),finish='dark',bevel=0)
    tables(model,-3.2,-2.5,'plating_entry','plating_feed');tables(model,2.5,3.2,'plating_exit','plating_feed')
