// @vitest-environment node
import { createHash } from 'node:crypto';
import { spawnSync } from 'node:child_process';
import { cpSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { beforeAll, expect, it } from 'vitest';

const repo = process.cwd();
const evidence = resolve(process.env.ASSET_PIPELINE_EVIDENCE_ROOT ?? `.omo/evidence/asset-pipeline-${Date.now()}`);
const a = resolve(evidence, 'build-a');
const b = resolve(evidence, 'build-b');
const tool = JSON.parse(readFileSync('assets/toolchain.json', 'utf8')) as { executable_path: string };
let sequence = 0;
const digest = (bytes: Uint8Array) => createHash('sha256').update(bytes).digest('hex');
function run(label: string, command: string, args: string[], timeout = 110_000) {
  const result = spawnSync(command, args, {
    cwd: repo, encoding: 'utf8', timeout, maxBuffer: 16 * 1024 * 1024,
    env: { ...process.env, PYTHONDONTWRITEBYTECODE: '1', PYTHONPYCACHEPREFIX: resolve(evidence, 'runtime/pycache'),
      BLENDER_USER_RESOURCES: resolve(evidence, 'runtime/blender'), TMPDIR: resolve(evidence, 'runtime/tmp'),
      XDG_CACHE_HOME: resolve(evidence, 'runtime/cache'), npm_config_cache: resolve(evidence, 'runtime/npm'), BUN_INSTALL_CACHE_DIR: resolve(evidence, 'runtime/bun') },
  });
  const prefix = resolve(evidence, `${++sequence}-${label}`);
  writeFileSync(`${prefix}.stdout.log`, result.stdout ?? '');
  writeFileSync(`${prefix}.stderr.log`, result.stderr ?? '');
  writeFileSync(`${prefix}.json`, JSON.stringify({ command, args, timeout, exit: result.status, signal: result.signal, error: result.error?.message }, null, 2));
  expect(result.error, label).toBeUndefined();
  expect(result.signal, label).toBeNull();
  return result;
}
function build(out: string) {
  const r = run('blender', tool.executable_path, ['--background', '--factory-startup', '--python-exit-code', '1', '--python', 'scripts/assets/build.py', '--', '--out', out]);
  expect(r.status, r.stderr + r.stdout).toBe(0);
  expect(r.stdout).toContain('STEELFLOW_BUILD_COMPLETE');
}
function verify(root: string) {
  return run('verify', process.execPath, ['scripts/assets/verify.mjs', '--root', root]);
}
function manifest(root: string) {
  return JSON.parse(readFileSync(resolve(root, 'public/assets/steelworks/manifest.json'), 'utf8'));
}
beforeAll(() => {
  mkdirSync(evidence, { recursive: true });
  writeFileSync(resolve(evidence, 'resources.json'), JSON.stringify({ owner: 'T12-pipeline-test', resources: [a, b, resolve(evidence, 'corrupt'), resolve(evidence, 'runtime')], cleanup: 'retain proof outputs; runtime removed after process completion' }, null, 2));
  mkdirSync(resolve(evidence, 'runtime/tmp'), { recursive: true });
  build(a);
}, 120_000);

it('reproducible uses two independent pinned Blender processes with identical mesh, node, texture and animation semantics', () => {
  build(b);
  for (const root of [a, b]) {
    const r = verify(root);
    expect(r.status, r.stderr).toBe(0);
    const result = JSON.parse(r.stdout);
    expect(result.status).toBe('PASS');
    expect(result.assets).toHaveLength(2);
    expect(result.assets.every((asset: { lods: unknown[] }) => asset.lods.length === 3)).toBe(true);
  }
  const left = manifest(a); const right = manifest(b);
  const semantics = (m: typeof left) => m.assets.map((asset: { id: string; lods: { semantic_geometry_sha256: string }[] }) => ({ id: asset.id, hashes: asset.lods.map(lod => lod.semantic_geometry_sha256) }));
  expect(semantics(left)).toEqual(semantics(right));
  expect(left.assets[0].lods[0].semantic_geometry_sha256).not.toBe(left.assets[0].lods[2].semantic_geometry_sha256);
  writeFileSync(resolve(evidence, 'reproducible.assertions.json'), JSON.stringify({ status: 'PASS', first: semantics(left), second: semantics(right), distinctProcesses: true }, null, 2));
}, 120_000);

it('reject_corrupt rejects actual GLB axis, pivot, texture, scale, missing mechanical node and geometry byte corruption', () => {
  const tracked = ['scripts/assets/build.py', 'scripts/assets/verify.mjs', 'assets/source/recipe.json', 'assets/toolchain.json'];
  const before = Object.fromEntries(tracked.map(path => [path, digest(readFileSync(path))]));
  const cases = ['axis', 'pivot', 'texture', 'scale', 'missing-node', 'semantic-bytes'] as const;
  const reports = [];
  for (const kind of cases) {
    const root = resolve(evidence, 'corrupt', kind); cpSync(a, root, { recursive: true });
    const m = manifest(root); const asset = m.assets[0]; const lod = asset.lods[0];
    const path = resolve(root, lod.artifact.path); const bytes = readFileSync(path);
    const jsonLength = bytes.readUInt32LE(12); const gltf = JSON.parse(bytes.subarray(20, 20 + jsonLength).toString());
    const bin = Buffer.from(bytes.subarray(28 + jsonLength));
    const node = (id: string) => gltf.nodes.find((n: { extras?: { semantic_id?: string } }) => n.extras?.semantic_id === id);
    if (kind === 'axis') node('axis_front').translation = [0, 0, 1];
    if (kind === 'pivot') node('cutting_tool').translation[1] += 0.2;
    if (kind === 'scale') node('root').scale = [0.01, 0.01, 0.01];
    if (kind === 'texture') gltf.textures[0].source = 999;
    if (kind === 'missing-node') node('cutting_tool').extras.semantic_id = 'removed';
    if (kind === 'semantic-bytes') {
      const accessor = gltf.accessors[gltf.meshes[0].primitives[0].attributes.POSITION];
      const view = gltf.bufferViews[accessor.bufferView];
      const offset = (view.byteOffset ?? 0) + (accessor.byteOffset ?? 0);
      bin.writeFloatLE(bin.readFloatLE(offset) + 0.03125, offset);
    }
    const json = Buffer.from(JSON.stringify(gltf)); const padded = Buffer.alloc(Math.ceil(json.length / 4) * 4, 32); json.copy(padded);
    const output = Buffer.alloc(28 + padded.length + bin.length);
    output.write('glTF'); output.writeUInt32LE(2, 4); output.writeUInt32LE(output.length, 8);
    output.writeUInt32LE(padded.length, 12); output.writeUInt32LE(0x4e4f534a, 16); padded.copy(output, 20);
    output.writeUInt32LE(bin.length, 20 + padded.length); output.writeUInt32LE(0x004e4942, 24 + padded.length); bin.copy(output, 28 + padded.length);
    writeFileSync(path, output); lod.artifact.sha256 = digest(output);
    writeFileSync(resolve(root, 'public/assets/steelworks/manifest.json'), JSON.stringify(m));
    const r = verify(root);
    expect(r.status, kind).toBe(1);
    const expected = { axis: 'axis', pivot: 'pivot', texture: 'texture', scale: 'scale', 'missing-node': 'missing-node', 'semantic-bytes': 'semantic' }[kind];
    expect(r.stderr, kind).toContain(expected);
    reports.push({ kind, exit: r.status, stderr: r.stderr });
  }
  const after = Object.fromEntries(tracked.map(path => [path, digest(readFileSync(path))]));
  expect(after).toEqual(before);
  writeFileSync(resolve(evidence, 'reject_corrupt.assertions.json'), JSON.stringify({ status: 'PASS', reports, sourceBefore: before, sourceAfter: after }, null, 2));
}, 120_000);
