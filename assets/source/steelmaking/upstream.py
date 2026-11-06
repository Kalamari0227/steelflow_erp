"""Original burden feed and blast-furnace miniatures; material remains independently owned."""
import math
from geometry import Motion
from details import profile,platform


def charge(model):
    model.length,model.width=7,4.5
    for x in [-1.7,.7]:
        for z in [-1,1]:model.box(f'hopper_leg_{x}_{z}',(.22,3.1,.22),(x,1.7,z),finish='blue')
    # Open square hopper: the tapered walls are independent editable plate meshes.
    for side in [-1,1]:
        verts=[(-2,3.8,side*1.25),(.9,3.8,side*1.25),(.25,2.3,side*.45),(-1.35,2.3,side*.45)]
        model.node('hopper_side_'+str(side),mesh=model.mesh('hopper_side',verts,[(0,1,2,3)]),finish='teal')
        verts=[((-.55+side*1.45),3.8,-1.25),((-.55+side*1.45),3.8,1.25),((-.55+side*.8),2.3,.45),((-.55+side*.8),2.3,-.45)]
        model.node('hopper_end_'+str(side),mesh=model.mesh('hopper_end',verts,[(0,1,2,3)]),finish='blue')
    model.node('charge_feed',position=(-.55,2.25,0))
    model.box('metering_slide',(1.7,.12,1.02),parent='charge_feed',finish='steel')
    model.cylinder('gate_cylinder',.12,1.1,(-.55,2.25,-1),finish='safety')
    model.box('feed_chute',(3.6,.16,1.1),(1.25,1.42,0),finish='dark')
    for z in [-.62,.62]:model.box('chute_wall_'+str(z),(3.6,.45,.12),(1.25,1.7,z),finish='teal')
    for z in [-.55,.55]:model.box('chute_exit_leg_'+str(z),(.16,1.16,.16),(2.7,.76,z),finish='blue')
    platform(model,'loading_service',(-.6,2.2,1.8,3,.7))
    model.motion(Motion('charge_feed','translation',(0,0,-1),1.12))
    return [('support','root',(-.6,1.5,0),['ORE']),('entry','root',(-.6,2.28,0),['ORE']),('work','root',(.5,1.5,0),['ORE']),('exit','root',(2.7,1.5,0),['ORE'])]


def blast(model):
    model.length,model.width=10,7
    profile(model,'furnace_shell',[(.15,.4),(1.55,.4),(1.8,2.4),(1.8,4.2),(1.28,7.8),(.7,8.9),(.7,9.4),(.62,9.4),(.62,8.8),(1.18,7.8),(1.65,4.2),(1.65,2.4),(1.4,.6),(.15,.6)],position=(-.3,0,0),finish='blue')
    model.cylinder('furnace_foundation_ring',1.55,.22,(-.3,.29,0),finish='dark',axis='y')
    for y,r in [(1,1.75),(2.6,1.91),(4.4,1.87),(6.4,1.6),(8,1.4)]:
        profile(model,'shell_band_'+str(y),[(r,y),(r,y+.15),(r-.07,y+.15),(r-.07,y)],position=(-.3,0,0),finish='steel')
    for z in [-2.6,2.6]:
        for x in [-2.1,1.7]:model.box(f'tower_leg_{x}_{z}',(.28,9.4,.28),(x,4.88,z),finish='dark')
        model.tube('tower_cross_'+str(z),[(-2.1,1,z),(1.7,4.7,z),(-2.1,8.9,z)],.075,finish='steel')
    for i in range(3):
        x=-3.5+i*.95
        profile(model,'hot_blast_stove_'+str(i),[(.05,.3),(.4,.3),(.4,6.4),(.3,6.85),(.05,7)],position=(x,0,-2.5),finish='ceramic')
        model.cylinder('stove_base_'+str(i),.46,.12,(x,.24,-2.5),finish='dark',axis='y')
        model.tube('stove_manifold_'+str(i),[(x,5.5,-2.5),(x,5.5,-1.7),(-.3,3,-1.7)],.18,finish='steel')
    for i in range(8):
        a=i*math.tau/8
        model.tube('tuyere_'+str(i),[(-.3+1.8*math.cos(a),1.8,1.8*math.sin(a)),(-.3+2.1*math.cos(a),1.8,2.1*math.sin(a))],.13,finish='safety')
    model.node('charge_gate',position=(-.3,9.35,0))
    model.cylinder('top_charge_seal',.65,.16,parent='charge_gate',finish='steel',axis='y')
    model.motion(Motion('charge_gate','translation',(0,1,0),.45))
    model.box('tap_race',(2.9,.12,.6),(2.7,1.29,0),finish='ceramic')
    for z in [-.35,.35]:model.box('tap_trough_wall_'+str(z),(2.9,.32,.12),(2.7,1.45,z),finish='ceramic')
    model.node('tap_control',position=(1.7,1.65,.4))
    model.cylinder('tap_drill_hub',.22,.25,parent='tap_control',finish='safety')
    model.box('tap_drill_arm',(.8,.12,.12),(.4,0,0),'tap_control','steel')
    model.motion(Motion('tap_control','rotation',(0,0,1),1.1))
    platform(model,'furnace_gallery',(-.3,4.65,2.6,4.4,.8))
    model.box('cast_house_roof',(4.6,.2,3.2),(2.3,3.7,0),finish='blue')
    for z in [-1.4,1.4]:model.box('cast_house_post_'+str(z),(.22,3.42,.22),(4.3,1.89,z),finish='blue')
    model.roofs.append('cast_house_roof');model.interior.extend(['tap_race','tap_control'])
    return [('support','root',(-.3,.5,0),['ORE','HOT_METAL']),('entry','root',(-.3,9.48,0),['ORE']),('work','root',(2.7,1.32,0),['HOT_METAL']),('exit','root',(4,1.32,0),['HOT_METAL'])]
