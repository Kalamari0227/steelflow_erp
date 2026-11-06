import { expect, test as browserTest, type Locator, type Page, type Request, type Response } from '@playwright/test';
import { z } from 'zod';
import { test, readWorld, resetScenario, sendOperation, recordJson, loseWebGL, captureBrowserFailures, clickOperation } from './helpers/operations';

async function keyboardActivate(page: Page, target: Locator, backwards = false): Promise<void> {
  for (let index = 0; index < 300; index += 1) {
    if (await target.evaluate(element => element === document.activeElement)) { await page.keyboard.press('Enter'); return; }
    await page.keyboard.press(backwards ? 'Shift+Tab' : 'Tab');
  }
  throw new Error(`Keyboard could not reach ${await target.getAttribute('aria-label') ?? await target.textContent()}`);
}

test('keyboard follows order material inspection shipment with no mutation and mobile has no page overflow', async ({ page, request }, testInfo) => {
  test.setTimeout(120_000);
  await resetScenario(request);
  let world = await readWorld(request);
  while (world.run.elapsed_ms < world.run.duration_ms) world = await sendOperation(request, { action: 'step' }, 48);
  const inspection = world.inspections.find(row => row.material_id === 'MAT-ga-01');
  const shipment = world.shipments.find(row => world.shipment_materials.some(member => member.shipment_id === row.id && member.material_id === 'MAT-ga-01'));
  if (!inspection || !shipment) throw new Error('Completed real run lacks GA inspection or shipment');
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/?view=2d');
  await expect(page.getByTestId('operations-table')).toBeVisible();
  const mutations: string[] = [];
  page.on('request', request => { if (request.method() === 'POST') mutations.push(request.url()); });
  await keyboardActivate(page, page.getByTestId('order-ORD-ga'));
  const table = page.getByTestId('operations-table');
  await keyboardActivate(page, table.getByRole('button', { name: '소재', exact: true }));
  await keyboardActivate(page, table.getByRole('button', { name: '소재 MAT-ga-01 상세' }));
  await expect(table.getByRole('region', { name: '소재 선택 기록' })).toBeFocused();
  await keyboardActivate(page, table.getByRole('button', { name: '검사', exact: true }), true);
  await keyboardActivate(page, table.getByRole('button', { name: `검사 ${inspection.id} 상세` }));
  await expect(table.getByRole('region', { name: '검사 선택 기록' })).toContainText(inspection.inspected_version_id);
  await keyboardActivate(page, table.getByRole('button', { name: '출하', exact: true }), true);
  await keyboardActivate(page, table.getByRole('button', { name: `출하 ${shipment.id} 상세` }));
  await expect(table.getByRole('region', { name: '출하 선택 기록' })).toContainText('배송 잔량 0 kg');
  const overflow = await page.evaluate(() => ({ viewport: window.innerWidth, width: document.documentElement.scrollWidth }));
  expect(overflow.width).toBeLessThanOrEqual(overflow.viewport);
  expect((await readWorld(request)).run).toEqual(world.run);
  expect(mutations).toEqual([]);
  await page.screenshot({ path: testInfo.outputPath('T17-mobile.png'), fullPage: true });
  await recordJson(testInfo, 'T17-keyboard', { run: world.run, material: 'MAT-ga-01', inspection, shipment, overflow, mutations, input: 'Tab / Shift+Tab / Enter only' });
});

test('real WebGL context loss automatically preserves identity in 2D and AI is disabled', async ({ page, request }, testInfo) => {
  const world = await resetScenario(request);
  await page.goto('/');
  await expect(page.getByTestId('simulation-step')).toBeEnabled();
  await page.getByTestId('order-ORD-ga').click();
  await page.getByTestId('material-MAT-ga-01').click();
  await page.locator('canvas').waitFor({ state: 'visible' });
  await expect(page.locator('canvas')).toHaveAttribute('data-scene-state', /"materials"/);
  await page.waitForTimeout(1200);
  await expect(page.getByRole('button', { name: '3D', exact: true })).toHaveAttribute('aria-pressed', 'true');
  await expect(page.locator('canvas')).toBeVisible();
  const initialCanvas = await page.locator('canvas').boundingBox();
  expect(initialCanvas).not.toBeNull();
  await page.screenshot({ path: testInfo.outputPath('T17-desktop-entry.png'), fullPage: true });
  await loseWebGL(page);
  await expect(page.getByTestId('operations-table')).toContainText('ORD-ga · MAT-ga-01');
  await expect(page.getByRole('status')).toContainText('선택한 주문과 소재는 그대로 유지');
  await expect(page.getByRole('status')).toBeFocused();
  await expect(page.getByTestId('material-inspector')).toContainText('MAT-ga-01');
  expect((await readWorld(request)).run).toEqual(world.run);
  expect(world.ai).toMatchObject({ enabled: false, available: false });
  await page.screenshot({ path: testInfo.outputPath('T17-webgl-loss.png'), fullPage: true });
  await recordJson(testInfo, 'T17-webgl-loss', { run: world.run, ai: world.ai, selection: page.url(), actualExtension: 'WEBGL_lose_context', initialCanvas });
});

