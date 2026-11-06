import { expect } from '@playwright/test';
import { readFile } from 'node:fs/promises';
import { createHash } from 'node:crypto';
import { z } from 'zod';
import { test, readWorld, recordJson, resetScenario } from '../../helpers/operations';
import { assertOwnedMutation } from '../../helpers/qaIdentity';
import { artifact, AuthoritySchema, compareScreenshotPixels, readBoundSample, startFactoryObservation, validateFactoryReceipt, verifyReceiptArtifacts } from '../../helpers/factory';
import type { FactoryReceipt } from '../../helpers/factory';

test.use({ trace: 'off' });
const contractShape = z.object({ authority: AuthoritySchema, manifestSha256: z.string(), pose: z.object({ channels: z.array(z.object({ function_id: z.string(), value: z.number() })) }), envelope: z.object({ confirmed_sim_ms: z.number() }).passthrough(), snapshot: z.object({ run: z.object({ elapsed_ms: z.number() }).passthrough() }).passthrough() }).passthrough();
const partIds = ['roughing_roll', 'roughing_roll_follower_1', 'roughing_roll_follower_2', 'roughing_roll_follower_3'] as const;
const matrices = (sample: Awaited<ReturnType<typeof readBoundSample>>) => partIds.map(id => {
  const node = sample.nodes.find(row => row.id === id && row.kind === 'part');
  if (!node) throw new RangeError(`Actual bound roll missing: ${id}`);
  return node.matrixWorld;
});

