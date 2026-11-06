"""Original hot/bloom/rod reduction stands with independent physical roll pivots."""
import math
from mathutils import Vector
from details import table, rails
from geometry import Motion


def rolling(model, kind, wire=False, plate=False):
    names={'roughing':'roughing_roll','finishing_mill':'finishing_roll','bloom_mill':'bloom_roll','wire_mill':'wire_reduction_roll','leveler':'leveling_roll'}
    function=names[kind]
    count={'roughing':1,'finishing_mill':4,'bloom_mill':2,'wire_mill':6,'leveler':1}[kind]
    if model.key=='HSM-B':
        count=5
    model.length=10 if count<3 else 14 if count==5 else 12
    model.width=1.15 if wire else 4.2 if plate else 3.0
    w=model.width
    gap=((count-1)*(1.45 if wire else 2.0))/2 + (2.0 if kind=='leveler' else .85)
    table(model,-model.length/2+.4,-gap,w,'entry_table')
    table(model,gap,model.length/2-.4,w,'exit_table')
    stand_width=4.2 if kind=='leveler' else 1.05 if wire else 1.25
    stand_height=2.5 if wire or kind=='leveler' else 3.9
    radius=.20 if wire else .46 if plate else .38
    model.drive_radius=.18 if kind=='leveler' else radius
    locations=[(i-(count-1)/2)*(1.45 if wire else 2.0) for i in range(count)]
    for i,x in enumerate(locations):
        for z,side in [(-w/2-.4,'left'),(w/2+.4,'right')]:
            model.box(f'stand_{i}_{side}_foot',(stand_width+.4,.22,.8),(x,.35,z),finish='dark')
            for dx,label in [(-stand_width/2+.12,'in'),(stand_width/2-.12,'out')]:
                model.box(f'stand_{i}_{side}_{label}_column',(.24,stand_height-.4,.38),(x+dx,stand_height/2+.2,z),finish='teal')
            model.box(f'stand_{i}_{side}_cap',(stand_width,.35,.48),(x,stand_height,z),finish='blue')
            model.cylinder(f'stand_{i}_{side}_screw',.09,.8,(x,stand_height-.2,z),finish='steel',axis='y')
            model.cylinder(f'stand_{i}_{side}_adjuster',.21,.12,(x,stand_height+.15,z),finish='safety',axis='y')
            for j,dx in enumerate([-.18,.18]):
                model.cylinder(f'stand_{i}_{side}_bolt_{j}',.045,.1,(x+dx,stand_height+.2,z),finish='steel',axis='y')
        model.box(f'stand_{i}_bridge',(stand_width,.28,w+1.3),(x,stand_height+.2,0),finish='blue')
        gap_height=.35 if kind=='bloom_mill' else .22 if wire else .012 if kind in {'finishing_mill','leveler'} and not plate else .18
        banks=[] if kind=='leveler' else [('lower',1.32-radius),('upper',1.32+gap_height+radius)]
        for bank,y in banks:
            name=function if i==0 and bank=='lower' else f'stand_{i}_{bank}_roll'
            model.node(name,position=(x,y,0))
            model.cylinder(name+'_barrel',radius,w,parent=name)
            for z,side in [(-w/2-.4,'left'),(w/2+.4,'right')]:
                model.ring(name+'_'+side+'_chock',(radius*.34,.31),.55,(x,y,z),finish='steel')
                model.box(name+'_'+side+'_chock_foot',(.90,.16,.55),(x,y-.30,z),finish='teal')
            model.cylinder(name+'_shaft',radius*.32,w+1.15,parent=name,finish='dark')
            model.box(name+'_index',(.055,.06,.08),(radius,0,-w/2-.08),name,'safety',bevel=.01)
            model.cylinder(name+'_drive_coupling',radius*.6,.28,(0,0,-w/2-.65),name,'safety')
            if wire:
                for side,z in [('left',-w/2-.08),('right',w/2+.08)]:
                    model.cylinder(name+f'_{side}_retaining_collar',radius*1.04,.035,(0,0,z),name,'dark')
            if name!=function:
                model.followers.append({'node_id':name,'driver':function,'ratio':-1 if bank=='upper' else 1,'axis':[0,0,-1],'pivot_m':[x,y,0]})
        model.tube(f'stand_{i}_hydraulic',[(-.35+x,stand_height-.2,-w/2-.6),(-.35+x,1.8,-w/2-.6),(x,1.8,-w/2-.6)],.045,finish='dark')
        for z,side in [(-w/2+.15,'left'),(w/2-.15,'right')]:
            model.box(f'stand_{i}_{side}_guide',(.42,.22,.16),(x-.9,1.50,z),finish='safety')
            outer=(-w/2-.4) if side=='left' else (w/2+.4)
            model.box(f'stand_{i}_{side}_guide_bracket',(.80,.14,abs(outer-z)+.18),(x-.65,1.32,(outer+z)/2),finish='teal')
            model.box(f'stand_{i}_{side}_guide_seat',(.22,.18,.16),(x-.9,1.38,z),finish='teal')
    if kind=='leveler':
        for i in range(8):
            x=(i-3.5)*.44
            name=function if i==0 else f'leveling_bank_{i}'
            y=1.14 if i%2==0 else 1.32+(.18 if plate else .012)+.18
            model.node(name,position=(x,y,0))
            model.cylinder(name+'_barrel',.18,w,parent=name)
            model.cylinder(name+'_shaft',.065,w+.6,parent=name,finish='dark')
            for z,side in [(-w/2-.16,'left'),(w/2+.16,'right')]:
                model.ring(name+'_'+side+'_bearing',(.075,.17),.25,(x,y,z),finish='teal')
                model.box(name+'_'+side+'_seat',(.28,y-.81,.25),(x,(y+.51)/2,z),finish='blue')
            model.box(name+'_index',(.045,.045,.08),(.18,0,-w/2-.08),name,'safety',bevel=.005)
            if i>0:
                model.followers.append({'node_id':name,'driver':function,'ratio':1 if i%2==0 else -1,'axis':[0,0,-1],'pivot_m':[x,y,0]})
    if count%2==0 and kind!='leveler':
        table(model,0,0,w,'middle_table')
    model.motion(Motion(function,'rotation',(0,0,-1),5.4/model.drive_radius))
    rails(model,model.length-.8,2.2,w+2.0)


