"""Author the sealed Q1/Q2 synthetic sequence from actual T65 binding seeds."""
from pathlib import Path
import copy
import hashlib
import json
import math
import sys
import argparse

HERE=Path(__file__).resolve().parent
sys.dont_write_bytecode=True
sys.path.insert(0,str(HERE.parents[2]/'backend'))
from app.operations.time_adapter_v3 import sim_ms_to_utc,canonical_utc
parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--inputs',required=True);parser.add_argument('--out',required=True);args=parser.parse_args()
source=Path(args.inputs).resolve()
original=json.loads(source.read_text())
recipe=json.loads((HERE.parents[2]/'assets/source/finishing/recipe.json').read_text())
MAX=22.32152017305749;JOIN1=22.22222222222222;JOIN2=22.29677508587558
rows=[]

def channel(request,name,value):
    found=next(c for c in request['envelope']['channels'] if c['function_id']==name)
    found.update(start_value=value,end_value=value)

def anchor(request,name):
    e=request['envelope'];b=request['context']['asset_bindings'][0];s=next(s for s in b['sockets'] if s['socket_id']==name)
    e['anchor']={'owner_id':b['owner_id'],'socket_id':name,'position_m':s['position_m'][:],'orientation_xyzw':s['orientation_xyzw'][:]}

def finish(name,request,time,kind):
    e=request['envelope'];e.update(confirmed_sim_ms=time,effective_sim_ms=time,frozen_progress=time/10000,clock_state='paused')
    request['context']['snapshot']['run'].update(elapsed_ms=time,playing=False)
    request['context']['authorizations']=[copy.deepcopy(e)]
    rows.append({'name':name,'kind':kind,'request':request})

