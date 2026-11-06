import { test as fixtureTest, expect, request as playwrightRequest } from '@playwright/test';
import { execFile } from 'node:child_process';
import { createServer } from 'node:http';
import { promisify } from 'node:util';
import { resolve } from 'node:path';
import { rm, stat } from 'node:fs/promises';
import { WorldSchema } from '../src/contracts';
import { captureBrowserFailures, createIsolatedRun, readWorld, ready, recordJson, resetScenario, runSnapshot, stepUntil, test } from './helpers/operations';
import { postOwnedOperation } from './helpers/qaIdentity';

const execute = promisify(execFile);

test('isolated database persists steps without mutating a second fresh database', async ({ page, request }, testInfo) => {
  test.setTimeout(120_000);
  await resetScenario(request);
  const databasePath = process.env.STEELFLOW_E2E_DATABASE_PATH;
  if (!databasePath) throw new Error('Missing harness database path');
  const separate = createIsolatedRun();
  try {
  expect(databasePath).not.toBe(separate.databasePath);
  const python = 'import asyncio,sys\nfrom app.database import Database\nasync def main():\n db=Database("sqlite+aiosqlite:///"+sys.argv[1])\n await db.initialize()\n snapshot=await db.snapshot()\n print(snapshot.model_dump_json())\n await db.close()\nasyncio.run(main())';
  const inspectDatabase = async (path: string) => {
    const { stdout } = await execute(resolve('backend/.venv/bin/python'), ['-c', python, path], { cwd: resolve('backend') });
    return WorldSchema.parse(JSON.parse(stdout));
  };
  const independentBefore = await inspectDatabase(separate.databasePath);
  expect(independentBefore.simulation.tick).toBe(0);
  const reset = await postOwnedOperation(request, '/api/v1/scenarios/NORMAL/activate');
  expect(reset.ok()).toBe(true);
  await page.goto('/');
  const initial = await ready(page, request);
  expect(initial.simulation.tick).toBe(0);
  const stepped = await stepUntil(request, world => world.simulation.tick === 2, 2);
  expect(stepped.simulation.tick).toBe(2);
  const persisted = await inspectDatabase(databasePath);
  expect(persisted.simulation.tick).toBe(2);
  const independentAfter = await inspectDatabase(separate.databasePath);
  expect(independentAfter.simulation).toEqual(independentBefore.simulation);
  expect((await stat(databasePath)).size).toBeGreaterThan(0);
  expect((await stat(separate.databasePath)).size).toBeGreaterThan(0);
  await recordJson(testInfo, 'T05-database-isolation', { databasePath, separateDatabasePath: separate.databasePath, initial: initial.simulation, persisted: persisted.simulation, independentBefore: independentBefore.simulation, independentAfter: independentAfter.simulation });
  await runSnapshot(page, request, testInfo, 'T05-ready');
  await expect(stepUntil(request, () => false, 0)).rejects.toThrow('Condition was not reached');
  } finally {
    await rm(separate.root, { recursive: true });
    await recordJson(testInfo, 'T05-owned-temp-cleanup', { removedRoot: separate.root, complete: true });
  }
});

fixtureTest('captures browser failures and refuses API failures', async ({ page, context, baseURL, request }, testInfo) => {
  if (!baseURL) throw new Error('Missing harness baseURL');
  const capture = captureBrowserFailures(context, baseURL);
  const failureServer = createServer((_request, response) => { response.writeHead(503); response.end('T05 intentional API failure'); });
  try {
    await page.goto('/');
    await ready(page, request);
    capture.assertHealthy();
    const errorEvent = page.waitForEvent('pageerror');
    await page.evaluate(() => { setTimeout(() => { throw new Error('T05 intentional browser error'); }, 0); });
    await errorEvent;
    await page.evaluate(() => console.error('T18 intentional console error'));
    await page.route('**/api/v1/harness-http-failure', route => route.fulfill({ status: 503, body: 'T05 intentional unavailable' }));
    await page.evaluate(async () => { await fetch('/api/v1/harness-http-failure'); });
    await page.route('**/api/v1/harness-network-failure', route => route.abort('connectionrefused'));
    await page.evaluate(async () => { await fetch('/api/v1/harness-network-failure').catch(() => undefined); });
    await page.route('https://example.invalid/t05-probe', route => route.fulfill({ status: 200, body: 'intercepted locally', headers: { 'access-control-allow-origin': '*' } }));
    await page.evaluate(async () => { await fetch('https://example.invalid/t05-probe'); });
    await expect.poll(() => capture.failures.map(item => item.kind)).toEqual(expect.arrayContaining(['pageerror', 'http', 'requestfailed', 'external', 'console']));
    expect(capture.failures.some(item => item.message === 'T05 intentional browser error')).toBe(true);
    expect(capture.failures.some(item => item.kind === 'console' && item.message === 'T18 intentional console error')).toBe(true);
    expect(() => capture.assertHealthy()).toThrow('Browser failures detected');
    await new Promise<void>(resolveListening => failureServer.listen(0, '127.0.0.1', resolveListening));
    const address = failureServer.address();
    if (!address || typeof address === 'string') throw new Error('Failure server did not bind');
    const failingRequest = await playwrightRequest.newContext({ baseURL: `http://127.0.0.1:${address.port}` });
    try {
      await expect(readWorld(failingRequest)).rejects.toThrow('World request failed: HTTP 503');
      await expect(stepUntil(failingRequest, () => true)).rejects.toThrow('World request failed: HTTP 503');
    } finally {
      await failingRequest.dispose();
    }
    await page.route('**/api/v1/world', route => route.fulfill({ status: 503, body: 'T05 intentional API failure' }));
    await page.reload();
    await expect(page.getByRole('heading', { name: '운영 서버에 연결할 수 없습니다', exact: true })).toBeVisible();
    await expect(page.getByTestId('simulation-step')).toHaveCount(0);
    await expect(page.getByRole('button', { name: '다시 연결', exact: true })).toBeEnabled();
    await expect(ready(page, request)).rejects.toThrow();
    await recordJson(testInfo, 'T05-error-capture', { failures: capture.failures, guardRejectedFailures: true, readWorldRejected503: true, stepUntilRejected503: true, readyRejectedUnavailableUI: true });
    const screenshot = testInfo.outputPath('T05-unavailable.png');
    await page.screenshot({ path: screenshot, fullPage: true });
    await testInfo.attach('T05-unavailable', { path: screenshot, contentType: 'image/png' });
  } finally {
    capture.dispose();
    if (failureServer.listening) {
      await new Promise<void>((resolveClosed, reject) => failureServer.close(error => error ? reject(error) : resolveClosed()));
    }
  }
});
