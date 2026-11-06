/** Actual SQL child input; explicitly synthetic new winding execution/history. */
import {build} from 'esbuild';
import {readFileSync,writeFileSync,mkdirSync} from 'node:fs';
import {resolve} from 'node:path';
import {hash,requireProof} from './oracle.mjs';

const args=process.argv.slice(2),v=k=>args[args.indexOf(k)+1],root=resolve(v('--root')),out=resolve(v('--out'));
const raw=readFileSync(resolve(root,'public/assets/steelworks/finishing/manifest.json'));
requireProof(hash(raw)===v('--expected-sha'),'preflight','exact independent current manifest');
const inputPath=resolve(v('--inputs')),inputRaw=readFileSync(inputPath);
requireProof(hash(inputRaw)===v('--inputs-sha'),'preflight','actual SQL derived terminal corpus');
const recipe=JSON.parse(readFileSync(resolve(root,'assets/source/finishing/recipe.json'))),manifest=JSON.parse(raw);
requireProof(manifest.assets.length===58&&manifest.assets.every(a=>a.family==='finishing'&&a.lods.length===3),'preflight','58 finishing owners and174LODs');
for(const a of manifest.assets)for(const lod of a.lods)requireProof(hash(readFileSync(resolve(root,lod.artifact.path)))===lod.artifact.sha256,'preflight','actual174 bytes');
mkdirSync(out);
await build({stdin:{contents:"export {parseMotionContext,parseMotionEnvelopeValue,evaluateMotion} from './src/operations/scene/motion/contracts';export {recipes} from './src/operations/scene/motion/testFixtures';export {businessEpochMs} from './src/operations/scene/worldContractMath';",resolveDir:resolve('.')},outfile:resolve(out,'api.mjs'),bundle:true,packages:'external',platform:'node',format:'esm'});
const api=await import(resolve(out,'api.mjs')),index=[];
for(const row of JSON.parse(inputRaw).cases.filter(r=>r.operation==='cut')){
 const dataPath=resolve(resolve(inputPath,'..'),row.file),dataRaw=readFileSync(dataPath);
 requireProof(hash(dataRaw)===row.sha256,'preflight','exact source SQL child fixture');
 const data=JSON.parse(dataRaw),asset=manifest.assets.find(a=>a.placement_ids[0]==='equipment:'+data.owner),spec=recipe.models.find(s=>s.key===data.owner),fn=data.winding_function;
 const base=data.output_envelopes.find(e=>e.material.material_id.endsWith(':C1')),left=data.output_envelopes.find(e=>e.material.material_id.endsWith(':C0'));
 requireProof(base&&left&&fn,'input','both actual cut children and independent winding function');
 const binding=data.post_context.asset_bindings[0],winding=binding.functions.find(f=>f.function_id===fn),coilSocket=binding.sockets.find(s=>s.socket_id===(asset.kind==='coiler'?'coil_support':'intermediate_coil_support'));
 requireProof(winding&&coilSocket,'binding','exact physical final coil socket');
 const id=base.material.material_id,processId='synthetic:T21:postcut-winding:'+data.owner,batchId=processId+':batch',start=10000,end=20000;
 const state=structuredClone(data.post_context.snapshot),world=structuredClone(data.post_context.world),priorProcess=state.processes.find(p=>p.id===base.execution_id);
 requireProof(priorProcess?.status==='COMPLETED','input','actual completed cut observation');
 const process={...priorProcess,id:processId,status:'RUNNING',ready_at_ms:start,start_ms:start,end_ms:end,planned_duration_ms:end-start,blocked_reason:null};
 state.processes.push(process);
 state.process_batches.push({run_id:state.run.id,id:batchId,process_id:processId,recipe_id:spec.source_step_id,status:'RUNNING',start_ms:start,end_ms:end});
 state.batch_io.push({run_id:state.run.id,id:batchId+':input',batch_id:batchId,role:'INPUT',material_version_id:base.material.material_version_id,quantity_kg:400,source_id:null});
 const held=structuredClone(left);held.execution_id=processId;
 const material=state.materials.find(m=>m.id===id),version=state.material_versions.find(m=>m.id===base.material.material_version_id);
 requireProof(material?.active&&material.weight_kg===400&&version?.dimensions.length_mm===4000,'input','actual4m400kg current child');
 const frames=[];
 function frame(name,progress,clock='running',speed=1){
  const snapshot=structuredClone(state),time=start+Math.round((end-start)*progress),e=structuredClone(base);
  Object.assign(snapshot.run,{elapsed_ms:time,playing:clock==='running',speed});
  const p=snapshot.processes.find(p=>p.id===processId);p.status=clock==='blocked'?'BLOCKED':'RUNNING';
  Object.assign(e,{execution_id:processId,phase_start_ms:start,phase_end_ms:end,confirmed_sim_ms:time,effective_sim_ms:time,frozen_progress:progress,clock_state:clock,boundary:null});
  e.channels=e.channels.map(c=>({...c,start_value:0,end_value:c.function_id===fn?winding.max_value:0}));
  return {name,progress,request:{envelope:e,context:{...data.post_context,snapshot,world,authorizations:[structuredClone(e)]},ownerPose:data.ownerPose}};
 }
 for(const [name,p,clock,speed]of [['start',0,'paused',1],['quarter',.25,'running',1],['half',.5,'running',1],['blocked',.5,'blocked',1],['paused',.5,'paused',1],['resumed',.5,'running',1],['speed2',.5,'running',2],['speed4',.5,'running',4],['three-quarter',.75,'running',1],['end-before',1,'paused',1]])frames.push(frame(name,p,clock,speed));
 const final=structuredClone(frames.at(-1));final.name='end-after';
 const e=final.request.envelope,s=final.request.context.snapshot,previous=structuredClone(e.material),old=s.attachments.find(a=>a.id===e.attachment_id),newId=version.id+':wound',eventId=processId+':formed';
 const t=data.thickness_m,k=(t+.0002)/(2*Math.PI),dimensions={length_mm:null,width_mm:1200,thickness_mm:t*1000,diameter_mm:2*(.44+t+k*winding.max_value)*1000,inner_diameter_mm:880};
 const nextVersion={...version,id:newId,ordinal:version.ordinal+1,form:spec.output_form,dimensions,cause_event_id:eventId};s.material_versions.push(nextVersion);
 Object.assign(s.materials.find(m=>m.id===id),{current_version_id:newId,form:spec.output_form,dimensions});
 const owner=world.owners.find(o=>o.id===data.owner),portId='v2:'+processId+':coil-port',nodeId=portId+':node',[x,y,z]=coilSocket.position_m,[ox,oy,oz]=owner.pose.position,yaw=owner.pose.yaw_rad;
 world.nodes.push({id:nodeId,position:[ox+Math.cos(yaw)*x+Math.sin(yaw)*z,oy+y,oz-Math.sin(yaw)*x+Math.cos(yaw)*z],modes:['roller']});
 world.ports.push({id:portId,owner_id:data.owner,socket_id:coilSocket.socket_id,node_id:nodeId,capacity_kg:60000,modes:['roller']});
 final.request.context.world=structuredClone(world);
 old.released_at_ms=end;const acquired={...old,id:old.id+':wound',owner_id:portId,socket_id:coilSocket.socket_id,acquired_at_ms:end,released_at_ms:null};s.attachments.push(acquired);
 e.attachment_id=acquired.id;e.material={...e.material,material_version_id:newId,form:spec.output_form,dimensions};e.anchor={owner_id:data.owner,socket_id:coilSocket.socket_id,position_m:coilSocket.position_m,orientation_xyzw:coilSocket.orientation_xyzw};
 const batch=s.process_batches.find(b=>b.id===batchId);batch.status='COMPLETED';
 s.batch_io.push({run_id:s.run.id,id:batchId+':output',batch_id:batchId,role:'OUTPUT',material_version_id:newId,quantity_kg:400,source_id:null});
 s.version_edges.push({run_id:s.run.id,id:batchId+':edge',batch_id:batchId,input_version_id:version.id,output_version_id:newId,transferred_kg:400});
 s.events.push({run_id:s.run.id,id:eventId,sequence:s.run.event_sequence+1,event_type:'MATERIAL_TRANSFORMED',entity_type:'material',entity_id:id,at_ms:end,occurred_at:new Date(api.businessEpochMs(end)).toISOString(),source_id:processId,payload:{reason_code:'SYNTHETIC_ASSET_FIXTURE',reason:'Explicit synthetic retained final winding history, not a production writer command or live event',material_ids:[id],process_id:processId,batch_id:batchId}});s.run.event_sequence++;
 e.boundary={released_attachment_id:old.id,acquired_attachment_id:acquired.id,at_ms:end,previous_material:previous,previous_anchor:structuredClone(base.anchor),previous_channels:e.channels.map(c=>({function_id:c.function_id,node_id:c.node_id,kind:c.kind,axis:c.axis,pivot_m:c.pivot_m,value:c.end_value}))};
 final.request.context.authorizations=[structuredClone(e)];frames.push(final);
 writeFileSync(resolve(out,data.owner+'-raw.json'),JSON.stringify({frames})+'\n');
 for(const f of frames){const envelope=api.parseMotionEnvelopeValue(f.request.envelope),context=api.parseMotionContext(f.request.context);f.pose=api.evaluateMotion(envelope,context,api.recipes);}
 const result={schema_version:1,owner:data.owner,ownerPose:data.ownerPose,manifest_sha256:hash(raw),winding_function:fn,winding_maximum:winding.max_value,thickness_m:t,actual_SQL_source_sha256:data.source_sql_sha256,actual_child_corpus_sha256:hash(dataRaw),left_child_envelope:left,original_post_context:data.post_context,frames,qualification:'ActualT10 SQL child input. New execution/batch, finalsame-IDversion and retainedcustody are explicit synthetic asset history, not production command processing. Backend same-ID production writer remains unimplemented.'};
 const file=data.owner+'.json',bytes=JSON.stringify(result)+'\n';writeFileSync(resolve(out,file),bytes);index.push({owner:data.owner,file,sha256:hash(Buffer.from(bytes)),frames:frames.length});
}
requireProof(index.length===11,'coverage','exact11 cut-child owners');
writeFileSync(resolve(out,'index.json'),JSON.stringify({manifest_sha256:hash(raw),source_corpus_sha256:hash(inputRaw),cases:index},null,2)+'\n');
console.log(JSON.stringify({owners:index.length,frames:index.reduce((n,r)=>n+r.frames,0),scope:'SYNTHETIC_NEW_WINDING_ASSET_HISTORY_NOT_PRODUCTION_WRITER'}));
