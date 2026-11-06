"""Open refractory vessels with physical trunnions, lance guides and EAF roof clearance."""
import math
import bpy
from geometry import Motion
from details import profile,platform


def trunnions(model, height, radius):
    for z,side in [(-radius-.28,'near'),(radius+.28,'far')]:
        model.box(side+'_pedestal_foot',(.95,.12,.9),(0,.24,z),finish='dark')
        model.box(side+'_pedestal',(.8,height-.3,.75),(0,(height+.3)/2,z),finish='blue')
        model.cylinder(side+'_bearing',.4,.35,(0,height,z),finish='safety')
        model.cylinder(side+'_trunnion',.21,.7,(0,height,z),finish='steel')
    model.cylinder('tilt_gearbox',.58,.45,(0,height,-radius-.8),finish='dark')
    for i in range(5):model.box('gearbox_fin_'+str(i),(.72,.04,.52),(0,height-.25+i*.12,-radius-.8),finish='teal')


def shell(model, kind, scale=1):
    model.node('vessel_tilt',position=(0,2.5,0))
    rings=[(.05,-1.6),(1.05,-1.6),(1.55,-.8),(1.6,.8),(1.2,1.7),(.84,2.05),(.84,2.22),(.68,2.22),(.68,2.0),(1.02,1.6),(1.4,.7),(1.35,-.6),(.9,-1.35),(.05,-1.35)]
    if kind=='eaf':rings=[(.05,-1.5),(1.3,-1.5),(1.65,-.7),(1.65,.8),(1.5,1.1),(1.5,1.3),(1.32,1.3),(1.32,.9),(1.45,-.6),(1.15,-1.25),(.05,-1.25)]
    profile(model,'refractory_vessel',[(r*scale,y*scale) for r,y in rings],parent='vessel_tilt',finish='teal')
    if kind=='eaf':
        lining=[(.05,-1.24),(1.12,-1.24),(1.42,-.59),(1.29,.90),(1.29,1.28),(1.46,1.28),(1.46,1.35),(1.24,1.35),(1.24,.90),(1.38,-.58),(1.10,-1.22),(.05,-1.22),(.05,-1.24)]
        profile(model,'refractory_lining',[(r*scale,y*scale) for r,y in lining],parent='vessel_tilt',finish='ceramic')
        # Outward bands join the continuous shell at boundary edges; no duplicate rear face.
        for y in [-.7,.65]:profile(model,'vessel_hoop_'+str(y),[(1.65*scale,y*scale),(1.74*scale,y*scale),(1.74*scale,y*scale+.12),(1.65*scale,y*scale+.12)],parent='vessel_tilt',finish='steel')
    else:
        inner=[(r*scale-.04,y*scale) for r,y in rings[-7:]]
        profile(model,'refractory_lining',inner,parent='vessel_tilt',finish='ceramic')
        for y,r in [(-.7,1.6),(.65,1.65)]:profile(model,'vessel_hoop_'+str(y),[(r*scale,y*scale),(r*scale,y*scale+.12),((r-.08)*scale,y*scale+.12),((r-.08)*scale,y*scale)],parent='vessel_tilt',finish='steel')
    model.box('tap_spout',(.9,.18,.45),(1.7*scale,.1,0),'vessel_tilt','ceramic')
    for z in [-1,1]:model.box('trunnion_mount_'+str(z),(.75,.6,.35),(0,0,z*1.55*scale),'vessel_tilt','dark')
    model.motion(Motion('vessel_tilt','rotation',(0,0,-1),.95))
    model.interior.append('refractory_lining')
    trunnions(model,2.5,1.65*scale)