def coiler(model):
    model.length,model.width=8,3.2
    model.drive_radius=.44
    table(model,-3.6,-.7,2.1)
    table(model,.3,.3,2.1,'feed_roller')
    model.box('headstock_plinth',(1.6,.12,1.0),(.7,.20,-.65),finish='dark')
    model.box('gearbox_support',(.8,.14,1.0),(.7,.21,-1.1),finish='dark')
    model.box('gearbox',(1.35,1.55,.75),(.7,1.0,-1.1),finish='blue')
    model.box('headstock',(1.4,2.2,.4),(.7,1.3,-.55),finish='teal')
    model.node('winding_mandrel',position=(.7,1.772,.35))
    model.cylinder('mandrel_core',.35,1.65,parent='winding_mandrel',finish='dark')
    for i in range(8):
        angle=i*math.tau/8
        model.tube(f'mandrel_segment_{i}',[(.365*math.cos(angle),.365*math.sin(angle),-.72),(.365*math.cos(angle),.365*math.sin(angle),.72)],.075,'winding_mandrel','steel')
    model.cylinder('mandrel_flange',.65,.12,(0,0,-.85),'winding_mandrel','safety')
    model.box('mandrel_index',(.05,.06,.08),(.51,0,-.95),'winding_mandrel','safety',bevel=.01)
    for i,angle in enumerate([-.5,.5,2.1]):
        x=.7+.645*math.cos(angle)
        y=1.772+.645*math.sin(angle)
        model.cylinder(f'wrapper_roll_{i}',.18,1.9,(x,y,.35),finish='steel')
        model.cylinder(f'wrapper_axle_{i}',.07,2.4,(x,y,.35),finish='dark')
        model.cylinder(f'wrapper_bearing_{i}',.25,.24,(x,y,-.75),finish='teal')
        model.tube(f'wrapper_arm_{i}',[(.7,.55,-.75),(x,y,-.75)],.12,finish='teal')
    for z,side in [(-.4,'left'),(1.2,'right')]:
        model.box(side+'_coil_saddle',(1.6,.2,.36),(2.7,.65,z),finish='safety')
    model.motion(Motion('winding_mandrel','rotation',(0,0,1),math.tau))


