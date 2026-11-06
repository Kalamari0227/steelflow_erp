import { expect, type Page, type Response } from '@playwright/test';
import { z } from 'zod';
import { test, resetScenario, sendOperation, recordJson } from './helpers/operations';
import { factoryLayout } from '../src/operations/scene/layout';
import { WorldSchema, type World } from '../src/contracts';
import type { ProcessExecution } from '../src/operations/contracts';

const point = z.tuple([z.number(), z.number(), z.number()]);
const sceneSchema = z.object({ runId: z.string(), revision: z.number(), elapsedMs: z.number(), authoritativeElapsedMs: z.number(), reduced: z.boolean(), stale: z.boolean(), materials: z.array(z.object({ id: z.string(), worldRunId: z.string(), worldRevision: z.number(), form: z.string(), versionId: z.string(), position: point, phase: z.number(), equipmentId: z.string().nullable(), custody: z.string(), matrixWorld: z.array(z.number()) })), contacts: z.array(z.object({ equipmentId: z.string(), kind: z.string(), position: point })) });
const sceneState = async (page: Page) => {
  await expect(page.locator('canvas')).toHaveAttribute('data-scene-state', /"materials"/);
  return sceneSchema.parse(JSON.parse(await page.locator('canvas').getAttribute('data-scene-state') ?? '{}'));
};
async function focus(page: Page, world: World, materialId: string, equipmentId: string) {
  const station = factoryLayout.equipment.find(row => row.id === equipmentId);
  const material = world.materials.find(row => row.id === materialId);
  const lot = world.lots.find(row => row.id === material?.lot_id);
  const navigation = { selection: { run_id: world.run.id, order_id: lot?.order_id, material_id: materialId, stage_id: station?.stage_id, equipment_id: equipmentId }, level: 'equipment', view: '3d', followMaterial: false, cameraByScope: {} };
  await page.goto(`/?nav=${encodeURIComponent(JSON.stringify(navigation))}`);
  await expect.poll(async () => (await sceneState(page)).revision).toBe(world.run.revision);
}

const cameraSchema = z.object({ position: point, target: point, zoom: z.number() });
async function cameraState(page: Page) {
  await expect(page.locator('canvas')).toHaveAttribute('data-camera', /"position"/);
  return cameraSchema.parse(JSON.parse(await page.locator('canvas').getAttribute('data-camera') ?? '{}'));
}
async function orbitAndReturn(page: Page, process: ProcessExecution) {
  const canvas = page.locator('canvas');
  await canvas.scrollIntoViewIfNeeded();
  const bounds = await canvas.boundingBox();
  if (!bounds) throw new Error('Actual canvas bounds missing');
  const before = await cameraState(page);
  await page.mouse.move(bounds.x + bounds.width * 0.5, bounds.y + bounds.height * 0.5);
  await page.mouse.down();
  await page.mouse.move(bounds.x + bounds.width * 0.65, bounds.y + bounds.height * 0.55, { steps: 8 });
  await page.mouse.up();
  await expect.poll(async () => (await cameraState(page)).position).not.toEqual(before.position);
  const manual = await cameraState(page);
  await page.getByRole('button', { name: '공장 전경', exact: true }).click();
  await page.getByRole('button', { name: '2D', exact: true }).click();
  await page.getByTestId(`process-${process.id}`).click();
  await page.getByRole('button', { name: '3D', exact: true }).click();
  await expect.poll(async () => Math.hypot(...(await cameraState(page)).position.map((value, axis) => value - (manual.position[axis] ?? 0)))).toBeLessThan(0.000001);
  const restored = await cameraState(page);
  for (let axis = 0; axis < 3; axis += 1) expect(restored.target[axis]).toBeCloseTo(manual.target[axis] ?? 0, 6);
  expect(restored.zoom).toBe(manual.zoom);
  await page.getByRole('checkbox', { name: '소재 따라가기' }).check();
  return { before, manual, restored };
}

