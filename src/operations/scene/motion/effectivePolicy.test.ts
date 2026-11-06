import { describe, expect, it } from 'vitest';
import policyJson from '../../../../shared/asset-requirements.json';
import registryJson from '../../../../shared/motion-recipes.json';
import seed from '../../../../shared/fixtures/finishing-contract-cases.json';
import { effectivePolicy, parseEffectiveCatalog } from './effectivePolicy';
import { evaluateMotion, parseMotionRegistryValue } from './contracts';
import { parseMotionRequestValue } from './request';

const registry = parseMotionRegistryValue(registryJson);
function request(name: string) {
  const row = seed.requests.find(r => r.name === name);
  if (row === undefined) throw new RangeError('Missing sealed fixture');
  return structuredClone(row.request);
}
function evaluate(raw: unknown, selected = registry) {
  const parsed = parseMotionRequestValue(raw);
  return evaluateMotion(parsed.envelope, parsed.context, selected);
}

describe('explicit finishing policy alternatives', () => {
  for (const [owner, extra] of Object.entries(seed.additional_functions_by_owner)) it(`${owner} keeps base unless explicitly selected`, () => {
    // Given
    const binding = policyJson.existing_bindings.find(b => b.placement_ids.includes(`equipment:${owner}`));
    if (binding === undefined) throw new RangeError('Missing registered owner');
    // When
    const base = effectivePolicy('equipment', binding.kind, owner);
    const extended = effectivePolicy('equipment', binding.kind, owner, `policy:equipment:finishing:${owner}:v1`);
    // Then
    expect(base.id).toBe(binding.policy_group_id);
    expect(extended.required_functions).toEqual([...base.required_functions, ...extra.moving]);
    expect(extended.state_bound_fixed_functions).toEqual([...base.state_bound_fixed_functions, ...extra.state]);
  });

  for (const mode of ['partial', 'null', 'unknown-field', 'duplicate', 'base-duplicate', 'cross-kind', 'forged-extra', 'chain'] as const) it(`rejects catalog ${mode}`, () => {
    // Given
    const raw = structuredClone(policyJson);
    const binding = raw.existing_bindings.find(b => 'extension_policy_id' in b && b.extension_policy_id === 'policy:equipment:finishing:CS-GI-05:v1');
    if (binding === undefined || !('additional_functions' in binding) || binding.additional_functions === undefined) throw new RangeError('Missing extension');
    switch (mode) {
      case 'partial': Reflect.deleteProperty(binding, 'extension_policy_id'); break;
      case 'null': Reflect.set(binding, 'additional_functions', null); break;
      case 'unknown-field': Reflect.set(binding.additional_functions, 'extra', []); break;
      case 'duplicate': binding.additional_functions.state.push('coating_cooling'); break;
      case 'base-duplicate': binding.additional_functions.moving.push('sink_roll'); break;
      case 'cross-kind': binding.extension_policy_id = 'policy:equipment:finishing:CS-GO-07:v1'; break;
      case 'forged-extra': binding.additional_functions.state = ['invented_cooler']; break;
      case 'chain': binding.policy_group_id = 'policy:equipment:finishing:CS-HGI-05:v1'; break;
    }
    // When / Then
    expect(() => parseEffectiveCatalog(raw)).toThrow();
  });
});

for (const row of seed.requests) it(`public parsed request admits ${row.name}`, () => {
  // Given / When
  const pose = evaluate(row.request);
  // Then
  expect(pose.material.form).toBe(row.request.envelope.material.form);
  expect(pose.material.dimensions).toEqual(row.request.envelope.material.dimensions);
  expect(pose.channels.map(c => c.function_id).sort()).toEqual(row.request.envelope.channels.map(c => c.function_id).sort());
});

for (const row of seed.negative_requests) it(`public parsed request rejects ${row.name}`, () => {
  // Given / When / Then
  expect(() => evaluate(row.request)).toThrow(expect.objectContaining({ code: row.error }));
});

for (const fraction of [0, .1, .25, .5, .75, .9, 1]) it(`coated rigid body retains full travel at ${fraction}`, () => {
  // Given
  const raw = request('coated-rigid-feed'), expected = seed.coated_feed_expected;
  const channel = raw.envelope.channels.find(c => c.function_id === expected.driver_function_id);
  if (channel === undefined) throw new RangeError('Missing fixed driver');
  channel.start_value = channel.end_value = expected.driver_min + (expected.driver_max - expected.driver_min) * fraction;
  Reflect.set(raw.context, 'authorizations', [structuredClone(raw.envelope)]);
  // When
  const pose = evaluate(raw);
  // Then
  expect(pose.position_m[0]).toBeCloseTo((expected.start_m[0] ?? NaN) + ((expected.end_m[0] ?? NaN) - (expected.start_m[0] ?? NaN)) * fraction, 10);
  expect(pose.material.dimensions).toEqual(raw.envelope.material.dimensions);
});

it('keeps old base-only recipes readable but rejects an extension with the old recipe', () => {
  // Given
  const raw = structuredClone(registryJson);
  for (const recipe of raw.recipes) {
    recipe.policy_ids = recipe.policy_ids.filter(id => !id.startsWith('policy:equipment:finishing:'));
    Reflect.set(recipe, 'functions', recipe.functions.filter(fn => !fn.policy_id?.startsWith('policy:equipment:finishing:')));
  }
  // When
  const legacy = parseMotionRegistryValue(raw);
  // Then
  expect(evaluate(request('legacy-gi-base'), legacy).owner_id).toBe('CS-GI-05');
  expect(() => evaluate(request('extended-gi-cooling'), legacy)).toThrow('binding:');
});

it('rejects a registry alternative missing an independent extension function', () => {
  // Given
  const raw = structuredClone(registryJson);
  const recipe = raw.recipes.find(r => r.id === 'motion:source:gi-05');
  if (recipe === undefined) throw new RangeError('Missing GI recipe');
  Reflect.set(recipe, 'functions', recipe.functions.filter(f => f.function_id !== 'coating_cooling'));
  // When / Then
  expect(() => parseMotionRegistryValue(raw)).toThrow('registry_coverage:');
});

for (const policy of ['unknown', 'policy:equipment:finishing:CS-HGI-05:v1']) it(`rejects user policy choice ${policy}`, () => {
  // Given
  const raw = request('extended-gi-cooling');
  const binding = raw.context.asset_bindings[0];
  if (binding === undefined) throw new RangeError('Missing binding');
  binding.policy_id = policy;
  // When / Then
  expect(() => evaluate(raw)).toThrow('binding:');
});
