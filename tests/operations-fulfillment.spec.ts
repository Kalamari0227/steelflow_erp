import { expect, type APIRequestContext, type Page } from '@playwright/test';
import { test, readWorld, resetScenario, sendOperation, recordJson } from './helpers/operations';

async function completeRun(request: APIRequestContext) {
  let world = await readWorld(request);
  while (world.run.elapsed_ms < world.run.duration_ms) world = await sendOperation(request, { action: 'step' }, 48);
  return world;
}

async function advanceTo(request: APIRequestContext, targetMs: number) {
  let world = await readWorld(request);
  while (world.run.elapsed_ms < targetMs) world = await sendOperation(request, { action: 'step' }, Math.min(48, Math.ceil((targetMs - world.run.elapsed_ms) / 1000)));
  return world;
}

const metric = (page: Page, name: string) => page.locator('.ops-fulfillment > div').filter({ has: page.getByText(name, { exact: true }) });

test('GA first two coils deliver 40200 kg and the order finishes only after the third 20100 kg', async ({ page, request }, info) => {
  test.setTimeout(180_000);
  await resetScenario(request);
  const completed = await completeRun(request);
  const firstEvent = completed.events.find(row => row.event_type === 'SHIPMENT_DELIVERED' && row.entity_id === 'SHIP-ga-01');
  const secondEvent = completed.events.find(row => row.event_type === 'SHIPMENT_DELIVERED' && row.entity_id === 'SHIP-ga-02');
  if (!firstEvent || !secondEvent) throw new Error('Real GA completion events are missing');
  expect(firstEvent.at_ms).toBeLessThan(secondEvent.at_ms);
  await resetScenario(request);
  await page.goto('/?view=2d');
  await expect(page.getByTestId('simulation-step')).toBeEnabled();
  await page.getByTestId('order-ORD-ga').click();
  await expect(metric(page, '주문량')).toContainText('60,300');
  const partial = await advanceTo(request, firstEvent.at_ms);
  const partialOrder = partial.orders.find(row => row.id === 'ORD-ga');
  expect(partialOrder).toMatchObject({ status: 'PARTIALLY_DELIVERED', delivered_kg: 40200, remaining_delivery_kg: 20100 });
  await expect(metric(page, '배송 완료')).toContainText('40,200');
  await expect(metric(page, '배송 잔량')).toContainText('20,100');
  const shipmentButton = page.locator('.ops-shipment-list').getByRole('button', { name: /SHIP-ga-01/ });
  await shipmentButton.click();
  await expect(page.locator('.ops-shipment-detail')).toContainText('MAT-ga-01');
  await expect(page.locator('.ops-shipment-detail')).toContainText('MAT-ga-02');
  await expect(page.locator('.ops-shipment-detail')).not.toContainText('MAT-ga-03');
  await page.locator('.ops-shipment-detail').getByRole('button', { name: /MAT-ga-02/ }).click();
  await expect(page.getByTestId('material-inspector')).toContainText('MAT-ga-02');
  await expect(page.getByTestId('material-inspector')).toContainText('LOT-ga-01');
  await expect(page.getByTestId('material-inspector')).toContainText('PASSED');
  const unchanged = await readWorld(request);
  expect(unchanged.run).toEqual(partial.run);
  await page.screenshot({ path: info.outputPath('T18-GA-first-partial-delivery.png'), fullPage: true });
  const final = await advanceTo(request, secondEvent.at_ms);
  const finalOrder = final.orders.find(row => row.id === 'ORD-ga');
  expect(finalOrder).toMatchObject({ status: 'DELIVERED', delivered_kg: 60300, remaining_delivery_kg: 0 });
  await expect(metric(page, '배송 완료')).toContainText('60,300');
  await expect(metric(page, '배송 잔량')).toHaveText('배송 잔량0 kg');
  await page.locator('.ops-shipment-list').getByRole('button', { name: /SHIP-ga-02/ }).click();
  await expect(page.locator('.ops-shipment-detail')).toContainText('MAT-ga-03');
  await expect(page.locator('.ops-shipment-detail')).not.toContainText('MAT-ga-01');
  await page.locator('.ops-shipment-detail').getByRole('button', { name: /MAT-ga-03/ }).click();
  await expect(page.getByTestId('material-inspector')).toContainText('MAT-ga-03');
  await expect(page.getByTestId('material-inspector')).toContainText('LOT-ga-02');
  await page.screenshot({ path: info.outputPath('T18-GA-final-delivery.png'), fullPage: true });
  await recordJson(info, 'T18-GA-fulfillment', { firstEvent, secondEvent, partial, final });
});

test('PLATE split keeps a consumed parent traceable and sends only the two inspected children', async ({ page, request }, info) => {
  test.setTimeout(120_000);
  await resetScenario(request);
  const final = await completeRun(request);
  const parent = final.materials.find(row => row.id === 'MAT-plate-01');
  const children = final.materials.filter(row => row.id === 'MAT-plate-01:A' || row.id === 'MAT-plate-01:B');
  expect(parent).toMatchObject({ active: false, availability_status: 'CONSUMED' });
  expect(children).toHaveLength(2);
  expect(children.map(row => row.weight_kg)).toEqual([9950, 9950]);
  expect(final.inventory_materials.some(row => row.id === parent?.id)).toBe(false);
  expect(final.shipment_materials.filter(row => row.shipment_id === 'SHIP-plate-01').map(row => row.material_id).sort()).toEqual(['MAT-plate-01:A', 'MAT-plate-01:B']);
  await page.goto('/?view=2d');
  await expect(page.getByTestId('current-run')).toHaveText(`${final.run.id} · rev ${final.run.revision}`);
  expect((await readWorld(request)).run).toEqual(final.run);
  expect(final.run.elapsed_ms).toBe(final.run.duration_ms);
  await expect(page.getByTestId('simulation-step')).toBeDisabled();
  await page.getByTestId('order-ORD-plate').click();
  await page.getByTestId('material-MAT-plate-01').click();
  const inspector = page.getByTestId('material-inspector');
  await expect(inspector).toContainText('소비된 부모');
  for (const child of children) {
    await inspector.getByRole('button', { name: child.id, exact: true }).click();
    await expect(inspector.locator('.ops-passport')).toContainText(child.id);
    await expect(inspector).toContainText(child.current_version_id);
    await expect(inspector).toContainText('PASSED');
    await expect(inspector).toContainText('SHIP-plate-01');
    await inspector.getByRole('button', { name: 'MAT-plate-01', exact: true }).click();
    await expect(inspector).toContainText('소비된 부모');
  }
  await page.locator('.ops-shipment-list').getByRole('button', { name: /SHIP-plate-01/ }).click();
  await expect(page.locator('.ops-shipment-detail').getByRole('button')).toHaveCount(2);
  await expect(metric(page, '배송 완료')).toContainText('19,900');
  expect((await readWorld(request)).run).toEqual(final.run);
  await page.screenshot({ path: info.outputPath('T18-PLATE-child-lineage.png'), fullPage: true });
  await recordJson(info, 'T18-PLATE-fulfillment', { parent, children, lineage: final.lineage_edges, shipment: final.shipments.find(row => row.id === 'SHIP-plate-01'), run: final.run });
});
