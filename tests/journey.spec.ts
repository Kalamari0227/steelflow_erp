import { expect, test as browserTest, type APIRequestContext, type Page, type Request, type Response } from '@playwright/test';
import { z } from 'zod';
import expectations from './fixtures/operations_route_expectations.json' with { type: 'json' };
import { test, readWorld, resetScenario, sendOperation, clickOperation, recordJson, clickSceneObject, stepUntil, loseWebGL, captureBrowserFailures } from './helpers/operations';

const routeSchema = z.object({ products: z.array(z.object({ id: z.string(), output: z.string(), input_units: z.number(), final_units: z.array(z.number()) })) });
const frameSchema = z.object({ runId: z.string(), elapsedMs: z.number(), authoritativeElapsedMs: z.number(), reduced: z.boolean(), materials: z.array(z.object({ id: z.string(), form: z.string(), versionId: z.string(), position: z.tuple([z.number(), z.number(), z.number()]) })) });
const cameraSchema = z.object({ target: z.tuple([z.number(), z.number(), z.number()]) });
const frame = async (page: Page) => frameSchema.parse(JSON.parse(await page.locator('canvas').getAttribute('data-scene-state') ?? '{}'));
async function finish(request: APIRequestContext) {
  let world = await readWorld(request);
  while (world.run.elapsed_ms < world.run.duration_ms) world = await sendOperation(request, { action: 'step' }, 48);
  return world;
}

test.beforeEach(async ({ page, request }) => {
  await resetScenario(request);
  await page.goto('/?workspace=journey');
  await expect(page.getByRole('heading', { name: '통합 운영', exact: true })).toBeVisible();
  await expect(page.getByTestId('simulation-step')).toBeEnabled();
});

test('all twenty routes finish exact forms in the shared ERP with no early transformation', async ({ page, request }, info) => {
  test.setTimeout(180_000);
  const initial = await readWorld(request);
  await clickOperation(page, 'simulation-play-pause', '/simulation/play');
  const early = await clickOperation(page, 'simulation-play-pause', '/simulation/pause');
  expect(early.run.elapsed_ms).toBeLessThan(1000);
  expect(early.materials.map(row => [row.id, row.form, row.current_version_id])).toEqual(initial.materials.map(row => [row.id, row.form, row.current_version_id]));
  const final = await finish(request);
  const expected = routeSchema.parse(expectations).products;
  expect(expected).toHaveLength(20);
  await page.getByRole('button', { name: '2D', exact: true }).click();
  for (const product of expected) {
    const order = final.orders.find(row => row.product_id === product.id);
    if (!order) throw new Error(`Missing order ${product.id}`);
    const materials = final.materials.filter(row => row.active && order.material_ids.includes(row.id));
    expect(materials.map(row => row.weight_kg).sort((a, b) => a - b)).toEqual(Array.from({ length: product.input_units }, () => product.final_units).flat().sort((a, b) => a - b));
    await page.getByTestId(`order-${order.id}`).click();
    for (const material of materials) {
      await page.getByTestId(`material-${material.id}`).click();
      expect(material.form).toBe(product.output);
      await expect(page.getByTestId('material-inspector')).toContainText(material.id);
      await expect(page.getByTestId('material-inspector')).toContainText(material.current_version_id);
      await expect(page.getByTestId('material-inspector')).toContainText(product.output);
      await expect(page.getByTestId('material-inspector')).toContainText('PASSED');
    }
    expect(order.status).toBe('DELIVERED');
  }
  expect((await readWorld(request)).run).toEqual(final.run);
  const reset = await clickOperation(page, 'simulation-reset', '/simulation/reset');
  expect(reset.run.id).not.toBe(initial.run.id);
  expect(reset.materials.map(({ run_id: _run, ...material }) => material)).toEqual(initial.materials.map(({ run_id: _run, ...material }) => material));
  await recordJson(info, 'journey-twenty-routes', { early: early.run, final, reset: reset.run });
});

test('eight product families expose their distinct selectable production equipment', async ({ page, request }, info) => {
  const world = await readWorld(request);
  const equipmentIds: string[] = [];
  for (const product of ['hr', 'plate', 'wire', 'cr', 'ga', 'go', 'sts-hr', 'ti-hr']) {
    const prefix = product.startsWith('sts-') || product.startsWith('ti-') ? product.toUpperCase() : `CS-${product.toUpperCase()}`;
    const process = world.processes.find(row => row.material_id === `MAT-${product}-01` && row.equipment_id.startsWith(`${prefix}-`));
    if (!process) throw new Error(`Missing distinct equipment ${product}`);
    equipmentIds.push(process.equipment_id);
    await page.getByTestId(`order-ORD-${product}`).click();
    await page.getByRole('button', { name: '2D', exact: true }).click();
    await page.getByTestId(`process-${process.id}`).click();
    await page.getByRole('button', { name: '3D', exact: true }).click();
    await clickSceneObject(page, 'equipment', process.equipment_id);
    await expect(page.getByRole('navigation', { name: '공장 탐색 경로' })).toContainText(process.equipment_id);
    await expect(page.getByTestId('material-inspector')).toContainText(`ORD-${product}`);
    await page.locator('canvas').screenshot({ path: info.outputPath(`journey-family-${product}.png`) });
  }
  expect(new Set(equipmentIds).size).toBe(8);
  expect((await readWorld(request)).run).toEqual(world.run);
  await recordJson(info, 'journey-family-equipment', equipmentIds);
});

