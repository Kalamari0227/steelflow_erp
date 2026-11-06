import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { Mesh, MeshStandardMaterial, Quaternion } from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { AssetRegistry, applyCutaway } from './registry';
import { AssetInstance } from './AssetInstance';
import { actualManifest, deferred, identity, origin, rawManifest, readActual, shear } from './loaderTestUtils';
import { representativePose } from '../../../../tests/fixtures/factory-assets/poses';

beforeEach(() => {
  vi.stubGlobal('self', globalThis);
  vi.stubGlobal('createImageBitmap', async () => ({ width: 8, height: 8, close: vi.fn() }));
});
afterEach(() => { vi.unstubAllGlobals(); vi.restoreAllMocks(); });
function registry() {
  const value = new AssetRegistry(rawManifest, { origin, read: readActual });
  value.beginRun(identity.run_id, identity.bundle_hash);
  return value;
}
function mesh(scene: Mesh | import('three').Object3D) {
  let found: Mesh | undefined;
  scene.traverse(node => { if (!found && node instanceof Mesh) found = node; });
  if (!found) throw new RangeError('Actual mesh missing');
  return found;
}

describe('shared asset ownership', () => {
  it('maps hover and pick to the same business identity after a real LOD swap and clears hover on exit', async () => {
    // Given
    const store = registry(), entity = store.entity(identity, shear().id), hover = vi.fn(), pick = vi.fn();
    await entity.show(0);
    const pointer = { stopPropagation: vi.fn() }, element = AssetInstance({ entity, onPick: pick, onHover: hover });
    // When
    element.props.onPointerOver?.(pointer); await entity.show(2); element.props.onPointerOver?.(pointer);
    element.props.onClick(pointer); element.props.onPointerOut?.(pointer);
    // Then
    expect(hover.mock.calls).toEqual([[entity.identity], [entity.identity], [null]]); expect(pick).toHaveBeenCalledWith(entity.identity);
    expect(pointer.stopPropagation).toHaveBeenCalledTimes(4); store.dispose();
  });

  it('shared_refcount keeps another clone alive until the final owner releases', async () => {
    // Given
    const store = registry();
    const [left, right] = await Promise.all([store.acquire(identity, shear().id, 0), store.acquire({ ...identity, entity_type: 'qa_comparison', entity_id: 'comparison' }, shear().id, 0)]);
    const leftMesh = mesh(left.scene), rightMesh = mesh(right.scene);
    const disposed = vi.fn(); leftMesh.geometry.addEventListener('dispose', disposed);
    // When
    left.nodes.get('cutting_tool')?.position.setY(0.4); left.release(); left.release();
    // Then
    expect(left.scene).not.toBe(right.scene);
    expect(leftMesh.geometry).toBe(rightMesh.geometry);
    expect(leftMesh.material).toBe(rightMesh.material);
    expect(right.nodes.get('cutting_tool')?.position.y).toBeCloseTo(1.8, 5);
    expect(disposed).not.toHaveBeenCalled();
    expect(store.resources()[0]?.refcount).toBe(1);
    right.release(); expect(disposed).toHaveBeenCalledTimes(1); expect(store.resources()).toEqual([]);
    store.dispose();
  });

  it('does not cancel a shared pending load when just one consumer aborts', async () => {
    // Given
    const gate = deferred<ArrayBuffer>(), started = deferred<void>();
    const store = new AssetRegistry(rawManifest, { origin, read: async () => { started.resolve(); return gate.promise; } });
    store.beginRun(identity.run_id, identity.bundle_hash);
    const controller = new AbortController();
    const cancelled = store.acquire(identity, shear().id, 0, controller.signal);
    const kept = store.acquire({ ...identity, entity_type: 'qa_comparison', entity_id: 'kept' }, shear().id, 0);
    const rejection = expect(cancelled).rejects.toMatchObject({ code: 'cancelled' });
    await started.promise;
    // When
    controller.abort(); gate.resolve(await readActual(`${origin}/assets/steelworks/shear-lod0.glb`, new AbortController().signal));
    // Then
    await rejection;
    const lease = await kept; expect(lease.nodes.has('cutting_tool')).toBe(true);
    expect(store.resources()[0]?.refcount).toBe(1); lease.release(); store.dispose();
  });

  it('run_change_race disposes a real late decoded model and never attaches it', async () => {
    // Given
    const parsed = deferred<void>(), finish = deferred<void>();
    const original = GLTFLoader.prototype.parseAsync;
    let lateMesh: Mesh | undefined;
    const disposed = vi.fn();
    vi.spyOn(GLTFLoader.prototype, 'parseAsync').mockImplementation(async function (this: GLTFLoader, data, path) {
      const result = await original.call(this, data, path);
      lateMesh = mesh(result.scene); lateMesh.geometry.addEventListener('dispose', disposed);
      parsed.resolve(); await finish.promise; return result;
    });
    const store = registry(); const entity = store.entity(identity, shear().id);
    const request = entity.show(0); const rejected = expect(request).rejects.toMatchObject({ code: 'cancelled' });
    await parsed.promise;
    // When
    store.beginRun('next-run', 'b'.repeat(64)); finish.resolve();
    // Then
    await rejected;
    await vi.waitFor(() => expect(disposed).toHaveBeenCalledTimes(1));
    expect(entity.root.children).toHaveLength(0); expect(lateMesh).toBeDefined(); expect(store.resources()).toEqual([]); store.dispose();
  });

  it('identity survives LOD changes, no-roof cutaway and scope reentry', async () => {
    // Given
    const store = registry(), entity = store.entity(identity, shear().id), key = entity.key, root = entity.root;
    await entity.show(0);
    // When
    entity.setSelected(true); entity.setCutaway(true); await entity.show(2); entity.hide(); await entity.show(1);
    // Then
    expect(entity.key).toBe(key); expect(entity.root).toBe(root); expect(entity.root.userData.selected).toBe(true);
    expect(store.entity(identity, shear().id)).toBe(entity);
    expect(entity.nodes.get('service_pad')?.getWorldQuaternion(new Quaternion())).toBeDefined();
    expect(entity.cutaway).toBe(true); store.dispose();
  });

  it('applies the same T58 desired pose and actual socket frames on every real LOD', async () => {
    // Given
    const asset = shear(), fixed = representativePose(actualManifest, asset);
    const store = registry(); store.beginRun(fixed.pose.run_id, fixed.envelope.bundle_hash);
    const entity = store.entity({ ...identity, run_id: fixed.pose.run_id, bundle_hash: fixed.envelope.bundle_hash }, asset.id);
    entity.applyPose(fixed.pose);
    const before = JSON.stringify(fixed);
    // When
    const samples = [];
    for (const level of [0, 1, 2]) { await entity.show(level); samples.push({ y: entity.nodes.get('cutting_tool')?.position.y, sockets: entity.sockets() }); }
    // Then
    expect(samples.every(sample => Math.abs((sample.y ?? 0) - 1.56) < 1e-5)).toBe(true);
    for (const sample of samples) expect(sample.sockets.find(s => s.id === 'work')?.position).toEqual([expect.closeTo(0.3, 5), expect.closeTo(1.05, 5), 0]);
    expect(JSON.stringify(fixed)).toBe(before); store.dispose();
  });

  it('changes an instance material without mutating another clone or disposing its texture', async () => {
    // Given
    const store = registry(), left = store.entity(identity, shear().id), right = store.entity({ ...identity, entity_type: 'qa_comparison', entity_id: 'comparison' }, shear().id);
    await Promise.all([left.show(0), right.show(0)]);
    const rightMaterials = new Set<import('three').Material>();
    right.root.traverse(node => { if (node instanceof Mesh) for (const material of Array.isArray(node.material) ? node.material : [node.material]) rightMaterials.add(material); });
    const disposed = vi.fn(), textureDisposed = vi.fn();
    for (const material of rightMaterials) {
      material.addEventListener('dispose', disposed);
      if (material instanceof MeshStandardMaterial && material.map) material.map.addEventListener('dispose', textureDisposed);
    }
    // When
    left.setMaterialColor('paint', '#aa0000'); left.hide();
    // Then
    expect(disposed).not.toHaveBeenCalled(); expect(textureDisposed).not.toHaveBeenCalled(); expect(right.root.children).toHaveLength(1);
    store.dispose(); expect(disposed).toHaveBeenCalled(); expect(textureDisposed).toHaveBeenCalledTimes(1);
  });

  it('roof_contract restores synthetic roof visibility while retaining its socket and parent', () => {
    // Given
    const roof = new Mesh(), socket = new Mesh(), root = new Mesh(); root.add(roof, socket);
    const nodes = new Map([['roof', roof], ['socket', socket]]);
    // When
    applyCutaway(nodes, ['roof'], true);
    // Then
    expect(roof.visible).toBe(false); expect(socket.visible).toBe(true); expect(roof.parent).toBe(root);
    applyCutaway(nodes, ['roof'], false); expect(roof.visible).toBe(true);
    roof.visible = false; applyCutaway(nodes, ['roof'], true); applyCutaway(nodes, ['roof'], false); expect(roof.visible).toBe(false);
    expect(() => applyCutaway(nodes, ['missing'], true)).toThrow(expect.objectContaining({ code: 'binding' }));
  });

  it('roof_contract defers a synthetic cutaway request until the actual nodes arrive', async () => {
    // Given: synthetic roof declaration only; this does not certify an authored roof asset.
    const asset = shear(), beam = asset.nodes.find(node => node.id === 'head_beam');
    if (!beam) throw new RangeError('Actual beam missing');
    const synthetic = { ...actualManifest, assets: actualManifest.assets.map(row => row.id === asset.id ? { ...row, cutaway: { roof_node_ids: [beam.id], interior_node_ids: [], retained_socket_ids: row.sockets.map(socket => socket.id) } } : row) };
    const store = new AssetRegistry(JSON.stringify(synthetic), { origin, read: readActual }); store.beginRun(identity.run_id, identity.bundle_hash);
    const entity = store.entity(identity, asset.id);
    // When
    entity.setCutaway(true); await entity.show(0);
    // Then
    expect(entity.nodes.get('head_beam')?.visible).toBe(false); expect(entity.nodes.get('cutting_tool')?.visible).toBe(true);
    entity.hide(); await entity.show(1); expect(entity.nodes.get('head_beam')?.visible).toBe(false);
    entity.setCutaway(false); expect(entity.nodes.get('head_beam')?.visible).toBe(true); store.dispose();
  });

  it('missing_asset keeps the selected valid LOD when the next real file is missing', async () => {
    // Given
    const store = new AssetRegistry(rawManifest, { origin, read: (url, signal) => readActual(url.endsWith('shear-lod2.glb') ? `${url}.missing` : url, signal) });
    store.beginRun(identity.run_id, identity.bundle_hash);
    const entity = store.entity(identity, shear().id); await entity.show(0); entity.setSelected(true);
    const before = entity.root.children[0], disposed = vi.fn(); mesh(entity.root).geometry.addEventListener('dispose', disposed);
    // When / Then
    await expect(entity.show(2)).rejects.toMatchObject({ code: 'network' });
    expect(entity.level).toBe(0); expect(entity.root.children).toEqual([before]); expect(entity.root.userData.selected).toBe(true);
    expect(store.resources()).toHaveLength(1); expect(disposed).not.toHaveBeenCalled(); store.dispose();
  });

  it('rejects a corrupt real LOD atomically without disposing the active geometry', async () => {
    // Given
    const store = new AssetRegistry(rawManifest, { origin, read: async (url, signal) => {
      const bytes = await readActual(url, signal);
      if (url.endsWith('shear-lod2.glb')) new Uint8Array(bytes)[100] = 0;
      return bytes;
    } });
    store.beginRun(identity.run_id, identity.bundle_hash);
    const entity = store.entity(identity, shear().id); await entity.show(0);
    const before = entity.root.children[0], disposed = vi.fn(); mesh(entity.root).geometry.addEventListener('dispose', disposed);
    // When / Then
    await expect(entity.show(2)).rejects.toMatchObject({ code: 'hash' });
    expect(entity.level).toBe(0); expect(entity.root.children).toEqual([before]); expect(disposed).not.toHaveBeenCalled();
    expect(store.resources()).toHaveLength(1); store.dispose(); expect(disposed).toHaveBeenCalledTimes(1);
  });

  it('rejects a stale bundle without replacing a selected active instance', async () => {
    // Given
    const store = registry(), entity = store.entity(identity, shear().id); await entity.show(0); entity.setSelected(true);
    // When / Then
    await expect(store.acquire({ ...identity, bundle_hash: 'b'.repeat(64) }, shear().id, 0)).rejects.toMatchObject({ code: 'stale' });
    expect(entity.root.userData.selected).toBe(true); expect(entity.root.children).toHaveLength(1); expect(store.resources()[0]?.refcount).toBe(1); store.dispose();
  });

  it('rejects an equipment identity that is not an admitted placement of this model', async () => {
    // Given
    const store = registry();
    // When / Then
    await expect(store.acquire({ ...identity, entity_id: 'BF-A' }, shear().id, 0)).rejects.toMatchObject({ code: 'binding' });
    expect(store.resources()).toEqual([]); store.dispose();
  });

  it('retains an isolated material state across LOD and scope reentry', async () => {
    // Given
    const store = registry(), entity = store.entity(identity, shear().id); entity.setMaterialColor('paint', '#aa0000');
    const colors: number[] = [];
    // When
    for (const level of [0, 2, 1]) {
      await entity.show(level);
      entity.root.traverse(node => { if (node instanceof Mesh) for (const material of Array.isArray(node.material) ? node.material : [node.material]) if (material instanceof MeshStandardMaterial && material.userData.semantic_id === 'paint') colors.push(material.color.getHex()); });
      entity.hide();
    }
    // Then
    expect(colors.length).toBeGreaterThan(2); expect(colors.every(color => color === 0xaa0000)).toBe(true); store.dispose();
  });

  it('recovers the same selected identity after two separately interrupted real-byte loads', async () => {
    // Given
    const gates = [deferred<void>(), deferred<void>()]; let call = 0;
    const store = new AssetRegistry(rawManifest, { origin, read: async (url, signal) => { const gate = gates[call++]; if (gate) await gate.promise; return readActual(url, signal); } });
    store.beginRun(identity.run_id, identity.bundle_hash); const entity = store.entity(identity, shear().id); entity.setSelected(true);
    // When
    for (const gate of gates) { const request = entity.show(0); const rejected = expect(request).rejects.toMatchObject({ code: 'cancelled' }); entity.hide(); gate.resolve(); await rejected; }
    await entity.show(0);
    // Then
    expect(entity.root.userData.selected).toBe(true); expect(entity.nodes.has('cutting_tool')).toBe(true); expect(store.resources()[0]?.refcount).toBe(1); store.dispose(); expect(store.resources()).toEqual([]);
  });
});