for owner in ['CS-CR-05','CS-GO-05','CS-NGO-05','CS-GO-08']:
    base=next(c['request'] for c in original['cases'] if c['name']==owner+'-clamp-to-feed')
    cfg=next(s['source_internal_sequence'] for s in recipe['models'] if s['key']==owner)
    t=cfg['thickness_m'];r0=.44+t/2;k=(t+.0002)/(2*math.pi);norm=math.hypot(r0,k);nx,ny=k/norm,r0/norm
    binding=base['context']['asset_bindings'][0];maximum=next(f['max_value'] for f in binding['functions'] if f['function_id']=='line_unwinding_mandrel')
    ident=base['envelope']['material']['material_id'];v1=ident+'-v1';v2=v1+':unwound';state=base['context']['snapshot'];stock=next(v for v in state['material_versions'] if v['id']==v1)
    def clamped():
        r=copy.deepcopy(base);e=r['envelope'];s=r['context']['snapshot'];old=e['boundary']['previous_material'];e['material']=copy.deepcopy(old);e['boundary']=None;anchor(r,'line_strip_support')
        s['attachments']=[a for a in s['attachments'] if a['material_id']!=ident or a['socket_id'] in ['line_coil_support','line_strip_support']]
        a=next(a for a in s['attachments'] if a['material_id']==ident and a['socket_id']=='line_strip_support');a['released_at_ms']=None;e['attachment_id']=a['id'];channel(r,'line_feed_lift',-.02)
        return r
    for label,theta,time in [('wound',maximum,0),('unwind-half',maximum/2,500),('unwound-before',0,1000)]:
        r=clamped();e=r['envelope'];s=r['context']['snapshot'];e['material']={'material_id':ident,'material_version_id':v1,'form':stock['form'],'dimensions':copy.deepcopy(stock['dimensions']),'support_local_mm':[-t*nx*500,-t*ny*500,0],'orientation_xyzw':[0,0,0,1]};anchor(r,'line_coil_support');channel(r,'line_unwinding_mandrel',theta)
        s['material_versions']=[v for v in s['material_versions'] if v['id']!=v2]
        for m in s['materials']:
            if m['id']==ident:m.update(current_version_id=v1,form=stock['form'],dimensions=copy.deepcopy(stock['dimensions']))
        s['process_batches']=[b for b in s['process_batches'] if b['id']!='synthetic:main-work:batch']
        next(b for b in s['process_batches'] if b['id']=='motion-batch').update(status='RUNNING',end_ms=10000)
        s['batch_io']=[io for io in s['batch_io'] if io['material_version_id']!=v2]
        s['version_edges']=[edge for edge in s['version_edges'] if edge['output_version_id']!=v2]
        s['events']=[];s['run']['event_sequence']=0
        s['attachments']=[a for a in s['attachments'] if a['material_id']!=ident or a['socket_id']=='line_coil_support'];a=next(a for a in s['attachments'] if a['material_id']==ident);a['released_at_ms']=None;e['attachment_id']=a['id']
        finish(owner+'-'+label,r,time,'source-unwind')
    for label,lift,time in [('unwound-after',-.02,1000),('lift-mid',-.01,1500),('feed-before',0,2000)]:
        r=clamped();channel(r,'line_feed_lift',lift)
        if label=='unwound-after':
            old=next(a for a in r['context']['snapshot']['attachments'] if a['material_id']==ident and a['socket_id']=='line_coil_support');previous=copy.deepcopy(rows[-1]['request']['envelope']['material']);e=r['envelope'];s=next(s for s in binding['sockets'] if s['socket_id']=='line_coil_support')
            e['boundary']={'released_attachment_id':old['id'],'acquired_attachment_id':e['attachment_id'],'at_ms':1000,'previous_material':previous,'previous_anchor':{'owner_id':owner,'socket_id':'line_coil_support','position_m':s['position_m'],'orientation_xyzw':s['orientation_xyzw']},'previous_channels':[{'function_id':c['function_id'],'node_id':c['node_id'],'kind':c['kind'],'axis':c['axis'],'pivot_m':c['pivot_m'],'value':c['end_value']} for c in e['channels']]}
        finish(owner+'-'+label,r,time,'source-retained-unwind-lift')
    for label,p,time in [('feed-after',0,2000),('feed-mid',.5,2500),('feed-end-before',1,3000)]:
        r=copy.deepcopy(base);e=r['envelope'];driver=next(f for f in binding['functions'] if f['function_id']==cfg['driver']);channel(r,cfg['driver'],driver['max_value']*p)
        if label!='feed-after':e['boundary']=None
        for f in binding['functions']:
            if f['function_id']=='cleaning_brush':channel(r,'cleaning_brush',f['max_value']*p)
            if f['function_id']=='thermal_chamber':channel(r,'thermal_chamber',1 if 0<p<1 else 0)
        finish(owner+'-'+label,r,time,'source-rigid-feed')
    if owner not in ['CS-GO-05','CS-NGO-05']:continue
    cold=copy.deepcopy(next(c['request'] for c in original['cases'] if c['name']==owner+'-feed-to-cold'))
    e=cold['envelope'];s=cold['context']['snapshot'];newcold=copy.deepcopy(next(a for a in s['attachments'] if a['id']==e['attachment_id']));newcold['acquired_at_ms']=3000
    history=copy.deepcopy([a for a in base['context']['snapshot']['attachments'] if a['material_id']==ident]);work=next(a for a in history if a['id']==base['envelope']['attachment_id']);work['released_at_ms']=3000
    s['attachments']=[a for a in s['attachments'] if a['material_id']!=ident]+history+[newcold]
    e['boundary'].update(released_attachment_id=work['id'],at_ms=3000)
    for label,theta,socket in [('main-after',0,'cold_entry_support'),('cold-half',MAX/2,'cold_entry_support'),('cold-entry-before',JOIN1,'cold_entry_support'),('cold-entry-after',JOIN1,'cold_bite_roll_support'),('cold-rotating-mid',(JOIN1+JOIN2)/2,'cold_bite_roll_support'),('cold-nip-before',JOIN2,'cold_bite_roll_support'),('cold-nip-after',JOIN2,'cold_nip_support'),('cold-complete-before',MAX,'cold_nip_support')]:
        r=copy.deepcopy(cold);e=r['envelope'];s=r['context']['snapshot'];time=3000 if theta==0 else round(3000+7000*theta/MAX);channel(r,'cold_reduction_roll',theta)
        if label!='main-after':e['boundary']=None
        prior=next(a for a in s['attachments'] if a['id']==e['attachment_id'])
        for nextsocket,angle,before in [('cold_bite_roll_support',JOIN1,'cold-entry-before'),('cold_nip_support',JOIN2,'cold-nip-before')]:
            if theta<angle or label==before:break
            at=round(3000+7000*angle/MAX);previous=copy.deepcopy(prior);prior['released_at_ms']=at;acquired={**prior,'id':prior['id']+':'+nextsocket,'socket_id':nextsocket,'acquired_at_ms':at,'released_at_ms':None};s['attachments'].append(acquired);e['attachment_id']=acquired['id'];prior=acquired
            if theta==angle:
                oldsocket=next(x for x in binding['sockets'] if x['socket_id']==previous['socket_id']);e['boundary']={'released_attachment_id':previous['id'],'acquired_attachment_id':acquired['id'],'at_ms':at,'previous_material':copy.deepcopy(e['material']),'previous_anchor':{'owner_id':owner,'socket_id':previous['socket_id'],'position_m':oldsocket['position_m'],'orientation_xyzw':oldsocket['orientation_xyzw']},'previous_channels':[{'function_id':c['function_id'],'node_id':c['node_id'],'kind':c['kind'],'axis':c['axis'],'pivot_m':c['pivot_m'],'value':c['end_value']} for c in e['channels']]}
        anchor(r,socket);finish(owner+'-'+label,r,time,'source-cold-reduction')
    r=copy.deepcopy(rows[-1]['request']);e=r['envelope'];s=r['context']['snapshot'];previous_material=copy.deepcopy(e['material']);newid=v2+':reduced';eventid='synthetic:T21:'+owner+':reduced:event';version=copy.deepcopy(next(v for v in s['material_versions'] if v['id']==v2));dims={**version['dimensions'],'length_mm':8000,'thickness_mm':2};version.update(id=newid,ordinal=3,form='THIN_STRIP',dimensions=dims,cause_event_id=eventid);s['material_versions'].append(version)
    next(m for m in s['materials'] if m['id']==ident).update(current_version_id=newid,form='THIN_STRIP',dimensions=copy.deepcopy(dims))
    e['material'].update(material_version_id=newid,form='THIN_STRIP',dimensions=copy.deepcopy(dims),support_local_mm=[0,-1,0])
    batch=next(b for b in s['process_batches'] if b['id']=='synthetic:main-work:batch');batch.update(status='COMPLETED',end_ms=10000)
    s['batch_io'].append({'run_id':s['run']['id'],'id':eventid+':output','batch_id':batch['id'],'role':'OUTPUT','material_version_id':newid,'quantity_kg':version['weight_kg'],'source_id':None})
    s['version_edges'].append({'run_id':s['run']['id'],'id':eventid+':edge','batch_id':batch['id'],'input_version_id':v2,'output_version_id':newid,'transferred_kg':version['weight_kg']})
    s['events'].append({'run_id':s['run']['id'],'id':eventid,'sequence':2,'event_type':'MATERIAL_TRANSFORMED','entity_type':'material','entity_id':ident,'at_ms':10000,'occurred_at':canonical_utc(sim_ms_to_utc(10000)),'source_id':'synthetic:T21:'+owner+':reduced-fixture','payload':{'reason_code':'SYNTHETIC_ASSET_FIXTURE','reason':'Explicit synthetic complete 4m raw to 8m thin source phase; not a live producer event','material_ids':[ident],'process_id':'motion-process','batch_id':batch['id']}});s['run']['event_sequence']=2
    prior=next(a for a in s['attachments'] if a['id']==e['attachment_id']);prior['released_at_ms']=10000;acquired={**prior,'id':prior['id']+':reduced','acquired_at_ms':10000,'released_at_ms':None};s['attachments'].append(acquired);e['attachment_id']=acquired['id']
    e['boundary']={'released_attachment_id':prior['id'],'acquired_attachment_id':acquired['id'],'at_ms':10000,'previous_material':previous_material,'previous_anchor':copy.deepcopy(e['anchor']),'previous_channels':[{'function_id':c['function_id'],'node_id':c['node_id'],'kind':c['kind'],'axis':c['axis'],'pivot_m':c['pivot_m'],'value':c['end_value']} for c in e['channels']]}
    finish(owner+'-cold-complete-after',r,10000,'source-reduced-version')

out=Path(args.out).resolve()
if out.exists():raise RuntimeError('Sequence output must be a new owned path; preserve old seeds')
out.write_text(json.dumps({'schema_version':1,'provenance':{'synthetic':True,'source_actual_seed_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'utc_adapter_sha256':hashlib.sha256((HERE.parents[2]/'backend/app/operations/time_adapter_v3.py').read_bytes()).hexdigest(),'decision':'R6-21D2 Q1/Q2 + registered T65','live_events':False,'remaining':'Actual PyTS and 3LOD mesh sequence admission remains required'},'cases':rows},indent=2)+'\n')
print(json.dumps({'cases':len(rows),'output':str(out),'sha256':hashlib.sha256(out.read_bytes()).hexdigest()}))
