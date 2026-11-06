"""Reheat, treatment and cooling machinery with genuine removable envelopes."""
import math
from details import table, rails
from geometry import Motion


def furnace(model, treatment=False, wire=False, secondary=False):
    model.length=10 if treatment or secondary else 12
    model.width=(1.15 if secondary else 1.65) if wire else 3.2
    w=model.width
    xs=model.roller_centers
    model.support_length=xs[-1]-xs[0]+.6
    table(model,xs[0],xs[-1],w,positions=[x for x in xs if abs(x+3.9)>1e-9])
    model.node('thermal_chamber')
    model.box('refractory_hearth',(7,.30,w+.75),(.0,.90,0),'thermal_chamber','ceramic')
    model.box('hearth_support',(7,.15,w+.6),(0,.72,0),'thermal_chamber','dark')
    for z,side in [(-w/2-.25,'far'),(w/2+.25,'near')]:
        model.node(side+'_envelope')
        model.box(side+'_refractory',(7,1.9,.24),(0,2.0,z),side+'_envelope','ceramic')
        model.box(side+'_cladding',(7.15,1.8,.14),(0,2.0,z+(.18 if z>0 else -.18)),side+'_envelope','blue')
        for i in range(8):
            x=-3.2+i*.9
            model.box(f'{side}_rib_{i}',(.10,2.1,.10),(x,2.0,z+(.28 if z>0 else -.28)),side+'_envelope','teal',bevel=.01)
            model.cylinder(f'{side}_burner_{i}',.13,.45,(x,1.65,z),parent='thermal_chamber',finish='dark')
            model.tube(f'{side}_gas_feed_{i}',[(x,1.65,z*1.2),(x,.65,z*1.2),(x,.65,z*1.4)],.035,finish='steel')
    model.node('roof')
    model.box('roof_insulation',(7.2,.28,w+.9),(0,3.08,0),'roof','ceramic')
    model.box('roof_skin',(7.3,.14,w+1.05),(0,3.28,0),'roof','blue')
    for i in range(12):
        model.box(f'roof_seam_{i}',(.045,.045,w+1.1),(-3.35+i*.6,3.38,0),'roof','steel',bevel=.005)
    for i,x in enumerate([-2.5,2.5]):
        model.cylinder(f'flue_{i}',.25,1.2,(x,3.85,-w/3),'roof','dark',axis='y')
        model.cylinder(f'flue_cap_{i}',.34,.10,(x,4.45,-w/3),'roof','steel',axis='y')
    model.roofs=['roof','near_envelope']
    model.interior=['thermal_chamber']
    feed='treatment_feed' if treatment else 'furnace_feed'
    model.node(feed,position=(-3.9,1.1,0))
    model.cylinder('drive_roll',.22,w,parent=feed)
    model.cylinder('furnace_drive_shaft',.065,w+.8,parent=feed,finish='dark')
    for z,side in [(-w/2-.18,'left'),(w/2+.18,'right')]:
        model.ring(side+'_feed_bearing',(.075,.18),.25,(-3.9,1.1,z),finish='teal')
        model.box(side+'_feed_seat',(.3,.28,.25),(-3.9,.80,z),finish='blue')
    model.box('drive_index',(.05,.06,.08),(.22,0,-w/2-.08),feed,'safety',bevel=.01)
    model.motion(Motion(feed,'rotation',(0,0,-1),(model.length-.6)/.22))
    if treatment:
        model.tube('entry_hood',[(-3.7,.25,-w/2-.35),(-3.7,3.05,-w/2-.35),(-3.7,3.05,w/2+.35),(-3.7,.25,w/2+.35)],.18,finish='teal')
    else:
        door_x=model.door_x
        model.node('furnace_door',position=(door_x,1.9,0))
        model.box('door_insulation',(.24,1.5,w+.3),parent='furnace_door',finish='ceramic')
        model.box('door_face',(.12,1.55,w+.45),(-.22,0,0),'furnace_door','teal')
        model.tube('door_crossbeam',[(-.32,-.6,-w/2),(-.32,.6,w/2)],.07,'furnace_door','safety')
        for z,side in [(-w/2-.45,'left'),(w/2+.45,'right')]:
            model.box(side+'_door_foot',(.5,.12,.5),(door_x,.20,z),finish='dark')
            model.box(side+'_door_rail',(.20,3.8,.18),(door_x,2.1,z),finish='dark')
            model.cylinder(side+'_door_cylinder',.10,1.5,(door_x,3.6,z),finish='steel',axis='y')
        model.motion(Motion('furnace_door','translation',(0,1,0),1.45,'entry'))
    for i in range(4):
        model.box(f'zone_panel_{i}',(.9,.5,.16),(-2.5+i*1.65,2.45,-w/2-.5),finish='teal')
    rails(model,7.5,1.9,w+1.5)