test('real material selection moves with its carrier and freezes resumes at speed and resets', async ({ page, request }, info) => {
  test.setTimeout(120_000);
  const world = await stepUntil(request, current => current.transfers.some(row => row.material_id === 'MAT-ga-01' && row.mode === 'flatbed' && row.status === 'IN_TRANSIT' && row.phase_start_ms !== null && current.run.elapsed_ms > row.phase_start_ms), 40);
  await page.getByTestId('order-ORD-ga').click();
  await page.getByTestId('material-MAT-ga-01').click();
  await page.getByRole('checkbox', { name: '소재 따라가기' }).check();
  await expect.poll(async () => {
    const material = (await frame(page)).materials.find(row => row.id === 'MAT-ga-01');
    const camera = cameraSchema.parse(JSON.parse(await page.locator('canvas').getAttribute('data-camera') ?? '{}'));
    return material ? Math.hypot(...material.position.map((value, axis) => value - (camera.target[axis] ?? 0))) : Infinity;
  }).toBeLessThan(0.01);
  await page.getByRole('checkbox', { name: '소재 따라가기' }).uncheck();
  await page.getByTestId('material-MAT-ga-02').click();
  await clickSceneObject(page, 'material', 'MAT-ga-01');
  await expect(page.getByTestId('material-inspector')).toContainText('MAT-ga-01');
  const before = await frame(page);
  await clickOperation(page, 'simulation-play-pause', '/simulation/play');
  await expect.poll(async () => (await frame(page)).elapsedMs).toBeGreaterThan(before.elapsedMs + 300);
  const paused = await clickOperation(page, 'simulation-play-pause', '/simulation/pause');
  await expect.poll(async () => (await frame(page)).elapsedMs).toBe(paused.run.elapsed_ms);
  await page.mouse.move(0, 0);
  const image = await page.locator('canvas').screenshot({ path: info.outputPath('journey-motion-paused.png') });
  await page.waitForTimeout(600);
  expect((await page.locator('canvas').screenshot()).equals(image)).toBe(true);
  expect((await readWorld(request)).run.elapsed_ms).toBe(paused.run.elapsed_ms);
  const speedReply = page.waitForResponse(response => response.url().endsWith('/simulation/speed') && response.request().method() === 'POST');
  await page.getByRole('combobox', { name: '실행 속도', exact: true }).selectOption('4');
  expect((await speedReply).ok()).toBe(true);
  const resumed = await clickOperation(page, 'simulation-play-pause', '/simulation/play');
  expect(resumed.run.speed).toBe(4);
  await expect.poll(async () => (await readWorld(request)).run.elapsed_ms).toBeGreaterThan(paused.run.elapsed_ms + 1000);
  await clickOperation(page, 'simulation-play-pause', '/simulation/pause');
  const reset = await clickOperation(page, 'simulation-reset', '/simulation/reset');
  expect(reset.run.elapsed_ms).toBe(0);
  expect(reset.run.id).not.toBe(world.run.id);
  await recordJson(info, 'journey-motion', { before, paused: paused.run, resumed: resumed.run, reset: reset.run });
});

test('390px keyboard and WebGL loss preserve the same material and process tracking', async ({ page, request }, info) => {
  await page.setViewportSize({ width: 390, height: 844 });
  const before = await readWorld(request);
  await loseWebGL(page);
  const titanium = page.getByTestId('order-ORD-ti-sheet');
  await titanium.focus(); await page.keyboard.press('Enter');
  await expect(page.getByTestId('material-inspector')).toContainText('MAT-ti-sheet-01');
  const process = page.locator('[data-testid^="process-"]').nth(4);
  await process.focus(); await page.keyboard.press('Enter');
  await expect(page.getByTestId('operations-table')).toBeVisible();
  expect((await readWorld(request)).run).toEqual(before.run);
  const advanced = await clickOperation(page, 'simulation-step', '/simulation/step');
  expect(advanced.run.elapsed_ms).toBe(before.run.elapsed_ms + 1000);
  const layout = await page.evaluate(() => ({ viewport: innerWidth, document: document.documentElement.scrollWidth }));
  expect(layout.document).toBeLessThanOrEqual(layout.viewport);
  await page.screenshot({ path: info.outputPath('journey-mobile-fallback.png'), fullPage: true });
  await recordJson(info, 'journey-mobile', { layout, before: before.run, advanced: advanced.run });
});

