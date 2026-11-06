// @vitest-environment node
import { readFileSync } from 'node:fs';
import { createHash } from 'node:crypto';
import { join } from 'node:path';
import { describe, expect, it } from 'vitest';
import golden from '../../../shared/fixtures/factory-world-v2-cases.json';
import encoding from '../../../shared/fixtures/factory-world-v2-encoding-cases.json';
import { pointSchema, poseSchema } from './worldContractMath';
import { parseContractJson } from './worldContractJson';
import { businessEpochMs, canonicalManifest, composePose, contactDistance, contactWithinTolerance, mmToM, parseBundle, parseFactoryWorld, parseManifest, parseWorld, phaseAt, sha256, supportPose, transformPoint, wallToSimMs, WorldContractError } from './worldContract';

function required<T>(value: T | undefined): T { if (value === undefined) throw new RangeError('Missing fixture'); return value; }
function fixture() { return structuredClone(required(golden.valid[0]).world); }
function artifacts() { return new Map(golden.bundle.artifacts.map(row => [row.path, new Uint8Array(readFileSync(join('shared/fixtures', row.file)))])); }
function assertFrozen(value: unknown): void {
  if (typeof value !== 'object' || value === null) return;
  expect(Object.isFrozen(value)).toBe(true);
  for (const child of Object.values(value)) assertFrozen(child);
}

function encodingBundle(row: (typeof encoding.cases)[number]) {
  const bytes = new Uint8Array(readFileSync(join('shared/fixtures', row.file)));
  const entry = required(row.manifest.artifacts[0]);
  expect(createHash('sha256').update(bytes).digest('hex')).toBe(row.sha256);
  expect(entry.sha256).toBe(row.sha256);
  expect(createHash('sha256').update(row.canonical_utf8).digest('hex')).toBe(row.manifest.bundle_hash);
  const raw = JSON.stringify(row.manifest);
  expect(canonicalManifest(parseManifest(raw))).toBe(row.canonical_utf8);
  return parseBundle(raw, new Map([[entry.path, bytes]]));
}

describe('encoding byte boundary', () => {
  it.each(encoding.cases.filter(row => row.accepted))('accepts valid $name with correct raw and manifest hashes', async row => {
    const bundle = await encodingBundle(row);
    expect(bundle.world).toEqual(required(golden.valid[0]).world); assertFrozen(bundle);
  });
  it.each(encoding.cases.filter(row => !row.accepted))('rejects invalid $name after correct hash verification', async row => {
    const failure: unknown = await encodingBundle(row).then(() => undefined, (error: unknown) => error);
    if (failure instanceof WorldContractError) expect(failure.code).toBe('json');
    else {
      expect(failure).toBeInstanceOf(TypeError);
      expect(String(failure)).toMatch(/encoded data|encoding/i);
    }
  });
  it.each(['\ufeff', '\ufeff\ufeff', ' \ufeff'])('rejects invalid decoded JSON prefix %j without byte-boundary normalization', prefix => {
    expect(() => parseWorld(prefix + JSON.stringify(required(golden.valid[0]).world))).toThrow('json');
    expect(() => parseManifest(prefix + JSON.stringify(golden.bundle.manifest))).toThrow('json');
  });
});

