import { expect, test as base } from '@playwright/test';
import { createServer } from 'node:http';
import { mkdir, writeFile } from 'node:fs/promises';
import { dirname } from 'node:path';
import { choosePorts, protectedPorts } from '../tools/qa/ownership.mjs';
import { test, clickOperation, readWorld, recordJson, resetScenario, sendOperation } from './helpers/operations';
import { assertOwnedMutation, guardBrowserMutations, readQaIdentity } from './helpers/qaIdentity';

test('owned-isolation renders the real factory and changes only its owned run', async ({ page, request, browser }, testInfo) => {
  test.setTimeout(90_000);
  const identity = await readQaIdentity();
  const initial = await resetScenario(request);
  await recordJson(testInfo, 'current-engine-before-expectation-edit', { identity, run: initial.run, recovery: initial.recovery, forecast: initial.forecast });
  await page.goto('/');
  await expect(page.locator('canvas')).toBeVisible();
  const graphics = await page.locator('canvas').evaluate(element => {
    if (!(element instanceof HTMLCanvasElement)) throw new Error('Expected the real factory canvas');
    const gl = element.getContext('webgl2');
    if (!gl) throw new Error('Factory WebGL2 context is unavailable');
    const extension = gl.getExtension('WEBGL_debug_renderer_info');
    return { userAgent: navigator.userAgent, devicePixelRatio, renderer: gl.getParameter(extension ? extension.UNMASKED_RENDERER_WEBGL : gl.RENDERER), vendor: gl.getParameter(extension ? extension.UNMASKED_VENDOR_WEBGL : gl.VENDOR) };
  });
  await recordJson(testInfo, 'browser-hardware', { browserVersion: browser.version(), ...graphics });
  await expect(page.getByTestId('simulation-step')).toBeEnabled();
  await page.getByTestId('order-ORD-ga').click();
  await page.getByTestId('material-MAT-ga-01').click();
  await expect(page.getByTestId('material-inspector')).toContainText('MAT-ga-01');
  const stepped = await clickOperation(page, 'simulation-step', '/api/v1/simulation/step');
  expect(stepped.run.id).toBe(initial.run.id);
  expect(stepped.run.elapsed_ms).toBeGreaterThan(initial.run.elapsed_ms);
  expect(stepped.run.revision).toBeGreaterThan(initial.run.revision);
  await expect(page.getByRole('progressbar', { name: '전체 실행 진행률', exact: true })).toHaveAttribute('value', String(stepped.run.elapsed_ms));
  const current = await readWorld(request);
  expect(current.run).toEqual(stepped.run);
  await page.screenshot({ path: testInfo.outputPath('owned-factory-step.png'), fullPage: true });
  await recordJson(testInfo, 'owned-isolation', { identity, initial: initial.run, afterClick: stepped.run, persisted: current.run, canvas: await page.locator('canvas').getAttribute('data-scene-state') });
});

