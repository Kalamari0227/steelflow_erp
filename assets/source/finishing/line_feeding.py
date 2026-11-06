"""Sealed T65 actual independent entry feeders and retractable lift beds."""
from __future__ import annotations

from details import roller,motor
from geometry import Motion


def line_feeder(model,spec):
    cfg=model.line_spec;driver=cfg['driver'];plane=cfg['feed_plane_m'];radius=cfg['driver_radius_m']
    if driver not in model.objects:
        roller(model,driver,cfg['clamp_x_m'],plane-radius,radius,parent='line_feed_lift')
        model.motion(Motion(driver,'rotation',(0,0,-1),cfg['stroke_m']/radius))
        motor(model,'line_entry_feed',cfg['clamp_x_m'],z=-1.8,height=plane-.3)
    candidates=[r for r in model.roller_specs if r['parent']=='line_feed_lift' and abs(r['center_m'][1]+r['radius_m']-plane)<1e-9]
    for i in range(cfg['roller_count']):
        x=cfg['clamp_x_m']+.4*i
        if any(abs(r['center_m'][0]-x)<r['radius_m']+.22 for r in candidates):continue
        name=f'line_feed_idler_{i}';roller(model,name,x,plane-.2,.2,parent='line_feed_lift',driver=driver,ratio=radius/.2);candidates.append(model.roller_specs[-1])
    profile=[]
    for r in candidates:
        name=r['part_id']
        if name!=driver and not any(f['node_id']==name for f in model.followers):
            model.followers.append({'node_id':name,'driver':driver,'ratio':radius/r['radius_m'],'axis':[0,0,-1],'pivot_m':r['center_m']})
        f=next((f for f in model.followers if f['node_id']==name),None)
        if name!=driver and (f is None or f['driver']!=driver or f['ratio']<=0):continue
        profile.append({k:r[k] for k in ['part_id','surface_node_id','radius_m','width_m']})
    xs=[r['center_m'][0] for r in candidates];left,right=min(xs),max(xs)
    for z,side in [(-.9,'near'),(.9,'far')]:
        model.box('line_lift_'+side+'_carriage',(right-left+.5,.12,.18),((left+right)/2,.72,z),'line_feed_lift','blue')
        for i,x in enumerate([left,(left+right)/2,right]):
            model.ring(f'line_lift_{side}_actuator_{i}',(.05,.09),.38,(x,.40,z),finish='dark',axis='y')
            model.cylinder(f'line_lift_{side}_rod_{i}',.035,.20,(x,.63,z),'line_feed_lift','steel',axis='y')
            model.box(f'line_lift_{side}_actuator_foot_{i}',(.30,.06,.28),(x,.19,z),finish='teal')
    model.motion(Motion('line_feed_lift','translation',(0,1,0),0,minimum=-.02))
    start=cfg['clamp_x_m']+2
    model.feed_spec={'schema_version':1,'id':'finishing_strip_feed','kind':'linear_roller_feed','custody_socket_id':'work','driver_part_id':driver,'start_m':[start,plane,0],'end_m':[start+cfg['stroke_m'],plane,0],'rollers':profile,'support_lift_part_id':'line_feed_lift'}
