import { z } from 'zod';
import { validateFeedLift } from './finishingContinuity';
import type { Point } from '../worldContractMath';
import { distance } from '../worldContractMath';
import { requireMotion, equalData } from './errors';
import { rotatePoint, transformPoint } from './geometry';
import type { Transform, Quaternion } from './geometry';
import type { Anchor, AssetBinding, ChannelValue, MaterialSupport } from './shapes';

const text=z.string().min(1),finite=z.number().finite(),vector=z.tuple([finite,finite,finite]).readonly();
const rollerFields={part_id:text,surface_node_id:text,radius_m:finite.positive(),width_m:finite.positive()};
const feedFields={schema_version:z.literal(1),id:text,kind:z.literal('linear_roller_feed'),custody_socket_id:text,start_m:vector,end_m:vector};
export const internalFeedAssetShape=z.strictObject({...feedFields,driver_part_id:text,support_lift_part_id:text.optional(),rollers:z.array(z.strictObject(rollerFields).readonly()).min(2).max(64).readonly()}).readonly();
export const internalFeedBindingShape=z.strictObject({...feedFields,driver_function_id:text,support_lift_function_id:text.optional(),rollers:z.array(z.strictObject({...rollerFields,center_m:vector,ratio:finite.positive()}).readonly()).min(2).max(64).readonly()}).readonly();
export const internalFeedReferenceShape=z.strictObject({schema_version:z.literal(1),feed_id:text}).readonly();
export type InternalFeed=z.infer<typeof internalFeedBindingShape>;
export type InternalFeedAsset=z.infer<typeof internalFeedAssetShape>;
export type FeedWitness={readonly part_id:string;readonly position_m:Point;readonly normal:Point};
export type FeedProjection={readonly position_m:Point;readonly orientation_xyzw:Quaternion;readonly contact_m:Point;readonly witnesses:readonly FeedWitness[]};

export function validateInternalFeed(feed:InternalFeed,binding:AssetBinding):void {
  validateFeedLift(feed,binding);
  const socket=binding.sockets.find(s=>s.socket_id===feed.custody_socket_id),driver=binding.functions.find(f=>f.function_id===feed.driver_function_id);
  requireMotion(socket!==undefined && socket.motion_function_ids.length===0 && driver!==undefined && driver.kind==='rotation' && equalData(driver.axis,[0,0,-1]),'binding',feed.id);
  requireMotion(feed.start_m[0]<feed.end_m[0] && equalData(feed.start_m.slice(1),feed.end_m.slice(1)) && feed.start_m[2]===0,'binding',feed.id);
  requireMotion(new Set(feed.rollers.map(r=>r.part_id)).size===feed.rollers.length && new Set(feed.rollers.map(r=>r.surface_node_id)).size===feed.rollers.length,'binding',feed.id);
  const driving=feed.rollers.find(r=>r.part_id===driver.node_id);requireMotion(driving!==undefined,'binding',feed.id);
  requireMotion(Math.abs(feed.end_m[0]-feed.start_m[0]-driving.radius_m*(driver.max_value-driver.min_value))<=1e-9,'binding',feed.id);
  for(const r of feed.rollers){requireMotion(r.radius_m>0 && r.width_m>0 && r.center_m[2]===0 && Math.abs(r.center_m[1]+r.radius_m-feed.start_m[1])<=1e-9 && Math.abs(r.ratio-driving.radius_m/r.radius_m)<=1e-9,'binding',r.part_id);}
}

function supportAt(feed:InternalFeed,length:number,width:number,center:number) {
  const active=feed.rollers.filter(r=>Math.abs(r.center_m[0]-center)<=length/2);
  requireMotion(active.length>=2 && active.every(r=>r.width_m>=width) && Math.min(...active.map(r=>r.center_m[0]))<center && Math.max(...active.map(r=>r.center_m[0]))>center,'feed_support',feed.id);
  return active;
}
export function validatePathSupport(feed:InternalFeed,length:number,width:number):readonly number[] {
  const start=feed.start_m[0],end=feed.end_m[0],points=[...new Set([start,end,...feed.rollers.flatMap(r=>[r.center_m[0]-length/2,r.center_m[0]+length/2]).filter(x=>x>start && x<end)])].sort((a,b)=>a-b);
  requireMotion(points.length<=130,'feed_support',feed.id);
  for(const point of points)supportAt(feed,length,width,point);
  for(let i=1;i<points.length;i++){const a=points[i-1],b=points[i];requireMotion(a!==undefined && b!==undefined,'feed_support',feed.id);const active=supportAt(feed,length,width,(a+b)/2);requireMotion(Math.min(...active.map(r=>r.center_m[0]))<=a && Math.max(...active.map(r=>r.center_m[0]))>=b,'feed_support',feed.id);}
  return Object.freeze(points);
}

