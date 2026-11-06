import { expect } from '@playwright/test';
import { WorldSchema } from '../src/contracts';
import { test, readWorld, resetScenario, sendOperation, clickOperation, businessState, loseWebGL, recordJson, clickSceneObject } from './helpers/operations';

test.beforeEach(async ({ request, page }) => {
  await resetScenario(request);
  await page.goto('/?workspace=production');
  await expect(page.getByRole('heading', { name: '통합 운영', exact: true })).toBeVisible();
  await expect(page.getByTestId('simulation-step')).toBeEnabled();
});

test('every canonical stage exposes its actual work and returns to overview without mutation', async ({ page, request }, testInfo) => {
  const before = await readWorld(request);
  await page.getByRole('button', { name: '2D', exact: true }).click();
  const stages = page.locator('.ops-stage-strip button');
  await expect(stages).toHaveCount(before.production.stages.length);
  for (let index = 0; index < before.production.stages.length; index += 1) {
    const stage = before.production.stages[index]; if (!stage) throw new Error('Missing stage');
    await stages.nth(index).click();
    await expect(stages.nth(index)).toHaveAttribute('aria-pressed', 'true');
    await expect(page.locator('[data-testid^="process-"]')).toHaveCount(stage.process_ids.length);
    await page.getByRole('button', { name: '공장 전경', exact: true }).click();
  }
  const after = await readWorld(request);
  expect(after.run).toEqual(before.run);
  await recordJson(testInfo, 'stage-navigation', before.production.stages);
});

test('all twenty routes retain casting branches and HGI bypasses the cold rolling route', async ({ page, request }, testInfo) => {
  const world = await readWorld(request);
  expect(new Set(world.orders.map(row => row.product_id)).size).toBe(20);
  await page.getByRole('button', { name: '2D', exact: true }).click();
  for (const order of world.orders) {
    await page.getByTestId(`order-${order.id}`).click();
    const materialId = order.material_ids[0]; if (!materialId) throw new Error(`No material for ${order.id}`);
    await page.getByTestId(`material-${materialId}`).click();
    const processes = world.processes.filter(row => row.material_id === materialId);
    await expect(page.locator('[data-testid^="process-"]')).toHaveCount(processes.length);
    await expect(page.getByTestId('material-inspector')).toContainText(order.id);
    const equipment = processes.map(row => row.equipment_id);
    if (order.product_id === 'slab') expect(equipment).toContain('CAST-SLAB');
    if (order.product_id === 'bloom') expect(equipment).toContain('CAST-BLOOM');
    if (order.product_id === 'billet') expect(equipment).toContain('CAST-BILLET');
    if (order.product_id === 'hgi') { expect(equipment.some(id => id.startsWith('CS-HGI-'))).toBe(true); expect(equipment.some(id => id.startsWith('CS-CR-'))).toBe(false); }
    if (order.product_id === 'ga') expect(equipment.some(id => id.startsWith('CS-CR-'))).toBe(true);
  }
  await page.getByTestId('order-ORD-hgi').click();
  await page.locator('.ops-stage-strip').getByRole('button', { name: '냉연', exact: true }).click();
  await expect(page.getByTestId('material-inspector')).toContainText('MAT-hgi-01');
  await expect(page.getByTestId('operations-table').locator('[data-testid^="process-"]')).toHaveCount(0);
  await expect(page.getByTestId('operations-table').getByText('선택한 대상의 공정 기록이 아직 없습니다.', { exact: true })).toBeVisible();
  await page.getByTestId('order-ORD-ga').click();
  await page.locator('.ops-stage-strip').getByRole('button', { name: '냉연', exact: true }).click();
  const coldRolling = world.production.stages.find(row => row.id === 'cr');
  if (!coldRolling) throw new Error('Missing canonical cold rolling stage');
  const gaColdProcesses = world.processes.filter(row => row.material_id === 'MAT-ga-01' && coldRolling.process_ids.includes(row.id));
  expect(gaColdProcesses.length).toBeGreaterThan(0);
  await expect(page.getByTestId('operations-table').locator('[data-testid^="process-"]')).toHaveCount(gaColdProcesses.length);
  for (const process of gaColdProcesses) await expect(page.getByTestId(`process-${process.id}`)).toBeVisible();
  expect((await readWorld(request)).run).toEqual(world.run);
  await recordJson(testInfo, 'routes', world.production.batches);
});