test('full-cycle actual independent rolls preserve pause blocked LOD and scope using the existing observer', async ({ browser, baseURL }, testInfo) => {
  test.setTimeout(180_000);
  if (!baseURL) throw new RangeError('Owned base URL required');
  const recording = await startFactoryObservation(browser, baseURL, testInfo), page = recording.page;
  let media: Awaited<ReturnType<typeof recording.finish>> | undefined;
  try {
    await page.goto(`/tests/fixtures/mechanical-followers/index.html?steelflow-qa=1&qa-attempt=${encodeURIComponent(recording.identity.attempt_id)}`);
    await expect(page.getByTestId('observer-status')).toHaveText('실제 모델 표시');
    await expect(page.locator('canvas')).toHaveAttribute('data-qa-bound-state', /roughing_roll_follower_3/);
    await expect(page.getByTestId('step-counter')).toHaveText('Step 0 · 연속 영상 카운터');
    const step0Path = testInfo.outputPath('step-0.png'); await page.screenshot({ path: step0Path, fullPage: true });
    const step0 = { sequence: 0 as const, atMs: Number(await page.getByTestId('step-counter').getAttribute('data-step0-at-ms')), screenshot: await artifact(step0Path) };
    const firstActionAtMs = Date.now(), backend = await resetScenario(page.request), backendPath = await recordJson(testInfo, 'backend-payload', backend);
    const start = await readBoundSample(page), timeline = [start], canvas = page.locator('canvas');
    const startImage = await canvas.screenshot({ path: testInfo.outputPath('rolls-start.png') });
    for (let sample = 1; sample <= 48; sample += 1) {
      await assertOwnedMutation(page.request, page.url());
      await page.getByRole('button', { name: '다음 승인 샘플', exact: true }).click();
      await expect(page.getByTestId('sample-index')).toHaveText(String(sample));
      await expect.poll(async () => (await readBoundSample(page)).authority.authoritativeElapsedMs).toBe(400 + sample * 25);
      const observed = await readBoundSample(page); timeline.push(observed);
      const contract = contractShape.parse(JSON.parse(await page.getByTestId('observer-contract').textContent() ?? 'null'));
      expect(contract.pose.channels).toHaveLength(1);
      expect(contract.pose.channels[0]?.value).toBeCloseTo(4 * Math.PI * sample / 48, 9);
      if ([6, 18, 30, 42, 48].includes(sample)) await page.screenshot({ path: testInfo.outputPath(`cycle-${sample}.png`), fullPage: true });
    }
    expect(timeline).toHaveLength(49);
    for (const [index, initial] of matrices(start).entries()) {
      const midway = matrices(timeline[6] ?? start)[index];
      expect(midway).toBeDefined(); expect(midway).not.toEqual(initial);
    }
    const supportStart = start.nodes.find(node => node.kind === 'socket' && node.id === 'work')?.matrixWorld;
    for (const sample of timeline) expect(sample.nodes.find(node => node.kind === 'socket' && node.id === 'work')?.matrixWorld).toEqual(supportStart);
    await page.getByLabel('승인 샘플', { exact: true }).fill('18');
    await expect.poll(async () => (await readBoundSample(page)).authority.authoritativeElapsedMs).toBe(850);
    const movedImage = await canvas.screenshot({ path: testInfo.outputPath('rolls-part-cycle.png') }), motionPixels = await compareScreenshotPixels(page, movedImage, startImage);
    expect(motionPixels.changedPixels).toBeGreaterThan(50);
    await page.getByRole('button', { name: '일시 정지', exact: true }).click();
    await expect(page.getByTestId('clock-state')).toHaveText('paused');
    const held = await readBoundSample(page), heldMatrices = matrices(held);
    for (const action of ['차단 상태', 'LOD 1', 'LOD 2', 'LOD 0', '진행 상태', '일시 정지']) {
      await page.getByRole('button', { name: action, exact: true }).click();
      await expect(page.getByTestId('observer-status')).toHaveText('실제 모델 표시');
      for (const [index, actual] of matrices(await readBoundSample(page)).entries()) expect(actual).toEqual(heldMatrices[index]?.map(value => expect.closeTo(value, 5)));
    }
    await page.getByRole('button', { name: '범위 나가기', exact: true }).click(); await expect(page.getByTestId('observer-status')).toHaveText('범위 밖');
    await page.getByRole('button', { name: '같은 개체 재진입', exact: true }).click(); await expect(page.getByTestId('observer-status')).toHaveText('실제 모델 표시');
    for (const [index, actual] of matrices(await readBoundSample(page)).entries()) expect(actual).toEqual(heldMatrices[index]?.map(value => expect.closeTo(value, 5)));
    for (const angle of ['정면', '측면', '후면']) { await page.getByRole('button', { name: angle, exact: true }).click(); await page.screenshot({ path: testInfo.outputPath(`view-${angle}.png`), fullPage: true }); }
    await page.getByRole('button', { name: '정면', exact: true }).click();
    const contract = contractShape.parse(JSON.parse(await page.getByTestId('observer-contract').textContent() ?? 'null'));
    const checkpoint = await readBoundSample(page), positivePath = testInfo.outputPath('actual-object.png'), emptyPath = testInfo.outputPath('actual-empty.png');
    const positive = await canvas.screenshot({ path: positivePath }), metadataBefore = await canvas.getAttribute('data-qa-bound-state');
    await page.getByRole('button', { name: '기하 숨김 · 메타데이터 유지', exact: true }).click();
    await expect(page.getByRole('button', { name: '기하 숨김 · 메타데이터 유지', exact: true })).toHaveAttribute('aria-pressed', 'true');
    await page.evaluate(() => new Promise<void>(resolve => requestAnimationFrame(() => requestAnimationFrame(() => resolve()))));
    const empty = await canvas.screenshot({ path: emptyPath }), pixels = await compareScreenshotPixels(page, positive, empty);
    expect(await canvas.getAttribute('data-qa-bound-state')).toBe(metadataBefore); expect(pixels.changedPixels).toBeGreaterThan(500);
    const after = await readWorld(page.request); expect(after.run).toEqual(backend.run);
    const manifest = await readFile('tests/fixtures/mechanical-followers/generated/public/assets/steelworks/manifest.json');
    expect(createHash('sha256').update(manifest).digest('hex')).toBe(contract.manifestSha256);
    expect(contract.authority.authoritativeElapsedMs).toBe(contract.envelope.confirmed_sim_ms);
    expect(contract.snapshot.run.elapsed_ms).toBe(contract.authority.authoritativeElapsedMs);
    const projectionPath = await recordJson(testInfo, 't58-contract-payload', contract);
    await recordJson(testInfo, 'continuous-roll-samples', { source: 'explicit approved synthetic contract samples; no new wall clock', timeline, held, reentered: checkpoint, motionPixels, canonicalValues: timeline.map((_, index) => index * 4 * Math.PI / 48) });
    media = await recording.finish();
    const expected = { attemptId: recording.identity.attempt_id, authority: contract.authority, backend: { runId: backend.run.id, revision: backend.run.revision, elapsedMs: backend.run.elapsed_ms }, manifestSha256: contract.manifestSha256, videoSha256: media.video.sha256 };
    const receipt: FactoryReceipt = { schemaVersion: 1, attemptId: recording.identity.attempt_id, authority: contract.authority, backend: { ...expected.backend, payload: await artifact(backendPath), custody: backend.materials.map(row => ({ materialId: row.id, versionId: row.current_version_id, locationId: row.location_id })) }, samples: [checkpoint], screenshot: await artifact(positivePath), emptyScreenshot: await artifact(emptyPath), pixels, video: { artifact: media.video, attemptId: recording.identity.attempt_id, authority: contract.authority, continuous: true, step0, firstActionAtMs }, trace: media.trace, chrome: media.chrome, source: { manifestSha256: contract.manifestSha256, bundleHash: contract.authority.bundleHash, projectionPayload: await artifact(projectionPath) }, cancelled: false };
    await recordJson(testInfo, 'factory-observation-receipt', receipt); await verifyReceiptArtifacts(receipt);
    expect(validateFactoryReceipt(receipt, expected)).toEqual(receipt);
  } finally { if (!media) await recording.finish(); }
});
