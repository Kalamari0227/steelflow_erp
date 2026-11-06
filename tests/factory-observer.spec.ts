import { expect } from '@playwright/test';
import { createHash } from 'node:crypto';
import { readFile, writeFile } from 'node:fs/promises';
import { z } from 'zod';
import { test, readWorld, recordJson, resetScenario, clickOperation } from './helpers/operations';
import { assertOwnedMutation } from './helpers/qaIdentity';
import { artifact, AuthoritySchema, compareScreenshotPixels, readBoundSample, startFactoryObservation, validateFactoryReceipt, verifyReceiptArtifacts } from './helpers/factory';
import type { FactoryReceipt, ReceiptExpected } from './helpers/factory';

// This file owns trace completion before receipt validation; other specs retain the configured auto tracing.
test.use({ trace: 'off' });

const entry = '/tests/fixtures/factory-observer/index.html?steelflow-qa=1';
const contractSchema = z.object({ authority: AuthoritySchema, manifestSha256: z.string(), envelope: z.object({ run_id: z.string(), revision: z.number(), bundle_hash: z.string(), confirmed_sim_ms: z.number() }).passthrough(), snapshot: z.object({ run: z.object({ id: z.string(), revision: z.number(), elapsed_ms: z.number(), bundle_hash: z.string() }).passthrough() }).passthrough() });

test('actual-frame QA off keeps business canvas without diagnostic work', async ({ browser, baseURL }, testInfo) => {
  if (!baseURL) throw new Error('Owned base URL required');
  const recording = await startFactoryObservation(browser, baseURL, testInfo), page = recording.page, request = page.request;
  try {
  await resetScenario(request);
  await page.goto('/?steelflow-qa=0');
  await expect(page.getByTestId('simulation-step')).toBeEnabled();
  const canvas = page.locator('canvas'); await expect(canvas).toBeVisible();
  const world = await readWorld(request);
  await clickOperation(page, 'simulation-step', '/api/v1/simulation/step');
  expect((await readWorld(request)).run.revision).toBeGreaterThan(world.run.revision);
  for (const attribute of ['data-render-stats', 'data-pick-targets', 'data-scene-state']) await expect(canvas).not.toHaveAttribute(attribute, /.*/);
  await page.screenshot({ path: testInfo.outputPath('qa-off-business-frame.png'), fullPage: true });
  await recordJson(testInfo, 'off-observer-evidence', { diagnosticAttributes: await canvas.evaluate(node => ['data-render-stats', 'data-pick-targets', 'data-scene-state'].map(name => node.getAttribute(name))), businessRevision: (await readWorld(request)).run.revision, frameworkMatrixWorkExcluded: true });
  } finally { await recording.finish(); }
});

