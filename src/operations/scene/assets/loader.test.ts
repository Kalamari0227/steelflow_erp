import { mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { createServer } from 'node:http';
import { z } from 'zod';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { parseProductionAssetManifest } from './manifest';
import { loadAsset, ownedAssetUrl, inspectGlb } from './loader';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { deferred, glbRows, mutateActual } from './loaderTestUtils';
import { AssetLoadError } from './errors';

const manifest = parseProductionAssetManifest(readFileSync('public/assets/steelworks/manifest.json', 'utf8'));
const first = manifest.assets[0];
if (!first) throw new RangeError('Actual shear asset missing');
const lod = first.lods[0];
if (!lod || lod.artifact.status !== 'built') throw new RangeError('Actual built LOD missing');
const bytes = new Uint8Array(readFileSync(lod.artifact.path)).buffer;
const origin = 'http://127.0.0.1:4176';

afterEach(() => { vi.unstubAllGlobals(); vi.restoreAllMocks(); });

describe('actual local GLB admission', () => {
  it('reads both real models and every LOD before any decoding', async () => {
    // Given
    const reports = [];
    // When
    for (const asset of manifest.assets) for (const level of asset.lods) {
      if (level.artifact.status !== 'built') throw new RangeError('Unbuilt representative');
      reports.push(await inspectGlb(new Uint8Array(readFileSync(level.artifact.path)).buffer, asset, level));
    }
    // Then
    expect(reports.map(report => report.nodeCount)).toEqual([31, 31, 31, 40, 40, 40]);
    expect(reports.every(report => report.externalResources === 0)).toBe(true);
  });

  it('missing_asset rejects different bytes instead of admitting a successful placeholder', async () => {
    // Given
    const corrupted = bytes.slice(0); new Uint8Array(corrupted)[100] = 0;
    // When / Then
    await expect(inspectGlb(corrupted, first, lod)).rejects.toMatchObject({ code: 'hash' });
  });

  it('accepts the equivalent negative unit quaternion in an actual rehashed GLB', async () => {
    // Given
    const mutant = mutateActual(raw => {
      const node = glbRows(raw, 'nodes').find(row => row.name === 'cutting_tool');
      if (!node) throw new RangeError('Actual cutting tool missing');
      node.rotation = [0, 0, 0, -1];
    });
    // When
    const admitted = await inspectGlb(mutant.bytes, mutant.asset, mutant.lod);
    // Then
    expect(admitted.nodeCount).toBe(31); expect(admitted.externalResources).toBe(0);
  });

  it('rejects protocols, traversal and nonowned paths before requesting them', () => {
    // Given
    const unsafe = ['https://example.com/a.glb', 'public/assets/steelworks/../a.glb', 'public/assets/steelworks/%2e%2e/a.glb', '//example.com/a.glb', 'assets/source/a.glb'];
    // When / Then
    for (const path of unsafe) expect(() => ownedAssetUrl(path, origin)).toThrow(expect.objectContaining({ code: 'path' }));
    expect(ownedAssetUrl(lod.artifact.path, origin)).toBe(`${origin}/assets/steelworks/shear-lod0.glb`);
  });

  it('loads actual geometry and embedded texture with the installed GLTFLoader', async () => {
    // Given: Node decodes real geometry; browser tests separately decode actual PNG pixels.
    vi.stubGlobal('self', globalThis);
    vi.stubGlobal('createImageBitmap', async () => ({ width: 8, height: 8, close: vi.fn() }));
    // When
    const loaded = await loadAsset(first, lod, { origin, read: async () => bytes });
    // Then
    expect(loaded.nodes.size).toBe(31);
    expect(loaded.nodes.get('cutting_tool')?.position.y).toBeCloseTo(1.8, 5);
    expect(loaded.animations.map(clip => clip.name)).toEqual(['shear.cutting_tool']);
    expect(loaded.resources.geometries.size).toBeGreaterThan(0);
    expect(loaded.resources.textures.size).toBe(1);
    loaded.dispose();
  });
});

const cases: readonly { readonly name: string; readonly code: string; readonly change: (raw: Record<string, unknown>) => void }[] = [
  { name: 'external_uri', code: 'path', change: raw => { const buffer = glbRows(raw, 'buffers')[0]; if (buffer) buffer.uri = 'https://example.com/collect'; } },
  { name: 'duplicate_semantic_id', code: 'binding', change: raw => { const node = glbRows(raw, 'nodes')[0]; if (node) node.extras = { semantic_id: 'root' }; } },
  { name: 'wrong_rest_frame', code: 'binding', change: raw => { const node = glbRows(raw, 'nodes').find(n => n.name === 'cutting_tool'); if (node) node.translation = [0, 2, 0]; } },
  { name: 'nonunit_rest_rotation', code: 'binding', change: raw => { const node = glbRows(raw, 'nodes').find(n => n.name === 'cutting_tool'); if (node) node.rotation = [1, 0, 0, 1]; } },
  { name: 'wrong_locator', code: 'binding', change: raw => { const node = glbRows(raw, 'nodes').find(n => n.name === 'cutting_tool'); if (node) node.name = 'renamed'; } },
  { name: 'changed_parent', code: 'binding', change: raw => { const nodes = glbRows(raw, 'nodes'), root = nodes.find(n => n.name === 'root'); if (root) root.children = z.array(z.number()).parse(root.children).filter(i => nodes[i]?.name !== 'cutting_tool'); } },
  { name: 'missing_clip', code: 'binding', change: raw => { raw.animations = []; } },
  { name: 'dangling_texture', code: 'binding', change: raw => { const texture = glbRows(raw, 'textures')[0]; if (texture) texture.source = 99; } },
  { name: 'remote_decoder_extension', code: 'unsupported', change: raw => { raw.extensionsRequired = ['KHR_draco_mesh_compression']; } },
];
describe('binding_error from actual mutated GLBs', () => {
  it.each(cases)('$name refuses a rehashed actual file before decoder or network use', async ({ name, code, change }) => {
    // Given
    const mutant = mutateActual(change), path = resolve(process.env.ASSET_LOADER_EVIDENCE_ROOT ?? '', 'mutants');
    mkdirSync(path, { recursive: true }); writeFileSync(resolve(path, `${name}.glb`), new Uint8Array(mutant.bytes));
    writeFileSync(resolve(path, `${name}.json`), JSON.stringify({ artifact: mutant.lod.artifact, semantic_geometry_sha256: mutant.lod.semantic_geometry_sha256, expected_error: code }));
    // When / Then
    await expect(inspectGlb(mutant.bytes, mutant.asset, mutant.lod)).rejects.toMatchObject({ code });
  });
});

describe('loader error normalization', () => {
  it.each([
    { name: 'DOMException timeout', cause: new DOMException('Asset body deadline exceeded', 'TimeoutError') },
    { name: 'Error', cause: new TypeError('Reader failed') },
  ])('normalizes $name with the original cause and artifact reference', async ({ cause }) => {
    const rejection: unknown = await loadAsset(first, lod, { origin, read: async () => Promise.reject(cause) }).catch((error: unknown) => error);
    expect(rejection).toBeInstanceOf(AssetLoadError);
    expect(rejection).toMatchObject({ code: 'network', reference: lod.artifact.path });
    expect(rejection instanceof AssetLoadError && rejection.cause).toBe(cause);
  });

  it('preserves an existing AssetLoadError instance', async () => {
    const error = new AssetLoadError('hash', 'original-artifact');
    await expect(loadAsset(first, lod, { origin, read: async () => Promise.reject(error) })).rejects.toBe(error);
  });

  it.each([
    { name: 'timeout-shaped plain object', value: { name: 'TimeoutError', message: 'not a DOMException' } },
    { name: 'string', value: 'TimeoutError' },
  ])('rethrows an unknown $name unchanged', async ({ value }) => {
    await expect(loadAsset(first, lod, { origin, read: async () => Promise.reject(value) })).rejects.toBe(value);
  });

  it.each([
    { name: 'DOMException timeout', cause: new DOMException('Asset body deadline exceeded', 'TimeoutError') },
    { name: 'existing AssetLoadError', cause: new AssetLoadError('hash', 'original-artifact') },
  ])('prioritizes caller cancellation over $name and preserves its cause', async ({ cause }) => {
    const controller = new AbortController();
    const rejection: unknown = await loadAsset(first, lod, { origin, signal: controller.signal, read: async () => {
      controller.abort();
      return Promise.reject(cause);
    } }).catch((error: unknown) => error);
    expect(rejection).toBeInstanceOf(AssetLoadError);
    expect(rejection).toMatchObject({ code: 'cancelled', reference: lod.artifact.path });
    expect(rejection instanceof AssetLoadError && rejection.cause).toBe(cause);
  });
});

it('bounds a real HTTP response whose headers arrive but whose body never completes', async () => {
  // Given: only this test's ephemeral listener; no existing service or protected port is touched.
  const server = createServer((_request, response) => { response.writeHead(200, { 'content-type': 'model/gltf-binary', 'content-length': String(bytes.byteLength) }); response.flushHeaders(); });
  await new Promise<void>(accept => server.listen(0, '127.0.0.1', accept));
  const address = server.address(); if (!address || typeof address === 'string') throw new RangeError('Owned listener missing');
  const started = performance.now(), evidence = resolve(process.env.ASSET_LOADER_EVIDENCE_ROOT ?? '', 'http-body-deadline.json');
  let rejection: unknown;
  writeFileSync(evidence, JSON.stringify({ owner: 'T13 loader HTTP deadline test', pid: process.pid, port: address.port, protected_ports_touched: [], deadline_ms: 15000, cleanup: 'closeAllConnections and close in finally' }));
  try {
    // When / Then
    const loading = loadAsset(first, lod, { origin: `http://127.0.0.1:${address.port}` });
    rejection = await loading.catch((error: unknown) => error);
    await expect(loading).rejects.toMatchObject({ code: 'network' });
    expect(rejection instanceof AssetLoadError && rejection.cause).toBeInstanceOf(DOMException);
    expect(rejection instanceof AssetLoadError && rejection.cause).toMatchObject({ name: 'TimeoutError' });
    expect(performance.now() - started).toBeGreaterThanOrEqual(14000);
    expect(performance.now() - started).toBeLessThan(19000);
  } finally {
    server.closeAllConnections(); await new Promise<void>((accept, reject) => server.close(error => error ? reject(error) : accept()));
    const cause = rejection instanceof AssetLoadError ? rejection.cause : undefined;
    writeFileSync(evidence, JSON.stringify({ owner: 'T13 loader HTTP deadline test', pid: process.pid, port: address.port, elapsed_ms: performance.now() - started, code: rejection instanceof AssetLoadError ? rejection.code : undefined, cause_name: cause instanceof DOMException ? cause.name : undefined, cause_is_domexception: cause instanceof DOMException, listener_closed: !server.listening, protected_ports_touched: [] }));
  }
}, 20000);

it.each(['success', 'status404', 'status404-stalled', 'redirect', 'caller-abort'] as const)('settles real HTTP %s without retries, redirect targets or pending bodies', async scenario => {
  // Given
  const controller = new AbortController(), requested = deferred<void>(), events: string[] = [];
  let requests = 0, responseClosed = false;
  const server = createServer((request, response) => {
    requests += 1; events.push(request.url ?? ''); response.once('close', () => { responseClosed = true; });
    switch (scenario) {
      case 'status404': response.writeHead(404); response.end('missing'); break;
      case 'status404-stalled': response.writeHead(404, { 'content-length': '1000' }); response.flushHeaders(); break;
      case 'redirect': response.writeHead(302, { location: '/redirect-target' }); response.end(); break;
      case 'caller-abort': response.writeHead(200, { 'content-length': String(bytes.byteLength) }); response.flushHeaders(); break;
      case 'success': response.writeHead(200, { 'content-type': 'model/gltf-binary' }); response.end(new Uint8Array(bytes)); break;
      default: { const exhaustive: never = scenario; throw new RangeError(exhaustive); }
    }
    requested.resolve();
  });
  await new Promise<void>(accept => server.listen(0, '127.0.0.1', accept));
  const address = server.address(); if (!address || typeof address === 'string') throw new RangeError('Owned HTTP listener missing');
  const started = performance.now(), decoder = vi.spyOn(GLTFLoader.prototype, 'parseAsync');
  const evidence = resolve(process.env.ASSET_LOADER_EVIDENCE_ROOT ?? '', `http-${scenario}.json`);
  writeFileSync(evidence, JSON.stringify({ owner: 'T13 loader HTTP regression', pid: process.pid, port: address.port, scenario, registered_before_request: true }));
  try {
    // When
    const loading = loadAsset(first, lod, { origin: `http://127.0.0.1:${address.port}`, signal: controller.signal });
    if (scenario === 'success') {
      vi.stubGlobal('self', globalThis); vi.stubGlobal('createImageBitmap', async () => ({ width: 8, height: 8, close: vi.fn() }));
      const loaded = await loading;
      // Then
      expect(loaded.nodes.size).toBe(31); expect(decoder).toHaveBeenCalledTimes(1); loaded.dispose();
    } else {
      const rejection = expect(loading).rejects.toMatchObject({ code: scenario === 'caller-abort' ? 'cancelled' : 'network' });
      await requested.promise; if (scenario === 'caller-abort') controller.abort();
      // Then
      await rejection; expect(decoder).not.toHaveBeenCalled();
      await vi.waitFor(() => expect(responseClosed).toBe(true), { timeout: 1000 });
    }
    expect(requests).toBe(1); expect(events).toEqual(['/assets/steelworks/shear-lod0.glb']);
    expect(performance.now() - started).toBeLessThan(1500);
  } finally {
    const closed = new Promise<void>((accept, reject) => server.close(error => error ? reject(error) : accept()));
    server.closeAllConnections(); await closed;
    writeFileSync(evidence, JSON.stringify({ owner: 'T13 loader HTTP regression', pid: process.pid, port: address.port, scenario, requests, events, responseClosed, elapsed_ms: performance.now() - started, listener_closed: !server.listening, protected_ports_touched: [] }));
  }
}, 2500);
