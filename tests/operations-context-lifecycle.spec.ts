import { expect } from '@playwright/test';
import { test, resetScenario, readWorld, recordJson, clickOperation } from './helpers/operations';

test('context loss at first connected canvas preserves identity and recreated 3D remains usable', async ({ page, request }, testInfo) => {
  const initial = await resetScenario(request);
  await page.addInitScript(() => {
    const seen = new WeakSet<HTMLCanvasElement>();
    let armed = true;
    const observer = new MutationObserver(() => {
      if (document.documentElement.dataset.armEarlyLoss === 'true') {
        armed = true;
        delete document.documentElement.dataset.armEarlyLoss;
      }
      for (const canvas of document.querySelectorAll('canvas')) {
        if (!canvas.isConnected || seen.has(canvas)) continue;
        seen.add(canvas);
        if (!armed) continue;
        armed = false;
        const context = canvas.getContext('webgl2');
        const extension = context?.getExtension('WEBGL_lose_context');
        if (!extension) throw new Error('Early context-loss regression requires real WebGL2');
        extension.loseContext();
        document.documentElement.dataset.earlyLossCount = String(Number(document.documentElement.dataset.earlyLossCount ?? '0') + 1);
      }
    });
    observer.observe(document, { childList: true, subtree: true });
  });
  await page.goto('/?order_id=ORD-ga&material_id=MAT-ga-01');
  await expect(page.getByRole('button', { name: '2D', exact: true })).toHaveAttribute('aria-pressed', 'true');
  await expect(page.locator('html')).toHaveAttribute('data-early-loss-count', '1');
  await expect(page.getByTestId('material-inspector')).toContainText('MAT-ga-01');
  await expect(page.getByTestId('operations-table')).toContainText('ORD-ga · MAT-ga-01');
  expect((await readWorld(request)).run).toEqual(initial.run);

  await page.getByRole('button', { name: '3D', exact: true }).click();
  await expect(page.locator('canvas')).toHaveAttribute('data-scene-state', /"materials"/);
  await expect(page.getByRole('button', { name: '3D', exact: true })).toHaveAttribute('aria-pressed', 'true');
  await expect(page.getByTestId('material-inspector')).toContainText('MAT-ga-01');
  await page.getByRole('button', { name: '2D', exact: true }).click();
  await expect(page.locator('canvas')).toHaveCount(0);
  await page.evaluate(() => { document.documentElement.dataset.armEarlyLoss = 'true'; });
  await page.getByRole('button', { name: '3D', exact: true }).click();
  await expect(page.locator('html')).toHaveAttribute('data-early-loss-count', '2');
  await expect(page.getByRole('button', { name: '2D', exact: true })).toHaveAttribute('aria-pressed', 'true');
  await expect(page.getByTestId('material-inspector')).toContainText('MAT-ga-01');
  const advanced = await clickOperation(page, 'simulation-step', '/api/v1/simulation/step');
  expect(advanced.run.id).toBe(initial.run.id);
  expect(advanced.run.elapsed_ms).toBeGreaterThan(initial.run.elapsed_ms);
  await page.screenshot({ path: testInfo.outputPath('early-context-loss-recovered.png'), fullPage: true });
  await recordJson(testInfo, 'early-context-loss', { initial: initial.run, advanced: advanced.run, earlyLossCount: 2, successfulRecreation: true, materialId: 'MAT-ga-01', injection: 'real WEBGL_lose_context in MutationObserver at first connected canvas insertion; no scene-ready wait before injection' });
});