test('actual WebGL2 capability denial automatically selects 2D without losing the requested material', async ({ page, request }, testInfo) => {
  const world = await resetScenario(request);
  await page.addInitScript(() => {
    const original = HTMLCanvasElement.prototype.getContext;
    HTMLCanvasElement.prototype.getContext = new Proxy(original, {
      apply(target, canvas: HTMLCanvasElement, args: readonly unknown[]) {
        if (args[0] === 'webgl2') return null;
        return Reflect.apply(target, canvas, args);
      },
    });
  });
  await page.goto('/?order_id=ORD-ga&material_id=MAT-ga-01');
  await expect(page.getByTestId('operations-table')).toBeVisible();
  await expect(page.getByRole('button', { name: '2D', exact: true })).toHaveAttribute('aria-pressed', 'true');
  await expect(page.locator('canvas')).toHaveCount(0);
  await expect(page.getByRole('status')).toContainText('선택한 주문과 소재는 그대로 유지');
  await expect(page.getByTestId('material-inspector')).toContainText('MAT-ga-01');
  expect((await readWorld(request)).run).toEqual(world.run);
  await recordJson(testInfo, 'T17-no-webgl', { injection: 'HTMLCanvasElement.getContext(webgl2) returns null', run: world.run, selectedMaterial: 'MAT-ga-01', view: '2d' });
});

