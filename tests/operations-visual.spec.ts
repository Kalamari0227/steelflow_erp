import { expect, type Page } from '@playwright/test';
import { z } from 'zod';
import { Matrix4, Vector3 } from 'three';
import { test, resetScenario, sendOperation, recordJson } from './helpers/operations';
import type { World } from '../src/contracts';

const statsSchema = z.object({ frames: z.number(), times: z.array(z.number()), dpr: z.number(), calls: z.number(), triangles: z.number(), geometries: z.number(), textures: z.number() });
async function renderStats(page: Page) {
  await expect(page.locator('canvas')).toHaveAttribute('data-render-stats', /"frames"/);
  return statsSchema.parse(JSON.parse(await page.locator('canvas').getAttribute('data-render-stats') ?? '{}'));
}
async function openScene(page: Page, world: World, stage?: string) {
  const nav = { selection: { run_id: world.run.id, order_id: 'ORD-ga', material_id: 'MAT-ga-01', ...(stage ? { stage_id: stage } : {}) }, level: stage ? 'stage' : 'overview', view: '3d', followMaterial: false, cameraByScope: {} };
  await page.goto(`/?nav=${encodeURIComponent(JSON.stringify(nav))}`);
  await expect(page.locator('canvas')).toHaveAttribute('data-scene-state', /"materials"/);
  await page.locator('canvas').scrollIntoViewIfNeeded();
}
const percentile = (values: readonly number[], percentile: number) => {
  const sorted = [...values].sort((a, b) => a - b);
  const value = sorted[Math.min(sorted.length - 1, Math.floor(sorted.length * percentile))];
  if (value === undefined) throw new Error('No actual rendered frames were captured');
  return value;
};

test('T19 actual 24 active materials render within budget and paused scene rests for 60 seconds', async ({ page, request, browserName }, testInfo) => {
  test.setTimeout(240_000);
  let world = await resetScenario(request);
  for (let step = 0; step < 350 && world.materials.filter(row => row.active).length < 24; step += 1) world = await sendOperation(request, { action: 'step' }, 16);
  expect(world.materials.filter(row => row.active)).toHaveLength(24);
  expect(world.run.elapsed_ms).toBeLessThan(world.run.duration_ms);
  expect(world.shipments.some(row => row.status !== 'DELIVERED')).toBe(true);
  await page.setViewportSize({ width: 1440, height: 1000 });
  await openScene(page, world);
  await recordJson(testInfo, 'T19-active-world', world);
  await sendOperation(request, { action: 'play' });
  await page.waitForTimeout(2500);
  const start = await renderStats(page);
  let polls = 0;
  const observe = (response: { url(): string }) => { if (response.url().endsWith('/api/v1/world')) polls += 1; };
  page.on('response', observe);
  await page.waitForTimeout(8000);
  page.off('response', observe);
  const end = await renderStats(page);
  world = await sendOperation(request, { action: 'pause' });
  const startTime = start.times.at(-1) ?? 0;
  const times = end.times.filter(value => value > startTime);
  const intervals = times.slice(1).map((time, index) => time - (times[index] ?? time));
  const result = { browserName, userAgent: await page.evaluate(() => navigator.userAgent), viewport: page.viewportSize(), activeCount: world.materials.filter(row => row.active).length, playingFrameCount: end.frames - start.frames, pollResponses: polls, medianMs: percentile(intervals, 0.5), p95Ms: percentile(intervals, 0.95), start, end, intervals };
  await recordJson(testInfo, 'T19-performance', result);
  expect(result.activeCount).toBe(24);
  expect(world.shipments.some(row => row.status !== 'DELIVERED')).toBe(true);
  expect(result.playingFrameCount).toBeGreaterThan(120);
  expect(polls).toBeGreaterThan(10);
  expect(end.dpr).toBeLessThanOrEqual(1.5);
  expect(result.medianMs).toBeLessThanOrEqual(33.4);
  expect(result.p95Ms).toBeLessThanOrEqual(66.7);
  await page.waitForTimeout(1500);
  const idleStart = await renderStats(page);
  const cdp = await page.context().newCDPSession(page);
  await cdp.send('Performance.enable');
  const memoryStart = await cdp.send('Performance.getMetrics');
  polls = 0; page.on('response', observe);
  await page.waitForTimeout(60_000);
  page.off('response', observe);
  const idleEnd = await renderStats(page);
  const memoryEnd = await cdp.send('Performance.getMetrics');
  await recordJson(testInfo, 'T19-idle-60s', { seconds: 60, idleStart, idleEnd, memoryStart, memoryEnd, polls });
  await cdp.detach();
  expect(polls).toBeGreaterThan(30);
  expect(idleEnd.frames).toBe(idleStart.frames);
  expect(idleEnd.geometries).toBe(idleStart.geometries);
  expect(idleEnd.textures).toBe(idleStart.textures);
});