describe('valid factory world contract', () => {
  it.each(golden.valid)('accepts shared $name without changing equipment identity', row => {
    const world = parseWorld(JSON.stringify(row.world));
    expect(world).toEqual(row.world); expect(world.owners[0]?.id).toBe('BF-A');
    expect(world.segments.map(segment => segment.mode)).toEqual(['road', 'rail', 'hot_metal', 'ladle', 'roller', 'conveyor', 'sea']);
    assertFrozen(world);
    expect(Reflect.set(required(world.owners[0]).pose.position, '0', 999)).toBe(false);
    expect(Reflect.set(world.nodes, '0', null)).toBe(false);
  });
  it.each(golden.transforms)('matches shared transform $name', row => {
    const point = row.poses.reduce((value, pose) => transformPoint(value, poseSchema.parse(pose)), pointSchema.parse(row.point));
    point.forEach((value, axis) => expect(value).toBeCloseTo(required(row.expected[axis]), 12));
  });
  it.each(golden.contacts)('matches shared contact $name using support rather than center', row => {
    const pose = poseSchema.parse(row.material_pose), support = pointSchema.parse(row.local_support), socket = pointSchema.parse(row.socket_world);
    expect(contactDistance(pose, support, socket)).toBeCloseTo(row.expected_distance, 12);
    expect(contactWithinTolerance(pose, support, socket)).toBe(row.expected_valid);
  });
  it('preserves support contact through geometry changes and nested yaw', () => {
    const socket = composePose({ position: [3, 0, 0], yaw_rad: Math.PI / 2 }, { position: [10, 5, 0], yaw_rad: Math.PI / 2 });
    const thin = supportPose(socket.position, [1, -1, 0], socket.yaw_rad), thick = supportPose(socket.position, [1, -3, 0], socket.yaw_rad);
    expect(thick.position[1] - thin.position[1]).toBe(2);
    expect(contactWithinTolerance(thin, [1, -1, 0], socket.position)).toBe(true);
    expect(contactWithinTolerance(thick, [1, -3, 0], socket.position)).toBe(true);
    expect(contactWithinTolerance(thick, [1, -1, 0], socket.position)).toBe(false);
    assertFrozen(socket); assertFrozen(thin);
  });
  it.each(golden.dimensions)('converts $mm mm explicitly to meters', row => expect(mmToM(row.mm)).toBe(row.expected_m));
  it.each(golden.time)('matches business clock $name', row => expect(businessEpochMs(row.sim_ms)).toBe(row.expected_epoch_ms));
  it('anchors the business epoch to the actual UTC calendar', () => {
    expect(businessEpochMs(0)).toBe(Date.UTC(2026, 9, 30));
    expect(new Date(businessEpochMs(1000)).toISOString()).toBe('2026-10-30T00:01:00.000Z');
  });
  it.each(golden.wall_time)('applies speed $speed once at wall to simulation boundary', row => {
    expect(wallToSimMs(row.wall_ms, row.speed)).toBe(row.expected_sim_ms);
    expect(businessEpochMs(row.expected_sim_ms) - businessEpochMs(0)).toBe(row.expected_sim_ms * 60);
  });
  it.each(golden.phases)('clamps server phase at $sim_ms', row => expect(phaseAt(row.sim_ms, row.start_ms, row.end_ms)).toBe(row.expected));
  it('accepts lexical integral 2.0 and exact centimeter endpoint/socket limits', () => {
    const world = fixture(); required(required(world.segments[0]).points[0])[0] = .01;
    required(required(world.owners[0]).sockets[0]).pose.position[0] = .01;
    expect(parseWorld(JSON.stringify(world).replace('"version":2', '"version":2.0')).version).toBe(2);
  });
  it('checks rotated envelope corners in footprint local axes', () => {
    const world = fixture();
    required(world.footprints[0]).pose.yaw_rad = Math.PI / 2;
    required(world.allowed_interiors[0]).pose.yaw_rad = Math.PI / 2;
    expect(parseFactoryWorld(world).allowed_interiors).toHaveLength(1);
    required(world.allowed_interiors[0]).pose.yaw_rad = 0;
    expect(() => parseFactoryWorld(world)).toThrow('envelope');
  });
  it('verifies actual fixture bytes and independently specified canonical hash', async () => {
    const bundle = await parseBundle(JSON.stringify(golden.bundle.manifest), artifacts());
    expect(canonicalManifest(bundle.manifest)).toBe(golden.bundle.canonical_utf8);
    expect(await sha256(new TextEncoder().encode(golden.bundle.canonical_utf8))).toBe(golden.bundle.manifest.bundle_hash);
    expect(bundle.world).toEqual(required(golden.valid[0]).world); assertFrozen(bundle);
  });
  it('sorts manifest records by ASCII and excludes its own hash', () => {
    const base = golden.bundle.manifest, entry = required(base.artifacts[0]);
    const manifest = parseManifest(JSON.stringify({ ...base, artifacts: [entry, { ...entry, role: 'fixture', path: 'z.txt' }, { ...entry, role: 'fixture', path: 'Z.txt' }] }));
    const canonical = canonicalManifest(manifest);
    expect(canonical.indexOf('Z.txt')).toBeLessThan(canonical.indexOf('fixtures/'));
    expect(canonical.indexOf('fixtures/')).toBeLessThan(canonical.indexOf('z.txt'));
    expect(canonical).not.toContain(base.bundle_hash);
  });
  it('snapshots caller-owned bytes before asynchronous digest work', async () => {
    const bytes = artifacts(), promise = parseBundle(JSON.stringify(golden.bundle.manifest), bytes);
    required(bytes.values().next().value).fill(0);
    expect((await promise).world.version).toBe(2);
  });
});

