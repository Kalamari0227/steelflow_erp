import {test,expect} from '@playwright/test';
import {writeFile} from 'node:fs/promises';
import {z} from 'zod';
import type {Phase} from '../fixtures/transport/frames';
import type {} from '../fixtures/transport/api';
import type {} from '../fixtures/transport/complete/api';
const finite=z.number().finite(),vector=z.array(finite).length(3);
const stateShape=z.object({authority:z.literal('source-geometry-candidate-runtime-admission-pending'),manifestHash:z.string().length(64),lod:z.number(),phase:z.string(),progress:finite,paused:z.boolean(),actualProductLoader:z.literal(true),material:z.object({root:vector,quaternion:z.array(finite).length(4),materialId:z.literal('t16:material:1'),versionId:z.literal('t16:version:1'),dimensions:z.object({length_mm:z.null(),width_mm:z.literal(1000),thickness_mm:z.literal(2),diameter_mm:z.literal(1200),inner_diameter_mm:z.literal(600)}),support_local_mm:z.tuple([z.literal(0),z.literal(-600),z.literal(0)]),mass_kg:z.literal(20000),volumeM3:finite}),assets:z.array(z.object({id:z.string(),nodes:z.number(),parts:z.array(z.unknown())})),renderer:z.object({calls:z.number(),triangles:z.number()})});
const physicalShape=z.object({penetrations:z.array(z.object({mesh:z.string(),triangle:finite,radialMin:finite,radialMax:finite})),hook:z.object({distance:finite,mesh:z.string(),triangle:finite}).passthrough()}).passthrough();

test('full-cycle source geometry: all3 LOD, actual loader, insertion/lift/transfer/lower/withdraw and inverse',async({page},info)=>{
  // Given: immutable real .blend exports and the whole exact retained material version.
  const errors:string[]=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto('/tests/fixtures/transport/index.html');await expect(page.locator('canvas')).toHaveAttribute('data-ready','true');
  const records:unknown[]=[];
  for(const lod of [0,1,2]){
    await page.getByLabel('상세도',{exact:true}).selectOption(String(lod));await expect(page.locator('canvas')).toHaveAttribute('data-ready','true');
    const initial=stateShape.parse(JSON.parse(await page.locator('canvas').getAttribute('data-state')??'null'));expect(initial.assets).toHaveLength(3);expect(initial.renderer.triangles).toBeGreaterThan(1000);
    // When: the actual decoded parts traverse every finite operation phase in both directions.
    for(const phase of ['grip','lift','translate','lower','release','load-grip','load-lift','load-translate','load-lower','load-release'] satisfies Phase[]){
      const samples=await page.evaluate(({phase})=>{const rows=[];for(const progress of [0,.25,.5,.75,1]){const state=window.transportProof.sample(phase,progress);rows.push({state,physical:window.transportProof.physical()});}return rows;},{phase});
      for(const sample of samples){const state=stateShape.parse(sample.state),physical=physicalShape.parse(sample.physical);records.push({lod,phase,state,physical});
        // Then: the one source-bound rigid body keeps its exact version, dimensions and mass.
        expect(state.material.volumeM3).toBeCloseTo(Math.PI*.27,12);expect(physical.penetrations,JSON.stringify({lod,phase,progress:state.progress,hits:physical.penetrations.slice(0,4)})).toHaveLength(0);
        if(['lift','translate','lower','load-lift','load-translate','load-lower'].includes(phase))expect(physical.hook.distance).toBeLessThanOrEqual(.01);
      }
      await page.screenshot({path:info.outputPath(`lod${lod}-${phase}.png`),fullPage:true});
    }
    for(const label of ['정면','측면','후면','근접']){await page.getByRole('button',{name:label,exact:true}).click();await page.screenshot({path:info.outputPath(`lod${lod}-${label}.png`),fullPage:true});}
    const paused=await page.evaluate(()=>window.transportProof.sample('paused',.5));await page.getByRole('button',{name:'정지',exact:true}).click();const held=stateShape.parse(JSON.parse(await page.locator('canvas').getAttribute('data-state')??'null'));expect(held.material).toEqual(stateShape.parse(paused).material);
  }
  await writeFile(info.outputPath('actual-source-samples.json'),JSON.stringify({authority:'source geometry only; runtime T58/T16 pending',records},null,2));expect(errors).toHaveLength(0);
});

test('bad-pivot-or-binding rejects altered actual bytes through product loader',async({page},info)=>{
  // Given: the actual immutable exported truck and current product admission/loader.
  await page.goto('/tests/fixtures/transport/index.html');await expect(page.locator('canvas')).toHaveAttribute('data-ready','true');
  // When: exact same source GLB is loaded against forged hash/binding metadata.
  const result=z.array(z.object({mode:z.string(),rejected:z.boolean(),error:z.string().nullable()})).parse(await page.evaluate(()=>window.transportProof.negatives()));
  // Then: no altered candidate is admitted and the previously displayed scene stays intact.
  expect(result).toHaveLength(2);expect(result.every(r=>r.rejected)).toBe(true);await writeFile(info.outputPath('actual-browser-rejections.json'),JSON.stringify(result,null,2));await expect(page.locator('canvas')).toHaveAttribute('data-ready','true');
});

