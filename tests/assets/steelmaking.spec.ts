import { expect } from '@playwright/test';
import { createHash } from 'node:crypto';
import { readFile, readdir, mkdir } from 'node:fs/promises';
import { readFileSync } from 'node:fs';
import { execFileSync } from 'node:child_process';
import { join, resolve } from 'node:path';
import { z } from 'zod';
import { productionParser } from '../fixtures/steelmaking/parser.mjs';
import { test, readWorld, recordJson, resetScenario } from '../helpers/operations';
import { artifact, compareScreenshotPixels, readBoundSample, startFactoryObservation, validateFactoryReceipt, verifyReceiptArtifacts } from '../helpers/factory';
import type { FactoryReceipt } from '../helpers/factory';
import { corruptAsset } from '../fixtures/steelmaking/corrupt';
import { assertMechanics, button, contract, state } from '../fixtures/steelmaking/proof';

const requirements=z.object({existing_bindings:z.array(z.object({variant:z.string()}).passthrough())}).parse(JSON.parse(readFileSync('shared/asset-requirements.json','utf8')));
const contracts=z.object({models:z.array(z.object({key:z.string(),variant:z.string()}).passthrough())}).parse(JSON.parse(readFileSync('tests/fixtures/steelmaking/contracts.json','utf8')));
const sourceRoot=resolve(process.env.STEELFLOW_QA_STEELMAKING_ROOT??'.'),entry='/tests/fixtures/steelmaking/index.html';
const hash=(value:Uint8Array|string)=>createHash('sha256').update(value).digest('hex');
async function currentSources(){
  const raws=await Promise.all(['steelmaking','stainless'].map(f=>readFile(resolve(sourceRoot,`public/assets/steelworks/${f}/manifest.json`),'utf8')));
  const parse=await productionParser();
  return {raws,assets:raws.flatMap(raw=>parse(raw).assets),manifestSha256:hash(raws.join('\n')),familyHashes:raws.map(hash),policySha256:hash(await readFile('shared/asset-requirements.json')),recipesSha256:hash(await readFile('shared/motion-recipes.json'))};
}
test.use({trace:'off'});

