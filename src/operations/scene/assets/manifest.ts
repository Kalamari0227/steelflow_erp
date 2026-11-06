import {validateTransportMechanics,reviewedTransportFollower,reviewedTransportFixed,TransportMechanicsError} from './transportMechanics';
import { z } from 'zod';
import { isFeedLiftAncestor, validateAssetInternalFeeds } from './internalFeedGeometry';
import { registeredExtra, validateAssetSupportSockets } from '../motion/finishingContinuity';
import requirementsJson from '../../../../shared/asset-requirements.json';
import coverageJson from '../../../../shared/coverage-registry.json';
import { parseContractJson } from '../worldContractJson';
import { assetManifestShape } from './manifestShape';
import type { Asset, AssetArtifact, AssetManifest, AssetProvenance } from './manifestShape';
import { effectivePolicy, policyAlternatives } from '../motion/effectivePolicy';
import type { EffectivePolicy } from '../motion/effectivePolicy';
import { MotionError } from '../motion/errors';

export type { Asset, AssetManifest } from './manifestShape';
export class AssetManifestError extends Error {
  readonly name = 'AssetManifestError';
  constructor(readonly code: string, readonly reference: string) { super(`${code}: ${reference}`); }
}
function requireAsset(condition: boolean, code: string, reference: string): asserts condition {
  if (!condition) throw new AssetManifestError(code, reference);
}
function unique(values: readonly (string | number)[], reference: string): void {
  requireAsset(new Set(values).size === values.length, 'identity', reference);
}
function find<T extends { readonly id: string }>(rows: readonly T[], id: string): T {
  const found = rows.find(row => row.id === id);
  requireAsset(found !== undefined, 'reference', id);
  return found;
}
function contains(actual: readonly string[], expected: readonly string[], reference: string): void {
  requireAsset(expected.every(id => actual.includes(id)), 'requirements', reference);
}
function sameIds(actual: readonly string[], expected: readonly string[], code: string, reference: string): void {
  unique(actual, reference);
  requireAsset(actual.length === expected.length && expected.every(id => actual.includes(id)), code, reference);
}
function normalized(values: readonly number[], reference: string): void {
  requireAsset(Math.abs(Math.hypot(...values) - 1) < 1e-9, 'numeric', reference);
}
function sameRotation(a: readonly number[], b: readonly number[]): boolean {
  return Math.abs(Math.abs(a.reduce((sum, value, index) => sum + value * (b[index] ?? 0), 0)) - 1) < 1e-9;
}
function assertNever(value: never): never { throw new AssetManifestError('schema', String(value)); }

