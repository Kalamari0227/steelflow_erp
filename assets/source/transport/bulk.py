"""Original bulk-material machines with fabricated booms, rollers and operating tools."""
import math
from geometry import Model,Motion,quat


def belt(model: Model,name: str,length: float,parent: str='root',height: float=2.,width: float=1.4,driver: str='belt_feed') -> None:
    """A closed belt housing, drive pulley and separately editable return rollers."""
    model.box(name+'_upper_belt',(length,.09,width),(0.,height,0.),parent,'rubber',bevel=.01)
    model.box(name+'_return_belt',(length,.08,width),(0.,height-.55,0.),parent,'rubber',bevel=.01)
    for x,label in ((-length/2,'tail'),(length/2,'head')):
        anchor=driver if label=='head' else name+'_tail_pulley'
        model.node(anchor,(x,height-.25,0.),parent)
        model.cylinder(anchor+'_drum',.3,width,parent=anchor,finish='steel')
        model.cylinder(anchor+'_shaft',.12,width+.45,parent=anchor,finish='dark')
        if label=='head':model.motion(Motion(driver,'rotation',(0.,0.,1.),math.tau,'work'))
    for i in range(int(length/.9)+1):
        x=-length/2+i*.9
        model.cylinder(name+'_idler'+str(i),.1,width+.1,(x,height-.13,0.),parent,'steel')
        for z in (-width*.6,width*.6):model.box(name+'_stringer'+str(i)+'_'+str(z),(.11,.4,.11),(x,height-.4,z),parent,'blue')
    model.pending.append({'function':'belt_feed','driver':driver,'reason':'Full belt circulation/contact and transported material must be admitted separately; shaft turning is not a custody/flow PASS.'})


def lattice(model: Model,parent: str,length: float) -> None:
    for z in (-.9,.9):
        model.beam('boom_lower_'+str(z),(0.,0.,z),(length,0.,z),.16,parent,'safety')
        model.beam('boom_upper_'+str(z),(0.,1.5,z),(length,1.5,z),.14,parent,'safety')
        for i in range(int(length/2)):
            x=i*2.
            model.beam('boom_diagonal_'+str(z)+'_'+str(i),(x,0.,z),(x+2.,1.5,z),.08,parent,'steel')
            model.beam('boom_upper_cross_'+str(z)+'_'+str(i),(x,1.5,-.9),(x,1.5,.9),.08,parent,'steel')


