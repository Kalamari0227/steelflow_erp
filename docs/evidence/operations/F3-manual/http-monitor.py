from pathlib import Path
import subprocess,json,time,hashlib
r=Path(__file__).resolve().parent;run='OPS-RUN-383d0a45fed64693859f71d200a74b1a';seen=set();start=time.time();polls=0
initial=(r/'http-initial.txt').read_text();w=json.loads(initial.split('\n\n',1)[1]);(r/'http-initial-world.json').write_text(json.dumps(w,indent=2))
def save(tag,raw,w):
 (r/f'http-{tag}.txt').write_text(raw);(r/f'http-{tag}-world.json').write_text(json.dumps(w,indent=2));order=next(x for x in w['orders'] if x['id']=='ORD-ga');summary={'observedAt':time.time(),'run':w['run'],'order':order,'shipments':[x for x in w['shipments'] if x['order_id']=='ORD-ga'],'events':[x for x in w['events'] if x.get('order_id')=='ORD-ga']};(r/f'http-{tag}-facts.json').write_text(json.dumps(summary,indent=2));print(json.dumps({'milestone':tag,'run':w['run'],'delivered':order['delivered_kg'],'remaining':order['remaining_delivery_kg'],'facts':str(r/f'http-{tag}-facts.json')}),flush=True)
print('MONITOR_READY readonly curl -i http://127.0.0.1:8002/api/v1/world each1s',flush=True)
while time.time()-start<900:
 t=time.monotonic()
 if (r/'http-monitor-stop').exists(): print('STOP_REQUESTED',flush=True);break
 p=subprocess.run(['curl','-sS','-i','--max-time','5','http://127.0.0.1:8002/api/v1/world'],capture_output=True,text=True);polls+=1
 if p.returncode: print('HTTP_ERROR '+p.stderr,flush=True);break
 raw=p.stdout;w=json.loads(raw.split('\n\n',1)[1]);assert w['run']['id']==run,'run changed; stop instead of observing another run';o=next(x for x in w['orders'] if x['id']=='ORD-ga')
 with (r/'http-polls.jsonl').open('a') as f:f.write(json.dumps({'observedAt':time.time(),'runId':run,'revision':w['run']['revision'],'elapsedMs':w['run']['elapsed_ms'],'playing':w['run']['playing'],'delivered':o['delivered_kg'],'remaining':o['remaining_delivery_kg']})+'\n')
 tag=None
 if w['run']['playing'] and 'playing' not in seen:tag='playing'
 if o['delivered_kg']==40200 and 'partial' not in seen:tag='partial'
 if o['delivered_kg']==60300:tag='full'
 if tag:seen.add(tag);save(tag,raw,w)
 if tag=='full':break
 time.sleep(max(0,1-(time.monotonic()-t)))
files={str(p.name):{'size':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in r.glob('http-*') if p.is_file() and p.name!='http-monitor-receipt.json'};(r/'http-monitor-receipt.json').write_text(json.dumps({'invocation':'curl -sS -i --max-time 5 http://127.0.0.1:8002/api/v1/world','readOnly':True,'pollIntervalSeconds':1,'polls':polls,'milestones':sorted(seen),'files':files},indent=2));print('MONITOR_ENDED '+json.dumps({'polls':polls,'milestones':sorted(seen)}),flush=True)