test('HR material role follows the order and every shown version retains its actual genealogy', async ({ page, request }, testInfo) => {
  test.setTimeout(240_000);
  await page.getByRole('button', { name: '2D', exact: true }).click();
  let completed = await readWorld(request);
  while (completed.run.elapsed_ms < completed.run.duration_ms) completed = await sendOperation(request, { action: 'step' }, 48);
  const roles = [['hr', 'HR_COIL', '판매용 최종 HR'], ['cr', 'HR_COIL', '다음 공정 투입용 중간 HR'], ['cr', 'CR_COIL', '판매용 최종 CR'], ['gi', 'CR_COIL', '다음 공정 투입용 중간 CR']] as const;
  const targets = roles.map(([product, form, expectedRole]) => {
    const order = completed.orders.find(row => row.product_id === product);
    const materialId = order?.material_ids[0];
    if (!order || !materialId) throw new Error(`Missing role order ${product}`);
    const version = completed.material_versions.filter(row => row.material_id === materialId && row.form === form).sort((a, b) => a.ordinal - b.ordinal)[0];
    const event = completed.events.find(row => row.id === version?.cause_event_id);
    if (!version || !event || event.event_type !== 'MATERIAL_TRANSFORMED') throw new Error(`Missing actual creation event ${product}/${form}`);
    return { product, form, expectedRole, orderId: order.id, materialId, version, event };
  }).sort((a, b) => a.event.at_ms - b.event.at_ms);
  await recordJson(testInfo, 'genealogy-observed-targets', { run: completed.run, targets });
  let state = await resetScenario(request);
  for (const target of targets) {
    while (state.run.elapsed_ms < target.event.at_ms) state = await sendOperation(request, { action: 'step' }, Math.min(48, Math.ceil((target.event.at_ms - state.run.elapsed_ms) / 1000)));
    const material = state.materials.find(row => row.id === target.materialId);
    if (!material) throw new Error('Missing material at observed creation time');
    expect(material.form).toBe(target.form);
    expect(state.material_versions.some(row => row.id === target.version.id && row.form === target.form)).toBe(true);
    await expect(page.getByTestId('current-run')).toHaveText(`${state.run.id} · rev ${state.run.revision}`);
    await page.getByTestId(`order-${target.orderId}`).click();
    await page.getByTestId(`material-${material.id}`).click();
    await expect(page.getByTestId('material-inspector')).toContainText(target.expectedRole);
    const versions = state.material_versions.filter(row => row.material_id === material.id).sort((a, b) => a.ordinal - b.ordinal);
    for (const version of versions) await expect(page.getByTestId('material-inspector')).toContainText(version.id);
    for (let index = 1; index < versions.length; index += 1) expect(versions[index]?.parent_version_id).toBe(versions[index - 1]?.id);
    await recordJson(testInfo, `genealogy-${target.product}-${target.form}`, { target, run: state.run, material, versions });
  }
});

test('scenario changes alter work and deterministic reset replays at the same elapsed time', async ({ page, request }, testInfo) => {
  test.setTimeout(180_000);
  const results: Record<string, ReturnType<typeof businessState>> = {};
  for (const scenario of ['NORMAL', 'DELAY', 'RECOVERY'] as const) {
    await resetScenario(request, scenario);
    let state = await readWorld(request);
    for (let step = 0; step < 4; step += 1) state = await sendOperation(request, { action: 'step' }, 48);
    results[scenario] = businessState(state);
    await page.getByRole('button', { name: '2D', exact: true }).click();
    await page.getByTestId('order-ORD-ga').click();
    await expect(page.getByTestId('current-run')).toContainText(state.run.id);
    await page.screenshot({ path: testInfo.outputPath(`${scenario}-work.png`), fullPage: true });
    await sendOperation(request, { action: 'reset' });
    for (let step = 0; step < 4; step += 1) state = await sendOperation(request, { action: 'step' }, 48);
    expect(businessState(state)).toEqual(results[scenario]);
  }
  expect(results.NORMAL?.processes).not.toEqual(results.DELAY?.processes);
  expect(results.RECOVERY?.processes).not.toEqual(results.DELAY?.processes);
  await recordJson(testInfo, 'scenario-work', results);
});

