import test from 'node:test';
import assert from 'node:assert/strict';
import * as fs from 'node:fs/promises';
import path from 'node:path';
import os from 'node:os';
import { randomUUID } from 'node:crypto';
import { spawn } from 'node:child_process';
import { createStorage, validatePolicy } from './storage.mjs';

const moduleUrl = new URL('./storage.mjs', import.meta.url).href;
const base = { version: 1, maxRunBytes: 1048576, maxManagedBytes: 10485760, minFreeBytes: 0, legacyEvidenceMaxBytes: 1024, retainSuccessDays: 7, retainSuccessCount: 3, pollIntervalMs: 20, shutdownGraceMs: 100 };
const delay = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
async function fixture(t, overrides = {}) {
  const root = await fs.realpath(await fs.mkdtemp(path.join(os.tmpdir(), 'storage-policy-')));
  t.after(() => fs.rm(root, { recursive: true, force: true }));
  const policy = { ...base, ...overrides };
  return { root, policy, storage: await createStorage(root, policy) };
}
async function marker(root, changes = {}, age = 10) {
  const id = randomUUID(), dir = path.join(root, '.artifacts', 'runs', id);
  await fs.mkdir(dir, { recursive: true });
  const finished = new Date(Date.now() - age * 86400000).toISOString();
  await fs.writeFile(path.join(dir, 'storage-run.json'), JSON.stringify({ version: 1, runId: id, command: ['test'], category: 'disposable-test', ownerPid: 1073741823, status: 'success', startedAt: finished, finishedAt: finished, exitCode: 0, signal: null, ...changes }));
  await fs.writeFile(path.join(dir, 'data'), 'preserve or delete by policy');
  return { id, dir };
}
async function exists(target) { try { await fs.lstat(target); return true; } catch (error) { if (error.code === 'ENOENT') return false; throw error; } }
async function waitFor(check) {
  const deadline = Date.now() + 5000;
  while (!await check()) { if (Date.now() >= deadline) throw new Error('Timed out waiting for fixture'); await delay(20); }
}

test('clean deletes only aged successful disposable runs outside newest three; dry-run preserves everything', async (t) => {
  const { root, storage } = await fixture(t);
  const old = await marker(root, {}, 30);
  const newest = await Promise.all([1, 2, 3].map((age) => marker(root, {}, age)));
  const failed = await marker(root, { status: 'failed', exitCode: 1 }, 40);
  const pinned = await marker(root, {}, 40); await fs.writeFile(path.join(pinned.dir, '.keep'), '');
  const live = await marker(root, { ownerPid: process.pid }, 40);
  const manual = await marker(root, { category: 'manual' }, 40);
  const unknown = path.join(root, '.artifacts', 'runs', 'unknown'); await fs.mkdir(unknown); await fs.writeFile(path.join(unknown, 'important'), 'keep');
  const malformed = await marker(root, { exitCode: 2 }, 40);
  const link = await marker(root, {}, 40); await fs.symlink(path.join(root, 'outside'), path.join(link.dir, 'link'));
  const unfinished = await marker(root, { status: 'running', finishedAt: null }, 40);
  const dry = await storage.clean();
  assert.deepEqual(dry.runs.filter((run) => run.action === 'would-delete').map((run) => run.id), [old.id]);
  assert.equal(await exists(old.dir), true);
  const applied = await storage.clean({ apply: true });
  assert.deepEqual(applied.runs.filter((run) => run.action === 'deleted').map((run) => run.id), [old.id]);
  for (const item of [...newest, failed, pinned, live, manual, malformed, link, unfinished]) assert.equal(await exists(item.dir), true, item.id);
  assert.equal(await exists(unknown), true);
});

test('minimum age applies even beyond newest count; commands retain independently', async (t) => {
  const { root, storage } = await fixture(t);
  for (const age of [0.1, 0.2, 0.3, 0.4]) await marker(root, {}, age);
  const other = await marker(root, { command: ['different', '--flag'] }, 100);
  assert.equal((await storage.clean({ apply: true })).runs.every((run) => run.action === 'skip'), true);
  assert.equal(await exists(other.dir), true);
});

