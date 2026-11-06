"""Three section-specific continuous casters and supported cutting machines."""
import math
from geometry import Motion
from details import profile,platform

SECTION={'SLAB':(1.35,.2),'BLOOM':(.48,.48),'BILLET':(.26,.26)}


def roll(model,name,point,width,driver=False):
    model.node(name,position=point)
    barrel=model.cylinder(name+'_surface',.19,width,parent=name,finish='steel')
    # A flush painted face shows rotation without a raised marker hitting the strand.
    barrel.data.materials.append(model.materials['safety'])
    barrel.data.polygons[2].material_index=1
    model.cylinder(name+'_shaft',.075,width+.5,parent=name,finish='dark')
    for z in [-width/2-.18,width/2+.18]:model.box(name+'_bearing_'+str(z),(.32,.32,.22),(point[0],point[1],z),finish='teal')
    if driver:model.motion(Motion(name,'rotation',(0,0,-1),4*math.pi))
    else:model.followers.append({'node_id':name,'driver':'withdrawal_roll','ratio':1,'axis':[0,0,-1],'pivot_m':list(point)})


def caster(model,form):
    width,thickness=SECTION[form]
    model.length,model.width=11,3.8 if form=='SLAB' else 3.2
    model.section=(width,thickness)
    for x in [-4.4,-2.6]:
        for z in [-1.35,1.35]:model.box(f'casting_tower_{x}_{z}',(.28,6.2,.28),(x,3.4,z),finish='blue')
    for x in [-4.4,-2.6]:
        for z in [-1.35,1.35]:model.box(f'casting_tower_foot_{x}_{z}',(.5,.12,.5),(x,.24,z),finish='dark')
    for z in [-.65,.65]:model.box('tundish_saddle_'+str(z),(2.2,.16,.18),(-3.55,5.72,z),finish='steel')
    for x in [-4.4,-2.6]:model.box('tundish_cross_frame_'+str(x),(.22,.25,3),(x,5.65,0),finish='blue')
    # Open tundish and copper water-cooled mold; no baked molten decoration.
    profile(model,'tundish',[(.05,5.8),(.8,5.8),(1,6.65),(.88,6.65),(.68,5.98),(.05,5.98)],position=(-3.55,0,0),finish='ceramic')
    model.cylinder('submerged_entry_nozzle',min(.1,thickness*.25),1.02,(-3.55,5.56,0),finish='ceramic',axis='y')
    model.node('mold_oscillation',position=(-3.55,5.05,0))
    model.box('mold_slide_frame',(thickness+.8,.16,2.35),(0,-.32,0),'mold_oscillation','steel')
    for side in [-1,1]:
        model.box('mold_narrow_'+str(side),(.25,.75,width+.26),(side*(thickness/2+.16),0,0),'mold_oscillation','safety')
        model.box('mold_broad_'+str(side),(thickness+.12,.75,.16),(0,0,side*(width/2+.12)),'mold_oscillation','safety')
    for z in [-1,1]:
        model.cylinder('oscillation_link_'+str(z),.08,.9,(-3.55,4.5,z),finish='steel',axis='y')
        model.tube('mold_coolant_'+str(z),[(-4.15,5.2,z),(-4.5,5.2,z),(-4.5,2,z)],.07,finish='blue')
    model.motion(Motion('mold_oscillation','translation',(0,1,0),.06))
    for i in range(8):
        theta=(i+.2)/8*math.pi/2
        x=.1-3.65*math.cos(theta);y=4.98+thickness/2-3.65*math.sin(theta)
        for side in [-1,1]:
            d=side*(thickness/2+.19)
            point=(x+d*math.cos(theta),y+d*math.sin(theta),0)
            roll(model,f'arc_roll_{i}_{side}',point,width+.25)
    for z in [-width/2-.38,width/2+.38]:
        for side in [-1,1]:
            d=side*(thickness/2+.19)
            points=[(.1-(3.65-d)*math.cos(i/16*math.pi/2),4.98+thickness/2-(3.65-d)*math.sin(i/16*math.pi/2),z) for i in range(17)]
            model.tube(f'arc_frame_{z}_{side}',points,.12,finish='blue')
        model.box('arc_frame_leg_'+str(z),(.22,1.6,.22),(.1,.98,z),finish='blue')
        model.box('arc_frame_top_mount_'+str(z),(2.2,.25,.22),(-3.55,4.7,z),finish='blue')
    roll(model,'withdrawal_roll',(1.6,1.14,0),width+.25,True)
    for i,x in enumerate([.5,2.7,3.8,4.8]):roll(model,'output_roll_'+str(i),(x,1.14,0),width+.25)
    for z in [-width/2-.5,width/2+.5]:model.box('output_beam_'+str(z),(5.5,.3,.2),(2.3,.77,z),finish='blue')
    model.tube('spray_header',[(-3,3.6,-1.2),(-2,2,-1.2),(.1,1.8,-1.2)],.10,finish='blue')
    for i in range(5):model.cylinder('spray_nozzle_'+str(i),.065,.18,(-2.8+i*.55,3.4-i*.35,-1.05),finish='steel')
    platform(model,'casting_service',(-3.5,5.65,1.9,3,.8))
    return [('support','root',(2.4,1.30,0),[form]),('entry','root',(-3.55,6.0,0),['LIQUID_STEEL']),('work','root',(2.4,1.30,0),[form]),('exit','root',(4.7,1.30,0),[form])]


