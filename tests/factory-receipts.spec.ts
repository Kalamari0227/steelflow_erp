import { expect, test } from '@playwright/test';
import { writeFile } from 'node:fs/promises';
import { join } from 'node:path';
import policy from '../backend/app/data/factory_stock_policy_v1.json' with { type: 'json' };
import { factoryCoilsSchema, factoryCommandReplySchema, factoryMaterialDetailSchema, factoryWorldSchema } from '../src/operations/contractsV3';
import { captureBrowserFailures, recordJson } from './helpers/operations';
import { guardBrowserMutations, postOwnedOperation, readQaIdentity } from './helpers/qaIdentity';

test('purchased HR remains the selected physical stock before and after order allocation', async ({ page, request, context, baseURL }, info) => {
  // Given: the full admitted world and an actual trusted completed observation.
  if (!baseURL || !process.env.T9_EVIDENCE) throw new Error('Owned T9 runtime is required');
  const evidence = process.env.T9_EVIDENCE;
  const identity = await readQaIdentity();
  const guard = await guardBrowserMutations(context);
  const capture = captureBrowserFailures(context, baseURL);
  const network: { method: string; url: string; status: number }[] = [];
  context.on('response', response => network.push({ method: response.request().method(), url: response.url(), status: response.status() }));
  try {
    const rawWorld = await (await request.get('/api/v1/world')).json();
    const before = factoryWorldSchema.parse(rawWorld);
    const material = before.materials[0];
    if (!material) throw new Error('Trusted receipt did not create stock');
    expect(before.materials).toHaveLength(1);
    expect(before.kpis).toMatchObject({ active_material_count: 1, active_kg: 20000, available_kg: 20000, allocated_kg: 0, received_kg: 20000 });
    const detailPath = `/api/v1/materials/${encodeURIComponent(material.id)}`;
    const unallocated = factoryMaterialDetailSchema.parse(await (await request.get(detailPath)).json());
    expect(unallocated.order).toBeNull(); expect(unallocated.work_order).toBeNull(); expect(unallocated.production_lot).toBeNull();
    const coils = factoryCoilsSchema.parse(await (await request.get('/api/v1/coils')).json());
    expect(coils.materials[0]).toMatchObject({ id: material.id, production_lot_id: null, origin_stock_lot_id: material.origin_stock_lot_id });
    await writeFile(join(evidence, 'http/unallocated-world.json'), JSON.stringify(rawWorld, null, 2));
    await writeFile(join(evidence, 'http/unallocated-detail.json'), JSON.stringify(unallocated, null, 2));
    await writeFile(join(evidence, 'http/unallocated-coils.json'), JSON.stringify(coils, null, 2));
    await page.goto('/');
    await expect(page.getByTestId('factory-run')).toHaveText(before.run.id);
    await page.getByRole('region', { name: '소재 목록' }).getByRole('button', { name: material.id, exact: true }).click();
    const detail = page.getByRole('region', { name: '소재 상세' });
    await expect(detail).toContainText('PASSED / AVAILABLE');
    await expect(detail).toContainText('width_mm: 1000');
    await expect(detail).toContainText('v2:p:receipt:HR_COIL:work');
    await expect(detail.getByRole('heading', { level: 2 })).toHaveText(material.id);
    await expect(detail.locator('dt', { hasText: /^주문$/ }).locator('+ dd')).toHaveText('없음 (null)');
    await page.screenshot({ path: info.outputPath('unallocated.png'), fullPage: true });
    // When: the endpoint allocates the same complete physical material.
    const body = { action: 'allocate_stock', run_id: before.run.id, expected_revision: before.run.revision, command_id: 'T9-browser-allocation', material_id: material.id, order_id: 'order:gi:1', mode: 'processing' };
    await writeFile(join(evidence, 'http/allocation-body.json'), JSON.stringify(body, null, 2));
    const response = await postOwnedOperation(request, '/api/v1/stock/allocations', body);
    expect(response.status()).toBe(200);
    const rawReply = await response.json();
    const allocated = factoryCommandReplySchema.parse(rawReply);
    await writeFile(join(evidence, 'http/allocation-reply.json'), JSON.stringify(rawReply, null, 2));
    await writeFile(join(evidence, 'http/allocation-response.json'), JSON.stringify({ status: response.status(), headers: response.headers() }, null, 2));
    // Then: no physical relocation, manufactured ancestry, or completed process appears.
    await expect(detail).toContainText('PASSED / RESERVED');
    await expect(detail.getByRole('button', { name: 'order:gi:1', exact: true })).toBeVisible();
    await expect(detail.getByRole('heading', { level: 2 })).toHaveText(material.id);
    await expect(page.getByTestId('factory-run')).toHaveText(before.run.id);
    await expect(page.getByTestId('factory-revision')).toContainText(`리비전 ${allocated.run.revision}`);
    await expect(detail).toContainText(`상세 응답 리비전 ${allocated.run.revision}`);
    await expect(detail.locator('dt', { hasText: /^생산 로트$/ }).locator('+ dd')).toHaveText('없음 (null)');
    const after = factoryMaterialDetailSchema.parse(await (await request.get(detailPath)).json());
    expect(after.current_attachment).toEqual(unallocated.current_attachment);
    expect(after.current_version).toEqual(unallocated.current_version);
    expect(after.work_order?.status).toBe('RELEASED');
    const retainedRoute = policy.routes.find(route => route.product === 'gi');
    if (!retainedRoute) throw new Error('Retained GI route is missing');
    const expectedSuffix = retainedRoute.steps.filter(step => step.ordinal >= 12).map(step => step.key).sort();
    expect(expectedSuffix).toHaveLength(18);
    expect(allocated.processes.map(row => row.route_step_id).sort()).toEqual(expectedSuffix);
    expect(allocated.processes.every(row => row.status === 'QUEUED' && row.start_ms === null && row.end_ms === null)).toBe(true);
    expect(allocated.processes.some(row => row.route_step_id === 'gi:cr-02')).toBe(true);
    expect(allocated.events.filter(row => ['PROCESS_STARTED', 'PROCESS_COMPLETED', 'MATERIAL_TRANSFORMED', 'INSPECTION_PASSED', 'PACKAGING_COMPLETED'].includes(row.event_type))).toEqual([]);
    expect(allocated.kpis).toMatchObject({ available_kg: 0, allocated_kg: 20000, active_kg: 20000 });
    await page.screenshot({ path: info.outputPath('allocated.png'), fullPage: true });
    await writeFile(join(evidence, 'http/allocated-detail.json'), JSON.stringify(after, null, 2));
    await recordJson(info, 'assertions', { same_material: material.id === after.material.id, same_run: before.run.id === after.run_id, revision: after.revision === allocated.applied_revision, unallocated_nulls: !unallocated.order && !unallocated.work_order && !unallocated.production_lot, custody_unchanged: JSON.stringify(after.current_attachment) === JSON.stringify(unallocated.current_attachment), no_upstream_completion: allocated.events.every(row => !['PROCESS_COMPLETED', 'MATERIAL_TRANSFORMED', 'INSPECTION_PASSED', 'PACKAGING_COMPLETED'].includes(row.event_type)), ts_actual_http_parsed: true, identity });
  } finally {
    await guard.dispose(); capture.dispose();
    await recordJson(info, 'console-network', { failures: capture.failures, refused: guard.refused, network });
    expect(capture.failures).toEqual([]); expect(guard.refused).toEqual([]);
  }
});