def cooling(model, plate=False):
    model.length,model.width=12,3.6 if plate else 2.5
    w=model.width
    table(model,-5.5,5.5,w)
    model.node('cooling_feed',position=(-4.8,1.10,0))
    model.cylinder('cooling_drive',.22,w,parent='cooling_feed')
    model.cylinder('cooling_drive_shaft',.065,w+.8,parent='cooling_feed',finish='dark')
    for z,side in [(-w/2-.18,'left'),(w/2+.18,'right')]:
        model.ring(side+'_drive_bearing',(.075,.18),.25,(-4.8,1.1,z),finish='teal')
        model.box(side+'_drive_seat',(.3,.28,.25),(-4.8,.80,z),finish='blue')
    model.box('cooling_drive_index',(.06,.06,.08),(.22,0,-w/2-.08),'cooling_feed','safety')
    model.motion(Motion('cooling_feed','rotation',(0,0,-1),5.4/.22))
    for i in range(6):
        x=-3.5+i*1.4
        model.tube(f'cooling_portal_{i}',[(x,.4,-w/2-.3),(x,2.4,-w/2-.3),(x,2.4,w/2+.3),(x,.4,w/2+.3)],.09,finish='teal')
        model.tube(f'header_branch_{i}',[(x,2.1,-w/2-.6),(x,2.1,-w/2-.25)],.085,finish='steel')
        model.cylinder(f'header_{i}',.11,w+.5,(x,2.1,0),finish='steel')
        for j in range(7):
            model.cylinder(f'nozzle_{i}_{j}',.035,.16,(x,1.94,(j-3)*w/7),finish='dark',axis='y')
    model.tube('main_cooling_pipe',[(-4,.45,-w/2-.6),(-4,2.1,-w/2-.6),(4.5,2.1,-w/2-.6)],.16,finish='steel')
    model.node('coolant_valve',position=(-4,2.1,-w/2-.6))
    model.cylinder('valve_wheel',.24,.08,parent='coolant_valve',finish='red',axis='x')
    for i in range(4):
        a=i*math.pi/2
        model.tube(f'valve_spoke_{i}',[(0,0,0),(0,.24*math.cos(a),.24*math.sin(a))],.025,'coolant_valve','steel')
    model.box('valve_index',(.1,.06,.06),(0,.25,0),'coolant_valve','safety')
    model.motion(Motion('coolant_valve','rotation',(1,0,0),math.pi/2))


def cooling_bed(model):
    model.length,model.width=11,5
    for i in range(19):
        x=(i-9)*.5
        model.box(f'fixed_rack_{i}',(.08,.25,5.4),(x,1.15,0),finish='steel',bevel=.01)
    model.node('bed_transfer',position=(0,1.2,0))
    for i in range(18):
        x=(i-8.5)*.5
        model.box(f'moving_rack_{i}',(.09,.22,4.5),(x,0,0),'bed_transfer','teal',bevel=.01)
        for j in range(5):
            model.box(f'cooling_tooth_{i}_{j}',(.13,.08,.10),(x,.15,(j-2)*.8),'bed_transfer','steel',bevel=.01)
    for i in range(18):
        for z,side in [(-2.0,'left'),(2.0,'right')]:
            model.box(f'transfer_bridge_{i}_{side}',(.09,.16,.18),((i-8.5)*.5,-.15,z),'bed_transfer','teal')
    for z,side in [(-2.65,'left'),(2.65,'right')]:
        model.box(side+'_rack_sill',(10,.30,.22),(0,.88,z),finish='blue')
        for i,x in enumerate([-4,0,4]):
            model.box(f'{side}_rack_leg_{i}',(.3,.64,.3),(x,.46,z),finish='teal')
    for z,side in [(-2.0,'left'),(2.0,'right')]:
        model.box(side+'_transfer_rail',(9,.18,.18),(0,-.28,z),'bed_transfer','blue')
    for x,side in [(-3,'entry'),(3,'exit')]:
        model.cylinder(side+'_hydraulic_barrel',.18,.9,(x,.75,-2.6),finish='dark')
        model.box(side+'_cylinder_pedestal',(.4,.48,.55),(x,.38,-2.6),finish='teal')
        model.cylinder(side+'_moving_rod',.06,1.0,(x,-.45,-2.15),'bed_transfer','steel')
        model.box(side+'_moving_bracket',(.25,.45,.25),(x,-.25,-2.0),'bed_transfer','safety')
    model.motion(Motion('bed_transfer','translation',(0,0,1),.4))
