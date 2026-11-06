import { expect, test as browserTest, type APIRequestContext, type Page, type Request } from '@playwright/test';
import { test, captureBrowserFailures, clickOperation, readWorld, recordJson, resetScenario, sendOperation } from './helpers/operations';
import { commandWorld } from './helpers/commandReply';
import type { ScenarioId, World } from '../src/contracts';

async function caption(page: Page, text: string) {
  await page.evaluate(message => {
    const note = document.getElementById('t20-recording-note') ?? document.createElement('div');
    note.id = 't20-recording-note';
    note.textContent = message;
    note.style.cssText = 'position:fixed;bottom:12px;left:50%;transform:translateX(-50%);z-index:9999;padding:10px 16px;background:#12252eee;color:white;border-radius:8px;font:14px sans-serif;pointer-events:none;max-width:80vw;text-align:center';
    document.body.append(note);
  }, text);
}

async function scenarioViaUI(page: Page, scenario: ScenarioId): Promise<World> {
  await page.getByTestId('simulation-scenario').scrollIntoViewIfNeeded();
  const response = page.waitForResponse(row => row.request().method() === 'POST' && row.url().endsWith(`/scenarios/${scenario}/activate`));
  await page.getByTestId('simulation-scenario').selectOption(scenario);
  const result = await response;
  expect(result.ok()).toBe(true);
  return commandWorld(await result.json());
}

async function advanceTo(request: APIRequestContext, predicate: (world: World) => boolean): Promise<World> {
  let world = await readWorld(request);
  while (!predicate(world) && world.run.elapsed_ms < world.run.duration_ms) {
    world = await sendOperation(request, { action: 'step' }, 48);
  }
  expect(predicate(world)).toBe(true);
  return world;
}

const metric = (page: Page, name: string) => page.locator('.ops-fulfillment > div').filter({ has: page.getByText(name, { exact: true }) });

