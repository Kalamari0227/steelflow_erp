import {describe,it,expect} from 'vitest';
import seed from '../../../../shared/fixtures/internal-feed-cases.json';
import {parseMotionRequestValue} from './request';
import {evaluateMotion} from './contracts';
import {recipes} from './testFixtures';
import {validateFeedBoundary} from './internalFeed';
function phase(entry:(typeof seed.cases)[number],u:number){const raw=structuredClone(entry.request),e=entry.expected,c=raw.envelope.channels.find(c=>c.function_id===e.driver_function_id);if(!c)throw Error('Seed driver absent');c.start_value=c.end_value=e.driver_min+(e.driver_max-e.driver_min)*u;raw.context.authorizations=[raw.envelope];return raw;}
function evaluate(raw:unknown){const request=parseMotionRequestValue(raw);return evaluateMotion(request.envelope,request.context,recipes);}
describe('immutable linear roller feed public projection',()=>{
  expect(seed.cases).toHaveLength(16);
  for(const entry of seed.cases)it(`${entry.name} retains dimensions/datum through original knots`,()=>{
    for(const u of [0,.1,.25,.5,.75,.9,1]){const raw=phase(entry,u),pose=evaluate(raw),e=entry.expected;expect(pose.position_m[0]).toBeCloseTo((e.start_m[0] ?? NaN)+((e.end_m[0] ?? NaN)-(e.start_m[0] ?? NaN))*u,10);expect(pose.material.support_local_mm).toEqual([0,-(pose.material.dimensions.thickness_mm ?? 0)/2,0]);expect(pose.material).toHaveProperty('internal_feed',raw.envelope.material.internal_feed);expect(pose.attachment_id).toBe(entry.request.envelope.attachment_id);expect(parseMotionRequestValue(JSON.parse(JSON.stringify(parseMotionRequestValue(raw))))).toEqual(parseMotionRequestValue(raw));}
  });
  for(const mode of ['null','unknown','missing','wrong-id','support-rewrite','wrong-range','wrong-ratio','wrong-axis','sparse','narrow','one-sided'] as const)it(`rejects ${mode}`,()=>{
    const entry=seed.cases[0];if(!entry)throw Error('Seed required');const raw=phase(entry,.5),binding=raw.context.asset_bindings[0],material=raw.envelope.material;if(!binding || !('internal_feeds' in binding))throw Error('Feed binding required');const feed=binding.internal_feeds[0];if(!feed)throw Error('Feed required');
    if(mode==='null')Reflect.set(material,'internal_feed',null);
    if(mode==='unknown')Reflect.set(material.internal_feed,'unknown',1);
    if(mode==='missing')Reflect.deleteProperty(feed,'rollers');
    if(mode==='wrong-id')material.internal_feed.feed_id='missing-feed';
    if(mode==='support-rewrite')material.support_local_mm[0]=100;
    if(mode==='wrong-range'){const driver=binding.functions.find(f=>f.function_id===feed.driver_function_id);if(driver)driver.max_value+=1;}
    if(mode==='wrong-ratio'){const roller=feed.rollers[1];if(roller)roller.ratio=(roller.ratio ?? NaN)*2;}
    if(mode==='wrong-axis'){const driver=binding.functions.find(f=>f.function_id===feed.driver_function_id);if(driver)driver.axis=[0,0,1];}
    if(mode==='sparse')feed.rollers=feed.rollers.filter((_,i)=>i%4===0);
    if(mode==='narrow')for(const r of feed.rollers)r.width_m=.01;
    if(mode==='one-sided')feed.rollers=feed.rollers.filter(r=>(r.center_m[0] ?? NaN)<=0);
    raw.context.authorizations=[raw.envelope];expect(()=>evaluate(raw)).toThrow();
  });
  it('rejects same contact/datum disguising a rigid pose or version jump',()=>{const entry=seed.cases[0];if(!entry)throw Error('Seed required');const pose=evaluate(phase(entry,.5)),same={pose:{position_m:pose.position_m,rotation_xyzw:pose.orientation_xyzw},contact:pose.contact_m};expect(()=>validateFeedBoundary(same,{...same,pose:{...same.pose,position_m:[1,pose.position_m[1],0]}},pose.material,pose.material)).toThrow('feed_boundary:');expect(()=>validateFeedBoundary(same,same,pose.material,{...pose.material,material_version_id:'different-version'})).toThrow('feed_boundary:');});
});
for(const entry of seed.boundary_cases)it(entry.name,()=>{if(entry.error===null)expect(evaluate(entry.request).position_m[0]).toBeCloseTo(0,10);else expect(()=>evaluate(entry.request)).toThrow(`${entry.error}:`);});
it('checks corresponding eight corners beyond the quaternion tolerance',()=>{const entry=seed.cases[0];if(!entry)throw Error('Seed required');const pose=evaluate(phase(entry,.5)),material={...pose.material,dimensions:{...pose.material.dimensions,length_mm:1e9}},a={pose:{position_m:pose.position_m,rotation_xyzw:pose.orientation_xyzw},contact:pose.contact_m},angle=1e-7;expect(()=>validateFeedBoundary(a,{...a,pose:{...a.pose,rotation_xyzw:[0,Math.sin(angle/2),0,Math.cos(angle/2)]}},material,material)).toThrow('feed_boundary:');});
for(const [mode,code]of [['null-list','invalid_contract'],['unknown-kind','invalid_contract'],['nan-radius','invalid_contract'],['infinite-width','invalid_contract'],['zero-radius','invalid_contract'],['zero-width','invalid_contract'],['wrong-owner','binding'],['wrong-socket','binding'],['unknown-driver','binding'],['unknown-feed','binding'],['support-rewrite','feed_support']]as const)it(`typed malformed admission ${mode}`,()=>{
  const entry=seed.cases[0];if(!entry)throw Error('Seed required');const raw=phase(entry,.5),binding=raw.context.asset_bindings[0],feed=binding?.internal_feeds[0],roller=feed?.rollers[0];if(!binding||!feed||!roller)throw Error('Pinned feed required');
  if(mode==='null-list')Reflect.set(binding,'internal_feeds',null);
  if(mode==='unknown-kind')Reflect.set(feed,'kind','belt');
  if(mode==='nan-radius')roller.radius_m=NaN;
  if(mode==='infinite-width')roller.width_m=Infinity;
  if(mode==='zero-radius')roller.radius_m=0;
  if(mode==='zero-width')roller.width_m=0;
  if(mode==='wrong-owner')binding.owner_id='absent-owner';
  if(mode==='wrong-socket')feed.custody_socket_id='absent-socket';
  if(mode==='unknown-driver')feed.driver_function_id='absent-driver';
  if(mode==='unknown-feed')raw.envelope.material.internal_feed.feed_id='absent-feed';
  if(mode==='support-rewrite')raw.envelope.material.support_local_mm[0]=1;
  raw.context.authorizations=[raw.envelope];expect(()=>evaluate(raw)).toThrow(`${code}:`);
});
