#!/usr/bin/env node
import { parseArgs } from 'node:util';
import { mkdtempSync, existsSync, readFileSync, readdirSync, rmSync, statSync } from 'node:fs';
import { resolve, join, relative, isAbsolute } from 'node:path';
import { randomUUID } from 'node:crypto';
import { choosePorts, createOwnedEvidenceDirectory } from './ownership.mjs';
import { workspace, json, appendLog, hash, snapshot, processOwner, startServices, hostMetadata } from './runtime.mjs';
import { createStorage } from '../../scripts/storage.mjs';

const started = Date.now();
let evidence;
let runtime;
let owner;
let code = 1;
let failure;
let before;
let protectedPaths;
let sourcePaths;
let sourceBefore;
const controller = new AbortController();
let interrupted = false;
const interrupt = signal => {
  if (interrupted) return;
  interrupted = true;
  controller.abort(new Error(`Interrupted by ${signal}`));
  void owner?.cleanup();
};
process.on('SIGINT', () => interrupt('SIGINT'));
process.on('SIGTERM', () => interrupt('SIGTERM'));

try {
  const parsed = parseArgs({ options: {
    spec: { type: 'string' }, grep: { type: 'string' }, evidence: { type: 'string' },
    'api-port': { type: 'string' }, 'web-port': { type: 'string' },
  }, allowPositionals: true, strict: true });
  if (parsed.positionals.length !== 1 || parsed.positionals[0] !== 'browser') throw new Error('Usage: run.mjs browser --spec <path> --grep <pattern> --evidence <new-directory>');
  const values = parsed.values;
  if (!values.spec || !values.grep || !values.evidence) throw new Error('Required: --spec, --grep, --evidence');
  for (const flag of ['--spec', '--grep', '--evidence', '--api-port', '--web-port']) {
    if (process.argv.slice(2).filter(arg => arg === flag || arg.startsWith(`${flag}=`)).length > 1) throw new Error(`Duplicate option: ${flag}`);
  }
  new RegExp(values.grep);
  const spec = resolve(workspace, values.spec);
  const specRelative = relative(join(workspace, 'tests'), spec);
  if (specRelative.startsWith('..') || isAbsolute(specRelative) || !existsSync(spec) || !statSync(spec).isFile()) throw new Error(`Missing or unsafe spec: ${values.spec}`);
  const candidateEvidence = resolve(values.evidence);
  const evidenceRelative = relative(join(workspace, '.omo/evidence'), candidateEvidence);
  if (!evidenceRelative || evidenceRelative.startsWith('..') || isAbsolute(evidenceRelative)) throw new Error('Evidence must be a new directory below .omo/evidence');
  const storage = await createStorage(workspace, JSON.parse(readFileSync(join(workspace, 'storage-policy.json'), 'utf8')));
  const storageErrors = storage.violations(await storage.report(), 0, { includeLegacy: true });
  if (storageErrors.length) throw new Error(`Storage preflight failed: ${storageErrors.join('; ')}`);
  const evidenceToken = createOwnedEvidenceDirectory(candidateEvidence);
  evidence = candidateEvidence;
  appendLog(join(evidence, 'command.log'), `${JSON.stringify({ argv: process.argv, cwd: process.cwd(), started_at: new Date(started).toISOString() })}\n`);
  const ports = await choosePorts(values['api-port'] ?? process.env.STEELFLOW_QA_API_PORT, values['web-port'] ?? process.env.STEELFLOW_QA_WEB_PORT);
  json(join(evidence, 'ports.json'), ports);
  runtime = mkdtempSync(join(evidence, 'runtime-'));
  const env = { ...process.env,
    TMPDIR: runtime, NODE_COMPILE_CACHE: join(runtime, 'node-cache'), BUN_RUNTIME_TRANSPILER_CACHE_PATH: join(runtime, 'bun-cache'),
    STEELFLOW_QA_MANAGED: '1', STEELFLOW_QA_ATTEMPT_ID: randomUUID(),
    STEELFLOW_QA_EVIDENCE_TOKEN: evidenceToken,
    STEELFLOW_QA_API_PORT: String(ports.api), STEELFLOW_QA_WEB_PORT: String(ports.web),
    STEELFLOW_E2E_RUN_DIR: runtime, STEELFLOW_E2E_DATABASE_PATH: join(runtime, 'steelflow.sqlite'),
    STEELFLOW_E2E_BUILD_DIR: join(runtime, 'dist'), STEELFLOW_EVIDENCE_DIR: evidence,
    STEELFLOW_QA_IDENTITY_PATH: join(evidence, 'identity.json'),
    STEELFLOW_DATABASE_URL: `sqlite+aiosqlite:///${join(runtime, 'steelflow.sqlite')}`,
    STEELFLOW_TICK_SECONDS: '0.1', STEELFLOW_AI_ENABLED: 'false', VITE_API_TARGET: `http://127.0.0.1:${ports.api}`,
  };
  const envKeys = ['TMPDIR', 'NODE_COMPILE_CACHE', 'BUN_RUNTIME_TRANSPILER_CACHE_PATH', 'STEELFLOW_QA_MANAGED', 'STEELFLOW_QA_ATTEMPT_ID', 'STEELFLOW_QA_API_PORT', 'STEELFLOW_QA_WEB_PORT', 'STEELFLOW_E2E_RUN_DIR', 'STEELFLOW_E2E_DATABASE_PATH', 'STEELFLOW_E2E_BUILD_DIR', 'STEELFLOW_EVIDENCE_DIR', 'STEELFLOW_QA_IDENTITY_PATH', 'STEELFLOW_DATABASE_URL', 'STEELFLOW_TICK_SECONDS', 'STEELFLOW_AI_ENABLED', 'VITE_API_TARGET'];
  json(join(evidence, 'resources.json'), { runtime, env: Object.fromEntries(envKeys.map(key => [key, env[key]])) });
  protectedPaths = [join(workspace, 'dist'), ...['backend/steelflow.db', 'backend/steelflow.db-wal', 'backend/steelflow.db-shm', 'backend/steelflow.sqlite', 'backend/data'].map(path => join(workspace, path)), '/Users/ethanlee/.local/share/steelflow/demos/2026-10-30-campus', '/Users/ethanlee/.local/share/steelflow/demos/2026-10-30-unified'];
  before = snapshot(protectedPaths);
  json(join(evidence, 'protected-before.json'), before);
  sourcePaths = ['src', 'tests', 'tools/qa', 'backend/app', 'public', 'shared', 'playwright.config.ts', 'vite.config.ts', 'package.json'].map(path => join(workspace, path));
  sourceBefore = snapshot(sourcePaths);
  json(join(evidence, 'source-before.json'), sourceBefore);
  json(join(evidence, 'host.json'), hostMetadata());
  owner = processOwner(evidence, env);
  const playwright = join(workspace, 'node_modules/@playwright/test/cli.js');
  const selector = spec.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  const args = [playwright, 'test', selector, '--grep', values.grep, '--workers=1', '--retries=0'];
  await owner.execute(process.execPath, [...args, '--list']);
  const listed = JSON.parse(readFileSync(join(evidence, 'playwright-results.json'), 'utf8'));
  const countSpecs = suites => suites.reduce((count, suite) => count + (suite.specs?.length ?? 0) + countSpecs(suite.suites ?? []), 0);
  if (countSpecs(listed.suites) === 0) throw new Error('Zero matching tests');
  json(join(evidence, 'discovery.json'), listed);
  controller.signal.throwIfAborted();
  const identity = await startServices(owner, env, controller.signal);
  json(join(evidence, 'identity.json'), identity);
  await owner.execute(process.execPath, [...args, '--headed']);
  controller.signal.throwIfAborted();
  const result = JSON.parse(readFileSync(join(evidence, 'assertions.json'), 'utf8'));
  if (result.status !== 'passed' || result.assertion_count === 0 || result.tests.length === 0 || result.tests.some(test => test.status !== 'passed' || test.retry !== 0)) throw new Error('Missing assertions, skipped, retried, or nonpassing tests');
  code = 0;
} catch (error) {
  failure = error instanceof Error ? error.message : String(error);
  console.error(failure);
} finally {
  const stopped = owner ? await owner.cleanup() : [];
  if (evidence && existsSync(evidence)) {
    if (before) {
      const after = snapshot(protectedPaths);
      json(join(evidence, 'protected-after.json'), after);
      if (JSON.stringify(before) !== JSON.stringify(after)) { code = 1; failure = `${failure ?? ''} Protected file hashes changed`; }
    }
    if (sourceBefore) {
      const sourceAfter = snapshot(sourcePaths);
      json(join(evidence, 'source-after.json'), sourceAfter);
      json(join(evidence, 'source-binding.json'), { unchanged: JSON.stringify(sourceBefore) === JSON.stringify(sourceAfter) });
      if (JSON.stringify(sourceBefore) !== JSON.stringify(sourceAfter)) { code = 1; failure = `${failure ?? ''} Source changed during verification; rerun against frozen source`; }
    }
    if (runtime) {
      json(join(evidence, 'runtime-final.json'), snapshot([join(runtime, 'steelflow.sqlite'), join(runtime, 'dist')]));
      rmSync(runtime, { recursive: true, force: true });
    }
    const media = [];
    const visit = path => {
      for (const entry of readdirSync(path, { withFileTypes: true })) {
        const child = join(path, entry.name);
        if (entry.isDirectory()) visit(child);
        else if (/\.(png|webm|zip)$/.test(entry.name)) media.push({ path: relative(evidence, child), bytes: statSync(child).size, sha256: hash(readFileSync(child)) });
      }
    };
    visit(evidence);
    json(join(evidence, 'media.json'), media);
    if (code === 0 && !['.png', '.webm', '.zip'].every(extension => media.some(item => item.path.endsWith(extension) && item.bytes > 0))) { code = 1; failure = 'Missing actual screenshot, video, or trace'; }
    json(join(evidence, 'cleanup.json'), { stopped, runtime_removed: !runtime || !existsSync(runtime), complete: true });
    json(join(evidence, 'exit.json'), { code: interrupted ? 130 : code, failure, duration_ms: Date.now() - started, interrupted });
    if (!existsSync(join(evidence, 'assertions.json'))) json(join(evidence, 'assertions.json'), { status: 'failed', assertion_count: 0, failure });
    if (failure) appendLog(join(evidence, 'command.log'), `${failure}\n`);
  }
}
process.exitCode = interrupted ? 130 : code;
