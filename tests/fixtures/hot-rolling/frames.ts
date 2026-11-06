import type { Asset, AssetManifest } from '../../../src/operations/scene/assets/manifest';
import { bindingsFromAssetManifest, evaluateMotion, parseMotionContext, parseMotionEnvelopeValue } from '../../../src/operations/scene/motion/contracts';
import type { MotionPose } from '../../../src/operations/scene/motion/contracts';
import { fixture, recipes } from '../../../src/operations/scene/motion/testFixtures';
import { evaluateInternalFeed, validatePathSupport } from '../../../src/operations/scene/motion/internalFeed';
import { anchorTransform } from '../../../src/operations/scene/motion/kinematics';
import { channelValues } from '../../../src/operations/scene/motion/kinematics';
import { requireAsset } from '../../../src/operations/scene/assets/errors';

export const frames = [
  { name: 'idle', progress: 0, clock: 'paused', feed: 0, stroke: 0, heat: 0 },
  { name: 'entry', progress: .2, clock: 'running', feed: .1, stroke: 0, heat: 0 },
  { name: 'running-25', progress: .35, clock: 'running', feed: .25, stroke: .5, heat: 1 },
  { name: 'running-50', progress: .5, clock: 'running', feed: .5, stroke: 1, heat: 1 },
  { name: 'blocked', progress: .5, clock: 'blocked', feed: .5, stroke: 1, heat: 1 },
  { name: 'paused', progress: .5, clock: 'paused', feed: .5, stroke: 1, heat: 1 },
  { name: 'resumed', progress: .5, clock: 'running', feed: .5, stroke: 1, heat: 1 },
  { name: 'running-75', progress: .65, clock: 'running', feed: .75, stroke: .5, heat: 1 },
  { name: 'exit', progress: .8, clock: 'running', feed: .9, stroke: 0, heat: 0 },
  { name: 'complete', progress: 1, clock: 'paused', feed: 1, stroke: 0, heat: 0 },
] as const;
export type Frame = { readonly name:string; readonly progress:number; readonly clock:'running'|'paused'|'blocked'; readonly feed:number; readonly stroke:number; readonly heat:number };
export const coilerContactFrames: readonly Frame[] = [...Array.from({length:21},(_,i) => i/20),.4999,.5001].sort((a,b) => a-b).map(feed => ({name:`contact-${feed.toFixed(4)}`,progress:feed,clock:'paused',feed,stroke:0,heat:1}));
export const layingContactFrames:readonly Frame[]=Array.from({length:101},(_,i)=>({name:`laying-${(i/100).toFixed(4)}`,progress:i/100,clock:'paused',feed:i/100,stroke:0,heat:1}));

export const bedBoundaryFrames:readonly Frame[]=[{name:'handoff-before',progress:.5,clock:'paused',feed:.5,stroke:1,heat:1},{name:'handoff',progress:.5,clock:'paused',feed:.5,stroke:1,heat:1}];

export const feedKnots:readonly (readonly [number,number])[]=[[0,0],[.2,.1],[.35,.25],[.5,.5],[.65,.75],[.8,.9],[1,1]];
export function feedAtProgress(progress:number):number {
  for(let i=1;i<feedKnots.length;i++){const a=feedKnots[i-1],b=feedKnots[i];if(a && b && progress>=a[0] && progress<=b[0])return progress===a[0] ? a[1] : progress===b[0] ? b[1] : a[1]+(b[1]-a[1])*(progress-a[0])/(b[0]-a[0]);}
  throw new Error('Synthetic phase outside declared schedule');
}
export function doorAtProgress(progress:number){return progress<=.2 ? progress/.2 : progress<=.8 ? 1 : progress===1 ? 0 : (1-progress)/.2;}