def converter(model, kind, plate=False):
    model.length,model.width=8.5,6.7
    scale=1.10 if plate else 1
    shell(model,kind,scale)
    if kind=='bof':
        for z in [-2.2,2.2]:model.box('lance_tower_'+str(z),(.3,8.5,.3),(-2.7,4.6,z),finish='blue')
        model.box('lance_crosshead',(.6,.45,4.9),(-2.7,8.4,0),finish='dark')
        model.box('lance_linear_guide',(.25,8.5,.35),(-2.7,4.6,0),finish='steel')
        model.node('oxygen_lance',position=(0,2.0,0))
        model.cylinder('oxygen_pipe',.105,3.5,(0,1.75,0),'oxygen_lance','steel',axis='y')
        model.cylinder('copper_lance_tip',.14,.35,(0,.1,0),'oxygen_lance','safety',axis='y')
        model.box('lance_carriage',(.7,.6,.7),(-2.2,3.0,0),'oxygen_lance','blue')
        model.box('lance_cantilever',(2.6,.22,.35),(-1.1,3.0,0),'oxygen_lance','safety')
        model.tube('oxygen_supply_trunk',[(-2.7,3.2,.4),(-2.7,8.4,.4)],.09,finish='safety')
        model.tube('oxygen_sliding_feed',[(-2.7,3,.4),(-1.2,3.5,.4),(0,3.5,0)],.08,parent='oxygen_lance',finish='steel')
        model.motion(Motion('oxygen_lance','translation',(0,1,0),3.0))
        platform(model,'lance_service',(-2.7,5.5,2.6,3,.8))
    else:
        model.node('gas_tuyere',parent='vessel_tilt',position=(-1.45,-.65,0))
        for i in range(3):model.cylinder('gas_injector_'+str(i),.10,.7,(0,0,(i-1)*.38),'gas_tuyere','steel',axis='x')
        model.tube('argon_manifold',[(-2.6,1.9,-1.7),(-2.6,1.9,1.7)],.12,finish='safety')
        model.box('gas_valve_bank',(.75,.85,.45),(-2.6,.8,-2),finish='blue')
        for z in [-2.15,-1.85]:model.box('gas_cabinet_leg_'+str(z),(.15,.195,.12),(-2.6,.2775,z),finish='dark')
        platform(model,'aod_service',(-2,3.6,2.5,3.2,.8))
    return [('support','root',(0,.4,0),['HOT_METAL','LIQUID_STEEL']),('entry','vessel_tilt',(0,-1.35*scale+.03,0),['HOT_METAL','LIQUID_STEEL']),('work','vessel_tilt',(0,-1.35*scale+.03,0),['HOT_METAL','LIQUID_STEEL']),('exit','vessel_tilt',(2.1*scale,.1,0),['LIQUID_STEEL'])]


def electrodes(model, parent, position, lift):
    model.node('electrode_lift',parent=parent,position=position)
    length=4.8
    back,span={'roof_swing':(-1.5,2.3),'root':(-1.9,4.1)}[parent]
    model.box('electrode_carrier',(1.9,.22,1.7),(0,length-.05,0),'electrode_lift','safety')
    model.box('electrode_slide_carriage',(.5,.65,span),(back+.45,length-.05,0),'electrode_lift','blue')
    model.box('electrode_cantilever',(abs(back+.45)+.6,.22,.35),((back+.45)/2,length-.05,0),'electrode_lift','safety')
    half_width=.125 if parent=='roof_swing' else .15
    for side in [-1,1]:model.box('guide_slide_pad_'+str(side),(.08,.4,.28),(back+half_width+.04,length-.05,side*(.95 if parent=='roof_swing' else 1.8)),'electrode_lift','ceramic',bevel=.01)
    for i in range(3):
        angle=i*math.tau/3
        x,z=.56*math.cos(angle),.56*math.sin(angle)
        model.cylinder('graphite_electrode_'+str(i),.13,length,(x,length/2,z),'electrode_lift','dark',axis='y')
        model.cylinder('copper_clamp_'+str(i),.19,.28,(x,length-.35,z),'electrode_lift','steel',axis='y')
        model.tube('electrode_bus_'+str(i),[(x,length-.1,z),(back+.45,length-.1,z),(back+.45,length-.1,z-1.5)],.07,parent='electrode_lift',finish='safety')
    model.motion(Motion('electrode_lift','translation',(0,1,0),lift))


