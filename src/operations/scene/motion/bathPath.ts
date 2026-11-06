import { z } from 'zod';
import sourceJson from '../../../../shared/finishing-bath-source05.json';
import { parseContractJson } from '../worldContractJson';

const source = structuredClone(sourceJson);
import { MotionError, equalData, requireMotion } from './errors';
import type { Anchor, AssetBinding, MaterialSupport, MotionEnvelope, MotionRegistry } from './shapes';
import type { MotionContext } from './context';

const text = z.string().min(1);
const digest = z.string().regex(/^[0-9a-f]{64}$/);
const finite = z.number().finite();
export const bathPathReferenceShape = z.strictObject({ schema_version: z.literal(1), profile_id: text }).readonly();
export const bathPathBindingShape = z.strictObject({
  schema_version: z.literal(1), id: text, kind: z.literal('finite_galvanizing_bath'),
  custody_socket_id: text, driver_function_id: text, source_asset_id: text,
  source_manifest_sha256: digest, source_recipe_sha256: digest,
  glb_sha256_by_lod: z.tuple([digest, digest, digest]).readonly(),
  stock_length_m: finite, width_m: finite, thickness_m: finite,
  required_state_functions: z.array(text).readonly(), outlet_roller_ids: z.array(text).readonly(),
}).readonly();
export type BathPathBinding = z.infer<typeof bathPathBindingShape>;
type BathAssetBinding = Extract<AssetBinding, { readonly bath_paths: readonly BathPathBinding[] }>;

/** Exact table equality is descriptor eligibility, never physical admission. */
export function validateBathBinding(binding: BathAssetBinding, world: MotionContext['world']) {
  const row = source.profiles.find(p => p.owner_id === binding.owner_id);
  requireMotion(row !== undefined, 'binding', binding.owner_id);
  requireMotion(equalData(binding.bath_paths, [row.descriptor]), 'binding', row.descriptor.id);
  const { bath_paths: _bath, ...base } = binding;
  requireMotion(equalData(base, row.canonical_binding), 'binding', binding.owner_id);
  const owner = world.owners.find(o => o.id === binding.owner_id);
  requireMotion(owner !== undefined && owner.kind === row.owner_kind && equalData(owner.pose, row.owner_pose), 'binding', binding.owner_id);
  for (const socket of binding.sockets) {
    const graph = owner.sockets.find(s => s.id === socket.socket_id);
    requireMotion(graph !== undefined && equalData(graph.pose.position, socket.position_m) && graph.pose.yaw_rad === 0, 'binding', binding.owner_id);
  }
}

/** Either half forces this branch, including a stripped material reference. */
export function validateBathSupport(anchor: Anchor, material: MaterialSupport, binding: AssetBinding): void {
  if (!('bath_path' in material || 'bath_paths' in binding)) return;
  requireMotion('bath_path' in material && 'bath_paths' in binding, 'binding', anchor.owner_id);
  const descriptor = binding.bath_paths[0], reference = material.bath_path.profile_id;
  requireMotion(reference === descriptor.id && anchor.owner_id === binding.owner_id && anchor.socket_id === 'work', 'binding', reference);
  const socket = binding.sockets[0];
  requireMotion(socket !== undefined && equalData(anchor.position_m, socket.position_m) && equalData(anchor.orientation_xyzw, socket.orientation_xyzw), 'binding', reference);
  const d = material.dimensions;
  requireMotion(d.length_mm === descriptor.stock_length_m * 1000 && d.width_mm === descriptor.width_m * 1000
    && d.thickness_mm === descriptor.thickness_m * 1000 && d.diameter_mm === null && d.inner_diameter_mm === null
    && equalData(material.orientation_xyzw, [0,0,0,1]) && equalData(material.support_local_mm, [0,-descriptor.thickness_m * 500,0]), 'binding', reference);
}

export function rejectUnqualifiedBath(anchor: Anchor, material: MaterialSupport, binding: AssetBinding): void {
  validateBathSupport(anchor, material, binding);
  if ('bath_path' in material || 'bath_paths' in binding) throw new MotionError('bath_unqualified', anchor.owner_id);
}

export function validateBathContext(context: MotionContext): void {
  for (const binding of context.asset_bindings) {
    if (!('bath_paths' in binding)) continue;
    requireMotion(!context.snapshot.fleet.some(f => f.id === binding.owner_id) && !context.snapshot.vehicle_states.some(v => v.fleet_id === binding.owner_id), 'binding', binding.owner_id);
  }
  for (const envelope of context.authorizations) validateBathEnvelope(envelope, context);
}

function validateBathEnvelope(envelope: MotionEnvelope, context: MotionContext): void {
  const pairs = [{anchor: envelope.anchor, material: envelope.material}];
  if (envelope.boundary !== null) pairs.push({anchor: envelope.boundary.previous_anchor, material: envelope.boundary.previous_material});
  for (const {anchor, material} of pairs) {
    if (!('bath_path' in material)) continue;
    const binding = context.asset_bindings.find(b => b.owner_id === anchor.owner_id);
    requireMotion(binding !== undefined, 'binding', anchor.owner_id);
    validateBathSupport(anchor, material, binding);
  }
}