test('eight real processing contacts retain mesh identity and confirmed form', async ({ page, request }, testInfo) => {
  test.setTimeout(240_000);
  let world = await resetScenario(request);
  const captures: object[] = [];
  const stepMs = world.simulation.step_ms;
  const targets = [
    { kind: 'blast_furnace', material: 'MAT-ga-01' }, { kind: 'caster', material: 'MAT-ga-01' },
    { kind: 'roughing', material: 'MAT-ga-01' }, { kind: 'coiler', material: 'MAT-ga-01' },
    { kind: 'uncoiler', material: 'MAT-ga-01' }, { kind: 'annealing', material: 'MAT-ga-01' }, { kind: 'galvanizing', material: 'MAT-ga-01' },
    { kind: 'shear', material: 'MAT-plate-01' },
  ];
  const processIds = targets.map(target => {
    const process = world.processes.filter(row => row.material_id === target.material && factoryLayout.equipment.find(item => item.id === row.equipment_id)?.kind === target.kind).sort((a, b) => a.step_ordinal - b.step_ordinal)[0];
    if (!process) throw new Error(`Missing actual route operation: ${target.kind}`);
    return { ...target, processId: process.id };
  });
  for (let batch = 0; batch < 100 && processIds.some(target => world.processes.find(row => row.id === target.processId)?.status !== 'COMPLETED'); batch += 1) world = await sendOperation(request, { action: 'step' }, 48);
  const schedule = processIds.map(target => {
    const process = world.processes.find(row => row.id === target.processId);
    if (!process || process.status !== 'COMPLETED' || process.start_ms === null || process.end_ms === null) throw new Error(`Actual schedule was not observed: ${target.kind}`);
    return { ...target, startMs: process.start_ms, endMs: process.end_ms, midpointMs: Math.round((process.start_ms + process.end_ms) / (2 * stepMs)) * stepMs };
  });
  await recordJson(testInfo, 'T14-real-schedule-discovery', { discoveryRun: world.run, schedule });
  world = await resetScenario(request);
  for (const target of schedule) {
    if (target.kind === 'shear') world = await resetScenario(request);
    const inspectPhases = ['coiler', 'uncoiler', 'annealing'].includes(target.kind);
    if (inspectPhases) {
      const entryMs = Math.ceil((target.startMs + (target.endMs - target.startMs) * 0.05) / stepMs) * stepMs;
      while (world.run.elapsed_ms < entryMs) world = await sendOperation(request, { action: 'step' }, Math.min(48, (entryMs - world.run.elapsed_ms) / stepMs));
      const entryProcess = world.processes.find(row => row.id === target.processId);
      if (!entryProcess || entryProcess.status !== 'RUNNING') throw new Error(`Actual entry not running: ${target.kind}`);
      await focus(page, world, target.material, entryProcess.equipment_id);
      const entry = await sceneState(page);
      const bodies = entry.materials.filter(row => row.id === target.material);
      expect(bodies).toHaveLength(1);
      expect(bodies[0]?.phase).toBeGreaterThanOrEqual(0);
      expect(bodies[0]?.phase).toBeLessThan(0.35);
      expect(bodies[0]?.form).toBe(world.materials.find(row => row.id === target.material)?.form);
      await page.locator('canvas').screenshot({ path: testInfo.outputPath(`T19-${target.kind}-entry.png`) });
      await recordJson(testInfo, `T19-${target.kind}-entry`, { run: world.run, process: entryProcess, scene: entry, camera: await cameraState(page) });
    }
    expect(world.run.elapsed_ms).toBeLessThanOrEqual(target.midpointMs);
    while (world.run.elapsed_ms < target.midpointMs) world = await sendOperation(request, { action: 'step' }, Math.min(48, (target.midpointMs - world.run.elapsed_ms) / stepMs));
    const process = world.processes.find(row => row.id === target.processId);
    if (!process || process.start_ms === null || process.end_ms === null) throw new Error(`Replay operation missing: ${target.kind}`);
    expect(process.status).toBe('RUNNING');
    expect([process.start_ms, process.end_ms]).toEqual([target.startMs, target.endMs]);
    const phase = (world.run.elapsed_ms - process.start_ms) / (process.end_ms - process.start_ms);
    expect(phase).toBeGreaterThanOrEqual(0.35);
    expect(phase).toBeLessThanOrEqual(0.65);
    await focus(page, world, target.material, process.equipment_id);
    const snapshot = await sceneState(page);
    const material = snapshot.materials.filter(row => row.id === target.material);
    expect(material).toHaveLength(1);
    const mesh = material[0], contact = snapshot.contacts.find(row => row.equipmentId === process.equipment_id);
    if (!mesh || !contact) throw new Error('Actual mesh/contact was not rendered');
    expect(Math.hypot(...mesh.position.map((value, index) => value - (contact.position[index] ?? 0)))).toBeLessThan(0.01);
    expect(mesh.form).toBe(world.materials.find(row => row.id === target.material)?.form);
    expect(mesh.custody).toBe('process');
    expect(mesh.matrixWorld.slice(12, 15)).toEqual(mesh.position);
    captures.push({ kind: target.kind, run: world.run, process, mesh, contact });
    await page.locator('canvas').screenshot({ path: testInfo.outputPath(`T14-${target.kind}.png`) });
    const paused = await sceneState(page);
    await page.waitForTimeout(450);
    expect((await sceneState(page)).materials).toEqual(paused.materials);
    if (inspectPhases) {
      const exitMs = Math.floor((target.endMs - 1) / stepMs) * stepMs;
      while (world.run.elapsed_ms < exitMs) world = await sendOperation(request, { action: 'step' }, Math.min(48, (exitMs - world.run.elapsed_ms) / stepMs));
      const exitProcess = world.processes.find(row => row.id === target.processId);
      if (!exitProcess || exitProcess.status !== 'RUNNING') throw new Error(`Actual exit not running: ${target.kind}`);
      await expect.poll(async () => (await sceneState(page)).revision).toBe(world.run.revision);
      const exit = await sceneState(page);
      const bodies = exit.materials.filter(row => row.id === target.material);
      expect(bodies).toHaveLength(1);
      expect(bodies[0]?.phase).toBeGreaterThan(0.65);
      expect(bodies[0]?.phase).toBeLessThan(1);
      expect(bodies[0]?.form).toBe(world.materials.find(row => row.id === target.material)?.form);
      await page.locator('canvas').screenshot({ path: testInfo.outputPath(`T19-${target.kind}-exit.png`) });
      await recordJson(testInfo, `T19-${target.kind}-exit`, { run: world.run, process: exitProcess, scene: exit, camera: await cameraState(page) });
    }
    if (target.kind === 'blast_furnace') {
      const cameras = await orbitAndReturn(page, process);
      const followBefore = await cameraState(page);
      world = await sendOperation(request, { action: 'step' }, 2);
      await expect.poll(async () => (await sceneState(page)).revision).toBe(world.run.revision);
      const followAfter = await cameraState(page);
      for (let axis = 0; axis < 3; axis += 1) expect((followAfter.position[axis] ?? 0) - (followAfter.target[axis] ?? 0)).toBeCloseTo((followBefore.position[axis] ?? 0) - (followBefore.target[axis] ?? 0), 6);
      await page.getByRole('checkbox', { name: '소재 따라가기' }).uncheck();
      await recordJson(testInfo, 'T14-camera-continuity', { ...cameras, followBefore, followAfter });
    }

  }
  await recordJson(testInfo, 'T14-process-contact', captures);
});

