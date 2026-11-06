import { z } from 'zod';
import { FactoryRunSchema } from '../../contractsV3Core';
import { MaterialSchema } from '../../contractsV3Rows';
import { internalFeedBindingShape, internalFeedReferenceShape } from './internalFeed';
import { bathPathBindingShape, bathPathReferenceShape } from './bathPath';
import { requireMotion, unique } from './errors';

export const text = z.string().min(1);
export const finite = z.number().finite();
export const vector = z.tuple([finite, finite, finite]).readonly();
export const quaternion = z.tuple([finite, finite, finite, finite]).readonly().superRefine(value => {
  requireMotion(Math.abs(Math.hypot(...value) - 1) <= 1e-6, 'quaternion', 'orientation_xyzw');
});
export const progress = finite.min(0).max(1);
export const windowName = z.enum(['entry', 'work', 'exit', 'approach', 'load', 'travel', 'unload', 'return', 'hold']);
export const executionKind = z.enum(['process', 'transport', 'logistics']);
export const windowShape = z.strictObject({ id: windowName, start: progress, end: progress }).readonly().superRefine(value => {
  requireMotion(value.start < value.end, 'window', value.id);
});
export const functionNeed = z.strictObject({ function_id: text, kind: z.enum(['moving', 'state', 'unresolved']), window_id: windowName, policy_id: text.nullable(), semantic_need: text }).readonly();
export const recipeShape = z.strictObject({
  id: text, semantic_id: text, execution_kind: executionKind, meaning: text,
  requirement_ids: z.array(text).readonly(), policy_ids: z.array(text).readonly(), source_step_ids: z.array(text).readonly(), compiled_step_ids: z.array(text).readonly(),
  windows: z.array(windowShape).readonly(), functions: z.array(functionNeed).readonly(), binding_status: z.literal('pending_delivery'),
}).readonly().superRefine(value => {
  requireMotion(value.windows.length > 0, 'window', value.id);
  unique(value.windows.map(w => w.id), value.id);
  for (let i = 1; i < value.windows.length; i++) {
    const prior = value.windows[i - 1], current = value.windows[i];
    requireMotion(prior !== undefined && current !== undefined && prior.end <= current.start, 'window_overlap', value.id);
  }
  unique(value.policy_ids, value.id);
  unique(value.functions.map(f => `${f.policy_id ?? ''}:${f.function_id}`), value.id);
  requireMotion(value.functions.every(f => value.windows.some(w => w.id === f.window_id)), 'window', value.id);
});
export const registryShape = z.strictObject({
  schema_version: z.literal(1), authority: text, recipes: z.array(recipeShape).readonly(),
  applicability: z.array(z.strictObject({ kind: z.enum(['requirement', 'connection', 'disposition', 'receipt', 'fleet']), reference_id: text, recipe_ids: z.array(text).readonly() }).readonly()).readonly(),
}).readonly();
export const anchorShape = z.strictObject({ owner_id: text, socket_id: text, position_m: vector, orientation_xyzw: quaternion }).readonly();
const dimension = finite.positive().nullable().default(null);
const dimensions = z.strictObject({ length_mm: dimension, width_mm: dimension, thickness_mm: dimension, diameter_mm: dimension, inner_diameter_mm: dimension }).readonly();
const legacyMaterialSupportShape = z.strictObject({
  material_id: text, material_version_id: text, form: MaterialSchema.unwrap().shape.form,
  dimensions, support_local_mm: vector, orientation_xyzw: quaternion,
}).readonly();
export const materialSupportShape=z.union([z.strictObject({...legacyMaterialSupportShape.unwrap().shape,bath_path:bathPathReferenceShape}).readonly(),z.strictObject({...legacyMaterialSupportShape.unwrap().shape,internal_feed:internalFeedReferenceShape}).readonly(),legacyMaterialSupportShape]);
export const channelKind = z.enum(['rotation', 'translation', 'state']);
export const mechanicalChannelShape = z.strictObject({ function_id: text, node_id: text, kind: channelKind, window_id: windowName, axis: vector, pivot_m: vector, start_value: finite, end_value: finite }).readonly();
export const channelValueShape = z.strictObject({ function_id: text, node_id: text, kind: channelKind, value: finite, axis: vector, pivot_m: vector }).readonly();
const runFields = FactoryRunSchema.unwrap().shape;
export const envelopeShape = z.strictObject({
  schema_version: z.literal(1), run_id: text, bundle_id: text, bundle_hash: runFields.bundle_hash, revision: runFields.revision,
  confirmed_sim_ms: runFields.elapsed_ms, execution_id: text, execution_kind: executionKind, recipe_id: text,
  phase_start_ms: runFields.elapsed_ms, phase_end_ms: runFields.elapsed_ms, effective_sim_ms: runFields.elapsed_ms,
  frozen_progress: progress.nullable(), clock_state: z.enum(['running', 'paused', 'stale', 'blocked']), material: materialSupportShape,
  attachment_id: text, anchor: anchorShape, channels: z.array(mechanicalChannelShape).readonly(),
  boundary: z.strictObject({ released_attachment_id: text, acquired_attachment_id: text, at_ms: runFields.elapsed_ms, previous_material: materialSupportShape, previous_anchor: anchorShape, previous_channels: z.array(channelValueShape).readonly() }).readonly().nullable(),
}).readonly().superRefine(value => {
  requireMotion(value.phase_end_ms > value.phase_start_ms, 'window', value.execution_id);
  requireMotion(value.effective_sim_ms <= value.confirmed_sim_ms, 'future_time', value.execution_id);
  requireMotion(value.clock_state === 'running' || value.frozen_progress !== null, 'held_progress_required', value.execution_id);
  unique(value.channels.map(c => c.function_id), value.execution_id);
  for (const c of value.channels) requireMotion(Math.abs(c.axis.reduce((sum, x) => sum + x * x, 0) - 1) <= 1e-6, 'axis', c.function_id);
});
const bindingFunction = z.strictObject({ function_id: text, node_id: text, kind: channelKind, axis: vector, pivot_m: vector, min_value: finite, max_value: finite }).readonly().superRefine(fn => {
  requireMotion(fn.min_value < fn.max_value, 'binding', fn.function_id);
  requireMotion(Math.abs(fn.axis.reduce((sum, x) => sum + x * x, 0) - 1) <= 1e-6, 'axis', fn.function_id);
  requireMotion(fn.node_id === fn.function_id, 'binding', fn.function_id);
});
const legacyBindingShape = z.strictObject({
  owner_id: text, policy_id: text,
  sockets: z.array(z.strictObject({ socket_id: text, family: z.enum(['ORE', 'SCRAP', 'LIQUID_IRON', 'LIQUID_STEEL', 'SLAB', 'BLOOM', 'BILLET', 'INGOT', 'STRIP', 'PLATE', 'COIL', 'WIRE_COIL', 'PACKAGED']), motion_function_ids: z.array(text).readonly(), position_m: vector, orientation_xyzw: quaternion }).readonly()).readonly(),
  functions: z.array(bindingFunction).readonly(),
}).readonly().superRefine(binding => {
  unique(binding.sockets.map(s => s.socket_id), binding.owner_id);
  unique(binding.functions.map(f => f.function_id), binding.owner_id);
  for (const socket of binding.sockets) requireMotion(new Set(socket.motion_function_ids).size === socket.motion_function_ids.length && socket.motion_function_ids.every(id => binding.functions.some(f => f.function_id === id && f.kind !== 'state')), 'binding', binding.owner_id);
});
const bathBindingShape = z.strictObject({...legacyBindingShape.unwrap().shape,bath_paths:z.tuple([bathPathBindingShape]).readonly()}).readonly().superRefine(binding => {
  unique(binding.sockets.map(s => s.socket_id), binding.owner_id);
  unique(binding.functions.map(f => f.function_id), binding.owner_id);
  for (const socket of binding.sockets) requireMotion(new Set(socket.motion_function_ids).size === socket.motion_function_ids.length && socket.motion_function_ids.every(id => binding.functions.some(f => f.function_id === id && f.kind !== 'state')), 'binding', binding.owner_id);
});
export const bindingShape=z.union([bathBindingShape,z.strictObject({...legacyBindingShape.unwrap().shape,internal_feeds:z.array(internalFeedBindingShape).length(1).readonly()}).readonly().superRefine(binding=>{
  unique(binding.sockets.map(s=>s.socket_id),binding.owner_id);unique(binding.functions.map(f=>f.function_id),binding.owner_id);
  for(const socket of binding.sockets)requireMotion(new Set(socket.motion_function_ids).size===socket.motion_function_ids.length && socket.motion_function_ids.every(id=>binding.functions.some(f=>f.function_id===id && f.kind!=='state')),'binding',binding.owner_id);
}),legacyBindingShape]);
export type MotionEnvelope = z.infer<typeof envelopeShape>;
export type MotionRegistry = z.infer<typeof registryShape>;
export type MotionRecipe = z.infer<typeof recipeShape>;
export type AssetBinding = z.infer<typeof bindingShape>;
export type Anchor = z.infer<typeof anchorShape>;
export type MaterialSupport = z.infer<typeof materialSupportShape>;
export type MechanicalChannel = z.infer<typeof mechanicalChannelShape>;
export type ChannelValue = Readonly<Omit<MechanicalChannel, 'window_id' | 'start_value' | 'end_value'> & { readonly value: number }>;
export const poseShape = z.strictObject({
  run_id: text, revision: runFields.revision, execution_id: text, recipe_id: text,
  material: materialSupportShape, attachment_id: text, owner_id: text, socket_id: text,
  position_m: vector, contact_m: vector, orientation_xyzw: quaternion,
  progress, phase_complete: z.literal(false), channels: z.array(channelValueShape).readonly(),
}).readonly();
export type MotionPose = z.infer<typeof poseShape>;
