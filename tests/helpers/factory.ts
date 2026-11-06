import { createHash } from 'node:crypto';
import { readFile, stat, writeFile } from 'node:fs/promises';
import type { Browser, Page, TestInfo } from '@playwright/test';
import { z } from 'zod';
import { captureBrowserFailures, recordJson } from './operations';
import { guardBrowserMutations, readQaIdentity } from './qaIdentity';
import { WorldSchema } from '../../src/contracts';

const finite = z.number().finite(), matrix = z.array(finite).length(16), sha = z.string().regex(/^[a-f0-9]{64}$/);
export const AuthoritySchema = z.strictObject({ source: z.literal('t58-fixed-contract'), runId: z.string().min(1), revision: z.number().int().nonnegative(), bundleHash: sha, authoritativeElapsedMs: finite.nonnegative(), stale: z.literal(false) });
export const BoundSampleSchema = z.strictObject({ authority: AuthoritySchema, sampledAtMs: finite.nonnegative(), rafSequence: z.number().int().positive(),
  nodes: z.array(z.strictObject({ entityId: z.string().min(1), id: z.string().min(1), kind: z.enum(['node', 'part', 'socket']), matrixWorld: matrix, visible: z.boolean() })).min(1).max(256),
  camera: z.strictObject({ matrixWorld: matrix, projectionMatrix: matrix }),
});
const ArtifactSchema = z.strictObject({ path: z.string().min(1), bytes: z.number().int().positive(), sha256: sha });
export type Artifact = z.infer<typeof ArtifactSchema>;
export const PixelSchema = z.strictObject({ screenshotSha256: sha, emptySha256: sha, changedPixels: z.number().int().nonnegative(), totalPixels: z.number().int().positive(), minimumPixels: z.literal(500) });
export const FactoryReceiptSchema = z.strictObject({
  schemaVersion: z.literal(1), attemptId: z.string().min(1), authority: AuthoritySchema,
  backend: z.strictObject({ runId: z.string().min(1), revision: z.number().int().nonnegative(), elapsedMs: finite.nonnegative(), payload: ArtifactSchema, custody: z.array(z.object({ materialId: z.string(), versionId: z.string(), locationId: z.string() })) }),
  samples: z.array(BoundSampleSchema).min(1), screenshot: ArtifactSchema, emptyScreenshot: ArtifactSchema, pixels: PixelSchema,
  video: z.strictObject({ artifact: ArtifactSchema, attemptId: z.string().min(1), authority: AuthoritySchema, continuous: z.literal(true), step0: z.strictObject({ sequence: z.literal(0), atMs: finite, screenshot: ArtifactSchema }), firstActionAtMs: finite }),
  trace: ArtifactSchema, chrome: z.strictObject({ artifact: ArtifactSchema, events: z.record(z.string(), z.number().int().nonnegative()), presentedFrameEvents: z.number().int().nonnegative(), presentationConfirmed: z.boolean() }),
  source: z.strictObject({ manifestSha256: sha, bundleHash: sha, projectionPayload: ArtifactSchema }), cancelled: z.literal(false),
});
export type FactoryReceipt = z.infer<typeof FactoryReceiptSchema>;
export type ReceiptExpected = { readonly attemptId: string; readonly authority: z.infer<typeof AuthoritySchema>; readonly backend: { readonly runId: string; readonly revision: number; readonly elapsedMs: number }; readonly manifestSha256: string; readonly videoSha256: string };
export class FactoryObservationError extends Error {}