test('390px process navigation pause and step retain backend authority', async ({ page, request }, testInfo) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.getByRole('button', { name: '2D', exact: true }).click();
  await page.getByTestId('order-ORD-ga').click();
  await page.locator('[data-testid^="process-"]').first().click();
  await expect(page.getByTestId('material-inspector')).toContainText('ORD-ga');
  const playing = await clickOperation(page, 'simulation-play-pause', '/simulation/play');
  await expect.poll(async () => (await readWorld(request)).run.elapsed_ms).toBeGreaterThan(playing.run.elapsed_ms);
  const paused = await clickOperation(page, 'simulation-play-pause', '/simulation/pause');
  await page.waitForTimeout(600);
  expect((await readWorld(request)).run.elapsed_ms).toBe(paused.run.elapsed_ms);
  const stepped = await clickOperation(page, 'simulation-step', '/simulation/step');
  expect(stepped.run.elapsed_ms).toBe(paused.run.elapsed_ms + 1000);
  const layout = await page.evaluate(() => ({ width: innerWidth, document: document.documentElement.scrollWidth }));
  expect(layout.document).toBeLessThanOrEqual(layout.width);
  await recordJson(testInfo, 'mobile-process', layout);
});

test('WebGL loss restores usable stage and material selection in the same run', async ({ page, request }, testInfo) => {
  const before = await readWorld(request);
  await page.getByTestId('order-ORD-hgi').click();
  await loseWebGL(page);
  await page.locator('.ops-stage-strip').getByRole('button', { name: '열연도금', exact: true }).click();
  await page.locator('[data-testid^="process-"]').first().click();
  await expect(page.getByTestId('material-inspector')).toContainText('ORD-hgi');
  expect((await readWorld(request)).run).toEqual(before.run);
  await page.screenshot({ path: testInfo.outputPath('production-webgl-fallback.png'), fullPage: true });
});

test('3D detail and overview switches retain camera interaction and remain local', async ({ page, request }, testInfo) => {
  const before = await readWorld(request);
  await expect(page.locator('canvas')).toBeVisible();
  await page.getByTestId('order-ORD-ga').click();
  for (let index = 0; index < 3; index += 1) {
    await page.getByRole('button', { name: '2D', exact: true }).click();
    await page.locator('[data-testid^="process-"]').first().click();
    await page.getByRole('button', { name: '3D', exact: true }).click();
    await expect(page.locator('canvas')).toBeVisible();
    await page.getByRole('button', { name: '공장 전경', exact: true }).click();
    await expect(page.getByTestId('material-inspector')).toContainText('ORD-ga');
  }
  expect((await readWorld(request)).run).toEqual(before.run);
  await recordJson(testInfo, 'view-switches', { run: before.run, url: page.url() });
});

test('GA EG and HGI equipment navigation selects the matching actual operation', async ({ page, request }, testInfo) => {
  const state = await readWorld(request);
  await page.getByRole('button', { name: '2D', exact: true }).click();
  for (const product of ['ga', 'eg', 'hgi']) {
    await page.getByTestId(`order-ORD-${product}`).click();
    const order = state.orders.find(row => row.product_id === product); if (!order) throw new Error('Missing coating order');
    const process = state.processes.find(row => row.material_id === order.material_ids[0] && row.equipment_id.startsWith(`CS-${product.toUpperCase()}-`));
    if (!process) throw new Error('Missing coating equipment');
    await page.getByTestId(`process-${process.id}`).click();
    await page.getByRole('button', { name: '3D', exact: true }).click();
    await clickSceneObject(page, 'equipment', process.equipment_id);
    await expect(page.getByRole('navigation', { name: '공장 탐색 경로' })).toContainText(process.equipment_id);
    await expect(page.getByTestId('material-inspector')).toContainText(order.id);
    const world = WorldSchema.parse(await (await request.get('/api/v1/world')).json());
    expect(world.run).toEqual(state.run);
    await page.getByRole('button', { name: '2D', exact: true }).click();
  }
  await page.screenshot({ path: testInfo.outputPath('coating-equipment.png'), fullPage: true });
});