const completeShape=z.object({authority:z.literal('source-geometry-only-runtime-admission-pending'),manifestHash:z.string().length(64),lod:z.number(),direction:z.enum(['load','unload']),elapsed:z.number(),duration:z.literal(34400),playing:z.boolean(),blocked:z.boolean(),frame:z.object({phase:z.string(),segment:z.string(),bridge:z.number(),trolley:z.number(),hoist:z.number(),material:vector}),materialId:z.literal('t16:material:1'),versionId:z.literal('t16:version:1'),factorySegments:z.literal(64),materialScale:z.tuple([z.literal(1),z.literal(1),z.literal(1)]),materialRoot:vector,nodes:z.number().positive(),renderer:z.object({triangles:z.number().positive(),calls:z.number().positive()})});
for(const lod of[0,1,2])for(const direction of['unload','load'] as const)test(`complete parked source LOD${lod} ${direction}`,async({page},info)=>{
 const errors:string[]=[];page.on('pageerror',error=>errors.push(error.message));await page.goto('/tests/fixtures/transport/complete/index.html');await expect(page.locator('canvas')).toHaveAttribute('data-ready','true');await page.getByRole('combobox',{name:'상세도',exact:true}).selectOption(String(lod));await expect(page.locator('canvas')).toHaveAttribute('data-ready','true');await page.getByRole('combobox',{name:'방향',exact:true}).selectOption(direction);await expect(page.locator('canvas')).toHaveAttribute('data-ready','true');
 const initial=completeShape.parse(await page.evaluate(()=>window.completeHandlingQA.state()));expect(initial.lod).toBe(lod);expect(initial.direction).toBe(direction);expect(initial.frame).toMatchObject({bridge:6,trolley:0,hoist:2});
 const samples=await page.evaluate(async({lod,direction})=>{const response=await fetch(`/handling-fixture/lod${lod}/drop1-${direction==='unload'?'unload':'load-source'}.json`);const raw:unknown=await response.json();if(typeof raw!=='object'||raw===null||!('phases'in raw)||!Array.isArray(raw.phases))throw Error('Source phases absent');const records:unknown[]=[];let elapsed=0;for(const phase of raw.phases){if(typeof phase!=='object'||phase===null||!('segments'in phase)||!Array.isArray(phase.segments))throw Error('Source segments absent');for(const segment of phase.segments){if(typeof segment!=='object'||segment===null||!('duration_ms'in segment)||typeof segment.duration_ms!=='number')throw Error('Source duration absent');for(const fraction of[0,.5,1])records.push(window.completeHandlingQA.sample(elapsed+fraction*segment.duration_ms));elapsed+=segment.duration_ms;}}return records;},{lod,direction});
 for(const sample of samples)completeShape.parse(sample);expect(samples).toHaveLength(24);await page.evaluate(()=>window.completeHandlingQA.sample(20000));for(const name of['사선','측면','상부','근접']){await page.getByRole('button',{name,exact:true}).click();await page.screenshot({path:info.outputPath(`lod${lod}-${direction}-${name}.png`),fullPage:true});}
 const held=completeShape.parse(await page.evaluate(()=>window.completeHandlingQA.hold(false)));await page.waitForTimeout(120);expect(completeShape.parse(await page.evaluate(()=>window.completeHandlingQA.state())).frame).toEqual(held.frame);const blocked=completeShape.parse(await page.evaluate(()=>window.completeHandlingQA.hold(true)));expect(blocked.blocked).toBe(true);await page.waitForTimeout(120);expect(completeShape.parse(await page.evaluate(()=>window.completeHandlingQA.state())).frame).toEqual(blocked.frame);
 await page.getByRole('button',{name:'사선',exact:true}).click();await page.evaluate(()=>window.completeHandlingQA.play(4));await expect.poll(async()=>completeShape.parse(await page.evaluate(()=>window.completeHandlingQA.state())).elapsed,{timeout:15000}).toBe(34400);const final=completeShape.parse(await page.evaluate(()=>window.completeHandlingQA.state()));expect(final.frame).toMatchObject({bridge:6,trolley:0,hoist:2});expect(final.materialRoot).toEqual([0,2.6,direction==='unload'?6:0]);await writeFile(info.outputPath('complete-source-records.json'),JSON.stringify({qualification:'Actual product geometry factory and real decoded source preview; no runtime/C1 admission or VersionCoil component resource claim.',initial,samples,held,blocked,final,errors},null,2));expect(errors).toEqual([]);expect(await page.evaluate(()=>window.completeHandlingQA.dispose())).toEqual({loaded:0,disposed:true});
});