describe('invalid factory world contract', () => {
  it.each(golden.invalid)('rejects shared $name', row => expect(() => parseWorld(JSON.stringify(row.world))).toThrow());
  it.each(golden.invalid_json)('rejects shared raw JSON $name', row => expect(() => parseWorld(row.raw)).toThrow());
  it.each(golden.invalid_time)('rejects shared clock $name', row => expect(() => Reflect.apply(businessEpochMs, undefined, [row.value])).toThrow());
  it.each([NaN, Infinity, -Infinity])('rejects nonfinite coordinate %s without JSON coercion', value => {
    const world = fixture(); required(world.nodes[0]).position[0] = value;
    expect(() => parseFactoryWorld(world)).toThrow();
  });
  it.each(['{"x":1,"x":2}', '{"x":1,"\\u0078":2}', '{"outer":{"x":1,"x":2}}', '{"x":NaN}', '{"x":Infinity}', '{"x":1,}', '{"x":01}', '{"x":"unterminated}', '{]'])('rejects malformed or duplicate JSON %s', raw => expect(() => parseContractJson(raw)).toThrow());
  it('handles nested string punctuation without false duplicate keys', () => {
    expect(parseContractJson('{"a":"{ \\\"a\\\": ","b":{"a":1},"c":[{"a":2}]}')).toEqual({ a: '{ "a": ', b: { a: 1 }, c: [{ a: 2 }] });
  });
  it.each([
    ['extra world key', (world: ReturnType<typeof fixture>) => Object.assign(world, { camera_scale: 2 })],
    ['extra nested key', (world: ReturnType<typeof fixture>) => Object.assign(required(world.owners[0]).pose, { speed: 4 })],
    ['empty nodes', (world: ReturnType<typeof fixture>) => world.nodes.splice(0)],
    ['missing collection', (world: ReturnType<typeof fixture>) => Reflect.deleteProperty(world, 'ports')],
    ['newline identifier', (world: ReturnType<typeof fixture>) => { required(world.owners[0]).id += '\n'; }],
    ['socket beyond centimeter', (world: ReturnType<typeof fixture>) => { required(required(world.owners[0]).sockets[0]).pose.position[0] = .010001; }],
    ['duplicate socket', (world: ReturnType<typeof fixture>) => { const owner = required(world.owners[0]); owner.sockets.push(required(owner.sockets[0])); }],
    ['duplicate global location', (world: ReturnType<typeof fixture>) => { required(world.slots[0]).id = required(world.nodes[0]).id; }],
    ['zero length segment', (world: ReturnType<typeof fixture>) => { const segment = required(world.segments[0]); segment.points = [[0, 0, 0], [0, 0, 0]]; }],
    ['missing owner footprint', (world: ReturnType<typeof fixture>) => world.footprints.splice(0)],
  ])('rejects %s', (_name, change) => { const world = fixture(); change(world); expect(() => parseFactoryWorld(world)).toThrow(); });
  it.each([-1, .5, NaN, Infinity, Number.MAX_SAFE_INTEGER + 1, 143970111360001])('rejects invalid business time %s', value => expect(() => businessEpochMs(value)).toThrow());
  it.each([0, -1, NaN, Infinity])('rejects invalid dimension %s', value => expect(() => mmToM(value)).toThrow());
  it('rejects invalid speed, overflow and zero/negative phase intervals', () => {
    for (const speed of [0, 3, 8, .5]) expect(() => wallToSimMs(1, speed)).toThrow();
    expect(() => wallToSimMs(Number.MAX_SAFE_INTEGER, 4)).toThrow();
    expect(() => phaseAt(0, 10, 10)).toThrow(); expect(() => phaseAt(0, 11, 10)).toThrow();
  });
  it('rejects nonfinite public geometry and arithmetic overflow', () => {
    expect(() => transformPoint([Infinity, 0, 0], { position: [0, 0, 0], yaw_rad: 0 })).toThrow();
    expect(() => transformPoint([1e308, 0, 0], { position: [1e308, 0, 0], yaw_rad: 0 })).toThrow();
    expect(() => contactDistance({ position: [1e308, 0, 0], yaw_rad: 0 }, [0, 0, 0], [-1e308, 0, 0])).toThrow();
    expect(() => supportPose([NaN, 0, 0], [0, 0, 0], 0)).toThrow();
  });
  it.each(['../world.json', '/world.json', '.hidden/world.json', 'world/../file', 'world\\file', 'world.json\n'])('rejects unsafe manifest path %s', path => {
    const manifest = structuredClone(golden.bundle.manifest); required(manifest.artifacts[0]).path = path;
    expect(() => parseManifest(JSON.stringify(manifest))).toThrow();
  });
  it('rejects missing bytes, raw-byte corruption and wrong manifest hash/version', async () => {
    const raw = JSON.stringify(golden.bundle.manifest);
    await expect(parseBundle(raw, new Map())).rejects.toThrow();
    const corrupt = artifacts(); required(corrupt.values().next().value)[0] = 0;
    await expect(parseBundle(raw, corrupt)).rejects.toThrow('artifact_hash');
    await expect(parseBundle(JSON.stringify({ ...golden.bundle.manifest, bundle_hash: '0'.repeat(64) }), artifacts())).rejects.toThrow('bundle_hash');
    expect(() => parseManifest(JSON.stringify({ ...golden.bundle.manifest, world_version: 3 }))).toThrow();
    const wrong = structuredClone(golden.bundle.manifest); required(wrong.artifacts[0]).version = '3';
    expect(() => parseManifest(JSON.stringify(wrong))).toThrow('version');
    const duplicate = structuredClone(golden.bundle.manifest); duplicate.artifacts.push(required(duplicate.artifacts[0]));
    expect(() => parseManifest(JSON.stringify(duplicate))).toThrow('duplicate');
  });
  it('rejects malformed world even with newly correct raw and canonical hashes', async () => {
    const manifest = structuredClone(golden.bundle.manifest), entry = required(manifest.artifacts[0]);
    const bytes = new TextEncoder().encode('{"version":2}'); entry.sha256 = await sha256(bytes);
    manifest.bundle_hash = await sha256(new TextEncoder().encode(canonicalManifest(parseManifest(JSON.stringify(manifest)))));
    await expect(parseBundle(JSON.stringify(manifest), new Map([[entry.path, bytes]]))).rejects.toThrow();
  });
});