// Snapshot trusted catalogs so a caller's mutable JSON imports cannot weaken admission policy.
const requirements = structuredClone(requirementsJson);
const coverage = structuredClone(coverageJson);
const registeredRequirements = [...coverage.source_requirements, ...coverage.approved_scope_requirements];
function selectedPolicy(asset: Asset): EffectivePolicy {
  const owner = asset.category === 'equipment' ? asset.placement_ids[0]?.replace(/^equipment:/, '') ?? '' : '';
  try { return effectivePolicy(asset.category, asset.kind, owner, asset.motion_policy_id); }
  catch (error) {
    if (error instanceof MotionError) throw new AssetManifestError('requirements', `${asset.id}:motion-policy`);
    throw error;
  }
}
function identity(asset: Asset): void {
  const policy = selectedPolicy(asset);
  requireAsset(policy !== undefined && policy.families.includes(asset.family), 'requirements', `${asset.id}:kind-family`);
  for (const id of asset.requirement_ids) find(registeredRequirements, id);
  contains(asset.requirement_ids, policy.requirement_ids, `${asset.id}:policy-requirements`);
  const allowedQaTargets = new Set<string>([asset.variant, `kind:${asset.kind}`, ...asset.requirement_ids, ...asset.placement_ids]);
  for (const qa of asset.qa_row_ids) requireAsset(allowedQaTargets.has(find(coverage.qa_rows, qa).target_id), 'requirements', `${asset.id}:qa:${qa}`);
  for (const source of asset.source_refs) {
    const knownSource = coverage.sources.find(row => row.id === source.id);
    requireAsset(knownSource !== undefined || asset.requirement_ids.includes(source.id), 'reference', source.id);
    if (knownSource) requireAsset(source.uri === knownSource.url, 'reference', `${source.id}:uri`);
  }
  switch (asset.category) {
    case 'equipment': {
      const binding = requirements.existing_bindings.find(row => row.variant === asset.variant);
      requireAsset(binding !== undefined && binding.category === asset.category && binding.kind === asset.kind && binding.policy_group_id === effectivePolicy(asset.category, asset.kind, asset.placement_ids[0]?.replace(/^equipment:/, '') ?? '').id, 'requirements', `${asset.id}:variant-policy`);
      requireAsset(binding.allowed_families.includes(asset.family), 'requirements', `${asset.id}:variant-family`);
      sameIds(asset.placement_ids, binding.placement_ids, 'requirements', `${asset.id}:binding-placements`);
      contains(asset.requirement_ids, binding.requirement_ids, `${asset.id}:binding-requirements`);
      contains(asset.qa_row_ids, binding.qa_row_ids, `${asset.id}:binding-qa`);
      const variant = find(coverage.observed_inventory.semantic_variants, asset.variant);
      requireAsset(variant.kind === asset.kind, 'requirements', `${asset.id}:variant-kind`);
      contains(asset.requirement_ids, variant.requirement_ids, `${asset.id}:variant-requirements`);
      contains(asset.qa_row_ids, variant.qa_row_ids, `${asset.id}:variant-qa`);
      sameIds(asset.placement_ids, variant.equipment_ids.map(id => `equipment:${id}`), 'requirements', `${asset.id}:placements`);
      for (const placement of asset.placement_ids) {
        const row = find(coverage.observed_inventory.equipment, placement);
        requireAsset(row.kind === asset.kind && row.semantic_variant_id === asset.variant && binding.stage_ids.includes(row.stage_id), 'requirements', placement);
        contains(asset.requirement_ids, row.requirement_ids, `${placement}:requirements`);
        contains(asset.qa_row_ids, row.qa_row_ids, `${placement}:qa`);
      }
      break;
    }
    case 'fleet':
    case 'campus': {
      const binding = requirements.planned_bindings.find(row => row.variant === asset.variant);
      requireAsset(binding !== undefined && binding.category === asset.category && binding.kind === asset.kind && binding.family === asset.family && binding.policy_group_id === policy.id, 'requirements', `${asset.id}:planned-binding`);
      sameIds(asset.placement_ids, binding.placement_ids, 'requirements', `${asset.id}:placements`);
      contains(asset.requirement_ids, binding.requirement_ids, `${asset.id}:binding-requirements`);
      contains(asset.qa_row_ids, binding.qa_row_ids, `${asset.id}:binding-qa`);
      break;
    }
    default: assertNever(asset.category);
  }
  for (const fn of policy.required_functions) requireAsset(asset.moving_parts.some(part => part.function === fn && part.role === 'operational' && part.id === fn && part.node_id === fn), 'requirements', `${asset.id}:function:${fn}`);
  for (const part of asset.moving_parts.filter(p => p.role === 'operational' && p.binding.type !== 'mechanical_follower')) requireAsset(policy.required_functions.includes(part.function) && part.id === part.function && part.node_id === part.function, 'requirements', `${asset.id}:unreviewed-moving:${part.function}`);
  if (asset.category === 'equipment') {
    const alternatives = policyAlternatives(asset.category, asset.kind, asset.placement_ids[0]?.replace(/^equipment:/, '') ?? '');
    const registered = new Set(alternatives.flatMap(p => [...p.required_functions, ...p.fixed_functions]));
    for (const part of [...asset.moving_parts, ...asset.fixed_parts]) requireAsset(!registered.has(part.function) || policy.required_functions.includes(part.function) || policy.fixed_functions.includes(part.function), 'requirements', `${asset.id}:unselected-part:${part.function}`);
  }
  for (const fn of policy.fixed_functions) requireAsset(asset.fixed_parts.some(part => part.function === fn && part.id === fn && part.node_id === fn), 'requirements', `${asset.id}:fixed:${fn}`);
  for (const role of policy.required_socket_roles) requireAsset(asset.sockets.some(socket => socket.role === role && socket.id === role), 'requirements', `${asset.id}:socket:${role}`);
  for (const fn of policy.state_bound_fixed_functions) requireAsset(asset.fixed_parts.some(part => part.function === fn && part.binding !== null), 'requirements', `${asset.id}:state-binding:${fn}`);
  for (const part of asset.fixed_parts) requireAsset(part.binding === null || policy.state_bound_fixed_functions.includes(part.function), 'requirements', `${asset.id}:unreviewed-state:${part.function}`);
  if (policy.roof_required) requireAsset(asset.cutaway.roof_node_ids.length > 0 && asset.cutaway.interior_node_ids.length > 0, 'requirements', `${asset.id}:roof`);
}