export function validateFactoryReceipt(input: unknown, expected: ReceiptExpected): FactoryReceipt {
  const receipt = FactoryReceiptSchema.parse(input);
  if (receipt.attemptId !== expected.attemptId || JSON.stringify(receipt.authority) !== JSON.stringify(AuthoritySchema.parse(expected.authority))) throw new FactoryObservationError('Wrong attempt, run, revision, bundle or authoritative clock');
  if (receipt.backend.runId !== expected.backend.runId || receipt.backend.revision !== expected.backend.revision || receipt.backend.elapsedMs !== expected.backend.elapsedMs) throw new FactoryObservationError('Wrong backend run, revision or clock');
  if (receipt.source.manifestSha256 !== expected.manifestSha256 || receipt.source.bundleHash !== expected.authority.bundleHash) throw new FactoryObservationError('Dirty source or bundle');
  for (const sample of receipt.samples) {
    if (JSON.stringify(sample.authority) !== JSON.stringify(AuthoritySchema.parse(expected.authority))) throw new FactoryObservationError('Stale or mismatched sampled authority');
    if (!sample.nodes.some(node => node.kind === 'part') || !sample.nodes.some(node => node.kind === 'socket')) throw new FactoryObservationError('Real part/socket bindings missing');
  }
  if (receipt.pixels.screenshotSha256 !== receipt.screenshot.sha256 || receipt.pixels.emptySha256 !== receipt.emptyScreenshot.sha256 || receipt.screenshot.sha256 === receipt.emptyScreenshot.sha256 || receipt.pixels.changedPixels < receipt.pixels.minimumPixels || receipt.pixels.changedPixels > receipt.pixels.totalPixels) throw new FactoryObservationError('Actual screenshot pixels do not show the target object');
  if (receipt.video.attemptId !== expected.attemptId || receipt.video.artifact.sha256 !== expected.videoSha256) throw new FactoryObservationError('Wrong video attempt or captured video hash');
  if (JSON.stringify(receipt.video.authority) !== JSON.stringify(AuthoritySchema.parse(expected.authority))) throw new FactoryObservationError('Wrong video run, revision, bundle or clock');
  if (receipt.video.step0.atMs > receipt.video.firstActionAtMs) throw new FactoryObservationError('Continuous video did not start at Step 0');
  if (receipt.chrome.presentedFrameEvents !== (receipt.chrome.events['FramePresented'] ?? 0) || receipt.chrome.presentationConfirmed !== (receipt.chrome.presentedFrameEvents > 0)) throw new FactoryObservationError('RAF/submit events cannot certify presentation');
  return receipt;
}
export async function artifact(path: string): Promise<Artifact> {
  const data = await readFile(path), info = await stat(path);
  return ArtifactSchema.parse({ path, bytes: info.size, sha256: createHash('sha256').update(data).digest('hex') });
}
export async function verifyReceiptArtifacts(receipt: FactoryReceipt): Promise<void> {
  for (const expected of [receipt.backend.payload, receipt.screenshot, receipt.emptyScreenshot, receipt.video.artifact, receipt.video.step0.screenshot, receipt.trace, receipt.chrome.artifact, receipt.source.projectionPayload]) {
    const actual = await artifact(expected.path);
    if (actual.bytes !== expected.bytes || actual.sha256 !== expected.sha256) throw new FactoryObservationError(`Evidence artifact changed: ${expected.path}`);
  }
  for (const [path, hex] of [[receipt.screenshot.path, '89504e470d0a1a0a'], [receipt.emptyScreenshot.path, '89504e470d0a1a0a'], [receipt.video.step0.screenshot.path, '89504e470d0a1a0a'], [receipt.video.artifact.path, '1a45dfa3'], [receipt.trace.path, '504b0304']] as const) {
    const header = Buffer.from(hex, 'hex'), bytes = await readFile(path);
    if (!bytes.subarray(0, header.length).equals(header)) throw new FactoryObservationError(`Actual media signature missing: ${path}`);
  }
  const backend = WorldSchema.parse(JSON.parse(await readFile(receipt.backend.payload.path, 'utf8')));
  if (backend.run.id !== receipt.backend.runId || backend.run.revision !== receipt.backend.revision || backend.run.elapsed_ms !== receipt.backend.elapsedMs) throw new FactoryObservationError('Backend payload identity does not match receipt');
  const custody = backend.materials.map(row => ({ materialId: row.id, versionId: row.current_version_id, locationId: row.location_id }));
  if (JSON.stringify(custody) !== JSON.stringify(receipt.backend.custody)) throw new FactoryObservationError('Backend custody does not match payload');
  const projection = z.object({ authority: AuthoritySchema }).parse(JSON.parse(await readFile(receipt.source.projectionPayload.path, 'utf8')));
  if (JSON.stringify(projection.authority) !== JSON.stringify(receipt.authority)) throw new FactoryObservationError('Projection payload identity does not match receipt');
  const chrome = z.object({ traceEvents: z.array(ChromeEventSchema).min(1) }).parse(JSON.parse(await readFile(receipt.chrome.artifact.path, 'utf8')));
  const counts: Record<string, number> = {};
  for (const event of chrome.traceEvents) counts[event.name] = (counts[event.name] ?? 0) + 1;
  if (Object.keys(counts).length !== Object.keys(receipt.chrome.events).length || Object.entries(counts).some(([name, count]) => receipt.chrome.events[name] !== count)) throw new FactoryObservationError('Chrome event summary does not match trace');
  const presentationEvents = chrome.traceEvents.filter(event => event.name === 'FramePresented').length;
  if (receipt.chrome.presentedFrameEvents !== presentationEvents) throw new FactoryObservationError('Chrome presented-frame count does not match trace');
}
export async function readBoundSample(page: Page) {
  const raw = await page.locator('canvas').getAttribute('data-qa-bound-state');
  return BoundSampleSchema.parse(JSON.parse(raw ?? 'null'));
}
export async function compareScreenshotPixels(page: Page, actual: Buffer, empty: Buffer) {
  const result = await page.evaluate(async ({ actual, empty }) => {
    async function pixels(encoded: string) {
      const image = new Image(); image.src = `data:image/png;base64,${encoded}`; await image.decode();
      const canvas = document.createElement('canvas'); canvas.width = image.width; canvas.height = image.height;
      const context = canvas.getContext('2d'); if (!context) throw new Error('Screenshot decoder unavailable');
      context.drawImage(image, 0, 0); return { width: image.width, height: image.height, data: context.getImageData(0, 0, image.width, image.height).data };
    }
    const a = await pixels(actual), b = await pixels(empty);
    if (a.width !== b.width || a.height !== b.height) throw new Error('Screenshot dimensions changed');
    let changedPixels = 0;
    for (let index = 0; index < a.data.length; index += 4) {
      const delta = Math.abs((a.data[index] ?? 0) - (b.data[index] ?? 0)) + Math.abs((a.data[index + 1] ?? 0) - (b.data[index + 1] ?? 0)) + Math.abs((a.data[index + 2] ?? 0) - (b.data[index + 2] ?? 0));
      if (delta > 30) changedPixels += 1;
    }
    return { changedPixels, totalPixels: a.width * a.height };
  }, { actual: actual.toString('base64'), empty: empty.toString('base64') });
  return PixelSchema.parse({ ...result, screenshotSha256: createHash('sha256').update(actual).digest('hex'), emptySha256: createHash('sha256').update(empty).digest('hex'), minimumPixels: 500 });
}
const ChromeEventSchema = z.object({ name: z.string(), ts: finite.optional(), ph: z.string().optional() }).passthrough();