export function internalFeedContactFrames(asset:Asset):readonly Frame[]{
  const profile=asset.internal_feeds?.[0];if(!profile)return [];
  const length=['furnace','heat_treatment'].includes(asset.kind) ? 1.8 : 6,start=profile.start_m[0],end=profile.end_m[0];
  const xs=profile.rollers.map(r=>{const p=asset.moving_parts.find(p=>p.id===r.part_id),n=asset.nodes.find(n=>n.id===p?.node_id);requireAsset(n && n.parent_id===asset.root_node_id,'binding','direct authored feed pivot');return n.transform.position_m[0];});
  const points=[...new Set([start,end,...xs.flatMap(x=>[x-length/2,x+length/2]).filter(x=>x>start && x<end)])].sort((a,b)=>a-b),centers=[...points,...points.slice(1).map((x,i)=>(x+(points[i] ?? x))/2)];
  const inverse=(u:number)=>{for(let i=1;i<feedKnots.length;i++){const a=feedKnots[i-1],b=feedKnots[i];if(a && b && u>=a[1] && u<=b[1])return a[0]+(b[0]-a[0])*(u-a[1])/(b[1]-a[1]);}throw new Error('Outside feed schedule');};
  const phases=[...feedKnots.map(k=>k[0]),...centers.map(x=>inverse((x-start)/(end-start)))];
  if(asset.kind==='furnace'){const door=asset.nodes.find(n=>n.id==='furnace_door');if(door)for(const x of [door.transform.position_m[0]-.3,door.transform.position_m[0]+.3])for(const edge of [-length/2,length/2]){const u=(x+edge-start)/(end-start);if(u>=0 && u<=1){const p=inverse(u);phases.push(...[p-.0001,p,p+.0001].filter(v=>v>=0 && v<=1));}}}
  return [...new Map(phases.sort((a,b)=>a-b).map(progress=>{const name=`feed-${progress.toFixed(6)}`;return [name,{name,progress,clock:'paused' as const,feed:feedAtProgress(progress),stroke:0,heat:progress>.2 && progress<.8 ? 1 : 0}];})).values()];
}

