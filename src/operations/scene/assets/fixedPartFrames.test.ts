import { readFileSync, mkdirSync, mkdtempSync, rmSync, writeFileSync } from 'node:fs';
import { join, resolve } from 'node:path';
import { tmpdir } from 'node:os';
import { spawnSync } from 'node:child_process';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { Matrix4 } from 'three';
import { z } from 'zod';
import { AssetRegistry } from './registry';
import { inspectGlb, loadAsset } from './loader';
import { AssetManifestError, parseProductionAssetManifest } from './manifest';
import type { Asset } from './manifest';
import { phaseSample, frameAt } from '../../../../tests/fixtures/steelmaking/poses';
import { mutateFixed } from '../../../../tests/fixtures/steelmaking/fixedMutants';

const sourceRoot=resolve(process.env.STEELFLOW_FIXED_PART_ASSET_ROOT??'.'),record=z.record(z.string(),z.unknown());
const rows=(value:unknown)=>z.array(record).parse(value);
const needed=<T>(value:T|undefined):T=>{if(value===undefined)throw new RangeError('Actual fixed-part fixture missing');return value;};
function actual(){
  const fragments=['steelmaking','stainless'].map(f=>parseProductionAssetManifest(readFileSync(resolve(sourceRoot,`public/assets/steelworks/${f}/manifest.json`),'utf8')));
  return parseProductionAssetManifest(JSON.stringify({schema_version:1,purpose:'production',assets:fragments.flatMap(f=>f.assets)}));
}
const single=(asset:unknown)=>needed(parseProductionAssetManifest(JSON.stringify({schema_version:1,purpose:'production',assets:[asset]})).assets[0]);
const bytes=(asset:Asset,level:number)=>new Uint8Array(readFileSync(resolve(sourceRoot,needed(asset.lods.find(l=>l.level===level)).artifact.path))).buffer;
afterEach(()=>{vi.unstubAllGlobals();vi.restoreAllMocks();});

function offline(asset:Asset,input:ArrayBuffer,label:string){
  const temporary=mkdtempSync(join(tmpdir(),'steelflow-fixed-part-'));
  try{
    const path=join(temporary,'input.glb'),descriptor=join(temporary,'input.json');writeFileSync(path,new Uint8Array(input));writeFileSync(descriptor,JSON.stringify({asset,bytesPath:path}));
    const result=spawnSync(process.execPath,['tests/fixtures/steelmaking/check-fixed.mjs',descriptor],{encoding:'utf8'}),evidence=process.env.ASSET_LOADER_EVIDENCE_ROOT;
    if(evidence){const output=resolve(evidence,'fixed-parts');mkdirSync(output,{recursive:true});writeFileSync(join(output,label+'.glb'),new Uint8Array(input));writeFileSync(join(output,label+'.json'),JSON.stringify({asset,exit:result.status,stdout:result.stdout,stderr:result.stderr},null,2));}
    return result;
  }finally{rmSync(temporary,{recursive:true,force:true});}
}

