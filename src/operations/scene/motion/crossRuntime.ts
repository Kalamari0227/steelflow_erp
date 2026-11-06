import { createHash } from 'node:crypto';
import { readFileSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { spawnSync } from 'node:child_process';
import { z } from 'zod';
import { authorize, boundaryCase, fixture, sampled, furnaceCase, chainCase } from './testFixtures';
import type { Fixture } from './testFixtures';
import { MotionError } from './errors';

const jsonValue = z.json();
type Json = z.infer<typeof jsonValue>;
function equivalent(a: Json, b: Json): boolean {
  if (typeof a === 'number' && typeof b === 'number') return Math.abs(a - b) <= 1e-10 * Math.max(1, Math.abs(a), Math.abs(b));
  if (a === b) return true;
  if (Array.isArray(a) && Array.isArray(b)) return a.length === b.length && a.every((value, i) => { const other = b[i]; return other !== undefined && equivalent(value, other); });
  if (typeof a === 'object' && a !== null && !Array.isArray(a) && typeof b === 'object' && b !== null && !Array.isArray(b)) return Object.keys(a).length === Object.keys(b).length && Object.entries(a).every(([key, value]) => { const other = b[key]; return other !== undefined && equivalent(value, other); });
  return false;
}
const outputDir = process.argv[2], serverRequestPath = process.argv[3];
if (outputDir === undefined || serverRequestPath === undefined) throw new MotionError('invalid_contract', 'output directory and saved Python request path required');
const hash = (bytes: string | Uint8Array) => createHash('sha256').update(bytes).digest('hex');
const serialize = (c: Fixture) => JSON.stringify({ envelope: c.envelope, context: c.context });
const cases: { readonly name: string; readonly bytes: Uint8Array; readonly exit: number }[] = [];
const add = (name: string, raw: string, exit = 0) => cases.push({ name, bytes: new TextEncoder().encode(raw), exit });
cases.push({ name: 'actual-saved-python-request', bytes: new Uint8Array(readFileSync(serverRequestPath)), exit: 0 });
for (const time of [0, 500, 1499, 1500, 2499, 2500, 2600]) add(`time-${time}`, serialize(sampled(time)));
for (const speed of [1, 2, 4]) { const c = sampled(1500); c.context.snapshot.run.speed = speed; add(`speed-${speed}`, serialize(c)); }
for (const state of ['paused', 'stale', 'blocked']) {
  const c = fixture(); Object.assign(c.envelope, { clock_state: state, confirmed_sim_ms: 1800 }); c.context.snapshot.run.elapsed_ms = 1800;
  add(`held-${state}`, serialize(authorize(c)));
}
for (const gap of [0, 0.01, 0.010001]) add(`boundary-${gap}`, serialize(boundaryCase(gap)), gap > 0.01 ? 2 : 0);
add('authoritative-mobile-root', serialize(fixture(1)));
add('noncommutative-moving-chain', serialize(chainCase()));
add('zero-channel-static-warehouse', serialize(fixture(3)));
add('three-joint-crane', serialize(fixture(4)));
for (const clock_state of ['paused', 'stale', 'blocked']) {
  const c = fixture(4); Object.assign(c.envelope, { clock_state, confirmed_sim_ms: 1800 }); c.context.snapshot.run.elapsed_ms = 1800;
  add(`crane-held-${clock_state}`, serialize(authorize(c)));
}
const wrongPolicy = fixture(3); wrongPolicy.envelope.recipe_id = 'motion:scope:internal:load'; add('wrong-known-policy', serialize(authorize(wrongPolicy)), 2);
add('fixed-thermal-state', serialize(furnaceCase()));
const stale = fixture(); stale.envelope.run_id = 'old-run'; add('stale-run', serialize(stale), 2);
const unauthorized = fixture(); unauthorized.envelope.material.support_local_mm = [0, 0, 0]; add('unauthorized', serialize(unauthorized), 2);
const missingHold = fixture(); Object.assign(missingHold.envelope, { frozen_progress: null }); add('missing-held', serialize(missingHold), 2);
for (const token of ['true', '"1"', '1.0', '1e0']) add(`schema-${token.replaceAll('"', '')}`, serialize(fixture()).replace('"schema_version":1', `"schema_version":${token}`), 2);
add('duplicate-decoded-key', serialize(fixture()).replace('"run_id":', '"run_id":"duplicate","run_\\u0069d":'), 2);
add('text-bom-double', '\ufeff\ufeff' + serialize(fixture()), 2);
add('utf8-bom-single', '\ufeff' + serialize(fixture()));
cases.push({ name: 'utf16-rejected', bytes: new Uint8Array([0xff, 0xfe, 0x7b, 0]), exit: 2 });
cases.push({ name: 'malformed-utf8', bytes: new Uint8Array([0xc0, 0xaf]), exit: 2 });
const errorSchema = z.object({ error: z.object({ code: z.string() }) });
const results = cases.map(testCase => {
  const requestPath = join(outputDir, `${testCase.name}.request.json`);
  writeFileSync(requestPath, testCase.bytes);
  const pythonArgs = ['-m', 'app.operations.motion_cli'];
  const python = spawnSync('backend/.venv/bin/python', pythonArgs, { input: testCase.bytes, encoding: 'utf8', env: { ...process.env, PYTHONPATH: 'backend' } });
  const tsArgs = ['src/operations/scene/motion/cli.ts', requestPath];
  const typescript = spawnSync(process.execPath, tsArgs, { encoding: 'utf8', env: process.env });
  const pythonPath = join(outputDir, `${testCase.name}.python.json`), tsPath = join(outputDir, `${testCase.name}.typescript.json`);
  writeFileSync(pythonPath, python.stdout); writeFileSync(tsPath, typescript.stdout);
  writeFileSync(join(outputDir, `${testCase.name}.stderr.log`), python.stderr + typescript.stderr);
  let matching = false;
  if (python.stdout.trim() !== '' && typescript.stdout.trim() !== '') {
    const a: unknown = JSON.parse(python.stdout), b: unknown = JSON.parse(typescript.stdout);
    matching = testCase.exit === 0 ? equivalent(jsonValue.parse(a), jsonValue.parse(b)) : errorSchema.parse(a).error.code === errorSchema.parse(b).error.code;
  }
  return { scenario: testCase.name, expectedExit: testCase.exit, pythonExit: python.status, typescriptExit: typescript.status, matching,
    pass: matching && python.status === testCase.exit && typescript.status === testCase.exit,
    pythonInvocation: ['backend/.venv/bin/python', ...pythonArgs], typescriptInvocation: [process.execPath, ...tsArgs],
    requestPath, pythonPath, tsPath, requestSha256: hash(testCase.bytes), pythonSha256: hash(python.stdout), typescriptSha256: hash(typescript.stdout) };
});
const report = { pass: results.every(r => r.pass), scenarios: results.length, results };
writeFileSync(join(outputDir, 'cross-runtime-report.json'), JSON.stringify(report, null, 2));
console.log(JSON.stringify({ pass: report.pass, scenarios: report.scenarios, failures: results.filter(r => !r.pass) }, null, 2));
if (!report.pass) process.exitCode = 1;
