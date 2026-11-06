import {validateTransportMechanics,validateTransportDecodedGeometry,TransportMechanicsError} from './transportMechanics';
import { validateInternalFeedGeometry } from './internalFeedGeometry';
import { z } from 'zod';
import { BufferGeometry, LoadingManager, Material, Matrix4, Mesh, Quaternion, Texture, Triangle, Vector3 } from 'three';
import type { AnimationClip, Group, Object3D } from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import type { Asset } from './manifest';
import { AssetLoadError, requireAsset } from './errors';
import { parseContractJson, WorldContractError } from '../worldContractJson';
import { sha256 } from '../worldContractBundle';

export type AssetLod = Asset['lods'][number];
export type AssetResources = {
  readonly geometries: ReadonlySet<BufferGeometry>;
  readonly materials: ReadonlySet<Material>;
  readonly textures: ReadonlySet<Texture>;
};
export type LoadedAsset = {
  readonly asset: Asset; readonly lod: AssetLod; readonly scene: Group;
  readonly animations: readonly AnimationClip[]; readonly nodes: ReadonlyMap<string, Object3D>;
  readonly resources: AssetResources; readonly dispose: () => void;
};
export type AssetReader = (url: string, signal: AbortSignal) => Promise<ArrayBuffer>;
export type LoadOptions = { readonly origin: string; readonly signal?: AbortSignal; readonly read?: AssetReader };

const vector = z.tuple([z.number().finite(), z.number().finite(), z.number().finite()]);
const rotation = z.tuple([z.number().finite(), z.number().finite(), z.number().finite(), z.number().finite()]);
const index = z.number().int().nonnegative();
const nodeShape = z.object({ name: z.string(), extras: z.object({ semantic_id: z.string() }).passthrough(),
  children: z.array(index).optional(), translation: vector.optional(), rotation: rotation.optional(), scale: vector.optional(), mesh: index.optional(), matrix: z.unknown().optional() }).passthrough();
const glbShape = z.object({ asset: z.object({ version: z.literal('2.0') }).passthrough(), nodes: z.array(nodeShape).min(1),
  scene: index.optional(), scenes: z.array(z.object({ nodes: z.array(index) }).passthrough()),
  buffers: z.array(z.object({ byteLength: index }).passthrough()).length(1),
  bufferViews: z.array(z.object({ buffer: z.literal(0), byteOffset: index.optional(), byteLength: index, byteStride: index.optional() }).passthrough()),
  accessors: z.array(z.object({ bufferView: index, byteOffset: index.optional(), componentType: index, count: index, type: z.string(), normalized: z.boolean().optional(), sparse: z.unknown().optional() }).passthrough()),
  meshes: z.array(z.object({ primitives: z.array(z.object({ mode: index.optional() }).passthrough()) }).passthrough()),
  materials: z.array(z.object({ name: z.string(), extras: z.object({ semantic_id: z.string() }).passthrough() }).passthrough()),
  images: z.array(z.object({ bufferView: index, mimeType: z.literal('image/png') }).passthrough()).optional(),
  textures: z.array(z.object({ source: index }).passthrough()).optional(),
  animations: z.array(z.object({ name: z.string(), channels: z.array(z.object({ sampler: index, target: z.object({ node: index, path: z.enum(['translation', 'rotation', 'scale', 'weights']) }) })),
    samplers: z.array(z.object({ input: index, output: index, interpolation: z.string().optional() })) })).optional(),
  extensionsUsed: z.array(z.string()).optional(), extensionsRequired: z.array(z.string()).optional(), skins: z.array(z.unknown()).optional(),
}).passthrough();

