import { z } from 'zod';
import { internalFeedAssetShape } from '../motion/internalFeed';
import sharedSchema from '../../../../shared/asset-manifest.schema.json';
import { finiteNumber } from '../worldContractMath';

const id = z.string().max(160).regex(/^[A-Za-z0-9][A-Za-z0-9_.:-]*(?![\s\S])/).brand('AssetSemanticId');
const text = z.string().min(1).max(2048).refine(value => value.trim().length > 0);
const hash = z.string().regex(/^[a-f0-9]{64}(?![\s\S])/).brand('AssetSha256');
const path = z.string().max(512).regex(/^(?!\/)(?!.*(?:^|\/)\.\.(?:\/|$))[A-Za-z0-9_./-]+(?![\s\S])/);
const url = z.url().refine(value => value.startsWith('https://') && !/\s/.test(value));
const coordinate = finiteNumber.min(-1e9).max(1e9);
const unit = finiteNumber.min(-1).max(1);
const fraction = finiteNumber.min(0).max(1);
const vector = z.tuple([coordinate, coordinate, coordinate]).readonly();
const axis = z.tuple([unit, unit, unit]).readonly();
const quaternion = z.tuple([unit, unit, unit, unit]).readonly();
const ids = z.array(id).max(10000).readonly();
const builtArtifact = z.strictObject({ status: z.literal('built'), path, sha256: hash }).readonly();
const artifact = z.discriminatedUnion('status', [z.strictObject({ status: z.literal('unbuilt'), path }).readonly(), builtArtifact]);
const provenance = z.discriminatedUnion('origin', [
  z.strictObject({ origin: z.literal('self_created'), creator: text, title: text, license: z.literal('project-owned'), distribution_permission: z.enum(['project-local', 'redistribution-authorized']), recipe: artifact, third_party_inputs: ids }).readonly(),
  z.strictObject({ origin: z.literal('external'), creator: text, title: text, license: z.enum(['CC0-1.0', 'CC-BY-4.0']), source_url: url, download_url: url, license_url: url, evidence: builtArtifact, original: builtArtifact, verified_at: z.iso.date(), modification_note: text, attribution: builtArtifact }).readonly(),
]);
const transform = z.strictObject({ position_m: vector, rotation_xyzw: quaternion }).readonly();
const node = z.strictObject({ id, parent_id: id.nullable(), locator: path, transform }).readonly();
const nodes = z.array(node).min(1).max(10000).readonly();
const socket = z.strictObject({ id, node_id: id, role: z.enum(['support', 'load', 'grip', 'entry', 'work', 'exit', 'coupler']), transform, normal: axis, forms: z.array(z.enum(['ORE', 'SCRAP', 'LIQUID_IRON', 'LIQUID_STEEL', 'SLAB', 'BLOOM', 'BILLET', 'INGOT', 'STRIP', 'PLATE', 'COIL', 'WIRE_COIL', 'PACKAGED'])).min(1).readonly(), max_load_kg: z.number().int().positive().max(Number.MAX_SAFE_INTEGER) }).readonly();
const bindingFields = { clock: z.literal('server_sim'), phase: z.enum(['entry', 'work', 'exit', 'approach', 'load', 'travel', 'unload', 'return']), progress_source: z.literal('server_phase_progress'), pause: z.literal('hold'), fault: z.literal('hold'), rest: z.literal('range_rest') };
const binding = z.discriminatedUnion('type', [
  z.strictObject({ type: z.literal('procedural'), ...bindingFields, procedure_id: id }).readonly(),
  z.strictObject({ type: z.literal('clip'), ...bindingFields, clip_id: id }).readonly(),
  z.strictObject({ type: z.literal('mechanical_follower'), driver_part_id: id, ratio: finiteNumber.refine(value => value !== 0) }).readonly(),
]);
const movingPart = z.strictObject({ id, node_id: id, function: id, role: z.enum(['operational', 'decorative']), motion: z.enum(['rotation', 'translation']), axis, pivot_m: vector, range: z.strictObject({ min: coordinate, max: coordinate, rest: coordinate, unit: z.enum(['m', 'rad']) }).readonly(), binding }).readonly();
const fixedBinding = z.strictObject({ type: z.literal('operational_state'), clock: bindingFields.clock, phase: bindingFields.phase, progress_source: bindingFields.progress_source, pause: bindingFields.pause, fault: bindingFields.fault, rest: z.literal('inactive'), state_id: id }).readonly();
const fixedPart = z.strictObject({ id, node_id: id, function: id, reason: text, binding: fixedBinding.nullable(), fixed_to_part_id: id.optional() }).readonly();
const textureSlot = z.strictObject({ slot: z.enum(['baseColor', 'normal', 'metallicRoughness', 'occlusion', 'emissive']), texture_id: id }).readonly();
const material = z.strictObject({ id, model: z.literal('metallic-roughness'), base_color: z.tuple([fraction, fraction, fraction, fraction]).readonly(), metallic: fraction, roughness: fraction, textures: z.array(textureSlot).readonly(), provenance }).readonly();
const texture = z.strictObject({ id, artifact, color_space: z.enum(['srgb', 'linear']), provenance }).readonly();
const collision = z.strictObject({ id, node_id: id, shape: z.literal('box'), transform, size_m: z.tuple([coordinate.positive(), coordinate.positive(), coordinate.positive()]).readonly(), purpose: z.enum(['body', 'moving_sweep']), part_id: id.nullable(), contact_socket_ids: ids }).readonly();
const lod = z.strictObject({ level: z.number().int().min(0).max(3), artifact, semantic_geometry_sha256: hash.nullable(), nodes, socket_ids: ids, part_ids: ids, material_ids: ids }).readonly();
const sourceRef = z.strictObject({ id, uri: text, note: text }).readonly();
const source = z.strictObject({ artifact, provenance }).readonly();
const exportShape = z.strictObject({ tool: z.literal('Blender'), version: z.literal('4.5.15'), tool_artifact: artifact, recipe: artifact, settings: z.strictObject({ format: z.literal('GLB'), y_up: z.literal(true), apply_transforms: z.literal(true), animations: z.literal(true) }).readonly(), authoring_axes: z.strictObject({ up: z.literal('+Z'), forward: z.literal('+X') }).readonly(), conversion_rotation_xyzw: quaternion, world_boundary: z.literal('yaw_root_full_quaternion_internal') }).readonly();
const asset = z.strictObject({
  id, family: z.enum(['steelmaking', 'hot-rolling', 'finishing', 'stainless', 'titanium', 'transport', 'campus']), category: z.enum(['equipment', 'fleet', 'campus']), kind: id, variant: id, motion_policy_id: id.optional(),
  requirement_ids: ids, qa_row_ids: ids, placement_ids: ids, source_refs: z.array(sourceRef).readonly(),
  coordinate_system: z.strictObject({ length: z.literal('m'), up: z.literal('+Y'), forward: z.literal('+X'), handedness: z.literal('right'), angle: z.literal('rad') }).readonly(),
  internal_feeds:z.array(internalFeedAssetShape).length(1).readonly().optional(),
  root_node_id: id, nodes, sockets: z.array(socket).readonly(), moving_parts: z.array(movingPart).readonly(), fixed_parts: z.array(fixedPart).readonly(),
  cutaway: z.strictObject({ roof_node_ids: ids, interior_node_ids: ids, retained_socket_ids: ids }).readonly(),
  materials: z.array(material).readonly(), textures: z.array(texture).readonly(), collision_proxies: z.array(collision).readonly(), lods: z.array(lod).readonly(), source, export: exportShape,
}).readonly();
const typedManifest = z.strictObject({ schema_version: z.literal(1), purpose: z.enum(['contract_example', 'production']), assets: z.array(asset).readonly() }).readonly();

// Shared JSON Schema owns structural admission; this projection supplies strict immutable TypeScript types.
export const assetManifestShape = z.fromJSONSchema(z.record(z.string(), z.unknown()).parse(sharedSchema)).pipe(typedManifest);
export type AssetManifest = z.infer<typeof typedManifest>;
export type Asset = AssetManifest['assets'][number];
export type AssetArtifact = z.infer<typeof artifact>;
export type AssetProvenance = z.infer<typeof provenance>;
