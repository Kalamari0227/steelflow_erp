import { test as isolatedTest, expect, type Request } from '@playwright/test';
import { MaterialViewSchema } from '../src/contracts';
import { test, readWorld, resetScenario, sendOperation, clickOperation, businessState, loseWebGL, recordJson, clickSceneObject, captureBrowserFailures } from './helpers/operations';

test.beforeEach(async ({ request, page }) => {
  await resetScenario(request);
  await page.goto('/');
  await expect(page.getByTestId('simulation-step')).toBeEnabled();
});

test('3D factory renders and orbit and zoom respond without changing selected material', async ({ page }, testInfo) => {
  await page.getByTestId('order-ORD-ga').click();
  const canvas = page.locator('canvas');
  await expect(canvas).toBeVisible();
  await clickSceneObject(page, 'material', 'MAT-ga-01');
  await expect(page.getByTestId('material-inspector')).toContainText('MAT-ga-01');
  const before = await canvas.screenshot();
  const bounds = await canvas.boundingBox();
  if (!bounds) throw new Error('Canvas has no rendered bounds');
  await page.mouse.move(bounds.x + bounds.width * .7, bounds.y + bounds.height * .5);
  await page.mouse.down();
  await page.mouse.move(bounds.x + bounds.width * .5, bounds.y + bounds.height * .65, { steps: 12 });
  await page.mouse.up();
  await page.mouse.wheel(0, -250);
  await expect.poll(async () => (await canvas.screenshot()).equals(before)).toBe(false);
  await expect(page.getByTestId('material-inspector')).toContainText('ORD-ga');
  await page.screenshot({ path: testInfo.outputPath('orbit-zoom.png'), fullPage: true });
});

test('search finds the actual customer and empty search is explained', async ({ page, request }, testInfo) => {
  const world = await readWorld(request);
  const customer = world.customers[0];
  if (!customer) throw new Error('Fixture has no customer');
  const search = page.getByRole('textbox', { name: '주문 검색' });
  await search.fill(customer.name);
  await expect(page.getByRole('complementary', { name: '주문 탐색' })).toContainText(customer.name);
  await search.fill('nonexistent-order-98765');
  await expect(page.getByRole('complementary', { name: '주문 탐색' }).getByRole('status')).toContainText('검색 결과가 없습니다');
  await page.screenshot({ path: testInfo.outputPath('search-empty.png'), fullPage: true });
  await search.clear();
  await expect(page.getByTestId('order-ORD-ga')).toBeVisible();
});

test('accessible material selection exposes exact order lot location and shipment relationships', async ({ page, request }, testInfo) => {
  await page.getByRole('button', { name: '2D', exact: true }).click();
  await page.getByTestId('order-ORD-ga').click();
  await page.getByTestId('material-MAT-ga-01').click();
  const response = await request.get('/api/v1/materials/MAT-ga-01');
  expect(response.ok()).toBe(true);
  const detail = MaterialViewSchema.parse(await response.json());
  const inspector = page.getByTestId('material-inspector');
  for (const value of [detail.material.id, detail.order.id, detail.lot.id, detail.work_order.id]) await expect(inspector).toContainText(value);
  const world = await readWorld(request);
  await expect(inspector).toContainText(world.locations.find(row => row.id === detail.material.location_id)?.name ?? detail.material.location_id);
  expect((await request.get('/api/v1/coils/MAT-ga-01')).status()).toBe(404);
  await recordJson(testInfo, 'material-relationships', detail);
});

test('three scenarios preserve baseline and due dates and reset replays actual business state', async ({ request }, testInfo) => {
  test.setTimeout(180_000);
  const results: Record<string, ReturnType<typeof businessState>> = {};
  const dues: string[][] = [];
  for (const scenario of ['NORMAL', 'DELAY', 'RECOVERY'] as const) {
    const baseline = await resetScenario(request, scenario);
    dues.push(baseline.orders.map(order => order.due_at));
    let advanced = baseline;
    for (let i = 0; i < 4; i += 1) advanced = await sendOperation(request, { action: 'step' }, 48);
    results[scenario] = businessState(advanced);
    const reset = await sendOperation(request, { action: 'reset' });
    expect(reset.run.id).not.toBe(baseline.run.id);
    expect(businessState(reset)).toEqual(businessState(baseline));
    for (let i = 0; i < 4; i += 1) advanced = await sendOperation(request, { action: 'step' }, 48);
    expect(businessState(advanced)).toEqual(results[scenario]);
  }
  expect(dues[1]).toEqual(dues[0]); expect(dues[2]).toEqual(dues[0]);
  expect(results.NORMAL?.processes).not.toEqual(results.DELAY?.processes);
  expect(results.RECOVERY?.processes).not.toEqual(results.DELAY?.processes);
  await recordJson(testInfo, 'deterministic-scenarios', results);
});

test('play speed and pause are backend owned and continue without a page', async ({ page, request, context }, testInfo) => {
  await page.getByRole('combobox', { name: '실행 속도' }).selectOption('4');
  const playing = await clickOperation(page, 'simulation-play-pause', '/simulation/play');
  expect(playing.run.playing).toBe(true); expect(playing.run.speed).toBe(4);
  await expect.poll(async () => (await readWorld(request)).run.elapsed_ms).toBeGreaterThan(playing.run.elapsed_ms);
  await page.close();
  const closedTime = (await readWorld(request)).run.elapsed_ms;
  await expect.poll(async () => (await readWorld(request)).run.elapsed_ms).toBeGreaterThan(closedTime);
  const reopened = await context.newPage(); await reopened.goto('/');
  await expect(reopened.getByTestId('simulation-play-pause')).toHaveText('일시 정지');
  const paused = await clickOperation(reopened, 'simulation-play-pause', '/simulation/pause');
  await reopened.waitForTimeout(600);
  expect((await readWorld(request)).run.elapsed_ms).toBe(paused.run.elapsed_ms);
  await recordJson(testInfo, 'backend-clock', { playing: playing.run, paused: paused.run });
});