/** The reviewed AOD tuyere is rigid in one canonical vessel frame, never an attachment graph. */
function fixedFrames(asset: Asset): void {
  const policy = selectedPolicy(asset);
  requireAsset(policy !== undefined, 'requirements', `${asset.id}:fixed-policy`);
  for (const part of asset.fixed_parts) {
    if (part.fixed_to_part_id === undefined) continue;
    if (reviewedTransportFixed(asset,part.id)) continue;
    const relations = 'relative_fixed_parts' in policy ? policy.relative_fixed_parts ?? [] : [];
    requireAsset(relations.some(row => row.fixed_part_id === part.id && row.parent_part_id === part.fixed_to_part_id), 'requirements', `${part.id}:unreviewed-fixed-frame`);
    requireAsset(part.id === part.node_id && part.id === part.function && part.binding !== null, 'requirements', `${part.id}:fixed-frame-identity`);
    const parent = find(asset.moving_parts, part.fixed_to_part_id), node = find(asset.nodes, part.node_id);
    requireAsset(parent.id === parent.node_id && parent.id === parent.function && parent.role === 'operational' && policy.required_functions.includes(parent.function), 'requirements', `${part.id}:canonical-fixed-parent`);
    requireAsset(parent.binding.type === 'clip' && parent.motion === 'rotation' && parent.range.unit === 'rad', 'requirements', `${part.id}:rotation-fixed-parent`);
    requireAsset(node.parent_id === parent.node_id, 'reference', `${part.id}:direct-fixed-parent`);
    requireAsset(asset.fixed_parts.filter(row => row.node_id === part.node_id).length === 1 && !asset.moving_parts.some(row => row.node_id === part.node_id), 'identity', `${part.id}:fixed-node-owner`);
    requireAsset(asset.moving_parts.filter(row => row.node_id === parent.node_id).length === 1 && !asset.fixed_parts.some(row => row.node_id === parent.node_id), 'identity', `${part.id}:parent-node-owner`);
    let ancestor = find(asset.nodes, parent.node_id).parent_id;
    while (ancestor !== null) {
      requireAsset(!asset.moving_parts.some(row => row.node_id === ancestor), 'reference', `${part.id}:stationary-parent-frame`);
      ancestor = find(asset.nodes, ancestor).parent_id;
    }
    for (const descendant of asset.nodes) {
      let cursor: string | null = descendant.id;
      while (cursor !== null && cursor !== part.node_id) cursor = find(asset.nodes, cursor).parent_id;
      if (cursor === null) continue;
      requireAsset(!asset.moving_parts.some(row => row.node_id === descendant.id), 'requirements', `${part.id}:moving-fixed-descendant`);
      requireAsset(!asset.sockets.some(socket => socket.node_id === descendant.id), 'requirements', `${part.id}:fixed-socket-descendant`);
      requireAsset(!asset.fixed_parts.some(row => row.id !== part.id && row.node_id === descendant.id), 'identity', `${part.id}:fixed-branch-owner`);
    }
  }
}

