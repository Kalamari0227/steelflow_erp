"""Authored physical supports, servicing detail and verification contact surfaces."""
import math
import re
from geometry import IDENTITY


def base(model):
    l, w = getattr(model,'support_length',model.length), model.width
    model.box('foundation',(l+.5,.14,w+2.8),(0,.07,0),finish='ceramic')
    for z, side in [(-w/2-.18,'left'),(w/2+.18,'right')]:
        model.box(side+'_bed_beam',(l,.32,.25),(0,.50,z),finish='blue')
        for i in range(5):
            x = (i/4-.5)*(l-.6)
            model.box(f'{side}_leg_{i}',(.22,.58,.24),(x,.36,z),finish='teal')
            model.box(f'{side}_foot_{i}',(.5,.10,.48),(x,.19,z),finish='dark')
            for dx in [-.15,.15]:
                model.cylinder(f'{side}_anchor_{i}_{str(dx).replace("-","m")}',.035,.09,(x+dx,.25,z),finish='steel',axis='y')
    model.box('motor_plinth',(.9,.15,.7),(-.9,.215,-w/2-.67),finish='dark')
    model.box('gearbox_plinth',(.7,.32,.6),(0,.30,-w/2-.67),finish='dark')
    model.box('control_post',(.20,.50,.20),(l/2-.8,.39,-w/2-.65),finish='teal')
    model.box('motor_pad',(1.1,.18,.8),(-.9,.35,-w/2-.67),finish='dark')
    model.cylinder('motor_housing',.29,.8,(-.9,.72,-w/2-.67),finish='blue',axis='x')
    for i in range(6):
        model.box(f'motor_cooling_fin_{i}',(.035,.48,.5),(-1.2+i*.11,.72,-w/2-.67),finish='teal',bevel=.01)
    model.box('right_angle_gearbox',(.55,.6,.5),(0,.75,-w/2-.67),finish='teal')
    model.cylinder('motor_drive_shaft',.07,.75,(-.45,.72,-w/2-.67),finish='steel',axis='x')
    model.box('control_box',(.42,.68,.32),(l/2-.8,.9,-w/2-.65),finish='blue')
    for i, finish in enumerate(['red','green','safety']):
        model.cylinder(f'control_button_{i}',.042,.035,(l/2-.9+i*.11,1.05,-w/2-.827),finish=finish)


def rails(model, length, height, width):
    for z, side in [(-width/2,'left'),(width/2,'right')]:
        model.box(side+'_walkway',(length,.10,.60),(0,height-.85,z),finish='dark')
        for i,x in enumerate([-length/2,0,length/2]):
            model.box(f'{side}_walkway_leg_{i}',(.10,height-1.04,.10),(x,(height-.76)/2,z),finish='teal')
        for y, level in [(height,'top'),(height-.35,'middle')]:
            model.tube(f'{side}_rail_{level}',[(-length/2,y,z),(length/2,y,z)],.025,finish='safety')
        for i in range(5):
            model.cylinder(f'{side}_rail_post_{i}',.027,.8,((i/4-.5)*length,height-.4,z),finish='safety',axis='y')


def table(model, start, end, width, prefix='table', positions=None):
    count = len(positions) if positions is not None else 1 if start==end else max(2,min(9,int(abs(end-start)/.36)+1))
    for i in range(count):
        x = positions[i] if positions is not None else start if count==1 else start+(end-start)*i/(count-1)
        model.cylinder(f'{prefix}_idler_{i}',.16,width,(x,1.16,0),finish='steel')
        model.cylinder(f'{prefix}_idler_shaft_{i}',.05,width+.5,parent=f'{prefix}_idler_{i}',finish='dark')
        model.box(f'{prefix}_idler_index_{i}',(.035,.045,.08),(.16,0,-width/2+.05),f'{prefix}_idler_{i}','safety',bevel=.005)
        for z, side in [(-width/2-.12,'left'),(width/2+.12,'right')]:
            model.box(f'{prefix}_{side}_bearing_{i}',(.25,.24,.2),(x,1.16,z),finish='teal',bevel=.025)
    for z, side in [(-width/2-.05,'left'),(width/2+.05,'right')]:
        model.box(f'{prefix}_{side}_sill',(end-start+.5,.18,.25),((start+end)/2,.96,z),finish='blue')
        for x,label in ([(start,'center')] if start==end else [(start,'entry'),(end,'exit')]):
            model.box(f'{prefix}_{side}_{label}_leg',(.22,.78,.25),(x,.53,z),finish='teal')
            model.box(f'{prefix}_{side}_{label}_foot',(.42,.10,.45),(x,.19,z),finish='dark')
        model.box(f'{prefix}_{side}_guard',(end-start+.4,.1,.12),((start+end)/2,1.34,z),finish='safety',bevel=.015)


