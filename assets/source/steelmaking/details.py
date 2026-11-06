"""Miniature foundations, real service details and material contact surfaces."""
import math
from geometry import IDENTITY


def foundation(model):
    """Anchor the machine to an individually proportioned concrete plinth."""
    model.box('foundation',(model.length+.6,.18,model.width+.9),(0,.09,0),finish='ceramic')
    for x in [-model.length/2+.5,model.length/2-.5]:
        for z in [-model.width/2+.3,model.width/2-.3]:
            name=f'foot_{x}_{z}'
            model.box(name,(.55,.14,.55),(x,.24,z),finish='dark')
            for d in [-.16,.16]: model.cylinder(name+str(d),.035,.09,(x+d,.35,z),finish='steel',axis='y')
    model.box('control_cabinet',(.5,.9,.4),(model.length/2-.6,.7,-model.width/2+.1),finish='blue')
    model.box('control_cabinet_base',(.55,.07,.45),(model.length/2-.6,.215,-model.width/2+.1),finish='dark')
    for i,finish in enumerate(['red','green','safety']):model.cylinder('control_button_'+str(i),.045,.035,(model.length/2-.73+i*.13,.9,-model.width/2-.12),finish=finish)
    model.box('axis_origin',(.05,.05,.05),finish='dark',bevel=0)
    vertices=[(-.08,-.025,-.025),(-.08,.025,-.025),(-.08,.025,.025),(-.08,-.025,.025),(.14,0,0)]
    model.node('axis_front',position=(1,0,0),mesh=model.mesh('axis_front',vertices,[(0,3,2,1),(0,1,4),(1,2,4),(2,3,4),(3,0,4)]),finish='red')
    model.box('axis_up',(.04,.16,.04),(0,1,0),finish='green',bevel=0)
    model.box('axis_side',(.04,.04,.12),(0,0,-1),finish='axisblue',bevel=0)


def platform(model, name, bounds):
    """Open gratings and safety rails retain the equipment silhouette."""
    x,y,z,l,w=bounds
    model.box(name+'_deck',(l,.1,w),(x,y,z),finish='dark')
    for side in [-1,1]:
        for h in [.5,.9]:model.tube(name+f'_rail_{side}_{h}',[(x-l/2,y+h,z+side*w/2),(x+l/2,y+h,z+side*w/2)],.025,finish='safety')
        for i in range(4):model.cylinder(name+f'_post_{side}_{i}',.025,.9,(x+(i/3-.5)*l,y+.45,z+side*w/2),finish='safety',axis='y')
    for sx in [-1,1]:
        for sz in [-1,1]:
            px,pz=x+sx*(l/2-.2),z+sz*(w/2-.1)
            model.box(name+f'_support_{sx}_{sz}',(.12,y-.18,.12),(px,(y+.18)/2,pz),finish='blue')
            model.box(name+f'_support_pad_{sx}_{sz}',(.35,.18,.35),(px,.09,pz),finish='ceramic')
    if y>2.8:
        lx=x-l/2-.15
        for side in [-1,1]:model.tube(name+'_ladder_rail_'+str(side),[(lx,.18,z+side*w*.3),(lx,y+.8,z+side*w*.3)],.035,finish='steel')
        count=math.ceil((y-.35)/.28)
        for i in range(count):model.cylinder(name+'_ladder_rung_'+str(i),.025,w*.6,(lx,.35+i*(y-.35)/max(1,count-1),z),finish='steel')
        for side in [-1,1]:model.tube(name+'_ladder_bracket_'+str(side),[(lx,y-.1,z+side*w*.3),(x-l/2+.1,y-.1,z+side*w*.3)],.035,finish='steel')
        model.box(name+'_ladder_landing',(.6,.18,w),(lx,.09,z),finish='ceramic')
    else:
        count=math.ceil((y-.18)/.2);rise=(y-.18)/count
        for i in range(count):model.box(name+'_tread_'+str(i),(.25,.08,w*.7),(x-l/2-.2-i*.22,y-rise*(i+.5),z),finish='steel',bevel=.01)
        last_x=x-l/2-.2-(count-1)*.22
        for side in [-1,1]:model.tube(name+'_stair_stringer_'+str(side),[(x-l/2-.2,y-.1,z+side*w*.3),(last_x,.18,z+side*w*.3)],.065,finish='blue')
        model.box(name+'_stair_landing',(.6,.18,w),(last_x,.09,z),finish='ceramic')



def contacts(model, spec):
    """Each socket is on an actual authored surface, never an empty mesh centre."""
    result=[]
    for role,frame,position,form in spec:
        name=role+'_contact'
        model.box(name,(.32,.06,.32),position,parent=frame,finish='steel',bevel=0)
        result.append({'id':role,'node_id':name,'role':role,'transform':{'position_m':[0,.03,0],'rotation_xyzw':list(IDENTITY)},'normal':[0,1,0],'forms':['LIQUID_IRON' if f=='HOT_METAL' else f for f in form],'max_load_kg':60000})
    q=(math.sin(.23),0,0,math.cos(.23))
    model.node('service_bracket',position=(-model.length/2+.6,.6,model.width/2+.2),rotation=q)
    model.box('service_pad',(.4,.12,.4),parent='service_bracket',finish='safety')
    result.append({'id':'service_support','node_id':'service_pad','role':'support','transform':{'position_m':[0,.06,0],'rotation_xyzw':list(IDENTITY)},'normal':[0,1,0],'forms':['PACKAGED'],'max_load_kg':50})
    return result


def profile(model, name, rings, parent='root', position=(0,0,0), finish='teal'):
    """Closed radial cross-section surface for hollow vessels and furnace shells."""
    n=model.segments
    vertices=[(r*math.cos(j*math.tau/n),y,r*math.sin(j*math.tau/n)) for r,y in rings for j in range(n)]
    faces=[]
    for i in range(len(rings)-1):
        for j in range(n):faces.append((i*n+j,(i+1)*n+j,(i+1)*n+(j+1)%n,i*n+(j+1)%n))
    result=model.node(name,parent,position,mesh=model.mesh(name,vertices,faces),finish=finish)
    for polygon in result.data.polygons:polygon.use_smooth=True
    return result
