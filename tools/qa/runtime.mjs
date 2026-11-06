import { spawn, execFileSync } from 'node:child_process';
import { appendFileSync, writeFileSync, readFileSync, readdirSync, lstatSync, existsSync, renameSync, rmSync, constants } from 'node:fs';
import { join, resolve, dirname, basename } from 'node:path';
import { createHash, randomUUID } from 'node:crypto';
import { setTimeout as delay } from 'node:timers/promises';
import { assertAllowedPort, assertOwnedHealth, fingerprintDatabase, portAvailable, assertNoSymlink } from './ownership.mjs';

export const workspace = resolve(import.meta.dirname, '../..');
export function json(path, value) {
  assertNoSymlink(path);
  const temporary = join(dirname(path), `.${basename(path)}.${randomUUID()}.tmp`);
  try {
    writeFileSync(temporary, `${JSON.stringify(value, null, 2)}\n`, { flag: 'wx', mode: 0o600 });
    renameSync(temporary, path);
  } finally { rmSync(temporary, { force: true }); }
}
export function appendLog(path, value) {
  assertNoSymlink(path);
  if (existsSync(path) && lstatSync(path).nlink > 1) throw new Error('QA log must not be a hard link');
  appendFileSync(path, value, { flag: constants.O_WRONLY | constants.O_APPEND | constants.O_CREAT | constants.O_NOFOLLOW });
}
export const hash = data => createHash('sha256').update(data).digest('hex');

export function snapshot(paths) {
  const entries = {};
  const visit = path => {
    if (!existsSync(path)) { entries[path] = null; return; }
    const stat = lstatSync(path);
    if (stat.isSymbolicLink()) { entries[path] = 'symlink'; return; }
    if (stat.isDirectory()) {
      for (const child of readdirSync(path).sort()) {
        if (!['.venv', '__pycache__', '.pytest_cache', 'node_modules'].includes(child)) visit(join(path, child));
      }
    } else if (stat.isFile()) entries[path] = { bytes: stat.size, sha256: hash(readFileSync(path)) };
  };
  paths.forEach(visit);
  return entries;
}

export function processOwner(evidence, env) {
  const resources = [];
  let cleanupPromise;
  const log = join(evidence, 'command.log');
  const record = () => json(join(evidence, 'processes.json'), resources.map(({ child, done, ...receipt }) => receipt));
  function start(command, args, options = {}) {
    if (cleanupPromise) throw new Error('Cannot spawn after owned cleanup began');
    appendLog(log, `${JSON.stringify({ command, args, cwd: options.cwd ?? workspace })}\n`);
    const child = spawn(command, args, { cwd: options.cwd ?? workspace, env, detached: true, stdio: ['ignore', 'pipe', 'pipe'] });
    const resource = { child, pid: child.pid, command, args, started_at: new Date().toISOString(), exit_code: null, signal: null };
    resource.done = new Promise(resolveDone => {
      child.once('error', error => { resource.error = error.message; record(); resolveDone(1); });
      child.once('close', (code, signal) => { resource.exit_code = code; resource.signal = signal; record(); resolveDone(code ?? 1); });
    });
    for (const stream of [child.stdout, child.stderr]) stream.on('data', data => { appendLog(log, data); process.stdout.write(data); });
    resources.push(resource);
    record();
    return resource;
  }
  async function execute(command, args, options) {
    const resource = start(command, args, options);
    const code = await resource.done;
    if (code !== 0) throw new Error(`Command failed (${code}): ${command} ${args.join(' ')}`);
    return resource;
  }
  async function stopResources() {
    const stopped = [];
    for (const resource of [...resources].reverse()) {
      if (!resource.pid) continue;
      let alive = true;
      try { process.kill(-resource.pid, 0); }
      catch (error) { if (error.code !== 'ESRCH') throw error; alive = false; }
      if (alive) {
        process.kill(-resource.pid, 'SIGTERM');
        await Promise.race([resource.done, delay(5_000)]);
        try { process.kill(-resource.pid, 'SIGKILL'); }
        catch (error) { if (error.code !== 'ESRCH') throw error; }
        await resource.done;
      }
      stopped.push({ pid: resource.pid, owned: true, already_exited: !alive });
    }
    return stopped;
  }
  function cleanup() {
    cleanupPromise ??= stopResources();
    return cleanupPromise;
  }
  return { start, execute, cleanup };
}

