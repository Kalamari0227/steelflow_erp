import { mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { spawnSync } from 'node:child_process';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { Matrix4, Mesh, Quaternion, Vector3 } from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { z } from 'zod';
import { followerMetadata } from '../../../../tests/fixtures/mechanical-followers/metadata';
import { required } from './manifestTestFixtures';
import { parseAssetManifestValue } from './manifest';
import { bindingsFromAssetManifest, evaluateMotion, parseMotionContext, parseMotionEnvelopeValue } from '../motion/contracts';
import { recipes } from '../motion/testFixtures';
import { miniatureRequest } from '../../../../tests/fixtures/mechanical-followers/poses';
import { AssetRegistry } from './registry';
import { collectResources, inspectGlb, loadAsset } from './loader';
import { parseProductionAssetManifest } from './manifest';
import { mutateMiniature, rows } from '../../../../tests/fixtures/mechanical-followers/mutate';

const fixtureRoot = 'tests/fixtures/mechanical-followers/generated';
const rawActual = readFileSync(`${fixtureRoot}/public/assets/steelworks/manifest.json`, 'utf8');
function actual() { return parseProductionAssetManifest(rawActual); }
function registry() {
  vi.stubGlobal('self', globalThis);
  vi.stubGlobal('createImageBitmap', async () => ({ width: 32, height: 32, close: () => undefined }));
  const manifest = actual(), input = miniatureRequest(manifest, 0.5);
  const store = new AssetRegistry(rawActual, { origin: 'http://127.0.0.1:4176', read: async url => new Uint8Array(readFileSync(`${fixtureRoot}/public${new URL(url).pathname}`)).buffer });
  store.beginRun(input.pose.run_id, input.envelope.bundle_hash);
  const entity = store.entity({ run_id: input.pose.run_id, entity_type: 'equipment', entity_id: input.pose.owner_id, bundle_hash: input.envelope.bundle_hash }, required(manifest.assets[0]).id);
  return { manifest, store, entity };
}
afterEach(() => { vi.unstubAllGlobals(); vi.restoreAllMocks(); });

function geometryMutant(mutation: 'no-mesh' | 'empty-primitives' | 'position-count-zero' | 'index-count-zero' | 'index-out-of-range' | 'degenerate' | 'nonfinite-position' | 'line-primitive' | 'shared-mesh' | 'empty-canonical-sweep') {
  return mutateMiniature((raw, binary) => {
    const nodes = rows(raw, 'nodes'), meshes = rows(raw, 'meshes');
    const subtree = (index: number): number[] => [index, ...z.array(z.number()).parse(required(nodes[index]).children ?? []).flatMap(subtree)];
    const followerIndex = nodes.findIndex(node => node.name === 'roughing_roll_follower_1');
    const owned = subtree(mutation === 'empty-canonical-sweep' ? nodes.findIndex(node => node.name === 'roughing_roll') : followerIndex);
    const barrel = required(nodes.find(node => node.name === 'roughing_roll_follower_1_barrel'));
    if (mutation === 'shared-mesh') {
      const sharedBarrel = required(nodes.find(node => node.name === 'roughing_roll_follower_2_barrel'));
      for (const name of ['roughing_roll_follower_2', 'roughing_roll_follower_3']) {
        const ownBarrel = required(nodes.find(node => node.name === `${name}_barrel`));
        for (const index of subtree(nodes.findIndex(node => node.name === name))) if (nodes[index] !== ownBarrel) Reflect.deleteProperty(required(nodes[index]), 'mesh');
        ownBarrel.mesh = sharedBarrel.mesh;
      }
      return;
    }
    for (const index of owned) if (mutation === 'no-mesh' || mutation === 'empty-canonical-sweep' || nodes[index] !== barrel) Reflect.deleteProperty(required(nodes[index]), 'mesh');
    if (mutation === 'no-mesh' || mutation === 'empty-canonical-sweep') return;
    const mesh = required(meshes[z.number().parse(barrel.mesh)]);
    if (mutation === 'empty-primitives') { mesh.primitives = []; return; }
    const primitive = required(rows(mesh, 'primitives')[0]);
    if (mutation === 'line-primitive') { primitive.mode = 1; return; }
    const attributes = z.record(z.string(), z.number()).parse(primitive.attributes);
    const accessor = required(rows(raw, 'accessors')[z.number().parse(mutation.startsWith('index-') || mutation === 'degenerate' ? primitive.indices : attributes.POSITION)]);
    if (mutation === 'position-count-zero' || mutation === 'index-count-zero') { accessor.count = 0; return; }
    const view = required(rows(raw, 'bufferViews')[z.number().parse(accessor.bufferView)]);
    const offset = z.number().parse(view.byteOffset ?? 0) + z.number().parse(accessor.byteOffset ?? 0);
    if (mutation === 'nonfinite-position') { binary.writeFloatLE(NaN, offset); return; }
    const component = z.number().parse(accessor.componentType), count = z.number().parse(accessor.count);
    const positionCount = z.number().parse(required(rows(raw, 'accessors')[z.number().parse(attributes.POSITION)]).count);
    for (let index = 0; index < (mutation === 'degenerate' ? count : 1); index += 1) {
      const value = mutation === 'degenerate' ? 0 : positionCount + 1;
      switch (component) {
        case 5121: binary.writeUInt8(value, offset + index); break;
        case 5123: binary.writeUInt16LE(value, offset + index * 2); break;
        case 5125: binary.writeUInt32LE(value, offset + index * 4); break;
        default: throw new RangeError('Unexpected actual index layout');
      }
    }
  });
}

function offlineGeometryResult(changed: ReturnType<typeof mutateMiniature>, label: string) {
  const temporary = mkdtempSync(join(tmpdir(), 't61-geometry-'));
  try {
    const bytesPath = join(temporary, 'actual.glb'), descriptor = join(temporary, 'asset.json');
    writeFileSync(bytesPath, new Uint8Array(changed.bytes)); writeFileSync(descriptor, JSON.stringify({ asset: changed.asset, bytesPath }));
    const result = spawnSync(process.execPath, ['tests/fixtures/mechanical-followers/check-mutant.mjs', descriptor], { encoding: 'utf8' });
    const evidence = process.env.MECHANICAL_FOLLOWER_EVIDENCE_ROOT;
    if (evidence) { mkdirSync(evidence, { recursive: true }); writeFileSync(join(evidence, `${label}.glb`), new Uint8Array(changed.bytes)); writeFileSync(join(evidence, `${label}.json`), JSON.stringify({ asset: changed.asset, lod: changed.lod, exit: result.status, stdout: result.stdout, stderr: result.stderr }, null, 2)); }
    return result;
  } finally { rmSync(temporary, { recursive: true, force: true }); }
}

describe('each follower owns actual renderable triangle geometry', () => {
  it.each(['no-mesh', 'empty-primitives', 'position-count-zero', 'index-count-zero', 'index-out-of-range', 'degenerate', 'nonfinite-position', 'line-primitive'] as const)('rejects %s using actual decoded geometry and the offline pipeline', async mutation => {
    // Given: other followers, parent, siblings, animation, IDs and re-signed checksums remain valid.
    vi.stubGlobal('self', globalThis); vi.stubGlobal('createImageBitmap', async () => ({ width: 32, height: 32, close: () => undefined }));
    const changed = geometryMutant(mutation);
    // When / Then
    const rejection: unknown = await loadAsset(changed.asset, changed.lod, { origin: 'http://127.0.0.1:4176', read: async () => changed.bytes }).then(loaded => { loaded.dispose(); return null; }, (error: unknown) => error);
    expect(rejection).toMatchObject({ code: 'binding' });
    const offline = offlineGeometryResult(changed, `geometry-${mutation}`);
    expect(offline.status, offline.stdout + offline.stderr).toBe(1);
  });

  it('rejects zero actual vertex samples for a canonical moving sweep as well', () => {
    // Given: follower subtrees still contain real valid geometry.
    const changed = geometryMutant('empty-canonical-sweep');
    // When
    const offline = offlineGeometryResult(changed, 'geometry-empty-canonical-sweep');
    // Then
    expect(offline.status).toBe(1); expect(offline.stderr).toContain('collision');
  });

  it('accepts a real mesh referenced independently by each follower own subtree', async () => {
    // Given
    vi.stubGlobal('self', globalThis); vi.stubGlobal('createImageBitmap', async () => ({ width: 32, height: 32, close: () => undefined }));
    const changed = geometryMutant('shared-mesh');
    // When
    const loaded = await loadAsset(changed.asset, changed.lod, { origin: 'http://127.0.0.1:4176', read: async () => changed.bytes });
    try {
      // Then
      const left = loaded.nodes.get('roughing_roll_follower_2_barrel'), right = loaded.nodes.get('roughing_roll_follower_3_barrel');
      expect(left).toBeInstanceOf(Mesh); expect(right).toBeInstanceOf(Mesh);
      if (!(left instanceof Mesh) || !(right instanceof Mesh)) throw new RangeError('Actual reused barrel mesh missing');
      expect(left.geometry).toBe(right.geometry);
      expect(offlineGeometryResult(changed, 'geometry-shared-mesh').status).toBe(0);
    } finally { loaded.dispose(); }
  });

  it('disposes every decoded resource when a follower has only degenerate triangles', async () => {
    // Given
    vi.stubGlobal('self', globalThis); vi.stubGlobal('createImageBitmap', async () => ({ width: 32, height: 32, close: () => undefined }));
    const changed = geometryMutant('degenerate'), disposed: ReturnType<typeof vi.fn>[] = [];
    const original = GLTFLoader.prototype.parseAsync;
    vi.spyOn(GLTFLoader.prototype, 'parseAsync').mockImplementation(async function (this: GLTFLoader, data, path) {
      const result = await original.call(this, data, path), resources = collectResources(result.scene);
      for (const resource of [...resources.geometries, ...resources.materials, ...resources.textures]) { const listener = vi.fn(); resource.addEventListener('dispose', listener); disposed.push(listener); }
      return result;
    });
    // When / Then
    const rejection: unknown = await loadAsset(changed.asset, changed.lod, { origin: 'http://127.0.0.1:4176', read: async () => changed.bytes }).then(loaded => { loaded.dispose(); return null; }, (error: unknown) => error);
    expect(rejection).toMatchObject({ code: 'binding' });
    expect(disposed.length).toBeGreaterThan(0);
    for (const listener of disposed) expect(listener).toHaveBeenCalledTimes(1);
  });
});

describe('real exported independent miniature rolls', () => {
  it.each(['roughing_roll_follower_1', 'roughing_roll_follower_2', 'roughing_roll_follower_3'])('rejects %s as a server canonical channel on the unchanged wire', functionId => {
    // Given
    const input = miniatureRequest(actual(), .5), channel = required(input.envelope.channels[0]);
    const envelope = parseMotionEnvelopeValue({ ...input.envelope, channels: [...input.envelope.channels, { ...channel, function_id: functionId, node_id: functionId }] });
    const context = parseMotionContext({ ...input.context, authorizations: [envelope] });
    // When / Then
    expect(() => evaluateMotion(envelope, context, recipes)).toThrow(expect.objectContaining({ code: 'unknown_function' }));
  });

  it('admits every actual LOD with four authored rotation tracks in one canonical clip', async () => {
    // Given
    const asset = required(actual().assets[0]);
    // When
    const reports = await Promise.all(asset.lods.map(lod => inspectGlb(new Uint8Array(readFileSync(`${fixtureRoot}/${lod.artifact.path}`)).buffer, asset, lod)));
    // Then
    expect(reports.map(report => report.nodeCount)).toEqual([41, 41, 41]);
  });

  it.each([0, 2 * Math.PI, 4 * Math.PI])('samples canonical scalar %s without modulo and derives every ratio from nonzero rest', async value => {
    // Given
    const { manifest, store, entity } = registry(), asset = entity.asset;
    try {
      await entity.show(0);
      const input = miniatureRequest(manifest, 0.2 + 0.6 * value / (4 * Math.PI));
      // When
      entity.applyPose(input.pose);
      // Then
      expect(required(input.pose.channels[0]).value).toBeCloseTo(value, 10);
      for (const part of asset.moving_parts) {
        const node = required(entity.nodes.get(part.node_id)), rest = required(asset.nodes.find(row => row.id === part.node_id));
        const driver = required(asset.moving_parts[0]);
        const derived = part.binding.type === 'mechanical_follower' ? part.range.rest + part.binding.ratio * (value - driver.range.rest) : value;
        const expected = new Quaternion().setFromAxisAngle(new Vector3(...part.axis), derived - part.range.rest).multiply(new Quaternion(...rest.transform.rotation_xyzw));
        expect(Math.abs(node.quaternion.dot(expected))).toBeCloseTo(1, 10);
        expect(node.position.toArray()).toEqual(rest.transform.position_m);
        const frame = required(asset.nodes.find(row => row.id === rest.parent_id));
        const expectedWorld = new Matrix4().compose(new Vector3(...frame.transform.position_m), new Quaternion(...frame.transform.rotation_xyzw), new Vector3(1, 1, 1))
          .multiply(new Matrix4().compose(new Vector3(...rest.transform.position_m), expected, new Vector3(1, 1, 1)));
        expect(node.matrixWorld.elements).toEqual(expectedWorld.elements.map(component => expect.closeTo(component, 5)));
      }
    } finally { store.dispose(); }
  });

  it('resamples held canonical values through pause, blocked, all LODs and scope reentry', async () => {
    // Given
    const { manifest, store, entity } = registry();
    try {
      const held = miniatureRequest(manifest, .43, 'paused');
      entity.applyPose(held.pose); await entity.show(0);
      const before = entity.asset.moving_parts.map(part => [...required(entity.nodes.get(part.node_id)).matrixWorld.elements]);
      // When
      entity.applyPose(miniatureRequest(manifest, .43, 'blocked').pose);
      const samples: number[][][] = [];
      for (const level of [1, 2, 0]) {
        await entity.show(level);
        samples.push(entity.asset.moving_parts.map(part => [...required(entity.nodes.get(part.node_id)).matrixWorld.elements]));
      }
      entity.hide(); await entity.show(2);
      samples.push(entity.asset.moving_parts.map(part => [...required(entity.nodes.get(part.node_id)).matrixWorld.elements]));
      // Then
      for (const sample of samples) for (const [index, matrix] of sample.entries()) expect(matrix).toEqual(required(before[index]).map(value => expect.closeTo(value, 5)));
    } finally { store.dispose(); }
  });

  it('rejects a missing last follower node before changing any canonical or earlier follower matrix', async () => {
    // Given
    const { manifest, store, entity } = registry();
    try {
      await entity.show(0); entity.applyPose(miniatureRequest(manifest, .35).pose);
      const nodes = entity.nodes;
      if (!(nodes instanceof Map)) throw new RangeError('Actual decoded node map missing');
      const last = required(entity.asset.moving_parts.at(-1)); nodes.delete(last.node_id);
      const before = [...nodes].map(([id, node]) => ({ id, matrix: node.matrix.clone() }));
      // When / Then
      expect(() => entity.applyPose(miniatureRequest(manifest, .65).pose)).toThrow(expect.objectContaining({ code: 'binding' }));
      for (const row of before) expect(required(nodes.get(row.id)).matrix.equals(row.matrix)).toBe(true);
    } finally { store.dispose(); }
  });
});

describe('actual follower GLB rejection', () => {
  it.each(['undeclared-target', 'other-clip', 'animated-scale', 'nonuniform-scale', 'negative-scale', 'matrix', 'wrong-follower-sample', 'wrong-multiplication-order', 'wrong-rest-subtraction', 'self-interpolated-follower', 'mismatched-timeline', 'sparse-4pi-identity-keys', 'nonunit-output', 'nonfinite-time'] as const)('rejects %s with checksums recomputed from the actual mutant', async mutation => {
    // Given
    const changed = mutateMiniature((raw, binary) => {
      const nodes = rows(raw, 'nodes'), clip = required(rows(raw, 'animations')[0]);
      const channels = rows(clip, 'channels'), channel = required(channels[1]), target = z.record(z.string(), z.unknown()).parse(channel.target); channel.target = target;
      const node = required(nodes.find(row => row.name === 'roughing_roll_follower_1'));
      switch (mutation) {
        case 'undeclared-target': target.node = nodes.findIndex(row => row.name === 'support_bed'); break;
        case 'other-clip': clip.name = 'unapproved.clip'; break;
        case 'animated-scale': target.path = 'scale'; break;
        case 'nonuniform-scale': node.scale = [1, 2, 1]; break;
        case 'negative-scale': node.scale = [-1, 1, 1]; break;
        case 'matrix': node.matrix = new Matrix4().toArray(); break;
        case 'nonfinite-time': {
          const sampler = required(rows(clip, 'samplers')[z.number().parse(channel.sampler)]), accessor = required(rows(raw, 'accessors')[z.number().parse(sampler.input)]);
          const view = required(rows(raw, 'bufferViews')[z.number().parse(accessor.bufferView)]);
          binary.writeFloatLE(NaN, z.number().parse(view.byteOffset ?? 0) + z.number().parse(accessor.byteOffset ?? 0) + 4);
          break;
        }
        case 'mismatched-timeline': {
          const sampler = required(rows(clip, 'samplers')[z.number().parse(channel.sampler)]), accessors = rows(raw, 'accessors'), accessor = required(accessors[z.number().parse(sampler.input)]);
          sampler.input = accessors.length; accessors.push({ ...accessor, count: 48, byteOffset: 4 });
          break;
        }
        case 'sparse-4pi-identity-keys': {
          const parts = required(actual().assets[0]).moving_parts, samplers = rows(clip, 'samplers'), accessors = rows(raw, 'accessors'), views = rows(raw, 'bufferViews');
          for (const [partIndex, targetChannel] of channels.entries()) {
            const part = required(parts[partIndex]), rest = required(required(actual().assets[0]).nodes.find(row => row.id === part.node_id)), sampler = required(samplers[z.number().parse(targetChannel.sampler)]);
            const input = required(accessors[z.number().parse(sampler.input)]), output = required(accessors[z.number().parse(sampler.output)]);
            input.count = 3; output.count = 3;
            const inputOffset = z.number().parse(required(views[z.number().parse(input.bufferView)]).byteOffset ?? 0) + z.number().parse(input.byteOffset ?? 0);
            const outputOffset = z.number().parse(required(views[z.number().parse(output.bufferView)]).byteOffset ?? 0) + z.number().parse(output.byteOffset ?? 0);
            for (const [key, scalar] of [0, 2 * Math.PI, 4 * Math.PI].entries()) {
              binary.writeFloatLE(key, inputOffset + key * 4);
              const displacement = (part.binding.type === 'mechanical_follower' ? part.binding.ratio : 1) * (scalar - required(parts[0]).range.rest);
              const rotation = new Quaternion().setFromAxisAngle(new Vector3(...part.axis), displacement).multiply(new Quaternion(...rest.transform.rotation_xyzw));
              rotation.toArray().forEach((component, index) => binary.writeFloatLE(component, outputOffset + key * 16 + index * 4));
            }
          }
          break;
        }
        case 'wrong-follower-sample':
        case 'nonunit-output':
        case 'wrong-multiplication-order':
        case 'wrong-rest-subtraction':
        case 'self-interpolated-follower': {
          const sampler = required(rows(clip, 'samplers')[z.number().parse(channel.sampler)]);
          const accessor = required(rows(raw, 'accessors')[z.number().parse(sampler.output)]);
          const view = required(rows(raw, 'bufferViews')[z.number().parse(accessor.bufferView)]);
          const offset = z.number().parse(view.byteOffset ?? 0) + z.number().parse(accessor.byteOffset ?? 0);
          if (mutation === 'wrong-follower-sample' || mutation === 'nonunit-output') binary.writeFloatLE(mutation === 'nonunit-output' ? 2 : .6, offset + 16 * 8);
          else {
            const asset = required(actual().assets[0]), part = required(asset.moving_parts[1]), driver = required(asset.moving_parts[0]), rest = required(asset.nodes.find(row => row.id === part.node_id));
            if (part.binding.type !== 'mechanical_follower') throw new RangeError('Follower input missing');
            const scalar = 4 * Math.PI * 8 / 48;
            const displacement = mutation === 'wrong-rest-subtraction' ? part.binding.ratio * scalar
              : mutation === 'self-interpolated-follower' ? part.range.min + (part.range.max - part.range.min) * 8 / 48 - part.range.rest
                : part.binding.ratio * (scalar - driver.range.rest);
            const delta = new Quaternion().setFromAxisAngle(new Vector3(...part.axis), displacement), restRotation = new Quaternion(...rest.transform.rotation_xyzw);
            const rotation = mutation === 'wrong-multiplication-order' ? restRotation.multiply(delta) : delta.multiply(restRotation);
            rotation.toArray().forEach((component, index) => binary.writeFloatLE(component, offset + 16 * 8 + index * 4));
          }
          break;
        }
      }
    });
    // When / Then
    await expect(inspectGlb(changed.bytes, changed.asset, changed.lod)).rejects.toMatchObject({ code: 'binding' });
    const temporary = mkdtempSync(join(tmpdir(), 't61-glb-mutant-'));
    try {
      const bytesPath = join(temporary, 'actual.glb'), descriptor = join(temporary, 'asset.json');
      writeFileSync(bytesPath, new Uint8Array(changed.bytes)); writeFileSync(descriptor, JSON.stringify({ asset: changed.asset, bytesPath }));
      const offline = spawnSync(process.execPath, ['tests/fixtures/mechanical-followers/check-mutant.mjs', descriptor], { encoding: 'utf8' });
      expect(offline.status, offline.stdout + offline.stderr).toBe(1);
      const evidence = process.env.MECHANICAL_FOLLOWER_EVIDENCE_ROOT;
      if (evidence) { mkdirSync(evidence, { recursive: true }); writeFileSync(join(evidence, `${mutation}.glb`), new Uint8Array(changed.bytes)); writeFileSync(join(evidence, `${mutation}.json`), JSON.stringify({ asset: changed.asset, lod: changed.lod, offline: { code: offline.status, error: offline.stderr } }, null, 2)); }
    } finally { rmSync(temporary, { recursive: true, force: true }); }
  });

  it('accepts physically equivalent negative quaternion samples without losing the scalar branch', async () => {
    // Given
    const changed = mutateMiniature((raw, binary) => {
      const clip = required(rows(raw, 'animations')[0]), channel = required(rows(clip, 'channels')[1]), sampler = required(rows(clip, 'samplers')[z.number().parse(channel.sampler)]);
      const accessor = required(rows(raw, 'accessors')[z.number().parse(sampler.output)]), view = required(rows(raw, 'bufferViews')[z.number().parse(accessor.bufferView)]);
      const offset = z.number().parse(view.byteOffset ?? 0) + z.number().parse(accessor.byteOffset ?? 0) + 16 * 8;
      for (let component = 0; component < 4; component += 1) binary.writeFloatLE(-binary.readFloatLE(offset + component * 4), offset + component * 4);
    });
    // When
    const admitted = await inspectGlb(changed.bytes, changed.asset, changed.lod);
    // Then
    expect(admitted.nodeCount).toBe(41);
  });
});

describe('bounded mechanical follower metadata', () => {
  it('admits three independent rotation pivots while exposing exactly the canonical server function', () => {
    // Given
    const raw = followerMetadata();
    // When
    const manifest = parseAssetManifestValue(raw), asset = required(manifest.assets[0]);
    const binding = required(bindingsFromAssetManifest(manifest, [{ owner_id: 'CS-HR-03', asset_id: asset.id, socket_families: Object.fromEntries(asset.sockets.map(socket => [socket.id, 'SLAB'])) }])[0]);
    // Then
    expect(asset.moving_parts.map(part => part.node_id)).toHaveLength(4);
    expect(binding.functions.map(fn => fn.function_id)).toEqual(['roughing_roll']);
  });

  it.each([0, Infinity, NaN])('rejects invalid ratio %s at the strict boundary', ratio => {
    // Given
    const raw = followerMetadata(); Object.assign(required(raw.assets[0]?.moving_parts[1]).binding, { ratio });
    // When / Then
    expect(() => parseAssetManifestValue(raw)).toThrow(expect.objectContaining({ code: 'schema' }));
  });

  it.each(['self', 'chain', 'missing', 'translation', 'other-function', 'socket', 'moving-parent', 'range', 'duplicate-node'] as const)('rejects %s instead of weakening canonical admission', mutation => {
    // Given
    const raw = followerMetadata(), asset = required(raw.assets[0]), driver = required(asset.moving_parts[0]), follower = required(asset.moving_parts[1]);
    switch (mutation) {
      case 'self': Object.assign(follower.binding, { driver_part_id: follower.id }); break;
      case 'chain': Object.assign(follower.binding, { driver_part_id: required(asset.moving_parts[2]).id }); break;
      case 'missing': Object.assign(follower.binding, { driver_part_id: 'absent' }); break;
      case 'translation': driver.motion = 'translation'; driver.range.unit = 'm'; break;
      case 'other-function': follower.function = 'work_roll'; break;
      case 'socket': required(asset.sockets[0]).node_id = follower.node_id; break;
      case 'moving-parent': required(asset.nodes.find(node => node.id === 'roll_frame')).parent_id = driver.node_id; break;
      case 'range': follower.range.min = -0.1; break;
      case 'duplicate-node': follower.node_id = driver.node_id; break;
    }
    // When / Then
    expect(() => parseAssetManifestValue(raw)).toThrow();
  });

  it('permits different explicitly validated follower counts across variants', () => {
    // Given
    const first = followerMetadata(), second = followerMetadata('variant:roughing:CS-PLATE-03', 1);
    // When
    const manifest = parseAssetManifestValue({ ...first, assets: [...first.assets, ...second.assets] });
    // Then
    expect(manifest.assets.map(asset => asset.moving_parts.length)).toEqual([4, 2]);
  });
});