for(const specification of contracts.models){
  const binding=requirements.existing_bindings.find(b=>b.variant===specification.variant);
  if(!binding)throw new RangeError('Registered T19 binding missing');
  test(`full-cycle ${specification.key} actual miniature, 65 admitted samples, three views and close-up`,async({browser,baseURL},testInfo)=>{
    test.setTimeout(240_000);if(!baseURL)throw new RangeError('Owned steelmaking fixture URL required');
    const recording=await startFactoryObservation(browser,baseURL,testInfo),page=recording.page;
    try{
      const sources=await currentSources(),asset=sources.assets.find(a=>a.variant===specification.variant);if(!asset)throw new RangeError('Actual T19 asset missing');
      expect(contracts.models).toHaveLength(14);expect(sources.assets).toHaveLength(14);expect(new Set(sources.assets.map(a=>a.kind)).size).toBe(8);
      expect(sources.assets.filter(a=>a.family==='steelmaking')).toHaveLength(10);expect(sources.assets.filter(a=>a.family==='stainless')).toHaveLength(4);
      await page.goto(`${entry}?asset=${encodeURIComponent(asset.id)}&qa-attempt=${recording.identity.attempt_id}&steelflow-qa=1`);
      await expect(page.getByTestId('load-status')).toHaveText('실제 모델 표시');await expect(page.locator('canvas')).toHaveAttribute('data-asset-state',/^\{/);await expect(page.locator('canvas')).toHaveAttribute('data-qa-bound-state',/^\{/);await expect.poll(async()=>(await state(page)).variant).toBe(asset.variant);
      const step0Path=testInfo.outputPath('step-0.png');await page.screenshot({path:step0Path,fullPage:true});
      const step0={sequence:0 as const,atMs:Date.now(),screenshot:await artifact(step0Path)},firstActionAtMs=Date.now();
      const backend=await resetScenario(page.request),backendPath=await recordJson(testInfo,'backend-payload',backend),initial=await state(page),initialSample=await readBoundSample(page),initialContract=await contract(page);
      expect(initial.triangles).toBeGreaterThan(4000);assertMechanics(asset,initial);
      for(const key of ['manifestSha256','policySha256','recipesSha256'] as const)expect(initialContract[key]).toBe(sources[key]);expect(initialContract.familyHashes).toEqual(sources.familyHashes);
      expect(initialSample.authority.authoritativeElapsedMs).toBe(0);
      const projectionPath=await recordJson(testInfo,'t58-contract-payload',initialContract),actualPath=testInfo.outputPath('actual.png'),emptyPath=testInfo.outputPath('empty.png');
      const actual=await page.locator('canvas').screenshot({path:actualPath});await button(page,'기하 숨김 · 메타데이터 유지').click();const empty=await page.locator('canvas').screenshot({path:emptyPath});
      const pixels=await compareScreenshotPixels(page,actual,empty);expect(pixels.changedPixels).toBeGreaterThan(pixels.minimumPixels);await button(page,'기하 숨김 · 메타데이터 유지').click();
      const samples=[],payloads=[],boundSamples=[];await button(page,'진행 상태').click();
      for(let index=0;index<=64;index++){
        if(index>0)await button(page,'다음 승인 샘플').click();await expect.poll(async()=>(await state(page)).frame.index).toBe(index);
        const current=await state(page),payload=await contract(page),bound=await readBoundSample(page);samples.push(current);payloads.push(payload);boundSamples.push(bound);
        expect(bound.authority.authoritativeElapsedMs).toBe(index*125);
        if(asset.kind==='aod'){const manifold=bound.nodes.find(n=>n.id==='argon_manifold'),initialManifold=initialSample.nodes.find(n=>n.id==='argon_manifold');expect(manifold?.matrixWorld).toEqual(initialManifold?.matrixWorld);}
        if((asset.kind==='aod'&&[56,64].includes(index))||(asset.kind==='eaf'&&[16,20,28,40,52,56,60,64].includes(index))){await button(page,'근접').click();await page.screenshot({path:testInfo.outputPath(`mechanism-${index}-close.png`),fullPage:true});await recordJson(testInfo,`mechanism-${index}-close-nodes`,{state:current,bound,payload});await button(page,'정면').click();}
        expect(current.key).toBe(initial.key);expect(current.rootUuid).toBe(initial.rootUuid);assertMechanics(asset,current);
        expect(payload.authority.authoritativeElapsedMs).toBe(index*125);
        expect(payload.snapshot.attachments.filter(a=>a.material_id===payload.envelope.material.material_id&&a.released_at_ms===null)).toHaveLength(1);
        if((asset.kind==='eaf'&&index===40)||(asset.kind==='ladle_furnace'&&index===32)){await button(page,'지붕 절개').click();await page.screenshot({path:testInfo.outputPath(`work-${index}-cutaway.png`),fullPage:true});expect((await state(page)).parts).toEqual(current.parts);expect((await state(page)).materialNodes).toEqual(current.materialNodes);await button(page,'지붕 절개').click();}
        if(index===0||index===32)for(const [angle,label]of [['front','정면'],['side','측면'],['rear','후면'],['close','근접']]){
          if(!label||!angle)throw new RangeError('Required camera view missing');await button(page,label).click();await page.screenshot({path:testInfo.outputPath(`${index===0?'idle':'running'}-${angle}.png`),fullPage:true});await recordJson(testInfo,`${index===0?'idle':'running'}-${angle}-nodes`,await state(page));
        }
        if(index===32){
          const running=await state(page);await button(page,'차단 상태').click();await expect.poll(async()=>(await state(page)).frame.clock).toBe('blocked');const blocked=await state(page);
          expect(blocked.parts).toEqual(running.parts);expect(blocked.fixed).toEqual(running.fixed);expect(blocked.materialNodes).toEqual(running.materialNodes);
          for(const [angle,label]of [['front','정면'],['side','측면'],['rear','후면'],['close','근접']]){if(!label||!angle)throw new RangeError('Blocked camera view missing');await button(page,label).click();await page.screenshot({path:testInfo.outputPath(`blocked-${angle}.png`),fullPage:true});await recordJson(testInfo,`blocked-${angle}-nodes`,await state(page));}
          await button(page,'일시 정지').click();await expect.poll(async()=>(await state(page)).frame.clock).toBe('paused');const paused=await state(page);expect(paused.parts).toEqual(blocked.parts);expect(paused.materialNodes).toEqual(blocked.materialNodes);
          await button(page,'진행 상태').click();await expect.poll(async()=>(await state(page)).frame.clock).toBe('running');const resumed=await state(page);expect(resumed.parts).toEqual(paused.parts);expect(resumed.materialNodes).toEqual(paused.materialNodes);
          await recordJson(testInfo,'hold-resume',{running,blocked,paused,resumed});await button(page,'정면').click();
        }
      }
      for(const part of asset.moving_parts)expect(samples.some(s=>s.parts.find(p=>p.id===part.id)?.matrix.some((v,i)=>Math.abs(v-(initial.parts.find(p=>p.id===part.id)?.matrix[i]??Infinity))>1e-4))).toBe(true);
      await button(page,'일시 정지').click();await expect.poll(async()=>(await state(page)).frame.clock).toBe('paused');const paused=await state(page),lodSamples=[];
      for(const level of [0,1,2,0]){
        await button(page,`LOD ${level}`).click();await expect.poll(async()=>(await state(page)).lod).toBe(level);const current=await state(page);lodSamples.push(current);assertMechanics(asset,current);
        expect(current.parts).toEqual(paused.parts);expect(current.fixed).toEqual(paused.fixed);expect(current.sockets).toEqual(paused.sockets);expect(current.materialNodes).toEqual(paused.materialNodes);await page.screenshot({path:testInfo.outputPath(`paused-lod-${level}.png`),fullPage:true});
      }
      expect(lodSamples[0]?.triangles).toBeGreaterThan(lodSamples[1]?.triangles??Infinity);expect(lodSamples[1]?.triangles).toBeGreaterThan(lodSamples[2]?.triangles??Infinity);
      if(asset.cutaway.roof_node_ids.length){await button(page,'지붕 절개').click();await page.screenshot({path:testInfo.outputPath('cutaway.png'),fullPage:true});expect((await state(page)).parts).toEqual(paused.parts);expect((await state(page)).sockets).toEqual(paused.sockets);await button(page,'지붕 절개').click();}
      expect((await readWorld(page.request)).run).toEqual(backend.run);
      const cyclePath=await recordJson(testInfo,'full-cycle-samples',{binding,assetId:asset.id,samples,boundSamples,lodSamples,synthetic:true,scope:'14 actual assets and explicit family mechanism/custody fixture; T28 transport and T31 scheduler integration remain future.'});
      await recordJson(testInfo,'full-cycle-authorizations',{source:sources,payloads});const media=await recording.finish();
      const receipt:FactoryReceipt={schemaVersion:1,attemptId:recording.identity.attempt_id,authority:initialContract.authority,backend:{runId:backend.run.id,revision:backend.run.revision,elapsedMs:backend.run.elapsed_ms,payload:await artifact(backendPath),custody:backend.materials.map(m=>({materialId:m.id,versionId:m.current_version_id,locationId:m.location_id}))},samples:[initialSample],screenshot:await artifact(actualPath),emptyScreenshot:await artifact(emptyPath),pixels,video:{artifact:media.video,attemptId:recording.identity.attempt_id,authority:initialContract.authority,continuous:true,step0,firstActionAtMs},trace:media.trace,chrome:media.chrome,source:{manifestSha256:sources.manifestSha256,bundleHash:initialContract.authority.bundleHash,projectionPayload:await artifact(projectionPath)},cancelled:false};
      validateFactoryReceipt(receipt,{attemptId:receipt.attemptId,authority:receipt.authority,backend:receipt.backend,manifestSha256:sources.manifestSha256,videoSha256:media.video.sha256});await verifyReceiptArtifacts(receipt);
      const decoded=testInfo.outputPath('decoded');await mkdir(decoded);execFileSync('/opt/homebrew/bin/ffmpeg',['-hide_banner','-loglevel','error','-i',media.video.path,'-vf','fps=2,scale=720:-1',join(decoded,'frame-%03d.png')],{timeout:30_000});
      const decodedFrames=await readdir(decoded);expect(decodedFrames.length).toBeGreaterThanOrEqual(3);await recordJson(testInfo,'receipt',{...receipt,cyclePayload:await artifact(cyclePath),decodedFrames:await Promise.all(decodedFrames.map(f=>artifact(join(decoded,f))))});
    }finally{await recording.finish();}
  });

  test(`bad-pivot-or-binding ${specification.key} typed rejection without partial geometry`,async({browser,baseURL},testInfo)=>{
    test.setTimeout(120_000);if(!baseURL)throw new RangeError('Owned fixture URL required');const recording=await startFactoryObservation(browser,baseURL,testInfo),page=recording.page;
    try{
      const sources=await currentSources(),asset=sources.assets.find(a=>a.variant===specification.variant);if(!asset)throw new RangeError('Actual asset absent');
      const baseline=await resetScenario(page.request),familyPath=`**/assets/steelworks/${asset.family}/manifest.json`,manifest=JSON.parse(sources.raws[asset.family==='steelmaking'?0:1]??'null'),reports=[];
      for(const mode of ['pivot','binding'] as const){
        const changed=corruptAsset(asset,mode,sourceRoot),lod=asset.lods[0];if(!lod)throw new RangeError('Actual LOD absent');
        const body=JSON.stringify({...manifest,assets:sources.assets.filter(a=>a.family===asset.family).map(a=>a.id===asset.id?changed.asset:a)});
        await page.route(familyPath,route=>route.fulfill({contentType:'application/json',body}));await page.route(`**/${lod.artifact.path.slice(7)}`,route=>route.fulfill({contentType:'model/gltf-binary',body:changed.bytes}));
        await page.goto(`${entry}?asset=${encodeURIComponent(asset.id)}&qa-attempt=${recording.identity.attempt_id}`);await expect(page.getByRole('alert')).toContainText(mode==='pivot'?'rest:':'clip:');await expect(page.getByTestId('load-status')).toHaveText('자산 오류');await expect(page.locator('canvas')).toHaveAttribute('data-asset-state',/^\{/);
        const partial=z.object({triangles:z.number(),materialNodes:z.array(z.unknown())}).parse(JSON.parse(await page.locator('canvas').getAttribute('data-asset-state')??'null'));expect(partial.triangles).toBe(0);expect(partial.materialNodes).toHaveLength(0);expect((await readWorld(page.request)).run).toEqual(baseline.run);
        await page.screenshot({path:testInfo.outputPath(`${mode}-rejected.png`),fullPage:true});reports.push({mode,originalSha256:changed.originalSha256,changedSha256:changed.changedSha256,error:await page.getByRole('alert').textContent(),partialGeometry:false});
        await page.unroute(familyPath);await page.unroute(`**/${lod.artifact.path.slice(7)}`);
      }
      expect((await currentSources()).manifestSha256).toBe(sources.manifestSha256);await recordJson(testInfo,'bad-pivot-or-binding',{binding,reports,sourceUntouched:true});
    }finally{await recording.finish();}
  });
}

test('bad-pivot-or-binding missing EAF roof and wrong semantic family reject current manifests',async({browser,baseURL},testInfo)=>{
  if(!baseURL)throw new RangeError('Owned fixture URL required');const recording=await startFactoryObservation(browser,baseURL,testInfo),page=recording.page;
  try{
    const sources=await currentSources(),manifest=JSON.parse(sources.raws[1]??'null'),eaf=sources.assets.find(a=>a.kind==='eaf');if(!eaf)throw new RangeError('Required EAF absent');
    for(const mode of ['roof','family'] as const){
      const changed=mode==='roof'?{...eaf,moving_parts:eaf.moving_parts.filter(p=>p.id!=='roof_swing')}:{...eaf,family:'steelmaking'};
      await page.route('**/assets/steelworks/stainless/manifest.json',route=>route.fulfill({contentType:'application/json',body:JSON.stringify({...manifest,assets:sources.assets.filter(a=>a.family==='stainless').map(a=>a.id===eaf.id?changed:a)})}));
      await page.goto(`${entry}?asset=${encodeURIComponent(eaf.id)}&qa-attempt=${recording.identity.attempt_id}`);await expect(page.getByRole('alert')).toContainText('requirements:');await expect(page.locator('canvas')).toHaveCount(0);await page.screenshot({path:testInfo.outputPath(`${mode}-rejected.png`),fullPage:true});await recordJson(testInfo,`${mode}-rejected`,{changed,error:await page.getByRole('alert').textContent()});await page.unroute('**/assets/steelworks/stainless/manifest.json');
    }
    expect((await currentSources()).manifestSha256).toBe(sources.manifestSha256);
  }finally{await recording.finish();}
});
