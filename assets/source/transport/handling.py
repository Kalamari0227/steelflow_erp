"""Real gantry, eye C-hook and independent coil-receiving cradle assemblies."""
import math
from geometry import Model, Motion, quat


def i_beam(model: Model,name: str,length: float,center: tuple[float,float,float],parent: str='root',axis: str='z') -> None:
    """Fabricated I profile retains flanges and web as separate editable solids."""
    x,y,z=center
    for dy,label in ((-.27,'lower'),(.27,'upper')):
        size=(.45,.08,length) if axis=='z' else (length,.08,.45)
        model.box(name+'_'+label,size,(x,y+dy,z),parent,'safety')
    size=(.1,.5,length) if axis=='z' else (length,.5,.1)
    model.box(name+'_web',size,center,parent,'safety')


def gantry(model: Model,overhead: bool=False,tool: str='eye-c-hook') -> None:
    """Bridge Z, trolley X and independent vertical hoist with genuine tool geometry."""
    model.length=18.;model.ground=0.
    for x,label in ((-3.,'west'),(3.,'east')):
        for z,end in ((-3.3,'south'),(9.3,'north')):
            if not overhead:
                model.box(label+'_'+end+'_foot',(1.2,.3,1.2),(x,.15,z),finish='dark')
                model.box(label+'_'+end+'_column',(.4,7.,.4),(x,3.5,z),finish='safety')
                model.beam(label+'_'+end+'_brace',(x,5.8,z),(x+(-.7 if x<0 else .7),6.8,z),.09,finish='steel')
            model.box(label+'_'+end+'_rail_cap',(.48,.16,1.),(x,7.,z),finish='steel')
        i_beam(model,label+'_runway',13.,(x,6.85,3.))
        model.box(label+'_running_rail',(.09,.12,13.),(x,7.2,3.),finish='steel')
    model.node('bridge_travel')
    for z,label in ((-.6,'south'),(.6,'north')):
        i_beam(model,'bridge_'+label,6.4,(0.,7.6,z),'bridge_travel','x')
        for x,end in ((-3.,'west'),(3.,'east')):
            model.cylinder('bridge_'+label+'_'+end+'_roller',.22,.3,(x,7.48,z),'bridge_travel','dark')
    model.node('trolley_travel',(-1.6,0.,0.),'bridge_travel')
    model.node('trolley_frame',parent='trolley_travel')
    for x in (-.7,.7):model.box('trolley_longeron_'+str(x),(.2,.25,1.7),(x,8.035,0.),'trolley_frame','blue')
    for z in (-.7,.7):model.box('trolley_crossmember_'+str(z),(1.6,.25,.2),(0.,8.035,z),'trolley_frame','blue')
    model.box('hydraulic_crosshead',(1.6,.3,.5),(0.,8.95,0.),'trolley_travel','blue')
    model.box('hydraulic_power_pack',(.7,.5,.6),(1.2,8.15,0.),'trolley_travel','dark')
    model.node('hoist',parent='trolley_travel')
    # Actual nested hydraulic columns: fixed outer sleeves, sliding steel rams.
    # No moving full-length rope or visual cable extension substitutes for support.
    for x in (-.32,.32):
        sleeve=model.ring('hoist_outer_'+str(x),(.078,.105),2.3,(x,7.65,0.),'trolley_travel','blue')
        sleeve.rotation_quaternion=quat((0.,0.,math.sqrt(.5),math.sqrt(.5)))
        model.nodes[-1]['transform']['rotation_xyzw']=[0.,0.,math.sqrt(.5),math.sqrt(.5)]
        model.cylinder('hoist_ram_'+str(x),.075,2.6,(x,5.5,0.),'hoist','steel','y')
    model.box('hook_block',(.85,.3,.45),(0.,4.3,0.),'hoist','safety')
    model.ring('suspension_bail',(.12,.19),.15,(0.,4.05,0.),'hoist','steel')
    if tool=='eye-c-hook':
        # Arm top atY2.9 meets the upper inner bore of a1.2m OD/.6m ID coil.
        model.box('c_hook_spine',(.24,1.4,.32),(-.82,3.2,0.),'hoist','safety',bevel=.08)
        model.box('c_hook_upper_arm',(1.97,.22,.32),(.09,3.8,0.),'hoist','safety',bevel=.07)
        model.cylinder('c_hook_load_arm',.10,1.35,(-.18,2.8,0.),'hoist','steel','x')
        model.box('c_hook_counterweight',(.45,.6,.6),(.85,3.55,0.),'hoist','dark',bevel=.1)
        model.beam('guide_handle',(-.95,3.,-.28),(-.95,3.45,-.28),.04,'hoist','steel')
        model.socket('grip','hoist',(0.,2.9,0.),forms=('COIL',))
    else:
        model.box('fork_spine',(.75,1.1,.2),(0.,2.55,-.9),'hoist','safety')
        model.box('fork_upper',(.75,.18,1.1),(0.,3.1,-.4),'hoist','safety')
        for x in (-.15,.15):model.box('suspended_prong_'+str(x),(.12,.12,1.65),(x,1.94,-.12),'hoist','steel',bevel=.005)
        model.socket('grip','hoist',(0.,2.,0.),forms=('COIL',))
    model.socket('support','west_south_rail_cap' if overhead else 'west_south_foot',(0.,.08 if overhead else .15,0.),forms=('PACKAGED',),capacity=100000)
    model.socket('pick','hoist',(0.,2.9 if tool=='eye-c-hook' else 2.,0.),role='grip',forms=('COIL',))
    model.socket('drop','hoist',(0.,2.9 if tool=='eye-c-hook' else 2.,0.),role='grip',forms=('COIL',))
    model.motion(Motion('bridge_travel','translation',(0.,0.,1.),6.,'unload'))
    model.motion(Motion('trolley_travel','translation',(1.,0.,0.),1.6,'load'))
    model.motion(Motion('hoist','translation',(0.,1.,0.),2.,'unload'))
    for i in range(16):model.box('maintenance_rung_'+str(i),(.55,.055,.055),(-3.25,.4+i*.4,-3.25),finish='steel')
    model.box('electrical_cabinet',(.55,.95,.45),(-3.,1.,-3.6),finish='blue')