function hierarchy(asset: Asset): void {
  unique(asset.nodes.map(row => row.locator), `${asset.id}:locators`);
  const root = find(asset.nodes, asset.root_node_id);
  requireAsset(root.parent_id === null && asset.nodes.filter(node => node.parent_id === null).length === 1, 'reference', `${asset.id}:root`);
  requireAsset(root.transform.position_m.every(value => Math.abs(value) < 1e-9) && sameRotation(root.transform.rotation_xyzw, [0, 0, 0, 1]), 'numeric', `${asset.id}:root-origin`);
  for (const node of asset.nodes) {
    normalized(node.transform.rotation_xyzw, `${node.id}:quaternion`);
    const visited = new Set<string>([node.id]);
    let parent = node.parent_id;
    while (parent !== null) {
      requireAsset(!visited.has(parent), 'reference', `${node.id}:cycle`);
      visited.add(parent);
      parent = find(asset.nodes, parent).parent_id;
    }
  }
  const conversion = asset.export.conversion_rotation_xyzw;
  normalized(conversion, `${asset.id}:conversion`);
  requireAsset(sameRotation(conversion, [-Math.SQRT1_2, 0, 0, Math.SQRT1_2]), 'numeric', `${asset.id}:authoring-conversion`);
  for (const socket of asset.sockets) {
    find(asset.nodes, socket.node_id);
    normalized(socket.normal, `${socket.id}:normal`);
    normalized(socket.transform.rotation_xyzw, `${socket.id}:quaternion`);
    unique(socket.forms, `${socket.id}:forms`);
  }
  unique([...asset.moving_parts, ...asset.fixed_parts].map(row => row.id), `${asset.id}:parts`);
  for (const part of asset.fixed_parts) find(asset.nodes, part.node_id);
  try { validateTransportMechanics(asset); }
  catch(error) { if(error instanceof TransportMechanicsError) throw new AssetManifestError('requirements',error.reference); throw error; }
  fixedFrames(asset);
  for (const part of asset.moving_parts) {
    find(asset.nodes, part.node_id);
    normalized(part.axis, `${part.id}:axis`);
    requireAsset(part.range.max > part.range.min && part.range.rest >= part.range.min && part.range.rest <= part.range.max, 'numeric', `${part.id}:range`);
    switch (part.motion) {
      case 'rotation': requireAsset(part.range.unit === 'rad', 'numeric', `${part.id}:unit`); break;
      case 'translation': requireAsset(part.range.unit === 'm', 'numeric', `${part.id}:unit`); break;
      default: assertNever(part.motion);
    }
    requireAsset(asset.collision_proxies.some(proxy => proxy.purpose === 'moving_sweep' && proxy.part_id === part.id), 'collision', `${part.id}:sweep`);
    if (part.binding.type === 'mechanical_follower') {
      const driver = find(asset.moving_parts, part.binding.driver_part_id);
      const policy = selectedPolicy(asset);
      requireAsset(policy !== undefined && driver.binding.type === 'clip' && driver.role === 'operational' && driver.id === driver.node_id && driver.id === driver.function && policy.required_functions.includes(driver.function), 'requirements', `${part.id}:canonical-driver`);
      requireAsset(part.role === 'operational' && part.function === driver.function && part.id !== driver.id && part.node_id !== driver.node_id && part.id !== part.function, 'requirements', `${part.id}:follower-identity`);
      requireAsset(part.motion === 'rotation' && part.range.unit === 'rad' && driver.motion === 'rotation' && driver.range.unit === 'rad', 'requirements', `${part.id}:rotation-only`);
      requireAsset(asset.moving_parts.filter(row => row.node_id === part.node_id).length === 1 && !asset.fixed_parts.some(row => row.node_id === part.node_id), 'identity', `${part.id}:independent-node`);
      requireAsset(asset.moving_parts.filter(row => row.node_id === driver.node_id).length === 1 && !asset.fixed_parts.some(row => row.node_id === driver.node_id), 'identity', `${driver.id}:independent-node`);
      const node = find(asset.nodes, part.node_id), driverNode = find(asset.nodes, driver.node_id);
      requireAsset(node.parent_id !== null && (node.parent_id === driverNode.parent_id || reviewedTransportFollower(asset,part.id)), 'reference', `${part.id}:common-frame`);
      for (const moving of [part, driver]) {
        const current = find(asset.nodes, moving.node_id);
        requireAsset(moving.pivot_m.every((value, index) => Math.abs(value - (current.transform.position_m[index] ?? Infinity)) < 1e-9), 'numeric', `${moving.id}:pivot-origin`);
        let parent = current.parent_id;
        while (parent !== null) {
          requireAsset(!asset.moving_parts.some(row => row.node_id === parent) || isFeedLiftAncestor(asset,part.id,parent) || reviewedTransportFollower(asset,part.id), 'reference', `${part.id}:stationary-frame`);
          parent = find(asset.nodes, parent).parent_id;
        }
      }
      for (const socket of asset.sockets) {
        let ancestor: string | null = socket.node_id;
        while (ancestor !== null) {
          requireAsset(ancestor !== part.node_id, 'requirements', `${part.id}:socket-descendant:${socket.id}`);
          ancestor = find(asset.nodes, ancestor).parent_id;
        }
      }
      for (const value of [driver.range.min, driver.range.max]) {
        const derived = part.range.rest + part.binding.ratio * (value - driver.range.rest);
        requireAsset(Number.isFinite(derived) && derived >= part.range.min - 1e-9 && derived <= part.range.max + 1e-9, 'numeric', `${part.id}:derived-range`);
      }
    }
  }
  requireAsset(asset.collision_proxies.some(proxy => proxy.purpose === 'body'), 'collision', `${asset.id}:body`);
  for (const proxy of asset.collision_proxies) {
    find(asset.nodes, proxy.node_id);
    normalized(proxy.transform.rotation_xyzw, `${proxy.id}:quaternion`);
    unique(proxy.contact_socket_ids, `${proxy.id}:contacts`);
    for (const id of proxy.contact_socket_ids) find(asset.sockets, id);
    switch (proxy.purpose) {
      case 'moving_sweep': requireAsset(proxy.part_id !== null, 'collision', proxy.id); find(asset.moving_parts, proxy.part_id); break;
      case 'body': requireAsset(proxy.part_id === null, 'collision', proxy.id); break;
      default: assertNever(proxy.purpose);
    }
  }
  const cutaway = asset.cutaway;
  for (const id of [...cutaway.roof_node_ids, ...cutaway.interior_node_ids]) find(asset.nodes, id);
  for (const id of cutaway.retained_socket_ids) find(asset.sockets, id);
  if (cutaway.roof_node_ids.length > 0) {
    sameIds(cutaway.retained_socket_ids, asset.sockets.map(row => row.id), 'requirements', `${asset.id}:retained-sockets`);
    const retained = [...cutaway.interior_node_ids, ...asset.sockets.map(row => row.node_id), ...asset.moving_parts.map(row => row.node_id), ...asset.fixed_parts.map(row => row.node_id)];
    for (const id of retained) {
      let node: Asset['nodes'][number] | undefined = find(asset.nodes, id);
      while (node) {
        requireAsset(!cutaway.roof_node_ids.includes(node.id), 'requirements', `${asset.id}:roof-removes:${id}`);
        node = node.parent_id === null ? undefined : find(asset.nodes, node.parent_id);
      }
    }
  } else requireAsset(cutaway.interior_node_ids.length === 0 && cutaway.retained_socket_ids.length === 0, 'requirements', `${asset.id}:cutaway-without-roof`);
}

