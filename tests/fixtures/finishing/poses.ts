import type { Asset, AssetManifest } from '../../../src/operations/scene/assets/manifest';
import { bindingsFromAssetManifest, evaluateMotion, parseMotionContext, parseMotionEnvelopeValue } from '../../../src/operations/scene/motion/contracts';
import { fixture, recipes } from '../../../src/operations/scene/motion/testFixtures';
import canonicalWorld from '../../../shared/factory-world-v2.json';
import recipe from '../../../assets/source/finishing/recipe.json';
import sourceRoots from './accepted-source-roots.json';
import assetRequirements from '../../../shared/asset-requirements.json';
import { requireAsset } from '../../../src/operations/scene/assets/errors';
import {businessEpochMs,poseSchema} from '../../../src/operations/scene/worldContractMath';
import {coldLaw} from './forming';
import {batchCar,batchBell} from './schedules';
export {batchCar,batchBell} from './schedules';
import {z} from 'zod';
import seedIndex from './seed-index.json';
const seedCase=z.object({name:z.string(),context_id:z.string(),request:z.object({envelope:z.object({frozen_progress:z.number()}).passthrough(),context:z.record(z.string(),z.unknown())})});
const corpusShape=z.object({contexts:z.record(z.string(),z.record(z.string(),z.unknown())),continuity_cases:z.array(seedCase),sequence_cases:z.array(seedCase)});
let loadedCorpus:z.infer<typeof corpusShape>|undefined;
export async function loadContinuityCorpus(){if(loadedCorpus)return;const raw=await import('./seed-corpus.json?raw');loadedCorpus=corpusShape.parse(JSON.parse(raw.default));}

export const frames=[
  {name:'idle',progress:0,clock:'paused'},
  {name:'running-25',progress:.25,clock:'running'},
  {name:'running-50',progress:.5,clock:'running'},
  {name:'blocked',progress:.5,clock:'blocked'},
  {name:'paused',progress:.5,clock:'paused'},
  {name:'resumed',progress:.5,clock:'running'},
  {name:'running-75',progress:.75,clock:'running'},
  {name:'complete-before',progress:1,clock:'paused'},
  {name:'complete',progress:1,clock:'paused'},
  {name:'cold-entry-before',progress:coldLaw.entryHandoffRad/coldLaw.maximumRad,clock:'paused'},
  {name:'cold-entry-after',progress:coldLaw.entryHandoffRad/coldLaw.maximumRad,clock:'paused'},
  {name:'cold-rotating-mid',progress:(coldLaw.entryHandoffRad+coldLaw.nipHandoffRad)/2/coldLaw.maximumRad,clock:'running'},
  {name:'cold-nip-before',progress:coldLaw.nipHandoffRad/coldLaw.maximumRad,clock:'paused'},
  {name:'cold-nip-after',progress:coldLaw.nipHandoffRad/coldLaw.maximumRad,clock:'paused'},
  ...seedIndex.continuity_cases.map(c=>({name:'continuity:'+c.name,progress:c.progress,clock:'paused' as const})),
  ...seedIndex.sequence_cases.map(c=>({name:'sequence:'+c.name,progress:c.progress,clock:'paused' as const})),
  {name:'batch-load-before',progress:.25,clock:'paused'},
  {name:'batch-load-after',progress:.25,clock:'paused'},
  {name:'batch-unload-before',progress:.85,clock:'paused'},
  {name:'batch-unload-after',progress:.85,clock:'paused'},
  {name:'bath-wiping',progress:.9,clock:'running'},
  {name:'bath-cooling',progress:.975,clock:'running'},
  ...(['speed-1','speed-2','speed-4'] as const).map(name=>({name,progress:.5,clock:'running' as const})),
  ...(['CS-CR-05','CS-GO-05','CS-NGO-05','CS-GO-08'] as const).flatMap(owner=>['blocked','paused','resumed','speed1','speed2','speed4'].map(mode=>({name:'replay:'+owner+':'+mode,progress:.5,clock:'paused' as const}))),
  ...(['entry_looper_lift','exit_looper_lift'] as const).flatMap(fn=>[{name:'supplement:'+fn+':idle',progress:0,clock:'paused' as const},{name:'supplement:'+fn+':lower-quarter',progress:.1,clock:'running' as const},{name:'supplement:'+fn+':stored',progress:.2,clock:'running' as const},{name:'supplement:'+fn+':blocked',progress:.5,clock:'blocked' as const},{name:'supplement:'+fn+':paused',progress:.5,clock:'paused' as const},{name:'supplement:'+fn+':resumed',progress:.5,clock:'running' as const},{name:'supplement:'+fn+':return',progress:.9,clock:'running' as const},{name:'supplement:'+fn+':complete',progress:1,clock:'paused' as const}]),
  ...([{name:'idle',progress:0,clock:'paused' as const},{name:'quarter',progress:.25,clock:'running' as const},{name:'half',progress:.5,clock:'running' as const},{name:'three-quarter',progress:.75,clock:'running' as const},{name:'end',progress:1,clock:'paused' as const},{name:'blocked',progress:.5,clock:'blocked' as const},{name:'paused',progress:.5,clock:'paused' as const},{name:'resumed',progress:.5,clock:'running' as const}]).map(f=>({...f,name:'main:'+f.name})),
] as const;
export type Frame={readonly name:string;readonly progress:number;readonly clock:'paused'|'running'|'blocked'};

