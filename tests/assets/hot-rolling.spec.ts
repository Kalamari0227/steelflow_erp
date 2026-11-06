import type { Asset } from '../../src/operations/scene/assets/manifest';
import { expect } from '@playwright/test';
import type { Page } from '@playwright/test';
import { createHash } from 'node:crypto';
import { readFile, readdir, mkdir } from 'node:fs/promises';
import { readFileSync } from 'node:fs';
import { execFileSync } from 'node:child_process';
import { join, resolve } from 'node:path';
import { z } from 'zod';
import { Quaternion, Vector3 } from 'three';
import { productionParser } from '../fixtures/hot-rolling/parser.mjs';
import { test, readWorld, recordJson, resetScenario } from '../helpers/operations';
import { artifact, compareScreenshotPixels, readBoundSample, startFactoryObservation, validateFactoryReceipt, verifyReceiptArtifacts, AuthoritySchema } from '../helpers/factory';
import type { FactoryReceipt } from '../helpers/factory';
import { corruptAsset } from '../fixtures/hot-rolling/corrupt';

const requirements=z.object({existing_bindings:z.array(z.object({variant:z.string(),allowed_families:z.array(z.string())}).passthrough())}).parse(JSON.parse(readFileSync('shared/asset-requirements.json','utf8')));
const bindings = requirements.existing_bindings.filter(b => b.allowed_families.includes('hot-rolling'));
const entry = '/tests/fixtures/hot-rolling/index.html';
const sourceRoot=resolve(process.env.STEELFLOW_QA_HOT_ROLLING_ROOT ?? '.');
const manifestPath=resolve(sourceRoot,'public/assets/steelworks/hot-rolling/manifest.json');
const number = z.number().finite(), vector = z.array(number).length(3), quaternion = z.array(number).length(4);
const stateShape = z.object({ key:z.string(),rootUuid:z.string(),variant:z.string(),lod:z.number().nullable(),cutaway:z.boolean(),triangles:z.number(),parts:z.array(z.object({id:z.string(),position:vector,quaternion,matrix:z.array(number).length(16)})),fixed:z.array(z.object({id:z.string(),state:number,matrix:z.array(number).length(16)})),sockets:z.array(z.object({id:z.string(),position:vector,normal:vector})),materialNodes:z.array(z.object({id:z.string(),attachmentId:z.string(),versionId:z.string(),position:vector,min:vector,max:vector,supportDistanceM:number}).passthrough()),machineContact:z.object({distance:number,triangleId:number,worldVertices:z.array(vector).length(3),closestPoint:vector,normal:vector,meshName:z.string(),matrixWorld:z.array(number).length(16)}).nullable(),pose:z.object({socket_id:z.string(),contact_m:vector,position_m:vector,channels:z.array(z.object({function_id:z.string(),kind:z.string(),value:number}))}).passthrough(),frame:z.object({name:z.string(),progress:number,clock:z.string()}) }).passthrough();
const surfaceShape=z.object({distance:number,triangleId:number,worldVertices:z.array(vector).length(3),closestPoint:vector,normal:vector,matrixWorld:z.array(number).length(16)});
function assertCoilerContact(current:ReturnType<typeof stateShape.parse>) {
  const input=z.object({at_ms:number,anchor:z.object({socket_id:z.literal('work')}),attachment_id:z.string(),material:z.object({dimensions:z.object({length_mm:z.literal(4000)})}),attachments:z.array(z.object({id:z.string(),socket_id:z.string(),released_at_ms:number.nullable()}))}).parse(current.phaseInput);
  expect(input.attachments.filter(a => a.released_at_ms===null)).toHaveLength(1);expect(input.attachments.find(a => a.id===input.attachment_id)?.socket_id).toBe('work');
  expect(current.pose.socket_id).toBe('work');expect(current.pose.contact_m).toEqual([.3,1.32,0]);
  expect(current.materialNodes).toHaveLength(1);const material=current.materialNodes[0];if(!material || !current.machineContact)throw new Error('Actual coiler surfaces absent');
  const surface=surfaceShape.parse(material.surface);expect(material.components).toBe(1);
  for(const actual of [surface,current.machineContact]) {expect(actual.distance).toBeLessThanOrEqual(.01);expect(actual.triangleId).toBeGreaterThanOrEqual(0);}
  const clearance=z.object({maxPenetrationM:number,meshes:z.array(z.unknown()).min(1)}).parse(current.feedClearance);expect(clearance.maxPenetrationM).toBeLessThanOrEqual(.000001);
  expect(current.machineContact.normal[1]).toBeGreaterThan(.97);expect(surface.normal[1]).toBeLessThan(-.99);
  expect(current.machineContact.normal.reduce((sum,v,i) => sum+v*(surface.normal[i] ?? 0),0)).toBeLessThan(-.97);
  const channel=current.pose.channels.find(c => c.function_id==='winding_mandrel');if(!channel)throw new Error('Canonical winding scalar absent');
  expect(material.mechanismProgress).toBeCloseTo(channel.value/(2*Math.PI),10);expect(current.pose.position_m).toEqual([0,1.326,.35]);
}
const phaseInputShape=z.object({at_ms:number,attachment_id:z.string(),anchor:z.object({owner_id:z.string(),socket_id:z.string()}),material:z.object({support_local_mm:vector}),boundary:z.object({released_attachment_id:z.string(),acquired_attachment_id:z.string(),at_ms:number}).nullable(),attachments:z.array(z.object({id:z.string(),owner_id:z.string(),socket_id:z.string(),acquired_at_ms:number,released_at_ms:number.nullable()}))});
function assertRetainedSupport(previous:ReturnType<typeof phaseInputShape.parse>,current:ReturnType<typeof phaseInputShape.parse>) {
  const prior=previous.attachments.find(a => a.id===previous.attachment_id),active=current.attachments.find(a => a.id===current.attachment_id);
  if(!prior || !active)throw new Error('Actual retained attachment absent');
  if(prior.id===active.id){expect(active.owner_id).toBe(prior.owner_id);expect(active.socket_id).toBe(prior.socket_id);}
  else {const boundary=current.boundary;if(!boundary)throw new Error('Support changed without exact retained boundary');
    expect(boundary.released_attachment_id).toBe(prior.id);expect(boundary.acquired_attachment_id).toBe(active.id);expect(boundary.at_ms).toBe(current.at_ms);
    const released=current.attachments.find(a => a.id===prior.id);if(!released)throw new Error('Prior support history erased');
    expect(released.owner_id).toBe(prior.owner_id);expect(released.socket_id).toBe(prior.socket_id);expect(released.acquired_at_ms).toBe(prior.acquired_at_ms);expect(released.released_at_ms).toBe(boundary.at_ms);expect(active.acquired_at_ms).toBe(boundary.at_ms);
  }
}
function assertInternalFeed(current:ReturnType<typeof stateShape.parse>,asset:Asset){
  const profile=asset.internal_feeds?.[0];if(!profile)throw new Error('Declared feed absent');
  const input=z.object({material:z.object({internal_feed:z.object({feed_id:z.string()}),support_local_mm:vector,dimensions:z.object({thickness_mm:number})})}).parse(current.phaseInput);
  expect(input.material.internal_feed.feed_id).toBe(profile.id);expect(input.material.support_local_mm).toEqual([0,-input.material.dimensions.thickness_mm/2,0]);
  const driver=asset.moving_parts.find(p=>p.id===profile.driver_part_id),channel=current.pose.channels.find(c=>c.function_id===driver?.function);if(!driver || !channel)throw new Error('Real canonical feed driver absent');
  const u=(channel.value-driver.range.min)/(driver.range.max-driver.range.min);expect(current.pose.position_m[0]).toBeCloseTo(profile.start_m[0]+(profile.end_m[0]-profile.start_m[0])*u,9);
  const witnesses=z.array(z.object({part_id:z.string(),position_m:vector,machine:surfaceShape,material:surfaceShape})).min(6).parse(current.feedWitnesses);
  expect(Math.min(...witnesses.map(w=>w.position_m[0] ?? Infinity))).toBeLessThan(current.pose.position_m[0] ?? -Infinity);expect(Math.max(...witnesses.map(w=>w.position_m[0] ?? -Infinity))).toBeGreaterThan(current.pose.position_m[0] ?? Infinity);
  expect(Math.min(...witnesses.map(w=>w.position_m[2] ?? Infinity))).toBeLessThan(current.pose.position_m[2] ?? -Infinity);expect(Math.max(...witnesses.map(w=>w.position_m[2] ?? -Infinity))).toBeGreaterThan(current.pose.position_m[2] ?? Infinity);
  for(const witness of witnesses){expect(witness.machine.distance).toBeLessThanOrEqual(.01);expect(witness.material.distance).toBeLessThanOrEqual(.01);expect(witness.machine.normal[1]).toBeGreaterThanOrEqual(.97);expect(witness.material.normal[1]).toBeLessThanOrEqual(-.97);}
  expect(z.object({hits:z.array(z.unknown())}).parse(current.rigidClearance).hits).toHaveLength(0);expect(z.array(number).min(2).parse(current.continuousSupport).length).toBeLessThanOrEqual(130);
}
const contractShape = z.object({ authority:AuthoritySchema,manifestSha256:z.string(),envelope:z.object({run_id:z.string(),revision:number,bundle_hash:z.string(),confirmed_sim_ms:number}).passthrough(),snapshot:z.object({run:z.object({id:z.string(),revision:number,elapsed_ms:number}).passthrough()}).passthrough(),context:z.unknown() });
const state = async (page: Page) => stateShape.parse(JSON.parse(await page.locator('canvas').getAttribute('data-asset-state') ?? 'null'));
const waitFrame=async(page:Page,name:string)=>{await page.waitForFunction(label=>document.querySelector('canvas')?.getAttribute('data-asset-state')?.includes(JSON.stringify({name:label}).slice(1,-1)) && document.querySelector('canvas')?.getAttribute('data-asset-state')?.includes('\"poseReady\":true'),name,{polling:'raf',timeout:10_000});};
const selected = (page: Page, name: string) => page.getByRole('button',{name,exact:true});
test.use({trace:'off'});