def eaf(model, plate=False):
    model.length,model.width=9.5,7.5
    scale=1.1 if plate else 1
    shell(model,'eaf',scale)
    model.node('roof_swing',position=(-2.8,4.2,0))
    model.box('roof_column_base',(.9,.22,.9),(-2.8,.29,0),finish='dark')
    model.cylinder('roof_pivot_column',.3,3.8,(-2.8,2.3,0),finish='blue',axis='y')
    model.box('roof_swing_arm',(3.1,.3,.42),(1.3,.2,0),'roof_swing','safety')
    roof=model.cylinder('roof_shell',1.65,.28,(2.8,.06,0),'roof_swing','ceramic',axis='y')
    for i in range(3):
        angle=i*math.tau/3;name='roof_bore_tool_'+str(i)
        cutter=model.cylinder(name,.2,.9,(2.8+.56*math.cos(angle),.06,.56*math.sin(angle)),'roof_swing','steel',axis='y')
        bpy.context.view_layer.update();modifier=roof.modifiers.new('actual_electrode_bore_'+str(i),'BOOLEAN');modifier.operation='DIFFERENCE';modifier.solver='EXACT';modifier.object=cutter
        bpy.context.view_layer.objects.active=roof;roof.select_set(True);bpy.ops.object.modifier_apply(modifier=modifier.name);roof.select_set(False)
        bpy.data.objects.remove(cutter,do_unlink=True);model.objects.pop(name);model.nodes=[n for n in model.nodes if n['id']!=name]

    profile(model,'roof_water_jacket',[(1.58,-.13),(1.76,-.13),(1.76,.08),(1.58,.08),(1.58,-.13)],parent='roof_swing',position=(2.8,0,0),finish='steel')
    for z in [-.95,.95]:model.box('roof_electrode_guide_'+str(z),(.25,4.6,.25),(1.3,3.5,z),'roof_swing','blue')
    electrodes(model,'roof_swing',(2.8,-2.65,0),3.0)
    model.motion(Motion('roof_swing','rotation',(0,1,0),2.1))
    model.roofs.append('roof_shell');model.interior.append('graphite_electrode_0')
    model.box('transformer_plinth',(1.6,.12,1.5),(-3,.24,-2.5),finish='dark')
    model.box('transformer_cabinet',(1.4,2.8,1.25),(-3,1.7,-2.5),finish='blue')
    for i in range(7):model.box('transformer_rib_'+str(i),(.10,2.2,1.45),(-3.55+i*.18,1.7,-2.5),finish='teal')
    platform(model,'eaf_service',(0,3.4,2.5,4.5,.85))
    return [('support','root',(0,.4,0),['SCRAP','LIQUID_STEEL']),('entry','vessel_tilt',(0,-1.25*scale+.03,0),['SCRAP']),('work','vessel_tilt',(0,-1.25*scale+.03,0),['SCRAP','LIQUID_STEEL']),('exit','vessel_tilt',(2.1,.1,0),['LIQUID_STEEL'])]


def ladle_furnace(model):
    model.length,model.width=7.5,6.5
    model.node('ladle_support',position=(0,.55,0))
    for z in [-.95,.95]:model.box('ladle_cradle_'+str(z),(3.8,.5,.4),(0,0,z),'ladle_support','blue')
    for z in [-1.8,1.8]:model.box('electrode_mast_'+str(z),(.3,9.0,.3),(-1.9,4.8,z),finish='blue')
    model.box('mast_bridge',(.6,.4,4.1),(-1.9,9.3,0),finish='dark')
    electrodes(model,'root',(0,1.45,0),2.2)
    profile(model,'refining_roof',[(.85,3.5),(1.55,3.5),(1.48,3.75),(.85,3.75),(.85,3.5)],finish='steel')
    model.roofs.append('refining_roof');model.interior.append('graphite_electrode_0')
    platform(model,'lf_service',(-1.7,3.6,2.5,3,.8))
    return [('support','ladle_support',(.1,.22,0),['LIQUID_STEEL']),('entry','root',(0,1.11,0),['LIQUID_STEEL']),('work','root',(0,1.11,0),['LIQUID_STEEL']),('exit','root',(0,1.11,0),['LIQUID_STEEL'])]