test('pause, stale, reduced motion and server form boundary remain authoritative', async ({ page, request }, testInfo) => {
  test.setTimeout(120_000);
  let world = await resetScenario(request);
  for (let attempt = 0; attempt < 500; attempt += 1) {
    if (world.processes.some(row => row.material_id === 'MAT-ga-01' && row.equipment_id === 'BF-A' && row.status === 'RUNNING')) break;
    world = await sendOperation(request, { action: 'step' });
  }
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await focus(page, world, 'MAT-ga-01', 'BF-A');
  const paused = await sceneState(page);
  expect(paused.reduced).toBe(true);
  await page.waitForTimeout(450);
  expect((await sceneState(page)).materials).toEqual(paused.materials);
  world = await sendOperation(request, { action: 'play' });
  await expect.poll(async () => (await sceneState(page)).revision).toBeGreaterThanOrEqual(world.run.revision);
  const reduced = await sceneState(page);
  expect(reduced.elapsedMs).toBe(reduced.authoritativeElapsedMs);
  await page.route('**/api/v1/world', route => route.fulfill({ status: 200, contentType: 'application/json', body: '{}' }));
  await expect(page.getByRole('alert')).toContainText('연결 상태');
  const stale = await sceneState(page);
  await page.waitForTimeout(500);
  expect((await sceneState(page)).materials).toEqual(stale.materials);
  expect(stale.stale).toBe(true);
  await page.unroute('**/api/v1/world');
  world = await sendOperation(request, { action: 'pause' });
  for (let attempt = 0; attempt < 100; attempt += 1) {
    if (world.materials.find(row => row.id === 'MAT-ga-01')?.form === 'HOT_METAL') break;
    world = await sendOperation(request, { action: 'step' });
  }
  await expect.poll(async () => (await sceneState(page)).revision).toBe(world.run.revision);
  const boundary = await sceneState(page);
  expect(boundary.materials.find(row => row.id === 'MAT-ga-01')?.form).toBe('HOT_METAL');
  await recordJson(testInfo, 'T14-boundaries', { paused, reduced, stale, boundary });
});


