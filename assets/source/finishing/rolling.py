"""Cold tandem, electrical-steel reduction and compact skin-pass stands."""
from __future__ import annotations

import math

from details import motor, roller, tables
from geometry import Motion


def mill(model,spec):
    cold=spec['kind']=='cold_mill'
    name='cold_reduction_roll' if cold else 'temper_roll'
    count=4 if cold and spec['stage']=='cr' else 2 if cold else 1
    radius=.36 if cold else .23
    thickness=.002 if cold else spec['thickness_m']
    xs=[(i-(count-1)/2)*1.65 for i in range(count)]
    model.precision_rolls=cold
    model.length=max(model.length,2*max(abs(x) for x in xs)+7)
    for i,x in enumerate(xs):
        h=3.65 if cold else 3.0
        for z,side in [(-1.2,'near'),(1.2,'far')]:
            model.box(f'stand_{i}_{side}_foot',(1.4,.2,.8),(x,.32,z),finish='dark')
            for dx,end in [(-.48,'in'),(.48,'out')]:
                model.box(f'stand_{i}_{side}_{end}_column',(.22,h-.4,.42),(x+dx,(h+.4)/2,z),finish='teal')
            model.box(f'stand_{i}_{side}_cap',(1.3,.28,.5),(x,h,z),finish='blue')
            model.cylinder(f'stand_{i}_{side}_screw',.08,.7,(x,h+.12,z),finish='steel',axis='y')
            model.cylinder(f'stand_{i}_{side}_screw_head',.18,.09,(x,h+.45,z),finish='safety',axis='y')
        model.box(f'stand_{i}_bridge',(1.3,.25,2.9),(x,h+.2,0),finish='blue')
        for bank,y,rr,ratio in [('lower',model.datum-radius,radius,1),('upper',model.datum+thickness+radius,radius,-1),('backup_lower',model.datum-2*radius-.44,.44,radius/.44),('backup_upper',model.datum+thickness+2*radius+.44,.44,-radius/.44)]:
            # Compact temper still has real backup rolls but shorter housing.
            node=name if i==0 and bank=='lower' else f'stand_{i}_{bank}'
            roller(model,node,x,y,rr,driver=None if node==name else name,ratio=ratio)
            for z,side in [(-1.18,'near'),(1.18,'far')]:
                model.box(node+'_'+side+'_chock',(.62,.35,.40),(x,y,z),finish='steel',bevel=.025)
        motor(model,f'stand_{i}',x,z=-2.1,height=model.datum-.3)
    model.drive_radius=radius
    maximum=spec['cold_reduction']['maximum_rad'] if cold else 4/radius
    model.motion(Motion(name,'rotation',(0,0,-1),maximum))
    if cold:
        datum=model.datum
        if not model.line_spec:
            model.datum=datum-.001
            tables(model,xs[0]-4-spec['cold_reduction']['bite_m']-.5,xs[0]-.8,'entry_table',name)
            model.datum=datum
        for follower in model.followers:
            if follower['node_id'].startswith('entry_table_'):follower['ratio']*=.5
        end=xs[0]+8.4
        if abs(end-(model.length/2-.4))<.32:end=model.length/2-.4
        tables(model,xs[-1]+.8,end,'exit_table',name)
    else:
        tables(model,min(-3.6,xs[0]-1.4),xs[0]-.8,'entry_table',name)
        tables(model,xs[-1]+.8,max(3.6,xs[-1]+1.4),'exit_table',name)
    # A canonical work datum at x=0 lands on an additional actual lower roll
    # between tandem stands, rather than a hidden floating support patch.
    if not any(abs(x)<1e-6 for x in xs):
        roller(model,'interstand_work_roll',0,model.datum-.16,.16,driver=name,ratio=radius/.16)
    if cold:
        model.forming={'mode':'cold-reduction','driver':name,'length_m':4,'width_m':1.2,'inlet_thickness_m':.004,'outlet_thickness_m':.002,'roll_radius_m':radius,'nip_x_m':xs[0],**spec['cold_reduction']}


def leveler(model,spec):
    name='leveling_roll'
    model.drive_radius=.13
    for i in range(9):
        x=(i-4)*.35
        upper=i%2==1
        y=model.datum+(.134 if upper else -.13)
        node=name if i==4 else f'leveler_roll_{i}'
        roller(model,node,x,y,.13,driver=None if node==name else name,ratio=-1 if upper else 1)
    model.motion(Motion(name,'rotation',(0,0,-1),4/.13))
    for z,side in [(-1.2,'near'),(1.2,'far')]:
        model.box(side+'_tension_frame',(3.8,.3,.3),(0,2.6,z),finish='teal')
    tables(model,-3,-2,'entry_bridle',name)
    tables(model,2,3,'exit_bridle',name)
