import { describe, expect, it } from 'vitest';
import seed from '../../../../shared/fixtures/bath-path-cases.json';
import sourceJson from '../../../../shared/finishing-bath-source05.json';
import { parseMotionRequestValue } from './request';
import { evaluateMotion } from './contracts';
import { recipes } from './testFixtures';
import { bindingsFromBathSource, createBathRuntime, evaluateBathMotion } from './bathPath';
import { bindingShape, materialSupportShape } from './shapes';

function first<T>(items: readonly T[]): T {
  const item=items[0];
  if(item===undefined) throw new RangeError('Fixture row required');
  return item;
}
function request(index=0, previous=false) {
  const entry=seed.cases[index];
  if(entry===undefined) throw new RangeError('Fixture row required');
  const raw=structuredClone(entry.request), material=structuredClone(raw.envelope.material), anchor=structuredClone(raw.envelope.anchor);
  if(previous) Reflect.set(raw.envelope,'boundary',{released_attachment_id:'previous',acquired_attachment_id:raw.envelope.attachment_id,at_ms:1000,previous_material:material,previous_anchor:anchor,previous_channels:[]});
  return {raw,material:previous?material:raw.envelope.material,anchor:previous?anchor:raw.envelope.anchor};
}
function evaluate(raw: ReturnType<typeof request>['raw'] | typeof seed.legacy_request) {
  raw.context.authorizations=[structuredClone(raw.envelope)];
  const parsed=parseMotionRequestValue(raw);
  return evaluateMotion(parsed.envelope,parsed.context,recipes);
}