test('material forms and poses share the committed world during play and run replacement', async ({ page, request }, testInfo) => {
  test.setTimeout(120_000);
  let world = await resetScenario(request);
  const worlds: World[] = [world];
  const responses: Promise<void>[] = [];
  const captureResponse = (response: Response): void => {
    if (response.url().endsWith('/api/v1/world') && response.ok()) responses.push(response.json().then(value => { worlds.push(WorldSchema.parse(value)); }));
  };
  page.on('response', captureResponse);
  for (let attempt = 0; attempt < 500; attempt += 1) {
    const furnace = world.processes.find(row => row.material_id === 'MAT-ga-01' && row.equipment_id === 'BF-A' && row.status === 'RUNNING');
    if (furnace?.end_ms !== null && furnace?.end_ms !== undefined && furnace.end_ms - world.run.elapsed_ms <= world.simulation.step_ms * 2) break;
    world = await sendOperation(request, { action: 'step' });
  }
  expect(world.materials.find(row => row.id === 'MAT-ga-01')?.form).not.toBe('HOT_METAL');
  worlds.push(world);
  await focus(page, world, 'MAT-ga-01', 'BF-A');
  const capture = await page.evaluateHandle(() => {
    const snapshots: string[] = [];
    const observer = new MutationObserver(records => {
      for (const record of records) if (record.target instanceof HTMLCanvasElement) {
        const value = record.target.dataset.sceneState;
        if (value) snapshots.push(value);
      }
    });
    observer.observe(document.body, { subtree: true, attributes: true, attributeFilter: ['data-scene-state'] });
    return { snapshots, observer };
  });
  world = await sendOperation(request, { action: 'play' });
  worlds.push(world);
  await expect.poll(async () => (await sceneState(page)).materials.find(row => row.id === 'MAT-ga-01')?.form, { timeout: 30_000 }).toBe('HOT_METAL');
  world = await sendOperation(request, { action: 'pause' });
  worlds.push(world);
  await expect.poll(async () => (await sceneState(page)).revision).toBe(world.run.revision);
  const oldRun = world.run.id;
  world = await resetScenario(request);
  worlds.push(world);
  await expect.poll(async () => (await sceneState(page)).runId).toBe(world.run.id);
  const snapshots = z.array(z.string()).parse(await capture.evaluate(value => { value.observer.disconnect(); return value.snapshots; })).map(value => sceneSchema.parse(JSON.parse(value)));
  await capture.dispose();
  page.off('response', captureResponse);
  await Promise.all(responses);
  await recordJson(testInfo, 'T19-committed-material-cohorts', { snapshots, worlds: worlds.map(value => ({ run: value.run, materials: value.materials })) });
  expect(snapshots.length).toBeGreaterThan(2);
  expect(new Set(snapshots.map(value => value.runId))).toEqual(new Set([oldRun, world.run.id]));
  expect(new Set(snapshots.flatMap(value => value.materials.filter(row => row.id === 'MAT-ga-01').map(row => row.form))).size).toBeGreaterThan(1);
  for (const snapshot of snapshots) {
    const authoritative = worlds.find(value => value.run.id === snapshot.runId && value.run.revision === snapshot.revision);
    expect(authoritative, `Observed HTTP world for ${snapshot.runId}/${snapshot.revision}`).toBeDefined();
    for (const body of snapshot.materials) {
      expect([body.worldRunId, body.worldRevision]).toEqual([snapshot.runId, snapshot.revision]);
      const material = authoritative?.materials.find(row => row.id === body.id);
      expect([body.form, body.versionId]).toEqual([material?.form, material?.current_version_id]);
    }
  }
});