base('reject-foreign refuses foreign, stale, malformed, DB/PID, occupied and protected targets with zero POST', async ({ playwright, request }, testInfo) => {
  const identity = await readQaIdentity();
  const initial = await readWorld(request);
  const health = await (await request.get('/health')).json();
  let servedHealth: unknown = health;
  let posts = 0;
  const server = createServer((incoming, response) => {
    if (incoming.method === 'POST') posts += 1;
    response.setHeader('content-type', 'application/json');
    response.end(JSON.stringify(incoming.url === '/health' ? servedHealth : initial));
  });
  await new Promise<void>(resolve => server.listen(0, '127.0.0.1', resolve));
  const address = server.address();
  if (!address || typeof address === 'string') throw new Error('Foreign fixture must own a TCP port');
  const origin = `http://127.0.0.1:${address.port}`;
  const foreign = await playwright.request.newContext({ baseURL: origin });
  const receiptPath = testInfo.outputPath('adversarial-identity.json');
  await mkdir(dirname(receiptPath), { recursive: true });
  const originalPath = process.env.STEELFLOW_QA_IDENTITY_PATH;
  const observations: { scenario: string; rejection: string; posts: number }[] = [];
  const foreignReceipt = { ...identity, api_origin: origin, web_origin: origin };
  async function rejected(scenario: string, action: () => Promise<unknown>) {
    let rejection = '';
    try { await action(); } catch (error) {
      if (!(error instanceof Error)) throw error;
      rejection = error.message;
    }
    observations.push({ scenario, rejection, posts });
    await recordJson(testInfo, 'reject-foreign-observations', { observations, posts });
    expect(rejection, scenario).not.toBe('');
    expect(posts, scenario).toBe(0);
  }
  async function receipt(value: unknown) {
    await writeFile(receiptPath, JSON.stringify(value));
    process.env.STEELFLOW_QA_IDENTITY_PATH = receiptPath;
  }
  try {
    await rejected('foreign origin with copied live health', () => sendOperation(foreign, { action: 'step' }));
    await receipt({ ...foreignReceipt, attempt_id: `${identity.attempt_id}-stale` });
    await rejected('stale receipt attempt', () => sendOperation(foreign, { action: 'reset' }));
    await receipt(foreignReceipt);
    for (const [scenario, qa] of [
      ['foreign attempt', { ...identity, attempt_id: 'foreign' }],
      ['different database', { ...identity, db_fingerprint: '0'.repeat(64) }],
      ['different health PID', { ...identity, pid: identity.pid + 1 }],
      ['missing QA identity', undefined],
      ['malformed QA identity', 'not-an-object'],
    ] as const) {
      servedHealth = { status: 'ok', qa };
      await rejected(scenario, () => sendOperation(foreign, { action: 'pause' }));
    }
    servedHealth = health;
    await rejected('copied health cannot spoof actual listener PID', () => sendOperation(foreign, { action: 'step' }));
    await receipt({ ...identity, web_origin: origin });
    await rejected('foreign web origin with real API origin and copied health', () => sendOperation(foreign, { action: 'step' }));
    await receipt({ ...foreignReceipt, pid: 'invalid' });
    await rejected('malformed receipt', () => sendOperation(foreign, { action: 'step' }));
    process.env.STEELFLOW_QA_IDENTITY_PATH = originalPath;
    await rejected('occupied requested port', () => choosePorts(String(address.port), '4176'));
    for (const port of protectedPorts) {
      await rejected(`protected target ${port}`, () => assertOwnedMutation(request, `http://127.0.0.1:${port}/api/v1/simulation/reset`));
    }
    const final = await readWorld(request);
    expect(final.run).toEqual(initial.run);
    await recordJson(testInfo, 'reject-foreign', { observations, posts, before: initial.run, after: final.run, foreignListener: { pid: process.pid, port: address.port } });
  } finally {
    process.env.STEELFLOW_QA_IDENTITY_PATH = originalPath;
    await foreign.dispose();
    await new Promise<void>((resolve, reject) => server.close(error => error ? reject(error) : resolve()));
  }
});

base('reject-foreign blocks a real UI mutation after the receipt becomes stale', async ({ page, context, request }, testInfo) => {
  const identity = await readQaIdentity();
  const initial = await readWorld(request);
  const guard = await guardBrowserMutations(context);
  const originalPath = process.env.STEELFLOW_QA_IDENTITY_PATH;
  const path = testInfo.outputPath('stale-ui-receipt.json');
  await mkdir(dirname(path), { recursive: true });
  const attemptedPosts: { url: string; body: string | null }[] = [];
  const failedRequests: { url: string; failure: string | undefined }[] = [];
  page.on('request', item => { if (item.method() === 'POST') attemptedPosts.push({ url: item.url(), body: item.postData() }); });
  page.on('requestfailed', item => { if (item.method() === 'POST') failedRequests.push({ url: item.url(), failure: item.failure()?.errorText }); });
  try {
    await page.goto('/');
    await expect(page.getByTestId('simulation-step')).toBeEnabled();
    await writeFile(path, JSON.stringify({ ...identity, attempt_id: 'stale-ui-attempt' }));
    process.env.STEELFLOW_QA_IDENTITY_PATH = path;
    await expect(clickOperation(page, 'simulation-step', '/api/v1/simulation/step')).rejects.toThrow('stale runner attempt');
    expect(guard.refused).toHaveLength(0);
    const blocked = page.waitForEvent('requestfailed', { predicate: item => item.url().endsWith('/simulation/step') });
    await page.getByTestId('simulation-step').click();
    await blocked;
    await expect(page.getByRole('alert')).toContainText('로컬 서버 응답을 확인하지 못했습니다.');
    expect(attemptedPosts.length).toBeGreaterThan(0);
    expect(guard.refused).toHaveLength(attemptedPosts.length);
    expect(failedRequests).toHaveLength(attemptedPosts.length);
    expect(guard.refused.every(item => item.reason.includes('stale runner attempt'))).toBe(true);
    expect(failedRequests.every(item => item.failure?.includes('ERR_BLOCKED_BY_CLIENT'))).toBe(true);
    expect(new Set(attemptedPosts.map(item => item.body)).size).toBe(1);
    const final = await readWorld(request);
    expect(final.run).toEqual(initial.run);
    await page.screenshot({ path: testInfo.outputPath('rejected-ui-step.png'), fullPage: true });
    await recordJson(testInfo, 'reject-foreign-ui', { attemptedPosts, refused: guard.refused, failedRequests, before: initial.run, after: final.run });
  } finally {
    process.env.STEELFLOW_QA_IDENTITY_PATH = originalPath;
    await guard.dispose();
  }
});