function lods(asset: Asset): void {
  unique(asset.lods.map(lod => lod.level), `${asset.id}:lod-levels`);
  unique(asset.lods.map(lod => lod.artifact.path), `${asset.id}:lod-paths`);
  requireAsset(asset.lods.some(lod => lod.level === 0), 'lod', `${asset.id}:lod0`);
  for (const lod of asset.lods) {
    const reference = `${asset.id}:lod${lod.level}`;
    requireAsset(lod.artifact.path.endsWith('.glb'), 'artifact', `${reference}:glb`);
    sameIds(lod.nodes.map(node => node.id), asset.nodes.map(node => node.id), 'lod', reference);
    sameIds(lod.socket_ids, asset.sockets.map(row => row.id), 'lod', `${reference}:sockets`);
    sameIds(lod.part_ids, [...asset.moving_parts, ...asset.fixed_parts].map(row => row.id), 'lod', `${reference}:parts`);
    sameIds(lod.material_ids, asset.materials.map(row => row.id), 'lod', `${reference}:materials`);
    unique(lod.nodes.map(node => node.locator), `${reference}:locators`);
    for (const node of lod.nodes) {
      const original = find(asset.nodes, node.id);
      normalized(node.transform.rotation_xyzw, `${reference}:${node.id}:quaternion`);
      requireAsset(node.parent_id === original.parent_id && node.locator === original.locator && node.transform.position_m.every((value, index) => original.transform.position_m[index] !== undefined && Math.abs(value - original.transform.position_m[index]) < 1e-9) && sameRotation(node.transform.rotation_xyzw, original.transform.rotation_xyzw), 'lod', `${reference}:${node.id}:transform`);
    }
    requireAsset((lod.artifact.status === 'built') === (lod.semantic_geometry_sha256 !== null), 'artifact', `${reference}:geometry-hash`);
  }
}

