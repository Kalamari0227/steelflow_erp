import { expect, type Page, type APIRequestContext } from '@playwright/test';
import { z } from 'zod';
import { WorldSchema } from '../src/contracts';
import { test, readWorld, resetScenario, sendOperation, stepUntil, recordJson, clickOperation } from './helpers/operations';
import { transferPose } from '../src/operations/scene/transferPose';
import { distance } from '../src/operations/scene/layout';
import { Matrix4, Vector3 } from 'three';

const sceneSchema = z.object({ vehicles: z.array(z.object({ id: z.string(), position: z.tuple([z.number(), z.number(), z.number()]), matrixWorld: z.array(z.number()) })), runId: z.string(), revision: z.number(), elapsedMs: z.number(), materials: z.array(z.object({ id: z.string(), position: z.tuple([z.number(), z.number(), z.number()]), custody: z.string() })), stale: z.boolean() });
async function scene(page: Page) {
  await expect(page.locator('canvas')).toHaveAttribute('data-scene-state', /"materials"/);
  const raw = await page.locator('canvas').getAttribute('data-scene-state');
  if (!raw) throw new Error('Real scene diagnostics missing');
  return sceneSchema.parse(JSON.parse(raw));
}

async function focusMaterial(page: Page) {
  await page.getByRole('button', { name: '2D', exact: true }).click();
  await page.locator('[data-testid^="process-"]').last().click();
  await page.getByRole('button', { name: '3D', exact: true }).click();
  await page.getByRole('checkbox', { name: '소재 따라가기' }).check();
  await page.locator('canvas').scrollIntoViewIfNeeded();
  await expect.poll(async () => {
    const raw = await page.locator('canvas').getAttribute('data-camera');
    return raw ? z.object({ zoom: z.number() }).parse(JSON.parse(raw)).zoom : 0;
  }).toBeGreaterThan(10);
}
async function seekGaLoading(request: APIRequestContext) {
  let coarse = await readWorld(request);
  for (let batch = 0; batch < 200; batch += 1) {
    if (coarse.shipments.some(row => row.order_id === 'ORD-ga' && !['PLANNED', 'ALLOCATED'].includes(row.status))) break;
    coarse = await sendOperation(request, { action: 'step' }, 48);
  }
  const shipment = coarse.shipments.find(row => row.order_id === 'ORD-ga' && !['PLANNED', 'ALLOCATED'].includes(row.status));
  const loading = coarse.events.find(row => row.entity_id === shipment?.id && row.event_type === 'SHIPMENT_LOADING');
  if (!loading) throw new Error('Actual coarse run did not publish GA loading');
  const target = Math.floor(loading.at_ms / 1000) * 1000;
  let replay = await resetScenario(request);
  while (replay.run.elapsed_ms < target) replay = await sendOperation(request, { action: 'step' }, Math.min(48, (target - replay.run.elapsed_ms) / 1000));
  const world = await stepUntil(request, row => row.shipments.some(item => item.id === shipment?.id && item.status === 'LOADING'), 3);
  return { world, proof: { method: 'Actual 48-step coarse run and deterministic reset/replay to recorded loading event', coarseRun: coarse.run, actualLoadingEvent: loading, replayRun: world.run } };
}

