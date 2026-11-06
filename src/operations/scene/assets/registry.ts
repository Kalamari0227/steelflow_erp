import { z } from 'zod';
import { Color, Group, Matrix4, Mesh, MeshStandardMaterial, Quaternion, Vector3 } from 'three';
import type { ColorRepresentation, Material, Object3D } from 'three';
import { clone } from 'three/addons/utils/SkeletonUtils.js';
import { parseProductionAssetManifest } from './manifest';
import type { Asset } from './manifest';
import { AssetLoadError, requireAsset } from './errors';
import { loadAsset } from './loader';
import type { AssetLod, LoadOptions, LoadedAsset } from './loader';
import { bindingsFromAssetManifest } from '../motion/contracts';
import type { AssetBinding, MotionPose } from '../motion/contracts';

const identityShape = z.strictObject({ run_id: z.string().min(1), entity_type: z.string().min(1), entity_id: z.string().min(1), bundle_hash: z.string().regex(/^[a-f0-9]{64}$/) }).readonly();
const keyShape = z.string().brand('AssetBusinessKey');
export type AssetIdentity = z.infer<typeof identityShape>;
export type AssetBusinessKey = z.infer<typeof keyShape>;
export const businessKey = (identity: AssetIdentity): AssetBusinessKey => keyShape.parse(JSON.stringify([identity.run_id, identity.entity_type, identity.entity_id, identity.bundle_hash]));
export type AssetLease = {
  readonly scene: Object3D; readonly nodes: ReadonlyMap<string, Object3D>; readonly asset: Asset; readonly lod: AssetLod;
  readonly localMaterials: Set<Material>; readonly release: () => void;
};

// Cache entries are deliberately mutable: each token owns one pending or active lease.
class SharedAsset {
  readonly controller = new AbortController();
  readonly consumers = new Set<symbol>();
  readonly promise: Promise<LoadedAsset>;
  loaded: LoadedAsset | undefined;
  constructor(asset: Asset, lod: AssetLod, options: LoadOptions, readonly remove: () => void) {
    this.promise = loadAsset(asset, lod, { ...options, signal: this.controller.signal }).then(loaded => {
      this.loaded = loaded;
      if (this.consumers.size === 0) loaded.dispose();
      return loaded;
    }, (error: unknown) => { this.remove(); throw error; });
  }
  release(token: symbol): void {
    if (!this.consumers.delete(token) || this.consumers.size > 0) return;
    this.remove(); this.controller.abort(); this.loaded?.dispose();
  }
}

export class AssetRegistry {
  readonly manifest: ReturnType<typeof parseProductionAssetManifest>;
  private scope: { readonly run_id: string; readonly bundle_hash: string } | null = null;
  private readonly cache = new Map<string, SharedAsset>();
  private readonly entities = new Map<AssetBusinessKey, AssetEntity>();
  private readonly cancellations = new Set<() => void>();
  constructor(rawManifest: string, private readonly options: LoadOptions) { this.manifest = parseProductionAssetManifest(rawManifest); }