test('T19 campus and functional districts fit desktop and mobile viewports', async ({ page, request }, testInfo) => {
  test.setTimeout(150_000);
  const world = await resetScenario(request);
  const captures: object[] = [];
  for (const viewport of [{ width: 1600, height: 1000 }, { width: 1440, height: 1000 }, { width: 390, height: 844 }]) {
    await page.setViewportSize(viewport);
    for (const stage of [undefined, 'ga', 'logistics', 'sources']) {
      await openScene(page, world, stage);
      const name = `T19-${viewport.width}-${stage ?? 'overview'}`;
      await page.screenshot({ path: testInfo.outputPath(`${name}-page.png`), fullPage: true });
      await page.locator('canvas').screenshot({ path: testInfo.outputPath(`${name}-scene.png`) });
      const size = await page.evaluate(() => ({ document: document.documentElement.scrollWidth, viewport: innerWidth }));
      expect(size.document).toBeLessThanOrEqual(size.viewport);
      const stats = await renderStats(page);
      expect(stats.dpr).toBeLessThanOrEqual(1.5);
      captures.push({ name, viewport, size, stats, scene: await page.locator('canvas').getAttribute('data-scene-state') });
    }
  }
  await recordJson(testInfo, 'T19-viewports', captures);
});

const bodySchema = z.object({ id: z.string(), position: z.tuple([z.number(), z.number(), z.number()]), bodyBounds: z.object({ min: z.tuple([z.number(), z.number(), z.number()]), max: z.tuple([z.number(), z.number(), z.number()]) }) });
const visualSchema = z.object({ revision: z.number(), focusStage: z.string().nullable(), materials: z.array(bodySchema) });
async function actualScene(page: Page) { return visualSchema.parse(JSON.parse(await page.locator('canvas').getAttribute('data-scene-state') ?? '{}')); }

test('T19 actual coil and split plate body bounds remain separate on carriers and in storage', async ({ page, request }, testInfo) => {
  test.setTimeout(240_000);
  let world = await resetScenario(request);
  const ids = ['SHIP-ga-01', 'SHIP-plate-01', 'SHIP-ti-sheet-01'];
  for (let batch = 0; batch < 200 && ids.some(id => world.shipments.find(row => row.id === id)?.status !== 'DELIVERED'); batch += 1) world = await sendOperation(request, { action: 'step' }, 48);
  const targets = ids.flatMap(id => ['SHIPMENT_DISPATCHED', 'SHIPMENT_DELIVERED'].map(kind => {
    const event = world.events.find(row => row.entity_id === id && row.event_type === kind);
    if (!event) throw new Error(`Missing observed ${id}/${kind}`);
    return { id, kind, time: event.at_ms + (kind === 'SHIPMENT_DISPATCHED' ? 1000 : 0) };
  })).sort((a, b) => a.time - b.time);
  await recordJson(testInfo, 'T19-body-schedule-discovery', { run: world.run, targets });
  world = await resetScenario(request);
  const records: object[] = [];
  for (const target of targets) {
    while (world.run.elapsed_ms < target.time) world = await sendOperation(request, { action: 'step' }, Math.min(48, (target.time - world.run.elapsed_ms) / 1000));
    await openScene(page, world, 'logistics');
    await expect.poll(async () => (await actualScene(page)).revision).toBe(world.run.revision);
    const memberIds = world.shipment_materials.filter(row => row.shipment_id === target.id && row.active).map(row => row.material_id);
    const scene = await actualScene(page);
    const bodies = scene.materials.filter(row => memberIds.some(id => id === row.id));
    expect(bodies).toHaveLength(2);
    const first = bodies[0], second = bodies[1];
    if (!first || !second) throw new Error('Missing actual body bounds');
    const overlaps = first.bodyBounds.min.map((min, axis) => Math.min(first.bodyBounds.max[axis] ?? 0, second.bodyBounds.max[axis] ?? 0) - Math.max(min, second.bodyBounds.min[axis] ?? 0));
    expect(overlaps.some(overlap => overlap < -0.005), `${target.id}/${target.kind}: actual rendered boxes overlap`).toBe(true);
    records.push({ target, bodies, overlaps, worldMaterials: world.materials.filter(row => memberIds.some(id => id === row.id)) });
    await page.locator('canvas').screenshot({ path: testInfo.outputPath(`T19-bounds-${target.id}-${target.kind}.png`) });
  }
  await recordJson(testInfo, 'T19-actual-body-bounds', records);
});

test('T19 follow changes detailed district with the same actual material', async ({ page, request }, testInfo) => {
  test.setTimeout(180_000);
  let world = await resetScenario(request);
  await openScene(page, world, 'hr');
  await page.getByRole('checkbox', { name: '소재 따라가기' }).check();
  await expect.poll(async () => (await actualScene(page)).focusStage).toBe('sources');
  const source = await actualScene(page);
  for (let step = 0; step < 1000 && !world.processes.some(row => row.material_id === 'MAT-ga-01' && row.status === 'RUNNING'); step += 1) world = await sendOperation(request, { action: 'step' });
  await expect.poll(async () => (await actualScene(page)).revision).toBe(world.run.revision);
  const processing = await actualScene(page);
  expect(processing.focusStage).toBe('carbon-upstream');
  await page.locator('canvas').screenshot({ path: testInfo.outputPath('T19-follow-source-to-production.png') });
  await recordJson(testInfo, 'T19-follow-scope', { source, processing, world });
});