test('T20 GA continuous 4x manufacturing to two deliveries, then truthful delay and recovery demo', async ({ page, request }, testInfo) => {
  test.setTimeout(420_000);
  const initial = await resetScenario(request);
  expect(initial.orders).toHaveLength(20);
  expect(initial.materials.filter(row => row.active)).toHaveLength(22);
  expect(initial.ai.enabled).toBe(false);
  const health = await request.get('/health');
  expect(health.ok()).toBe(true);
  const mutations: { path: string; body: unknown }[] = [];
  page.on('request', row => { if (row.method() === 'POST') mutations.push({ path: new URL(row.url()).pathname, body: row.postDataJSON() }); });
  await page.goto('/');
  await expect(page.getByTestId('simulation-step')).toBeEnabled();
  await page.getByTestId('order-ORD-ga').click();
  await page.getByTestId('material-MAT-ga-01').click();
  await expect(page.getByTestId('material-inspector')).toContainText('LOT-ga-01');
  await page.getByRole('button', { name: '제선·제강', exact: true }).click();
  await page.getByRole('checkbox', { name: '소재 따라가기' }).check();
  const speedReply = page.waitForResponse(row => row.request().method() === 'POST' && row.url().endsWith('/simulation/speed'));
  await page.getByRole('combobox', { name: '실행 속도', exact: true }).selectOption('4');
  expect((await speedReply).ok()).toBe(true);
  await caption(page, '합성 데이터 · AI 미사용 · 실제 UI 4× 연속 재생 · 1000 시뮬레이션 ms = 제조 1분');
  await page.getByTestId('operations-scene').scrollIntoViewIfNeeded();
  await page.screenshot({ path: testInfo.outputPath('T20-normal-initial.png'), fullPage: true });
  const startedAt = Date.now();
  const playing = await clickOperation(page, 'simulation-play-pause', '/api/v1/simulation/play');
  expect(playing.run.speed).toBe(4);
  await page.getByTestId('operations-scene').scrollIntoViewIfNeeded();
  let partial: World | undefined;
  let final = playing;
  await expect.poll(async () => {
    final = await readWorld(request);
    expect(final.run.id).toBe(initial.run.id);
    const ga = final.orders.find(row => row.id === 'ORD-ga');
    if (!partial && ga?.status === 'PARTIALLY_DELIVERED') partial = final;
    return final.run.elapsed_ms === final.run.duration_ms;
  }, { timeout: 300_000, intervals: [500] }).toBe(true);
  const continuousWallMs = Date.now() - startedAt;
  expect(partial?.orders.find(row => row.id === 'ORD-ga')).toMatchObject({ delivered_kg: 40200, remaining_delivery_kg: 20100 });
  expect(final.orders.find(row => row.id === 'ORD-ga')).toMatchObject({ delivered_kg: 60300, remaining_delivery_kg: 0, status: 'DELIVERED' });
  expect(final.shipments.filter(row => row.order_id === 'ORD-ga').every(row => row.status === 'DELIVERED')).toBe(true);
  expect(mutations.filter(row => /simulation\/(step|reset)|scenarios\//.test(row.path))).toEqual([]);
  await expect(page.getByTestId('simulation-play-pause')).toHaveText('실행 완료');
  await expect(page.getByTestId('material-inspector')).toContainText('MAT-ga-01');
  await expect(metric(page, '배송 완료')).toContainText('60,300');
  await caption(page, 'GA 실제 배송 완료 · 1차 40,200 kg + 2차 20,100 kg · 같은 run과 소재 ID 유지');
  await page.locator('.ops-shipment-list').getByRole('button', { name: /SHIP-ga-01/ }).click();
  await expect(page.locator('.ops-shipment-detail')).toContainText('MAT-ga-01');
  await expect(page.locator('.ops-shipment-detail')).toContainText('MAT-ga-02');
  await page.screenshot({ path: testInfo.outputPath('T20-GA-complete.png'), fullPage: true });
  await recordJson(testInfo, 'T20-continuous-normal', { health: await health.json(), initialRun: initial.run, playingRun: playing.run, finalRun: final.run, continuousWallMs, mutations, partialOrder: partial?.orders.find(row => row.id === 'ORD-ga'), finalOrder: final.orders.find(row => row.id === 'ORD-ga'), shipments: final.shipments.filter(row => row.order_id === 'ORD-ga'), events: final.events.filter(row => row.order_id === 'ORD-ga'), ai: final.ai, massBalance: final.mass_balance });

  const delayInitial = await scenarioViaUI(page, 'DELAY');
  expect(delayInitial.run.id).not.toBe(initial.run.id);
  await caption(page, 'DELAY 새 실행 · 비교 장면은 서버 Step API로 가속 · HSM-A 실제 중단/대기');
  const delay = await advanceTo(request, world => world.events.some(row => row.event_type === 'PROCESS_BLOCKED' && row.reason === 'resource_unavailable'));
  await expect(page.getByRole('progressbar', { name: '전체 실행 진행률', exact: true })).toHaveAttribute('value', String(delay.run.elapsed_ms));
  await page.getByTestId('recovery-panel').scrollIntoViewIfNeeded();
  await expect(page.getByTestId('recovery-recommendation')).toHaveAttribute('data-recommendation', 'REVIEW_BENEFIT');
  await expect(page.getByTestId('recovery-recommendation')).toContainText('주문별 이득과 손실 검토 필요');
  await page.screenshot({ path: testInfo.outputPath('T20-DELAY.png'), fullPage: true });

  const recoveryInitial = await scenarioViaUI(page, 'RECOVERY');
  expect(recoveryInitial.run.id).not.toBe(delay.run.id);
  await caption(page, 'RECOVERY 새 실행 · 서버 Step API 가속 · HSM-B 우회: STS·Ti 후판 단축, GA 배송 개선 없음');
  const recovery = await advanceTo(request, world => world.events.some(row => row.event_type === 'RECOVERY_ROUTED'));
  expect(recovery.events.some(row => row.event_type === 'RECOVERY_ROUTED' && row.material_id === 'MAT-ga-01')).toBe(true);
  expect(recovery.recovery?.recommendation).toBe('REVIEW_BENEFIT');
  expect(recovery.recovery?.orders.find(row => row.order_id === 'ORD-ga')?.improvement_ms).toBe(0);
  expect(recovery.recovery?.orders.find(row => row.order_id === 'ORD-sts-plate')?.improvement_ms).toBe(14800);
  expect(recovery.recovery?.orders.find(row => row.order_id === 'ORD-ti-plate')?.improvement_ms).toBe(10200);
  await page.getByTestId('order-ORD-plate').click();
  await page.getByTestId('recovery-panel').scrollIntoViewIfNeeded();
  await expect(page.getByTestId('comparison-ORD-plate')).toHaveAttribute('data-improvement-ms', '0');
  await expect(page.getByTestId('comparison-ORD-plate')).toContainText('배송 개선 없음');
  await page.screenshot({ path: testInfo.outputPath('T20-RECOVERY.png'), fullPage: true });
  await recordJson(testInfo, 'T20-comparison', { delayInitial: delayInitial.run, delayRun: delay.run, delayEvents: delay.events.filter(row => row.event_type === 'RESOURCE_DOWN' || row.event_type === 'PROCESS_BLOCKED'), recoveryInitial: recoveryInitial.run, recoveryRun: recovery.run, recoveryEvents: recovery.events.filter(row => row.event_type === 'RECOVERY_ROUTED'), comparison: recovery.recovery });
  const split = await advanceTo(request, world => world.materials.some(row => row.id === 'MAT-plate-01:A'));
  await page.getByTestId('material-MAT-plate-01').click();
  await expect(page.getByTestId('material-inspector')).toContainText('소비된 부모');
  await page.getByTestId('material-inspector').getByRole('button', { name: 'MAT-plate-01:A', exact: true }).click();
  await expect(page.getByTestId('material-inspector')).toContainText('MAT-plate-01:A');
  await recordJson(testInfo, 'T20-plate-lineage', { run: split.run, materials: split.materials.filter(row => row.id.startsWith('MAT-plate-01')), lineage: split.lineage_edges.filter(row => row.parent_material_id === 'MAT-plate-01') });
});

browserTest('T20 API outage preserves the last GA snapshot in 2D and reconnects with AI off', async ({ page, context, request, baseURL }, testInfo) => {
  browserTest.setTimeout(60_000);
  if (!baseURL) throw new Error('Local preview base URL is required');
  const failures = captureBrowserFailures(context, baseURL);
  const injectedRequests = new Set<Request>();
  const observed: { url: string; error: string | null; expected: boolean }[] = [];
  const failed = (row: Request) => observed.push({ url: row.url(), error: row.failure()?.errorText ?? null, expected: injectedRequests.has(row) });
  context.on('requestfailed', failed);
  try {
    const initial = await resetScenario(request);
    await page.goto('/?order_id=ORD-ga&material_id=MAT-ga-01');
    await expect(page.getByTestId('simulation-step')).toBeEnabled();
    await caption(page, '장애 주입 시연 · 조회 요청만 차단 · 실제 서버와 기존 데모는 유지 · AI 미사용');
    await page.route('**/api/v1/world', async route => { injectedRequests.add(route.request()); await route.abort('failed'); });
    await expect(page.getByRole('alert')).toContainText('마지막 수신');
    await expect(page.getByTestId('simulation-step')).toBeDisabled();
    await page.getByRole('button', { name: '2D', exact: true }).click();
    await expect(page.getByTestId('operations-table')).toContainText('ORD-ga · MAT-ga-01');
    await expect(page.getByTestId('material-inspector')).toContainText('MAT-ga-01');
    await page.screenshot({ path: testInfo.outputPath('T20-fallback-last-state.png'), fullPage: true });
    await page.waitForTimeout(2000);
    await page.unroute('**/api/v1/world');
    await page.getByRole('button', { name: '다시 연결', exact: true }).click();
    await expect(page.getByRole('alert')).toHaveCount(0);
    await expect(page.getByTestId('simulation-step')).toBeEnabled();
    const restored = await readWorld(request);
    expect(restored.run).toEqual(initial.run);
    expect(restored.ai.enabled).toBe(false);
    await expect(page.getByTestId('material-inspector')).toContainText('MAT-ga-01');
    await caption(page, '연결 복구 완료 · 같은 실행/주문/소재 · 2D 유지 · AI 미사용');
    await page.screenshot({ path: testInfo.outputPath('T20-fallback-restored.png'), fullPage: true });
    await page.waitForTimeout(2000);
    expect(observed.length).toBeGreaterThan(0);
    expect(observed.filter(row => !row.expected || row.error !== 'net::ERR_FAILED')).toEqual([]);
    const unexpected = failures.failures.filter(row => {
      if (row.kind === 'requestfailed') return !observed.some(item => item.expected && item.url === row.url && item.error === row.message);
      if (row.kind === 'console') return !(row.message === 'Failed to load resource: net::ERR_FAILED' && observed.some(item => item.expected && item.url === row.url));
      return true;
    });
    expect(unexpected).toEqual([]);
    await recordJson(testInfo, 'T20-fallback', { initialRun: initial.run, restoredRun: restored.run, selectedOrder: 'ORD-ga', selectedMaterial: 'MAT-ga-01', view: '2d', ai: restored.ai, injectedRequestCount: injectedRequests.size, observed, failures: failures.failures, unexpected });
  } finally {
    await page.unrouteAll({ behavior: 'wait' });
    context.off('requestfailed', failed);
    failures.dispose();
  }
});