  beginRun(runId: string, bundleHash: string): void {
    identityShape.parse({ run_id: runId, bundle_hash: bundleHash, entity_type: 'run', entity_id: runId });
    if (this.scope?.run_id === runId && this.scope.bundle_hash === bundleHash) return;
    for (const entity of this.entities.values()) entity.hide();
    for (const cancel of [...this.cancellations]) cancel();
    this.entities.clear(); this.scope = { run_id: runId, bundle_hash: bundleHash };
  }
  private admitIdentity(identity: AssetIdentity): AssetIdentity {
    const admitted = identityShape.parse(identity);
    requireAsset(this.scope?.run_id === admitted.run_id && this.scope.bundle_hash === admitted.bundle_hash, 'stale', 'run or bundle');
    return admitted;
  }
  asset(id: string): Asset {
    const found = this.manifest.assets.find(asset => asset.id === id);
    requireAsset(found, 'binding', `asset:${id}`); return found;
  }
  private assetFor(identity: AssetIdentity, id: string): Asset {
    const asset = this.asset(id);
    if (identity.entity_type === 'equipment') requireAsset(asset.category === 'equipment' && asset.placement_ids.some(placement => placement === `equipment:${identity.entity_id}`), 'binding', 'equipment placement');
    return asset;
  }
  entity(identity: AssetIdentity, assetId: string): AssetEntity {
    const admitted = this.admitIdentity(identity), key = businessKey(admitted), existing = this.entities.get(key);
    if (existing) { requireAsset(existing.asset.id === assetId, 'identity', 'asset changed for same business key'); return existing; }
    const created = new AssetEntity(this, admitted, this.assetFor(admitted, assetId)); this.entities.set(key, created); return created;
  }
  async acquire(identity: AssetIdentity, assetId: string, level: number, signal?: AbortSignal): Promise<AssetLease> {
    this.admitIdentity(identity);
    requireAsset(!signal?.aborted, 'cancelled', assetId);
    const asset = this.assetFor(identity, assetId), lod = asset.lods.find(l => l.level === level);
    requireAsset(lod?.artifact.status === 'built', 'binding', `LOD:${level}`);
    const key = JSON.stringify([asset.id, lod.artifact.path, lod.artifact.sha256]);
    let entry = this.cache.get(key);
    if (!entry) {
      const created = new SharedAsset(asset, lod, this.options, () => { if (this.cache.get(key) === created) this.cache.delete(key); });
      this.cache.set(key, created); entry = created;
    }
    const ownedEntry = entry, token = Symbol(); ownedEntry.consumers.add(token);
    let released = false, instance: Object3D | undefined;
    const localMaterials = new Set<Material>();
    const release = (): void => {
      if (released) return;
      released = true; instance?.removeFromParent();
      for (const material of localMaterials) material.dispose(); localMaterials.clear();
      ownedEntry.release(token); this.cancellations.delete(cancel); signal?.removeEventListener('abort', cancel);
    };
    let rejectCancellation: (error: AssetLoadError) => void = () => undefined;
    const cancelled = new Promise<never>((_resolve, reject) => { rejectCancellation = reject; });
    const cancel = (): void => { release(); rejectCancellation(new AssetLoadError('cancelled', assetId)); };
    this.cancellations.add(cancel); signal?.addEventListener('abort', cancel, { once: true });
    try {
      const loaded = await Promise.race([ownedEntry.promise, cancelled]);
      requireAsset(!released, 'cancelled', assetId); this.admitIdentity(identity);
      instance = clone(loaded.scene);
      const nodes = new Map<string, Object3D>();
      instance.traverse(node => { const id: unknown = node.userData.semantic_id; if (typeof id === 'string') nodes.set(id, node); });
      return { scene: instance, nodes, asset, lod, localMaterials, release };
    } catch (error) { release(); throw error; }
  }
  resources() { return [...this.cache].map(([key, value]) => ({ key, refcount: value.consumers.size, loaded: value.loaded !== undefined })); }
  dispose(): void {
    for (const entity of this.entities.values()) entity.hide();
    for (const cancel of [...this.cancellations]) cancel();
    this.entities.clear(); this.scope = null;
  }
}

const roofVisibility = new WeakMap<Object3D, boolean>();
export function applyCutaway(nodes: ReadonlyMap<string, Object3D>, roofIds: readonly string[], enabled: boolean): void {
  for (const id of roofIds) {
    const roof = nodes.get(id); requireAsset(roof, 'binding', `roof:${id}`);
    if (enabled) { if (!roofVisibility.has(roof)) roofVisibility.set(roof, roof.visible); roof.visible = false; }
    else if (roofVisibility.has(roof)) { roof.visible = roofVisibility.get(roof) ?? true; roofVisibility.delete(roof); }
  }
}