def bulk_machine(model: Model,kind: str) -> None:
    model.length=25.;model.ground=0.
    if kind=='conveyor':
        model.node('belt_support');model.fixed.append('belt_support')
        for x in (-7.,-3.,1.,5.,9.):
            for z in (-.8,.8):model.box('conveyor_leg_'+str(x)+'_'+str(z),(.18,1.65,.18),(x,.825,z),'belt_support','blue')
        belt(model,'conveyor',18.,height=2.)
        for role,x in (('entry',-8.2),('exit',8.2),('support',0.)):
            model.box(role+'_contact',(.4,.04,1.2),(x,2.065,0.),finish='rubber',bevel=0)
            model.socket(role,role+'_contact',(0.,.02,0.),forms=('ORE','SCRAP','PACKAGED'))
        return
    model.box('crawler_chassis',(6.,.8,5.),(0.,1.,0.),finish='blue')
    for z in (-2.5,2.5):
        model.box('track_'+str(z),(7.,.7,.8),(0.,.5,z),finish='dark',bevel=.25)
        for i,x in enumerate((-2.5,-1.25,0.,1.25,2.5)):model.cylinder('trackroller_'+str(z)+'_'+str(i),.45,.9,(x,.55,z),finish='steel')
    model.cylinder('slew_ring',2.,.45,(0.,1.6,0.),finish='steel',axis='y')
    model.node('boom_slew',(0.,2.,0.))
    model.box('machinery_house',(4.,2.4,3.2),(-1.2,1.6,0.),'boom_slew','blue')
    model.box('control_cabin',(1.7,1.8,1.5),(1.,2.,-2.),'boom_slew','teal')
    model.box('control_glass',(1.2,.8,.04),(1.,2.4,-2.77),'boom_slew','glass')
    model.box('counterweight',(2.5,1.7,4.),(-4.,1.,0.),'boom_slew','dark')
    model.node('boom',(0.,14. if kind=='unloader' else 3.,0.),'boom_slew');lattice(model,'boom',18.)
    if kind=='unloader':
        for z in (-1.,1.):model.box('unloader_tower_'+str(z),(.4,13.,.4),(0.,7.5,z),'boom_slew','safety')
    model.motion(Motion('boom_slew','rotation',(0.,1.,0.),.5,'work'))
    match kind:
        case 'unloader':
            model.node('grab_hoist',(17.,-10.,0.),'boom')
            for z in (-.5,.5):
                sleeve=model.ring('grab_hoist_outer_'+str(z),(.055,.08),6.,(17.,-1.,z),'boom','blue')
                sleeve.rotation_quaternion=quat((0.,0.,math.sqrt(.5),math.sqrt(.5)))
                model.nodes[-1]['transform']['rotation_xyzw']=[0.,0.,math.sqrt(.5),math.sqrt(.5)]
                model.cylinder('grab_hoist_ram_'+str(z),.05,8.,(0.,4.,z),'grab_hoist','steel','y')
            model.box('grab_crosshead',(2.,.25,1.7),(0.,.7,0.),'grab_hoist','safety')
            model.node('grab_open',(-.75,0.,0.),'grab_hoist')
            model.node('grab_right',(.75,0.,0.),'grab_hoist')
            for parent,sign,label in (('grab_open',1.,'left'),('grab_right',-1.,'right')):
                model.box('grab_'+label+'_floor',(.75,.16,1.6),(sign*.375,-.3,0.),parent,'steel',bevel=0)
                model.box('grab_'+label+'_outer_wall',(.15,.8,1.6),(0.,.02,0.),parent,'safety')
                for z in (-.78,.78):model.box('grab_'+label+'_end_'+str(z),(.75,.6,.08),(sign*.375,-.05,z),parent,'steel')
                model.beam('grab_'+label+'_link',(0.,.65,0.),(sign*.2,0.,0.),.1,parent,'safety')
            model.motion(Motion('grab_hoist','translation',(0.,1.,0.),2.,'load'))
            model.motion(Motion('grab_open','rotation',(0.,0.,-1.),.4,'unload'))
            model.followers.append({'node_id':'grab_right','driver':'grab_open','ratio':-1.,'axis':(0.,0.,-1.)})
            model.socket('grip','grab_left_floor',(.375,.08,0.),forms=('ORE','SCRAP'),capacity=30000)
            model.socket('load','grab_left_floor',(.375,.08,0.),forms=('ORE','SCRAP'),capacity=30000)
        case 'stacker'|'reclaimer':
            belt(model,'boom_belt',17.,'boom',.45,1.2)
            model.box('transfer_chute',(1.6,1.6,1.5),(17.,-.4,0.),'boom','blue')
            model.socket('load','boom_belt_upper_belt',(0.,.045,0.),forms=('ORE',),capacity=50000)
            if kind=='reclaimer':
                model.node('bucket_wheel',(18.,-.5,0.),'boom')
                model.cylinder('wheel_disk',1.8,.35,parent='bucket_wheel',finish='safety')
                for i in range(10):
                    a=i*math.tau/10
                    model.box('bucket_'+str(i),(.7,.5,.9),(1.9*math.cos(a),1.9*math.sin(a),0.),'bucket_wheel','steel',bevel=.1)
                model.motion(Motion('bucket_wheel','rotation',(0.,0.,1.),math.tau,'work'))
        case unknown:raise RuntimeError('Unknown bulk machine '+unknown)
    model.socket('support','crawler_chassis',(0.,.4,0.),forms=('PACKAGED',),capacity=100000)


def harbour_crane(model: Model) -> None:
    """Actual slew pedestal and lattice jib; policy remains a separate candidate."""
    model.length=28.;model.ground=0.
    model.box('quay_base',(5.,.5,5.),(0.,.25,0.),finish='dark')
    model.cylinder('portal_tower',1.6,6.,(0.,3.5,0.),finish='blue',axis='y')
    model.node('boom_slew',(0.,6.5,0.));lattice(model,'boom_slew',20.)
    model.box('rear_counterweight',(4.,2.5,4.),(-4.,1.8,0.),'boom_slew','dark')
    model.box('operator_cabin',(2.,2.,2.),(1.,1.8,-2.),'boom_slew','teal')
    model.node('hoist',(19.,-2.,0.),'boom_slew')
    model.cylinder('load_hook_shank',.08,2.,(0.,0.,0.),'hoist','steel','y')
    model.box('hook_contact',(.5,.12,.5),(0.,-1.,0.),'hoist','steel',bevel=0)
    model.motion(Motion('boom_slew','rotation',(0.,1.,0.),.6,'load'));model.motion(Motion('hoist','translation',(0.,1.,0.),2.,'load'))
    model.socket('support','quay_base',(0.,.25,0.),forms=('PACKAGED',),capacity=100000)
    model.socket('grip','hook_contact',(0.,.06,0.),forms=('COIL','SLAB','PACKAGED'),capacity=50000)
