import * as fs from 'node:fs/promises';
import { constants as fsConstants } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { randomUUID } from 'node:crypto';
import { spawn } from 'node:child_process';
import { constants as osConstants } from 'node:os';

const PROJECT_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const MARKER = 'storage-run.json';
const ID = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/;
const delay = (ms) => new Promise((resolve) => setTimeout(resolve, ms));
const inside = (base, candidate) => candidate !== base && candidate.startsWith(`${base}${path.sep}`);

export function validatePolicy(value) {
  const fields = ['maxRunBytes', 'maxManagedBytes', 'minFreeBytes', 'legacyEvidenceMaxBytes', 'retainSuccessDays', 'retainSuccessCount', 'pollIntervalMs', 'shutdownGraceMs'];
  if (!value || value.version !== 1 || Object.keys(value).some((key) => !['version', ...fields].includes(key))) throw new Error('Unknown storage policy version or fields');
  for (const key of fields) {
    if (!Number.isSafeInteger(value[key]) || value[key] < (key === 'minFreeBytes' ? 0 : 1)) throw new Error(`Invalid policy ${key}`);
  }
  if (value.maxRunBytes > value.maxManagedBytes || value.pollIntervalMs > 60000 || value.shutdownGraceMs > 60000) throw new Error('Invalid storage policy limits');
  return Object.freeze({ ...value });
}

async function statOrNull(target) {
  try { return await fs.lstat(target); } catch (error) { if (error.code === 'ENOENT') return null; throw error; }
}

export async function treeSize(target) {
  const stat = await statOrNull(target);
  if (!stat) return { bytes: 0, unsafe: false };
  if (stat.isSymbolicLink()) return { bytes: 0, unsafe: true };
  if (stat.isFile()) return { bytes: stat.size, unsafe: false };
  if (!stat.isDirectory()) return { bytes: 0, unsafe: true };
  let bytes = 0, unsafe = false;
  for (const name of await fs.readdir(target)) {
    const result = await treeSize(path.join(target, name));
    bytes += result.bytes;
    unsafe ||= result.unsafe;
  }
  return { bytes, unsafe };
}

function validMarker(marker, id) {
  return marker?.version === 1 && ID.test(id) && marker.runId === id
    && Array.isArray(marker.command) && marker.command.length > 0 && marker.command.every((part) => typeof part === 'string' && part.length > 0)
    && ['disposable-test', 'manual'].includes(marker.category)
    && Number.isSafeInteger(marker.ownerPid) && marker.ownerPid > 0
    && Number.isFinite(Date.parse(marker.startedAt))
    && ['running', 'success', 'failed'].includes(marker.status)
    && (marker.status === 'running' ? marker.finishedAt === null : Number.isFinite(Date.parse(marker.finishedAt)) && Date.parse(marker.finishedAt) >= Date.parse(marker.startedAt))
    && (marker.status !== 'success' || marker.exitCode === 0 && marker.signal === null);
}

function alive(pid) {
  try { process.kill(pid, 0); return true; } catch (error) { return error.code !== 'ESRCH'; }
}