describe('spatial same bytes boundary', () => {
  const cases: { cases: { name: string; accepted: boolean; raw: string }[] } = JSON.parse(readFileSync('shared/fixtures/factory-world-v2-spatial-cases.json', 'utf8'));
  it.each(cases.cases)('$name', row => {
    const bytes = Buffer.from(row.raw, 'utf8');
    if (row.accepted) expect(parseWorld(bytes.toString('utf8')).version).toBe(2);
    else expect(() => parseWorld(bytes.toString('utf8'))).toThrow();
  });
  it('deeply freezes spatial records and preserves omitted legacy field', () => {
    const world = parseWorld(readFileSync('shared/fixtures/factory-world-v2-spatial.json', 'utf8'));
    assertFrozen(world);
    const callerInput = JSON.parse(readFileSync('shared/fixtures/factory-world-v2-spatial.json', 'utf8'));
    const snapshot = parseFactoryWorld(callerInput);
    callerInput.spatial.profiles[0].size_m[0] = 999;
    expect(required(required(snapshot.spatial).profiles[0]).size_m[0]).toBe(2);
    const spatial = required(world.spatial), profile = required(spatial.profiles[0]);
    expect(Reflect.set(profile.size_m, '0', 999)).toBe(false);
    expect(Reflect.set(profile, 'clearance_m', 999)).toBe(false);
    expect(Reflect.set(spatial.profiles, '0', null)).toBe(false);
    expect(parseWorld(readFileSync('shared/fixtures/factory-world-v2-example.json', 'utf8'))).not.toHaveProperty('spatial');
  });
});

describe('explicit support-relative envelope centers', () => {
  it('preserves signed offsets as frozen points without defaults', () => {
    const cases: { cases: { name: string; raw: string }[] } = JSON.parse(readFileSync('shared/fixtures/factory-world-v2-spatial-cases.json', 'utf8'));
    const world = parseWorld(required(cases.cases.find(row => row.name === 'explicit-signed-envelope-offsets')).raw);
    const profile = required(required(world.spatial).profiles[0]);
    expect(profile.body_offset_m).toEqual([-1, 2, .5]);
    expect(profile.load_offset_m).toEqual([.25, 4, -.5]);
    expect(Reflect.set(profile.body_offset_m, '1', 999)).toBe(false);
    expect(required(required(parseWorld(JSON.stringify(world)).spatial).profiles[0])).toEqual(profile);
  });
});