test('T19 actual material hover highlights without changing selection or world', async ({ page, request }, testInfo) => {
  const world = await resetScenario(request);
  await openScene(page, world, 'sources');
  const url = page.url();
  const targets = z.array(z.object({ kind: z.string(), id: z.string(), world: z.tuple([z.number(), z.number(), z.number()]) })).parse(JSON.parse(await page.locator('canvas').getAttribute('data-pick-targets') ?? '[]'));
  const target = targets.find(row => row.kind === 'material' && row.id === 'MAT-ga-02');
  if (!target) throw new Error('Missing native second material hover target');
  const canvas = page.locator('canvas');
  const bounds = await canvas.boundingBox();
  if (!bounds) throw new Error('Missing current canvas bounds');
  const camera = z.object({ camera: z.object({ projectionMatrix: z.array(z.number()).length(16), matrixWorld: z.array(z.number()).length(16) }) }).parse(JSON.parse(await canvas.getAttribute('data-scene-state') ?? '{}')).camera;
  const projected = new Vector3(...target.world).applyMatrix4(new Matrix4().fromArray(camera.matrixWorld).invert()).applyMatrix4(new Matrix4().fromArray(camera.projectionMatrix));
  expect(Math.abs(projected.x)).toBeLessThanOrEqual(1);
  expect(Math.abs(projected.y)).toBeLessThanOrEqual(1);
  const pointer = { x: bounds.x + (projected.x + 1) * bounds.width / 2, y: bounds.y + (1 - projected.y) * bounds.height / 2 };
  await page.mouse.move(pointer.x, pointer.y);
  await expect(page.locator('canvas')).toHaveAttribute('data-hover-target', 'material:MAT-ga-02');
  await expect(page.locator('canvas')).toHaveCSS('cursor', 'pointer');
  await page.locator('canvas').screenshot({ path: testInfo.outputPath('T19-native-material-hover.png') });
  expect(page.url()).toBe(url);
  expect((await actualScene(page)).revision).toBe(world.run.revision);
  await page.mouse.move(0, 0);
  await expect(page.locator('canvas')).not.toHaveAttribute('data-hover-target');
  expect(page.url()).toBe(url);
  await recordJson(testInfo, 'T19-hover-preserves-state', { runId: world.run.id, revision: world.run.revision, beforeUrl: url, afterUrl: page.url(), target, bounds, pointer });
});

test('T19 completed material keeps operations reachable and all transport history keyboard accessible', async ({ page, request }, testInfo) => {
  test.setTimeout(180_000);
  let world = await resetScenario(request);
  for (let batch = 0; batch < 100 && world.shipments.some(row => row.status !== 'DELIVERED'); batch += 1) world = await sendOperation(request, { action: 'step' }, 48);
  expect(world.shipments.every(row => row.status === 'DELIVERED')).toBe(true);
  const expected = world.transfers.filter(row => row.material_id === 'MAT-ga-01').length;
  expect(expected).toBeGreaterThan(10);
  for (const viewport of [{ width: 1440, height: 1000 }, { width: 390, height: 844 }]) {
    await page.setViewportSize(viewport);
    await openScene(page, world);
    const inspector = page.getByTestId('material-inspector');
    await expect(inspector.getByRole('heading', { name: 'MAT-ga-01', exact: true })).toBeVisible();
    const history = page.getByRole('region', { name: '선택 소재 운송', exact: true });
    await expect(history.getByTestId(/^transfer-/)).toHaveCount(expected);
    const height = await page.evaluate(() => document.documentElement.scrollHeight);
    expect(height).toBeLessThan(viewport.width > 1000 ? 3200 : 6000);
    await history.focus();
    await page.keyboard.press('End');
    await expect.poll(async () => history.evaluate(element => element.scrollHeight - element.clientHeight - element.scrollTop)).toBeLessThan(2);
    await history.getByTestId(/^transfer-/).last().getByRole('button', { name: '도착 공정 보기' }).focus();
    await expect(history.getByTestId(/^transfer-/).last().getByRole('button', { name: '도착 공정 보기' })).toBeFocused();
    expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(viewport.width);
    await page.screenshot({ path: testInfo.outputPath(`T19-completed-inspector-${viewport.width}.png`), fullPage: true });
    await recordJson(testInfo, `T19-completed-inspector-${viewport.width}`, { viewport, height, expected, run: world.run, history: await history.evaluate(element => ({ clientHeight: element.clientHeight, scrollHeight: element.scrollHeight, scrollTop: element.scrollTop })) });
  }
});
