import { expect } from '@playwright/test';
import { z } from 'zod';
import { test, readWorld, resetScenario, sendOperation, clickOperation, stepUntil, businessState, loseWebGL, recordJson, clickSceneObject } from './helpers/operations';

test.beforeEach(async ({ request, page }) => {
  await resetScenario(request);
  await page.goto('/?workspace=production');
  await expect(page.getByTestId('simulation-step')).toBeEnabled();
});

test('transport arrival gates processing with one material location and deterministic replay', async ({ page, request }, testInfo) => {
  test.setTimeout(180_000);
  await page.getByRole('button', { name: '2D', exact: true }).click();
  const states = [];
  let sawTransit = false;
  for (let step = 0; step <= 80; step += 1) {
    const world = step === 0 ? await readWorld(request) : await sendOperation(request, { action: 'step' });
    states.push(businessState(world));
    expect(world.mass_balance.initial_kg + world.mass_balance.additions_kg).toBe(world.mass_balance.active_kg + world.mass_balance.loss_kg);
    for (const material of world.materials.filter(row => row.active)) {
      const transfers = world.transfers.filter(row => row.material_id === material.id && ['LOADING', 'IN_TRANSIT', 'UNLOADING'].includes(row.status));
      expect(transfers.length).toBeLessThanOrEqual(1);
      const active = transfers[0];
      if (!active) continue;
      sawTransit = true;
      expect(world.processes.filter(row => row.material_id === material.id && row.status === 'RUNNING')).toEqual([]);
      expect(material.location_id.length).toBeGreaterThan(0);
      if (active.status === 'IN_TRANSIT' && active.vehicle_id) expect(material.location_id).toBe(`OPS-${active.vehicle_id}-CARGO`);
      const downstream = world.processes.find(row => row.id === active.process_id);
      if (downstream) expect(downstream.status).not.toBe('RUNNING');
    }
  }
  expect(sawTransit).toBe(true);
  await sendOperation(request, { action: 'reset' });
  for (let step = 0; step <= 8; step += 1) {
    const replay = step === 0 ? await readWorld(request) : await sendOperation(request, { action: 'step' });
    expect(businessState(replay)).toEqual(states[step]);
  }
  await recordJson(testInfo, 'transport-custody-replay', { states, matchedSteps: 9 });
});

test('loaded carrier moves, freezes on pause, resumes and resets the same authoritative flow', async ({ page, request }, testInfo) => {
  test.setTimeout(180_000);
  const transit = await stepUntil(request, world => world.transfers.some(row => row.status === 'IN_TRANSIT' && row.vehicle_id !== null), 2000);
  const transfer = transit.transfers.find(row => row.status === 'IN_TRANSIT' && row.vehicle_id !== null);
  if (!transfer) throw new Error('No loaded carrier reached');
  await page.getByTestId(`material-${transfer.material_id}`).click();
  await page.getByRole('checkbox', { name: '소재 따라가기' }).check();
  const canvas = page.locator('canvas'); await expect(canvas).toBeVisible();
  if (!transfer.vehicle_id) throw new Error('Loaded transport has no vehicle');
  await clickSceneObject(page, 'vehicle', transfer.vehicle_id);
  await expect(page.getByTestId('material-inspector')).toContainText(transfer.material_id);
  await page.waitForTimeout(500);
  const before = await canvas.screenshot({ path: testInfo.outputPath('transport-before.png') });
  await clickOperation(page, 'simulation-play-pause', '/simulation/play');
  await expect.poll(async () => (await canvas.screenshot()).equals(before)).toBe(false);
  const paused = await clickOperation(page, 'simulation-play-pause', '/simulation/pause');
  await page.mouse.move(0, 0); await page.waitForTimeout(500);
  const frozen = await canvas.screenshot({ path: testInfo.outputPath('transport-paused.png') });
  await page.waitForTimeout(650);
  expect((await canvas.screenshot()).equals(frozen)).toBe(true);
  expect((await readWorld(request)).run.elapsed_ms).toBe(paused.run.elapsed_ms);
  await clickOperation(page, 'simulation-play-pause', '/simulation/play');
  await expect.poll(async () => (await readWorld(request)).run.elapsed_ms).toBeGreaterThan(paused.run.elapsed_ms);
  await clickOperation(page, 'simulation-play-pause', '/simulation/pause');
  const reset = await clickOperation(page, 'simulation-reset', '/simulation/reset');
  expect(reset.run.elapsed_ms).toBe(0); expect(reset.run.id).not.toBe(transit.run.id);
  await expect(page.getByTestId('material-inspector')).toContainText(transfer.material_id);
  await recordJson(testInfo, 'transport-motion', { transfer, paused: paused.run, reset: reset.run, pixelChange: true, pausedPixelEquality: true });
});