describe('source05 contract-only barrier',()=>{
  for(let index=0;index<3;index++) it(`valid typed source ${index} parses but never admits a pose`,()=>{
    const {raw}=request(index),parsed=parseMotionRequestValue(raw);
    expect(parsed.envelope.material).toHaveProperty('bath_path');
    expect(first(parsed.context.asset_bindings)).toHaveProperty('bath_paths');
    expect(parseMotionRequestValue(JSON.parse(JSON.stringify(parsed)))).toEqual(parsed);
    expect(()=>evaluateMotion(parsed.envelope,parsed.context,recipes)).toThrow('bath_unqualified:');
  });
  for(const previous of [false,true]) for(const fault of ['null','empty','missing-profile','unknown','boolean-version','wrong-version','feed-mix','rigid-mix'] as const) it(`strict ${previous?'previous':'current'} material ${fault}`,()=>{
    const {raw,material}=request(0,previous);
    switch(fault){
      case 'null': Reflect.set(material,'bath_path',null);break;
      case 'empty': Reflect.set(material,'bath_path',{});break;
      case 'missing-profile': Reflect.deleteProperty(material.bath_path,'profile_id');break;
      case 'unknown': Reflect.set(material.bath_path,'verified',true);break;
      case 'boolean-version': Reflect.set(material.bath_path,'schema_version',true);break;
      case 'wrong-version': material.bath_path.schema_version=2;break;
      case 'feed-mix': Reflect.set(material,'internal_feed',{schema_version:1,feed_id:'feed'});break;
      case 'rigid-mix': Reflect.set(material,'rigid_handling',{schema_version:1,profile_id:'rigid'});break;
    }
    expect(()=>evaluate(raw)).toThrow('invalid_contract:');
  });
  for(const fault of ['null','empty','duplicate','boolean-version','unknown','missing','bad-digest','missing-lod','boolean-number','feed-mix','contacts-mix','handoffs-mix'] as const) it(`strict binding ${fault}`,()=>{
    const {raw}=request(),binding=first(raw.context.asset_bindings),d=first(binding.bath_paths);
    switch(fault){
      case 'null': Reflect.set(binding,'bath_paths',null);break;
      case 'empty': binding.bath_paths=[];break;
      case 'duplicate': binding.bath_paths.push(structuredClone(d));break;
      case 'boolean-version': Reflect.set(d,'schema_version',true);break;
      case 'unknown': Reflect.set(d,'approved',true);break;
      case 'missing': Reflect.deleteProperty(d,'outlet_roller_ids');break;
      case 'bad-digest': d.source_manifest_sha256='A'.repeat(64);break;
      case 'missing-lod': d.glb_sha256_by_lod.pop();break;
      case 'boolean-number': Reflect.set(d,'width_m',true);break;
      case 'feed-mix': Reflect.set(binding,'internal_feeds',seed.internal_feed_template);break;
      case 'contacts-mix': Reflect.set(binding,'handling_contacts',[]);break;
      case 'handoffs-mix': Reflect.set(binding,'handling_handoffs',[]);break;
    }
    expect(()=>evaluate(raw)).toThrow('invalid_contract:');
  });
  for(const field of ['id','custody_socket_id','driver_function_id','source_asset_id','source_manifest_sha256','source_recipe_sha256','glb_sha256_by_lod','stock_length_m','width_m','thickness_m','required_state_functions','outlet_roller_ids'] as const) it(`source-bound ${field}`,()=>{
    const {raw}=request(),d=first(first(raw.context.asset_bindings).bath_paths),value=d[field];
    Reflect.set(d,field,typeof value==='number'?value+1:Array.isArray(value)?value.length>1?[...value].reverse():['wrong-state']:field.endsWith('sha256')?'0'.repeat(64):'wrong-source');
    expect(()=>evaluate(raw)).toThrow('binding:');
  });
  for(let current=0;current<3;current++) for(let other=0;other<3;other++) if(current!==other) it(`profile ${other} cannot be used by owner ${current}`,()=>{
    const {raw}=request(current),alternative=seed.cases[other];
    if(alternative===undefined) throw new RangeError('Profile required');
    raw.envelope.material.bath_path.profile_id=alternative.request.envelope.material.bath_path.profile_id;
    expect(()=>evaluate(raw)).toThrow('binding:');
  });
  for(const previous of [false,true]) for(const fault of ['profile','orientation','offset','width','thickness','diameter','anchor'] as const) it(`source frame ${previous} ${fault}`,()=>{
    const {raw,material,anchor}=request(0,previous);
    switch(fault){
      case 'profile': material.bath_path.profile_id='unknown-profile';break;
      case 'orientation': material.orientation_xyzw=[0,0,1,0];break;
      case 'offset': material.support_local_mm[0]=1;break;
      case 'width': material.dimensions.width_mm=1199;break;
      case 'thickness': material.dimensions.thickness_mm=6;break;
      case 'diameter': Reflect.set(material.dimensions,'diameter_mm',1);break;
      case 'anchor': anchor.position_m[1]=(anchor.position_m[1]??0)+1;break;
    }
    expect(()=>evaluate(raw)).toThrow('binding:');
  });
  for(const mode of ['same','shifted','fleet-only','unrelated'] as const) it(`bath alias ${mode}`,()=>{
    const {raw}=request(),identity=mode==='unrelated'?'unrelated-truck':raw.envelope.anchor.owner_id;
    const fleet={...seed.fleet_template,id:identity},vehicle={...seed.vehicle_template,fleet_id:identity,position_m:first(raw.context.world.owners).pose.position,yaw_rad:0};
    if(mode==='shifted')vehicle.position_m=[0,0,0];
    Reflect.set(raw.context.snapshot,'fleet',[fleet]);
    if(mode!=='fleet-only')Reflect.set(raw.context.snapshot,'vehicle_states',[vehicle]);
    if(mode==='unrelated')expect(()=>evaluate(raw)).toThrow('bath_unqualified:');
    else expect(()=>evaluate(raw)).toThrow('binding:');
  });
  for(const strip of ['material','binding'] as const) it(`stripped ${strip} never restores point fallback`,()=>{
    const {raw}=request();
    if(strip==='material')Reflect.deleteProperty(raw.envelope.material,'bath_path');
    else Reflect.deleteProperty(first(raw.context.asset_bindings),'bath_paths');
    expect(()=>evaluate(raw)).toThrow(/(?:binding|bath_unqualified):/);
  });
  it('previous-only bath and an unrelated bath binding reach the request-wide barrier',()=>{
    const {raw}=request(0,true);
    Reflect.deleteProperty(raw.envelope.material,'bath_path');
    expect(()=>evaluate(raw)).toThrow('bath_unqualified:');
    const legacy=structuredClone(seed.legacy_request),source=request(1).raw;
    legacy.context.world.owners.push(...source.context.world.owners);
    legacy.context.world.footprints.push(...source.context.world.footprints);
    Reflect.set(legacy.context,'asset_bindings',[...legacy.context.asset_bindings,...source.context.asset_bindings]);
    expect(()=>evaluate(legacy)).toThrow('bath_unqualified:');
  });
  it('preserves legacy absence and dimensional defaults',()=>{
    const raw=structuredClone(seed.legacy_request),expected=evaluate(raw);
    Reflect.deleteProperty(raw.envelope.material.dimensions,'diameter_mm');
    Reflect.deleteProperty(raw.envelope.material.dimensions,'inner_diameter_mm');
    expect(evaluate(raw).position_m).toEqual(expected.position_m);
    expect(expected.material).not.toHaveProperty('bath_path');
    const bath=request().raw;
    expect(materialSupportShape.parse(bath.envelope.material)).toHaveProperty('bath_path');
    expect(bindingShape.parse(first(bath.context.asset_bindings))).toHaveProperty('bath_paths');
  });
  it('rejects missing source bytes and a forged dedicated runtime',async()=>{
    const world=parseMotionRequestValue(request().raw).context.world;
    await expect(createBathRuntime(new Map(),world)).rejects.toThrow('binding:');
    expect(()=>Reflect.apply(evaluateBathMotion,null,[{},null,null])).toThrow('bath_unqualified:');
  });
  it('does not expose a mutable source-table row through semantic validation',()=>{
    // A caller changing its JSON import cannot rewrite the module snapshot.
    const original=sourceJson.profiles[0]?.descriptor.width_m;
    const row=first(sourceJson.profiles);
    row.descriptor.width_m=9;
    expect(()=>evaluate(request().raw)).toThrow('bath_unqualified:');
    if(original!==undefined)row.descriptor.width_m=original;
  });
  it('revalidates a typed context mutation before the generic projection',()=>{
    const parsed=parseMotionRequestValue(request().raw),binding=first(parsed.context.asset_bindings);
    const bad={...binding,policy_id:'wrong-policy'};
    expect(()=>evaluateMotion(parsed.envelope,{...parsed.context,asset_bindings:[bad]},recipes)).toThrow('binding:');
    const raw=request().raw;
    Reflect.set(raw.context.snapshot,'fleet',[{...seed.fleet_template,id:'unrelated-truck'}]);
    Reflect.set(raw.context.snapshot,'vehicle_states',[{...seed.vehicle_template,fleet_id:'unrelated-truck'}]);
    const admitted=parseMotionRequestValue(raw),owner=admitted.envelope.anchor.owner_id;
    const snapshot={...admitted.context.snapshot,fleet:admitted.context.snapshot.fleet.map(f=>({...f,id:owner})),vehicle_states:admitted.context.snapshot.vehicle_states.map(v=>({...v,fleet_id:owner}))};
    expect(()=>evaluateMotion(admitted.envelope,{...admitted.context,snapshot},recipes)).toThrow('binding:');
  });

});