/** Explicit authorized synthetic phase samples. The wall clock never advances machinery. */
export function preparePhase(manifest: AssetManifest, asset: Asset, bundleHash?:string, speed:1|2|4=1) {
  const ownerId = asset.placement_ids[0]?.replace(/^equipment:/, '');
  requireAsset(ownerId, 'binding', 'hot-rolling placement');
  const families: Record<string, string> = {};
  for (const socket of asset.sockets) { const form = socket.forms[0]; requireAsset(form, 'binding', socket.id); families[socket.id] = form; }
  const bindings = bindingsFromAssetManifest(manifest, [{ owner_id: ownerId, asset_id: asset.id, socket_families: families }]);
  const binding = bindings[0];
  if(asset.internal_feeds)requireAsset(bundleHash && /^[a-f0-9]{64}$/.test(bundleHash),'binding','pinned synthetic asset bundle hash');
  return (frame:Frame) => {
  const input=fixture(),profile=asset.internal_feeds?.[0];
  if(bundleHash){const bundleId='synthetic-hot-rolling-'+bundleHash.slice(0,16);Object.assign(input.envelope,{bundle_hash:bundleHash,bundle_id:bundleId});Object.assign(input.context.snapshot.run,{bundle_hash:bundleHash,bundle_id:bundleId});}
  let support = binding?.sockets.find(s => s.socket_id === 'work');
  const bedReceived=asset.kind==='cooling_bed' && ['handoff','running-75','exit','complete'].includes(frame.name);
  if (bedReceived) support=binding?.sockets.find(s => s.socket_id === 'bed_received');
  const feedSockets = profile ? [] : binding?.sockets.filter(s => s.socket_id.startsWith('feed_contact_')) ?? [];
  let centerX = support?.position_m[0] ?? 0;
  if (feedSockets.length) {
    const first=feedSockets[0],last=feedSockets.at(-1); requireAsset(first && last,'binding','feed support endpoints');
    centerX=first.position_m[0]+(last.position_m[0]-first.position_m[0])*frame.feed;
    support=feedSockets.reduce((a,b) => Math.abs(a.position_m[0]-centerX)<Math.abs(b.position_m[0]-centerX) ? a : b);
  }
  requireAsset(binding && support, 'binding', 'authored work support');
  const sourceStep = asset.requirement_ids.find(id => /^src:(?:hr|plate|wire)-\d+$/.test(id))?.slice(4) ?? 'hr-04';
  const recipe = recipes.recipes.find(r => r.id === `motion:source:${sourceStep}`);
  requireAsset(recipe, 'binding', sourceStep);
  const form = asset.kind === 'laying_head' ? 'WIRE_COIL' : asset.sockets.find(s => s.id === 'work')?.forms[0]; requireAsset(form, 'binding', 'work form');
  const thickness = form === 'WIRE_COIL' ? 60 : form === 'STRIP' ? 12 : form === 'BLOOM' ? 350 : form === 'BILLET' ? 220 : 180;
  const width = asset.placement_ids.some(id => id==='equipment:CS-PLATE-06') ? 3600 : form === 'WIRE_COIL' ? 250 : form === 'BLOOM' ? 350 : form === 'BILLET' ? 220 : 1200;
  const dimensions = { length_mm: form === 'WIRE_COIL' ? null : ['furnace','heat_treatment'].includes(asset.kind) ? 1800 : asset.kind === 'coiler' ? 4000 : 6000, width_mm: width, thickness_mm: thickness, diameter_mm: form === 'WIRE_COIL' ? 1800 : null, inner_diameter_mm: form === 'WIRE_COIL' ? 1680 : null };
  Object.assign(input.envelope, { recipe_id: recipe.id, frozen_progress: frame.progress, clock_state: frame.clock });
  input.context.snapshot.run.speed=speed;
  input.context.snapshot.run.playing = frame.clock === 'running';
  input.envelope.anchor = { owner_id: ownerId, socket_id: support.socket_id, position_m: [...support.position_m], orientation_xyzw: [...support.orientation_xyzw] };
  Object.assign(input.envelope.material, { form, dimensions, support_local_mm: [feedSockets.length ? (support.position_m[0]-centerX)*1000 : asset.kind === 'coiler' ? support.position_m[0]*1000 : asset.kind === 'laying_head' ? (support.position_m[0]+2)*1000 : ['shear','cooling_bed'].includes(asset.kind) ? 0 : (0.5-frame.feed)*5400, asset.kind === 'coiler' ? (support.position_m[1]-1.326)*1000 : -thickness/2, asset.kind === 'coiler' ? (support.position_m[2]-.35)*1000 : 0], orientation_xyzw: [0,0,0,1] });
  if(profile)Object.assign(input.envelope.material,{internal_feed:{schema_version:1,feed_id:profile.id},support_local_mm:[0,-thickness/2,0]});
  input.envelope.channels = binding.functions.map(fn => {
    const need = recipe.functions.find(f => f.function_id === fn.function_id); requireAsset(need, 'binding', fn.function_id);
    const normalized = asset.placement_ids.some(id => id==='equipment:CS-PLATE-06') && fn.function_id === 'cutting_tool' ? frame.feed : fn.function_id === 'coolant_valve' ? frame.heat : fn.function_id === 'furnace_door' ? doorAtProgress(frame.progress) : fn.kind === 'state' ? frame.heat : fn.kind === 'translation' ? frame.stroke : profile ? feedAtProgress(frame.progress) : frame.feed;
    const value = fn.min_value + (fn.max_value-fn.min_value)*normalized;
    return { function_id: fn.function_id, node_id: fn.node_id, kind: fn.kind, window_id: need.window_id, axis: [...fn.axis], pivot_m: [...fn.pivot_m], start_value: value, end_value: value };
  });
  for (const owner of input.context.world.owners) { owner.id = ownerId; owner.sockets.push(...binding.sockets.map(s => ({ id: s.socket_id, pose: { position: [...s.position_m], yaw_rad: 0 } }))); }
  for (const row of [...input.context.world.slots, ...input.context.world.ports, ...input.context.world.footprints, ...input.context.world.allowed_interiors]) row.owner_id = ownerId;
  for (const process of input.context.snapshot.processes) Object.assign(process, { equipment_id: ownerId, route_step_id: `${sourceStep.split('-')[0]}:${sourceStep}`, status: frame.clock === 'blocked' ? 'BLOCKED' : 'RUNNING' });
  for (const material of input.context.snapshot.materials) if (material.id === input.envelope.material.material_id) Object.assign(material, { form, dimensions: structuredClone(dimensions) });
  for (const version of input.context.snapshot.material_versions) if (version.id === input.envelope.material.material_version_id) Object.assign(version, { form, dimensions: structuredClone(dimensions) });
  for (const stock of input.context.snapshot.stock_lots) if (stock.id === input.envelope.material.material_id) stock.form = form;
  for (const attachment of input.context.snapshot.attachments) if (attachment.id === input.envelope.attachment_id) Object.assign(attachment, { kind: 'equipment', owner_id: ownerId, socket_id: asset.kind==='cooling_bed' ? 'work' : support.socket_id });
  if(asset.kind==='cooling_bed') {
    const atMs=1000,now=Math.round(frame.progress*2000),old=input.context.snapshot.attachments.find(a => a.id===input.envelope.attachment_id),work=binding.sockets.find(s => s.socket_id==='work');
    requireAsset(old && work,'binding','retained bed attachment');
    old.acquired_at_ms=0;input.context.snapshot.run.elapsed_ms=now;Object.assign(input.envelope,{confirmed_sim_ms:now,effective_sim_ms:now});
    if(bedReceived) {
      Object.assign(old,{released_at_ms:atMs});
      const acquired={...old,id:old.id+'-bed-received',socket_id:'bed_received',acquired_at_ms:atMs,released_at_ms:null};
      input.context.snapshot.attachments.push(acquired);input.envelope.attachment_id=acquired.id;
      if(now===atMs) Object.assign(input.envelope,{boundary:{released_attachment_id:old.id,acquired_attachment_id:acquired.id,at_ms:atMs,previous_material:structuredClone(input.envelope.material),previous_anchor:{owner_id:ownerId,socket_id:work.socket_id,position_m:[...work.position_m],orientation_xyzw:[...work.orientation_xyzw]},previous_channels:binding.functions.map(fn => ({function_id:fn.function_id,node_id:fn.node_id,kind:fn.kind,value:fn.max_value,axis:[...fn.axis],pivot_m:[...fn.pivot_m]}))}});
    }
  }
  let envelope=parseMotionEnvelopeValue(input.envelope),context=parseMotionContext({...input.context,asset_bindings:bindings,authorizations:[envelope]});
  const evaluatedChannels=channelValues(envelope,recipe,context),driver=asset.moving_parts.find(p => p.binding.type==='clip' && p.motion==='rotation' && p.function!=='coolant_valve'),canonical=evaluatedChannels.find(c => c.function_id===driver?.function);
  const feed=driver && canonical ? (canonical.value-driver.range.min)/(driver.range.max-driver.range.min) : 0;
  const fixedLinear=!profile && !feedSockets.length && !['coiler','laying_head','shear','cooling_bed'].includes(asset.kind);
  if(fixedLinear) {
    requireAsset(driver && canonical,'binding','fixed support canonical feed law');
    input.envelope.material.support_local_mm[0]=(0.5-feed)*5400;
    envelope=parseMotionEnvelopeValue(input.envelope);context=parseMotionContext({...input.context,asset_bindings:bindings,authorizations:[envelope]});
  }
  const pose:MotionPose=evaluateMotion(envelope,context,recipes);
  const internalProjection=profile ? evaluateInternalFeed(envelope.anchor,envelope.material,pose.channels,binding,anchorTransform(envelope.anchor,context)) : null;
  const feedBinding='internal_feeds' in binding ? binding.internal_feeds[0] : undefined;
  const continuousSupport=feedBinding ? validatePathSupport(feedBinding,(dimensions.length_mm ?? 0)/1000,width/1000) : null;
  return {internalProjection,continuousSupport,pose,envelope,context,snapshot:context.snapshot,frame,supportLaw:{synthetic:true,driverFunction:driver?.function ?? null,driverValue:canonical?.value ?? null,normalizedFeed:feed,displacementM:fixedLinear ? feed*5.4 : 0,mode:fixedLinear ? 'canonical-fixed-support-linear-feed' : asset.kind==='shear' ? 'stationary-cut' : 'declared-forming-or-support-mechanism'}};
}
}

export function phaseSample(manifest:AssetManifest,asset:Asset,frame:Frame,bundleHash?:string){return preparePhase(manifest,asset,bundleHash)(frame);}
