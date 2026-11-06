import { afterEach, describe, expect, it, vi } from 'vitest';
import { PerspectiveCamera, Scene } from 'three';
import type { WebGLRenderer } from 'three';
import { isQaProbeEnabled, QaProbe, type QaAuthority } from './qaProbe';
import { testWorld } from '../testWorld';

const authority: QaAuthority = { source: 't58-fixed-contract', runId: 'fixture', revision: 0, bundleHash: 'a'.repeat(64), authoritativeElapsedMs: 1000, stale: false };
afterEach(() => vi.restoreAllMocks());
describe('explicit scene QA opt-in', () => {
  it.each(['', '?steelflow-qa=0', '?steelflow-qa=true', '?steelflow-qa=01', '?other=1', '?steelflow-qa=1&steelflow-qa=0'])('keeps ordinary builds off for %s', search => expect(isQaProbeEnabled(search)).toBe(false));
  it('allows exactly 1 and lets an explicit off override an owned QA build', () => {
    expect(isQaProbeEnabled('?steelflow-qa=1')).toBe(true);
    expect(isQaProbeEnabled('', true)).toBe(true);
    expect(isQaProbeEnabled('?steelflow-qa=0', true)).toBe(false);
    expect(isQaProbeEnabled('?steelflow-qa=true', true)).toBe(false);
  });
  it('performs zero observer traversal, matrix updates or JSON on 120 disabled business frames', () => {
    const probe = new QaProbe(false), scene = new Scene(), camera = new PerspectiveCamera(), world = testWorld();
    const traversal = vi.spyOn(scene, 'traverse'), sceneMatrices = vi.spyOn(scene, 'updateMatrixWorld'), cameraMatrices = vi.spyOn(camera, 'updateMatrixWorld');
    const json = vi.spyOn(JSON, 'stringify');
    // An off observer must not read the renderer at all; the real prototype detects accidental access.
    const frame = { get gl(): WebGLRenderer { throw new Error('Disabled observer accessed renderer'); }, scene, camera, world, elapsedMs: 0, reduced: false, stale: false };
    for (let i = 0; i < 120; i++) {
      probe.observeLegacy(frame);
      expect(probe.observeAssets([], authority, camera)).toBeNull();
    }
    expect(traversal).not.toHaveBeenCalled(); expect(sceneMatrices).not.toHaveBeenCalled(); expect(cameraMatrices).not.toHaveBeenCalled();
    expect(json).not.toHaveBeenCalled();
    expect(probe.work).toEqual({ frames: 0, traversals: 0, serializations: 0, matrixUpdates: 0, boundNodes: 0 });
  });
  it('rejects stale authority and empty bindings before sampling', () => {
    const probe = new QaProbe(true), camera = new PerspectiveCamera();
    expect(() => probe.observeAssets([], { ...authority, stale: true }, camera)).toThrow('stale');
    expect(() => probe.observeAssets([], authority, camera)).toThrow('empty');
    expect(probe.work.frames).toBe(0);
  });
});

// Receipt validation is shared by browser evidence production and these boundary unit cases.
import { FactoryReceiptSchema, validateFactoryReceipt, type ReceiptExpected } from '../../../tests/helpers/factory';
const file = { path: '/owned/real-artifact', bytes: 12, sha256: 'a'.repeat(64) };
const emptyFile = { ...file, sha256: 'c'.repeat(64) };
const receiptAuthority = { ...authority, stale: false as const };
const expected: ReceiptExpected = { attemptId: 'owned-attempt', authority: receiptAuthority, backend: { runId: 'legacy', revision: 2, elapsedMs: 0 }, manifestSha256: 'b'.repeat(64), videoSha256: file.sha256 };
function receipt() {
  const m = new PerspectiveCamera().matrix.toArray();
  return FactoryReceiptSchema.parse({ schemaVersion: 1, attemptId: expected.attemptId, authority: receiptAuthority,
    backend: { ...expected.backend, payload: file, custody: [] }, samples: [{ authority: receiptAuthority, sampledAtMs: 1, rafSequence: 1, nodes: ['part', 'socket'].map(kind => ({ entityId: 'CUT-SLAB', id: kind, kind, matrixWorld: m, visible: true })), camera: { matrixWorld: m, projectionMatrix: m } }],
    screenshot: file, emptyScreenshot: emptyFile, pixels: { screenshotSha256: file.sha256, emptySha256: emptyFile.sha256, changedPixels: 1000, totalPixels: 10000, minimumPixels: 500 }, video: { artifact: file, attemptId: expected.attemptId, authority: receiptAuthority, continuous: true, step0: { sequence: 0, atMs: 1, screenshot: file }, firstActionAtMs: 2 }, trace: file,
    chrome: { artifact: file, events: { DrawFrame: 2 }, presentedFrameEvents: 0, presentationConfirmed: false }, source: { manifestSha256: expected.manifestSha256, bundleHash: receiptAuthority.bundleHash, projectionPayload: file }, cancelled: false });
}
describe('factory observation receipt boundaries', () => {
  it('accepts a bound receipt without pretending RAF is a presented frame', () => expect(validateFactoryReceipt(receipt(), expected).chrome.presentationConfirmed).toBe(false));
  it.each(['attempt', 'run', 'revision', 'bundle', 'clock', 'backend', 'dirty', 'stale', 'video', 'pixels', 'cancel', 'presentation', 'video-attempt', 'video-hash'])('rejects %s evidence', variant => {
    const row = receipt();
    const cases: Record<string, unknown> = {
      attempt: { ...row, attemptId: 'wrong' }, run: { ...row, authority: { ...row.authority, runId: 'wrong' } },
      revision: { ...row, authority: { ...row.authority, revision: 3 } }, bundle: { ...row, authority: { ...row.authority, bundleHash: 'c'.repeat(64) } },
      clock: { ...row, authority: { ...row.authority, authoritativeElapsedMs: 2000 } }, backend: { ...row, backend: { ...row.backend, revision: 9 } },
      dirty: { ...row, source: { ...row.source, manifestSha256: 'c'.repeat(64) } }, stale: { ...row, samples: row.samples.map(sample => ({ ...sample, authority: { ...sample.authority, stale: true } })) },
      video: { ...row, video: undefined }, pixels: { ...row, pixels: { ...row.pixels, changedPixels: 0 } }, cancel: { ...row, cancelled: true },
      'video-attempt': { ...row, video: { ...row.video, attemptId: 'stale-attempt' } }, 'video-hash': { ...row, video: { ...row.video, artifact: { ...file, sha256: 'd'.repeat(64) } } },
      presentation: { ...row, chrome: { ...row.chrome, presentationConfirmed: true } },
    };
    expect(() => validateFactoryReceipt(cases[variant], expected)).toThrow();
  });
  it('rejects matrix metadata without the actual part and socket binding classes', () => {
    const row = receipt();
    expect(() => validateFactoryReceipt({ ...row, samples: row.samples.map(sample => ({ ...sample, nodes: sample.nodes.filter(node => node.kind === 'part') })) }, expected)).toThrow('bindings missing');
  });
});