async function waitHttp(url, resource, signal, check) {
  const deadline = Date.now() + 60_000;
  while (Date.now() < deadline) {
    signal?.throwIfAborted();
    if (resource.exit_code !== null || resource.signal || resource.error) throw new Error(`Owned server exited before ready: ${url}`);
    try {
      const response = await fetch(url, { signal: AbortSignal.timeout(1_000) });
      if (response.ok) { if (check) check(await response.json()); return; }
    } catch (error) {
      if (!(error instanceof TypeError) && error.name !== 'TimeoutError') throw error;
    }
    await delay(100, undefined, { signal });
  }
  throw new Error(`Owned server did not become ready: ${url}`);
}

/** Select only registered owned fixtures; family names are never interpreted as paths. */
export function selectOwnedFixture(env) {
  const family = env.STEELFLOW_QA_ASSET_FAMILY;
  if (family !== undefined) {
    if (env.STEELFLOW_QA_OBSERVER_FIXTURE !== undefined || env.STEELFLOW_QA_ASSET_FIXTURE !== undefined) throw new Error('Family fixture conflicts with legacy fixture flags');
    switch (family) {
      case 'hot-rolling': return 'hot-rolling';
      case 'steelmaking': return 'steelmaking';
      case 'mechanical-followers': return 'mechanical-followers';
      default: throw new Error('Unknown owned asset family fixture');
    }
  }
  return env.STEELFLOW_QA_OBSERVER_FIXTURE === '1' ? 'factory-observer'
    : env.STEELFLOW_QA_ASSET_FIXTURE === '1' ? 'factory-assets' : null;
}

export async function startServices(owner, env, signal) {
  const fixture = selectOwnedFixture(env);
  const apiPort = assertAllowedPort(env.STEELFLOW_QA_API_PORT);
  const webPort = assertAllowedPort(env.STEELFLOW_QA_WEB_PORT);
  if (!await portAvailable(apiPort) || !await portAvailable(webPort)) throw new Error('QA ports became occupied; refusing to reuse or stop occupants');
  const backend = owner.start(join(workspace, 'backend/.venv/bin/python'), ['-m', 'uvicorn', 'app.factory_bootstrap:create_legacy_fixture_app', '--factory', '--host', '127.0.0.1', '--port', String(apiPort)], { cwd: join(workspace, 'backend') });
  if (!backend.pid) throw new Error('Backend spawn did not produce a PID');
  const identity = {
    attempt_id: env.STEELFLOW_QA_ATTEMPT_ID,
    db_fingerprint: fingerprintDatabase(env.STEELFLOW_E2E_DATABASE_PATH),
    pid: backend.pid,
    api_origin: `http://127.0.0.1:${apiPort}`,
    web_origin: `http://127.0.0.1:${webPort}`,
  };
  await waitHttp(`${identity.api_origin}/health`, backend, signal, health => assertOwnedHealth(health, identity, { verifyWeb: false }));
  json(join(env.STEELFLOW_EVIDENCE_DIR, 'backend-identity.json'), identity);
  const vite = join(workspace, 'node_modules/vite/bin/vite.js');
  // This owned QA build explicitly opts into test diagnostics; normal builds stay off.
  env.VITE_STEELFLOW_QA_PROBE = '1';
  const fixtureConfig = fixture ? ['--config', join(workspace, `tests/fixtures/${fixture}/vite.config.mts`)] : [];
  await owner.execute(process.execPath, [vite, 'build', ...fixtureConfig, '--outDir', env.STEELFLOW_E2E_BUILD_DIR]);
  signal?.throwIfAborted();
  const frontend = owner.start(process.execPath, [vite, 'preview', ...fixtureConfig, '--host', '127.0.0.1', '--port', String(webPort), '--strictPort', '--outDir', env.STEELFLOW_E2E_BUILD_DIR]);
  if (!frontend.pid) throw new Error('Frontend spawn did not produce a PID');
  await waitHttp(fixture ? `${identity.web_origin}/tests/fixtures/${fixture}/index.html` : identity.web_origin, frontend, signal);
  const completeIdentity = { ...identity, web_pid: frontend.pid };
  await waitHttp(`${identity.api_origin}/health`, backend, signal, health => assertOwnedHealth(health, completeIdentity));
  json(env.STEELFLOW_QA_IDENTITY_PATH, completeIdentity);
  return completeIdentity;
}

export function hostMetadata() {
  let gpu;
  try { gpu = execFileSync('/usr/sbin/system_profiler', ['SPDisplaysDataType', '-json'], { encoding: 'utf8', timeout: 15_000 }); }
  catch (error) { gpu = `unavailable: ${error.message}`; }
  return { platform: process.platform, arch: process.arch, node: process.version, gpu };
}
