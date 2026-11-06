"""Continuous strip furnaces and GO's distinct batch-coil bell furnace."""
from __future__ import annotations

from details import driven_roll, tables
from geometry import Motion


def continuous(model,spec):
    name={'annealing':'anneal_feed','alloying':'induction_feed','decarburizing':'decarb_feed'}[spec['kind']]
    driven_roll(model,name,radius=.22)
    model.node('thermal_chamber')
    count=4 if spec['kind']=='decarburizing' else 3 if spec['stage'] in {'go','ngo'} else 2
    for i in range(count):
        x=(i-(count-1)/2)*1.25
        for z,side in [(-1.0,'near'),(1.0,'far')]:
            model.box(f'zone_{i}_{side}_shell',(1.18,1.6,.14),(x,model.datum+.2,z),'thermal_chamber','teal')
            model.box(f'zone_{i}_{side}_lining',(1.15,1.35,.08),(x,model.datum+.2,z+(.12 if z<0 else -.12)),'thermal_chamber','ceramic')
            model.tube(f'zone_{i}_{side}_radiant',[(x-.35,model.datum+.45,z*.8),(x-.35,model.datum+.8,z*.8),(x+.35,model.datum+.8,z*.8),(x+.35,model.datum+.45,z*.8)],.045,'thermal_chamber','steel')
        model.box(f'zone_{i}_hearth',(1.18,.12,1.8),(x,model.datum-.55,0),'thermal_chamber','ceramic')
        roof=f'zone_{i}_roof'
        model.box(roof,(1.2,.16,2.2),(x,model.datum+1.1,0),finish='blue')
        model.roofs.append(roof)
        model.tube(f'zone_{i}_stack',[(x,model.datum+1.2,.65),(x,model.datum+2,.65)],.15,finish='dark')
    model.interior.extend(['thermal_chamber',name])
    for x,side in [(-count*.625-.1,'entry'),(count*.625+.1,'exit')]:
        for z,edge in [(-.85,'near'),(.85,'far')]:
            model.box(side+'_'+edge+'_seal',(.2,.48,.16),(x,model.datum+.12,z),finish='dark')
    tables(model,-3.5,-count*.625-.35,'furnace_entry',name)
    tables(model,count*.625+.35,3.5,'cooling_exit',name)
    for i in range(3):
        model.tube(f'exit_cooling_{i}',[(2.7+i*.25,model.datum+.45,-.8),(2.7+i*.25,model.datum+.45,.8)],.045,finish='steel')


def bell(model,spec):
    """Charge car at canonical work height, separate base and lifting bell."""
    model.length=8.0
    model.node('thermal_chamber')
    model.node('batch_base',position=(0,model.datum-.1,0))
    # Docking tines and fixed base pads share boundary edges, not overlapping
    # disks. The back cantilever legs are outside the complete car stroke.
    for z,width,side in [(.15,.30,'center'),(-.65,.20,'near')]:
        model.box('batch_base_'+side+'_pad',(3.0,.10,width),(1.25,.05,z),'batch_base','ceramic',bevel=0)
        model.box('batch_base_'+side+'_leg',(.35,model.datum-.31,.32),(2.55,(model.datum-.31)/2+.16,z),finish='teal')
        model.box('batch_base_'+side+'_foot',(.65,.12,.60),(2.55,.22,z),finish='dark')
    model.tube('batch_gas_manifold',[(-.8,1.15,1.25),(.8,1.15,1.25)],.055,'thermal_chamber','steel')
    model.box('batch_burner_control',(.5,.6,.3),(.7,.7,1.45),'thermal_chamber','blue')
    model.ring('batch_base_seal',(1.09,1.29),.04,(.5,model.datum-.06,0),finish='steel',axis='y')
    model.node('treatment_feed',position=(0,model.datum,0))
    for z,width,side in [(-.25,.50,'near'),(.40,.20,'far')]:
        model.box('charge_car_'+side+'_fork',(1.8,.10,width),(.5,-.05,z),'treatment_feed','steel',bevel=0)
        for x,end in [(-.2,'in'),(1.2,'out')]:
            model.box('charge_car_'+side+'_'+end+'_fork_post',(.15,.22,.12),(x,-.21,z),'treatment_feed','teal')
    for x,end in [(-.2,'in'),(1.2,'out')]:
        model.box('charge_car_'+end+'_crossbeam',(.20,.16,2.0),(x,-.36,0),'treatment_feed','blue')
    for z,side in [(-.9,'near'),(.9,'far')]:
        model.box('charge_car_'+side+'_beam',(1.8,.18,.16),(.5,-.34,z),'treatment_feed','blue')
        for x,end in [(-.52,'in'),(.52,'out')]:
            model.cylinder('charge_car_'+side+'_'+end+'_wheel',.17,.13,(x+.5,-.41,z),'treatment_feed','dark')
        model.box('charge_rail_'+side,(5.0,.12,.12),(-.5,model.datum-.64,z),finish='steel')
        for x in [-2.8,-1.4,0,1.5]:
            model.box('charge_rail_'+side+str(x)+'_post',(.22,model.datum-.84,.25),(x,(model.datum-.84)/2+.16,z),finish='teal')
    model.motion(Motion('treatment_feed','translation',(1,0,0),0,minimum=-2))
    model.node('bell_lift',position=(.5,model.datum+.03,0))
    model.ring('bell_wall',(1.13,1.28),1.7,(0,.85,0),'bell_lift','teal',axis='y')
    model.ring('bell_lining',(1.04,1.12),1.62,(0,.85,0),'bell_lift','ceramic',axis='y')
    model.cylinder('bell_roof',1.28,.16,(0,1.78,0),'bell_lift','blue',axis='y')
    model.ring('bell_seal',(1.1,1.31),.10,(0,.05,0),'bell_lift','safety',axis='y')
    model.box('bell_lifting_lug',(.25,.35,.22),(0,2.0,0),'bell_lift','steel')
    for z,side in [(-1.8,'near'),(1.8,'far')]:
        model.box(side+'_bell_column',(.3,6.3,.3),(.5,3.31,z),finish='teal')
        model.box(side+'_bell_guide',(.12,5.2,.12),(.71,3.8,z),finish='steel')
        model.box(side+'_bell_slide',(.45,.4,.3),(0,.9,z),'bell_lift','blue')
        model.box(side+'_bell_lifting_arm',(.3,.2,.8),(0,.9,z*.8),'bell_lift','blue')
    model.box('bell_gantry',(.48,.35,4.0),(.5,6.6,0),finish='blue')
    model.cylinder('bell_hoist_drum',.28,.65,(.5,7.0,0),finish='safety')
    model.motion(Motion('bell_lift','translation',(0,1,0),2.0))
    model.interior.extend(['thermal_chamber','treatment_feed']);model.roofs.extend(['bell_wall','bell_roof','bell_lining'])
    # Long straight rail keeps the charge car's real wheels over the track.
    model.forming={'mode':'batch-coil','driver':'treatment_feed','outer_diameter_m':1.4,'inner_diameter_m':.6,'width_m':.6,'axis':'Y','coil_center_offset_m':[.5,.3,0],'support_local_mm':[-500,-300,0],'lift_driver':'bell_lift','car_min_m':-2,'car_max_m':0}