test('real scene preserves one canonical material across crane cargo and destination', async ({ page, request }, testInfo) => {
  test.setTimeout(180_000);
  await resetScenario(request);
  let world = await stepUntil(request, row => row.transfers.some(transfer => transfer.mode === 'flatbed' && transfer.status === 'LOADING'), 2000);
  const selected = world.transfers.find(row => row.mode === 'flatbed' && row.status === 'LOADING');
  if (!selected) throw new Error('No canonical flatbed handoff');
  const captures = [];
  for (let step = 0; step < 8; step += 1) {
    const transfer = world.transfers.find(row => row.id === selected.id);
    const material = world.materials.find(row => row.id === selected.material_id);
    if (!transfer || !material) throw new Error('Canonical transfer identity disappeared');
    await page.goto(`/?material_id=${selected.material_id}`);
    await expect(page.locator('canvas')).toBeVisible();
    await expect.poll(async () => (await scene(page)).revision).toBe(world.run.revision);
    await focusMaterial(page);
    const rendered = await scene(page);
    const meshes = rendered.materials.filter(row => row.id === material.id);
    expect(meshes).toHaveLength(1);
    const actual = meshes[0]; if (!actual) throw new Error('Missing material mesh');
    if (transfer.status !== 'ARRIVED') {
      const expected = transferPose(material, world, rendered.elapsedMs);
      if (!expected) throw new Error('Missing identity-specific transfer pose');
      expect(distance(actual.position, expected.position)).toBeLessThan(0.01);
    }
    captures.push({ transfer, material, rendered: actual, elapsedMs: rendered.elapsedMs });
    await page.screenshot({ path: testInfo.outputPath(`T15-${transfer.status}-${step}.png`) });
    if (transfer.status === 'ARRIVED') break;
    world = await sendOperation(request, { action: 'step' });
  }
  expect(new Set(captures.map(row => row.transfer.status))).toEqual(new Set(['LOADING', 'IN_TRANSIT', 'UNLOADING', 'ARRIVED']));
  await recordJson(testInfo, 'T15-real-handoffs', captures);
});

test('loaded material freezes on pause and a hung world request', async ({ page, request }, testInfo) => {
  test.setTimeout(180_000);
  await resetScenario(request);
  const world = await stepUntil(request, row => row.transfers.some(transfer => transfer.mode !== 'roller' && transfer.status === 'IN_TRANSIT'), 2000);
  const transfer = world.transfers.find(row => row.mode !== 'roller' && row.status === 'IN_TRANSIT');
  if (!transfer) throw new Error('Missing transfer');
  await page.goto(`/?material_id=${transfer.material_id}`);
  await expect(page.getByTestId('simulation-play-pause')).toBeEnabled();
  await clickOperation(page, 'simulation-play-pause', '/simulation/play');
  await clickOperation(page, 'simulation-play-pause', '/simulation/pause');
  await page.waitForTimeout(400);
  const paused = await scene(page);
  await page.waitForTimeout(550);
  expect((await scene(page)).materials).toEqual(paused.materials);
  await page.route('**/api/v1/world', () => new Promise<void>(() => {}));
  await clickOperation(page, 'simulation-play-pause', '/simulation/play');
  await page.waitForTimeout(650);
  const bounded = await scene(page);
  await page.waitForTimeout(650);
  expect((await scene(page)).materials).toEqual(bounded.materials);
  await sendOperation(request, { action: 'pause' });
  await page.unrouteAll({ behavior: 'ignoreErrors' });
  await recordJson(testInfo, 'T15-stops', { paused, bounded, after: await scene(page) });
});

