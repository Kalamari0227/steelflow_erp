import { z } from 'zod';
import requirementsJson from '../../../../shared/asset-requirements.json';
import { requireMotion } from './errors';

const names = z.array(z.string().min(1)).readonly();
const policyShape = z.strictObject({
  id: z.string(), category: z.string(), kind: z.string(), families: names,
  required_functions: names, fixed_functions: names, state_bound_fixed_functions: names,
  required_socket_roles: names, roof_required: z.boolean(), requirement_ids: names,
  relative_fixed_parts: z.array(z.strictObject({ fixed_part_id: z.string(), parent_part_id: z.string() }).readonly()).readonly().default([]),
}).readonly();
const bindingShape = z.strictObject({
  category: z.string(), kind: z.string(), variant: z.string(), policy_group_id: z.string(),
  placement_ids: names, allowed_families: names, stage_ids: names, requirement_ids: names, qa_row_ids: names,
  additional_functions: z.strictObject({ moving: names, state: names }).readonly().optional(),
  extension_policy_id: z.string().optional(),
}).readonly();
const catalogShape = z.object({ policies: z.array(policyShape).readonly(), existing_bindings: z.array(bindingShape).readonly() }).readonly();
export type EffectiveCatalog = z.infer<typeof catalogShape>;
export type EffectivePolicy = z.infer<typeof policyShape>;

/** Only these closed policy/placement projections participate in motion admission. */
export function parseEffectiveCatalog(input: unknown): EffectiveCatalog {
  const catalog = catalogShape.parse(input);
  requireMotion(new Set(catalog.policies.map(p => p.id)).size === catalog.policies.length, 'duplicate', 'policies');
  const bases = catalog.policies.filter(p => !p.id.startsWith('policy:equipment:finishing:'));
  requireMotion(new Set(bases.map(p => `${p.category}:${p.kind}`)).size === bases.length, 'duplicate', 'base_policies');
  const extensions = new Set<string>();
  for (const binding of catalog.existing_bindings) {
    const base = catalog.policies.find(p => p.id === binding.policy_group_id);
    requireMotion(base !== undefined && !binding.policy_group_id.startsWith('policy:equipment:finishing:') && base.category === binding.category && base.kind === binding.kind, 'binding', binding.variant);
    const extra = binding.additional_functions, extensionId = binding.extension_policy_id;
    requireMotion((extra === undefined) === (extensionId === undefined), 'invalid_contract', binding.variant);
    if (extra === undefined || extensionId === undefined) continue;
    const owner = binding.placement_ids[0]?.replace(/^equipment:/, '');
    requireMotion(binding.placement_ids.length === 1 && extensionId === `policy:equipment:finishing:${owner}:v1` && !extensions.has(extensionId), 'binding', binding.variant);
    extensions.add(extensionId);
    const extension = catalog.policies.find(p => p.id === extensionId);
    requireMotion(extension !== undefined, 'binding', extensionId);
    const added = [...extra.moving, ...extra.state];
    requireMotion(new Set(added).size === added.length && added.every(f => !base.required_functions.includes(f) && !base.fixed_functions.includes(f)), 'duplicate', binding.variant);
    const expected = { ...base, id: extensionId, required_functions: [...base.required_functions, ...extra.moving], fixed_functions: [...base.fixed_functions, ...extra.state], state_bound_fixed_functions: [...base.state_bound_fixed_functions, ...extra.state] };
    for (const key of Object.keys(base)) {
      requireMotion(JSON.stringify(Reflect.get(extension, key)) === JSON.stringify(Reflect.get(expected, key)), 'binding', extensionId);
    }
  }
  const registered = catalog.policies.filter(p => p.id.startsWith('policy:equipment:finishing:'));
  requireMotion(registered.length === extensions.size && registered.every(p => extensions.has(p.id)), 'binding', 'extension_policies');
  return catalog;
}

const catalog = parseEffectiveCatalog(structuredClone(requirementsJson));

export function policyAlternatives(category: string, kind: string, ownerId: string, source: EffectiveCatalog = catalog): readonly EffectivePolicy[] {
  const base = source.policies.find(p => p.category === category && p.kind === kind && !p.id.startsWith('policy:equipment:finishing:'));
  requireMotion(base !== undefined, 'binding', ownerId);
  const bindings = source.existing_bindings.filter(b => b.placement_ids.includes(`equipment:${ownerId}`));
  requireMotion(bindings.length <= 1 && bindings.every(b => b.category === category && b.kind === kind && b.policy_group_id === base.id), 'binding', ownerId);
  const extensionId = bindings[0]?.extension_policy_id;
  if (extensionId === undefined) return [base];
  const extension = source.policies.find(p => p.id === extensionId);
  requireMotion(extension !== undefined, 'binding', extensionId);
  return [base, extension];
}

/** undefined is omission; null and user-declared additional functions are never choices. */
export function effectivePolicy(category: string, kind: string, ownerId: string, selectedPolicyId?: string, source: EffectiveCatalog = catalog): EffectivePolicy {
  const alternatives = policyAlternatives(category, kind, ownerId, source);
  const selected = selectedPolicyId === undefined ? alternatives[0]?.id : selectedPolicyId;
  const policy = alternatives.find(p => p.id === selected);
  requireMotion(policy !== undefined, 'binding', selected ?? ownerId);
  return policy;
}

export function policyForId(policyId: string): EffectivePolicy {
  const policy = catalog.policies.find(p => p.id === policyId);
  requireMotion(policy !== undefined, 'binding', policyId);
  return policy;
}