test('unsafe roots, path escapes and symlink managed roots are refused', async (t) => {
  const { root, storage } = await fixture(t);
  await assert.rejects(createStorage('/', base), /Unsafe project root/);
  await assert.rejects(storage.guard(path.join(root, '.omo')), /escape/);
  await assert.rejects(storage.guard(path.join(root, '.artifacts', 'runs', '..', '..', 'source')), /escape/);
  const outside = path.join(root, 'outside'); await fs.mkdir(outside);
  await fs.symlink(outside, path.join(root, '.artifacts'));
  await assert.rejects(storage.clean({ apply: true }), /Unsafe storage directory/);
  assert.equal(await exists(outside), true);
});

test('legacy evidence is advisory for ordinary runs, enforced only by includeLegacy', async (t) => {
  const { root, storage } = await fixture(t);
  const legacy = path.join(root, '.omo', 'evidence'); await fs.mkdir(legacy, { recursive: true });
  await fs.writeFile(path.join(legacy, 'historical'), Buffer.alloc(2048));
  const report = await storage.report();
  assert.equal(report.legacyOmoLogicalBytes, 2048);
  assert.equal(report.legacyEvidenceLogicalBytes, 2048);
  assert.equal(typeof report.diskFreeBytes, 'number');
  assert.deepEqual(storage.violations(report), []);
  assert.match(storage.violations(report, 0, { includeLegacy: true }).join(), /Legacy .omo\/evidence/);
  await storage.clean({ apply: true });
  assert.equal(await exists(path.join(legacy, 'historical')), true);
});

test('legacy symlink roots are not followed and browser preflight fails conservatively', async (t) => {
  const { root, storage } = await fixture(t);
  const outside = path.join(root, 'outside'); await fs.mkdir(path.join(outside, 'evidence'), { recursive: true });
  await fs.writeFile(path.join(outside, 'evidence', 'preserve'), 'untouched');
  await fs.symlink(outside, path.join(root, '.omo'));
  const report = await storage.report();
  assert.equal(report.legacyOmoLogicalBytes, 0);
  assert.equal(report.legacyEvidenceLogicalBytes, 0);
  assert.match(storage.violations(report, 0, { includeLegacy: true }).join(), /symlinks/);
  assert.equal(await fs.readFile(path.join(outside, 'evidence', 'preserve'), 'utf8'), 'untouched');
});

test('policy validation disallows missing, negative, unknown or unbounded timing values', () => {
  for (const change of [{ version: 2 }, { maxRunBytes: -1 }, { minFreeBytes: -1 }, { retainSuccessDays: 0 }, { root: '/' }, { pollIntervalMs: 60001 }, { maxRunBytes: base.maxManagedBytes + 1 }]) assert.throws(() => validatePolicy({ ...base, ...change }));
});

test('child success/failure preserve exit code and evidence; runtime is removed after shutdown', async (t) => {
  const { storage } = await fixture(t);
  for (const code of [0, 7]) {
    const result = await storage.run([process.execPath, '-e', `const fs=require('node:fs');fs.writeFileSync(process.env.TMPDIR+'/temp','runtime');fs.mkdirSync(process.env.ASSET_LOADER_EVIDENCE_ROOT,{recursive:true});fs.writeFileSync(process.env.ASSET_LOADER_EVIDENCE_ROOT+'/proof','evidence');process.exit(${code})`], { category: 'disposable-test', env: { TMPDIR: '/system/default/temp' } });
    assert.equal(result.exitCode, code);
    assert.equal(result.marker.status, code === 0 ? 'success' : 'failed');
    assert.deepEqual(result.marker.relocatedEnvironmentKeys, ['TMPDIR']);
    assert.equal(await exists(path.join(result.directory, 'runtime')), false);
    assert.equal(await exists(path.join(result.directory, 'evidence', 'asset-loader', 'proof')), true);
    assert.equal(JSON.parse(await fs.readFile(path.join(result.directory, 'storage-run.json'))).status, result.marker.status);
  }
});

test('explicit external evidence overrides fail before child starts', async (t) => {
  const { root, storage } = await fixture(t);
  for (const key of ['ASSET_LOADER_EVIDENCE_ROOT', 'ASSET_PIPELINE_EVIDENCE_ROOT']) {
    await assert.rejects(storage.run([process.execPath, '-e', 'process.exit(99)'], { env: { [key]: root } }), new RegExp(`${key} points outside`));
  }
  assert.deepEqual((await storage.report()).runs, []);
});