export async function createStorage(root, policyInput) {
  const policy = validatePolicy(policyInput);
  root = path.resolve(root);
  if (root === path.parse(root).root || ['.artifacts', 'runs', '.git', '.omo'].includes(path.basename(root))) throw new Error('Unsafe project root');
  if ((await fs.realpath(root)) !== root || !(await fs.lstat(root)).isDirectory()) throw new Error('Project root must be a real directory without symlinks');
  const artifacts = path.join(root, '.artifacts');
  const runs = path.join(artifacts, 'runs');

  async function guard(target = runs) {
    if (target !== artifacts && target !== runs && !inside(runs, target)) throw new Error('Unsafe storage path escape');
    if (await fs.realpath(root) !== root) throw new Error('Project root changed');
    let current = root;
    for (const name of path.relative(root, target).split(path.sep)) {
      current = path.join(current, name);
      const stat = await statOrNull(current);
      if (!stat) break;
      if (stat.isSymbolicLink() || !stat.isDirectory()) throw new Error(`Unsafe storage directory: ${current}`);
    }
  }

  async function initialize() {
    await guard();
    await fs.mkdir(runs, { recursive: true });
    await guard();
  }

  async function inspect(id) {
    const dir = path.join(runs, id);
    await guard();
    const stat = await fs.lstat(dir);
    if (!stat.isDirectory() || stat.isSymbolicLink()) return { id, bytes: 0, reason: 'unknown or symlink entry' };
    const size = await treeSize(dir);
    if (size.unsafe) return { id, bytes: size.bytes, reason: 'symlink or special entry' };
    let marker;
    try { marker = JSON.parse(await fs.readFile(path.join(dir, MARKER), 'utf8')); } catch { return { id, bytes: size.bytes, reason: 'unknown marker' }; }
    if (!validMarker(marker, id)) return { id, bytes: size.bytes, reason: 'malformed marker' };
    const pin = await statOrNull(path.join(dir, '.keep'));
    return { id, bytes: size.bytes, marker, identity: { ino: stat.ino, dev: stat.dev }, reason: pin ? 'pinned' : alive(marker.ownerPid) ? 'live owner PID' : marker.status !== 'success' ? 'failure or unfinished evidence' : marker.category !== 'disposable-test' ? 'non-disposable category' : null };
  }

  async function report({ legacy = true } = {}) {
    await guard();
    const entries = await statOrNull(runs) ? await fs.readdir(runs) : [];
    const results = [];
    for (const id of entries) results.push(await inspect(id));
    const filesystem = await fs.statfs(root);
    const managed = await treeSize(artifacts);
    const legacySize = legacy ? await treeSize(path.join(root, '.omo')) : null;
    const legacyRoot = legacy ? await statOrNull(path.join(root, '.omo')) : null;
    const evidenceRoot = legacyRoot?.isDirectory() && !legacyRoot.isSymbolicLink() ? await statOrNull(path.join(root, '.omo', 'evidence')) : null;
    const legacyEvidence = legacyRoot?.isDirectory() && !legacyRoot.isSymbolicLink() ? await treeSize(path.join(root, '.omo', 'evidence')) : null;
    const legacyRootUnsafe = Boolean(legacyRoot && (!legacyRoot.isDirectory() || legacyRoot.isSymbolicLink()) || evidenceRoot && (!evidenceRoot.isDirectory() || evidenceRoot.isSymbolicLink()));
    return { policy, managedLogicalBytes: managed.bytes, managedUnsafe: managed.unsafe, diskFreeBytes: filesystem.bavail * filesystem.bsize, legacyOmoLogicalBytes: legacySize?.bytes, legacyEvidenceLogicalBytes: legacy ? legacyEvidence?.bytes ?? 0 : undefined, legacyUnsafe: legacySize?.unsafe ?? false, legacyRootUnsafe, legacyAdvisoryOnly: true, runs: results };
  }

  function violations(result, runBytes = 0, { includeLegacy = false } = {}) {
    const errors = [];
    if (result.managedUnsafe) errors.push('Managed area contains symlinks or special entries');
    if (runBytes > policy.maxRunBytes) errors.push('Run logical byte limit exceeded');
    if (result.runs.some((run) => run.bytes > policy.maxRunBytes)) errors.push('Managed run logical byte limit exceeded');
    if (result.managedLogicalBytes >= policy.maxManagedBytes) errors.push('Managed logical byte limit reached');
    if (result.diskFreeBytes < policy.minFreeBytes) errors.push('Minimum actual disk free space breached');
    if (includeLegacy && result.legacyEvidenceLogicalBytes > policy.legacyEvidenceMaxBytes) errors.push('Legacy .omo/evidence logical byte limit exceeded; archive and verify retained evidence before starting more browser QA');
    if (includeLegacy && result.legacyRootUnsafe) errors.push('Legacy root contains symlinks or special entries; review before browser QA');
    return errors;
  }

  function eligible(result, now) {
    const successes = new Map();
    for (const run of result.runs) {
      if (run.marker?.status !== 'success') continue;
      const key = JSON.stringify(run.marker.command);
      if (!successes.has(key)) successes.set(key, []);
      successes.get(key).push(run);
    }
    const newest = new Set();
    for (const group of successes.values()) {
      group.sort((a, b) => Date.parse(b.marker.finishedAt) - Date.parse(a.marker.finishedAt) || b.id.localeCompare(a.id));
      for (const run of group.slice(0, policy.retainSuccessCount)) newest.add(run.id);
    }
    return result.runs.map((run) => ({ ...run, reason: run.reason ?? (newest.has(run.id) ? 'newest successful runs' : now - Date.parse(run.marker.finishedAt) < policy.retainSuccessDays * 86400000 ? 'minimum age retention' : null) }));
  }

  async function removeTree(target) {
    if (!inside(runs, target)) throw new Error('Unsafe deletion path');
    await guard(path.dirname(target));
    const stat = await fs.lstat(target);
    if (stat.isSymbolicLink()) throw new Error('Refusing deletion through symlink');
    if (stat.isDirectory()) {
      for (const name of await fs.readdir(target)) await removeTree(path.join(target, name));
      await guard(target);
      await fs.rmdir(target);
    } else if (stat.isFile()) {
      await guard(path.dirname(target));
      const fresh = await fs.lstat(target);
      if (!fresh.isFile() || fresh.ino !== stat.ino || fresh.dev !== stat.dev) throw new Error('Deletion entry changed');
      await fs.unlink(target);
    } else throw new Error('Refusing deletion of special entry');
  }

  async function clean({ apply = false, now = Date.now() } = {}) {
    const candidates = eligible(await report({ legacy: false }), now);
    const output = [];
    for (const candidate of candidates) {
      if (candidate.reason || !apply) { output.push({ id: candidate.id, action: candidate.reason ? 'skip' : 'would-delete', reason: candidate.reason }); continue; }
      const fresh = eligible(await report({ legacy: false }), now).find((run) => run.id === candidate.id);
      if (!fresh || fresh.reason || fresh.identity.ino !== candidate.identity.ino || fresh.identity.dev !== candidate.identity.dev || JSON.stringify(fresh.marker) !== JSON.stringify(candidate.marker)) { output.push({ id: candidate.id, action: 'skip', reason: 'changed during cleanup' }); continue; }
      const dir = path.join(runs, candidate.id);
      await guard(dir);
      await removeTree(dir);
      output.push({ id: candidate.id, action: 'deleted' });
    }
    return { apply, runs: output };
  }

  async function run(command, { category = 'manual', env = process.env } = {}) {
    if (!Array.isArray(command) || !command.length || command.some((part) => typeof part !== 'string' || !part)) throw new Error('Supply an executable after --');
    if (!['manual', 'disposable-test'].includes(category)) throw new Error('Invalid run category');
    const before = await report({ legacy: false });
    const preflight = violations(before);
    if (preflight.length) throw new Error(`Storage preflight failed: ${preflight.join('; ')}. Run storage:report and storage:clean; archive retained failures manually.`);
    await initialize();
    const id = randomUUID(), dir = path.join(runs, id);
    await fs.mkdir(dir);
    const evidence = path.join(dir, 'evidence'), runtime = path.join(dir, 'runtime');
    const childEnv = { ...env }, relocatedEnvironmentKeys = [];
    const defaults = { ASSET_LOADER_EVIDENCE_ROOT: path.join(evidence, 'asset-loader'), ASSET_PIPELINE_EVIDENCE_ROOT: path.join(evidence, 'asset-pipeline'), TMPDIR: runtime, TMP: runtime, TEMP: runtime, XDG_CACHE_HOME: path.join(runtime, 'cache'), VITE_CACHE_DIR: path.join(runtime, 'vite'), NODE_COMPILE_CACHE: path.join(runtime, 'node-cache'), BUN_RUNTIME_TRANSPILER_CACHE_PATH: path.join(runtime, 'bun-cache'), npm_config_cache: path.join(runtime, 'npm-cache'), NPM_CONFIG_CACHE: path.join(runtime, 'npm-cache') };
    try {
      for (const [key, defaultValue] of Object.entries(defaults)) {
        const runtimeVariable = !key.startsWith('ASSET_');
        if (runtimeVariable && childEnv[key]) relocatedEnvironmentKeys.push(key);
        const value = childEnv[key] && !runtimeVariable ? path.resolve(root, childEnv[key]) : defaultValue;
        const allowed = key.startsWith('ASSET_') ? evidence : runtime;
        if (value !== allowed && !inside(allowed, value)) throw new Error(`${key} points outside this owned run. Unset ${key} so storage run can assign its ${key.startsWith('ASSET_') ? 'evidence' : 'runtime'} directory; external paths cannot be monitored.`);
        childEnv[key] = value;
      }
      await fs.mkdir(evidence);
      await fs.mkdir(runtime);
    } catch (error) { await fs.rmdir(dir); throw error; }
    const marker = { version: 1, runId: id, command, category, startedAt: new Date().toISOString(), finishedAt: null, ownerPid: process.pid, status: 'running', exitCode: null, signal: null, relocatedEnvironmentKeys };
    async function writeMarker() {
      await guard(dir);
      const handle = await fs.open(path.join(dir, MARKER), fsConstants.O_WRONLY | fsConstants.O_CREAT | fsConstants.O_NOFOLLOW, 0o600);
      try {
        const stat = await handle.stat();
        if (!stat.isFile() || stat.nlink !== 1) throw new Error('Unsafe ownership marker');
        await handle.truncate(0);
        await handle.writeFile(`${JSON.stringify(marker, null, 2)}\n`);
      } finally { await handle.close(); }
    }
    await writeMarker();
    console.error(`Storage run ${id}: ${dir}`);
    if (relocatedEnvironmentKeys.length) console.error(`Storage: ${relocatedEnvironmentKeys.join(', ')} reassigned to this run's owned runtime directory.`);
    let child, stopped = false, reason = null, forwardedSignal = null, killTimer, monitorBusy = false, descendantsTerminated = true;
    const signalOwned = (signal) => {
      if (!child?.pid) return;
      try { process.kill(process.platform === 'win32' ? child.pid : -child.pid, signal); } catch (error) { if (error.code !== 'ESRCH') throw error; }
    };
    const stop = (message, signal = 'SIGTERM') => {
      if (stopped) return;
      stopped = true; reason = message;
      signalOwned(signal);
      killTimer = setTimeout(() => signalOwned('SIGKILL'), policy.shutdownGraceMs);
    };
    const handlers = new Map(['SIGINT', 'SIGTERM', 'SIGHUP'].map((signal) => [signal, () => { forwardedSignal = signal; stop(`Forwarded ${signal}`, signal); }]));
    let timer;
    let result;
    try {
      child = spawn(command[0], command.slice(1), { cwd: root, env: childEnv, stdio: 'inherit', detached: process.platform !== 'win32' });
      for (const [signal, handler] of handlers) process.on(signal, handler);
      const monitor = async () => {
        if (monitorBusy) return;
        monitorBusy = true;
        try {
          const current = await report({ legacy: false });
          const errors = violations(current, (await treeSize(dir)).bytes);
          if (errors.length) stop(errors.join('; '));
        } catch (error) { stop(`Storage monitoring failed: ${error.message}`); }
        finally { monitorBusy = false; }
      };
      timer = setInterval(() => { void monitor(); }, policy.pollIntervalMs);
      result = await new Promise((resolve) => {
        child.once('error', (error) => resolve({ code: 1, signal: null, error: error.message }));
        child.once('close', (code, signal) => resolve({ code, signal }));
      });
      clearInterval(timer);
      while (monitorBusy) await delay(10);
      await monitor();
      // A command may leave descendants in its process group after its own exit.
      signalOwned('SIGTERM');
      if (process.platform !== 'win32' && child.pid) {
        const deadline = Date.now() + policy.shutdownGraceMs;
        while (alive(-child.pid) && Date.now() < deadline) await delay(20);
        if (alive(-child.pid)) {
          signalOwned('SIGKILL');
          const killDeadline = Date.now() + policy.shutdownGraceMs;
          while (alive(-child.pid) && Date.now() < killDeadline) await delay(20);
          if (alive(-child.pid)) { descendantsTerminated = false; reason = `${reason ?? ''} Owned process group still exists after SIGKILL; runtime retained`.trim(); }
        }
      }
      try {
        const finalReport = await report({ legacy: false });
        const finalErrors = violations(finalReport, (await treeSize(dir)).bytes);
        if (finalErrors.length) reason = [reason, ...finalErrors].filter(Boolean).join('; ');
      } catch (error) {
        reason = [reason, `Final storage monitoring failed: ${error.message}`].filter(Boolean).join('; ');
      }
    } finally {
      clearInterval(timer); clearTimeout(killTimer);
      for (const [signal, handler] of handlers) process.off(signal, handler);
    }
    marker.finishedAt = new Date().toISOString();
    marker.exitCode = result.code;
    marker.signal = result.signal ?? forwardedSignal;
    marker.status = !reason && !result.error && result.code === 0 ? 'success' : 'failed';
    marker.reason = reason ?? result.error ?? null;
    try {
      if (!descendantsTerminated) throw new Error('Owned process group termination could not be verified');
      if ((await treeSize(runtime)).unsafe) throw new Error('Runtime contains symlinks or special files; retained for manual review');
      await removeTree(runtime);
    } catch (error) { marker.status = 'failed'; marker.reason = `${marker.reason ?? ''} Runtime cleanup failed: ${error.message}`.trim(); }
    await writeMarker();
    return { id, directory: dir, marker, exitCode: marker.status === 'success' ? 0 : result.code || (marker.signal ? 128 + (osConstants.signals[marker.signal] ?? 1) : 1) };
  }
  return { report, clean, run, violations, guard };
}

