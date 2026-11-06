import { createHash, randomUUID } from 'node:crypto';
import { realpathSync, lstatSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { dirname, basename, resolve, join } from 'node:path';
import { createServer } from 'node:net';
import { execFileSync } from 'node:child_process';

export const protectedPorts = Object.freeze([8000, 4173, 8002, 4175]);

export function assertNoSymlink(path) {
  for (let cursor = resolve(path); ; cursor = dirname(cursor)) {
    try {
      if (lstatSync(cursor).isSymbolicLink()) throw new Error(`QA evidence path must not traverse symlinks: ${cursor}`);
    } catch (error) { if (error.code !== 'ENOENT') throw error; }
    if (cursor === dirname(cursor)) break;
  }
}

export function assertFreshEvidenceDirectory(path) {
  assertNoSymlink(path);
  try { lstatSync(path); }
  catch (error) { if (error.code === 'ENOENT') return; throw error; }
  throw new Error('Evidence directory already exists; use a fresh attempt path');
}

export function createOwnedEvidenceDirectory(path) {
  assertFreshEvidenceDirectory(path);
  mkdirSync(dirname(path), { recursive: true });
  mkdirSync(path);
  const token = randomUUID();
  writeFileSync(join(path, '.qa-owner.json'), JSON.stringify({ token, pid: process.pid }), { flag: 'wx', mode: 0o600 });
  return token;
}

export function verifyOwnedEvidenceDirectory(path, token) {
  const marker = join(path, '.qa-owner.json');
  assertNoSymlink(marker);
  const owner = JSON.parse(readFileSync(marker, 'utf8'));
  if (!token || owner.token !== token || !Number.isSafeInteger(owner.pid) || owner.pid <= 0) throw new Error('Evidence directory is not owned by this QA attempt');
  process.kill(owner.pid, 0);
  return token;
}

export function assertAllowedPort(value) {
  const port = typeof value === 'string' && /^\d+$/.test(value) ? Number(value) : value;
  if (!Number.isInteger(port) || port < 1024 || port > 65535 || protectedPorts.includes(port)) {
    throw new Error(`Unsafe QA port: ${value}`);
  }
  return port;
}

export function fingerprintDatabase(path) {
  let canonical = resolve(path);
  try { canonical = realpathSync(canonical); }
  catch (error) {
    if (error.code !== 'ENOENT') throw error;
    canonical = join(realpathSync(dirname(canonical)), basename(canonical));
  }
  return createHash('sha256').update(canonical, 'utf8').digest('hex');
}

export function assertOwnedHealth(health, expected, { verifyWeb = true } = {}) {
  if (!expected || typeof expected.attempt_id !== 'string' || !expected.attempt_id ||
      !/^[a-f0-9]{64}$/.test(expected.db_fingerprint) || !Number.isSafeInteger(expected.pid) || expected.pid <= 0) {
    throw new Error('Invalid owned process receipt');
  }
  for (const origin of [expected.api_origin, expected.web_origin]) {
    const url = new URL(origin);
    if (url.hostname !== '127.0.0.1' || url.protocol !== 'http:') throw new Error('Foreign QA origin');
    assertAllowedPort(url.port);
  }
  if (health?.status !== 'ok' || health.qa?.attempt_id !== expected.attempt_id ||
      health.qa?.db_fingerprint !== expected.db_fingerprint || health.qa?.pid !== expected.pid) {
    throw new Error('Foreign QA health: attempt, database, or spawned PID mismatch');
  }
  process.kill(expected.pid, 0);
  const listeners = execFileSync('/usr/sbin/lsof', ['-nP', '-t', `-iTCP:${new URL(expected.api_origin).port}`, '-sTCP:LISTEN'], { encoding: 'utf8' }).trim().split('\n').map(Number);
  if (listeners.length !== 1 || listeners[0] !== expected.pid) throw new Error('Foreign QA listener PID');
  if (verifyWeb) {
    if (!Number.isSafeInteger(expected.web_pid) || expected.web_pid <= 0) throw new Error('Invalid owned web process receipt');
    const webListeners = execFileSync('/usr/sbin/lsof', ['-nP', '-t', `-iTCP:${new URL(expected.web_origin).port}`, '-sTCP:LISTEN'], { encoding: 'utf8' }).trim().split('\n').map(Number);
    if (webListeners.length !== 1 || webListeners[0] !== expected.web_pid) throw new Error('Foreign QA web listener PID');
  }
}

export async function portAvailable(port) {
  assertAllowedPort(port);
  const server = createServer();
  return new Promise((resolveAvailable, reject) => {
    server.once('error', error => error.code === 'EADDRINUSE' ? resolveAvailable(false) : reject(error));
    server.listen(port, '127.0.0.1', () => server.close(error => error ? reject(error) : resolveAvailable(true)));
  });
}

export async function choosePorts(apiValue, webValue) {
  const requested = { api: assertAllowedPort(apiValue ?? 8003), web: assertAllowedPort(webValue ?? 4176) };
  if (requested.api === requested.web) throw new Error('QA API and web ports must differ');
  const occupied = [];
  for (let offset = 0; offset < 100; offset += 1) {
    const api = requested.api + offset;
    const web = requested.web + offset;
    if (protectedPorts.includes(api) || protectedPorts.includes(web) || api === web) continue;
    if (await portAvailable(api) && await portAvailable(web)) return { api, web, requested, occupied };
    occupied.push({ api, web });
    if (apiValue !== undefined || webValue !== undefined) throw new Error(`Requested QA ports occupied: ${api}/${web}`);
  }
  throw new Error('No unused QA port pair available');
}