test('CLI forwards child --help after delimiter without consuming it as wrapper help', async (t) => {
  const { root, policy } = await fixture(t);
  await fs.mkdir(path.join(root, 'scripts'));
  await fs.copyFile(new URL('./storage.mjs', import.meta.url), path.join(root, 'scripts', 'storage.mjs'));
  await fs.writeFile(path.join(root, 'storage-policy.json'), JSON.stringify(policy));
  const script = "require('node:fs').writeFileSync(process.env.ASSET_LOADER_EVIDENCE_ROOT+'/help',process.argv.at(-1))";
  // The child creates its evidence subdirectory itself, as a normal producer does.
  const code = "require('node:fs').mkdirSync(process.env.ASSET_LOADER_EVIDENCE_ROOT,{recursive:true});" + script;
  const child = spawn(process.execPath, [path.join(root, 'scripts', 'storage.mjs'), 'run', '--', process.execPath, '-e', code, '--', '--help'], { env: {}, stdio: 'ignore' });
  assert.equal(await new Promise((resolve) => child.once('close', resolve)), 0);
  const runs = await fs.readdir(path.join(root, '.artifacts', 'runs'));
  assert.equal(runs.length, 1);
  assert.equal(await fs.readFile(path.join(root, '.artifacts', 'runs', runs[0], 'evidence', 'asset-loader', 'help'), 'utf8'), '--help');
});

test('missing executable remains a failed run and runtime is cleaned', async (t) => {
  const { storage } = await fixture(t);
  const result = await storage.run(['/missing-storage-fixture-executable'], { env: {} });
  assert.equal(result.exitCode, 1);
  assert.equal(result.marker.status, 'failed');
  assert.match(result.marker.reason, /ENOENT/);
  assert.equal(await exists(path.join(result.directory, 'runtime')), false);
});

test('inherited npm/OS cache variables are relocated into owned runtime and recorded by key', async (t) => {
  const { storage } = await fixture(t);
  const env = Object.fromEntries(['XDG_CACHE_HOME', 'npm_config_cache', 'NPM_CONFIG_CACHE', 'NODE_COMPILE_CACHE', 'BUN_RUNTIME_TRANSPILER_CACHE_PATH'].map((key) => [key, '/external/cache']));
  const result = await storage.run([process.execPath, '-e', "const path=require('node:path');for(const key of ['XDG_CACHE_HOME','npm_config_cache','NPM_CONFIG_CACHE','NODE_COMPILE_CACHE','BUN_RUNTIME_TRANSPILER_CACHE_PATH'])if(!process.env[key].startsWith(process.env.TMPDIR+path.sep))process.exit(9)"], { env });
  assert.equal(result.exitCode, 0);
  assert.deepEqual(result.marker.relocatedEnvironmentKeys.sort(), Object.keys(env).sort());
  assert.equal(JSON.stringify(result.marker).includes('/external/cache'), false);
  assert.equal(await exists(path.join(result.directory, 'runtime')), false);
});

test('preflight refuses managed capacity and actual disk free limits before spawn', async (t) => {
  const { root, storage } = await fixture(t, { maxRunBytes: 1000, maxManagedBytes: 1000 });
  await marker(root);
  await fs.writeFile(path.join(root, '.artifacts', 'large'), Buffer.alloc(2000));
  await assert.rejects(storage.run([process.execPath, '-e', 'process.exit(0)'], { env: {} }), /preflight failed/);
  const low = await createStorage(root, { ...base, minFreeBytes: Number.MAX_SAFE_INTEGER });
  await assert.rejects(low.run([process.execPath, '-e', 'process.exit(0)'], { env: {} }), /disk free/);
});

test('overflow stops only owned process group, retains failed evidence and removes runtime', async (t) => {
  const { root, storage } = await fixture(t, { maxRunBytes: 4096 });
  const unrelated = spawn(process.execPath, ['-e', 'setInterval(()=>{},1000)'], { stdio: 'ignore' });
  t.after(() => unrelated.kill('SIGKILL'));
  const started = Date.now();
  const result = await storage.run([process.execPath, '-e', "const fs=require('node:fs');fs.mkdirSync(process.env.ASSET_LOADER_EVIDENCE_ROOT,{recursive:true});fs.writeFileSync(process.env.ASSET_LOADER_EVIDENCE_ROOT+'/large',Buffer.alloc(8192));process.on('SIGTERM',()=>{});setInterval(()=>{},1000)"], { env: {} });
  assert.ok(Date.now() - started < 5000);
  assert.notEqual(result.exitCode, 0);
  assert.equal(result.marker.status, 'failed');
  assert.match(result.marker.reason, /byte limit/);
  assert.equal(await exists(path.join(result.directory, 'runtime')), false);
  assert.equal(await exists(path.join(result.directory, 'evidence', 'asset-loader', 'large')), true);
  assert.doesNotThrow(() => process.kill(unrelated.pid, 0));
  assert.equal((await storage.clean({ apply: true })).runs[0].action, 'skip');
  assert.equal(await exists(root), true);
});