def laying_bore(model, name, points, outer, inner, parent='root'):
    """Editable open bore with annular end faces, including its actual inner wall."""
    n=model.segments
    vertices=[]
    side=None
    for i,point in enumerate(points):
        tangent=(Vector(points[min(i+1,len(points)-1)])-Vector(points[max(0,i-1)])).normalized()
        side=side-tangent*side.dot(tangent) if side is not None else tangent.cross(Vector((0,1,0)))
        if side.length<.01:
            side=tangent.cross(Vector((1,0,0)))
        side.normalize()
        up=tangent.cross(side).normalized()
        for radius in (outer,inner):
            for j in range(n):
                vertices.append(Vector(point)+radius*(math.cos(j*math.tau/n)*side+math.sin(j*math.tau/n)*up))
    faces=[]
    for i in range(len(points)-1):
        for j in range(n):
            a=i*2*n+j;b=i*2*n+(j+1)%n
            faces.extend([(a,b,b+2*n,a+2*n),(a+n,a+3*n,b+3*n,b+n)])
    end=(len(points)-1)*2*n
    for j in range(n):
        k=(j+1)%n
        faces.extend([(j,j+n,k+n,k),(end+j,end+k,end+k+n,end+j+n)])
    return model.node(name,parent,mesh=model.mesh(name,vertices,faces),finish='steel')


def laying_head(model):
    model.length,model.width=9,2.7
    model.drive_radius=.9
    table(model,-3.8,-1.8,.7)
    model.box('head_pedestal',(1.6,.25,2.0),(-1.2,.265,0),finish='dark')
    model.box('head_mount',(1.3,1.35,1.8),(-1.2,1.0,0),finish='blue')
    model.ring('head_housing',(.15,.65),.7,(-1.2,2.3,0),finish='teal',axis='x')
    model.node('laying_rotation',position=(-.8,2.3,0))
    model.ring('laying_drive_flange',(.12,.52),.18,parent='laying_rotation',finish='safety',axis='x')
    inlet=[(-2.07,1.35,0)]
    for i in range(1,9):
        a=-math.pi/2+i*math.pi/16
        inlet.append((-2.07+.12*math.cos(a),1.47+.12*math.sin(a),0))
    inlet.extend([(-1.95,1.85,0),(-1.82,2.12,0),(-1.60,2.3,0),(-.96,2.3,0)])
    laying_bore(model,'fixed_inlet_guide',inlet,.08,.06)
    model.ring('inlet_collar',(.079,.12),.10,(-1.95,1.85,0),finish='teal',axis='y')
    model.box('inlet_collar_bracket',(.37,.10,.10),(-1.80,1.85,-.13),finish='teal',bevel=.01)
    model.box('inlet_bracket_post',(.16,.20,.16),(-1.70,1.73,-.13),finish='blue',bevel=.01)
    laying_bore(model,'curved_laying_pipe',[(-.15,0,0),(.3,0,.1),(.65,-.22,.42),(.9,-.25,.64),(1.25,-.32,.75)],.105,.06,'laying_rotation')
    model.box('head_index',(.18,.10,.10),(.03,.5,0),'laying_rotation','red')
    for i in range(16):
        x=.5+i*.22
        model.box(f'cooling_conveyor_slat_{i}',(.08,.10,2.6),(x,1.27,0),finish='steel',bevel=.01)
    for z,side in [(-1.2,'left'),(1.2,'right')]:
        model.box(side+'_conveyor_frame',(4.3,.28,.16),(2.0,1.08,z),finish='blue')
        for i,x in enumerate([.1,3.9]):
            model.box(f'{side}_conveyor_leg_{i}',(.20,.86,.20),(x,.57,z),finish='teal')
            model.box(f'{side}_conveyor_foot_{i}',(.45,.10,.45),(x,.19,z),finish='dark')
    model.motion(Motion('laying_rotation','rotation',(1,0,0),math.tau*2.5))
