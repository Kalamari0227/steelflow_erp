"""Original railway stock with finite bogie, coupler and hot-vessel assemblies."""
import math
from geometry import Model,Motion


def bogies(model: Model,length: float,width: float) -> None:
    """Two actual pivoted bogies and four separate axles per vehicle."""
    for index,x in enumerate((-length*.33,length*.33)):
        name='bogie_rotation' if index==0 else 'rear_bogie'
        model.node(name,(x,.8,0.))
        model.box(name+'_frame',(3.,.35,width*.8),parent=name,finish='dark')
        for axle,dx in enumerate((-1.05,1.05)):
            model.cylinder(name+f'_axle{axle}',.13,width,(dx,-.18,0.),name,'steel')
            for z in (-width*.4,width*.4):
                model.cylinder(name+f'_wheel{axle}_{z}',.6,.16,(dx,-.18,z),name,'dark')
                model.cylinder(name+f'_flange{axle}_{z}',.65,.055,(dx,-.18,z*.96),name,'steel')
                model.box(name+f'_spring{axle}_{z}',(.5,.15,.18),(dx,.1,z*.8),name,'steel')
        if index==0:model.motion(Motion(name,'rotation',(0.,1.,0.),.18,'travel'))
        else:model.followers.append({'node_id':name,'driver':'bogie_rotation','ratio':-1.,'axis':(0.,1.,0.)})
    model.node('coupler')
    for x,label in ((-length/2,'rear'),(length/2,'front')):
        model.box(label+'_coupler_shank',(.8,.2,.25),(x,1.,0.),'coupler','steel')
        model.box(label+'_coupler_head',(.28,.38,.5),(x+(.4 if x>0 else -.4),1.,0.),'coupler','dark')
        model.socket(label+'_coupling',label+'_coupler_head',(0.,.19,0.),role='coupler',forms=('PACKAGED',))
    model.socket('coupler','front_coupler_head',(0.,.19,0.),forms=('PACKAGED',))


def rail_vehicle(model: Model,kind: str) -> None:
    model.ground=0.;length=30. if kind=='torpedo' else 15. if kind=='ladle-car' else 20.;width=5. if kind=='torpedo' else 6. if kind=='ladle-car' else 4.
    model.length=length
    bogies(model,length,width)
    model.box('main_underframe',(length-.8,.4,width-.4),(0.,1.4,0.),finish='blue')
    match kind:
        case 'torpedo':
            model.node('vessel_tilt',(0.,4.,0.))
            # Faceted tapered torpedo shell rather than a box or generic cylinder.
            vertices=[];faces=[];n=model.segments
            rings=[(-10.,.9),(-7.,2.2),(7.,2.2),(10.,.9)]
            for x,r in rings:
                for i in range(n):vertices.append((x,r*math.cos(i*math.tau/n),r*math.sin(i*math.tau/n)))
            for r in range(3):
                for i in range(n):j=(i+1)%n;faces.append((r*n+i,r*n+j,(r+1)*n+j,(r+1)*n+i))
            faces += [tuple(range(n-1,-1,-1)),tuple(range(3*n,4*n))]
            model.node('hot_metal_vessel',parent='vessel_tilt',mesh=model.mesh('hot_metal_vessel',vertices,faces),finish='dark')
            model.fixed.append('hot_metal_vessel');model.relative_fixed['hot_metal_vessel']='vessel_tilt'
            model.cylinder('charge_throat',.8,1.,(0.,2.,0.),'vessel_tilt','steel','y')
            for x in (-7.5,7.5):
                model.cylinder('trunnion_'+str(x),.6,1.2,(x,4.,0.),axis='x')
                model.box('vessel_pedestal_'+str(x),(1.6,2.5,3.),(x,2.65,0.),finish='safety')
            model.motion(Motion('vessel_tilt','rotation',(1.,0.,0.),.65,'unload'))
            model.socket('support','charge_throat',(0.,.5,0.),forms=('LIQUID_IRON',),capacity=300000)
            model.socket('load','charge_throat',(0.,.5,0.),forms=('LIQUID_IRON',),capacity=300000)
        case 'ladle-car':
            model.node('ladle_support',(0.,1.85,0.));model.fixed.append('ladle_support')
            model.box('ladle_seat',(6.,.5,5.),parent='ladle_support',finish='safety')
            model.ring('ladle_shell',(1.5,1.8),3.2,(0.,3.5,0.),finish='dark')
            vessel=model.objects['ladle_shell'];from geometry import quat
            vessel.rotation_quaternion=quat((0.,0.,math.sqrt(.5),math.sqrt(.5)));model.nodes[-1]['transform']['rotation_xyzw']=[0.,0.,math.sqrt(.5),math.sqrt(.5)]
            for z in (-1.95,1.95):model.cylinder('ladle_lug_'+str(z),.3,.5,(0.,3.5,z),finish='steel')
            model.socket('support','ladle_seat',(0.,.25,0.),forms=('LIQUID_STEEL',),capacity=150000)
            model.socket('load','ladle_seat',(0.,.25,0.),forms=('LIQUID_STEEL',),capacity=150000)
        case 'locomotive':
            model.fixed.append('coupler')
            model.box('engine_hood',(11.,2.8,2.9),(-1.,3.,0.),finish='teal')
            model.box('driver_cabin',(3.,3.5,3.5),(6.,3.3,0.),finish='blue')
            for z in (-1.76,1.76):model.box('driver_glass_'+str(z),(2.3,1.,.03),(6.,4.1,z),finish='glass')
            model.box('cabin_front_glass',(.03,1.,2.7),(7.52,4.1,0.),finish='glass')
            for x in (-4.,0.,3.):model.cylinder('roof_fan_'+str(x),.6,.12,(x,4.46,0.),axis='y')
            model.cylinder('diesel_exhaust',.15,.8,(-2.,4.7,0.),finish='dark',axis='y')
            for z in (-1.85,1.85):
                model.box('walkway_'+str(z),(17.,.12,.45),(0.,1.75,z),finish='steel')
                model.beam('handrail_'+str(z),(-8.,2.8,z),(8.,2.8,z),.045)
                for i,x in enumerate((-8.,-5.,-2.,1.,4.,7.)):model.beam('railpost_'+str(z)+'_'+str(i),(x,1.8,z),(x,2.8,z),.035)
            model.socket('support','walkway_-1.85',(0.,.06,0.),forms=('PACKAGED',),capacity=1000)
        case 'railcar':
            model.node('load_deck',(0.,1.9,0.));model.fixed += ['load_deck','coupler']
            model.box('deck',(18.5,.4,3.6),parent='load_deck',finish='steel')
            for x in range(-8,9,2):
                for z in (-1.9,1.9):model.box('stake_'+str(x)+'_'+str(z),(.12,1.,.12),(float(x),2.6,z),finish='safety')
            model.socket('support','deck',(0.,.2,0.),forms=('SLAB','COIL','PACKAGED'),capacity=80000)
            model.socket('load','deck',(0.,.2,0.),forms=('SLAB','COIL','PACKAGED'),capacity=80000)
        case unknown:raise RuntimeError('Unknown rail stock '+unknown)