test('partial GA shipment members follow their own hook truck ship and customer custody', async ({ page, request }, testInfo) => {
  test.setTimeout(240_000);
  await resetScenario(request);
  const seek = await seekGaLoading(request);
  let world = seek.world;
  await recordJson(testInfo, 'T15-GA-actual-seek', seek.proof);
  const shipment = world.shipments.find(row => row.order_id === 'ORD-ga' && row.status === 'LOADING');
  if (!shipment) throw new Error('Missing first GA shipment');
  const members = world.shipment_materials.filter(row => row.shipment_id === shipment.id && row.active);
  expect(members).toHaveLength(2);
  const member = members[0]; if (!member) throw new Error('Missing shipment material');
  const captures = [];
  for (let step = 0; step < 20; step += 1) {
    const current = world.shipments.find(row => row.id === shipment.id);
    if (!current) throw new Error('Shipment disappeared');
    await page.goto(`/?material_id=${member.material_id}`);
    await expect.poll(async () => (await scene(page)).revision).toBe(world.run.revision);
    await focusMaterial(page);
    const rendered = await scene(page);
    const physicalMembers = members.map(row => {
      const material = world.materials.find(item => item.id === row.material_id);
      const meshes = rendered.materials.filter(item => item.id === row.material_id);
      expect(meshes).toHaveLength(1);
      if (!material) throw new Error('Shipment material disappeared');
      const mesh = meshes[0];
      if (mesh?.custody === 'cargo') {
        const carrierId = material.location_id === 'OPS-FLATBED-A-CARGO' ? 'FLATBED-A' : 'SHIP-A';
        const carrier = rendered.vehicles.find(row => row.id === carrierId);
        if (!carrier) throw new Error(`Actual carrier ${carrierId} missing`);
        const local = new Vector3(...mesh.position).applyMatrix4(new Matrix4().fromArray(carrier.matrixWorld).invert());
        expect(Math.abs(local.x)).toBeCloseTo(0.75, 5);
        expect(local.y).toBeCloseTo(0, 5);
        expect(local.z).toBeCloseTo(0, 5);
      }
      return { material, mesh, vehicles: rendered.vehicles };
    });
    expect(physicalMembers.reduce((sum, row) => sum + row.material.weight_kg, 0)).toBe(40200);
    captures.push({ shipment: current, members: physicalMembers });
    await page.screenshot({ path: testInfo.outputPath(`T15-outbound-${step}-${current.status}.png`) });
    if (current.status === 'DELIVERED') {
      expect(physicalMembers.every(row => row.material.active && row.material.location_id === 'OPS-CUSTOMER-BUFFER' && row.mesh?.custody === 'destination')).toBe(true);
      break;
    }
    world = await sendOperation(request, { action: 'step' });
  }
  expect(captures.at(-1)?.shipment.status).toBe('DELIVERED');
  expect(captures.some(row => row.shipment.status === 'AT_PORT')).toBe(true);
  expect(captures.some(row => row.shipment.status === 'IN_TRANSIT')).toBe(true);
  await recordJson(testInfo, 'T15-partial-outbound', captures);
});

test('injected oversized waiting response shows a blocked reason and retains the source mesh', async ({ page, request }, testInfo) => {
  test.setTimeout(180_000);
  await resetScenario(request);
  const actual = await stepUntil(request, row => row.transfers.some(transfer => transfer.status === 'LOADING' && transfer.process_id !== null), 2000);
  const transfer = actual.transfers.find(row => row.status === 'LOADING' && row.process_id !== null);
  if (!transfer) throw new Error('Missing real baseline transfer');
  const material = actual.materials.find(row => row.id === transfer.material_id);
  if (!material) throw new Error('Missing baseline material');
  const reason = '운송 용량 초과: 승인된 QA 응답 경계 fixture';
  const materials = actual.materials.map(row => row.id === material.id ? { ...row, location_id: transfer.from_location_id } : row);
  const transfers = actual.transfers.map(row => row.id === transfer.id ? { ...row, status: 'WAITING', phase_start_ms: null, phase_end_ms: null, capacity_kg: material.weight_kg - 1 } : row);
  const processes = actual.processes.map(row => row.id === transfer.process_id ? { ...row, status: 'BLOCKED', blocked_reason: reason } : row);
  const fixture = WorldSchema.parse({ ...actual, materials, transfers, processes, production: { ...actual.production, materials, transfers, processes } });
  await page.route('**/api/v1/world', route => route.fulfill({ json: fixture }));
  await page.goto(`/?material_id=${material.id}`);
  await expect(page.getByTestId('material-inspector')).toContainText(reason);
  await expect.poll(async () => (await scene(page)).revision).toBe(fixture.run.revision);
  const before = (await scene(page)).materials.filter(row => row.id === material.id);
  expect(before).toHaveLength(1);
  expect(before[0]?.custody).toBe('source');
  await page.waitForTimeout(750);
  expect((await scene(page)).materials.filter(row => row.id === material.id)).toEqual(before);
  const picks = z.array(z.object({ kind: z.string(), id: z.string() })).parse(JSON.parse(await page.locator('canvas').getAttribute('data-pick-targets') ?? '[]'));
  expect(picks.filter(row => row.kind === 'vehicle' && row.id === transfer.vehicle_id)).toEqual([]);
  await recordJson(testInfo, 'T15-oversize-injected-response', { provenance: 'Schema-valid GET response fixture derived from actual paused World; not a live engine rejection', transfer: fixture.transfers.find(row => row.id === transfer.id), meshes: before, reason });
  await page.screenshot({ path: testInfo.outputPath('T15-oversize-blocked.png'), fullPage: true });
});
