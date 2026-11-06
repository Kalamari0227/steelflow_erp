import { guardBathRequest } from './bathPath';
import { validateFeedBoundary } from './internalFeed';
import { qualifiedContact } from './finishingContinuity';
import { anchorTransform } from './kinematics';
import { motionJson } from './json';
import { registryShape, poseShape } from './shapes';
import type { MotionEnvelope, MotionPose, MotionRegistry } from './shapes';
import { MotionError, equalData, requireMotion } from './errors';
import { parseEnvelopeValue, parseMotionRequestValue } from './request';
import type { MotionContext } from './context';
import { validateRegistry } from './registry';
import { validateCustody, validateExecution, validateBoundary } from './custody';
import { channelValues, checkContact, supportEvaluation, validateAnchor } from './kinematics';

export { MotionError } from './errors';
export { parseMotionContext } from './context';
export { bindingsFromAssetManifest } from './assetAdapter';
export type { MotionContext } from './context';
export type { MotionEnvelope, MotionPose, MotionRegistry, AssetBinding, MotionRecipe, MaterialSupport } from './shapes';

export { parseEnvelopeValue as parseMotionEnvelopeValue } from './request';
export function parseMotionEnvelope(raw: string | Uint8Array): MotionEnvelope { return parseEnvelopeValue(motionJson(raw, 'envelope')); }
export function parseMotionRegistryValue(input: unknown): MotionRegistry {
  const result = registryShape.safeParse(input);
  if (!result.success) throw new MotionError('invalid_contract', 'registry');
  validateRegistry(result.data);
  return result.data;
}
export function parseMotionRegistry(raw: string | Uint8Array): MotionRegistry { return parseMotionRegistryValue(motionJson(raw)); }

/** Pure metadata projection. The context authorization is supplied by the trusted server producer. */
export function evaluateMotion(input: MotionEnvelope, source: MotionContext, registry: MotionRegistry): MotionPose {
  const { envelope, context } = parseMotionRequestValue({ envelope: input, context: source });
  guardBathRequest(envelope, context);
  const recipe = registry.recipes.find(r => r.id === envelope.recipe_id);
  requireMotion(recipe !== undefined, 'unknown_recipe', envelope.recipe_id);
  requireMotion(recipe.execution_kind === envelope.execution_kind, 'execution', envelope.execution_id);
  const run = context.snapshot.run;
  requireMotion(envelope.run_id === run.id, 'stale_run', envelope.run_id);
  requireMotion(envelope.bundle_id === run.bundle_id && envelope.bundle_hash === run.bundle_hash, 'stale_bundle', envelope.bundle_id);
  requireMotion(envelope.revision === run.revision, 'stale_revision', envelope.execution_id);
  requireMotion(envelope.confirmed_sim_ms === run.elapsed_ms, 'stale_time', envelope.execution_id);
  requireMotion(context.authorizations.some(a => equalData(a, envelope)), 'unauthorized', envelope.execution_id);
  requireMotion(envelope.frozen_progress !== null || envelope.effective_sim_ms === envelope.confirmed_sim_ms, 'held_progress_required', envelope.execution_id);
  validateCustody(envelope, context);
  validateExecution(envelope, context, recipe);
  const progress = envelope.frozen_progress ?? Math.min(1, Math.max(0, (envelope.effective_sim_ms - envelope.phase_start_ms) / (envelope.phase_end_ms - envelope.phase_start_ms)));
  validateAnchor(envelope.anchor, envelope.material, context);
  const channels = channelValues(envelope, recipe, context);
  const current = supportEvaluation({ anchor: envelope.anchor, material: envelope.material, channels }, context);
  validateBoundary(envelope, context);
  if (envelope.boundary !== null) {
    const previous = supportEvaluation({ anchor: envelope.boundary.previous_anchor, material: envelope.boundary.previous_material, channels: envelope.boundary.previous_channels }, context);
    const binding=context.asset_bindings.find(b=>b.owner_id===envelope.anchor.owner_id);
    requireMotion(binding!==undefined,'binding',envelope.anchor.owner_id);
    const receipt=qualifiedContact({envelope,binding,root:anchorTransform(envelope.anchor,context),previous,current,channels});
    if(receipt===undefined)checkContact(previous.contact, current.contact);
    validateFeedBoundary(previous,current,envelope.boundary.previous_material,envelope.material);
  }
  const result = poseShape.safeParse({ run_id: envelope.run_id, revision: envelope.revision, execution_id: envelope.execution_id, recipe_id: envelope.recipe_id, material: envelope.material, attachment_id: envelope.attachment_id, owner_id: envelope.anchor.owner_id, socket_id: envelope.anchor.socket_id, position_m: current.pose.position_m, contact_m: current.contact, orientation_xyzw: current.pose.rotation_xyzw, progress, phase_complete: false, channels });
  if (!result.success) throw new MotionError('invalid_contract', 'pose');
  return result.data;
}