/** All paths are fixed artifact-map keys; provenance strings are never opened. */
async function verifySourceBytes(sourceBytes: ReadonlyMap<string, Uint8Array>): Promise<Uint8Array> {
  requireMotion(sourceBytes.size === source.artifacts.length && source.artifacts.every(a => sourceBytes.has(a.path)), 'binding', source.algorithm_id);
  // Own every view before the first await; later caller mutations cannot change verification.
  const snapshot = source.artifacts.map(artifact => {
    const bytes = sourceBytes.get(artifact.path);
    requireMotion(bytes !== undefined, 'binding', artifact.path);
    try {
      // Intrinsic getters read the real view slots even when own properties shadow them.
      const typedArray = Object.getPrototypeOf(Uint8Array.prototype);
      const buffer = Object.getOwnPropertyDescriptor(typedArray, 'buffer')?.get;
      const offset = Object.getOwnPropertyDescriptor(typedArray, 'byteOffset')?.get;
      const extent = Object.getOwnPropertyDescriptor(typedArray, 'byteLength')?.get;
      const byteLength = Object.getOwnPropertyDescriptor(ArrayBuffer.prototype, 'byteLength')?.get;
      requireMotion(buffer !== undefined && offset !== undefined && extent !== undefined && byteLength !== undefined, 'binding', artifact.path);
      const backing = Reflect.apply(buffer, bytes, []);
      Reflect.apply(byteLength, backing, []);
      const slice = new Uint8Array(backing, Reflect.apply(offset, bytes, []), Reflect.apply(extent, bytes, []));
      return {artifact, bytes: new Uint8Array(slice)};
    } catch (error) {
      if (!(error instanceof TypeError)) throw error;
      throw new MotionError('binding', artifact.path);
    }
  });
  for (const {artifact, bytes} of snapshot) {
    const result = await crypto.subtle.digest('SHA-256', bytes);
    const actual = [...new Uint8Array(result)].map(value => value.toString(16).padStart(2, '0')).join('');
    requireMotion(actual === artifact.sha256, 'binding', artifact.path);
  }
  const manifest = snapshot.find(row => row.artifact.path === 'public/assets/steelworks/finishing/manifest.json')?.bytes;
  requireMotion(manifest !== undefined, 'binding', source.algorithm_id);
  return manifest;
}

/** Metadata eligibility only: complete source inventory precedes the work wire projection. */
export async function bindingsFromBathSource(sourceBytes: ReadonlyMap<string, Uint8Array>, retainedWorld: MotionContext['world']): Promise<readonly AssetBinding[]> {
  const bytes = await verifySourceBytes(sourceBytes);
  const { bindingsFromAssetManifest } = await import('./assetAdapter');
  const { parseAssetManifestValue } = await import('../assets/manifest');
  const { bindingShape } = await import('./shapes');
  const manifest = parseAssetManifestValue(parseContractJson(new TextDecoder('utf-8', {fatal:true}).decode(bytes)));
  requireMotion(manifest.assets.length === source.profiles.length, 'binding', source.algorithm_id);
  const selections = source.profiles.map(row => {
    const asset = manifest.assets.find(a => a.id === row.descriptor.source_asset_id);
    requireMotion(asset !== undefined && equalData(asset.placement_ids, ['equipment:' + row.owner_id]) && asset.motion_policy_id === row.canonical_binding.policy_id, 'binding', row.owner_id);
    requireMotion(equalData({nodes:asset.nodes,moving_parts:asset.moving_parts,fixed_parts:asset.fixed_parts,sockets:asset.sockets,lods:asset.lods},row.source_inventory), 'binding', row.owner_id);
    const socket_families = Object.fromEntries(asset.sockets.map(socket => {
      const family = socket.forms[0];
      requireMotion(family !== undefined, 'binding', row.owner_id);
      return [socket.id, family];
    }));
    return {owner_id:row.owner_id,asset_id:asset.id,socket_families};
  });
  const extracted = bindingsFromAssetManifest(manifest, selections);
  return Object.freeze(extracted.map(binding => {
    const row = source.profiles.find(p => p.owner_id === binding.owner_id);
    requireMotion(row !== undefined, 'binding', binding.owner_id);
    const work = binding.sockets.filter(s => s.socket_id === 'work');
    requireMotion(work.length === 1, 'binding', binding.owner_id);
    const projected = bindingShape.parse({...binding,sockets:work,bath_paths:[row.descriptor]});
    requireMotion('bath_paths' in projected, 'binding', binding.owner_id);
    validateBathBinding(projected, retainedWorld);
    return projected;
  }));
}

/** No capability can be returned until the independent complete physical proof exists. */
export async function createBathRuntime(sourceBytes: ReadonlyMap<string, Uint8Array>, retainedWorld: MotionContext['world']): Promise<never> {
  await bindingsFromBathSource(sourceBytes, retainedWorld);
  // Exact hashes and metadata cannot replace GLB decoding, contact or interval proof.
  throw new MotionError('bath_unqualified', source.algorithm_id);
}

export function evaluateBathMotion(_runtime: never, _request: Readonly<{envelope: MotionEnvelope; context: MotionContext}>, _registry: MotionRegistry): never {
  throw new MotionError('bath_unqualified', source.algorithm_id);
}


export function guardBathRequest(envelope: MotionEnvelope, context: MotionContext): void {
  validateBathEnvelope(envelope, context);
  if ('bath_path' in envelope.material || (envelope.boundary !== null && 'bath_path' in envelope.boundary.previous_material)
    || context.asset_bindings.some(binding => 'bath_paths' in binding)) {
    throw new MotionError('bath_unqualified', envelope.anchor.owner_id);
  }
}