for (const binding of bindings) {
  const key = binding.variant.split(':').at(-1);
  test(`full-cycle ${key} real mechanics, all angles, contact, pause and all LODs`, async ({ browser, baseURL }, testInfo) => {
    test.setTimeout(150_000);
    if (!baseURL || !key) throw new Error('Owned hot-rolling fixture identity missing');
    const recording = await startFactoryObservation(browser,baseURL,testInfo), page = recording.page;
    try {
      const raw = await readFile(manifestPath,'utf8'), manifest = (await productionParser())(raw), asset = manifest.assets.find(a => a.variant === binding.variant);
      expect(manifest.assets).toHaveLength(21); expect(bindings).toHaveLength(21); expect(new Set(manifest.assets.map(a => a.kind)).size).toBe(12);
      if (!asset) throw new Error('Registered T20 variant missing');
      if(asset.internal_feeds || asset.kind==='laying_head')test.setTimeout(600_000);
      await page.goto(`${entry}?asset=${encodeURIComponent(asset.id)}&qa-attempt=${recording.identity.attempt_id}`);
      await expect(page.getByTestId('load-status')).toHaveText('실제 모델 표시');
      await expect.poll(async () => (await state(page)).variant).toBe(binding.variant);
      const step0Path=testInfo.outputPath('step-0.png'); await page.screenshot({path:step0Path,fullPage:true});
      const step0={sequence:0 as const,atMs:Date.now(),screenshot:await artifact(step0Path)},firstActionAtMs=Date.now();
      const backend=await resetScenario(page.request),backendPath=await recordJson(testInfo,'backend-payload',backend);
      const initial=await state(page),initialSample=await readBoundSample(page);
      expect(initial.triangles).toBeGreaterThan(7000); expect(initial.materialNodes).toHaveLength(1); expect(initial.materialNodes[0]?.supportDistanceM).toBeLessThanOrEqual(.01);
      const contract=contractShape.parse(JSON.parse(await page.getByTestId('fixture-contract').textContent() ?? 'null'));
      expect(contract.manifestSha256).toBe(createHash('sha256').update(raw).digest('hex'));
      const projectionPath=await recordJson(testInfo,'t58-contract-payload',contract);
      const actualPath=testInfo.outputPath('actual.png'),emptyPath=testInfo.outputPath('empty.png');
      const actual=await page.locator('canvas').screenshot({path:actualPath});
      await selected(page,'기하 숨김 · 메타데이터 유지').click(); const empty=await page.locator('canvas').screenshot({path:emptyPath});
      const pixels=await compareScreenshotPixels(page,actual,empty); expect(pixels.changedPixels).toBeGreaterThan(pixels.minimumPixels);
      await selected(page,'기하 숨김 · 메타데이터 유지').click();
      const samples=[];let previousSupport=phaseInputShape.parse(initial.phaseInput);
      for (const phase of ['idle','entry','running-25','running-50','blocked','paused','resumed',...(asset.kind==='cooling_bed' ? ['handoff-before','handoff'] : []),'running-75','exit','complete']) {
        await page.getByLabel('공정 샘플',{exact:true}).selectOption({label:phase});
        await expect.poll(async () => (await state(page)).frame.name).toBe(phase);
        const current=await state(page); samples.push(current);
        if(asset.kind==='coiler') assertCoilerContact(current);
        if(asset.internal_feeds)assertInternalFeed(current,asset);
        const currentSupport=phaseInputShape.parse(current.phaseInput);assertRetainedSupport(previousSupport,currentSupport);previousSupport=currentSupport;
        if(!current.machineContact)throw new Error('Actual GLB support surface missing');expect(current.machineContact.distance).toBeLessThanOrEqual(.01);expect(current.machineContact.normal[1]).toBeGreaterThan(.97);
        const body=current.materialNodes[0];if(!body)throw new Error('Single material missing');const bodySurface=surfaceShape.parse(body.surface);expect(bodySurface.normal[1]).toBeLessThan(-.97);
        expect(current.machineContact.normal.reduce((sum,v,i) => sum+v*(bodySurface.normal[i] ?? 0),0)).toBeLessThan(-.95);
        const law=z.object({mode:z.string(),driverFunction:z.string().nullable(),normalizedFeed:number,displacementM:number}).parse(current.supportLaw);
        if(law.mode==='canonical-fixed-support-linear-feed'){const driver=asset.moving_parts.find(p => p.function===law.driverFunction && p.binding.type==='clip'),channel=current.pose.channels.find(c => c.function_id===law.driverFunction);if(!driver || !channel)throw new Error('Canonical support law driver missing');
          expect(law.normalizedFeed).toBeCloseTo((channel.value-driver.range.min)/(driver.range.max-driver.range.min),10);expect(currentSupport.material.support_local_mm[0]).toBeCloseTo((.5-law.normalizedFeed)*5400,7);expect(current.pose.position_m[0]).toBeCloseTo((initial.pose.position_m[0] ?? 0)+law.displacementM,8);}
        if(phase==='handoff') await recordJson(testInfo,'bed-same-time-event-input',JSON.parse(await page.getByTestId('fixture-contract').textContent() ?? 'null'));
        for (const part of asset.moving_parts) {
          const binding=part.binding;
          const driver=binding.type==='mechanical_follower' ? asset.moving_parts.find(p => p.id===binding.driver_part_id) : part;
          if (!driver) throw new Error('Declared driver absent');
          const channel=current.pose.channels.find(c => c.function_id===driver.function),actualPart=current.parts.find(p => p.id===part.id),rest=asset.nodes.find(n => n.id===part.node_id);
          if (!channel || !actualPart || !rest) throw new Error('Actual pose frame absent');
          const value=part.binding.type==='mechanical_follower' ? part.range.rest+part.binding.ratio*(channel.value-driver.range.rest) : channel.value;
          const displacement=value-part.range.rest;
          if (part.motion==='rotation') { const expected=new Quaternion().setFromAxisAngle(new Vector3(...part.axis),displacement).multiply(new Quaternion(...rest.transform.rotation_xyzw)); expect(Math.abs(expected.dot(new Quaternion().fromArray(actualPart.quaternion)))).toBeCloseTo(1,5); }
          else expect(actualPart.position).toEqual(rest.transform.position_m.map((v,i) => expect.closeTo(v+(part.axis[i] ?? 0)*displacement,5)));
        }
        expect(current.key).toBe(initial.key); expect(current.rootUuid).toBe(initial.rootUuid); expect(current.materialNodes).toHaveLength(1);
        expect(current.materialNodes[0]?.supportDistanceM).toBeLessThanOrEqual(.01);
        const work=current.sockets.find(s => s.id===current.pose.socket_id); if (!work) throw new Error('Work surface absent');
        if(!asset.internal_feeds)expect(Math.hypot(...current.pose.contact_m.map((v,i) => v-(work.position[i] ?? Infinity)))).toBeLessThanOrEqual(.01);else expect(current.sockets.find(s=>s.id==='work')).toEqual(initial.sockets.find(s=>s.id==='work'));
        if(phase==='complete') await page.screenshot({path:testInfo.outputPath('complete-endpose.png'),fullPage:true});
        if (['idle','running-50','blocked'].includes(phase)) for (const angle of ['정면','측면','후면','근접']) {
          await selected(page,angle).click(); await page.screenshot({path:testInfo.outputPath(`${phase}-${angle}.png`),fullPage:true});
          await recordJson(testInfo,`${phase}-${angle}-nodes`,await state(page));
        }
      }
      if(asset.kind==='cooling_bed') {
        const before=samples.find(s => s.frame.name==='handoff-before'),after=samples.find(s => s.frame.name==='handoff');if(!before || !after)throw new Error('Exact cooling-bed boundary absent');
        expect(Math.hypot(...before.pose.contact_m.map((v,i) => v-(after.pose.contact_m[i] ?? Infinity)))).toBeLessThanOrEqual(.01);
        expect(Math.hypot(...before.pose.position_m.map((v,i) => v-(after.pose.position_m[i] ?? Infinity)))).toBeLessThanOrEqual(.01);expect(before.pose.channels).toEqual(after.pose.channels);expect(before.materialNodes[0]?.id).toBe(after.materialNodes[0]?.id);expect(before.materialNodes[0]?.versionId).toBe(after.materialNodes[0]?.versionId);
        const boundaryLods=[];for(const level of [0,1,2]){await selected(page,`LOD ${level}`).click();await expect.poll(async () => (await state(page)).lod).toBe(level);await page.getByLabel('공정 샘플',{exact:true}).selectOption({label:'handoff'});await expect.poll(async () => (await state(page)).frame.name).toBe('handoff');const current=await state(page);expect(current.machineContact?.distance).toBeLessThanOrEqual(.01);expect(current.materialNodes[0]?.supportDistanceM).toBeLessThanOrEqual(.01);boundaryLods.push(current);await page.screenshot({path:testInfo.outputPath(`bed-boundary-lod-${level}.png`),fullPage:true});}await selected(page,'LOD 0').click();await expect.poll(async () => (await state(page)).lod).toBe(0);
        await recordJson(testInfo,'bed-same-time-boundary',{before,after,boundaryLods,synthetic:true,scope:'Exact existing T58 release/acquire event at full stroke; subsequent empty rack return retains both attachments.'});
      }
      const running=samples.find(s => s.frame.name==='running-50'),blocked=samples.find(s => s.frame.name==='blocked'),paused=samples.find(s => s.frame.name==='paused'),resumed=samples.find(s => s.frame.name==='resumed');
      if (!running || !blocked || !paused || !resumed) throw new Error('Full hold/resume sample sequence absent');
      expect(running.parts).not.toEqual(initial.parts); expect(blocked.parts).toEqual(running.parts); expect(paused.parts).toEqual(blocked.parts); expect(resumed.parts).toEqual(paused.parts);
      expect(blocked.materialNodes).toEqual(running.materialNodes); expect(paused.materialNodes).toEqual(blocked.materialNodes); expect(resumed.materialNodes).toEqual(paused.materialNodes);
      await page.getByLabel('공정 샘플',{exact:true}).selectOption({label:'paused'});
      await expect.poll(async () => (await state(page)).frame.name).toBe('paused');
      const lodSamples=[];
      for (const level of [0,1,2,0]) {
        await selected(page,`LOD ${level}`).click(); await expect.poll(async () => (await state(page)).lod).toBe(level);
        const current=await state(page); lodSamples.push(current); expect(current.parts).toEqual(paused.parts); expect(current.sockets).toEqual(paused.sockets); expect(current.materialNodes).toEqual(paused.materialNodes);
        await page.screenshot({path:testInfo.outputPath(`paused-lod-${level}.png`),fullPage:true});
      }
      const denseContactSamples=[];
      if(asset.kind==='laying_head'){
        const dense=[],retained=z.object({anchor:z.unknown(),attachment_id:z.string(),material:z.unknown()}).parse(initial.phaseInput);
        for(const level of [0,1,2]){await selected(page,`LOD ${level}`).click();await expect.poll(async()=>(await state(page)).lod).toBe(level);
          for(let i=0;i<=100;i++){const name=`laying-${(i/100).toFixed(4)}`;await page.getByLabel('공정 샘플',{exact:true}).selectOption({label:name});await waitFrame(page,name);const current=await state(page),body=current.materialNodes[0];if(!body)throw Error('Single connected laying material absent');expect(body.components).toBe(1);expect(body.supportDistanceM).toBeLessThanOrEqual(.01);expect(current.machineContact?.distance).toBeLessThanOrEqual(.01);expect(body.mechanismProgress).toBeCloseTo(i/100,10);expect(current.pose.socket_id).toBe(initial.pose.socket_id);expect(current.pose.position_m).toEqual(initial.pose.position_m);expect(current.phaseInput).toMatchObject(retained);dense.push(current);}
        }
        await selected(page,'LOD 0').click();await page.getByLabel('공정 샘플',{exact:true}).selectOption({label:'paused'});await waitFrame(page,'paused');await recordJson(testInfo,'laying-canonical-all-LOD-dense',{samples:dense,originalRangeRad:[0,5*Math.PI],synthetic:true,scope:'One connected synthetic rod follows hollow actual inlet and rotating pipe; actual all-machine and self triangle clearance recorded in separately source-bound full-phase geometry proof.'});
      }
      if(asset.kind==='coiler') {
        const anchorIdentity=(current:ReturnType<typeof stateShape.parse>) => ({socket:current.pose.socket_id,contact:current.pose.contact_m,position:current.pose.position_m,material:current.materialNodes.map(m => ({id:m.id,attachmentId:m.attachmentId,versionId:m.versionId,position:m.position})),identity:current.identity,key:current.key,retainedAttachment:z.object({attachments:z.array(z.unknown()),anchor:z.unknown(),attachment_id:z.string()}).parse(current.phaseInput)});
        for(const level of [0,1,2]) {
          await selected(page,`LOD ${level}`).click();await expect.poll(async () => (await state(page)).lod).toBe(level);
          for(const feed of [...Array.from({length:21},(_,i) => i/20),.4999,.5001].sort((a,b) => a-b)) {
            const name=`contact-${feed.toFixed(4)}`;await page.getByLabel('공정 샘플',{exact:true}).selectOption({label:name});await expect.poll(async () => (await state(page)).frame.name).toBe(name);
            const current=await state(page);assertCoilerContact(current);expect(anchorIdentity(current)).toEqual(anchorIdentity(initial));denseContactSamples.push(current);
            if([.4999,.5,.5001,1].includes(feed)) await page.screenshot({path:testInfo.outputPath(`coiler-${name}-lod-${level}.png`),fullPage:true});
          }
        }
        await page.getByLabel('공정 샘플',{exact:true}).selectOption({label:'contact-0.5000'});await expect.poll(async () => (await state(page)).frame.name).toBe('contact-0.5000');
        const boundaryBefore=await state(page);await selected(page,'LOD 0').click();await expect.poll(async () => (await state(page)).lod).toBe(0);
        const boundaryAfter=await state(page);assertCoilerContact(boundaryAfter);expect(anchorIdentity(boundaryAfter)).toEqual(anchorIdentity(boundaryBefore));expect(boundaryAfter.materialNodes).toEqual(boundaryBefore.materialNodes);
        await selected(page,'같은 단계 재연결').click();await expect.poll(async () => (await state(page)).bindingRevision).toBe(1);
        const componentAfter=await state(page);assertCoilerContact(componentAfter);expect(anchorIdentity(componentAfter)).toEqual(anchorIdentity(boundaryBefore));expect(componentAfter.materialNodes).toEqual(boundaryBefore.materialNodes);expect(componentAfter.parts).toEqual(boundaryBefore.parts);
        await recordJson(testInfo,'coiler-same-anchor-contact',{samples:denseContactSamples,boundaryBefore,boundaryAfter,componentAfter,stripLengthM:4,rangeRad:[0,2*Math.PI],scope:'Complete declared synthetic one-turn phase; remaining unwound tail visible. No finished coil, business conversion or external handoff claim.'});
        await page.getByLabel('공정 샘플',{exact:true}).selectOption({label:'paused'});await expect.poll(async () => (await state(page)).frame.name).toBe('paused');
      }
      if(asset.internal_feeds){
        const labels=(await page.getByLabel('공정 샘플',{exact:true}).locator('option').allTextContents()).filter(name=>name.startsWith('feed-'));expect(labels.length).toBeGreaterThanOrEqual(3);const dense=[];
        for(const level of [0,1,2]){await selected(page,`LOD ${level}`).click();await expect.poll(async()=>(await state(page)).lod).toBe(level);for(const label of labels){await page.getByLabel('공정 샘플',{exact:true}).selectOption({label});await waitFrame(page,label);const current=await state(page);assertInternalFeed(current,asset);dense.push(current);}}
        await selected(page,'LOD 0').click();await page.getByLabel('공정 샘플',{exact:true}).selectOption({label:'paused'});await expect.poll(async()=>(await state(page)).frame.name).toBe('paused');
        for(const speed of [1,2,4]){await selected(page,`샘플 속도 x${speed}`).click();await expect.poll(async()=>z.object({speed:number}).parse((await state(page)).phaseInput).speed).toBe(speed);const held=await state(page);assertInternalFeed(held,asset);expect(held.parts).toEqual(paused.parts);expect(held.materialNodes).toEqual(paused.materialNodes);}
        await selected(page,'같은 단계 재연결').click();await expect.poll(async()=>(await state(page)).bindingRevision).toBe(1);const rebound=await state(page);assertInternalFeed(rebound,asset);expect(rebound.parts).toEqual(paused.parts);expect(rebound.materialNodes).toEqual(paused.materialNodes);
        const reopen=new URL(page.url());reopen.searchParams.set('phase','paused');
        const restartContext=await browser.newContext({baseURL,serviceWorkers:'block',recordVideo:{dir:testInfo.outputPath('restart-video'),size:{width:1440,height:1000}},viewport:{width:1440,height:1000}});let restarted;
        try{const restartPage=await restartContext.newPage(),video=restartPage.video();await restartPage.goto(reopen.toString());await expect(restartPage.getByTestId('load-status')).toHaveText('실제 모델 표시');await waitFrame(restartPage,'paused');restarted=await state(restartPage);assertInternalFeed(restarted,asset);expect(restarted.key).toBe(initial.key);expect(restarted.parts).toEqual(paused.parts);expect(restarted.materialNodes).toEqual(paused.materialNodes);await restartPage.screenshot({path:testInfo.outputPath('pinned-restart.png')});await restartContext.close();if(video)await video.saveAs(testInfo.outputPath('pinned-restart.webm'));}finally{await restartContext.close();}
        await recordJson(testInfo,'internal-feed-all-LOD-dense',{dense,rebound,restarted,sourceBindings:sourceRoot,scope:'Immutable synthetic canonical scalar projection with actual roller/material surfaces and whole-path COM admission. No business writer or external transfer claim.'});
      }
      expect(lodSamples[0]?.triangles).toBeGreaterThan(lodSamples[1]?.triangles ?? Infinity); expect(lodSamples[1]?.triangles).toBeGreaterThan(lodSamples[2]?.triangles ?? Infinity);
      if (asset.cutaway.roof_node_ids.length) { await selected(page,'지붕 절개').click(); await page.screenshot({path:testInfo.outputPath('roof-closed.png'),fullPage:true}); await selected(page,'지붕 절개').click(); expect((await state(page)).sockets).toEqual(paused.sockets); }
      expect((await readWorld(page.request)).run).toEqual(backend.run);
      const sourceBindings={manifest:await artifact(manifestPath),requirements:await artifact('shared/asset-requirements.json'),motionRecipes:await artifact('shared/motion-recipes.json'),sourceRoot};
      const cyclePath=await recordJson(testInfo,'full-cycle-samples',{sourceBindings,binding,assetId:asset.id,initial,samples,lodSamples,synthetic:true,scope:'Family mechanism and contact fixture; no live business scheduler integration.'});
      const media=await recording.finish();
      const receipt:FactoryReceipt={schemaVersion:1,attemptId:recording.identity.attempt_id,authority:contract.authority,backend:{runId:backend.run.id,revision:backend.run.revision,elapsedMs:backend.run.elapsed_ms,payload:await artifact(backendPath),custody:backend.materials.map(m => ({materialId:m.id,versionId:m.current_version_id,locationId:m.location_id}))},samples:[initialSample],screenshot:await artifact(actualPath),emptyScreenshot:await artifact(emptyPath),pixels,video:{artifact:media.video,attemptId:recording.identity.attempt_id,authority:contract.authority,continuous:true,step0,firstActionAtMs},trace:media.trace,chrome:media.chrome,source:{manifestSha256:contract.manifestSha256,bundleHash:contract.authority.bundleHash,projectionPayload:await artifact(projectionPath)},cancelled:false};
      validateFactoryReceipt(receipt,{attemptId:receipt.attemptId,authority:receipt.authority,backend:receipt.backend,manifestSha256:contract.manifestSha256,videoSha256:media.video.sha256}); await verifyReceiptArtifacts(receipt);
      const decoded=testInfo.outputPath('decoded'); await mkdir(decoded);
      execFileSync('/opt/homebrew/bin/ffmpeg',['-hide_banner','-loglevel','error','-i',media.video.path,'-vf','fps=2,scale=720:-1',join(decoded,'frame-%03d.png')],{timeout:30_000});
      const decodedFrames=await readdir(decoded); expect(decodedFrames.length).toBeGreaterThanOrEqual(3);
      await recordJson(testInfo,'receipt',{...receipt,cyclePayload:await artifact(cyclePath),decodedFrames:await Promise.all(decodedFrames.map(f => artifact(join(decoded,f))))});
    } finally { await recording.finish(); }
  });

  test(`bad-pivot-or-binding ${key} rejects corrupted actual GLB without partial state`, async ({ browser, baseURL },testInfo) => {
    test.setTimeout(90_000); if (!baseURL) throw new Error('Owned base URL required');
    const recording=await startFactoryObservation(browser,baseURL,testInfo),page=recording.page;
    try {
      const raw=await readFile(manifestPath,'utf8'),manifest=(await productionParser())(raw),asset=manifest.assets.find(a => a.variant===binding.variant);
      if (!asset) throw new Error('Actual asset missing');
      const baseline=await resetScenario(page.request),reports=[];
      for (const mode of ['pivot','binding'] as const) {
        const changed=corruptAsset(asset,mode,sourceRoot),lod=asset.lods[0]; if (!lod) throw new Error('LOD absent');
        const body=JSON.stringify({...manifest,assets:manifest.assets.map(a => a.id===asset.id ? changed.asset : a)});
        await page.route('**/assets/steelworks/hot-rolling/manifest.json',route => route.fulfill({contentType:'application/json',body}));
        await page.route(`**/${lod.artifact.path.slice('public/'.length)}`,route => route.fulfill({contentType:'model/gltf-binary',body:changed.bytes}));
        await page.goto(`${entry}?asset=${encodeURIComponent(asset.id)}&qa-attempt=${recording.identity.attempt_id}`);
        await expect(page.getByRole('alert')).toContainText(mode==='pivot' ? 'rest:' : 'clip:');
        await expect(page.getByTestId('load-status')).toHaveText('자산 오류');
        expect((await readWorld(page.request)).run).toEqual(baseline.run);
        const failed=z.object({triangles:number,materialNodes:z.array(z.unknown())}).parse(JSON.parse(await page.locator('canvas').getAttribute('data-asset-state') ?? 'null')); expect(failed.triangles).toBe(0); expect(failed.materialNodes).toHaveLength(0);
        await page.screenshot({path:testInfo.outputPath(`${mode}-rejected.png`),fullPage:true});
        reports.push({mode,originalSha256:changed.originalSha256,changedSha256:changed.changedSha256,error:await page.getByRole('alert').textContent(),partialGeometry:false});
        await page.unroute('**/assets/steelworks/hot-rolling/manifest.json'); await page.unroute(`**/${lod.artifact.path.slice('public/'.length)}`);
      }
      expect(createHash('sha256').update(await readFile(manifestPath)).digest('hex')).toBe(createHash('sha256').update(raw).digest('hex'));
      await recordJson(testInfo,'bad-pivot-or-binding',{binding,reports,realSourceUntouched:true});
    } finally {await recording.finish();}
  });
}

