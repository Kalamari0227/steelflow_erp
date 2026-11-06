"""Manufacturing domain-refinement head, separate from quality inspection."""
from __future__ import annotations

from details import tables,roller
from geometry import Motion


def domain_refinement(model,spec):
    model.node('inspection_scan',position=(0,model.datum+.45,-.65))
    model.box('domain_laser_head',(.32,.26,.25),parent='inspection_scan',finish='safety')
    model.cylinder('domain_laser_lens',.07,.15,(0,-.17,0),'inspection_scan','dark',axis='y')
    model.node('domain_laser',position=(0,model.datum+.45,0))
    model.box('domain_laser_power_cabinet',(.8,1.2,.6),(1.0,-1.65,1.7),'domain_laser','blue')
    model.box('domain_laser_control_base',(.9,.09,.7),(1.0,-2.245,1.7),'domain_laser','dark')
    model.tube('domain_laser_power_bus',[(1.0,-1.05,1.7),(1.0,.4,1.7),(0,.4,1.0)],.035,'domain_laser','dark')
    for z,side in [(-1.15,'near'),(1.15,'far')]:
        model.box('laser_'+side+'_column',(.25,2.7,.25),(0,1.51,z),finish='teal')
        model.box('laser_'+side+'_shield',(2.0,.7,.10),(0,model.datum+.3,z),finish='blue')
    model.box('laser_traverse_beam',(.45,.2,2.8),(0,model.datum+.8,0),finish='blue')
    model.cylinder('laser_traverse_rail',.055,2.3,(0,model.datum+.55,0),finish='steel')
    model.motion(Motion('inspection_scan','translation',(0,0,1),1.3))
    # Stationary support cylinders are deliberately not false canonical feed drives.
    for i,x in enumerate([-2.5,-1.8,-1.1,0,1.1,1.8,2.5]):
        roller(model,f'domain_support_{i}',x,model.datum-.16,.16)
