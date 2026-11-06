"""Original truck and carrier assemblies; all dimensions are synthetic metres."""
import math
import bpy
from geometry import Model, Motion


def wheels(model: Model,axles: tuple[float,...],radius: float=.7,half_track: float=1.12) -> None:
    """Independent wheel pivots. Nested steered rollers stay explicit pending contract."""
    model.node('steering',(axles[-1],radius,-half_track))
    model.node('steering_right',(axles[-1],radius,half_track))
    model.followers.append({'node_id':'steering_right','driver':'steering','ratio':1.,'axis':(0.,1.,0.)})
    model.motion(Motion('steering','rotation',(0.,1.,0.),.25,'approach'))
    for i,x in enumerate(axles):
        model.cylinder(f'axle_{i}',.13,2.45,(x,radius,0.),finish='dark')
        for side,z in (('left',-half_track),('right',half_track)):
            name='wheel_rotation' if i==0 and side=='left' else f'wheel_{i}_{side}_roll'
            parent=('steering' if side=='left' else 'steering_right') if i==len(axles)-1 else 'root'
            origin=(0.,0.,0.) if parent!='root' else (x,radius,z)
            model.node(name,origin,parent)
            model.cylinder(name+'_tyre',radius,.24,parent=name,finish='rubber')
            model.cylinder(name+'_rim',radius*.55,.25,parent=name,finish='steel')
            model.cylinder(name+'_hub',radius*.22,.3,parent=name,finish='dark')
            for j in range(8):
                a=j*math.tau/8
                model.cylinder(name+f'_bolt{j}',.035,.27,(radius*.35*math.cos(a),radius*.35*math.sin(a),0.),name,'safety')
            model.box(name+'_rotation_index',(.08,radius*.6,.015),(0.,radius*.4,-.133),name,'white',bevel=0)
            if name=='wheel_rotation':model.motion(Motion(name,'rotation',(0.,0.,1.),math.tau,'travel'))
            else:model.followers.append({'node_id':name,'driver':'wheel_rotation','ratio':1.,'axis':(0.,0.,1.)})


def cab(model: Model,x: float=6.7,width: float=2.7) -> None:
    """Sloped cab shell, glass, front cooling grille and functional-scale details."""
    vertices=[]
    for z in (-width/2,width/2):
        vertices += [(x-1.5,1.,z),(x+1.6,1.,z),(x+1.5,2.8,z),(x+.9,3.85,z),(x-1.5,3.85,z)]
    faces=[(4,3,2,1,0),(5,6,7,8,9)]+[(i,(i+1)%5,(i+1)%5+5,i+5) for i in range(5)]
    model.node('cab_shell',mesh=model.mesh('cab_shell',vertices,faces),finish='teal')
    for z,label in ((-1.36,'left'),(1.36,'right')):
        model.box('cab_'+label+'_glass',(1.7,.9,.028),(x-.25,3.15,z),finish='glass')
        model.box('cab_'+label+'_handle',(.3,.06,.055),(x-.85,2.4,z),finish='steel')
        for j in range(3):model.box('cab_'+label+f'_step{j}',(.7,.09,.28),(x-.9,.45+j*.25,z),finish='steel')
        model.beam('cab_'+label+'_mirror_arm',(x+.7,2.8,z),(x+.8,3.,z*1.06),.04)
        model.box('cab_'+label+'_mirror',(.13,.3,.08),(x+.8,3.,z*1.06),finish='glass')
        model.cylinder('cab_'+label+'_exhaust',.075,1.9,(x-1.6,2.4,z*.8),axis='y')
    model.box('front_windshield',(.035,.83,2.25),(x+1.19,3.22,0.),finish='glass')
    model.box('front_bumper',(.25,.28,2.9),(x+1.72,.8,0.),finish='steel')
    for j in range(7):model.box('grille_'+str(j),(.055,.07,1.55),(x+1.53,1.5+j*.12,0.),finish='dark',bevel=.004)
    for z in (-.95,.95):model.box('headlight_'+str(z),(.07,.25,.32),(x+1.61,1.2,z),finish='white')


