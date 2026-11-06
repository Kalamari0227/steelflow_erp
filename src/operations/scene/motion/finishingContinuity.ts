import { z } from 'zod';
import type { Asset } from '../assets/manifestShape';
import registrationJson from '../../../../shared/finishing-subassemblies.json';
import type { AssetBinding, ChannelValue, MotionEnvelope } from './shapes';
import type { InternalFeed, FeedWitness } from './internalFeed';
import type { Point } from '../worldContractMath';
import { distance } from '../worldContractMath';
import type { Transform } from './geometry';
import { rotatePoint, transformPoint } from './geometry';
import { equalData, requireMotion } from './errors';

const text=z.string().min(1),names=z.array(text).readonly();
const subassembly=z.strictObject({requirement_id:text,owner_id:text,section:text,moving_functions:names,state_functions:names,new_moving:names,new_state:names,stable_subassembly_id:text}).readonly();
const sequence=z.strictObject({owner_id:text,source_recipe_id:text,policy_id:text,unwind_function_id:text,feed_function_id:text,lift_function_id:text,coil_socket_id:text,strip_socket_id:text,feed_socket_id:text,cold_entry_socket_id:text.nullable(),added_moving_functions:names}).readonly();
const support=z.strictObject({owner_id:text,source_recipe_id:text,policy_id:text,socket_id:text,role:z.literal('support'),family:z.enum(['COIL','STRIP']),motion_function_ids:names}).readonly();
const registration=z.strictObject({schema_version:z.literal(1),rows:z.array(subassembly).readonly(),source_internal_sequences:z.array(sequence).readonly(),support_socket_registrations:z.array(support).readonly()}).readonly();
const trusted=registration.parse(structuredClone(registrationJson));
export const supportSocketRegistrations=trusted.support_socket_registrations;
export function sequenceFor(binding:{readonly owner_id:string;readonly policy_id:string}) {
  return trusted.source_internal_sequences.find(s=>s.owner_id===binding.owner_id && s.policy_id===binding.policy_id);
}

export function validateRegisteredSockets(binding:AssetBinding):void {
  for(const socket of binding.sockets){
    if(!supportSocketRegistrations.some(r=>r.socket_id===socket.socket_id) && !/^(line_|cold_)/.test(socket.socket_id))continue;
    const row=supportSocketRegistrations.find(r=>r.owner_id===binding.owner_id && r.policy_id===binding.policy_id && r.socket_id===socket.socket_id);
    requireMotion(row!==undefined && socket.family===row.family && equalData(socket.motion_function_ids,row.motion_function_ids),'binding',socket.socket_id);
  }
}

/** Optional immutable hardware metadata; omitted legacy profiles remain static. */
export function validateFeedLift(feed:InternalFeed,binding:AssetBinding):void {
  const id=feed.support_lift_function_id;
  if(id===undefined){requireMotion(!binding.functions.some(f=>f.function_id==='line_feed_lift'),'binding',feed.id);return;}
  const sequence=sequenceFor(binding);
  requireMotion(sequence!==undefined && id===sequence.lift_function_id && feed.driver_function_id===sequence.feed_function_id && feed.custody_socket_id===sequence.feed_socket_id,'binding',feed.id);
  const lift=binding.functions.find(f=>f.function_id===id);
  requireMotion(lift!==undefined && lift.kind==='translation' && equalData(lift.axis,[0,1,0]) && lift.min_value<0 && lift.max_value===0,'binding',feed.id);
}