function canonical(value: unknown): string {
  if (Array.isArray(value)) return `[${value.map((child: unknown) => canonical(child)).join(',')}]`;
  if (value !== null && typeof value === 'object') return `{${Object.keys(value).sort().map(key => `${JSON.stringify(key)}:${canonical(Reflect.get(value, key))}`).join(',')}}`;
  const result = JSON.stringify(value);
  requireAsset(result !== undefined, 'glb', 'invalid JSON value');
  return result;
}
function rejectUris(value: unknown): void {
  if (value === null || typeof value !== 'object') return;
  for (const [key, child] of Object.entries(value)) {
    requireAsset(key !== 'uri', 'path', 'GLB resources must be embedded');
    rejectUris(child);
  }
}
const close = (a: readonly number[], b: readonly number[], tolerance = 2e-5): boolean => a.length === b.length && a.every((v, i) => Math.abs(v - (b[i] ?? Infinity)) <= tolerance);
const rotationClose = (a: readonly number[], b: readonly number[]): boolean =>
  Math.abs(Math.hypot(...a) - 1) < 2e-5 && Math.abs(Math.hypot(...b) - 1) < 2e-5 &&
  Math.abs(Math.abs(a.reduce((sum, v, i) => sum + v * (b[i] ?? 0), 0)) - 1) < 2e-5;

export function ownedAssetUrl(path: string, origin: string): string {
  requireAsset(/^public\/assets\/steelworks\/[A-Za-z0-9_-]+(?:\/[A-Za-z0-9_-]+)*\.glb$/.test(path), 'path', path);
  let base: URL;
  try { base = new URL(origin); }
  catch (error) { if (error instanceof TypeError) throw new AssetLoadError('path', origin, { cause: error }); throw error; }
  requireAsset(['http:', 'https:'].includes(base.protocol) && base.origin === origin && !base.username && !base.password, 'path', origin);
  return `${origin}/${path.slice('public/'.length)}`;
}