function pulse(p:number):number{return p<=.2 ? p/.2 : p<=.8 ? 1 : (1-p)/.2;}

/** Only canonical admitted channel values drive geometry, never a wall clock. */
export function phaseRequest(manifest:AssetManifest,asset:Asset,frame:Frame,manifestHash:string,speed:1|2|4=1){
  if(frame.name.startsWith('main:'))return mainProcessRequest(manifest,asset,frame,manifestHash,speed);
  if(frame.name.startsWith('continuity:')||frame.name.startsWith('sequence:')||frame.name.startsWith('replay:'))return continuityRequest(manifest,asset,frame,manifestHash,speed);
  if(frame.name.startsWith('supplement:'))return looperRequest(manifest,asset,frame,manifestHash,speed);
  const phaseSpeed=frame.name==='speed-2'?2:frame.name==='speed-4'?4:speed;
  return basePhaseRequest(manifest,asset,frame,manifestHash,phaseSpeed);
}
function basePhaseRequest(manifest:AssetManifest,asset:Asset,frame:Frame,manifestHash:string,speed:1|2|4){
  const spec=recipe.models.find(m=>m.variant===asset.variant),ownerId=asset.placement_ids[0]?.replace('equipment:','');
  requireAsset(spec&&ownerId,'binding','sealed finishing owner');
  const families:Record<string,string>={};for(const s of asset.sockets){const f=s.forms[0];requireAsset(f,'binding',s.id);families[s.id]=f;}
  const bindings=bindingsFromAssetManifest(manifest,[{owner_id:ownerId,asset_id:asset.id,socket_families:families}]),binding=bindings[0];
  requireAsset(binding,'binding','finishing binding');
  const input=fixture(),world=structuredClone(canonicalWorld),owner=world.owners.find(o=>o.id===ownerId),source=recipes.recipes.find(r=>r.id==='motion:source:'+spec.source_step_id);
  requireAsset(owner&&source,'binding','canonical owner/source recipe');
  // Canonical owner poses, footprints, paths and existing sockets are retained.
  // Only additional authored support sockets are monotonic fixture additions.
  for(const s of binding.sockets){const existing=owner.sockets.find(x=>x.id===s.socket_id);if(existing){requireAsset(existing.pose.position.every((v,i)=>Math.abs(v-(s.position_m[i]??Infinity))<1e-9),'binding','canonical socket moved');}else owner.sockets.push({id:s.socket_id,pose:{position:[...s.position_m],yaw_rad:0}});}
  const p=frame.progress,time=Math.round(p*10000),batch=asset.kind==='heat_treatment',coiler=asset.kind==='coiler',uncoiler=asset.kind==='uncoiler',cold=asset.kind==='cold_mill';
  const complete=frame.name==='complete'&&(coiler||uncoiler||cold),received=batch&&p>=.25&&p<=.85;
  let socketId=received?'batch_base':complete&&coiler?'coil_support':complete&&uncoiler?'strip_support':'work';
  if(batch)socketId=p<.25||frame.name==='batch-load-before'||p>=.85&&frame.name!=='batch-unload-before'?'work':'batch_base';
  const coldScalar=frame.name.startsWith('cold-entry-')?coldLaw.entryHandoffRad:frame.name.startsWith('cold-nip-')?coldLaw.nipHandoffRad:frame.name==='cold-rotating-mid'?(coldLaw.entryHandoffRad+coldLaw.nipHandoffRad)/2:p*coldLaw.maximumRad;
  if(cold)socketId=coldScalar<coldLaw.entryHandoffRad||frame.name==='cold-entry-before'?'cold_entry_support':coldScalar<coldLaw.nipHandoffRad||frame.name==='cold-nip-before'?'cold_bite_roll_support':'cold_nip_support';
  const support=binding.sockets.find(s=>s.socket_id===socketId);requireAsset(support,'binding',socketId);
  const thickness=spec.thickness_m,coilThickness=spec.stage==='hgi'?.006:.002;
  const winding=asset.moving_parts.find(m=>m.binding.type!=='mechanical_follower'&&m.function===(coiler?'winding_mandrel':'unwinding_mandrel'));
  const t=coiler?coilThickness:thickness,max=winding?.range.max??0,k=(t+.0002)/(2*Math.PI),outer=2*(.44+t+k*max)*1000;
  const coilDimensions={length_mm:null,width_mm:1200,thickness_mm:t*1000,diameter_mm:outer,inner_diameter_mm:880};
  const stripDimensions={length_mm:4000,width_mm:1200,thickness_mm:t*1000,diameter_mm:null,inner_diameter_mm:null};
  const inputDimensions=batch?{length_mm:null,width_mm:600,thickness_mm:2,diameter_mm:1400,inner_diameter_mm:600}:uncoiler?coilDimensions:stripDimensions;
  const outputDimensions=coiler?coilDimensions:cold?{...stripDimensions,length_mm:8000,thickness_mm:2}:stripDimensions;
  const form=complete?(cold?'THIN_STRIP':spec.output_form):spec.input_form,dimensions=complete?outputDimensions:inputDimensions;
  const supportLocal=batch?[-500,-300,0]:[0,-(complete&&cold?.002:t)*500,0];
  Object.assign(input.envelope,{bundle_id:'synthetic-finishing-'+manifestHash.slice(0,16),bundle_hash:manifestHash,recipe_id:source.id,phase_start_ms:0,phase_end_ms:10000,confirmed_sim_ms:time,effective_sim_ms:time,frozen_progress:p,clock_state:frame.clock});
  Object.assign(input.context.snapshot.run,{bundle_id:input.envelope.bundle_id,bundle_hash:manifestHash,elapsed_ms:time,playing:frame.clock==='running',speed});
  input.envelope.anchor={owner_id:ownerId,socket_id:socketId,position_m:[...support.position_m],orientation_xyzw:[...support.orientation_xyzw]};
  Object.assign(input.envelope.material,{form,dimensions,support_local_mm:supportLocal,orientation_xyzw:[0,0,0,1]});
  const profile=asset.internal_feeds?.[0];
  if(profile&&!cold)Object.assign(input.envelope.material,{internal_feed:{schema_version:1,feed_id:profile.id}});
  const registered=assetRequirements.existing_bindings.find(b=>b.variant===asset.variant),basePolicy=assetRequirements.policies.find(p=>p.id===registered?.policy_group_id);requireAsset(basePolicy,'binding','Exact base hardware function set');
  input.envelope.channels=binding.functions.map(fn=>{
    const needed=source.functions.find(f=>f.policy_id===binding.policy_id&&f.function_id===fn.function_id);requireAsset(needed,'binding','selected exact source function '+fn.function_id);
    let normalized=fn.kind==='state'?(p>.2&&p<.8?1:0):fn.kind==='translation'?pulse(p):p;
    if(uncoiler&&fn.function_id==='unwinding_mandrel')normalized=1-p;
    if(fn.function_id==='strip_clamp')normalized=pulse(p);
    if(fn.function_id==='weld_head')normalized=p<=.25?0:p<=.75?(p-.25)/.5:1;
    let value=fn.min_value+(fn.max_value-fn.min_value)*normalized;
    if(asset.kind==='galvanizing'&&fn.function_id==='air_knife')value=p>=.84?1:0;
    if(batch&&fn.function_id==='treatment_feed')value=batchCar(p);
    if(batch&&fn.function_id==='bell_lift')value=batchBell(p);
    if(batch&&fn.function_id==='thermal_chamber')value=p>=.4&&p<=.7?1:0;
    if(cold&&fn.function_id==='cold_reduction_roll')value=coldScalar;
    if(!basePolicy.required_functions.includes(fn.function_id)&&!basePolicy.fixed_functions.includes(fn.function_id)&&fn.function_id!=='domain_laser')value=0;
    if(asset.kind==='galvanizing'&&fn.function_id==='coating_cooling')value=p>=.942?1:0;
    return {function_id:fn.function_id,node_id:fn.node_id,kind:fn.kind,window_id:needed.window_id,axis:[...fn.axis],pivot_m:[...fn.pivot_m],start_value:value,end_value:value};
  });
  for(const process of input.context.snapshot.processes)Object.assign(process,{equipment_id:ownerId,route_step_id:`${spec.stage}:${spec.source_step_id}`,start_ms:0,end_ms:10000,planned_duration_ms:10000,status:frame.clock==='blocked'?'BLOCKED':'RUNNING'});
  const material=input.context.snapshot.materials.find(m=>m.id===input.envelope.material.material_id),version=input.context.snapshot.material_versions.find(v=>v.id===input.envelope.material.material_version_id),old=input.context.snapshot.attachments.find(a=>a.id===input.envelope.attachment_id);
  requireAsset(material&&version&&old,'binding','retained synthetic stock history');
  Object.assign(version,{form:spec.input_form,dimensions:structuredClone(inputDimensions)});
  Object.assign(material,{form:spec.input_form,dimensions:structuredClone(inputDimensions)});
  for(const stock of input.context.snapshot.stock_lots)if(stock.id===material.id)stock.form=spec.input_form;
  Object.assign(old,{kind:'equipment',owner_id:ownerId,socket_id:'work',acquired_at_ms:0});
  if(batch){let previous=old;for(const join of [{at:2500,socket:'batch_base',before:'batch-load-before'},{at:8500,socket:'work',before:'batch-unload-before'}]){if(time<join.at||frame.name===join.before)break;const prior=previous,priorSocket=binding.sockets.find(s=>s.socket_id===prior.socket_id);requireAsset(priorSocket,'binding','actual batch retained support');Object.assign(prior,{released_at_ms:join.at});const acquired={...prior,id:old.id+':batch:'+join.at,socket_id:join.socket,acquired_at_ms:join.at,released_at_ms:null};input.context.snapshot.attachments.push(acquired);input.envelope.attachment_id=acquired.id;previous=acquired;if(time===join.at)Object.assign(input.envelope,{boundary:{released_attachment_id:prior.id,acquired_attachment_id:acquired.id,at_ms:join.at,previous_material:structuredClone(input.envelope.material),previous_anchor:{owner_id:ownerId,socket_id:prior.socket_id,position_m:[...priorSocket.position_m],orientation_xyzw:[...priorSocket.orientation_xyzw]},previous_channels:input.envelope.channels.map(c=>({function_id:c.function_id,node_id:c.node_id,kind:c.kind,value:c.end_value,axis:c.axis,pivot_m:c.pivot_m}))}});}}
  if(cold){
    old.socket_id='cold_entry_support';
    let previous=old;
    const joins=[{socket:'cold_bite_roll_support',theta:coldLaw.entryHandoffRad,before:'cold-entry-before'},{socket:'cold_nip_support',theta:coldLaw.nipHandoffRad,before:'cold-nip-before'}];
    for(const join of joins){if(coldScalar<join.theta||frame.name===join.before)break;const at=Math.round(join.theta/coldLaw.maximumRad*10000),prior=previous,priorSocket=binding.sockets.find(s=>s.socket_id===prior.socket_id);requireAsset(priorSocket,'binding','cold retained old socket');Object.assign(prior,{released_at_ms:at});const acquired={...prior,id:old.id+'-'+join.socket,socket_id:join.socket,acquired_at_ms:at,released_at_ms:null};input.context.snapshot.attachments.push(acquired);input.envelope.attachment_id=acquired.id;previous=acquired;if(coldScalar===join.theta)Object.assign(input.envelope,{boundary:{released_attachment_id:prior.id,acquired_attachment_id:acquired.id,at_ms:at,previous_material:structuredClone(input.envelope.material),previous_anchor:{owner_id:ownerId,socket_id:prior.socket_id,position_m:[...priorSocket.position_m],orientation_xyzw:[...priorSocket.orientation_xyzw]},previous_channels:input.envelope.channels.map(c=>({function_id:c.function_id,node_id:c.node_id,kind:c.kind,value:c.end_value,axis:c.axis,pivot_m:c.pivot_m}))}});}
  }
  if((complete||received)&&!cold&&!batch){
    const at=received?2500:10000,previousMaterial=structuredClone(input.envelope.material),work=binding.sockets.find(s=>s.socket_id==='work');requireAsset(work,'binding','retained work socket');
    Object.assign(previousMaterial,{form:spec.input_form,dimensions:structuredClone(inputDimensions)});
    Object.assign(old,{released_at_ms:at});
    const acquired={...old,id:old.id+'-'+(received?'batch-base':'formed'),socket_id:socketId,acquired_at_ms:at,released_at_ms:null};input.context.snapshot.attachments.push(acquired);input.envelope.attachment_id=acquired.id;
    if(complete){
      const id=version.id+'-formed';input.context.snapshot.material_versions.push(Object.assign(structuredClone(version),{id,ordinal:2,form:spec.output_form,dimensions:structuredClone(outputDimensions)}));
      Object.assign(material,{current_version_id:id,form:spec.output_form,dimensions:structuredClone(outputDimensions)});input.envelope.material.material_version_id=id;
      recordTransformation(input,version.id,id,time);
    }
    if(time===at)Object.assign(input.envelope,{boundary:{released_attachment_id:old.id,acquired_attachment_id:acquired.id,at_ms:at,previous_material:previousMaterial,previous_anchor:{owner_id:ownerId,socket_id:'work',position_m:[...work.position_m],orientation_xyzw:[...work.orientation_xyzw]},previous_channels:input.envelope.channels.map(c=>({function_id:c.function_id,node_id:c.node_id,kind:c.kind,value:c.end_value,axis:c.axis,pivot_m:c.pivot_m}))}});
  }
  if(complete&&cold){
    const previousMaterial={...structuredClone(input.envelope.material),material_version_id:version.id,form:spec.input_form,dimensions:structuredClone(inputDimensions),support_local_mm:[0,-2,0]},id=version.id+':reduced',prior=input.context.snapshot.attachments.find(a=>a.id===input.envelope.attachment_id);requireAsset(prior,'binding','final retained cold attachment');Object.assign(prior,{released_at_ms:10000});const acquired={...prior,id:prior.id+':reduced',acquired_at_ms:10000,released_at_ms:null};input.context.snapshot.attachments.push(acquired);input.envelope.attachment_id=acquired.id;
    input.context.snapshot.material_versions.push(Object.assign(structuredClone(version),{id,ordinal:2,form:'THIN_STRIP',dimensions:structuredClone(outputDimensions),cause_event_id:'synthetic:T21:transform:'+id}));Object.assign(material,{current_version_id:id,form:'THIN_STRIP',dimensions:structuredClone(outputDimensions)});input.envelope.material.material_version_id=id;recordTransformation(input,version.id,id,time);
    Object.assign(input.envelope,{boundary:{released_attachment_id:prior.id,acquired_attachment_id:acquired.id,at_ms:10000,previous_material:previousMaterial,previous_anchor:structuredClone(input.envelope.anchor),previous_channels:input.envelope.channels.map(c=>({function_id:c.function_id,node_id:c.node_id,kind:c.kind,value:c.end_value,axis:c.axis,pivot_m:c.pivot_m}))}});
  }
  return {envelope:input.envelope,context:{...input.context,world,asset_bindings:bindings,authorizations:[input.envelope]},frame,ownerPose:owner.pose};
}
function looperRequest(manifest:AssetManifest,asset:Asset,frame:Frame,manifestHash:string,speed:1|2|4){
  const fn=frame.name.split(':')[1];requireAsset(fn==='entry_looper_lift'||fn==='exit_looper_lift','binding','Explicit looper source phase');
  const request=basePhaseRequest(manifest,asset,{name:'idle',progress:0,clock:'paused'},manifestHash,speed),e=request.envelope,s=request.context.snapshot,binding=request.context.asset_bindings[0],socketId=fn==='entry_looper_lift'?'entry_looper_support':'exit_looper_support',socket=binding?.sockets.find(s=>s.socket_id===socketId),part=asset.moving_parts.find(p=>p.function===fn&&p.binding.type==='clip');requireAsset(binding&&socket&&part,'binding','Actual fixed looper inlet surface');
  const time=Math.round(frame.progress*10000);Object.assign(e,{phase_start_ms:0,phase_end_ms:10000,confirmed_sim_ms:time,effective_sim_ms:time,frozen_progress:frame.progress,clock_state:frame.clock});
  e.anchor={owner_id:binding.owner_id,socket_id:socketId,position_m:[...socket.position_m],orientation_xyzw:[...socket.orientation_xyzw]};
  Reflect.deleteProperty(e.material,'internal_feed');const thickness=e.material.dimensions.thickness_mm;requireAsset(thickness!==null,'binding','Actual looper sheet thickness');Object.assign(e.material,{support_local_mm:[0,-thickness/2,0],orientation_xyzw:[0,0,0,1]});
  const attachment=s.attachments.find(a=>a.id===e.attachment_id);requireAsset(attachment,'binding','Explicit synthetic looper starting custody');attachment.socket_id=socketId;
  for(const channel of e.channels){const value=channel.function_id===fn?part.range.max*pulse(frame.progress):0;channel.start_value=value;channel.end_value=value;}
  Object.assign(s.run,{elapsed_ms:time,playing:frame.clock==='running',speed});for(const process of s.processes)process.status=frame.clock==='blocked'?'BLOCKED':'RUNNING';
  request.context.authorizations=[structuredClone(e)];return {...request,frame};
}

