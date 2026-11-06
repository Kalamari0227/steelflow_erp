"""Original miniature product/bulk vessel with actual holds, hull and propulsion."""
import math
from geometry import Model,Motion


def ship(model: Model,bulk: bool=False) -> None:
    model.length=150.;model.ground=-.1
    # Closed shell sections: taper at stern/bow and broad midship, with a deck rim.
    sections=[(-72.,2.5,5.),(-60.,13.,0.),(-42.,15.,0.),(48.,15.,0.),(65.,7.,3.),(75.,.25,11.)]
    vertices=[];faces=[]
    for x,w,keel in sections:vertices += [(x,keel,-w*.55),(x,keel,w*.55),(x,16.,w),(x,16.,-w)]
    for i in range(len(sections)-1):
        for j in (0,1,3):faces.append((i*4+j,i*4+(j+1)%4,(i+1)*4+(j+1)%4,(i+1)*4+j))
    faces += [(3,2,1,0),tuple(range((len(sections)-1)*4,len(sections)*4))]
    model.node('hull_shell',mesh=model.mesh('hull_shell',vertices,faces),finish='blue')
    # Actual cargo floor and separate coamings leave visibly deep open holds.
    model.node('cargo_hold');model.fixed.append('cargo_hold')
    model.box('cargo_floor',(102.,.5,23.),(1.,14.75,0.),'cargo_hold','steel')
    for x in (-49.,-15.,19.,52.):model.box('hold_bulkhead_'+str(x),(.5,2.3,24.),(x,16.15,0.),'cargo_hold','dark')
    for z in (-12.,12.):model.box('hold_coaming_'+str(z),(102.,2.3,.5),(1.,16.15,z),'cargo_hold','dark')
    for z in (-13.6,13.6):
        model.box('side_deck_'+str(z),(124.,.4,2.1),(0.,16.2,z),finish='teal')
        model.beam('upper_guard_'+str(z),(-58.,17.5,z),(58.,17.5,z),.09)
        for i,x in enumerate(range(-58,59,6)):model.beam('guardpost_'+str(z)+'_'+str(i),(float(x),16.2,z),(float(x),17.5,z),.065)
    model.box('aft_deck',(15.,.6,23.),(-60.,16.,0.),finish='teal')
    model.box('accommodation',(12.,7.,15.),(-58.,20.,0.),finish='white')
    model.box('navigation_bridge',(14.,3.,22.),(-57.,25.,0.),finish='white')
    for i,z in enumerate(range(-9,10,3)):model.box('bridge_window_'+str(i),(.05,1.2,2.4),(-49.95,25.4,float(z)),finish='glass')
    for z in (-7.6,7.6):
        for x in (-61.,-57.,-53.):model.box('cabin_porthole_'+str(x)+'_'+str(z),(.9,.85,.04),(x,21.,z),finish='glass')
    model.box('funnel',(3.,5.,4.),(-63.,25.,0.),finish='safety')
    model.cylinder('mast',.15,8.,(-54.,30.,0.),finish='steel',axis='y')
    model.beam('radar_yard',(-54.,32.,-5.),(-54.,32.,5.),.12)
    for z in (-10.,10.):
        model.box('lifeboat_'+str(z),(5.,1.1,1.8),(-60.,21.,z),finish='safety',bevel=.35)
        model.cylinder('mooring_bollard_'+str(z),.3,1.2,(60.,17.,z),axis='y')
    model.node('propulsion',(-70.,3.,0.))
    model.cylinder('propeller_hub',.55,2.,parent='propulsion',axis='x')
    for i in range(4):
        a=i*math.pi/2;blade=model.box('propeller_blade'+str(i),(.25,2.7,.65),(0.,1.5*math.cos(a),1.5*math.sin(a)),'propulsion','steel',bevel=.25)
        from geometry import quat
        blade.rotation_quaternion=quat((math.sin(a/2),0.,0.,math.cos(a/2)));model.nodes[-1]['transform']['rotation_xyzw']=[math.sin(a/2),0.,0.,math.cos(a/2)]
    model.node('rudder',(-73.,3.,0.));model.box('rudder_blade',(2.,4.,.3),parent='rudder',finish='dark')
    model.motion(Motion('propulsion','rotation',(1.,0.,0.),math.tau,'travel'))
    model.motion(Motion('rudder','rotation',(0.,1.,0.),.35,'travel'))
    model.socket('support','cargo_floor',(0.,.25,0.),forms=('ORE','COIL','SLAB','PACKAGED'),capacity=20000000)
    model.socket('load','cargo_floor',(0.,.25,0.),forms=('ORE','COIL','SLAB','PACKAGED'),capacity=20000000)
    if bulk:
        # Hatch-cover pairs remain editable hardware, not hidden closed boxes.
        for i,x in enumerate((-32.,2.,36.)):
            for z in (-8.5,8.5):model.box('folded_hatch_'+str(i)+'_'+str(z),(25.,.5,4.),(x,17.6,z),finish='safety')