export function evaluateInternalFeed(anchor:Anchor,material:MaterialSupport,channels:readonly ChannelValue[],binding:AssetBinding,ownerRoot:Transform):FeedProjection {
  requireMotion('internal_feed' in material && 'internal_feeds' in binding,'binding',anchor.socket_id);
  const feed=binding.internal_feeds.find(f=>f.id===material.internal_feed.feed_id);requireMotion(feed!==undefined,'binding',material.internal_feed.feed_id);
  validateInternalFeed(feed,binding);
  if(feed.support_lift_function_id!==undefined)requireMotion(channels.some(c=>c.function_id===feed.support_lift_function_id && c.value===0),'binding',feed.id);
  requireMotion(anchor.socket_id===feed.custody_socket_id,'binding',feed.id);
  requireMotion(['SLAB','HOT_SLAB','BLOOM','HOT_BLOOM','BILLET','HOT_BILLET','STRIP','HOT_STRIP','THIN_STRIP','COATED_STRIP','PLATE','HOT_PLATE'].includes(material.form),'form',material.form);
  const d=material.dimensions;requireMotion(d.length_mm!==null && d.width_mm!==null && d.thickness_mm!==null && d.diameter_mm===null && d.inner_diameter_mm===null,'feed_support',feed.id);
  const length=d.length_mm/1000,width=d.width_mm/1000,thickness=d.thickness_mm/1000;
  requireMotion([length,width,thickness].every(v=>Number.isFinite(v) && v>0) && equalData(material.orientation_xyzw,[0,0,0,1]) && equalData(material.support_local_mm,[0,-d.thickness_mm/2,0]),'feed_support',feed.id);
  validatePathSupport(feed,length,width);
  const driver=binding.functions.find(f=>f.function_id===feed.driver_function_id),channel=channels.find(c=>c.function_id===feed.driver_function_id);requireMotion(driver!==undefined && channel!==undefined,'binding',feed.id);
  const u=(channel.value-driver.min_value)/(driver.max_value-driver.min_value);requireMotion(Number.isFinite(u) && u>=0 && u<=1,'binding',feed.id);
  const center:Point=u===0 ? feed.start_m : u===1 ? feed.end_m : [feed.start_m[0]+(feed.end_m[0]-feed.start_m[0])*u,feed.start_m[1],0];
  const active=supportAt(feed,length,width,center[0]),selected=[...active].sort((a,b)=>Math.abs(a.center_m[0]-center[0])-Math.abs(b.center_m[0]-center[0]) || (a.part_id<b.part_id ? -1 : a.part_id>b.part_id ? 1 : 0))[0];requireMotion(selected!==undefined,'feed_support',feed.id);
  const witnesses=active.flatMap(r=>[-width/4,0,width/4].map(z=>Object.freeze({part_id:r.part_id,position_m:transformPoint(ownerRoot,[r.center_m[0],feed.start_m[1],z]),normal:rotatePoint(ownerRoot.rotation_xyzw,[0,1,0])})));
  return Object.freeze({position_m:transformPoint(ownerRoot,[center[0],center[1]+thickness/2,0]),orientation_xyzw:ownerRoot.rotation_xyzw,contact_m:transformPoint(ownerRoot,[selected.center_m[0],feed.start_m[1],0]),witnesses:Object.freeze(witnesses)});
}

export function validateFeedBoundary(previous:{readonly pose:Transform;readonly contact:Point},current:{readonly pose:Transform;readonly contact:Point},previousMaterial:MaterialSupport,currentMaterial:MaterialSupport):void {
  if(!('internal_feed' in previousMaterial || 'internal_feed' in currentMaterial))return;
  const ref=currentMaterial.material_id;
  requireMotion(previousMaterial.material_version_id===currentMaterial.material_version_id && previousMaterial.form===currentMaterial.form && equalData(previousMaterial.dimensions,currentMaterial.dimensions),'feed_boundary',ref);
  requireMotion(distance(previous.pose.position_m,current.pose.position_m)<=.01+1e-12 && Math.abs(previous.pose.rotation_xyzw.reduce((sum,v,i)=>sum+v*(current.pose.rotation_xyzw[i] ?? 0),0))>=1-1e-12,'feed_boundary',ref);
  const d=currentMaterial.dimensions;requireMotion(d.length_mm!==null && d.width_mm!==null && d.thickness_mm!==null,'feed_boundary',ref);
  for(const x of [-d.length_mm/2000,d.length_mm/2000])for(const y of [-d.thickness_mm/2000,d.thickness_mm/2000])for(const z of [-d.width_mm/2000,d.width_mm/2000])requireMotion(distance(transformPoint(previous.pose,[x,y,z]),transformPoint(current.pose,[x,y,z]))<=.01+1e-12,'feed_boundary',ref);
}