describe('actual LF null support and explicitly vessel-relative AOD tuyere',()=>{
  it.each(['LF-A','STS-HR-03','STS-PLATE-03'])('%s preserves all three LODs and actual fixed geometry',async key=>{
    vi.stubGlobal('self',globalThis);const manifest=actual(),asset=needed(manifest.assets.find(a=>a.variant.endsWith(':'+key)));
    for(const level of [0,1,2]){
      const lod=needed(asset.lods.find(l=>l.level===level)),input=bytes(asset,level);await expect(inspectGlb(input,asset,lod)).resolves.toBeDefined();
      const loaded=await loadAsset(asset,lod,{origin:'http://127.0.0.1:4176',read:async()=>input});expect(loaded.nodes.has(needed(asset.fixed_parts[0]).node_id)).toBe(true);loaded.dispose();
      const proof=offline(asset,input,`${key}-lod${level}-valid`);expect(proof.status,proof.stderr).toBe(0);
      const reports=z.array(record).parse(JSON.parse(proof.stdout));expect(reports).toHaveLength(1);
      if(key==='LF-A'){expect(reports[0]?.state_id).toBeNull();expect(reports[0]?.state_bound).toBe(false);expect(reports[0]?.physical_motion).toBe(false);}
      else{expect(reports[0]?.local_physical_motion).toBe(false);expect(reports[0]?.inherited_from_part_id).toBe('vessel_tilt');expect(reports[0]?.state_bound).toBe(true);}
    }
  });
  it.each(['STS-HR-03','STS-PLATE-03'])('%s inherits only vessel tilt while state, local frame, pause and LOD remain exact',async key=>{
    vi.stubGlobal('self',globalThis);const manifest=actual(),asset=needed(manifest.assets.find(a=>a.variant.endsWith(':'+key))),sample=phaseSample(manifest,asset,frameAt(0,'paused'));
    const store=new AssetRegistry(JSON.stringify(manifest),{origin:'http://127.0.0.1:4176',read:async url=>new Uint8Array(readFileSync(resolve(sourceRoot,'public'+new URL(url).pathname))).buffer});
    store.beginRun(sample.pose.run_id,sample.envelope.bundle_hash);const entity=store.entity({run_id:sample.pose.run_id,entity_type:'equipment',entity_id:sample.pose.owner_id,bundle_hash:sample.envelope.bundle_hash},asset.id);
    try{
      let local:readonly number[]|undefined;
      for(const level of [0,1,2]){
        await entity.show(level);
        for(const index of [0,32,56,64]){
          const current=phaseSample(manifest,asset,frameAt(index,'running'));entity.applyPose(current.pose);entity.root.updateMatrixWorld(true);
          const fixed=needed(entity.nodes.get('gas_tuyere')),vessel=needed(entity.nodes.get('vessel_tilt'));local??=fixed.matrix.toArray();expect(fixed.matrix.toArray()).toEqual(local);
          const expected=new Matrix4().multiplyMatrices(vessel.matrixWorld,fixed.matrix);expect(fixed.matrixWorld.toArray()).toEqual(expected.toArray());
          expect(fixed.userData.operationalState).toBe(needed(current.pose.channels.find(c=>c.function_id==='gas_tuyere')).value);
          const matrix=fixed.matrixWorld.toArray(),operationalState=fixed.userData.operationalState;for(const clock of ['paused','blocked'] as const){entity.applyPose(phaseSample(manifest,asset,frameAt(index,clock)).pose);entity.root.updateMatrixWorld(true);expect(fixed.matrixWorld.toArray()).toEqual(matrix);expect(fixed.userData.operationalState).toBe(operationalState);}
        }
      }
      expect(phaseSample(manifest,asset,frameAt(32,'running')).pose.channels.map(c=>c.function_id)).toEqual(['vessel_tilt','gas_tuyere']);
    }finally{store.dispose();}
  });
});

const metadataCases=['null-state','missing-binding','unknown-field','null-parent','unknown-parent','self-parent','fixed-parent','follower-parent','procedural-parent','translation-parent','indirect-parent','moving-grandparent','node-alias','moving-descendant','socket-descendant','lod-reparent'] as const;
describe('bounded metadata rejection',()=>{
  it.each(metadataCases)('rejects %s without weakening legacy or canonical admission',mode=>{
    const original=needed(actual().assets.find(a=>a.variant==='variant:aod:STS-HR-03')),asset=record.parse(JSON.parse(JSON.stringify(original))),fixed=rows(asset.fixed_parts),part=needed(fixed[0]),moving=rows(asset.moving_parts),parent=needed(moving[0]),nodes=rows(asset.nodes),node=needed(nodes.find(n=>n.id==='gas_tuyere'));
    switch(mode){
      case 'null-state':part.binding=null;break;
      case 'missing-binding':Reflect.deleteProperty(part,'binding');break;
      case 'unknown-field':part.fixed_to_arbitrary_frame='vessel_tilt';break;
      case 'null-parent':part.fixed_to_part_id=null;break;
      case 'unknown-parent':part.fixed_to_part_id='unregistered';break;
      case 'self-parent':part.fixed_to_part_id='gas_tuyere';break;
      case 'fixed-parent':part.fixed_to_part_id='gas_injector_0';break;
      case 'follower-parent':parent.binding={type:'mechanical_follower',driver_part_id:'vessel_tilt',ratio:1};break;
      case 'procedural-parent':parent.binding={type:'procedural',clock:'server_sim',phase:'work',progress_source:'server_phase_progress',pause:'hold',fault:'hold',rest:'range_rest',procedure_id:'unsupported'};break;
      case 'translation-parent':parent.motion='translation';parent.range={min:0,max:1,rest:0,unit:'m'};break;
      case 'indirect-parent':nodes.push({id:'tuyere_mount',parent_id:'vessel_tilt',locator:'root/vessel_tilt/tuyere_mount',transform:{position_m:[0,0,0],rotation_xyzw:[0,0,0,1]}});node.parent_id='tuyere_mount';break;
      case 'moving-grandparent':moving.push({...parent,id:'extra_mount',node_id:'root',function:'extra_mount'});break;
      case 'node-alias':fixed.push({...part,id:'gas_alias',binding:null,fixed_to_part_id:undefined});break;
      case 'moving-descendant':moving.push({...parent,id:'gas_injector_0',node_id:'gas_injector_0',function:'hidden_motion'});break;
      case 'socket-descendant':{const sockets=rows(asset.sockets);needed(sockets[0]).node_id='gas_injector_0';asset.sockets=sockets;break;}
      case 'lod-reparent':{const lod=needed(rows(asset.lods)[1]),lodNodes=rows(lod.nodes);needed(lodNodes.find(n=>n.id==='gas_tuyere')).parent_id='root';lod.nodes=lodNodes;asset.lods=rows(asset.lods).map((l,i)=>i===1?lod:l);break;}
    }
    asset.fixed_parts=fixed;asset.moving_parts=moving;asset.nodes=nodes;
    let failure:AssetManifestError|undefined;try{single(asset);}catch(error){if(!(error instanceof AssetManifestError))throw error;failure=error;}
    expect(failure).toBeDefined();const rejection=needed(failure);expect(['schema','requirements','reference','identity','lod']).toContain(rejection.code);
    const evidence=process.env.ASSET_LOADER_EVIDENCE_ROOT;if(evidence){const output=resolve(evidence,'fixed-parts');mkdirSync(output,{recursive:true});writeFileSync(join(output,`metadata-${mode}.json`),JSON.stringify({input:asset,error:{code:rejection.code,reference:rejection.reference}},null,2));}
  });
  it('rejects the field on LF and preserves required nullable binding',()=>{
    const asset=needed(actual().assets.find(a=>a.kind==='ladle_furnace'));expect(single(asset).fixed_parts[0]?.binding).toBeNull();
    expect(()=>single({...asset,fixed_parts:asset.fixed_parts.map(p=>({...p,fixed_to_part_id:'electrode_lift'}))})).toThrow('unreviewed-fixed-frame');
  });
});