function continuityRequest(manifest:AssetManifest,asset:Asset,frame:Frame,manifestHash:string,speed:1|2|4){
  requireAsset(sourceRoots.accepted_roots.some(r=>r.manifest_sha256===manifestHash),'stale','Exact source-derived fixture root; fresh physical gate remains required');
  const corpus=loadedCorpus;requireAsset(corpus,'binding','Explicit sequence corpus must load before selecting source phase');
  const replay=frame.name.startsWith('replay:')?frame.name.split(':'):null,replayOwner=replay?.[1],replayMode=replay?.[2],replayName=replayOwner?replayOwner+((replayOwner==='CS-GO-05'||replayOwner==='CS-NGO-05')?'-cold-half':'-feed-mid'):null;
  const seed=replayName?corpus.sequence_cases.find(c=>c.name===replayName):frame.name.startsWith('sequence:')?corpus.sequence_cases.find(c=>'sequence:'+c.name===frame.name):corpus.continuity_cases.find(c=>'continuity:'+c.name===frame.name);requireAsset(seed,'binding','explicit source continuity seed');const sharedContext=corpus.contexts[seed.context_id];requireAsset(sharedContext,'binding','exact deduplicated seed context');
  const fixtureContext=z.object({snapshot:z.object({run:z.record(z.string(),z.unknown())}).passthrough(),world:z.object({owners:z.array(z.object({id:z.string(),pose:poseSchema}).passthrough())}).passthrough(),asset_bindings:z.array(z.unknown()),authorizations:z.array(z.unknown())}).passthrough();
  const request=structuredClone({envelope:parseMotionEnvelopeValue(seed.request.envelope),context:fixtureContext.parse({...seed.request.context,...sharedContext})}),ownerId=request.envelope.anchor.owner_id;requireAsset(asset.placement_ids[0]==='equipment:'+ownerId,'binding','source continuity owner');
  const families:Record<string,string>={};for(const s of asset.sockets){const form=s.forms[0];requireAsset(form,'binding','actual socket family');families[s.id]=form;}
  const bindings=bindingsFromAssetManifest(manifest,[{owner_id:ownerId,asset_id:asset.id,socket_families:families}]);requireAsset(JSON.stringify(bindings)===JSON.stringify(request.context.asset_bindings),'stale','actual manifest-derived canonical bindings changed');
  Object.assign(request.envelope,{bundle_hash:manifestHash,bundle_id:'synthetic-finishing-'+manifestHash.slice(0,16)});Object.assign(request.context.snapshot.run,{bundle_hash:manifestHash,bundle_id:request.envelope.bundle_id,speed});if(replayMode){const clock=replayMode==='blocked'?'blocked':replayMode==='paused'?'paused':'running',playing=clock==='running',replaySpeed=replayMode==='speed2'?2:replayMode==='speed4'?4:1;request.envelope={...request.envelope,clock_state:clock};Object.assign(request.context.snapshot.run,{playing,speed:replaySpeed});const processes=z.array(z.object({id:z.string(),status:z.string()}).passthrough()).parse(request.context.snapshot['processes']);for(const process of processes)if(process.id===request.envelope.execution_id)process.status=clock==='blocked'?'BLOCKED':'RUNNING';Object.assign(request.context.snapshot,{processes});}
  Object.assign(request.context,{authorizations:[structuredClone(request.envelope)]});
  const owner=request.context.world.owners.find(o=>o.id===ownerId);requireAsset(owner,'binding','retained source world owner');return {...request,frame,ownerPose:poseSchema.parse(owner.pose)};
}
function mainProcessRequest(manifest:AssetManifest,asset:Asset,frame:Frame,manifestHash:string,speed:1|2|4){
  const owner=asset.placement_ids[0]?.replace('equipment:',''),spec=recipe.models.find(m=>m.variant===asset.variant),cfg=spec?.source_internal_sequence;requireAsset((owner==='CS-CR-05'||owner==='CS-GO-08')&&cfg?.stroke_m===4,'binding','Existing exact4m source main-feed owners only');
  const request=continuityRequest(manifest,asset,{name:'sequence:'+owner+'-feed-mid',progress:.5,clock:'paused'},manifestHash,speed),time=6000+Math.round(4000*frame.progress),envelope={...request.envelope,confirmed_sim_ms:time,effective_sim_ms:time,frozen_progress:time/10000,clock_state:frame.clock,channels:request.envelope.channels.map(c=>{let value=0;if(c.function_id===cfg.driver||c.function_id==='cleaning_brush'){const part=asset.moving_parts.find(p=>p.function===c.function_id&&p.binding.type==='clip');requireAsset(part,'binding','Actual source main driver');value=part.range.max*frame.progress;}if(c.function_id==='thermal_chamber')value=frame.progress>=.2&&frame.progress<=.8?1:0;return {...c,start_value:value,end_value:value};})};
  Object.assign(request.context.snapshot.run,{elapsed_ms:time,playing:frame.clock==='running',speed});const processes=z.array(z.object({id:z.string(),status:z.string()}).passthrough()).parse(request.context.snapshot['processes']);for(const process of processes)if(process.id===envelope.execution_id)process.status=frame.clock==='blocked'?'BLOCKED':'RUNNING';return {...request,envelope,context:{...request.context,snapshot:{...request.context.snapshot,processes},authorizations:[envelope]},frame};
}
function recordTransformation(input:ReturnType<typeof fixture>,oldId:string,newId:string,time:number){
  const state=input.context.snapshot,batch=state.process_batches.find(b=>b.id==='motion-batch'),v=state.material_versions.find(v=>v.id===newId);requireAsset(batch&&v,'binding','complete synthetic history');const id='synthetic:T21:transform:'+newId,nextBatch=batch.id+':after:'+newId;Object.assign(v,{cause_event_id:id});Object.assign(batch,{recipe_id:input.envelope.recipe_id,status:'COMPLETED',end_ms:time});if(time<10000)state.process_batches.push({...batch,id:nextBatch,status:'RUNNING',start_ms:time,end_ms:10000});state.batch_io.push({run_id:state.run.id,id:id+':output',batch_id:batch.id,role:'OUTPUT',material_version_id:newId,quantity_kg:v.weight_kg,source_id:null});if(time<10000)state.batch_io.push({run_id:state.run.id,id:id+':input',batch_id:nextBatch,role:'INPUT',material_version_id:newId,quantity_kg:v.weight_kg,source_id:null});state.version_edges.push({run_id:state.run.id,id:id+':edge',batch_id:batch.id,input_version_id:oldId,output_version_id:newId,transferred_kg:v.weight_kg});Object.assign(state,{events:[...state.events,{run_id:state.run.id,id,sequence:1,event_type:'MATERIAL_TRANSFORMED',entity_type:'material',entity_id:v.material_id,at_ms:time,occurred_at:new Date(businessEpochMs(time)).toISOString(),source_id:'synthetic:T21:finishing-fixture',payload:{reason_code:'SYNTHETIC_ASSET_FIXTURE',reason:'Explicit synthetic retained source transformation; no live producer event',material_ids:[v.material_id],process_id:input.envelope.execution_id,batch_id:batch.id}}]});state.run.event_sequence=1;
}
export function sampleRequest(request:ReturnType<typeof phaseRequest>){const envelope=parseMotionEnvelopeValue(request.envelope),context=parseMotionContext(request.context),pose=evaluateMotion(envelope,context,recipes);return {pose,envelope,context,snapshot:context.snapshot,frame:request.frame,ownerPose:request.ownerPose,fixtureAuthority:'explicit synthetic T58 fixture; canonical owner world retained; additional sockets only; no live producer claim'};}
export function phaseSample(manifest:AssetManifest,asset:Asset,frame:Frame,manifestHash:string,speed:1|2|4=1){return sampleRequest(phaseRequest(manifest,asset,frame,manifestHash,speed));}
export type FamilySample=ReturnType<typeof phaseSample>;