browserTest('HTTP 500 and real timeout retain last snapshot then reconnect; old reply cannot roll back a command', async ({ page, request, context, baseURL }, testInfo) => {
  browserTest.setTimeout(90_000);
  if (!baseURL) throw new Error('Missing local base URL');
  const failures = captureBrowserFailures(context, baseURL);
  const injected: string[] = [];
  const injectedRequests = new Map<Request, { readonly id: number; readonly kind: 'http500' | 'timeout' }>();
  const observedNetwork: { readonly requestId: number | null; readonly kind: 'http' | 'requestfailed'; readonly message: string; readonly expected: boolean; readonly url: string; readonly atMs: number }[] = [];
  const observeResponse = (response: Response): void => {
    if (response.status() < 400) return;
    const injection = injectedRequests.get(response.request());
    observedNetwork.push({ requestId: injection?.id ?? null, kind: 'http', message: `HTTP ${response.status()}`, expected: injection?.kind === 'http500' && response.status() === 500, url: response.url(), atMs: Date.now() });
  };
  const observeFailure = (request: Request): void => {
    const injection = injectedRequests.get(request);
    const message = request.failure()?.errorText ?? 'Unknown network error';
    observedNetwork.push({ requestId: injection?.id ?? null, kind: 'requestfailed', message, expected: injection?.kind === 'timeout' && /ABORTED|TIMED_OUT/.test(message), url: request.url(), atMs: Date.now() });
  };
  context.on('response', observeResponse);
  context.on('requestfailed', observeFailure);
  try {
    const world = await resetScenario(request);
    await page.goto('/?view=2d');
    await expect(page.getByTestId('simulation-step')).toBeEnabled();
    await page.getByTestId('order-ORD-ga').click();
    const endpoint = '**/api/v1/world';
    await page.route(endpoint, async route => { injected.push('HTTP 500'); injectedRequests.set(route.request(), { id: injectedRequests.size + 1, kind: 'http500' }); await route.fulfill({ status: 500, contentType: 'application/json', body: '{"detail":"T17 injected service failure"}' }); });
    await expect(page.getByRole('alert')).toContainText('마지막 수신');
    await expect(page.getByTestId('simulation-step')).toBeDisabled();
    await expect(page.getByTestId('material-inspector')).toContainText('MAT-ga-01');
    await page.unroute(endpoint);
    await page.getByRole('button', { name: '다시 연결', exact: true }).click();
    await expect(page.getByRole('alert')).toHaveCount(0);
    await expect(page.getByTestId('simulation-step')).toBeEnabled();
    const timeoutObserved = context.waitForEvent('requestfailed', { predicate: request => injectedRequests.get(request)?.kind === 'timeout', timeout: 12000 });
    await page.route(endpoint, async route => { injected.push('timeout > 8000ms'); injectedRequests.set(route.request(), { id: injectedRequests.size + 1, kind: 'timeout' }); await timeoutObserved; });
    await expect(page.getByRole('alert')).toContainText('마지막 수신', { timeout: 12000 });
    await expect(page.getByTestId('operations-table')).toContainText('ORD-ga · MAT-ga-01');
    expect((await timeoutObserved).failure()?.errorText).toMatch(/ABORTED|TIMED_OUT/);
    await page.unroute(endpoint);
    await page.getByRole('button', { name: '다시 연결', exact: true }).click();
    await expect(page.getByRole('alert')).toHaveCount(0);
    let releaseOld: (() => void) | undefined;
    let observed: (() => void) | undefined;
    const observedRequest = new Promise<void>(resolve => { observed = resolve; });
    const oldGate = new Promise<void>(resolve => { releaseOld = resolve; });
    await page.route(endpoint, async route => { observed?.(); await oldGate; await route.fulfill({ json: world }); }, { times: 1 });
    await observedRequest;
    const commandReply = page.waitForResponse(response => response.url().endsWith('/api/v1/simulation/step') && response.request().method() === 'POST');
    await page.getByTestId('simulation-step').click();
    expect((await commandReply).ok()).toBe(true);
    const latest = await readWorld(request);
    await expect(page.getByRole('progressbar', { name: '전체 실행 진행률', exact: true })).toHaveAttribute('value', String(latest.run.elapsed_ms));
    releaseOld?.();
    await expect(page.getByTestId('current-run')).toContainText(`rev ${latest.run.revision}`);
    await page.waitForTimeout(300);
    await expect(page.getByTestId('current-run')).toContainText(`rev ${latest.run.revision}`);
    expect(latest.run.id).toBe(world.run.id);
    expect(latest.run.revision).toBeGreaterThan(world.run.revision);
    expect(failures.failures.filter(row => row.kind === 'pageerror' || row.kind === 'external')).toEqual([]);
    expect(observedNetwork.some(row => row.kind === 'http')).toBe(true);
    await expect.poll(() => observedNetwork.some(row => row.kind === 'requestfailed')).toBe(true);
    expect(observedNetwork.filter(row => !row.expected)).toEqual([]);
    const consoleErrors = failures.failures.filter(row => row.kind === 'console');
    const unexpectedConsole = consoleErrors.filter(row => !observedNetwork.some(network => network.expected && network.requestId !== null && network.url === row.url && row.atMs !== undefined && Math.abs(network.atMs - row.atMs) <= 1000 && (network.kind === 'http' ? row.message === 'Failed to load resource: the server responded with a status of 500 (Internal Server Error)' : row.message === `Failed to load resource: ${network.message}`)));
    expect(unexpectedConsole).toEqual([]);
    expect(injected).toContain('HTTP 500'); expect(injected).toContain('timeout > 8000ms');
    await recordJson(testInfo, 'T17-failures', { injected, observedFailures: failures.failures, observedNetwork, consoleErrors, unexpectedConsole, original: world.run, restored: latest.run, retainedIdentity: 'ORD-ga / MAT-ga-01', staleSnapshotTimestampVisible: true });
  } finally { await page.unrouteAll({ behavior: 'wait' }); await sendOperation(request, { action: 'pause' }); context.off('response', observeResponse); context.off('requestfailed', observeFailure); failures.dispose(); }
});

const frameSchema = z.object({ elapsedMs: z.number(), authoritativeElapsedMs: z.number(), reduced: z.boolean() });
test('reduced motion uses confirmed positions while business time continues', async ({ page, request }, testInfo) => {
  await resetScenario(request);
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await page.goto('/');
  await expect(page.getByTestId('simulation-step')).toBeEnabled();
  await clickOperation(page, 'simulation-play-pause', '/api/v1/simulation/play');
  await expect.poll(async () => (await readWorld(request)).run.elapsed_ms).toBeGreaterThan(500);
  await expect(page.locator('canvas')).toHaveAttribute('data-scene-state', /"reduced":true/);
  await expect.poll(async () => frameSchema.parse(JSON.parse(await page.locator('canvas').getAttribute('data-scene-state') ?? '{}')).authoritativeElapsedMs).toBeGreaterThan(0);
  const frame = frameSchema.parse(JSON.parse(await page.locator('canvas').getAttribute('data-scene-state') ?? '{}'));
  expect(frame.elapsedMs).toBe(frame.authoritativeElapsedMs);
  expect(frame.elapsedMs).toBeGreaterThan(0);
  const paused = await clickOperation(page, 'simulation-play-pause', '/api/v1/simulation/pause');
  await page.waitForTimeout(400);
  expect((await readWorld(request)).run.elapsed_ms).toBe(paused.run.elapsed_ms);
  await recordJson(testInfo, 'T17-reduced-motion', { frame, paused: paused.run });
});
