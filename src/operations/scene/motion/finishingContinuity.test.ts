import { describe,expect,it } from 'vitest';
import cases from '../../../../shared/fixtures/finishing-continuity-cases.json';
import legacy from '../../../../shared/fixtures/internal-feed-cases.json';
import registryJson from '../../../../shared/motion-recipes.json';
import { evaluateMotion,parseMotionRegistryValue } from './contracts';
import { parseMotionRequestValue } from './request';
import { anchorTransform,channelValues,supportEvaluation } from './kinematics';
import { qualifiedContact } from './finishingContinuity';
import { distance } from '../worldContractMath';

const registry=parseMotionRegistryValue(registryJson);
function evaluate(raw:unknown){const request=parseMotionRequestValue(raw);return evaluateMotion(request.envelope,request.context,registry);}
function required<T>(value:T|undefined):T {if(value===undefined)throw new Error('Required fixture absent');return value;}
function fresh(kind:string){return structuredClone(required(cases.cases.find(r=>r.kind===kind)).request);}
function authorized(raw:ReturnType<typeof fresh>){Reflect.set(raw.context,'authorizations',[structuredClone(raw.envelope)]);return raw;}

describe('closed finishing source-internal continuity',()=>{
  for(const row of cases.cases)it(`public request ${row.name}`,()=>{
    const pose=evaluate(row.request);expect(pose.material).toEqual(row.request.envelope.material);
    if(row.kind==='feed')return;
    const {envelope,context}=parseMotionRequestValue(row.request),event=envelope.boundary;
    expect(event).not.toBeNull();if(event===null)throw new Error('Boundary required');
    const recipe=required(registry.recipes.find(r=>r.id===envelope.recipe_id)),channels=channelValues(envelope,recipe,context),binding=required(context.asset_bindings.find(b=>b.owner_id===envelope.anchor.owner_id));
    const current=supportEvaluation({anchor:envelope.anchor,material:envelope.material,channels},context),previous=supportEvaluation({anchor:event.previous_anchor,material:event.previous_material,channels:event.previous_channels},context);
    const input={envelope,binding,root:anchorTransform(envelope.anchor,context),current,previous,channels},receipt=qualifiedContact(input);
    expect(receipt).toBeDefined();expect(receipt?.distance_m).toBeLessThanOrEqual(.01);
    expect(distance(previous.contact,current.contact)).toBeGreaterThan(.01);
    expect(distance(previous.pose.position_m,current.pose.position_m)).toBeLessThanOrEqual(1e-6);
    expect(pose.contact_m).toEqual(current.contact);
    for(let i=0;i<32;i++)expect(qualifiedContact(input)).toEqual(receipt);
    expect(Object.keys(pose).sort()).toEqual(['run_id','revision','execution_id','recipe_id','material','attachment_id','owner_id','socket_id','position_m','contact_m','orientation_xyzw','progress','phase_complete','channels'].sort());
  });
  for(const value of [-.02,-1e-16])it(`rejects exact nonzero lift ${value}`,()=>{
    const raw=fresh('feed'),lift=required(raw.envelope.channels.find(c=>c.function_id==='line_feed_lift'));lift.start_value=lift.end_value=value;
    expect(()=>evaluate(authorized(raw))).toThrow('binding:');
  });
  for(const mode of ['null','unknown','wrong-owner','wrong-kind','wrong-axis','positive-max','missing-channel','wrong-driver','driver-interval','omitted-descriptor','unknown-socket'] as const)it(`rejects immutable lift ${mode}`,()=>{
    const raw=fresh('feed'),binding=required(raw.context.asset_bindings[0]),feed=required(binding.internal_feeds[0]),lift=required(binding.functions.find(f=>f.function_id==='line_feed_lift'));
    if(mode==='unknown-socket'){required(binding.sockets.find(s=>s.socket_id==='line_coil_support')).socket_id='line_forged_support';const owner=required(raw.context.world.owners.find(o=>o.id===binding.owner_id));required(owner.sockets.find(s=>s.id==='line_coil_support')).id='line_forged_support';}
    if(mode==='omitted-descriptor')Reflect.deleteProperty(feed,'support_lift_function_id');
    if(mode==='null')Reflect.set(feed,'support_lift_function_id',null);
    if(mode==='unknown')feed.support_lift_function_id='unknown-lift';
    if(mode==='wrong-owner')binding.policy_id='policy:equipment:electrocleaning';
    if(mode==='wrong-kind')lift.kind='rotation';
    if(mode==='wrong-axis')lift.axis=[0,-1,0];
    if(mode==='positive-max')lift.max_value=.01;
    if(mode==='missing-channel')raw.envelope.channels=raw.envelope.channels.filter(c=>c.function_id!=='line_feed_lift');
    if(mode==='wrong-driver')feed.driver_function_id='line_unwinding_mandrel';
    if(mode==='driver-interval')Reflect.set(feed,'driver_interval',[0,20]);
    expect(()=>evaluate(authorized(raw))).toThrow();
  });
  for(const mode of ['source','socket','root','orientation','version','off-surface','lowered','unwind-running','feed-running'] as const)it(`rejects clamp ${mode}`,()=>{
    const raw=fresh('clamp'),event=raw.envelope.boundary;if(event===null)throw new Error('Boundary required');
    if(mode==='source')raw.envelope.recipe_id='motion:source:ngo-05';
    if(mode==='socket')event.previous_anchor.socket_id='work';
    if(mode==='root')event.previous_material.support_local_mm[0]=(event.previous_material.support_local_mm[0] ?? 0)+.01;
    if(mode==='orientation')event.previous_material.orientation_xyzw=[0,0,0,1];
    if(mode==='version')event.previous_material.material_version_id='absent-version';
    if(mode==='off-surface')event.previous_material.support_local_mm[2]=100;
    if(mode==='lowered')required(event.previous_channels.find(c=>c.function_id==='line_feed_lift')).value=-.02;
    if(mode==='unwind-running')required(event.previous_channels.find(c=>c.function_id==='line_unwinding_mandrel')).value=.001;
    if(mode==='feed-running')required(event.previous_channels.find(c=>c.function_id==='strip_feed')).value=.001;
    expect(()=>evaluate(authorized(raw))).toThrow();
  });
  for(const mode of ['nonendpoint','cold-running-old','cold-running-new','wrong-part','wrong-socket','wrong-source','no-old-surface','off-machine','off-material','lift-lowered','separation'] as const)it(`rejects cold entry ${mode}`,()=>{
    const raw=fresh('cold'),e=raw.envelope,event=e.boundary,b=required(raw.context.asset_bindings[0]);if(event===null)throw new Error('Boundary required');
    if(mode==='nonendpoint')required(event.previous_channels.find(c=>c.function_id==='line_strip_feed')).value=5-1e-9;
    if(mode==='cold-running-old')required(event.previous_channels.find(c=>c.function_id==='cold_reduction_roll')).value=1e-9;
    if(mode==='cold-running-new'){const c=required(e.channels.find(c=>c.function_id==='cold_reduction_roll'));c.start_value=c.end_value=1e-9;}
    if(mode==='wrong-part')required(b.functions.find(f=>f.function_id==='cold_reduction_roll')).node_id='forged-barrel';
    if(mode==='wrong-socket')e.anchor.socket_id='work';
    if(mode==='wrong-source')e.recipe_id='motion:source:cr-04';
    if(mode==='no-old-surface')b.functions=b.functions.filter(f=>f.function_id!=='cold_reduction_roll');
    if(mode==='off-machine'){
      const f=required(b.functions.find(f=>f.function_id==='cold_reduction_roll'));f.pivot_m[1]=(f.pivot_m[1] ?? 0)-.001;
      for(const channels of [event.previous_channels,e.channels]){const c=required(channels.find(c=>c.function_id==='cold_reduction_roll'));c.pivot_m[1]=(c.pivot_m[1] ?? 0)-.001;}
    }
    if(mode==='off-material')event.previous_material.support_local_mm[2]=1;
    if(mode==='lift-lowered')required(event.previous_channels.find(c=>c.function_id==='line_feed_lift')).value=-1e-16;
    if(mode==='separation')e.material.support_local_mm[1]=(e.material.support_local_mm[1] ?? 0)-11;
    expect(()=>evaluate(authorized(raw))).toThrow();
  });
  it('keeps omitted lift bytes unchanged for legacy static feeds',()=>{
    const seed=required(legacy.cases[0]).request,request=parseMotionRequestValue(seed);
    expect(evaluateMotion(request.envelope,request.context,registry).material).toEqual(seed.envelope.material);
    const binding=required(request.context.asset_bindings[0]);expect('internal_feeds' in binding && binding.internal_feeds[0]).not.toHaveProperty('support_lift_function_id');
  });
});
