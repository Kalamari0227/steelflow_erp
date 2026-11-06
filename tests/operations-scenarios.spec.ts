import { expect } from '@playwright/test';
import { test, readWorld, recordJson, sendOperation } from './helpers/operations';
import { commandWorld } from './helpers/commandReply';

for (const scenario of ['NORMAL', 'DELAY', 'RECOVERY'] as const) {
  test(`${scenario} uses actual scheduler ETA and truthful recovery comparison`, async ({ page, request }, testInfo) => {
    test.setTimeout(120_000);
    await page.goto('/');
    await expect(page.getByTestId('simulation-scenario')).toBeEnabled();
    const previous = await readWorld(request);
    const endpoint = previous.run.scenario_id === scenario ? '/simulation/reset' : `/scenarios/${scenario}/activate`;
    const responsePromise = page.waitForResponse(response => response.request().method() === 'POST' && response.url().endsWith(endpoint));
    if (previous.run.scenario_id === scenario) await page.getByTestId('simulation-reset').click();
    else await page.getByTestId('simulation-scenario').selectOption(scenario);
    const response = await responsePromise;
    expect(response.ok()).toBe(true);
    const initial = commandWorld(await response.json());
    await recordJson(testInfo, `T16-${scenario}-initial-comparison`, { run: initial.run, recovery: initial.recovery, forecast: initial.forecast });
    expect(initial.run.id).not.toBe(previous.run.id);
    expect(initial.ai.enabled).toBe(false);
    expect(initial.recovery?.recommendation).toBe('REVIEW_BENEFIT');
    expect(initial.recovery?.orders.filter(row => row.improvement_ms > 0).map(row => ({ order_id: row.order_id, improvement_ms: row.improvement_ms }))).toEqual([
      { order_id: 'ORD-sts-plate', improvement_ms: 14800 },
      { order_id: 'ORD-ti-plate', improvement_ms: 10200 },
    ]);
    expect(initial.recovery?.orders.filter(row => row.improvement_ms === 0)).toHaveLength(18);
    await page.getByTestId('order-ORD-plate').click();
    const panel = page.getByTestId('recovery-panel');
    await panel.scrollIntoViewIfNeeded();
    await expect(panel.getByTestId('comparison-ORD-plate')).toHaveAttribute('data-improvement-ms', '0');
    await expect(panel.getByTestId('comparison-ORD-plate')).toContainText('배송 개선 없음');
    await expect(panel.getByTestId('forecast-ORD-plate')).toHaveAttribute('data-status', 'ON_TIME');
    await panel.screenshot({ path: testInfo.outputPath(`T16-${scenario}-recovery.png`) });
    let final = initial;
    while (final.run.elapsed_ms < final.run.duration_ms) final = await sendOperation(request, { action: 'step' }, 48);
    const actual = final.events.filter(row => row.event_type === 'ORDER_DELIVERED');
    expect(actual).toHaveLength(20);
    expect(final.shipments.every(row => row.status === 'DELIVERED')).toBe(true);
    for (const prediction of initial.forecast) {
      expect(actual.find(row => row.entity_id === prediction.order_id)?.at_ms).toBe(prediction.completion_ms);
    }
    if (scenario !== 'NORMAL') {
      expect(final.events.some(row => row.event_type === 'RESOURCE_DOWN' && row.entity_id === 'HSM-A')).toBe(true);
      expect(final.events.some(row => row.event_type === 'PROCESS_BLOCKED' && row.reason === 'resource_unavailable')).toBe(true);
    }
    if (scenario === 'RECOVERY') {
      expect(final.events.some(row => row.event_type === 'RECOVERY_ROUTED' && row.material_id === 'MAT-ga-01')).toBe(true);
      expect(final.transfers.some(row => row.to_location_id === 'OPS-HSM-B-ENTRY' && row.mode === 'roller' && row.status === 'ARRIVED')).toBe(true);
    }
    await recordJson(testInfo, `T16-${scenario}-comparison`, { initial, actual, finalRun: final.run });
  });
}