function checkArtifact(artifact: AssetArtifact, production: boolean): void {
  if (production) requireAsset(artifact.status === 'built', 'artifact', `production:${artifact.path}`);
}
function provenance(value: AssetProvenance, id: string, resources: readonly { readonly id: string; readonly provenance: AssetProvenance }[], production: boolean): void {
  switch (value.origin) {
    case 'self_created':
      checkArtifact(value.recipe, production);
      unique(value.third_party_inputs, `${id}:third-party-inputs`);
      for (const input of value.third_party_inputs) {
        requireAsset(input !== id && resources.filter(resource => resource.id === input).length === 1, 'license', `${id}:input:${input}`);
        requireAsset(find(resources, input).provenance.origin === 'external', 'license', `${id}:input:${input}`);
      }
      break;
    case 'external': {
      const expectedUrl = value.license === 'CC0-1.0' ? 'https://creativecommons.org/publicdomain/zero/1.0/' : 'https://creativecommons.org/licenses/by/4.0/';
      requireAsset(value.license_url === expectedUrl || value.license_url === `${expectedUrl}legalcode` || value.license_url === `${expectedUrl}legalcode.en`, 'license', `${id}:license-url`);
      break;
    }
    default: assertNever(value);
  }
}
function resources(asset: Asset, manifest: AssetManifest): void {
  const production = manifest.purpose === 'production';
  requireAsset(asset.source.artifact.path.endsWith('.blend'), 'artifact', `${asset.id}:editable-source`);
  const tracked = [...manifest.assets.map(row => ({ id: row.id, provenance: row.source.provenance })), ...asset.materials, ...asset.textures];
  unique(tracked.map(row => row.id), `${asset.id}:provenance-ids`);
  for (const resource of [{ id: asset.id, provenance: asset.source.provenance }, ...asset.materials, ...asset.textures]) provenance(resource.provenance, resource.id, tracked, production);
  for (const artifact of [asset.source.artifact, asset.export.tool_artifact, asset.export.recipe, ...asset.textures.map(texture => texture.artifact), ...asset.lods.map(lod => lod.artifact)]) checkArtifact(artifact, production);
  for (const material of asset.materials) {
    unique(material.textures.map(slot => slot.slot), `${material.id}:slots`);
    for (const slot of material.textures) {
      const texture = find(asset.textures, slot.texture_id);
      requireAsset(texture.color_space === (slot.slot === 'baseColor' || slot.slot === 'emissive' ? 'srgb' : 'linear'), 'requirements', `${material.id}:${slot.slot}:color-space`);
    }
  }
  for (const texture of asset.textures) requireAsset(asset.materials.some(material => material.textures.some(slot => slot.texture_id === texture.id)), 'reference', `${texture.id}:unused-texture`);
}
function supportExtras(asset:Asset,complete=false):void {
  try { validateAssetSupportSockets(asset,complete); }
  catch(error) { if(error instanceof MotionError)throw new AssetManifestError(error.code,error.reference);throw error; }
}
function variantSemantics(asset: Asset, previous: Asset): void {
  const base = effectivePolicy(previous.category, previous.kind, previous.category === 'equipment' ? previous.placement_ids[0]?.replace(/^equipment:/, '') ?? '' : '');
  for (const part of previous.moving_parts.filter(row => row.role === 'operational' && row.binding.type !== 'mechanical_follower' && base.required_functions.includes(row.function))) {
    const matches = asset.moving_parts.filter(row => row.role === 'operational' && row.binding.type !== 'mechanical_follower' && row.function === part.function);
    requireAsset(matches.some(row => row.id === part.id && row.node_id === part.node_id), 'identity', `${asset.id}:variant-part:${part.function}`);
  }
  for (const part of previous.fixed_parts.filter(row => base.fixed_functions.includes(row.function))) requireAsset(asset.fixed_parts.some(row => row.function === part.function && row.id === part.id && row.node_id === part.node_id), 'identity', `${asset.id}:variant-fixed:${part.function}`);
  for (const socket of previous.sockets.filter(s=>!registeredExtra(previous,s.id))) requireAsset(asset.sockets.some(row => row.role === socket.role && row.id === socket.id && row.node_id === socket.node_id), 'identity', `${asset.id}:variant-socket:${socket.role}`);
}