test('descendant shutdown evidence overflow fails a main child that exited zero', { timeout: 10000 }, async (t) => {
  const { storage } = await fixture(t, { maxRunBytes: 4096, pollIntervalMs: 60000, shutdownGraceMs: 1000 });
  const descendant = "const fs=require('node:fs');fs.mkdirSync(process.env.ASSET_LOADER_EVIDENCE_ROOT,{recursive:true});process.on('SIGTERM',()=>{fs.writeFileSync(process.env.ASSET_LOADER_EVIDENCE_ROOT+'/shutdown-large',Buffer.alloc(8192));process.exit(0)});setInterval(()=>{},1000);process.send('ready');process.disconnect()";
  const main = `const {spawn}=require('node:child_process');const child=spawn(process.execPath,['-e',${JSON.stringify(descendant)}],{stdio:['ignore','ignore','ignore','ipc']});child.once('message',()=>process.exit(0));child.once('error',()=>process.exit(8));`;
  const result = await storage.run([process.execPath, '-e', main], { category: 'disposable-test', env: {} });
  assert.equal(result.marker.exitCode, 0);
  assert.notEqual(result.exitCode, 0);
  assert.equal(result.marker.status, 'failed');
  assert.match(result.marker.reason, /byte limit/);
  assert.equal((await fs.stat(path.join(result.directory, 'evidence', 'asset-loader', 'shutdown-large'))).size, 8192);
  assert.equal(await exists(path.join(result.directory, 'runtime')), false);
  assert.equal((await storage.clean({ apply: true })).runs[0].action, 'skip');
});

test('wrapper forwards signal and waits for child shutdown before removing runtime', async (t) => {
  const { root, policy } = await fixture(t);
  const output = path.join(root, 'result.json');
  const code = `import {createStorage} from ${JSON.stringify(moduleUrl)};import{writeFile}from'node:fs/promises';const s=await createStorage(${JSON.stringify(root)},${JSON.stringify(policy)});const r=await s.run([process.execPath,'-e',${JSON.stringify("const fs=require('node:fs');fs.mkdirSync(process.env.ASSET_LOADER_EVIDENCE_ROOT,{recursive:true});fs.writeFileSync(process.env.ASSET_LOADER_EVIDENCE_ROOT+'/ready','ready');process.on('SIGTERM',()=>{setTimeout(()=>{fs.writeFileSync(process.env.TMPDIR+'/last-write','done');fs.writeFileSync(process.env.ASSET_LOADER_EVIDENCE_ROOT+'/terminated','done');process.exit(0)},30)});setInterval(()=>{},1000)")}],{env:{}});await writeFile(${JSON.stringify(output)},JSON.stringify(r));process.exitCode=r.exitCode;`;
  const child = spawn(process.execPath, ['--input-type=module', '-e', code], { stdio: 'ignore' });
  t.after(() => child.kill('SIGKILL'));
  const closed = new Promise((resolve) => child.once('close', resolve));
  let runDir;
  await waitFor(async () => {
    const runs = path.join(root, '.artifacts', 'runs');
    if (!await exists(runs)) return false;
    const entries = await fs.readdir(runs); if (!entries.length) return false;
    runDir = path.join(runs, entries[0]);
    return exists(path.join(runDir, 'evidence', 'asset-loader', 'ready'));
  });
  child.kill('SIGTERM');
  assert.equal(await closed, 143);
  const result = JSON.parse(await fs.readFile(output));
  assert.equal(result.marker.status, 'failed');
  assert.equal(result.marker.signal, 'SIGTERM');
  assert.equal(await exists(path.join(runDir, 'runtime')), false);
  assert.equal(await exists(path.join(runDir, 'evidence', 'asset-loader', 'terminated')), true);
});