/** Inspect bytes before GLTFLoader can resolve or request a resource. */
export async function inspectGlb(input: ArrayBuffer, asset: Asset, lod: AssetLod) {
  try { validateTransportMechanics(asset); }
  catch(error) { if(error instanceof TransportMechanicsError) throw new AssetLoadError('binding',error.reference,{cause:error}); throw error; }
  const bytes = input.slice(0);
  requireAsset(lod.artifact.status === 'built', 'hash', 'unbuilt asset');
  requireAsset(await sha256(new Uint8Array(bytes)) === lod.artifact.sha256, 'hash', lod.artifact.path);
  requireAsset(bytes.byteLength >= 28 && bytes.byteLength <= 64 * 1024 * 1024, 'glb', 'byte length');
  const view = new DataView(bytes);
  requireAsset(view.getUint32(0, true) === 0x46546c67 && view.getUint32(4, true) === 2 && view.getUint32(8, true) === bytes.byteLength, 'glb', 'header');
  const jsonLength = view.getUint32(12, true), binStart = 28 + jsonLength;
  requireAsset(jsonLength % 4 === 0 && binStart <= bytes.byteLength && view.getUint32(16, true) === 0x4e4f534a, 'glb', 'JSON chunk');
  requireAsset(view.getUint32(24 + jsonLength, true) === 0x004e4942 && view.getUint32(20 + jsonLength, true) === bytes.byteLength - binStart, 'glb', 'binary chunk');
  let raw: unknown;
  try { raw = parseContractJson(new TextDecoder('utf-8', { fatal: true }).decode(bytes.slice(20, 20 + jsonLength))); }
  catch (error) {
    if (error instanceof WorldContractError || error instanceof TypeError) throw new AssetLoadError('glb', 'JSON chunk', { cause: error });
    throw error;
  }
  rejectUris(raw);
  const result = glbShape.safeParse(raw);
  requireAsset(result.success, 'glb', 'structure');
  const gltf = result.data;
  requireAsset(!gltf.extensionsUsed?.length && !gltf.extensionsRequired?.length && !gltf.skins?.length, 'unsupported', 'rigid uncompressed GLB required');
  const bin = new Uint8Array(bytes, binStart);
  const semanticText = new TextEncoder().encode(`${canonical(raw)}\0`);
  const semantic = new Uint8Array(semanticText.length + bin.length); semantic.set(semanticText); semantic.set(bin, semanticText.length);
  requireAsset(await sha256(semantic) === lod.semantic_geometry_sha256, 'hash', 'semantic geometry');
  const buffer = gltf.buffers[0];
  requireAsset(buffer && buffer.byteLength <= bin.length && bin.length - buffer.byteLength <= 3, 'glb', 'embedded buffer bounds');
  for (const v of gltf.bufferViews) requireAsset((v.byteOffset ?? 0) + v.byteLength <= buffer.byteLength, 'glb', 'bufferView bounds');
  const parents = new Map<number, number>(), ids = new Map<string, number>();
  gltf.nodes.forEach((node, i) => {
    requireAsset(!ids.has(node.extras.semantic_id), 'binding', `duplicate semantic ID:${node.extras.semantic_id}`);
    ids.set(node.extras.semantic_id, i);
    requireAsset(node.matrix === undefined && close(node.scale ?? [1, 1, 1], [1, 1, 1]), 'binding', `scale:${node.name}`);
    for (const child of node.children ?? []) {
      requireAsset(gltf.nodes[child] && !parents.has(child), 'binding', `parent:${child}`); parents.set(child, i);
    }
  });
  requireAsset(ids.size === lod.nodes.length, 'binding', 'node count');
  for (const expected of lod.nodes) {
    const i = ids.get(expected.id), node = i === undefined ? undefined : gltf.nodes[i];
    requireAsset(i !== undefined && node, 'binding', `missing node:${expected.id}`);
    const parent = parents.get(i), parentId = parent === undefined ? null : gltf.nodes[parent]?.extras.semantic_id;
    requireAsset(parentId === expected.parent_id, 'binding', `parent:${expected.id}`);
    const names: string[] = [], seen = new Set<number>();
    let cursor: number | undefined = i;
    while (cursor !== undefined) {
      requireAsset(!seen.has(cursor), 'binding', 'hierarchy cycle'); seen.add(cursor);
      const ancestor = gltf.nodes[cursor]; requireAsset(ancestor, 'binding', 'ancestor'); names.unshift(ancestor.name); cursor = parents.get(cursor);
    }
    requireAsset(names.join('/') === expected.locator, 'binding', `locator:${expected.id}`);
    requireAsset(close(node.translation ?? [0, 0, 0], expected.transform.position_m) && rotationClose(node.rotation ?? [0, 0, 0, 1], expected.transform.rotation_xyzw), 'binding', `rest:${expected.id}`);
  }
  const roots = gltf.scenes[gltf.scene ?? 0]?.nodes;
  const rootIndex = roots?.[0];
  requireAsset(roots?.length === 1 && rootIndex !== undefined && rootIndex === ids.get(asset.root_node_id) && !parents.has(rootIndex), 'binding', 'scene root');
  requireAsset(gltf.materials.length === asset.materials.length && asset.materials.every(m => gltf.materials.filter(actual => actual.extras.semantic_id === m.id).length === 1), 'binding', 'materials');
  for (const part of asset.moving_parts) {
    switch (part.binding.type) {
      case 'procedural': throw new AssetLoadError('unsupported', `procedural:${part.binding.procedure_id}`);
      case 'mechanical_follower': {
        const binding = part.binding, driver = asset.moving_parts.find(row => row.id === binding.driver_part_id);
        requireAsset(driver && driver.binding.type === 'clip', 'binding', `follower driver:${part.id}`);
        const clipId = driver.binding.clip_id, clips = (gltf.animations ?? []).filter(clip => clip.name === clipId), clip = clips[0];
        requireAsset(clips.length === 1 && clip && clip.channels.filter(channel => channel.target.node === ids.get(part.node_id) && channel.target.path === 'rotation').length === 1, 'binding', `follower channel:${part.id}`);
        break;
      }
      case 'clip': {
        const clipId = part.binding.clip_id;
        const clips = (gltf.animations ?? []).filter(clip => clip.name === clipId);
        const clip = clips[0];
        requireAsset(clips.length === 1 && clip, 'binding', `clip:${part.id}`);
        requireAsset(clip.channels.filter(c => c.target.node === ids.get(part.node_id) && c.target.path === part.motion).length === 1, 'binding', `channel:${part.id}`);
        break;
      }
    }
  }
  for (const clip of gltf.animations ?? []) for (const channel of clip.channels) {
    const part = asset.moving_parts.find(p => ids.get(p.node_id) === channel.target.node);
    requireAsset(part, 'binding', 'undeclared animation channel');
    const driverId = part.binding.type === 'mechanical_follower' ? part.binding.driver_part_id : part.id;
    const driver = asset.moving_parts.find(row => row.id === driverId);
    requireAsset(driver && driver.binding.type === 'clip' && driver.binding.clip_id === clip.name && channel.target.path === part.motion && clip.samplers[channel.sampler], 'binding', 'undeclared animation channel');
  }
  for (const clip of gltf.animations ?? []) requireAsset(asset.moving_parts.some(part => part.binding.type === 'clip' && part.binding.clip_id === clip.name), 'binding', `undeclared clip:${clip.name}`);
  const samples = (accessorId: number, arity: 1 | 4): readonly (readonly number[])[] => {
    const accessor = gltf.accessors[accessorId];
    requireAsset(accessor && accessor.componentType === 5126 && accessor.type === (arity === 1 ? 'SCALAR' : 'VEC4') && !accessor.normalized && accessor.sparse === undefined && accessor.count >= 3 && accessor.count <= 2_000_000, 'binding', 'rotation accessor');
    const bufferView = gltf.bufferViews[accessor.bufferView]; requireAsset(bufferView, 'binding', 'rotation bufferView');
    const stride = bufferView.byteStride ?? arity * 4, offset = accessor.byteOffset ?? 0;
    requireAsset(stride >= arity * 4 && stride % 4 === 0 && offset % 4 === 0 && offset + (accessor.count - 1) * stride + arity * 4 <= bufferView.byteLength, 'binding', 'rotation accessor bounds');
    return Array.from({ length: accessor.count }, (_, row) => Array.from({ length: arity }, (_, component) => {
      const value = view.getFloat32(binStart + (bufferView.byteOffset ?? 0) + offset + row * stride + component * 4, true);
      requireAsset(Number.isFinite(value), 'binding', 'nonfinite rotation sample'); return value;
    }));
  };
  for (const driver of asset.moving_parts) {
    if (driver.binding.type !== 'clip' || driver.motion !== 'rotation') continue;
    const clipId = driver.binding.clip_id, clip = (gltf.animations ?? []).find(row => row.name === clipId);
    requireAsset(clip, 'binding', `rotation clip:${driver.id}`);
    const channel = clip.channels.find(row => row.target.node === ids.get(driver.node_id) && row.target.path === 'rotation');
    const sampler = channel && clip.samplers[channel.sampler]; requireAsset(sampler && (sampler.interpolation ?? 'LINEAR') === 'LINEAR', 'binding', `rotation sampler:${driver.id}`);
    const times = samples(sampler.input, 1).map(row => row[0]), duration = times.at(-1);
    requireAsset(duration !== undefined && duration > 0 && times[0] === 0 && times.every((time, index) => time !== undefined && (index === 0 || time > (times[index - 1] ?? Infinity))), 'binding', `rotation timeline:${driver.id}`);
    const scalars = times.map(time => { requireAsset(time !== undefined, 'binding', 'rotation time'); return driver.range.min + (driver.range.max - driver.range.min) * time / duration; });
    const followers = asset.moving_parts.filter(part => part.binding.type === 'mechanical_follower' && part.binding.driver_part_id === driver.id);
    for (const part of [driver, ...followers]) {
      const rest = asset.nodes.find(row => row.id === part.node_id); requireAsset(rest && close(part.pivot_m, rest.transform.position_m), 'binding', `rotation pivot:${part.id}`);
      const track = clip.channels.find(row => row.target.node === ids.get(part.node_id) && row.target.path === 'rotation'), trackSampler = track && clip.samplers[track.sampler];
      requireAsset(trackSampler && (trackSampler.interpolation ?? 'LINEAR') === 'LINEAR', 'binding', `rotation sampler:${part.id}`);
      const trackTimes = samples(trackSampler.input, 1).map(row => row[0]), values = samples(trackSampler.output, 4);
      requireAsset(trackTimes.length === times.length && trackTimes.every((time, index) => time === times[index]) && values.length === times.length, 'binding', `rotation timeline:${part.id}`);
      let previous: number | undefined;
      for (const [index, scalar] of scalars.entries()) {
        const value = part.binding.type === 'mechanical_follower' ? part.range.rest + part.binding.ratio * (scalar - driver.range.rest) : scalar;
        const displacement = value - part.range.rest, actual = values[index];
        requireAsset(previous === undefined || Math.abs(displacement - previous) < Math.PI, 'binding', `undersampled rotation:${part.id}`);
        const expected = new Quaternion().setFromAxisAngle(new Vector3(...part.axis), displacement).multiply(new Quaternion(...rest.transform.rotation_xyzw));
        requireAsset(actual && rotationClose(actual, expected.toArray()), 'binding', `rotation sample:${part.id}:${index}`);
        previous = displacement;
      }
    }
  }
  for (const part of asset.fixed_parts) {
    const own = ids.get(part.node_id), inherited = part.fixed_to_part_id === undefined ? undefined : ids.get(part.fixed_to_part_id);
    requireAsset(own !== undefined, 'binding', `fixed node:${part.id}`);
    if (part.fixed_to_part_id !== undefined) requireAsset(inherited !== undefined && parents.get(own) === inherited, 'binding', `direct fixed parent:${part.id}`);
    const stationaryBranch = (index: number): void => {
      requireAsset(!(gltf.animations ?? []).some(clip => clip.channels.some(channel => channel.target.node === index)), 'binding', `fixed descendant moves:${part.id}`);
      for (const child of gltf.nodes[index]?.children ?? []) stationaryBranch(child);
    };
    if (part.fixed_to_part_id !== undefined) stationaryBranch(own);
    let ancestor: number | undefined = own;
    while (ancestor !== undefined) {
      if (ancestor !== inherited) requireAsset(!(gltf.animations ?? []).some(clip => clip.channels.some(channel => channel.target.node === ancestor)), 'binding', `fixed part moves:${part.id}`);
      ancestor = parents.get(ancestor);
    }
  }
  for (const part of asset.moving_parts.filter(row => row.binding.type === 'mechanical_follower')) {
    const root = ids.get(part.node_id); requireAsset(root !== undefined, 'binding', `follower node:${part.id}`);
    const checkModes = (nodeIndex: number): void => {
      const node = gltf.nodes[nodeIndex]; requireAsset(node, 'binding', `follower geometry:${part.id}`);
      if (node.mesh !== undefined) {
        const mesh = gltf.meshes[node.mesh]; requireAsset(mesh && mesh.primitives.every(primitive => (primitive.mode ?? 4) === 4), 'binding', `follower triangles:${part.id}`);
      }
      for (const child of node.children ?? []) checkModes(child);
    };
    checkModes(root);
  }
  const imageHashes: string[] = [];
  for (const image of gltf.images ?? []) {
    const v = gltf.bufferViews[image.bufferView]; requireAsset(v, 'binding', 'image bufferView');
    imageHashes.push(await sha256(bin.slice(v.byteOffset ?? 0, (v.byteOffset ?? 0) + v.byteLength)));
  }
  requireAsset(imageHashes.length === asset.textures.length && asset.textures.every(t => t.artifact.status === 'built' && imageHashes.includes(t.artifact.sha256)), 'binding', 'embedded texture hash');
  for (const texture of gltf.textures ?? []) requireAsset((gltf.images ?? [])[texture.source], 'binding', 'texture source');
  return { nodeCount: ids.size, externalResources: 0, bytes };
}

