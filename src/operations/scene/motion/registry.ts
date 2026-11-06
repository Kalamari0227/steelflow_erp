import coverageJson from '../../../../shared/coverage-registry.json';
import policyJson from '../../../../shared/asset-requirements.json';
import type { MotionRecipe, MotionRegistry } from './shapes';
import { PHASE_POLICIES } from './phasePolicies';
import { dimensionRecipes, requirementRecipes } from './applicability';
import { assertNever, requireMotion, unique } from './errors';
import { policyAlternatives } from './effectivePolicy';

const coverage = structuredClone(coverageJson);
const policies = structuredClone(policyJson.policies);
const temporalFamilies = new Set(['raw-sea', 'receiving', 'road', 'rail', 'sea', 'internal', 'quality']);
const sourceIds = new Set(coverage.observed_inventory.compiled_steps.map(step => step.source_step_id));
const additional = coverage.source_requirements.filter(row => !sourceIds.has(row.id.slice(4)));
const temporal = coverage.approved_scope_requirements.filter(row => row.id.split(':').length === 3 && temporalFamilies.has(row.id.split(':')[1] ?? ''));
const expectedSemantics = [...sourceIds].map(id => `source:${id}`).concat(additional.map(row => row.id), temporal.map(row => row.id));

function sameSet(actual: readonly string[], expected: readonly string[], reference: string): void {
  unique(actual, reference);
  requireMotion(actual.length === expected.length && expected.every(id => actual.includes(id)), 'registry_coverage', reference);
}

const travelPhases = new Set(['bulk-voyage', 'travel', 'empty-return', 'shunt', 'block-move', 'last-mile', 'voyage', 'quay-transfer', 'approach', 'move', 'gate-out', 'downstream-feed', 'process-feed', 'customer-delivery']);
const loadPhases = new Set(['load-port', 'unload', 'load', 'wagon-load', 'destination-unload', 'load-survey', 'unload-survey', 'customer-unload']);
function validateWindows(recipe: MotionRecipe): void {
  const manufacturing = recipe.semantic_id.startsWith('source:') || recipe.semantic_id.startsWith('src:');
  const phase = recipe.semantic_id.split(':').at(-1) ?? '';
  const logisticsWindow = travelPhases.has(phase) ? 'travel' : loadPhases.has(phase) ? 'load' : 'hold';
  sameSet(recipe.windows.map(w => w.id), manufacturing ? ['entry', 'work', 'exit'] : [logisticsWindow], `${recipe.id}:windows`);
  requireMotion(recipe.execution_kind === (manufacturing ? 'process' : logisticsWindow === 'travel' ? 'transport' : 'logistics'), 'registry_coverage', `${recipe.id}:kind`);
  requireMotion(recipe.windows[0]?.start === 0 && recipe.windows.at(-1)?.end === 1, 'window', recipe.id);
  for (const [index, window] of recipe.windows.entries()) if (index > 0) requireMotion(recipe.windows[index - 1]?.end === window.start, 'window', recipe.id);
  requireMotion(recipe.functions.every(f => f.window_id === (manufacturing ? 'work' : logisticsWindow)), 'window', recipe.id);
}

