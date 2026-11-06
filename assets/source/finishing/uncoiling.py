"""Finite-length coil clamps and visible load-bearing mandrel machinery."""
from __future__ import annotations

import math
from details import motor, roller, tables
from geometry import Motion


def spiral_length(theta,thickness):
    r0=.44+thickness/2
    k=(thickness+.0002)/math.tau
    def primitive(r):
        return (r*math.sqrt(r*r+k*k)+k*k*math.asinh(r/k))/(2*k)
    return primitive(r0+k*theta)-primitive(r0)


def winding_range(thickness):
    low,high=0.0,12.0
    for _ in range(80):
        middle=(low+high)/2
        if spiral_length(middle,thickness)<4:
            low=middle
        else:
            high=middle
    return (low+high)/2


def mandrel(model,name,x=0,thickness=.002,line=None,flat_start=False):
    """Grip's outer face is the exact rest datum and moves with the shaft."""
    center=model.datum-.44;rotation=(0,0,0,1)
    if line:
        r0=.44+thickness/2;k=(thickness+.0002)/math.tau;alpha=math.pi+math.atan(k/r0)
        x=line['clamp_x_m']+r0*math.sin(alpha);center=line['feed_plane_m']+thickness/2-r0*math.cos(alpha)
        rotation=(0,0,math.sin(alpha/2),math.cos(alpha/2))
    if flat_start and not line:
        r0=.44+thickness/2;k=(thickness+.0002)/math.tau;delta=math.atan(k/r0)
        x+=.44*math.sin(delta);center=model.datum-.44*math.cos(delta)
        rotation=(0,0,math.sin(delta/2),math.cos(delta/2))
    model.node(name,position=(x,center,0),rotation=rotation)
    model.cylinder(name+'_core',.435,1.35,parent=name,finish='dark')
    for i in range(8):
        a=i*math.tau/8
        model.tube(name+f'_expansion_segment_{i}',[(.385*math.cos(a),.385*math.sin(a),-.62),(.385*math.cos(a),.385*math.sin(a),.62)],.054,name,'steel')
    angles=[math.pi/2-.12+i*.03 for i in range(9)]
    vertices=[(r*math.cos(a),r*math.sin(a),z) for z in [-.6,.6] for r in [.41,.44] for a in angles]
    n=len(angles);faces=[]
    for i in range(n-1):
        faces.extend([(i,i+1,n+i+1,n+i),(2*n+i,3*n+i,3*n+i+1,2*n+i+1),(n+i,n+i+1,3*n+i+1,3*n+i),(i,2*n+i,2*n+i+1,i+1)])
    faces.extend([(0,n,3*n,2*n),(n-1,3*n-1,4*n-1,2*n-1)])
    model.node(name+'_clamp_jaw',name,mesh=model.mesh(name+'_clamp_jaw',vertices,faces),finish='steel')
    model.box(name+'_clamp_retainer',(.24,.06,.08),(0,.39,-.64),name,'safety',bevel=.008)
    model.cylinder(name+'_spindle',.15,2.4,(0,0,-.28),name,finish='steel')
    model.ring(name+'_bearing',(.155,.33),.4,(x,center,-1.02),finish='safety')
    model.box(name+'_headstock',(1.05,center-.12,.75),(x,(center+.12)/2,-1.02),finish='teal')
    model.box(name+'_headstock_cap',(1.1,.24,.82),(x,center+.38,-1.02),finish='blue')
    model.cylinder(name+'_backplate',.64,.09,(0,0,-.73),name,'blue')
    model.box(name+'_index',(.06,.06,.09),(.5,0,-.81),name,'safety',bevel=.008)
    motor(model,name,x-.8,z=-2.0,height=center)
    model.motion(Motion(name,'rotation',(0,0,-1),winding_range(thickness)))
    model.drive_radius=.44


def coil_machine(model,spec):
    uncoil=spec['kind']=='uncoiler'
    name='unwinding_mandrel' if uncoil else 'winding_mandrel'
    t=spec['thickness_m'] if uncoil else (.006 if spec['stage']=='hgi' else .002)
    mandrel(model,name,thickness=t,flat_start=not uncoil)
    model.forming={'mode':'unwinding' if uncoil else 'winding','driver':name,'length_m':4,'width_m':1.2,'thickness_m':t,'core_radius_m':.44,'layer_clearance_m':.0002,'maximum_rad':winding_range(t),'anchor_local_m':[0,.44,0],'center_m':next(n['transform']['position_m'] for n in model.nodes if n['id']==name),'rest_delta_rad':0 if uncoil else math.atan((t+.0002)/math.tau/(.44+t/2))}
    # Cradle sits below the wound coil and has visible rollers and guide cheeks.
    for i,x in enumerate([-.48,.48]):
        roller(model,f'cradle_roll_{i}',x,model.datum-1.10,.19,width=1.5)
    for z,side in [(-.9,'near'),(.9,'far')]:
        model.box('cradle_'+side+'_beam',(1.8,.18,.2),(0,model.datum-1.4,z),finish='blue')
    if uncoil:
        tables(model,-2.6,-1.1,'threading',name)
        model.box('threading_apron',(.7,.06,1.4),(-.95,model.datum-.03,0),finish='steel',bevel=.01)
    else:
        tables(model,-2.6,-1.1,'entry_table',name)
        for i,angle in enumerate([-.8,-2.3]):
            x=.69*math.cos(angle);y=model.datum-.44+.69*math.sin(angle)
            roller(model,f'wrapper_roll_{i}',x,y,.18,width=1.55,driver=name,ratio=-.44/.18)
