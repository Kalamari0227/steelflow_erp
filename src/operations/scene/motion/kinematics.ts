import { evaluateInternalFeed } from './internalFeed';
import { rejectUnqualifiedBath } from './bathPath';
import { validateRegisteredSockets } from './finishingContinuity';
import type { FeedWitness } from './internalFeed';
import type { Point } from '../worldContractMath';
import { distance } from '../worldContractMath';
import type { MotionContext } from './context';
import { assertNever, equalData, requireMotion, unique } from './errors';
import { FORM_FAMILIES } from './forms';
import { composeTransform, materialPose, multiplyQuaternion, normalizeQuaternion, rotatePoint } from './geometry';
import type { Transform } from './geometry';
import type { Anchor, AssetBinding, ChannelValue, MaterialSupport, MotionEnvelope, MotionRecipe } from './shapes';

export function channelValues(envelope: MotionEnvelope, recipe: MotionRecipe, context: MotionContext): readonly ChannelValue[] {
  const progress = envelope.frozen_progress ?? Math.min(1, Math.max(0, (envelope.effective_sim_ms - envelope.phase_start_ms) / (envelope.phase_end_ms - envelope.phase_start_ms)));
  const binding = context.asset_bindings.find(b => b.owner_id === envelope.anchor.owner_id);
  requireMotion(binding !== undefined, 'binding', envelope.anchor.owner_id);
  requireMotion(recipe.policy_ids.includes(binding.policy_id), 'binding', binding.policy_id);
  const resolved = recipe.functions.filter(f => f.policy_id === binding.policy_id && f.kind !== 'unresolved');
  for (const channel of envelope.channels) requireMotion(resolved.some(f => f.function_id === channel.function_id), 'unknown_function', channel.function_id);
  requireMotion(resolved.length === envelope.channels.length && resolved.every(f => envelope.channels.some(c => c.function_id === f.function_id)), 'unknown_function', envelope.execution_id);
  return Object.freeze(envelope.channels.map(channel => {
    const need = resolved.find(f => f.function_id === channel.function_id);
    const mechanic = binding.functions.find(f => f.function_id === channel.function_id);
    requireMotion(need !== undefined && mechanic !== undefined, 'unknown_function', channel.function_id);
    const window = recipe.windows.find(w => w.id === channel.window_id);
    requireMotion(window !== undefined && need.window_id === channel.window_id, 'binding', channel.function_id);
    requireMotion(need.policy_id === binding.policy_id && need.kind !== 'unresolved', 'unknown_function', channel.function_id);
    requireMotion((need.kind === 'state') === (channel.kind === 'state'), 'binding', channel.function_id);
    requireMotion(channel.node_id === mechanic.node_id && channel.kind === mechanic.kind && equalData(channel.axis, mechanic.axis) && equalData(channel.pivot_m, mechanic.pivot_m), 'binding', channel.function_id);
    requireMotion(Math.min(channel.start_value, channel.end_value) >= mechanic.min_value && Math.max(channel.start_value, channel.end_value) <= mechanic.max_value, 'binding', channel.function_id);
    const local = Math.min(1, Math.max(0, (progress - window.start) / (window.end - window.start)));
    const value = channel.start_value === channel.end_value || local === 0 ? channel.start_value
      : local === 1 ? channel.end_value : (1 - local) * channel.start_value + local * channel.end_value;
    return Object.freeze({ function_id: channel.function_id, node_id: channel.node_id, kind: channel.kind, value, axis: channel.axis, pivot_m: channel.pivot_m });
  }));
}

function applyJoint(base: Transform, channel: ChannelValue): Transform {
  switch (channel.kind) {
    case 'translation': return Object.freeze({ ...base, position_m: Object.freeze([base.position_m[0] + channel.axis[0] * channel.value, base.position_m[1] + channel.axis[1] * channel.value, base.position_m[2] + channel.axis[2] * channel.value] satisfies Point) });
    case 'rotation': {
      const sine = Math.sin(channel.value / 2), cosine = Math.cos(channel.value / 2);
      const rotation = normalizeQuaternion([channel.axis[0] * sine, channel.axis[1] * sine, channel.axis[2] * sine, cosine]);
      const relative: Point = [base.position_m[0] - channel.pivot_m[0], base.position_m[1] - channel.pivot_m[1], base.position_m[2] - channel.pivot_m[2]];
      const turned = rotatePoint(rotation, relative);
      return Object.freeze({ position_m: Object.freeze([turned[0] + channel.pivot_m[0], turned[1] + channel.pivot_m[1], turned[2] + channel.pivot_m[2]] satisfies Point), rotation_xyzw: normalizeQuaternion(multiplyQuaternion(rotation, base.rotation_xyzw)) });
    }
    case 'state': return base;
    default: return assertNever(channel.kind);
  }
}