/** A separate context starts its own uninterrupted video and trace before the first navigation. */
export async function startFactoryObservation(browser: Browser, baseURL: string, testInfo: TestInfo) {
  const identity = await readQaIdentity();
  const context = await browser.newContext({ baseURL, viewport: { width: 1440, height: 1000 }, serviceWorkers: 'block', recordVideo: { dir: testInfo.outputPath('continuous'), size: { width: 1440, height: 1000 } } });
  const failures = captureBrowserFailures(context, baseURL), guard = await guardBrowserMutations(context);
  // This spec disables auto tracing for these cases so this context has one explicit trace owner.
  await context.tracing.start({ screenshots: true, snapshots: true, sources: true });
  const page = await context.newPage(), video = page.video();
  if (!video) throw new FactoryObservationError('Actual video recording is required');
  const session = await context.newCDPSession(page), events: z.infer<typeof ChromeEventSchema>[] = [];
  session.on('Tracing.dataCollected', (params: unknown) => { events.push(...z.object({ value: z.array(ChromeEventSchema) }).parse(params).value); });
  await session.send('Tracing.start', { categories: 'devtools.timeline,disabled-by-default-devtools.timeline.frame,cc,viz,benchmark', transferMode: 'ReportEvents' });
  const finalize = async () => {
    const completed = new Promise<void>((resolve, reject) => {
      const timer = setTimeout(() => reject(new FactoryObservationError('Chrome tracing completion hung')), 15_000);
      session.once('Tracing.tracingComplete', () => { clearTimeout(timer); resolve(); });
    });
    await session.send('Tracing.end'); await completed;
    const chromePath = testInfo.outputPath('chrome-frames.json'), tracePath = testInfo.outputPath('observer-trace.zip'), videoPath = testInfo.outputPath('continuous.webm');
    await writeFile(chromePath, JSON.stringify({ traceEvents: events }));
    const counts: Record<string, number> = {};
    for (const event of events) counts[event.name] = (counts[event.name] ?? 0) + 1;
    // DrawFrame / SubmitCompositorFrame are auxiliary events, never presented-frame proof.
    const presentedFrameEvents = counts['FramePresented'] ?? 0;
    await context.tracing.stop({ path: tracePath });
    await guard.dispose(); failures.dispose(); await context.close(); await video.saveAs(videoPath);
    await recordJson(testInfo, 'observer-browser-health', { failures: failures.failures, refusedMutations: guard.refused, identity });
    failures.assertHealthy();
    if (guard.refused.length) throw new FactoryObservationError('Browser mutation ownership refused');
    return { video: await artifact(videoPath), trace: await artifact(tracePath), chrome: { artifact: await artifact(chromePath), events: counts, presentedFrameEvents, presentationConfirmed: presentedFrameEvents > 0 } };
  };
  let completion: ReturnType<typeof finalize> | undefined;
  return { page, identity, finish() { completion ??= finalize(); return completion; } };
}