export function collectResources(scene: Object3D): AssetResources {
  const geometries = new Set<BufferGeometry>(), materials = new Set<Material>(), textures = new Set<Texture>();
  scene.traverse(node => {
    if (!(node instanceof Mesh)) return;
    geometries.add(node.geometry);
    for (const material of Array.isArray(node.material) ? node.material : [node.material]) {
      materials.add(material);
      for (const value of Object.values(material)) if (value instanceof Texture) textures.add(value);
    }
  });
  return { geometries, materials, textures };
}
export function disposeResources(resources: AssetResources): void {
  for (const geometry of resources.geometries) geometry.dispose();
  for (const material of resources.materials) material.dispose();
  const images = new Set<unknown>();
  for (const texture of resources.textures) { images.add(texture.source.data); texture.dispose(); }
  for (const image of images) if (typeof ImageBitmap !== 'undefined' && image instanceof ImageBitmap) image.close();
}

function decodedNodes(scene: Object3D, asset: Asset): ReadonlyMap<string, Object3D> {
  const nodes = new Map<string, Object3D>();
  scene.traverse(node => {
    const id: unknown = node.userData.semantic_id;
    if (typeof id === 'string') { requireAsset(!nodes.has(id), 'binding', `duplicate decoded ID:${id}`); nodes.set(id, node); }
    if (node instanceof Mesh) {
      const positions = node.geometry.getAttribute('position');
      requireAsset(positions && positions.count > 0 && Array.from(positions.array).every(Number.isFinite), 'binding', 'actual mesh positions');
    }
  });
  requireAsset(nodes.size === asset.nodes.length && asset.nodes.every(node => nodes.has(node.id)), 'binding', 'decoded node set');
  scene.updateMatrixWorld(true);
  for (const part of [...asset.moving_parts.filter(row => row.binding.type === 'mechanical_follower'), ...asset.fixed_parts]) {
    const root = nodes.get(part.node_id); requireAsset(root, 'binding', `follower node:${part.id}`);
    let hasTriangle = false;
    root.traverse(node => {
      if (!(node instanceof Mesh)) return;
      const position = node.geometry.getAttribute('position'), indices = node.geometry.index;
      requireAsset(position && position.itemSize === 3, 'binding', `follower positions:${part.id}`);
      const count = indices?.count ?? position.count;
      requireAsset(count % 3 === 0, 'binding', `follower triangle count:${part.id}`);
      if (indices) requireAsset(indices.itemSize === 1 && Array.from(indices.array).every(value => typeof value === 'number' && Number.isInteger(value) && value >= 0 && value < position.count), 'binding', `follower indices:${part.id}`);
      for (let index = 0; index + 2 < count; index += 3) {
        const vertices = [index, index + 1, index + 2].map(offset => new Vector3().fromBufferAttribute(position, indices ? indices.getX(offset) : offset));
        const [a, b, c] = vertices; requireAsset(a && b && c, 'binding', `follower triangle:${part.id}`);
        const area = new Triangle(a, b, c).getArea();
        if (Number.isFinite(area) && area > 0) hasTriangle = true;
      }
    });
    requireAsset(hasTriangle, 'binding', `follower renderable geometry:${part.id}`);
  }
  for (const socket of asset.sockets) {
    const parent = nodes.get(socket.node_id); requireAsset(parent, 'binding', `socket:${socket.id}`);
    const socketMatrix = parent.matrixWorld.clone().multiply(new Matrix4().compose(new Vector3(...socket.transform.position_m), new Quaternion(...socket.transform.rotation_xyzw), new Vector3(1, 1, 1)));
    const point = new Vector3().setFromMatrixPosition(socketMatrix), normal = new Vector3(...socket.normal).transformDirection(socketMatrix);
    let nearest = Infinity;
    parent.traverse(node => {
      if (!(node instanceof Mesh)) return;
      const position = node.geometry.getAttribute('position'), indices = node.geometry.index;
      if (!position) return;
      const count = indices?.count ?? position.count;
      for (let i = 0; i + 2 < count; i += 3) {
        const vertices = [i, i + 1, i + 2].map(j => new Vector3().fromBufferAttribute(position, indices ? indices.getX(j) : j).applyMatrix4(node.matrixWorld));
        const [a, b, c] = vertices; requireAsset(a && b && c, 'binding', 'triangle');
        const triangle = new Triangle(a, b, c);
        if (triangle.getNormal(new Vector3()).dot(normal) > 0.99) nearest = Math.min(nearest, triangle.closestPointToPoint(point, new Vector3()).distanceTo(point));
      }
    });
    requireAsset(nearest <= 0.01, 'binding', `socket support:${socket.id}`);
  }
  return nodes;
}