export function validateAnchor(anchor: Anchor, material: MaterialSupport, context: MotionContext): AssetBinding {
  const binding = context.asset_bindings.find(b => b.owner_id === anchor.owner_id);
  requireMotion(binding !== undefined, 'binding', anchor.owner_id);
  validateRegisteredSockets(binding);
  const socket = binding.sockets.find(s => s.socket_id === anchor.socket_id);
  requireMotion(socket !== undefined, 'unknown_socket', anchor.socket_id);
  const owner = context.world.owners.find(o => o.id === anchor.owner_id);
  const graphSocket = owner?.sockets.find(s => s.id === anchor.socket_id);
  requireMotion(graphSocket !== undefined, 'unknown_socket', anchor.socket_id);
  requireMotion(distance(socket.position_m, graphSocket.pose.position) <= 0.01, 'binding', anchor.socket_id);
  const families: readonly string[] = FORM_FAMILIES[material.form];
  requireMotion(families.includes(socket.family), 'form', material.form);
  requireMotion(equalData(anchor.position_m, socket.position_m) && equalData(anchor.orientation_xyzw, socket.orientation_xyzw), 'binding', anchor.socket_id);
  return binding;
}

export function anchorTransform(anchor: Anchor, context: MotionContext): Transform {
  const owner = context.world.owners.find(o => o.id === anchor.owner_id);
  requireMotion(owner !== undefined, 'unknown_socket', anchor.owner_id);
  const vehicle = context.snapshot.vehicle_states.find(v => v.fleet_id === anchor.owner_id);
  requireMotion(!['vehicle', 'railcar', 'ship'].includes(owner.kind) || vehicle !== undefined, 'execution', owner.id);
  const position = vehicle?.position_m ?? owner.pose.position, yaw = vehicle?.yaw_rad ?? owner.pose.yaw_rad;
  return { position_m: position, rotation_xyzw: [0, Math.sin(yaw / 2), 0, Math.cos(yaw / 2)] };
}

export type SupportEvaluation = { readonly anchor: Anchor; readonly material: MaterialSupport; readonly channels: readonly ChannelValue[] };
export function supportEvaluation(input: SupportEvaluation, context: MotionContext): { readonly pose: Transform; readonly contact: Point; readonly witnesses: readonly FeedWitness[] } {
  const binding = validateAnchor(input.anchor, input.material, context);
  rejectUnqualifiedBath(input.anchor, input.material, binding);
  unique(input.channels.map(c => c.function_id), input.anchor.owner_id);
  const socket = binding.sockets.find(s => s.socket_id === input.anchor.socket_id);
  requireMotion(socket !== undefined && binding !== undefined, 'unknown_socket', input.anchor.socket_id);
  for (const channel of input.channels) {
    const mechanic = binding.functions.find(f => f.function_id === channel.function_id);
    requireMotion(mechanic !== undefined, 'unknown_function', channel.function_id);
    requireMotion(channel.node_id === mechanic.node_id && channel.kind === mechanic.kind && equalData(channel.axis, mechanic.axis) && equalData(channel.pivot_m, mechanic.pivot_m) && channel.value >= mechanic.min_value && channel.value <= mechanic.max_value, 'binding', channel.function_id);
  }
  if('internal_feed' in input.material){const projection=evaluateInternalFeed(input.anchor,input.material,input.channels,binding,anchorTransform(input.anchor,context));return {pose:{position_m:projection.position_m,rotation_xyzw:projection.orientation_xyzw},contact:projection.contact_m,witnesses:projection.witnesses};}
  let local: Transform = { position_m: input.anchor.position_m, rotation_xyzw: normalizeQuaternion(input.anchor.orientation_xyzw) };
  for (const functionId of [...socket.motion_function_ids].reverse()) {
    const channel = input.channels.find(c => c.function_id === functionId);
    requireMotion(channel !== undefined && channel.kind !== 'state', 'binding', functionId);
    local = applyJoint(local, channel);
  }
  const world = composeTransform(anchorTransform(input.anchor, context), local);
  const orientation = normalizeQuaternion(multiplyQuaternion(world.rotation_xyzw, normalizeQuaternion(input.material.orientation_xyzw)));
  const support: Point = [input.material.support_local_mm[0] / 1000, input.material.support_local_mm[1] / 1000, input.material.support_local_mm[2] / 1000];
  return Object.freeze({ pose: materialPose({ position_m: world.position_m, rotation_xyzw: orientation }, support), contact: world.position_m, witnesses: [{part_id:'point:'+input.anchor.socket_id,position_m:world.position_m,normal:[0,1,0]}] });
}
export function checkContact(a: Point, b: Point): void { requireMotion(distance(a, b) <= 0.01 + 1e-12, 'contact', 'handoff'); }