async function main(args) {
  const usage = 'Usage: node scripts/storage.mjs report|check|clean [--apply] [--include-legacy] [--policy FILE]\n       node scripts/storage.mjs run [--category disposable-test|manual] [--policy FILE] -- EXECUTABLE [ARGS...]\nclean defaults to dry-run. .keep pins a run. Failures require manual archive. External evidence overrides must be unset.\nTemp/cache variables are explicitly reassigned to owned runtime. Only owned .artifacts output is monitored; polling can overshoot byte caps between checks.';
  const separator = args.indexOf('--');
  if (!args.length || args.slice(0, separator < 0 ? args.length : separator).includes('--help')) { console.log(usage); return 0; }
  const action = args.shift();
  let policyFile = path.join(PROJECT_ROOT, 'storage-policy.json'), apply = false, includeLegacy = false, category = 'manual';
  while (args.length && args[0] !== '--') {
    const flag = args.shift();
    if (flag === '--policy' && args.length) policyFile = path.resolve(args.shift());
    else if (flag === '--category' && args.length && action === 'run') category = args.shift();
    else if (flag === '--apply' && action === 'clean') apply = true;
    else if (flag === '--include-legacy' && action === 'check') includeLegacy = true;
    else throw new Error(`Unknown option ${flag}\n${usage}`);
  }
  const storage = await createStorage(PROJECT_ROOT, JSON.parse(await fs.readFile(policyFile, 'utf8')));
  if (action === 'run') {
    if (args.shift() !== '--') throw new Error('Supply an executable after --');
    return (await storage.run(args, { category })).exitCode;
  }
  if (args.length) throw new Error(`Unexpected arguments\n${usage}`);
  if (action === 'clean') { console.log(JSON.stringify(await storage.clean({ apply }), null, 2)); return 0; }
  if (!['report', 'check'].includes(action)) throw new Error(usage);
  const result = await storage.report();
  if (includeLegacy) result.legacyAdvisoryOnly = false;
  console.log(JSON.stringify(result, null, 2));
  const errors = storage.violations(result, 0, { includeLegacy });
  if (action === 'check' && errors.length) { console.error(errors.join('\n')); return 1; }
  return 0;
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  main(process.argv.slice(2)).then((code) => { process.exitCode = code; }).catch((error) => { console.error(error.message); process.exitCode = 1; });
}