describe('source byte ownership boundary', () => {
  it('rejects shared backing before hashing any earlier artifact', async () => {
    const artifact = sourceJson.artifacts.at(-1);
    if (artifact === undefined) throw new RangeError('Source artifact required');
    const bytes = new Map<string, Uint8Array>(sourceJson.artifacts.map(row => [row.path, new Uint8Array([1])]));
    bytes.set(artifact.path, new Uint8Array(new SharedArrayBuffer(1)));
    const world = parseMotionRequestValue(request().raw).context.world;
    await expect(bindingsFromBathSource(bytes, world)).rejects.toMatchObject({code:'binding', reference:artifact.path});
  });
  it('retains the initial closed-key error if the caller restores the missing key', async () => {
    const artifact = first(sourceJson.artifacts);
    const bytes = new Map(sourceJson.artifacts.slice(1).map(row => [row.path, new Uint8Array([1])]));
    const world = parseMotionRequestValue(request().raw).context.world;
    const pending = bindingsFromBathSource(bytes, world);
    bytes.set(artifact.path, new Uint8Array([1]));
    await expect(pending).rejects.toMatchObject({code:'binding', reference:sourceJson.algorithm_id});
  });
});

for (const api of [bindingsFromBathSource, createBathRuntime]) describe(`${api.name} backing store boundary`, () => {
  for (const kind of ['foreign-shared-local-view', 'foreign-shared-view', 'detached'] as const) it(`rejects ${kind} with the exact source path`, async () => {
    // Given a real backing store unsupported at the byte boundary.
    const {runInNewContext} = await import('node:vm');
    const artifact = sourceJson.artifacts.at(-1);
    if (artifact === undefined) throw new RangeError('Source artifact required');
    const data = new Map<string, Uint8Array>(sourceJson.artifacts.map(row => [row.path, new Uint8Array([1])]));
    const backing = kind === 'detached' ? new ArrayBuffer(1) : runInNewContext('new SharedArrayBuffer(1)');
    const view: Uint8Array = kind === 'foreign-shared-view' ? runInNewContext('new Uint8Array(backing)', {backing}) : new Uint8Array(backing);
    data.set(artifact.path, view);
    if (kind === 'detached') structuredClone(backing, {transfer:[backing]});
    const world = parseMotionRequestValue(request().raw).context.world;
    // When either public byte wrapper begins synchronous ownership.
    const pending = api(data, world);
    // Then the unsupported view fails before hashing an earlier dummy artifact.
    await expect(pending).rejects.toMatchObject({code:'binding', reference:artifact.path});
  });
  for (const foreign of [false, true]) it(`accepts ordinary ${foreign ? 'foreign' : 'local'} backing through snapshot`, async () => {
    // Given an ordinary view; the first artifact remains deliberately invalid.
    const {runInNewContext} = await import('node:vm');
    const artifact = sourceJson.artifacts.at(-1);
    if (artifact === undefined) throw new RangeError('Source artifact required');
    const backing: ArrayBuffer = foreign ? runInNewContext('new ArrayBuffer(3)') : new ArrayBuffer(3);
    const data = new Map<string, Uint8Array>(sourceJson.artifacts.map(row => [row.path, new Uint8Array([1])]));
    data.set(artifact.path, new Uint8Array(backing, 1, 1));
    const world = parseMotionRequestValue(request().raw).context.world;
    // When the wrapper qualifies and copies the ordinary slice.
    const pending = api(data, world);
    // Then the subsequent hash check identifies the first dummy artifact.
    await expect(pending).rejects.toMatchObject({code:'binding', reference:first(sourceJson.artifacts).path});
  });
});