describe('actual GLB fixed subtree failures',()=>{
  it.each(['no-mesh','own-track','child-track','translation-track','scale-track','reparent'] as const)('rejects %s in all three actual AOD LODs before accepting geometry',async mode=>{
    vi.stubGlobal('self',globalThis);const original=needed(actual().assets.find(a=>a.variant==='variant:aod:STS-HR-03'));
    for(const level of [0,1,2]){
      const changed=mutateFixed(original,level,mode,sourceRoot),asset=single(changed.asset),lod=needed(asset.lods.find(l=>l.level===level));
      await expect(loadAsset(asset,lod,{origin:'http://127.0.0.1:4176',read:async()=>changed.bytes})).rejects.toMatchObject({code:'binding'});
      const result=offline(asset,changed.bytes,`aod-${mode}-lod${level}`);expect(result.status,result.stdout).toBe(1);
    }
  });
  it('rejects empty actual LF support geometry in every LOD while preserving nullable state',async()=>{
    vi.stubGlobal('self',globalThis);const original=needed(actual().assets.find(a=>a.kind==='ladle_furnace'));
    for(const level of [0,1,2]){const changed=mutateFixed(original,level,'no-mesh',sourceRoot),asset=single(changed.asset),lod=needed(asset.lods.find(l=>l.level===level));await expect(loadAsset(asset,lod,{origin:'http://127.0.0.1:4176',read:async()=>changed.bytes})).rejects.toMatchObject({code:'binding'});expect(offline(asset,changed.bytes,`lf-no-mesh-lod${level}`).status).toBe(1);}
  });
  it.each(['missing','unknown','malformed-state'] as const)('rejects LF %s binding input without manufacturing a state',mode=>{
    const original=needed(actual().assets.find(a=>a.kind==='ladle_furnace')),asset=record.parse(JSON.parse(JSON.stringify(original))),parts=rows(asset.fixed_parts),part=needed(parts[0]);
    switch(mode){case 'missing':Reflect.deleteProperty(part,'binding');break;case 'unknown':part.unregistered='value';break;case 'malformed-state':part.binding={type:'operational_state',clock:'wall',phase:'work',progress_source:'server_phase_progress',pause:'hold',fault:'hold',rest:'inactive',state_id:'invalid'};break;}
    asset.fixed_parts=parts;let rejection:AssetManifestError|undefined;try{single(asset);}catch(error){if(!(error instanceof AssetManifestError))throw error;rejection=error;}expect(rejection).toBeDefined();const failure=needed(rejection);
    const evidence=process.env.ASSET_LOADER_EVIDENCE_ROOT;if(evidence){const output=resolve(evidence,'fixed-parts');mkdirSync(output,{recursive:true});writeFileSync(join(output,`lf-metadata-${mode}.json`),JSON.stringify({input:asset,error:{code:failure.code,reference:failure.reference}},null,2));}
  });
  it('requires the explicit parent field and rejects actual parent motion without it',async()=>{
    const original=needed(actual().assets.find(a=>a.variant==='variant:aod:STS-HR-03')),asset=single({...original,fixed_parts:original.fixed_parts.map(({fixed_to_part_id:_parent,...part})=>part)});
    for(const level of [0,1,2]){const input=bytes(asset,level),lod=needed(asset.lods.find(l=>l.level===level));await expect(inspectGlb(input,asset,lod)).rejects.toMatchObject({code:'binding'});expect(offline(asset,input,`aod-undeclared-parent-lod${level}`).status).toBe(1);}
  });
});