test('390px transport tracking survives WebGL loss and arrival navigation', async ({ page, request }, testInfo) => {
  test.setTimeout(180_000);
  const transit = await stepUntil(request, world => world.transfers.some(row => row.status === 'IN_TRANSIT'), 2000);
  const transfer = transit.transfers.find(row => row.status === 'IN_TRANSIT'); if (!transfer) throw new Error('No transport');
  await page.setViewportSize({ width: 390, height: 844 });
  await page.getByTestId(`material-${transfer.material_id}`).click();
  await loseWebGL(page);
  const record = page.getByTestId(`transfer-${transfer.id}`);
  await expect(record).toContainText(transfer.vehicle_id ?? '롤러 이송');
  await expect(record).toContainText(transfer.to_location_id);
  await record.getByRole('button', { name: '도착 공정 보기' }).click();
  await expect(page.getByTestId('material-inspector')).toContainText(transfer.material_id);
  const arrived = await stepUntil(request, world => world.transfers.find(row => row.id === transfer.id)?.status === 'ARRIVED', 100);
  await expect(record).toContainText('ARRIVED');
  const material = arrived.materials.find(row => row.id === transfer.material_id);
  expect(material?.location_id).not.toBe(transfer.vehicle_id);
  const layout = await page.evaluate(() => ({ width: innerWidth, document: document.documentElement.scrollWidth }));
  expect(layout.document).toBeLessThanOrEqual(layout.width);
  await recordJson(testInfo, 'transport-mobile', { transfer, material, layout });
  await page.screenshot({ path: testInfo.outputPath('transport-mobile.png'), fullPage: true });
});

test('reduced motion retains static transport between confirmed snapshots and changes after a step', async ({ page, request }, testInfo) => {
  test.setTimeout(180_000);
  await page.emulateMedia({ reducedMotion: 'reduce' });
  const transit = await stepUntil(request, world => world.transfers.some(row => row.status === 'IN_TRANSIT'), 2000);
  const transfer = transit.transfers.find(row => row.status === 'IN_TRANSIT'); if (!transfer) throw new Error('No transport');
  await page.getByTestId(`material-${transfer.material_id}`).click();
  await page.getByRole('checkbox', { name: '소재 따라가기' }).check();
  const canvas = page.locator('canvas'); await expect(canvas).toBeVisible();
  const frameSchema = z.object({ runId: z.string(), revision: z.number(), elapsedMs: z.number(), authoritativeElapsedMs: z.number(), reduced: z.boolean(), camera: z.object({ position: z.array(z.number()), matrixWorld: z.array(z.number()) }) });
  await expect(canvas).toHaveAttribute('data-scene-state', /.+/);
  const readFrame = async () => frameSchema.parse(JSON.parse(await canvas.getAttribute('data-scene-state') ?? '{}'));
  await expect.poll(readFrame).toMatchObject({ runId: transit.run.id, revision: transit.run.revision, elapsedMs: transit.run.elapsed_ms, authoritativeElapsedMs: transit.run.elapsed_ms, reduced: true });
  const confirmedFrame = await readFrame();
  const before = await canvas.screenshot();
  await page.waitForTimeout(650);
  expect(await readFrame()).toEqual(confirmedFrame);
  expect((await canvas.screenshot()).equals(before)).toBe(true);
  expect((await readWorld(request)).run.elapsed_ms).toBe(transit.run.elapsed_ms);
  const stepped = await clickOperation(page, 'simulation-step', '/simulation/step');
  await expect.poll(readFrame).toMatchObject({ runId: stepped.run.id, revision: stepped.run.revision, elapsedMs: stepped.run.elapsed_ms, authoritativeElapsedMs: stepped.run.elapsed_ms, reduced: true });
  await expect.poll(async () => (await canvas.screenshot()).equals(before)).toBe(false);
  expect(stepped.run.elapsed_ms).toBeGreaterThan(transit.run.elapsed_ms);
  await recordJson(testInfo, 'reduced-motion', { before: transit.run, after: stepped.run, confirmedFrame, steppedFrame: await readFrame(), staticEquality: true, steppedDifference: true });
});