browserTest('connection failure freezes the actual scene and retry restores backend authority', async ({ page, request, context, baseURL }, info) => {
  if (!baseURL) throw new Error('Missing local baseURL');
  const health = captureBrowserFailures(context, baseURL);
  const endpoint = '**/api/v1/world';
  const injected = new Set<Request>();
  const observed: { readonly url: string; readonly atMs: number }[] = [];
  const observe = (response: Response): void => { if (response.status() === 500 && injected.has(response.request())) observed.push({ url: response.url(), atMs: Date.now() }); };
  context.on('response', observe);
  let release: (() => void) | undefined;
  const gate = new Promise<void>(resolve => { release = resolve; });
  let fail = false;
  try {
    await page.getByRole('checkbox', { name: '소재 따라가기' }).uncheck();
    await page.route(endpoint, async route => { await gate; if (fail) { injected.add(route.request()); await route.fulfill({ status: 500, contentType: 'application/json', body: '{"detail":"journey injected outage"}' }); } else await route.continue(); });
    const playing = await clickOperation(page, 'simulation-play-pause', '/simulation/play');
    await page.waitForTimeout(700);
    const first = await frame(page);
    await page.waitForTimeout(500);
    expect((await frame(page)).elapsedMs).toBe(first.elapsedMs);
    expect((await readWorld(request)).run.elapsed_ms).toBeGreaterThan(playing.run.elapsed_ms);
    fail = true; release?.();
    await expect(page.getByRole('alert')).toContainText('마지막 수신');
    await expect(page.getByTestId('simulation-step')).toBeDisabled();
    const frozen = await frame(page);
    await page.waitForTimeout(500);
    expect((await frame(page)).elapsedMs).toBe(frozen.elapsedMs);
    await sendOperation(request, { action: 'pause' });
    await page.unroute(endpoint);
    await page.getByRole('button', { name: '다시 연결', exact: true }).click();
    await expect(page.getByRole('alert')).toHaveCount(0);
    await expect(page.getByTestId('simulation-step')).toBeEnabled();
    const injectedUrl = new URL('/api/v1/world', baseURL).href;
    expect(observed.length).toBeGreaterThan(0);
    const unexpected = health.failures.filter(row => !(row.url === injectedUrl && (row.kind === 'http' && row.message === 'HTTP 500' && observed.some(event => event.url === row.url) || row.kind === 'console' && row.message === 'Failed to load resource: the server responded with a status of 500 (Internal Server Error)' && observed.some(event => event.url === row.url && row.atMs !== undefined && Math.abs(event.atMs - row.atMs) <= 1000))));
    expect(unexpected).toEqual([]);
    await recordJson(info, 'journey-connection', { first, frozen, failures: health.failures, observed, unexpected });
  } finally { release?.(); await page.unrouteAll({ behavior: 'wait' }); await sendOperation(request, { action: 'pause' }); context.off('response', observe); health.dispose(); }
});

test('reduced motion stays at confirmed positions while snapshots are delayed', async ({ page, request }, info) => {
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await page.getByRole('checkbox', { name: '소재 따라가기' }).uncheck();
  let release: (() => void) | undefined;
  const gate = new Promise<void>(resolve => { release = resolve; });
  await page.route('**/api/v1/world', async route => { await gate; await route.continue(); });
  try {
    await clickOperation(page, 'simulation-play-pause', '/simulation/play');
    const first = await frame(page);
    await page.waitForTimeout(500);
    const frozen = await frame(page);
    expect(frozen.reduced).toBe(true);
    expect(frozen.elapsedMs).toBe(first.elapsedMs);
    expect(frozen.elapsedMs).toBe(frozen.authoritativeElapsedMs);
    expect((await readWorld(request)).run.elapsed_ms).toBeGreaterThan(first.elapsedMs);
    release?.(); await page.unrouteAll({ behavior: 'wait' });
    const paused = await clickOperation(page, 'simulation-play-pause', '/simulation/pause');
    await expect.poll(async () => (await frame(page)).elapsedMs).toBe(paused.run.elapsed_ms);
    expect(paused.run.elapsed_ms).toBeGreaterThan(first.elapsedMs);
    await recordJson(info, 'journey-reduced-motion', { first, frozen, paused: paused.run });
  } finally { release?.(); await page.unrouteAll({ behavior: 'wait' }); }
});