test('laying LOD return retains the newer approved phase after delayed actual GLB read',async({browser,baseURL},testInfo)=>{
  test.setTimeout(90_000);if(!baseURL)throw Error('Owned base URL required');
  const recording=await startFactoryObservation(browser,baseURL,testInfo),page=recording.page;let release=()=>{};
  try{
    const raw=await readFile(manifestPath,'utf8'),manifest=(await productionParser())(raw),asset=manifest.assets.find(a=>a.kind==='laying_head');if(!asset)throw Error('Pinned laying head absent');
    await page.goto(`${entry}?asset=${encodeURIComponent(asset.id)}&qa-attempt=${recording.identity.attempt_id}`);await expect(page.getByTestId('load-status')).toHaveText('실제 모델 표시');
    const baseline=await resetScenario(page.request);await page.getByLabel('공정 샘플',{exact:true}).selectOption({label:'paused'});await waitFrame(page,'paused');const paused=await state(page),samples=[];
    for(const level of [1,2,0]){
      await page.getByLabel('공정 샘플',{exact:true}).selectOption({label:'complete'});await waitFrame(page,'complete');
      const lod=asset.lods.find(l=>l.level===level);if(!lod)throw Error('Actual LOD absent');const url=`**/${lod.artifact.path.slice('public/'.length)}`;let seen=()=>{};
      const requested=new Promise<void>(resolve=>{seen=resolve;}),gate=new Promise<void>(resolve=>{release=resolve;});
      await page.route(url,async route=>{seen();await gate;await route.continue();});
      await selected(page,`LOD ${level}`).click();await requested;
      await page.getByLabel('공정 샘플',{exact:true}).selectOption({label:'paused'});await expect(page.getByTestId('phase-name')).toHaveText('paused');await waitFrame(page,'paused');release();
      await expect.poll(async()=>(await state(page)).lod).toBe(level);await waitFrame(page,'paused');const current=await state(page);
      expect(current.parts).toEqual(paused.parts);expect(current.sockets).toEqual(paused.sockets);expect(current.materialNodes).toEqual(paused.materialNodes);expect(current.pose).toEqual(paused.pose);expect(current.poseReady).toBe(true);
      await page.screenshot({path:testInfo.outputPath(`newer-paused-after-actual-lod-${level}.png`),fullPage:true});samples.push({level,actualArtifact:lod.artifact,current,delivery:'Actual pinned GLB read released only after newer paused phase selected; no asset bytes changed.'});await page.unroute(url);
    }
    expect((await readWorld(page.request)).run).toEqual(baseline.run);await recordJson(testInfo,'actual-lod-newer-phase',{manifestSha256:createHash('sha256').update(raw).digest('hex'),paused,samples});
  }finally{release();await recording.finish();}
});