def cradle(model: Model,fork_access: bool=False) -> None:
    """Independent stationary saddle with real floor-to-coil load path and no motion."""
    model.length=2.5;model.ground=0.
    model.node('coil_saddle');model.fixed.append('coil_saddle')
    for x in (-.7,.7):
        model.box('foot_'+str(x),(.45,.16,1.65),(x,.08,0.),'coil_saddle','dark')
        for z in (-.65,.65):model.box('leg_'+str(x)+'_'+str(z),(.18,1.5,.18),(x,.85,z),'coil_saddle','blue')
    model.box('underframe',(1.8,.2,1.5),(0.,1.65,0.),'coil_saddle','blue')
    # Two finite saddle plates support the exact bottom tangent; axial central gap
    # is real hardware access rather than invisible contact/collision exclusion.
    for x in (-.45,.45):
        model.box('saddle_pad_'+str(x),(.3,.25,.48),(x,1.875,0.),'coil_saddle','steel',bevel=0)
        for z in (-.62,.62):model.box('roll_retainer_'+str(x)+'_'+str(z),(.3,.35,.14),(x,1.975,z),'coil_saddle','safety',bevel=.02)
    model.node('support_surface',(0.,2.,0.),'coil_saddle')

    if not fork_access:
        model.box('center_contact',(.6,.12,.3),(0.,1.94,0.),'coil_saddle','steel',bevel=0)
        model.socket('support','center_contact',(0.,.06,0.),forms=('COIL',),capacity=40000)
        model.socket('load','center_contact',(0.,.06,0.),forms=('COIL',),capacity=40000)