export class AssetEntity {
  readonly key: AssetBusinessKey;
  readonly root = new Group();
  private lease: AssetLease | undefined;
  private controller: AbortController | undefined;
  private sequence = 0;
  private desiredPose: MotionPose | undefined;
  private desiredBinding: AssetBinding | undefined;
  private readonly materialColors = new Map<string, number>();
  private cut = false;
  constructor(private readonly registry: AssetRegistry, readonly identity: AssetIdentity, readonly asset: Asset) {
    this.key = businessKey(identity);
    this.root.name = `asset-entity:${identity.entity_type}:${identity.entity_id}`;
    this.root.userData = { assetIdentity: identity, businessKey: this.key, selected: false };
  }
  get nodes(): ReadonlyMap<string, Object3D> { return this.lease?.nodes ?? new Map(); }
  get level(): number | null { return this.lease?.lod.level ?? null; }
  get cutaway(): boolean { return this.cut; }
  async show(level: number): Promise<void> {
    const sequence = ++this.sequence;
    this.controller?.abort(); const controller = new AbortController(); this.controller = controller;
    const next = await this.registry.acquire(this.identity, this.asset.id, level, controller.signal);
    if (sequence !== this.sequence) { next.release(); throw new AssetLoadError('cancelled', this.key); }
    try {
      if (this.desiredPose && this.desiredBinding) this.poseLease(next, this.desiredPose, this.desiredBinding);
      for (const [id, color] of this.materialColors) this.colorLease(next, id, color);
      applyCutaway(next.nodes, this.asset.cutaway.roof_node_ids, this.cut);
      const previous = this.lease; this.lease = next; this.root.add(next.scene); previous?.release();
      if (this.controller === controller) this.controller = undefined;
      this.root.updateMatrixWorld(true);
    } catch (error) { next.release(); throw error; }
  }
  hide(): void { this.sequence += 1; this.controller?.abort(); this.controller = undefined; this.lease?.release(); this.lease = undefined; }
  setSelected(selected: boolean): void { this.root.userData.selected = selected; }
  setCutaway(enabled: boolean): void {
    this.cut = enabled;
    if (this.lease) applyCutaway(this.nodes, this.asset.cutaway.roof_node_ids, enabled);
    this.root.updateMatrixWorld(true);
  }
  applyPose(pose: MotionPose): void {
    requireAsset(pose.run_id === this.identity.run_id && (this.identity.entity_type !== 'equipment' || pose.owner_id === this.identity.entity_id), 'identity', 'pose owner/run');
    const families: Record<string, string> = {};
    for (const socket of this.asset.sockets) { const family = socket.forms[0]; requireAsset(family, 'binding', socket.id); families[socket.id] = family; }
    const binding = bindingsFromAssetManifest(this.registry.manifest, [{ owner_id: pose.owner_id, asset_id: this.asset.id, socket_families: families }])[0];
    requireAsset(binding, 'binding', 'motion descriptor');
    if (this.lease) this.poseLease(this.lease, pose, binding);
    this.desiredPose = pose; this.desiredBinding = binding;
  }
  private poseLease(lease: AssetLease, pose: MotionPose, binding: AssetBinding): void {
    requireAsset(pose.channels.length === binding.functions.length && binding.functions.every(fn => pose.channels.filter(c => c.function_id === fn.function_id).length === 1), 'binding', 'pose functions');
    const states: { readonly node: Object3D; readonly value: number }[] = [];
    const transforms: { readonly node: Object3D; readonly position: Vector3; readonly rotation: Quaternion }[] = [];
    const prepare = (part: Asset['moving_parts'][number], value: number): void => {
      const node = lease.nodes.get(part.node_id), rest = this.asset.nodes.find(row => row.id === part.node_id);
      requireAsset(node && rest && Number.isFinite(value) && value >= part.range.min - 1e-6 && value <= part.range.max + 1e-6, 'binding', `pose part:${part.id}`);
      const position = new Vector3(...rest.transform.position_m), rotation = new Quaternion(...rest.transform.rotation_xyzw);
      const displacement = value - part.range.rest, axis = new Vector3(...part.axis);
      switch (part.motion) {
        case 'translation': position.addScaledVector(axis, displacement); break;
        case 'rotation': {
          const delta = new Quaternion().setFromAxisAngle(axis, displacement), pivot = new Vector3(...part.pivot_m);
          position.sub(pivot).applyQuaternion(delta).add(pivot); rotation.premultiply(delta);
          break;
        }
      }
      transforms.push({ node, position, rotation });
    };
    // Prepare every canonical and follower transform before mutating any node, including states.
    for (const channel of pose.channels) {
      const fn = binding.functions.find(f => f.function_id === channel.function_id);
      requireAsset(fn && fn.node_id === channel.node_id && fn.kind === channel.kind && Number.isFinite(channel.value) && channel.value >= fn.min_value - 1e-6 && channel.value <= fn.max_value + 1e-6, 'binding', `pose:${channel.function_id}`);
      requireAsset(new Vector3(...fn.axis).distanceTo(new Vector3(...channel.axis)) < 1e-6 && new Vector3(...fn.pivot_m).distanceTo(new Vector3(...channel.pivot_m)) < 1e-6, 'binding', `pose frame:${channel.function_id}`);
      requireAsset(lease.nodes.has(channel.node_id), 'binding', `pose node:${channel.node_id}`);
      const node = lease.nodes.get(channel.node_id); requireAsset(node, 'binding', channel.node_id);
      switch (channel.kind) {
        case 'state': states.push({ node, value: channel.value }); break;
        case 'rotation':
        case 'translation': {
          const part = this.asset.moving_parts.find(p => p.binding.type !== 'mechanical_follower' && p.function === channel.function_id && p.node_id === channel.node_id);
          requireAsset(part && part.motion === channel.kind, 'binding', channel.function_id);
          prepare(part, channel.value);
          break;
        }
      }
    }
    for (const part of this.asset.moving_parts) {
      if (part.binding.type !== 'mechanical_follower') continue;
      const follower = part.binding, driver = this.asset.moving_parts.find(row => row.id === follower.driver_part_id);
      requireAsset(driver && driver.binding.type === 'clip', 'binding', `follower driver:${part.id}`);
      const channel = pose.channels.find(row => row.function_id === driver.function && row.node_id === driver.node_id && row.kind === 'rotation');
      requireAsset(channel, 'binding', `follower channel:${part.id}`);
      prepare(part, part.range.rest + follower.ratio * (channel.value - driver.range.rest));
    }
    for (const state of states) state.node.userData.operationalState = state.value;
    for (const transform of transforms) { transform.node.position.copy(transform.position); transform.node.quaternion.copy(transform.rotation); }
    lease.scene.updateMatrixWorld(true);
  }
  setMaterialColor(id: string, color: ColorRepresentation): void {
    requireAsset(this.asset.materials.some(material => material.id === id), 'binding', `material:${id}`);
    const value = new Color(color).getHex(); this.materialColors.set(id, value);
    if (this.lease) this.colorLease(this.lease, id, value);
  }
  private colorLease(lease: AssetLease, id: string, color: ColorRepresentation): void {
    const copies = new Map<Material, Material>();
    lease.scene.traverse(node => {
      if (!(node instanceof Mesh)) return;
      const replace = (material: Material): Material => {
        if (material.userData.semantic_id !== id) return material;
        requireAsset(material instanceof MeshStandardMaterial, 'unsupported', `material:${id}`);
        if (lease.localMaterials.has(material)) { material.color.set(color); return material; }
        let copy = copies.get(material);
        if (!copy) { copy = material.clone(); copies.set(material, copy); lease.localMaterials.add(copy); }
        if (copy instanceof MeshStandardMaterial) copy.color.set(color);
        return copy;
      };
      node.material = Array.isArray(node.material) ? node.material.map(replace) : replace(node.material);
    });
  }
  sockets() {
    this.root.updateMatrixWorld(true);
    return this.asset.sockets.map(socket => {
      const node = this.nodes.get(socket.node_id); requireAsset(node, 'binding', socket.node_id);
      const matrix = node.matrixWorld.clone().multiply(new Matrix4().compose(new Vector3(...socket.transform.position_m), new Quaternion(...socket.transform.rotation_xyzw), new Vector3(1, 1, 1)));
      return { id: socket.id, matrix: [...matrix.elements], position: new Vector3().setFromMatrixPosition(matrix).toArray(), normal: new Vector3(...socket.normal).transformDirection(matrix).toArray() };
    });
  }
}