const readOwned: AssetReader = async (url, signal) => {
  // Direct URL keeps the owned signal connected through body consumption without an intermediate Request.
  const controller = new AbortController(), abort = () => controller.abort(signal.reason);
  signal.addEventListener('abort', abort, { once: true });
  if (signal.aborted) abort();
  const timer = setTimeout(() => controller.abort(new DOMException('Asset body deadline exceeded', 'TimeoutError')), 15_000);
  try {
    const response = await fetch(url, { signal: controller.signal, redirect: 'error' });
    if (!response.ok) controller.abort();
    requireAsset(response.ok, 'network', `HTTP ${response.status}`);
    return await response.arrayBuffer();
  }
  finally { clearTimeout(timer); signal.removeEventListener('abort', abort); }
};
export async function loadAsset(asset: Asset, lod: AssetLod, options: LoadOptions): Promise<LoadedAsset> {
  const signal = options.signal ?? new AbortController().signal;
  let resources: AssetResources | undefined;
  try {
    const url = ownedAssetUrl(lod.artifact.path, options.origin);
    signal.throwIfAborted();
    const inspected = await inspectGlb(await (options.read ?? readOwned)(url, signal), asset, lod);
    signal.throwIfAborted();
    const manager = new LoadingManager();
    manager.setURLModifier(resource => {
      // All input URI fields were rejected; these URLs are created for embedded images by GLTFLoader.
      requireAsset(resource.startsWith('blob:'), 'path', 'decoder resource');
      return resource;
    });
    const gltf = await new GLTFLoader(manager).parseAsync(inspected.bytes, `${options.origin}/assets/steelworks/`);
    resources = collectResources(gltf.scene);
    signal.throwIfAborted();
    const nodes = decodedNodes(gltf.scene, asset);
    try { validateTransportDecodedGeometry(asset,nodes); }
    catch(error) { if(error instanceof TransportMechanicsError) throw new AssetLoadError('binding',error.reference,{cause:error}); throw error; }
    validateInternalFeedGeometry(asset,nodes);
    requireAsset(resources.textures.size === asset.textures.length, 'binding', 'decoded textures');
    const ownedResources = resources;
    let disposed = false;
    return { asset, lod, scene: gltf.scene, nodes, animations: Object.freeze([...gltf.animations]), resources,
      dispose: () => { if (!disposed) { disposed = true; disposeResources(ownedResources); } } };
  } catch (error) {
    if (resources) disposeResources(resources);
    if (signal.aborted) throw new AssetLoadError('cancelled', lod.artifact.path, { cause: error });
    if (error instanceof AssetLoadError) throw error;
    if (error instanceof Error || (error instanceof DOMException && error.name === 'TimeoutError')) throw new AssetLoadError('network', lod.artifact.path, { cause: error });
    throw error;
  }
}