export type ContactReceipt={readonly kind:'clamp_to_feed'|'feed_to_cold';readonly previous_part_id:string;readonly current_part_id:string;readonly previous_m:Point;readonly current_m:Point;readonly distance_m:number};
type Projection={readonly pose:Transform;readonly contact:Point;readonly witnesses:readonly FeedWitness[]};
export type FinishingBoundary={readonly envelope:MotionEnvelope;readonly binding:AssetBinding;readonly root:Transform;readonly previous:Projection;readonly current:Projection;readonly channels:readonly ChannelValue[]};
function held(channels:readonly ChannelValue[],id:string,value:number):boolean {return channels.some(c=>c.function_id===id && c.value===value);}
function sameWorld(input:FinishingBoundary):void {
  const event=input.envelope.boundary;requireMotion(event!==null,'boundary',input.envelope.execution_id);
  const old=event.previous_material,current=input.envelope.material,a=input.previous.pose,b=input.current.pose;
  requireMotion(old.material_id===current.material_id && old.material_version_id===current.material_version_id && old.form===current.form && equalData(old.dimensions,current.dimensions),'feed_boundary',current.material_id);
  requireMotion(distance(a.position_m,b.position_m)<=1e-6 && Math.abs(a.rotation_xyzw.reduce((sum,v,i)=>sum+v*(b.rotation_xyzw[i] ?? 0),0))>=1-1e-12,'feed_boundary',current.material_id);
  const d=current.dimensions;requireMotion(d.length_mm!==null && d.width_mm!==null && d.thickness_mm!==null,'feed_boundary',current.material_id);
  for(const x of [-d.length_mm/2000,d.length_mm/2000])for(const y of [-d.thickness_mm/2000,d.thickness_mm/2000])for(const z of [-d.width_mm/2000,d.width_mm/2000])requireMotion(distance(transformPoint(a,[x,y,z]),transformPoint(b,[x,y,z]))<=1e-6,'feed_boundary',current.material_id);
}
function coordinateOrder(a:Point,b:Point):number {return a[0]-b[0] || a[1]-b[1] || a[2]-b[2];}

/** Return an internal receipt; the ordinary pose contact remains the COM diagnostic. */
export function qualifiedContact(input:FinishingBoundary):ContactReceipt|undefined {
  const {envelope,binding}=input,event=envelope.boundary,sequence=sequenceFor(binding);
  if(event===null || sequence===undefined || event.previous_anchor.owner_id!==binding.owner_id)return undefined;
  const oldFeed='internal_feed' in event.previous_material,newFeed='internal_feed' in envelope.material;
  if(oldFeed===newFeed)return undefined;
  const reference='internal_feed' in event.previous_material ? event.previous_material.internal_feed : 'internal_feed' in envelope.material ? envelope.material.internal_feed : undefined;
  if(reference===undefined || !('internal_feeds' in binding))return undefined;
  const feed=binding.internal_feeds.find(f=>f.id===reference.feed_id);
  if(feed===undefined || feed.support_lift_function_id===undefined)return undefined;
  requireMotion(envelope.recipe_id===sequence.source_recipe_id,'binding',envelope.recipe_id);
  validateFeedLift(feed,binding);sameWorld(input);
  for(const channels of [event.previous_channels,input.channels])requireMotion(held(channels,sequence.lift_function_id,0) && held(channels,sequence.unwind_function_id,0),'binding',feed.id);
  const driver=binding.functions.find(f=>f.function_id===sequence.feed_function_id);requireMotion(driver!==undefined,'binding',feed.id);
  if(newFeed){
    requireMotion(event.previous_anchor.socket_id===sequence.strip_socket_id && envelope.anchor.socket_id===sequence.feed_socket_id,'binding',feed.id);
    const socket=binding.sockets.find(s=>s.socket_id===sequence.strip_socket_id);
    requireMotion(socket!==undefined && socket.family==='STRIP' && equalData(socket.motion_function_ids,[sequence.unwind_function_id]),'binding',feed.id);
    requireMotion([event.previous_channels,input.channels].every(c=>held(c,sequence.feed_function_id,driver.min_value)),'binding',feed.id);
    const chosen=[...input.current.witnesses].sort((a,b)=>distance(input.previous.contact,a.position_m)-distance(input.previous.contact,b.position_m) || (a.part_id<b.part_id ? -1 : a.part_id>b.part_id ? 1 : 0) || coordinateOrder(a.position_m,b.position_m))[0];
    requireMotion(chosen!==undefined,'contact',feed.id);
    const gap=distance(input.previous.contact,chosen.position_m);requireMotion(gap<=.01+1e-12,'contact',feed.id);
    return {kind:'clamp_to_feed',previous_part_id:'line_unwinding_mandrel_clamp_jaw',current_part_id:chosen.part_id,previous_m:input.previous.contact,current_m:chosen.position_m,distance_m:gap};
  }
  requireMotion(sequence.cold_entry_socket_id!==null && envelope.anchor.socket_id===sequence.cold_entry_socket_id && event.previous_anchor.socket_id===sequence.feed_socket_id,'binding',feed.id);
  const cold=binding.functions.find(f=>f.function_id==='cold_reduction_roll');
  requireMotion(cold!==undefined && cold.kind==='rotation' && equalData(cold.axis,[0,0,-1]),'binding',feed.id);
  for(const channels of [event.previous_channels,input.channels])requireMotion(held(channels,sequence.feed_function_id,driver.max_value) && held(channels,cold.function_id,0),'binding',feed.id);
  const old=event.previous_material;
  requireMotion(old.form==='STRIP' && old.dimensions.thickness_mm===4 && old.dimensions.length_mm===4000 && old.dimensions.width_mm===1200,'feed_boundary',feed.id);
  const radius=.36,bite=Math.sqrt(radius**2-(radius-.001)**2),point:Point=[cold.pivot_m[0]-bite,cold.pivot_m[1]+radius-.001,cold.pivot_m[2]],world=transformPoint(input.root,point);
  const q=input.root.rotation_xyzw,relative:Point=[world[0]-input.previous.pose.position_m[0],world[1]-input.previous.pose.position_m[1],world[2]-input.previous.pose.position_m[2]],local=rotatePoint([-q[0],-q[1],-q[2],q[3]],relative);
  requireMotion(Math.abs(local[0]-2)<=1e-6 && Math.abs(local[1]+.002)<=1e-6 && Math.abs(local[2])<=.6,'contact',feed.id);
  const socket=binding.sockets.find(s=>s.socket_id===sequence.cold_entry_socket_id);
  requireMotion(socket!==undefined && socket.family==='STRIP' && socket.motion_function_ids.length===0 && distance(socket.position_m,point)<=1e-9,'binding',feed.id);
  const gap=distance(world,input.current.contact);requireMotion(gap<=.01+1e-12,'contact',feed.id);
  return {kind:'feed_to_cold',previous_part_id:'cold_reduction_roll_barrel',current_part_id:'cold_reduction_roll_barrel',previous_m:world,current_m:input.current.contact,distance_m:gap};
}