test('390px 2D selection remains navigable without horizontal document overflow', async ({ page }, testInfo) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.getByRole('button', { name: '2D', exact: true }).click();
  await page.getByTestId('order-ORD-ga').click();
  await page.getByTestId('material-MAT-ga-01').click();
  await expect(page.getByTestId('material-inspector')).toContainText('MAT-ga-01');
  const layout = await page.evaluate(() => ({ document: document.documentElement.scrollWidth, viewport: innerWidth }));
  expect(layout.document).toBeLessThanOrEqual(layout.viewport);
  await recordJson(testInfo, 'mobile-layout', layout);
  await page.screenshot({ path: testInfo.outputPath('mobile.png'), fullPage: true });
});

isolatedTest('backend unavailable initial state is explicit and retry restores operations', async ({ page, request, context, baseURL }, testInfo) => {
  if (!baseURL) throw new Error('Missing local baseURL');
  await resetScenario(request);
  const health = captureBrowserFailures(context, baseURL);
  const injected = new Set<Request>();
  const observed: { readonly url: string; readonly message: string; readonly atMs: number }[] = [];
  const observe = (item: Request): void => { if (injected.has(item)) observed.push({ url: item.url(), message: item.failure()?.errorText ?? '', atMs: Date.now() }); };
  context.on('requestfailed', observe);
  try {
  await page.route('**/api/v1/world', async route => { injected.add(route.request()); await route.abort('connectionrefused'); });
  await page.goto('/');
  await expect(page.getByRole('heading', { name: '운영 서버에 연결할 수 없습니다' })).toBeVisible();
  await page.unroute('**/api/v1/world');
  await page.getByRole('button', { name: '다시 연결' }).click();
  await expect(page.getByTestId('operations-workspace')).toBeVisible();
  expect(observed.length).toBeGreaterThan(0);
  const unexpected = health.failures.filter(row => !observed.some(network => row.url === network.url && (row.kind === 'requestfailed' && row.message === network.message || row.kind === 'console' && row.message === `Failed to load resource: ${network.message}` && row.atMs !== undefined && Math.abs(row.atMs - network.atMs) <= 1000)));
  expect(unexpected).toEqual([]);
  await recordJson(testInfo, 'intentional-offline-recovery', { failures: health.failures, observed, unexpected });
  } finally { await page.unrouteAll({ behavior: 'wait' }); context.off('requestfailed', observe); health.dispose(); }
});

test('disabled AI needs no provider and recovery remains a local operational scenario', async ({ page, request }, testInfo) => {
  const pending = page.waitForResponse(response => response.url().endsWith('/scenarios/RECOVERY/activate'));
  await page.getByRole('combobox', { name: '시나리오', exact: true }).selectOption('RECOVERY');
  expect((await pending).ok()).toBe(true);
  const world = await readWorld(request);
  expect(world.ai.enabled).toBe(false); expect(world.ai.available).toBe(false);
  expect(world.run.scenario_id).toBe('RECOVERY');
  await expect(page.getByText('AI 미사용 · 핵심 운영 독립 실행')).toBeVisible();
  await page.getByTestId('order-ORD-ga').click();
  await expect(page.getByTestId('material-inspector')).toContainText('ORD-ga');
  await recordJson(testInfo, 'ai-off-recovery', { run: world.run, ai: world.ai });
});

test('WebGL context loss preserves selection and common controls', async ({ page }, testInfo) => {
  await page.getByTestId('order-ORD-ga').click();
  await loseWebGL(page);
  await expect(page.getByTestId('material-inspector')).toContainText('ORD-ga');
  const advanced = await clickOperation(page, 'simulation-step', '/simulation/step');
  expect(advanced.run.elapsed_ms).toBeGreaterThan(0);
  await page.screenshot({ path: testInfo.outputPath('webgl-fallback.png'), fullPage: true });
});

test('operator recording follows order through delay recovery playback events and reset', async ({ page, request }, testInfo) => {
  await page.getByTestId('order-ORD-ga').click();
  await expect(page.locator('canvas')).toBeVisible();
  for (const scenario of ['DELAY', 'RECOVERY']) {
    const pending = page.waitForResponse(response => response.url().endsWith(`/scenarios/${scenario}/activate`));
    await page.getByRole('combobox', { name: '시나리오', exact: true }).selectOption(scenario);
    expect((await pending).ok()).toBe(true);
    await page.getByRole('button', { name: '2D', exact: true }).click();
    await expect(page.getByTestId('material-inspector')).toContainText('ORD-ga');
    await page.screenshot({ path: testInfo.outputPath(`demo-${scenario}.png`), fullPage: true });
  }
  await clickOperation(page, 'simulation-play-pause', '/simulation/play');
  await expect.poll(async () => (await readWorld(request)).run.elapsed_ms).toBeGreaterThan(0);
  await clickOperation(page, 'simulation-play-pause', '/simulation/pause');
  await page.getByRole('heading', { name: '현재 실행 이벤트' }).scrollIntoViewIfNeeded();
  await page.getByRole('button', { name: '실행 이력 불러오기' }).click();
  await expect(page.getByRole('combobox', { name: '보관 실행 선택' })).toBeVisible();
  const reset = await clickOperation(page, 'simulation-reset', '/simulation/reset');
  expect(reset.run.elapsed_ms).toBe(0);
  const video = page.video(); if (!video) throw new Error('Video not enabled');
  await page.close(); await video.saveAs(testInfo.outputPath('operator-demo.webm'));
});
