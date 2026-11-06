import { expect, test as base } from '@playwright/test';
import { z } from 'zod';
import { existsSync, readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { Matrix4, Quaternion, Vector3 } from 'three';
import type { Page, Request as BrowserRequest, Response as BrowserResponse } from '@playwright/test';
import type { BrowserFailure } from './helpers/operations';
import { captureBrowserFailures, clickOperation, readWorld, recordJson, resetScenario } from './helpers/operations';
import { guardBrowserMutations, readQaIdentity } from './helpers/qaIdentity';

const transformShape = z.object({ position_m: z.tuple([z.number(), z.number(), z.number()]), rotation_xyzw: z.tuple([z.number(), z.number(), z.number(), z.number()]) });
const actualManifest = z.object({ assets: z.array(z.object({ id: z.string(), kind: z.string(),
  nodes: z.array(z.object({ id: z.string(), parent_id: z.string().nullable(), transform: transformShape })),
  sockets: z.array(z.object({ id: z.string(), node_id: z.string(), transform: transformShape, normal: z.tuple([z.number(), z.number(), z.number()]) })),
})) }).parse(JSON.parse(readFileSync('public/assets/steelworks/manifest.json', 'utf8')));
const compose = (value: z.infer<typeof transformShape>) => new Matrix4().compose(new Vector3(...value.position_m), new Quaternion(...value.rotation_xyzw), new Vector3(1, 1, 1));
function authoredSocketFrames(asset: typeof actualManifest.assets[number]) {
  const ancestors = (id: string): Matrix4 => {
    const node = asset.nodes.find(row => row.id === id);
    if (!node) throw new RangeError(`Authored node missing: ${id}`);
    return (node.parent_id === null ? new Matrix4() : ancestors(node.parent_id)).multiply(compose(node.transform));
  };
  return asset.sockets.map(socket => {
    const matrix = ancestors(socket.node_id).multiply(compose(socket.transform));
    return { id: socket.id, matrix: matrix.toArray(), position: new Vector3().setFromMatrixPosition(matrix).toArray(), normal: new Vector3(...socket.normal).transformDirection(matrix).toArray() };
  });
}
function expectAuthoredFrames(actual: Awaited<ReturnType<typeof state>>, kind: string): void {
  const asset = actualManifest.assets.find(row => row.kind === kind);
  if (!asset) throw new RangeError(`Authored asset missing: ${kind}`);
  for (const expected of authoredSocketFrames(asset)) {
    const socket = actual.sockets.find(row => row.id === expected.id);
    expect(socket).toBeDefined();
    for (const field of ['matrix', 'position', 'normal'] as const) expected[field].forEach((value, i) => expect(socket?.[field][i]).toBeCloseTo(value, 5));
  }
}
function deferred() {
  let resolve: () => void = () => { throw new Error('Deferred not initialized'); };
  const promise = new Promise<void>(accept => { resolve = accept; });
  return { promise, resolve };
}

const entry = '/tests/fixtures/factory-assets/index.html';
const vector = z.array(z.number()).length(3), quaternion = z.array(z.number()).length(4);
const part = z.object({ id: z.string(), uuid: z.string().optional(), position: vector, quaternion, matrix: z.array(z.number()).optional(), state: z.number().nullable().optional() });
const handles = z.array(z.object({ node: z.string(), geometry: z.string(), materials: z.array(z.string()) }));
const stateShape = z.object({ key: z.string(), identity: z.object({ run_id: z.string(), entity_type: z.string(), entity_id: z.string(), bundle_hash: z.string() }), rootUuid: z.string(), lod: z.number().nullable(), selected: z.boolean(), cutaway: z.boolean(), roofs: z.array(z.string()), parts: z.array(part),
  sockets: z.array(z.object({ id: z.string(), matrix: z.array(z.number()).length(16), position: vector, normal: vector })), handles,
  comparison: z.object({ key: z.string(), lod: z.number().nullable(), handles, parts: z.array(part) }), resourceLeases: z.array(z.object({ key: z.string(), refcount: z.number(), loaded: z.boolean() })), pose: z.object({ run_id: z.string(), attachment_id: z.string(), owner_id: z.string(), socket_id: z.string(), position_m: vector, contact_m: vector, orientation_xyzw: quaternion, material: z.object({ material_id: z.string(), material_version_id: z.string(), form: z.string() }).passthrough(), channels: z.array(z.object({ function_id: z.string(), kind: z.string(), value: z.number() }).passthrough()) }).passthrough(), authorityElapsedMs: z.number(), triangles: z.number(),
  materialNodes: z.array(z.object({ id: z.string(), attachmentId: z.string(), versionId: z.string(), position: vector, matrix: z.array(z.number()).length(16), min: vector, max: vector })),
  renderer: z.object({ calls: z.number(), geometries: z.number(), textures: z.number() }), camera: z.object({ position: vector, matrixWorld: z.array(z.number()).length(16), projectionMatrix: z.array(z.number()).length(16) }), pick: z.object({ x: z.number(), y: z.number(), world: vector }),
});
async function state(page: Page) {
  const canvas = page.locator('canvas');
  await expect(canvas).toHaveAttribute('data-asset-state', /.*/);
  return stateShape.parse(JSON.parse(await canvas.getAttribute('data-asset-state') ?? '{}'));
}
const probeEventShape = z.object({ mode: z.string(), event: z.string(), url: z.string(), probe_request_id: z.string().nullable(), status_code: z.number().optional(), pid: z.number(), at_ms: z.number() });
// Event recording deliberately fills response/failure fields on the same request identity.
type RequestObservation = { readonly id: number; readonly url: string; readonly method: string; readonly started_at_ms: number; status?: number; status_at_ms?: number; failure?: string; failed_at_ms?: number; mode?: string; probe_request_id?: string };
type AssetObservations = ReturnType<typeof captureBrowserFailures> & { readonly requestRows: Map<BrowserRequest, RequestObservation> };
type AuditedFailure = { readonly failure: BrowserFailure; readonly request_id: number | undefined };
type FailureContext = { readonly case_id: string; readonly baseURL: string; readonly requests: readonly RequestObservation[]; readonly events: readonly Readonly<z.infer<typeof probeEventShape>>[]; readonly previewPid: number };

function isExpectedAssetFailure(observation: AuditedFailure, context: FailureContext): boolean {
  const failure = observation.failure, ownedGlb = new URL('/assets/steelworks/shear-lod2.glb', context.baseURL).href;
  const target = new URL('/__t13_redirect_target__', context.baseURL).href;
  const console404 = 'Failed to load resource: the server responded with a status of 404 (Not Found)';
  if (context.case_id === 'missing_asset_2d') {
    const requests = context.requests.filter(row => row.url === ownedGlb && row.method === 'GET');
    const row = requests.length === 1 ? requests[0] : undefined;
    if (!row || row.status !== 404 || failure.url !== ownedGlb) return false;
    switch (failure.kind) {
      case 'http': return observation.request_id === row.id && failure.message === 'HTTP 404';
      case 'console': return failure.message === console404;
      case 'requestfailed': return observation.request_id === row.id && failure.message === 'net::ERR_ABORTED' && row.failure === failure.message && (row.status_at_ms ?? Infinity) <= (row.failed_at_ms ?? -Infinity);
      case 'pageerror':
      case 'external': return false;
      default: { const exhaustive: never = failure.kind; throw new RangeError(exhaustive); }
    }
  }
  if (context.case_id !== 'network_asset_2d') return false;
  const pair = (mode: string, status: number, error: string): RequestObservation | undefined => {
    const rows = context.requests.filter(row => row.url === ownedGlb && row.method === 'GET' && row.mode === mode && row.probe_request_id === `t13-${mode}` && row.failure === error && (row.status === status || (mode === 'redirect' && row.status === undefined)));
    const row = rows.length === 1 ? rows[0] : undefined;
    if (!row) return undefined;
    const sameRequest = context.events.filter(event => event.mode === mode && event.probe_request_id === row.probe_request_id && event.url === '/assets/steelworks/shear-lod2.glb' && event.pid === context.previewPid);
    if (sameRequest.filter(event => event.event === 'request').length !== 1 || sameRequest.filter(event => event.event === 'close' && event.status_code === status).length !== 1) return undefined;
    return row;
  };
  const header = pair('headers-only', 200, 'net::ERR_ABORTED'), missing = pair('stalled-404', 404, 'net::ERR_ABORTED');
  const redirect = pair('redirect', 302, 'net::ERR_FAILED'), cancelled = pair('caller-abort', 200, 'net::ERR_ABORTED');
  switch (failure.kind) {
    case 'requestfailed': return failure.url === ownedGlb && [header, missing, redirect, cancelled].some(row => row !== undefined && row.id === observation.request_id && row.failure === failure.message);
    case 'http': return failure.url === ownedGlb && failure.message === 'HTTP 404' && missing !== undefined && observation.request_id === missing.id;
    case 'console':
      if (failure.url === ownedGlb && failure.message === console404) return missing !== undefined;
      return failure.url === target && failure.message === 'Failed to load resource: net::ERR_FAILED' && redirect !== undefined && context.requests.every(row => row.url !== target) && context.events.every(event => event.event !== 'target-hit');
    case 'pageerror':
    case 'external': return false;
    default: { const exhaustive: never = failure.kind; throw new RangeError(exhaustive); }
  }
}

const test = base.extend<{ observations: AssetObservations }>({
  observations: [async ({ context, baseURL }, use, testInfo) => {
    if (!baseURL) throw new Error('Owned base URL is required');
    const capture = captureBrowserFailures(context, baseURL), guard = await guardBrowserMutations(context);
    const identity = await readQaIdentity(), failureRequestIds = new Map<BrowserFailure, number>();
    const requests: RequestObservation[] = [], requestRows = new Map<BrowserRequest, RequestObservation>();
    const recordRequest = (request: BrowserRequest): void => { const row = { id: requests.length + 1, url: request.url(), method: request.method(), started_at_ms: Date.now() }; requests.push(row); requestRows.set(request, row); };
    const recordResponse = (response: BrowserResponse): void => {
      const row = requestRows.get(response.request()); if (!row) return;
      row.status = response.status(); row.status_at_ms = Date.now();
      const failure = capture.failures.at(-1); if (response.status() >= 400 && failure?.kind === 'http' && failure.url === row.url && failure.message === `HTTP ${response.status()}`) failureRequestIds.set(failure, row.id);
    };
    const recordFailure = (request: BrowserRequest): void => {
      const row = requestRows.get(request); if (!row) return;
      row.failure = request.failure()?.errorText ?? 'Unknown network failure'; row.failed_at_ms = Date.now();
      const failure = capture.failures.at(-1); if (failure?.kind === 'requestfailed' && failure.url === row.url && failure.message === row.failure) failureRequestIds.set(failure, row.id);
    };
    context.on('request', recordRequest);
    context.on('response', recordResponse); context.on('requestfailed', recordFailure);
    try { await use({ ...capture, requestRows }); }
    finally {
      await guard.dispose(); capture.dispose();
      context.off('request', recordRequest);
      context.off('response', recordResponse); context.off('requestfailed', recordFailure);
      const ownedGlb = new URL('/assets/steelworks/shear-lod2.glb', baseURL).href, redirectTarget = new URL('/__t13_redirect_target__', baseURL).href;
      const paired404Abort = requests.filter(row => row.url === ownedGlb && row.status === 404 && row.failure === 'net::ERR_ABORTED' && (row.status_at_ms ?? Infinity) <= (row.failed_at_ms ?? -Infinity));
      const evidence = process.env.STEELFLOW_EVIDENCE_DIR, probeLog = evidence ? resolve(evidence, 'asset-http-probes.jsonl') : null;
      const probeEvents = probeLog && existsSync(probeLog) ? readFileSync(probeLog, 'utf8').trim().split('\n').filter(Boolean).map(line => probeEventShape.parse(JSON.parse(line))) : [];
      const redirectRequests = requests.filter(row => row.url === ownedGlb && row.mode === 'redirect' && row.failure === 'net::ERR_FAILED');
      const targetRequests = requests.filter(row => row.url === redirectTarget), targetHits = probeEvents.filter(row => row.event === 'target-hit');
      const redirectCloses = probeEvents.filter(row => row.mode === 'redirect' && row.event === 'close' && row.status_code === 302 && redirectRequests.some(request => request.probe_request_id === row.probe_request_id));
      const classificationContext: FailureContext = { case_id: testInfo.title.split(' ', 1)[0] ?? '', baseURL, requests, events: probeEvents, previewPid: identity.web_pid };
      const audited = capture.failures.map(failure => ({ failure, request_id: failureRequestIds.get(failure) }));
      const expected = audited.filter(row => isExpectedAssetFailure(row, classificationContext)).map(row => row.failure);
      const redirectConsole = expected.filter(item => item.kind === 'console' && item.url === redirectTarget);
      const missingAbortCount = capture.failures.filter(item => item.kind === 'requestfailed' && item.url === ownedGlb && item.message === 'net::ERR_ABORTED').length;
      const unexpected = capture.failures.filter(item => !expected.includes(item));
      await recordJson(testInfo, 'asset-browser-observations', { all: capture.failures, audited, expected, unexpected, refusedMutations: guard.refused, paired404Abort, missingAbortCount, redirectRequests, redirectCloses, targetRequests, targetHits, redirectConsoleCount: redirectConsole.length });
      await recordJson(testInfo, 'asset-network', { requests, external: requests.filter(row => /^https?:/.test(row.url) && new URL(row.url).origin !== new URL(baseURL).origin) });
      if (testInfo.title.startsWith('missing_asset_2d')) { expect(requests.filter(row => row.url === ownedGlb)).toHaveLength(1); expect(requests.filter(row => row.url === ownedGlb && row.status === 404)).toHaveLength(1); expect(paired404Abort.length).toBeLessThanOrEqual(1); expect(missingAbortCount).toBeLessThanOrEqual(1); }
      if (testInfo.title.startsWith('network_asset_2d')) { expect(redirectRequests).toHaveLength(1); expect(redirectCloses).toHaveLength(1); expect(redirectConsole.length).toBeLessThanOrEqual(1); expect(targetRequests).toEqual([]); expect(targetHits).toEqual([]); expect(requests.filter(row => row.url === ownedGlb)).toHaveLength(4); }
      expect(guard.refused).toEqual([]); expect(unexpected).toEqual([]);
    }
  }, { auto: true }],
});

test('actual_glb_identity retains real geometry, selection, LOD, paused pose and shared ownership', async ({ page, request, observations }, testInfo) => {
  test.setTimeout(120_000);
  // Given: the live legacy API clock and the fixed T58 contract clock are deliberately separate.
  const identity = await readQaIdentity();
  const initialApi = await resetScenario(request);
  await page.goto(entry);
  await expect(page.getByTestId('load-status')).toHaveText('실제 모델 표시');
  await expect(page.getByTestId('simulation-play-pause')).toBeEnabled();
  await expect(page.locator('canvas')).toBeVisible();
  const initial = await state(page);
  expect(initial.triangles).toBeGreaterThan(100); expectAuthoredFrames(initial, 'shear');
  expect(initial.resourceLeases).toHaveLength(1); expect(initial.resourceLeases[0]?.refcount).toBe(2);
  expect(initial.handles.map(item => item.geometry)).toEqual(initial.comparison.handles.map(item => item.geometry));
  expect(initial.handles.map(item => item.materials)).toEqual(initial.comparison.handles.map(item => item.materials));
  expect(initial.parts.find(p => p.id === 'cutting_tool')?.position[1]).toBeCloseTo(1.56, 5);
  expect(initial.pose).toMatchObject({ run_id: 'factory-contract-run', owner_id: 'CUT-SLAB', socket_id: 'work', attachment_id: 'custody-stock-coil', material: { material_id: 'stock-coil', material_version_id: 'stock-coil-v1', form: 'SLAB' }, position_m: [expect.closeTo(0.3, 5), expect.closeTo(1.15, 5), 0], contact_m: [expect.closeTo(0.3, 5), expect.closeTo(1.05, 5), 0] });
  expect(initial.pose.channels.find(channel => channel.function_id === 'cutting_tool')?.value).toBeCloseTo(0.24, 6);
  expect(initial.materialNodes).toHaveLength(1); expect(initial.materialNodes[0]).toMatchObject({ id: 'stock-coil', attachmentId: 'custody-stock-coil', versionId: 'stock-coil-v1' });
  expect(initial.materialNodes[0]?.min[1]).toBeCloseTo(1.05, 5);
  expect(initial.comparison.parts.find(p => p.id === 'cutting_tool')?.position[1]).toBeCloseTo(1.8, 5);
  const samples = [initial];
  // When: literal browser interactions with real raycast geometry and the registered controls.
  await page.locator('canvas').scrollIntoViewIfNeeded();
  const bounds = await page.locator('canvas').boundingBox();
  if (!bounds) throw new Error('Actual canvas bounds missing');
  const projected = new Vector3().fromArray(initial.pick.world).applyMatrix4(new Matrix4().fromArray(initial.camera.matrixWorld).invert()).applyMatrix4(new Matrix4().fromArray(initial.camera.projectionMatrix));
  const target = { x: bounds.x + (projected.x + 1) * bounds.width / 2, y: bounds.y + (1 - projected.y) * bounds.height / 2 };
  const hoveredIdentity = async () => stateShape.shape.identity.nullable().parse(JSON.parse(await page.getByTestId('hovered-entity').getAttribute('data-hover-identity') ?? 'null'));
  await page.mouse.move(target.x, target.y);
  await expect.poll(hoveredIdentity).toEqual(initial.identity);
  await page.mouse.move(10, 10); await expect.poll(hoveredIdentity).toBeNull();
  await page.mouse.click(target.x, target.y);
  await expect(page.getByRole('button', { name: '이 개체 선택', exact: true })).toHaveAttribute('aria-pressed', 'true');
  for (const lod of [1, 2, 0]) {
    await page.getByRole('button', { name: `LOD ${lod}`, exact: true }).click();
    await expect.poll(async () => (await state(page)).lod).toBe(lod);
    const current = await state(page); samples.push(current); expectAuthoredFrames(current, 'shear');
    await page.screenshot({ path: testInfo.outputPath(`shear-lod${lod}.png`), fullPage: true });
    expect(current.key).toBe(initial.key); expect(current.rootUuid).toBe(initial.rootUuid); expect(current.selected).toBe(true);
    await page.locator('canvas').scrollIntoViewIfNeeded();
    const actualBounds = await page.locator('canvas').boundingBox();
    if (!actualBounds) throw new Error('Actual hover canvas bounds missing');
    const pointer = new Vector3().fromArray(current.pick.world).applyMatrix4(new Matrix4().fromArray(current.camera.matrixWorld).invert()).applyMatrix4(new Matrix4().fromArray(current.camera.projectionMatrix));
    await page.mouse.move(actualBounds.x + (pointer.x + 1) * actualBounds.width / 2, actualBounds.y + (1 - pointer.y) * actualBounds.height / 2);
    await expect.poll(hoveredIdentity).toEqual(initial.identity);
    await page.mouse.move(10, 10); await expect.poll(hoveredIdentity).toBeNull();
    expect(current.parts.find(p => p.id === 'cutting_tool')?.position[1]).toBeCloseTo(1.56, 5);
    expect(current.sockets.find(s => s.id === 'work')?.position).toEqual([expect.closeTo(0.3, 5), expect.closeTo(1.05, 5), 0]);
    expect(current.materialNodes).toHaveLength(1); expect(current.materialNodes[0]?.min[1]).toBeCloseTo(1.05, 5);
  }
  await page.getByRole('button', { name: '지붕 절개 · 지붕 없음', exact: true }).click();
  await expect.poll(async () => (await state(page)).cutaway).toBe(true);
  expect((await state(page)).roofs).toEqual([]);
  await page.getByRole('button', { name: '범위 나가기', exact: true }).click();
  await expect.poll(async () => (await state(page)).resourceLeases).toEqual([]);
  const empty = await state(page); expect(empty.triangles).toBe(0);
  await page.getByRole('button', { name: '같은 개체 재진입', exact: true }).click();
  await expect(page.getByTestId('load-status')).toHaveText('실제 모델 표시');
  expect((await state(page)).key).toBe(initial.key); expect((await state(page)).rootUuid).toBe(initial.rootUuid);
  for (const angle of ['정면', '측면', '후면']) {
    await page.getByRole('button', { name: angle, exact: true }).click();
    await page.screenshot({ path: testInfo.outputPath(`shear-${angle}.png`), fullPage: true });
    await recordJson(testInfo, `shear-${angle}-nodes`, await state(page));
  }
  const held = deferred(), release = deferred();
  await page.route('**/assets/steelworks/shear-lod1.glb', async route => { const response = await route.fetch(); held.resolve(); await release.promise; await route.fulfill({ response }); });
  await clickOperation(page, 'simulation-play-pause', '/api/v1/simulation/play');
  await page.getByRole('button', { name: 'LOD 1', exact: true }).click(); await held.promise;
  const pausedApi = await clickOperation(page, 'simulation-play-pause', '/api/v1/simulation/pause');
  const beforeResolve = await state(page); release.resolve();
  await expect.poll(async () => (await state(page)).lod).toBe(1);
  const afterResolve = await state(page), finalApi = await readWorld(request);
  expect(finalApi.run).toEqual(pausedApi.run); expect(afterResolve.pose).toEqual(beforeResolve.pose); expect(afterResolve.authorityElapsedMs).toBe(1000);
  expect(afterResolve.key).toBe(initial.key); expect(afterResolve.selected).toBe(true);
  await page.unroute('**/assets/steelworks/shear-lod1.glb');
  await page.reload(); await expect(page.getByTestId('load-status')).toHaveText('실제 모델 표시');
  expect((await state(page)).key).toBe(initial.key); expect((await state(page)).selected).toBe(true); expect((await state(page)).cutaway).toBe(true);
  const galvanizing = actualManifest.assets.find(asset => asset.kind === 'galvanizing');
  if (!galvanizing) throw new RangeError('Actual galvanizing asset missing');
  await page.getByRole('combobox', { name: '실제 자산', exact: true }).selectOption(galvanizing.id);
  await expect(page.getByTestId('selected-entity')).toHaveText('CS-GI-05');
  await expect(page.getByTestId('load-status')).toHaveText('실제 모델 표시');
  const fixedPose = (await state(page)).pose;
  const galvanizingSamples = [];
  for (const lod of [0, 1, 2]) {
    await page.getByRole('button', { name: `LOD ${lod}`, exact: true }).click();
    await expect.poll(async () => (await state(page)).lod).toBe(lod);
    const current = await state(page); galvanizingSamples.push(current); expectAuthoredFrames(current, 'galvanizing');
    await page.screenshot({ path: testInfo.outputPath(`galvanizing-lod${lod}.png`), fullPage: true });
    expect(current.pose).toEqual(fixedPose); expect(current.parts.find(p => p.id === 'air_knife')?.state).toBeCloseTo(0.5, 5);
    expect(current.pose).toMatchObject({ run_id: 'factory-contract-run', owner_id: 'CS-GI-05', socket_id: 'work', attachment_id: 'custody-stock-coil', material: { material_id: 'stock-coil', material_version_id: 'stock-coil-v1', form: 'STRIP' }, position_m: [0, expect.closeTo(1.761, 5), 0], contact_m: [0, expect.closeTo(1.76, 5), 0] });
    expect(current.pose.orientation_xyzw).toEqual([0, 0, 0, 1]);
    expect(current.pose.channels.find(channel => channel.function_id === 'sink_roll')?.value).toBeCloseTo(Math.PI, 6);
    expect(current.parts.find(p => p.id === 'sink_roll')?.position).toEqual([0, expect.closeTo(0.85, 5), 0]);
    expect(current.parts.find(p => p.id === 'sink_roll')?.quaternion).toEqual([0, 0, expect.closeTo(1, 6), expect.closeTo(0, 6)]);
    expect(current.parts.find(p => p.id === 'air_knife')?.position).toEqual([expect.closeTo(0.7, 5), expect.closeTo(2.05, 5), 0]);
    expect(current.parts.find(p => p.id === 'air_knife')?.quaternion).toEqual([0, 0, 0, 1]);
    expect(current.materialNodes).toHaveLength(1); expect(current.materialNodes[0]?.min[1]).toBeCloseTo(1.76, 5);
    expect(current.parts.find(p => p.id === 'sink_roll')?.quaternion).not.toEqual(current.comparison.parts.find(p => p.id === 'sink_roll')?.quaternion);
  }
  for (const angle of ['정면', '측면', '후면']) {
    await page.getByRole('button', { name: angle, exact: true }).click();
    await page.screenshot({ path: testInfo.outputPath(`galvanizing-${angle}.png`), fullPage: true });
    await recordJson(testInfo, `galvanizing-${angle}-nodes`, await state(page));
  }
  await page.getByRole('button', { name: '범위 나가기', exact: true }).click();
  await expect.poll(async () => (await state(page)).resourceLeases).toEqual([]);
  // Then
  expect(observations.failures.filter(f => f.kind === 'external')).toEqual([]);
  await recordJson(testInfo, 'actual-glb-identity', { identity, initialApi: initialApi.run, pausedApi: pausedApi.run, finalApi: finalApi.run, initial, samples, empty, beforeResolve, afterResolve, galvanizingSamples, final: await state(page), limits: ['fixed synthetic T58 pose; separate live legacy clock', 'no real roof nodes; no hall cutaway claim', 'two representatives only; T30 full scene pending'] });
});

test('missing_asset_2d exposes the real 404 and keeps the selected entity and accessible data', async ({ page, request, observations }, testInfo) => {
  // Given
  const api = await resetScenario(request);
  await page.goto(entry); await expect(page.getByTestId('load-status')).toHaveText('실제 모델 표시');
  const before = await state(page);
  await page.getByRole('button', { name: '이 개체 선택', exact: true }).focus(); await page.keyboard.press('Space');
  await expect(page.getByRole('button', { name: '이 개체 선택', exact: true })).toHaveAttribute('aria-pressed', 'true');
  await page.route('**/assets/steelworks/shear-lod2.glb', route => route.fulfill({ status: 404, contentType: 'text/plain', body: 'Intentionally missing owned GLB' }));
  // When
  await page.getByRole('button', { name: 'LOD 2', exact: true }).focus(); await page.keyboard.press('Enter');
  // Then
  await expect(page.getByTestId('asset-error')).toContainText('network');
  await expect(page.getByTestId('asset-2d')).toContainText('CUT-SLAB');
  await expect(page.getByTestId('asset-2d')).toContainText('1000 ms');
  await expect(page.locator('.notice[role="status"]')).toBeFocused();
  await expect(page.getByRole('button', { name: '이 개체 선택', exact: true })).toHaveAttribute('aria-pressed', 'true');
  await expect(page.locator('canvas')).toHaveCount(0);
  expect((await readWorld(request)).run).toEqual(api.run);
  expect(observations.failures.filter(f => f.kind === 'external')).toEqual([]);
  await page.screenshot({ path: testInfo.outputPath('actual-404-accessible-2d.png'), fullPage: true });
  await recordJson(testInfo, 'missing-asset-2d', { api: api.run, before, url: page.url(), selected: await page.getByTestId('selected-entity').textContent(), fallback: await page.getByTestId('asset-2d').textContent(), fixedPose: await page.getByTestId('fixed-pose').textContent() });
});

test('corrupt_asset_2d rejects altered real bytes and recovers the same selection after a clean reload', async ({ page, request }, testInfo) => {
  // Given
  const api = await resetScenario(request);
  await page.goto(entry); await expect(page.getByTestId('load-status')).toHaveText('실제 모델 표시');
  await page.getByRole('button', { name: '이 개체 선택', exact: true }).click();
  const before = await state(page);
  await page.route('**/assets/steelworks/shear-lod2.glb', async route => {
    const response = await route.fetch(), bytes = await response.body();
    bytes[100] = 0;
    await route.fulfill({ response, body: bytes });
  });
  // When
  await page.getByRole('button', { name: 'LOD 2', exact: true }).click();
  // Then
  await expect(page.getByTestId('asset-error')).toContainText('hash');
  await expect(page.getByTestId('asset-2d')).toContainText('CUT-SLAB');
  await expect(page.locator('.notice[role="status"]')).toBeFocused();
  await expect(page.getByRole('button', { name: '이 개체 선택', exact: true })).toHaveAttribute('aria-pressed', 'true');
  expect((await readWorld(request)).run).toEqual(api.run);
  await page.screenshot({ path: testInfo.outputPath('actual-corrupt-accessible-2d.png'), fullPage: true });
  const failure = { text: await page.getByTestId('asset-error').textContent(), fallback: await page.getByTestId('asset-2d').textContent() };
  await page.unroute('**/assets/steelworks/shear-lod2.glb');
  await page.getByRole('button', { name: '로컬 자산 다시 읽기', exact: true }).click();
  await expect(page.getByTestId('load-status')).toHaveText('실제 모델 표시');
  await expect(page.getByTestId('asset-error')).toHaveCount(0);
  await page.getByRole('button', { name: '2D 자료', exact: true }).click();
  await expect(page.locator('canvas')).toBeVisible();
  const recovered = await state(page);
  expect(recovered.key).toBe(before.key); expect(recovered.rootUuid).toBe(before.rootUuid); expect(recovered.selected).toBe(true);
  expect(recovered.lod).toBe(2); expect(recovered.pose).toEqual(before.pose);
  await recordJson(testInfo, 'corrupt-asset-2d', { before, failure, recovered, finalApi: (await readWorld(request)).run });
});

test('network_asset_2d bounds real Chrome bodies, rejects redirects and cancels the owned in-flight load', async ({ page, request, observations }, testInfo) => {
  test.setTimeout(70_000);
  // Given: only this test's opt-in preview middleware changes responses at the owned same-origin GLB URL.
  const identity = await readQaIdentity(), api = await resetScenario(request), samples = [];
  const evidence = process.env.STEELFLOW_EVIDENCE_DIR;
  if (!evidence) throw new Error('Owned browser evidence is required');
  const logPath = resolve(evidence, 'asset-http-probes.jsonl');
  const events = () => existsSync(logPath) ? readFileSync(logPath, 'utf8').trim().split('\n').filter(Boolean).map(line => probeEventShape.parse(JSON.parse(line))) : [];
  for (const mode of ['headers-only', 'stalled-404', 'redirect', 'caller-abort'] as const) {
    await page.goto(entry); await expect(page.getByTestId('load-status')).toHaveText('실제 모델 표시');
    await page.getByRole('button', { name: '이 개체 선택', exact: true }).click();
    const before = await state(page);
    await page.route('**/assets/steelworks/shear-lod2.glb', route => {
      const row = observations.requestRows.get(route.request()); if (!row) throw new Error('Original owned request identity missing');
      row.mode = mode; row.probe_request_id = `t13-${mode}`;
      return route.continue({ headers: { ...route.request().headers(), 'x-steelflow-asset-probe': mode, 'x-steelflow-asset-probe-id': row.probe_request_id } });
    });
    const started = Date.now();
    // When
    await page.getByRole('button', { name: 'LOD 2', exact: true }).click();
    await expect.poll(() => events().filter(row => row.mode === mode && row.event === 'request').length).toBe(1);
    if (mode === 'caller-abort') {
      await expect.poll(() => events().filter(row => row.mode === mode && row.event === 'headers-flushed').length).toBe(1);
      await page.getByRole('button', { name: '범위 나가기', exact: true }).click();
      // Then
      await expect(page.getByTestId('load-status')).toHaveText('범위 밖 · 같은 선택 유지');
      await expect.poll(async () => (await state(page)).resourceLeases).toEqual([]);
      expect((await state(page)).key).toBe(before.key); expect((await state(page)).selected).toBe(true);
      await expect(page.getByTestId('asset-error')).toHaveCount(0);
    } else {
      // Then
      await expect(page.getByTestId('asset-error')).toContainText('network', { timeout: 19_000 });
      await expect(page.getByTestId('asset-2d')).toContainText('CUT-SLAB');
      await expect(page.locator('.notice[role="status"]')).toBeFocused();
      await expect(page.getByRole('button', { name: '이 개체 선택', exact: true })).toHaveAttribute('aria-pressed', 'true');
    }
    const elapsed = Date.now() - started;
    if (mode === 'headers-only') { expect(elapsed).toBeGreaterThanOrEqual(14_000); expect(elapsed).toBeLessThan(19_000); }
    else expect(elapsed).toBeLessThan(3000);
    await expect.poll(() => events().filter(row => row.mode === mode && row.event === 'close').length).toBe(1);
    expect(events().filter(row => row.event === 'target-hit')).toEqual([]);
    expect((await readWorld(request)).run).toEqual(api.run);
    samples.push({ mode, before, elapsed_ms: elapsed, events: events().filter(row => row.mode === mode) });
    await page.screenshot({ path: testInfo.outputPath(`actual-http-${mode}.png`), fullPage: true });
    await page.unroute('**/assets/steelworks/shear-lod2.glb');
  }
  expect(events().every(row => row.pid === identity.web_pid)).toBe(true);
  expect(events().filter(row => row.event === 'request')).toHaveLength(4);
  const classificationContext: FailureContext = { case_id: 'network_asset_2d', baseURL: identity.web_origin, requests: [...observations.requestRows.values()], events: events(), previewPid: identity.web_pid };
  const header = classificationContext.requests.find(row => row.mode === 'headers-only'); if (!header) throw new Error('Actual headers-only request absent');
  const ownedGlb = new URL('/assets/steelworks/shear-lod2.glb', identity.web_origin).href;
  const counterexamples: readonly { readonly name: string; readonly observation: AuditedFailure }[] = [
    { name: 'unknown_console_404', observation: { failure: { kind: 'console', message: 'Unrelated invariant failure: count 404 is invalid', url: ownedGlb }, request_id: undefined } },
    { name: 'headers_only_wrong_err_failed', observation: { failure: { kind: 'requestfailed', message: 'net::ERR_FAILED', url: ownedGlb }, request_id: header.id } },
    { name: 'foreign_origin_same_suffix', observation: { failure: { kind: 'requestfailed', message: 'net::ERR_ABORTED', url: 'https://unowned.invalid/assets/steelworks/shear-lod2.glb' }, request_id: header.id } },
  ];
  for (const example of counterexamples) expect(isExpectedAssetFailure(example.observation, classificationContext)).toBe(false);
  expect(isExpectedAssetFailure({ failure: { kind: 'requestfailed', message: 'net::ERR_ABORTED', url: ownedGlb }, request_id: header.id }, classificationContext)).toBe(true);
  await recordJson(testInfo, 'asset-http-regressions', { identity, api: api.run, samples, events: events(), redirect_target_requests: 0, external_requests_expected: 0, classificationCounterexamples: counterexamples.map(row => ({ name: row.name, expected: false, actual: isExpectedAssetFailure(row.observation, classificationContext) })), legitimate_headers_abort_classified: true });
});