/** Metadata admission only: no file bytes, GLB geometry or actual clip/procedure implementation is certified. */
export function parseAssetManifestValue(input: unknown): AssetManifest {
  const result = assetManifestShape.safeParse(input);
  if (!result.success) throw new AssetManifestError('schema', z.prettifyError(result.error));
  const manifest = result.data;
  unique(manifest.assets.map(asset => asset.id), 'assets');
  unique(manifest.assets.map(asset => asset.variant), 'variants');
  unique(manifest.assets.flatMap(asset => asset.placement_ids), 'placements');
  const previous = new Map<string, Asset>();
  for (const asset of manifest.assets) {
    for (const key of ['nodes', 'sockets', 'moving_parts', 'fixed_parts', 'materials', 'textures', 'collision_proxies', 'source_refs'] as const) unique(asset[key].map(row => row.id), `${asset.id}:${key}`);
    for (const ids of [asset.requirement_ids, asset.qa_row_ids, asset.placement_ids, asset.cutaway.roof_node_ids, asset.cutaway.interior_node_ids, asset.cutaway.retained_socket_ids]) unique(ids, asset.id);
    identity(asset);
    hierarchy(asset);
    validateAssetInternalFeeds(asset);
    supportExtras(asset);
    lods(asset);
    resources(asset, manifest);
    const key = `${asset.category}:${asset.kind}`;
    const prior = previous.get(key);
    if (prior) { variantSemantics(asset, prior); variantSemantics(prior, asset); }
    previous.set(key, asset);
  }
  return manifest;
}
export function parseAssetManifest(raw: string): AssetManifest { return parseAssetManifestValue(parseContractJson(raw)); }
/** New finishing delivery completeness is separate from legacy/base manifest admission. */
export function parseFinishingAssetManifestValue(input: unknown): AssetManifest {
  const manifest = parseAssetManifestValue(input);
  const expected = requirements.existing_bindings.filter(b => b.allowed_families.includes('finishing'));
  sameIds(manifest.assets.map(a => a.variant), expected.map(b => b.variant), 'requirements', 'finishing:variants');
  let extended = 0;
  for (const asset of manifest.assets) {
    requireAsset(asset.category === 'equipment' && asset.family === 'finishing', 'requirements', `${asset.id}:finishing-family`);
    const binding = expected.find(b => b.variant === asset.variant);
    requireAsset(binding !== undefined, 'requirements', asset.variant);
    const extension = 'extension_policy_id' in binding ? binding.extension_policy_id : undefined;
    requireAsset(selectedPolicy(asset).id === (extension ?? binding.policy_group_id), 'requirements', `${asset.id}:finishing-profile`);
    supportExtras(asset,true);
    if (extension !== undefined) extended++;
  }
  requireAsset(manifest.assets.length === 58 && extended === 42, 'requirements', 'finishing:42-extended-16-base');
  return manifest;
}
/** T12 must call this entry point, then independently verify declared hashes and real exported geometry. */
export function parseProductionAssetManifest(raw: string): AssetManifest {
  const manifest = parseAssetManifest(raw);
  requireAsset(manifest.purpose === 'production', 'artifact', 'production purpose required');
  return manifest;
}