def truck(model: Model,dump: bool=False) -> None:
    """18m flatbed, support datum Y2, with a separate cab ahead of the load."""
    model.length=18.;model.ground=0.
    for z,label in ((-.85,'left'),(.85,'right')):
        model.box('chassis_'+label,(16.8,.36,.2),(-.2,.95,z),finish='dark')
        model.box('side_underrun_'+label,(7.5,.15,.12),(-.5,.6,z*1.68),finish='steel')
    for i,x in enumerate((-7.,-5.,-2.,1.,3.5)):
        model.box('chassis_cross_'+str(i),(.18,.28,2.55),(x,1.1,0.),finish='dark')
    cab(model);wheels(model,(-6.5,-4.7,6.7))
    model.node('load_bed',(-1.8,1.725,0.))
    model.fixed.append('load_bed')
    model.box('deck_plate',(12.7,.5,2.9),parent='load_bed',finish='steel',bevel=.015)
    for i in range(19):
        x=-5.9+i*.66
        if abs(x-1.8)<1.15:
            for z in (-1.075,1.075):model.box('deck_plank_'+str(i)+'_'+str(z),(.6,.025,.63),(x,.2625,z),'load_bed','blue',bevel=.004)
        else:model.box('deck_plank_'+str(i),(.6,.025,2.78),(x,.2625,0.),'load_bed','blue',bevel=.004)
    # Recessed central wear plate retains an exact planar Y2 support.
    model.box('deck_load_contact',(2.8,.025,1.45),(1.8,.2625,0.),'load_bed','steel',bevel=0)
    for i in range(8):
        for z in (-1.40,1.40):model.ring('lashing_'+str(i)+'_'+str(z),(.045,.075),.035,(-7.7+i*1.5,1.65,z),finish='safety')
    for z in (-1.15,1.15):
        model.box('rear_lamp_'+str(z),(.05,.2,.3),(-8.6,1.15,z),finish='red')
        model.box('mudguard_'+str(z),(3.1,.16,.47),(-5.6,1.48,z),finish='blue')
    model.box('rear_bumper',(.18,.22,2.8),(-8.7,.6,0.),finish='steel')
    model.cylinder('fuel_tank',.34,1.6,(3.,.95,-1.15),axis='x')
    model.socket('support','deck_load_contact',(0.,.0125,0.))
    model.socket('load','deck_load_contact',(0.,.0125,0.))
    if dump:
        model.fixed.remove('load_bed')
        model.objects['load_bed'].name='unused_flatbed_source'
        for node in [model.objects['load_bed'],*model.objects['load_bed'].children_recursive]:
            model.objects.pop(node['semantic_id'],None)
            model.nodes[:]=[n for n in model.nodes if n['id']!=node['semantic_id']]
            bpy.data.objects.remove(node,do_unlink=True)
        model.sockets.clear()
        model.node('tipper_lift',(-8.,1.75,0.))
        model.box('dump_floor',(11.5,.35,2.65),(5.75,0.,0.),'tipper_lift','steel')
        for z in (-1.35,1.35):
            model.box('dump_side_'+str(z),(11.5,1.9,.16),(5.75,1.,z),'tipper_lift','safety')
            for i in range(9):model.box('dump_rib_'+str(z)+'_'+str(i),(.12,1.9,.12),(.4+i*1.35,1.,z*1.06),'tipper_lift','blue')
        model.box('dump_headboard',(.18,2.,2.8),(11.4,1.,0.),'tipper_lift','safety')
        model.motion(Motion('tipper_lift','rotation',(0.,0.,1.),.8,'unload'))
        model.socket('support','dump_floor',(0.,.175,0.),forms=('ORE','SCRAP'))
        model.socket('load','dump_floor',(0.,.175,0.),forms=('ORE','SCRAP'))
        model.pending.append({'function':'tipper_lift','axis':[0,0,1],'range_rad':[0,.8],'reason':'actual body source; hydraulic lift drive/linkage and granular discharge remain pending independent proof'})


def carrier(model: Model,kind: str) -> None:
    """Low self-propelled carrier with an independently raised load platform."""
    model.ground=0.;model.length=14.
    model.box('carrier_frame',(13.5,.6,3.7),(0.,1.,0.),finish='blue')
    wheels(model,(-5.,-2.,2.,5.),.65,1.58)
    model.box('operator_cab',(2.,2.5,1.4),(4.8,2.,1.05),finish='teal')
    model.box('operator_glass',(1.6,1.,.03),(4.8,2.6,1.77),finish='glass')
    name='saddle_lift' if kind=='coil-carrier' else 'deck_lift'
    model.node(name,(0.,1.7,0.))
    model.box('lifting_deck',(10.,.45,3.5),parent=name,finish='safety')
    for x in (-4.,4.):
        for z in (-1.35,1.35):model.cylinder('lift_cylinder_'+str(x)+'_'+str(z),.14,.8,(x,1.3,z),axis='y')
    if kind=='coil-carrier':
        model.node('coil_saddle',(0.,.3,0.),name);model.fixed.append('coil_saddle');model.relative_fixed['coil_saddle']='saddle_lift'
        for z in (-.55,.55):model.box('saddle_'+str(z),(2.,.3,.25),(0.,0.,z),'coil_saddle','steel')
    model.motion(Motion(name,'translation',(0.,1.,0.),.8,'load'))
    model.socket('support',name,(0.,.225,0.),forms=('SLAB','BLOOM','BILLET','COIL'))
    model.socket('load',name,(0.,.225,0.),forms=('SLAB','BLOOM','BILLET','COIL'))


def forklift(model: Model) -> None:
    """Counterweight forklift with paired forks, tilt trunnion and real mast lift."""
    model.length=5.;model.ground=0.
    model.box('counterweight',(1.4,1.5,2.5),(-1.4,1.,0.),finish='safety',bevel=.2)
    model.box('power_pack',(1.8,.8,2.2),(-.5,1.1,0.),finish='blue')
    wheels(model,(-1.6,.8),.55,.95)
    for z in (-.9,.9):
        for x in (-.9,.5):model.box('cage_post_'+str(x)+'_'+str(z),(.12,2.3,.12),(x,2.,z),finish='dark')
    model.box('operator_guard',(1.9,.12,2.1),(-.25,3.2,0.),finish='safety')
    model.box('seat',(.6,.22,.65),(-.6,1.7,0.),finish='rubber')
    model.node('mast_tilt',(1.15,.6,0.))
    for z in (-.7,.7):model.box('mast_channel_'+str(z),(.22,3.5,.2),(0.,1.75,z),'mast_tilt','dark')
    model.node('fork_lift',(0.,.15,0.),'mast_tilt')
    model.box('fork_carriage',(.25,.7,1.7),(0.,.3,0.),'fork_lift','steel')
    for z in (-.5,.5):model.box('fork_tine_'+str(z),(1.5,.13,.22),(.55,0.,z),'fork_lift','steel',bevel=.015)
    model.motion(Motion('mast_tilt','rotation',(0.,0.,1.),.12,'load'))
    model.motion(Motion('fork_lift','translation',(0.,1.,0.),2.,'load'))
    model.socket('support','fork_lift',(.6,.065,-.5));model.socket('grip','fork_lift',(.6,.065,-.5))