def contacts(model, form):
    """Fixed-frame sockets land on actual machine surfaces, with no surrogate plate."""
    result=[]
    def add(name, point, role='support', node='root'):
        result.append({'id':name,'node_id':node,'role':role,'transform':{'position_m':list(point),'rotation_xyzw':list(IDENTITY)},'normal':[0,1,0],'forms':form,'max_load_kg':60000})
    if 'bed_transfer' in model.objects:
        for role,x in [('entry',-3.75),('work',-.15),('exit',3.75),('support',-.75)]:
            name=role+'_contact'
            model.box(name,(.30,.06,1.8),(x,.16,0),'bed_transfer','steel',bevel=0)
            model.box(name+'_seat',(.22 if role=='work' else .30,.12,1.8),(-.19 if role=='work' else x,.08,0),'bed_transfer','teal',bevel=0)
            add(role,(.15 if role=='work' else 0,.03,0),role,name)
        model.box('bed_received_contact',(.30,.06,1.8),(.15,1.36,.4),finish='steel',bevel=0)
        model.box('bed_received_seat',(.30,.06,1.8),(.15,1.305,.4),finish='teal',bevel=0)
        add('bed_received',(-.15,.03,0),node='bed_received_contact')
    else:
        rollers=sorted(n['transform']['position_m'][0] for n in model.nodes if re.fullmatch(r'(?:entry_table|exit_table|middle_table|table)_idler_\d+',n['id']))
        work={'CS-PLATE-06':-.45,'CS-WIRE-05':.16,'CS-HR-06':.3,'CS-WIRE-08':-2.2,'CS-HR-07':.22,'CS-PLATE-08':.22}.get(model.key,0)
        for role,x in [('entry',rollers[0]),('work',work),('exit',rollers[-1]),('support',work)]:
            add(role,(x,1.32,0),role)
        if 'furnace_feed' in model.objects or 'treatment_feed' in model.objects:
            all_rolls=sorted([*rollers,-3.9])
            for i in range(10):
                x=all_rolls[round(i*(len(all_rolls)-1)/9)]
                add(f'feed_contact_{i}',(x,1.32,0))
        if 'winding_mandrel' in model.objects:
            add('winding_support',(.7,2.212,.35))
    x,z=-model.length/2+.5,model.width/2+.5
    model.box('service_post',(.16,.46,.16),(x,.37,z),finish='dark')
    q=(math.sin(.23),0,0,math.cos(.23))
    model.node('service_bracket',position=(x,.6,z),rotation=q)
    model.box('service_pad',(.4,.12,.4),parent='service_bracket',finish='safety')
    result.append({'id':'service_support','node_id':'service_pad','role':'support','transform':{'position_m':[0,.06,0],'rotation_xyzw':list(IDENTITY)},'normal':[0,1,0],'forms':['PACKAGED'],'max_load_kg':50})
    return result


def markers(model):
    model.box('axis_origin',(.05,.05,.05),finish='dark',bevel=0)
    vertices=[(-.08,-.025,-.025),(-.08,.025,-.025),(-.08,.025,.025),(-.08,-.025,.025),(.14,0,0)]
    model.node('axis_front',position=(1,0,0),mesh=model.mesh('axis_front',vertices,[(0,3,2,1),(0,1,4),(1,2,4),(2,3,4),(3,0,4)]),finish='red')
    model.box('axis_up',(.04,.16,.04),(0,1,0),finish='green',bevel=0)
    model.box('axis_side',(.04,.04,.12),(0,0,-1),finish='axisblue',bevel=0)
