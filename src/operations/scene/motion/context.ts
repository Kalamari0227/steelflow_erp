import { validateInternalFeed } from './internalFeed';
import { validateBathBinding, validateBathContext } from './bathPath';
import { WorldContractError } from '../worldContractJson';
import { distance } from '../worldContractMath';
import { z } from 'zod';
import { factorySnapshotSchema } from '../../contractsV3';
import { parseFactoryWorld } from '../worldContract';
import { bindingShape, envelopeShape } from './shapes';
import type { AssetBinding, MotionEnvelope } from './shapes';
import { MotionError, requireMotion, unique } from './errors';
import { preflight } from './structure';
import { effectivePolicy, policyForId } from './effectivePolicy';

const inputShape = z.strictObject({ snapshot: z.unknown(), world: z.unknown(), authorizations: z.array(z.unknown()), asset_bindings: z.array(z.unknown()) });
export type MotionContext = {
  readonly snapshot: z.infer<typeof factorySnapshotSchema>;
  readonly world: ReturnType<typeof parseFactoryWorld>;
  readonly authorizations: readonly MotionEnvelope[];
  readonly asset_bindings: readonly AssetBinding[];
};

export function parseMotionContext(input: unknown): MotionContext {
  preflight(input, 'context');
  const raw = inputShape.parse(input);
  const snapshot = factorySnapshotSchema.safeParse(raw.snapshot);
  if (!snapshot.success) throw new MotionError('invalid_contract', 'snapshot');
  let world: ReturnType<typeof parseFactoryWorld>;
  try { world = parseFactoryWorld(raw.world); }
  catch (error) {
    if (error instanceof WorldContractError || error instanceof z.ZodError) throw new MotionError('invalid_contract', 'world');
    throw error;
  }
  const authorizations = raw.authorizations.map(value => {
    const parsed = envelopeShape.safeParse(value);
    if (!parsed.success) throw new MotionError('invalid_contract', 'authorizations');
    return parsed.data;
  });
  const bindings = raw.asset_bindings.map(value => {
    const parsed = bindingShape.safeParse(value);
    if (!parsed.success) throw new MotionError('invalid_contract', 'asset_bindings');
    return parsed.data;
  });
  const context = Object.freeze({ snapshot: snapshot.data, world, authorizations: Object.freeze(authorizations), asset_bindings: Object.freeze(bindings) });
  unique(context.asset_bindings.map(b => b.owner_id), 'asset_bindings');
  unique(context.authorizations.map(a => a.execution_id), 'authorizations');
  for (const binding of context.asset_bindings) {
    if ('bath_paths' in binding) validateBathBinding(binding, context.world);
    if('internal_feeds' in binding)for(const feed of binding.internal_feeds)validateInternalFeed(feed,binding);
    const owner = context.world.owners.find(o => o.id === binding.owner_id);
    requireMotion(owner !== undefined, 'binding', binding.owner_id);
    for (const socket of binding.sockets) {
      const graphSocket = owner.sockets.find(s => s.id === socket.socket_id);
      requireMotion(graphSocket !== undefined, 'unknown_socket', socket.socket_id);
      requireMotion(distance(graphSocket.pose.position, socket.position_m) <= 0.01, 'binding', socket.socket_id);
    }
    const selected = policyForId(binding.policy_id);
    const policy = effectivePolicy(selected.category, selected.kind, binding.owner_id, binding.policy_id);
    const expected = [...policy.required_functions, ...policy.state_bound_fixed_functions];
    requireMotion(binding.functions.length === expected.length && expected.every(id => binding.functions.some(f => f.function_id === id)), 'unknown_function', binding.policy_id);
    for (const fn of binding.functions) requireMotion((fn.kind === 'state') === policy.state_bound_fixed_functions.includes(fn.function_id), 'binding', fn.function_id);
  }
  validateBathContext(context);
  return context;
}
