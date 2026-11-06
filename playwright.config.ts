import { defineConfig, devices } from '@playwright/test';
import { mkdtempSync, realpathSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';
import { randomUUID } from 'node:crypto';
import { assertAllowedPort, assertFreshEvidenceDirectory, createOwnedEvidenceDirectory, verifyOwnedEvidenceDirectory } from './tools/qa/ownership.mjs';

const managed = process.env.STEELFLOW_QA_MANAGED === '1';
const apiPort = assertAllowedPort(process.env.STEELFLOW_QA_API_PORT ?? '8003');
const webPort = assertAllowedPort(process.env.STEELFLOW_QA_WEB_PORT ?? '4176');
if (apiPort === webPort) throw new Error('QA API and web ports must differ');
if (!managed && process.env.STEELFLOW_EVIDENCE_DIR) assertFreshEvidenceDirectory(resolve(process.env.STEELFLOW_EVIDENCE_DIR));
const root = managed && process.env.STEELFLOW_E2E_RUN_DIR
  ? resolve(process.env.STEELFLOW_E2E_RUN_DIR)
  : mkdtempSync(join(realpathSync(tmpdir()), 'steelflow-qa-'));
const evidence = resolve(process.env.STEELFLOW_EVIDENCE_DIR || join(root, 'evidence'));
const evidenceToken = managed
  ? verifyOwnedEvidenceDirectory(evidence, process.env.STEELFLOW_QA_EVIDENCE_TOKEN)
  : createOwnedEvidenceDirectory(evidence);
const apiOrigin = `http://127.0.0.1:${apiPort}`;
const webOrigin = `http://127.0.0.1:${webPort}`;
const env = {
  STEELFLOW_QA_MANAGED: '1',
  STEELFLOW_QA_EVIDENCE_TOKEN: evidenceToken,
  TMPDIR: root,
  NODE_COMPILE_CACHE: join(root, 'node-cache'),
  BUN_RUNTIME_TRANSPILER_CACHE_PATH: join(root, 'bun-cache'),
  STEELFLOW_E2E_RUN_DIR: root,
  STEELFLOW_E2E_DATABASE_PATH: join(root, 'steelflow.sqlite'),
  STEELFLOW_E2E_BUILD_DIR: join(root, 'dist'),
  STEELFLOW_DATABASE_URL: `sqlite+aiosqlite:///${join(root, 'steelflow.sqlite')}`,
  STEELFLOW_QA_ATTEMPT_ID: process.env.STEELFLOW_QA_ATTEMPT_ID || randomUUID(),
  STEELFLOW_QA_API_PORT: String(apiPort),
  STEELFLOW_QA_WEB_PORT: String(webPort),
  STEELFLOW_QA_IDENTITY_PATH: managed && process.env.STEELFLOW_QA_IDENTITY_PATH || join(evidence, 'identity.json'),
  STEELFLOW_EVIDENCE_DIR: evidence,
  STEELFLOW_TICK_SECONDS: '0.1',
  STEELFLOW_AI_ENABLED: 'false',
  VITE_API_TARGET: apiOrigin,
};
Object.assign(process.env, env);

export default defineConfig({
  testDir: './tests',
  fullyParallel: false,
  forbidOnly: true,
  workers: 1,
  retries: 0,
  timeout: 45_000,
  expect: { timeout: 10_000 },
  outputDir: join(evidence, 'test-results'),
  reporter: [
    ['list'],
    ['./tools/qa/reporter.mjs'],
    ['html', { open: 'never', outputFolder: join(evidence, 'html-report') }],
    ['json', { outputFile: join(evidence, 'playwright-results.json') }],
  ],
  use: {
    ...devices['Desktop Chrome'],
    channel: 'chrome',
    headless: false,
    serviceWorkers: 'block',
    baseURL: webOrigin,
    viewport: { width: 1440, height: 1000 },
    trace: 'on',
    video: { mode: 'on', size: { width: 1440, height: 1000 } },
    screenshot: 'on',
  },
  webServer: managed ? undefined : {
    command: 'node tools/qa/serve.mjs',
    url: webOrigin,
    env,
    reuseExistingServer: false,
    gracefulShutdown: { signal: 'SIGTERM', timeout: 10_000 },
    timeout: 120_000,
  },
});