export function validateRegistry(registry: MotionRegistry): void {
  unique(registry.recipes.map(r => r.id), 'recipes');
  sameSet(registry.recipes.map(r => r.semantic_id), expectedSemantics, 'semantics');
  const requirements = [...coverage.source_requirements, ...coverage.approved_scope_requirements];
  for (const recipe of registry.recipes) {
    validateWindows(recipe);
    requireMotion(recipe.id === `motion:${recipe.semantic_id}`, 'registry_coverage', recipe.id);
    unique(recipe.requirement_ids, recipe.id);
    requireMotion(recipe.requirement_ids.length > 0 && recipe.requirement_ids.every(id => requirements.some(r => r.id === id)), 'registry_coverage', recipe.id);
    const sourceId = recipe.semantic_id.startsWith('source:') ? recipe.semantic_id.slice(7) : null;
    const steps = coverage.observed_inventory.compiled_steps.filter(step => step.source_step_id === sourceId);
    sameSet(recipe.source_step_ids, sourceId === null ? [] : [sourceId], `${recipe.id}:sources`);
    sameSet(recipe.compiled_step_ids, steps.map(step => step.id), `${recipe.id}:steps`);
    if (steps.length > 0) sameSet(recipe.requirement_ids, [...new Set(steps.flatMap(step => step.requirement_ids))], `${recipe.id}:requirements`);
    else sameSet(recipe.requirement_ids, [recipe.semantic_id], `${recipe.id}:requirements`);
    if (steps.length > 0) {
      const equipmentKinds = new Set(steps.map(s => s.equipment_kind));
      requireMotion(equipmentKinds.size === 1, 'registry_coverage', recipe.id);
      const first = steps[0];
      requireMotion(first !== undefined, 'registry_coverage', recipe.id);
      const alternatives = policyAlternatives('equipment', first.equipment_kind, first.equipment_id);
      const ids = alternatives.map(p => p.id);
      requireMotion(steps.every(step => JSON.stringify(policyAlternatives('equipment', step.equipment_kind, step.equipment_id).map(p => p.id)) === JSON.stringify(ids)), 'registry_coverage', recipe.id);
      sameSet(recipe.policy_ids, recipe.policy_ids.length === 1 ? ids.slice(0, 1) : ids, `${recipe.id}:policies`);
      const expectedFunctions = alternatives.filter(p => recipe.policy_ids.includes(p.id)).flatMap(p => [
        ...p.required_functions.map(f => `${p.id}:${f}:moving`), ...p.state_bound_fixed_functions.map(f => `${p.id}:${f}:state`),
      ]);
      sameSet(recipe.functions.map(f => `${f.policy_id}:${f.function_id}:${f.kind}`), expectedFunctions, `${recipe.id}:functions`);
    } else if (recipe.semantic_id.startsWith('src:')) {
      sameSet(recipe.policy_ids, [], `${recipe.id}:policies`);
      requireMotion(recipe.functions.length === 1 && recipe.functions[0]?.kind === 'unresolved', 'unknown_function', recipe.id);
    } else {
      const expectedPolicies = PHASE_POLICIES[recipe.semantic_id];
      requireMotion(expectedPolicies !== undefined, 'registry_coverage', recipe.id);
      sameSet(recipe.policy_ids, expectedPolicies, `${recipe.id}:policies`);
      const expectedFunctions = expectedPolicies.flatMap(id => {
        const policy = policies.find(p => p.id === id);
        requireMotion(policy !== undefined, 'binding', id);
        return [...policy.required_functions.map(f => `${id}:${f}:moving`), ...policy.state_bound_fixed_functions.map(f => `${id}:${f}:state`)];
      });
      sameSet(recipe.functions.map(f => `${f.policy_id}:${f.function_id}:${f.kind}`), expectedFunctions, `${recipe.id}:functions`);
    }
    const sourceStep = steps[0];
    const requirement = requirements.find(r => r.id === recipe.semantic_id);
    const meaning = sourceStep === undefined ? requirement?.expected_function : `${sourceStep.name} — ${sourceStep.description}`;
    requireMotion(recipe.meaning === meaning, 'registry_coverage', `${recipe.id}:meaning`);
    for (const fn of recipe.functions) {
      requireMotion(fn.semantic_need === (sourceStep === undefined ? (fn.kind === 'unresolved' ? requirement?.expected_function : `${requirement?.expected_function}: ${fn.function_id}`) : `${sourceStep.name}: ${fn.function_id}`), 'registry_coverage', `${recipe.id}:need`);
      const policy = policies.find(p => p.id === fn.policy_id);
      switch (fn.kind) {
        case 'moving': requireMotion(policy !== undefined && policy.required_functions.includes(fn.function_id), 'unknown_function', fn.function_id); break;
        case 'state': requireMotion(policy !== undefined && policy.state_bound_fixed_functions.includes(fn.function_id), 'unknown_function', fn.function_id); break;
        case 'unresolved': requireMotion(fn.policy_id === null && fn.function_id === `need:${recipe.semantic_id}`, 'unknown_function', fn.function_id); break;
        default: assertNever(fn.kind);
      }
    }
  }
  unique(registry.applicability.map(a => `${a.kind}:${a.reference_id}`), 'applicability');
  const expected = {
    requirement: requirements.map(r => r.id), connection: coverage.observed_inventory.compiled_connections.map(c => c.id),
    disposition: coverage.source_step_dispositions.map(d => d.id), receipt: requirements.filter(r => r.id.startsWith('scope:receipt:')).map(r => r.id),
    fleet: requirements.filter(r => r.id.startsWith('scope:fleet:')).map(r => r.id),
  };
  for (const kind of ['requirement', 'connection', 'disposition', 'receipt', 'fleet'] as const) sameSet(registry.applicability.filter(a => a.kind === kind).map(a => a.reference_id), expected[kind], kind);
  for (const row of registry.applicability) {
    unique(row.recipe_ids, row.reference_id);
    requireMotion(row.recipe_ids.length > 0 && row.recipe_ids.every(id => registry.recipes.some(r => r.id === id)), 'registry_coverage', row.reference_id);
    switch (row.kind) {
      case 'connection': sameSet(row.recipe_ids, ['motion:scope:internal:move'], row.reference_id); break;
      case 'receipt': sameSet(row.recipe_ids, temporal.filter(t => t.id.startsWith('scope:receiving:')).map(t => `motion:${t.id}`), row.reference_id); break;
      case 'disposition': {
        const disposition = coverage.source_step_dispositions.find(d => d.id === row.reference_id);
        requireMotion(disposition !== undefined, 'registry_coverage', row.reference_id);
        const category = disposition.category;
        const replacement: Readonly<Record<string, string>> = { receiving: 'motion:scope:receiving:arrival', inspection: 'motion:scope:quality:inspect', packaging: 'motion:scope:quality:package', dispatch: 'motion:scope:road:dispatch' };
        const recipe = category === 'retained' ? `motion:source:${disposition.source_step_id}` : replacement[category];
        requireMotion(recipe !== undefined, 'registry_coverage', row.reference_id);
        sameSet(row.recipe_ids, [recipe], row.reference_id); break;
      }
      case 'requirement': sameSet(row.recipe_ids, requirementRecipes(row.reference_id, expectedSemantics), row.reference_id); break;
      case 'fleet': sameSet(row.recipe_ids, dimensionRecipes(row.reference_id, expectedSemantics), row.reference_id); break;
      default: assertNever(row.kind);
    }
  }
}