for (const api of [bindingsFromBathSource, createBathRuntime]) describe(`${api.name} actual backing boundary`, () => {
  for (const foreign of [false, true]) it(`rejects shared backing masked by ordinary buffer ${foreign}`, async () => {
    // Given a standard view whose own data property hides its real shared store.
    const {runInNewContext} = await import('node:vm');
    const artifact = sourceJson.artifacts.at(-1);
    if (artifact === undefined) throw new RangeError('Source artifact required');
    const backing = foreign ? runInNewContext('new SharedArrayBuffer(9)') : new SharedArrayBuffer(9);
    const view = new Uint8Array(backing, 4, 1);
    Object.defineProperty(view, 'buffer', {value:new ArrayBuffer(1)});
    const data = new Map<string, Uint8Array>(sourceJson.artifacts.map(row => [row.path, new Uint8Array([1])]));
    data.set(artifact.path, view);
    const world = parseMotionRequestValue(request().raw).context.world;
    // When either public API snapshots the view.
    const pending = api(data, world);
    // Then its actual backing fails before earlier dummy hashes.
    await expect(pending).rejects.toMatchObject({code:'binding', reference:artifact.path});
  });
  it('ignores own backing and extent getters for ordinary view ownership', async () => {
    // Given a supported ordinary view with untrusted properties shadowing its slots.
    const artifact = sourceJson.artifacts.at(-1);
    if (artifact === undefined) throw new RangeError('Source artifact required');
    const view = new Uint8Array(new ArrayBuffer(9), 4, 1);
    const events: string[] = [];
    for (const name of ['buffer', 'byteOffset', 'byteLength', 'length']) Object.defineProperty(view, name, {get(){events.push(name); throw new TypeError('caller property');}});
    const data = new Map<string, Uint8Array>(sourceJson.artifacts.map(row => [row.path, new Uint8Array([1])]));
    data.set(artifact.path, view);
    const world = parseMotionRequestValue(request().raw).context.world;
    // When intrinsic slots are used by either public API.
    const pending = api(data, world);
    // Then ownership succeeds, the earlier dummy hash fails, and no getter runs.
    await expect(pending).rejects.toMatchObject({code:'binding', reference:first(sourceJson.artifacts).path});
    expect(events).toEqual([]);
  });
});