export function registeredExtra(asset:Asset,socketId:string):boolean {
  const owner=asset.category==='equipment' ? asset.placement_ids[0]?.replace(/^equipment:/,'') ?? '' : '';
  return supportSocketRegistrations.some(row=>row.owner_id===owner && row.policy_id===asset.motion_policy_id && row.socket_id===socketId);
}
export function validateAssetSupportSockets(asset:Asset,complete=false):void {
  const owner=asset.placement_ids[0]?.replace(/^equipment:/,'') ?? '';
  for(const socket of asset.sockets){
    const reserved=supportSocketRegistrations.some(row=>row.socket_id===socket.id) || /^(line_|cold_)/.test(socket.id);
    if(!reserved)continue;
    const row=supportSocketRegistrations.find(row=>row.owner_id===owner && row.policy_id===asset.motion_policy_id && row.socket_id===socket.id);
    requireMotion(row!==undefined && socket.role===row.role && socket.forms.length===1 && socket.forms[0]===row.family,'requirements',`${asset.id}:support-extra:${socket.id}`);
    let node=asset.nodes.find(n=>n.id===socket.node_id);const chain:string[]=[];
    while(node){const moving=asset.moving_parts.find(p=>p.node_id===node?.id && p.role==='operational' && p.binding.type!=='mechanical_follower');if(moving)chain.unshift(moving.function);node=asset.nodes.find(n=>n.id===node?.parent_id);}
    requireMotion(chain.length===row.motion_function_ids.length && new Set(chain).size===chain.length && row.motion_function_ids.every(id=>chain.includes(id)),'requirements',`${asset.id}:support-chain:${socket.id}`);
    requireMotion(chain.every((id,i)=>id===row.motion_function_ids[i]),'requirements',`${asset.id}:support-order:${socket.id}`);
  }
  if(complete)for(const row of supportSocketRegistrations.filter(row=>row.owner_id===owner))requireMotion(registeredExtra(asset,row.socket_id) && asset.sockets.some(s=>s.id===row.socket_id),'requirements',`${asset.id}:finishing-support:${row.socket_id}`);
}