for (const mode of ['actual-frame', 'metadata-only'] as const) {
  test(`${mode} real GLB pixels bind matrices, video, trace and backend custody`, async ({ browser, baseURL }, testInfo) => {
    test.setTimeout(120_000);
    if (!baseURL) throw new Error('Owned base URL required');
    const recording = await startFactoryObservation(browser, baseURL, testInfo), page = recording.page;
    let media: Awaited<ReturnType<typeof recording.finish>> | undefined;
    try {
      await page.goto(`${entry}&qa-attempt=${encodeURIComponent(recording.identity.attempt_id)}`);
      await expect(page.getByTestId('visible-attempt')).toHaveText(`QA attempt ${recording.identity.attempt_id}`);
      await expect(page.getByTestId('observer-status')).toHaveText('실제 모델 표시');
      await expect(page.getByTestId('step-counter')).toHaveText('Step 0 · 연속 영상 카운터');
      const step0Path = testInfo.outputPath('step-0.png');
      await page.screenshot({ path: step0Path, fullPage: true });
      const step0 = { sequence: 0 as const, atMs: Number(await page.getByTestId('step-counter').getAttribute('data-step0-at-ms')), screenshot: await artifact(step0Path) };
      const firstActionAtMs = Date.now();
      const backend = await resetScenario(page.request);
      expect(backend.run.playing).toBe(false);
      const backendPath = await recordJson(testInfo, 'backend-payload', backend);
      const contract = contractSchema.parse(JSON.parse(await page.getByTestId('observer-contract').textContent() ?? 'null'));
      expect(contract.authority.runId).toBe(contract.envelope.run_id);
      expect(contract.authority.revision).toBe(contract.envelope.revision);
      expect(contract.authority.bundleHash).toBe(contract.envelope.bundle_hash);
      expect(contract.authority.authoritativeElapsedMs).toBe(contract.envelope.confirmed_sim_ms);
      expect(contract.snapshot.run.id).toBe(contract.authority.runId);
      expect(contract.snapshot.run.revision).toBe(contract.authority.revision);
      expect(contract.snapshot.run.bundle_hash).toBe(contract.authority.bundleHash);
      expect(contract.snapshot.run.elapsed_ms).toBe(contract.authority.authoritativeElapsedMs);
      const manifestBytes = await readFile('public/assets/steelworks/manifest.json');
      expect(createHash('sha256').update(manifestBytes).digest('hex')).toBe(contract.manifestSha256);
      const projectionPath = await recordJson(testInfo, 't58-contract-payload', contract);
      const expectedBase = { attemptId: recording.identity.attempt_id, authority: contract.authority, backend: { runId: backend.run.id, revision: backend.run.revision, elapsedMs: backend.run.elapsed_ms }, manifestSha256: contract.manifestSha256 };
      const canvas = page.locator('canvas');
      await expect(canvas).toHaveAttribute('data-qa-bound-state', /rafSequence/);
      const sample = await readBoundSample(page);
      expect(sample.nodes.some(node => node.kind === 'part' && node.visible)).toBe(true);
      expect(sample.nodes.some(node => node.kind === 'socket')).toBe(true);
      const positivePath = testInfo.outputPath('actual-object.png'), emptyPath = testInfo.outputPath('actual-empty.png');
      const positive = await canvas.screenshot({ path: positivePath });
      const metadataBefore = await canvas.getAttribute('data-qa-bound-state');
      await assertOwnedMutation(page.request, page.url());
      await page.getByRole('button', { name: '기하 숨김 · 메타데이터 유지', exact: true }).click();
      await expect(page.getByRole('button', { name: '기하 숨김 · 메타데이터 유지', exact: true })).toHaveAttribute('aria-pressed', 'true');
      await page.evaluate(() => new Promise<void>(resolve => requestAnimationFrame(() => requestAnimationFrame(() => resolve()))));
      const empty = await canvas.screenshot({ path: emptyPath });
      expect(await canvas.getAttribute('data-qa-bound-state')).toBe(metadataBefore);
      const pixels = await compareScreenshotPixels(page, mode === 'actual-frame' ? positive : empty, empty);
      if (mode === 'actual-frame') expect(pixels.changedPixels).toBeGreaterThan(pixels.minimumPixels);
      else expect(pixels.changedPixels).toBe(0);
      const screenshotPath = mode === 'actual-frame' ? positivePath : emptyPath;
      const backendAfter = await readWorld(page.request);
      expect(backendAfter.run).toEqual(backend.run);
      const sampleAfter = await readBoundSample(page); expect(sampleAfter).toEqual(sample);
      if (mode === 'metadata-only') expect(sampleAfter.nodes.some(node => node.visible && node.kind === 'part')).toBe(true);
      if (mode === 'actual-frame') {
        await assertOwnedMutation(page.request, page.url());
        await page.getByRole('button', { name: '기하 숨김 · 메타데이터 유지', exact: true }).click();
        await page.getByLabel('실제 자산', { exact: true }).selectOption({ label: 'galvanizing' });
        await expect(page.getByTestId('observer-status')).toHaveText('실제 모델 표시');
        await expect.poll(async () => (await readBoundSample(page)).nodes.some(node => node.entityId === 'CS-GI-05')).toBe(true);
        await page.screenshot({ path: testInfo.outputPath('second-family-galvanizing.png'), fullPage: true });
      }
      const completion = recording.finish();
      expect(recording.finish()).toBe(completion);
      media = await completion;
      const expected: ReceiptExpected = { ...expectedBase, videoSha256: media.video.sha256 };
      const receipt: FactoryReceipt = { schemaVersion: 1, attemptId: recording.identity.attempt_id, authority: contract.authority,
        backend: { ...expectedBase.backend, payload: await artifact(backendPath), custody: backend.materials.map(row => ({ materialId: row.id, versionId: row.current_version_id, locationId: row.location_id })) },
        samples: [sample], screenshot: await artifact(screenshotPath), emptyScreenshot: await artifact(emptyPath), pixels,
        video: { artifact: media.video, attemptId: recording.identity.attempt_id, authority: contract.authority, continuous: true, step0, firstActionAtMs }, trace: media.trace, chrome: media.chrome,
        source: { manifestSha256: contract.manifestSha256, bundleHash: contract.authority.bundleHash, projectionPayload: await artifact(projectionPath) }, cancelled: false };
      await recordJson(testInfo, 'factory-observation-receipt', receipt);
      await verifyReceiptArtifacts(receipt);
      if (mode === 'actual-frame') {
        expect(validateFactoryReceipt(receipt, expected)).toEqual(receipt);
        for (const [name, changed] of Object.entries({ malformed: { arbitrary: true }, wrongRun: { ...receipt, authority: { ...receipt.authority, runId: 'wrong' } }, wrongRevision: { ...receipt, authority: { ...receipt.authority, revision: receipt.authority.revision + 1 } }, stale: { ...receipt, authority: { ...receipt.authority, stale: true } }, missingVideo: { ...receipt, video: undefined }, wrongVideoAttempt: { ...receipt, video: { ...receipt.video, attemptId: 'stale-attempt' } }, wrongVideoHash: { ...receipt, video: { ...receipt.video, artifact: { ...receipt.video.artifact, sha256: 'f'.repeat(64) } } }, wrongVideo: { ...receipt, video: { ...receipt.video, authority: { ...receipt.video.authority, runId: 'wrong-video-run' } } }, cancelled: { ...receipt, cancelled: true }, dirty: { ...receipt, source: { ...receipt.source, manifestSha256: '0'.repeat(64) } } })) {
          expect(() => validateFactoryReceipt(changed, expected), name).toThrow();
        }
        const alteredPath = testInfo.outputPath('tampered-evidence.png'); await writeFile(alteredPath, 'log says PASS');
        await expect(verifyReceiptArtifacts({ ...receipt, screenshot: { ...receipt.screenshot, path: alteredPath } })).rejects.toThrow('artifact changed');
        const fakeVideo = await artifact(alteredPath);
        await expect(verifyReceiptArtifacts({ ...receipt, video: { ...receipt.video, artifact: fakeVideo } })).rejects.toThrow('media signature missing');
        await expect(verifyReceiptArtifacts({ ...receipt, video: { ...receipt.video, artifact: { ...receipt.video.artifact, path: testInfo.outputPath('missing.webm') } } })).rejects.toThrow('ENOENT');
      } else {
        expect(sample.nodes.length).toBeGreaterThan(0);
        expect(() => validateFactoryReceipt(receipt, expected)).toThrow('Actual screenshot pixels');
        await recordJson(testInfo, 'metadata-only-rejection', { metadataUnchanged: true, actualPixels: pixels, rejected: true, expectedFailure: 'Actual screenshot pixels do not show the target object', backendRunUnchanged: true });
      }
    } finally { if (!media) await recording.finish(); }
  });
}
