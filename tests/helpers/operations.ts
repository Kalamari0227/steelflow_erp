import { expect, test as base, type APIRequestContext, type BrowserContext, type ConsoleMessage, type Page, type Request, type Response, type TestInfo } from '@playwright/test';
import { mkdtempSync } from 'node:fs';
import { mkdir, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { dirname, join } from 'node:path';
import { WorldSchema, type World, type ScenarioId } from '../../src/contracts';
import type { SimulationCommand } from '../../src/api';
import { z } from 'zod';
import { Matrix4, Vector3 } from 'three';
import { commandWorld } from './commandReply';
import { assertOwnedMutation, guardBrowserMutations, postOwnedOperation } from './qaIdentity';

export function createIsolatedRun() {
  const root = mkdtempSync(join(tmpdir(), 'steelflow-e2e-'));
  return { root, databasePath: join(root, 'steelflow.sqlite') };
}

export async function readWorld(request: APIRequestContext): Promise<World> {
  const response = await request.get('/api/v1/world');
  if (!response.ok()) throw new Error(`World request failed: HTTP ${response.status()} ${await response.text()}`);
  return WorldSchema.parse(await response.json());
}

export async function sendOperation(request: APIRequestContext, command: SimulationCommand, steps = 1): Promise<World> {
  const world = await readWorld(request);
  const endpoint = command.action === 'scenario' ? `scenarios/${command.scenario}/activate` : `simulation/${command.action}`;
  const data = { run_id: world.run.id, command_id: crypto.randomUUID(), ...(command.action === 'reset' || command.action === 'scenario' ? { expected_revision: world.run.revision } : {}), ...(command.action === 'step' ? { steps } : {}), ...('speed' in command ? { speed: command.speed } : {}) };
  const response = await postOwnedOperation(request, `/api/v1/${endpoint}`, data);
  if (!response.ok()) throw new Error(`Command ${command.action} failed: HTTP ${response.status()} ${await response.text()}`);
  return commandWorld(await response.json());
}

export async function resetScenario(request: APIRequestContext, scenario: ScenarioId = 'NORMAL'): Promise<World> {
  await sendOperation(request, { action: 'pause' });
  return sendOperation(request, { action: 'scenario', scenario });
}

export async function clickOperation(page: Page, testId: string, endpoint: string): Promise<World> {
  await assertOwnedMutation(page.request, page.url());
  const pending = page.waitForResponse(response => response.url().endsWith(endpoint) && response.request().method() === 'POST');
  await page.getByTestId(testId).click();
  const response = await pending;
  if (!response.ok()) throw new Error(`UI command failed: HTTP ${response.status()} ${await response.text()}`);
  return commandWorld(await response.json());
}

export function businessState(world: World) {
  const withoutRun = <T extends { readonly run_id: string }>(rows: readonly T[]) => rows.map(({ run_id: _runId, ...row }) => row);
  const eventReference = (id: string | null) => id?.startsWith(`${world.run.id}:`) ? `<run>${id.slice(world.run.id.length)}` : id;
  const versions = withoutRun(world.material_versions).map(row => ({ ...row, cause_event_id: eventReference(row.cause_event_id) }));
  const inspections = withoutRun(world.inspections).map(row => ({ ...row, release_event_id: eventReference(row.release_event_id) }));
  return { orders: withoutRun(world.orders), lots: withoutRun(world.lots), materials: withoutRun(world.materials), versions, processes: withoutRun(world.processes), transfers: withoutRun(world.transfers), inspections, shipments: withoutRun(world.shipments), mass_balance: world.mass_balance, kpis: world.kpis };
}

export async function loseWebGL(page: Page): Promise<void> {
  const canvas = page.locator('canvas');
  await expect(canvas).toBeVisible();
  const supported = await canvas.evaluate(element => {
    if (!(element instanceof HTMLCanvasElement)) throw new Error('Expected canvas');
    const extension = element.getContext('webgl2')?.getExtension('WEBGL_lose_context');
    if (!extension) return false;
    extension.loseContext();
    return true;
  });
  expect(supported).toBe(true);
  await expect(page.getByRole('button', { name: '2D', exact: true })).toHaveAttribute('aria-pressed', 'true');
}

const PickTargetSchema = z.array(z.object({ kind: z.string(), id: z.string(), x: z.number(), y: z.number(), world: z.tuple([z.number(), z.number(), z.number()]) }));
export async function clickSceneObject(page: Page, kind: string, id: string): Promise<void> {
  const canvas = page.locator('canvas');
  await canvas.scrollIntoViewIfNeeded();
  await expect.poll(async () => {
    const raw = await canvas.getAttribute('data-pick-targets');
    return raw !== null && PickTargetSchema.parse(JSON.parse(raw)).some(row => row.kind === kind && row.id === id);
  }).toBe(true);
  const raw = await canvas.getAttribute('data-pick-targets');
  if (!raw) throw new Error('Scene has no real camera projection diagnostics');
  const target = PickTargetSchema.parse(JSON.parse(raw)).find(row => row.kind === kind && row.id === id);
  if (!target) throw new Error(`Scene target missing: ${kind}/${id}`);
  const camera = z.object({ camera: z.object({ projectionMatrix: z.array(z.number()).length(16), matrixWorld: z.array(z.number()).length(16) }) }).parse(JSON.parse(await canvas.getAttribute('data-scene-state') ?? '{}')).camera;
  const bounds = await canvas.boundingBox();
  if (!bounds) throw new Error('Actual canvas bounds unavailable');
  const projected = new Vector3(...target.world).applyMatrix4(new Matrix4().fromArray(camera.matrixWorld).invert()).applyMatrix4(new Matrix4().fromArray(camera.projectionMatrix));
  expect(Math.abs(projected.x)).toBeLessThanOrEqual(1);
  expect(Math.abs(projected.y)).toBeLessThanOrEqual(1);
  await page.mouse.click(bounds.x + (projected.x + 1) * bounds.width / 2, bounds.y + (1 - projected.y) * bounds.height / 2);
}

export async function ready(page: Page, request: APIRequestContext): Promise<World> {
  const world = await readWorld(request);
  await expect(page.getByTestId('simulation-step')).toBeEnabled();
  return world;
}

export async function stepUntil(request: APIRequestContext, predicate: (world: World) => boolean, maxSteps = 120): Promise<World> {
  let world = await readWorld(request);
  for (let step = 0; step <= maxSteps; step += 1) {
    if (predicate(world)) return world;
    if (step === maxSteps) break;
    world = await sendOperation(request, { action: 'step' });
  }
  throw new Error(`Condition was not reached after ${maxSteps} simulation steps`);
}

export async function recordJson(testInfo: TestInfo, name: string, value: unknown): Promise<string> {
  const path = testInfo.outputPath(`${name}.json`);
  await mkdir(dirname(path), { recursive: true });
  await writeFile(path, JSON.stringify(value, null, 2));
  await testInfo.attach(name, { path, contentType: 'application/json' });
  return path;
}

export async function runSnapshot(page: Page, request: APIRequestContext, testInfo: TestInfo, name: string): Promise<World> {
  const world = await readWorld(request);
  await expect(page.getByRole('progressbar', { name: '전체 실행 진행률', exact: true })).toHaveAttribute('value', String(world.run.elapsed_ms));
  await recordJson(testInfo, `${name}-world`, world);
  const path = testInfo.outputPath(`${name}.png`);
  await page.screenshot({ path, fullPage: true });
  await testInfo.attach(name, { path, contentType: 'image/png' });
  return world;
}

export type BrowserFailure = { kind: 'pageerror' | 'requestfailed' | 'http' | 'external' | 'console'; message: string; url?: string; atMs?: number; lineNumber?: number; columnNumber?: number };

export function captureBrowserFailures(context: BrowserContext, baseURL: string) {
  const failures: BrowserFailure[] = [];
  const origin = new URL(baseURL).origin;
  const pageHandlers = new Map<Page, (error: Error) => void>();
  const consoleHandlers = new Map<Page, (message: ConsoleMessage) => void>();
  const observePage = (page: Page) => {
    const handler = (error: Error) => failures.push({ kind: 'pageerror', message: error.message, url: page.url() });
    pageHandlers.set(page, handler);
    page.on('pageerror', handler);
    const consoleHandler = (message: ConsoleMessage): void => {
      if (message.type() === 'error') failures.push({ kind: 'console', message: message.text(), ...message.location(), atMs: Date.now() });
    };
    consoleHandlers.set(page, consoleHandler);
    page.on('console', consoleHandler);
  };
  const failed = (request: Request) => failures.push({ kind: 'requestfailed', message: request.failure()?.errorText ?? 'Unknown network failure', url: request.url() });
  const response = (item: Response) => {
    if (item.status() >= 400) failures.push({ kind: 'http', message: `HTTP ${item.status()}`, url: item.url() });
  };
  const request = (item: Request) => {
    const url = new URL(item.url());
    if (['http:', 'https:', 'ws:', 'wss:'].includes(url.protocol) && url.origin !== origin) {
      failures.push({ kind: 'external', message: `Unexpected external request: ${url.origin}`, url: item.url() });
    }
  };
  context.pages().forEach(observePage);
  context.on('page', observePage);
  context.on('requestfailed', failed);
  context.on('response', response);
  context.on('request', request);
  return {
    failures,
    assertHealthy() {
      if (failures.length) throw new Error(`Browser failures detected: ${JSON.stringify(failures)}`);
    },
    dispose() {
      context.off('page', observePage);
      context.off('requestfailed', failed);
      context.off('response', response);
      context.off('request', request);
      for (const [page, handler] of pageHandlers) page.off('pageerror', handler);
      for (const [page, handler] of consoleHandlers) page.off('console', handler);
    },
  };
}

export const test = base.extend<{ browserFailures: ReturnType<typeof captureBrowserFailures> }>({
  browserFailures: [async ({ context, baseURL, request }, use, testInfo) => {
    if (!baseURL) throw new Error('The operations harness requires a baseURL');
    const capture = captureBrowserFailures(context, baseURL);
    const ownership = await guardBrowserMutations(context);
    try {
      await use(capture);
    } finally {
      try {
        if ((await readWorld(request)).run.playing) await sendOperation(request, { action: 'pause' });
      } finally {
        await ownership.dispose();
        capture.dispose();
        await recordJson(testInfo, 'ownership-refusals', ownership.refused);
        await recordJson(testInfo, 'browser-failures', capture.failures);
      }
      expect(ownership.refused).toEqual([]);
      capture.assertHealthy();
    }
  }, { auto: true }],
});