def cutter(model,form):
    width,thickness=SECTION[form]
    model.length,model.width=7.4,max(3.5,width+2)
    for i in range(12):
        x=-3.25+i*.59
        model.cylinder('support_shaft_'+str(i),.065,width+.8,(x,1.17,0),finish='dark')
        model.cylinder('support_roll_'+str(i),.16,width+.35,(x,1.17,0),finish='steel')
        for z in [-width/2-.3,width/2+.3]:model.box(f'roll_bearing_{i}_{z}',(.28,.28,.2),(x,1.17,z),finish='teal')
    for z in [-width/2-.5,width/2+.5]:
        model.box('bed_side_'+str(z),(7,.3,.25),(0,.8,z),finish='blue')
        model.box('bearing_seat_'+str(z),(7,.08,.5),(0,.99,z-.2 if z>0 else z+.2),finish='blue')
        for x in [-2.7,2.7]:model.box(f'table_leg_{z}_{x}',(.18,.47,.18),(x,.415,z),finish='blue')
    if form=='SLAB':
        for z in [-1.25,1.25]:model.box('gantry_leg_'+str(z),(.35,2.7,.35),(0,1.6,z),finish='blue')
        for z in [-1.25,1.25]:model.box('gantry_foot_'+str(z),(.55,.07,.55),(0,.215,z),finish='dark')
        model.box('torch_bridge',(.45,.4,3),(0,3,0),finish='blue')
        model.node('cutting_tool',position=(0,2.8,-.85))
        model.box('torch_carriage',(.55,.35,.5),parent='cutting_tool',finish='safety')
        for x in [-.13,.13]:model.cylinder('torch_barrel_'+str(x),.055,1.2,(x,-.7,0),'cutting_tool','steel',axis='y')
        model.tube('torch_gas_hose',[(0,.15,0),(.3,.5,0),(.3,.6,1.4)],.035,parent='cutting_tool',finish='dark')
        model.motion(Motion('cutting_tool','translation',(0,0,1),1.7))
    else:
        height=3.5 if form=='BLOOM' else 2.7
        for z in [-.85,.85]:model.box('shear_column_'+str(z),(.65,height,.5),(0,height/2+.3,z),finish='blue')
        for z in [-.85,.85]:model.box('shear_column_foot_'+str(z),(.8,.12,.65),(0,.24,z),finish='dark')
        model.box('hydraulic_bridge',(.9,.5,2.2),(0,height,0),finish='blue')
        for z in [-.5,.5]:model.cylinder('shear_cylinder_'+str(z),.2,.9,(0,height-.4,z),finish='safety',axis='y')
        model.node('cutting_tool',position=(0,2.7 if form=='BLOOM' else 2.35,0))
        model.box('knife_crosshead',(.42,.35,1.18),parent='cutting_tool',finish='safety')
        for z in [-.5,.5]:model.cylinder('piston_rod_'+str(z),.09,1,(0,.4,z),'cutting_tool','steel',axis='y')
        verts=[(-.1,-.1,-.5),(.1,-.1,-.5),(.1,-.65,-.5),(-.1,-.65,-.5),(-.1,-.1,.5),(.1,-.1,.5),(.1,-.52,.5),(-.1,-.52,.5)]
        model.node('section_shear_blade',parent='cutting_tool',mesh=model.mesh('section_shear_blade',verts,[(0,3,2,1),(4,5,6,7),(0,1,5,4),(3,7,6,2),(0,4,7,3),(1,2,6,5)]),finish='steel')
        model.box('fixed_lower_die',(.3,.18,width+.12),(.3,1.24,0),finish='dark')
        model.motion(Motion('cutting_tool','translation',(0,-1,0),.78 if form=='BLOOM' else .5))
    for side in [-1,1]:model.box('section_guide_'+str(side),(1.6,.32,.12),(-1,1.58,side*(width/2+.12)),finish='safety')
    return [('support','root',(-1.6,1.30,0),[form]),('entry','root',(-3,1.30,0),[form]),('work','root',(.2,1.30,0),[form]),('exit','root',(3,1.30,0),[form])]
