import { describe, expect, it } from 'vitest';
import registryJson from '../../../../shared/motion-recipes.json';
import { parseMotionRegistryValue } from '../motion/contracts';

describe('EAF roof exact canonical contract', () => {
  it.each(['motion:source:sts-hr-02', 'motion:source:sts-plate-02'])('admits %s with the independently opening roof channel', id => {
    // Given
    const input = structuredClone(registryJson), recipe = input.recipes.find(row => row.id === id);
    if (!recipe) throw new RangeError('EAF recipe missing');
    if (!recipe.functions.some(fn => fn.function_id === 'roof_swing')) Object.assign(recipe, { functions: [...recipe.functions, { function_id: 'roof_swing', kind: 'moving', window_id: 'work', policy_id: 'policy:equipment:eaf', semantic_need: '전기로: roof_swing' }] });
    // When
    const registry = parseMotionRegistryValue(input);
    // Then
    expect(registry.recipes.find(row => row.id === id)?.functions.map(fn => fn.function_id)).toEqual(['electrode_lift', 'vessel_tilt', 'roof_swing']);
  });

  it.each(['missing', 'typo', 'other-kind'] as const)('rejects roof %s while retaining exact function sets', mutation => {
    // Given
    const input = structuredClone(registryJson), recipe = input.recipes.find(row => row.id === 'motion:source:sts-hr-02');
    if (!recipe) throw new RangeError('EAF recipe missing');
    if (mutation !== 'other-kind') Object.assign(recipe, { functions: recipe.functions.filter(fn => fn.function_id !== 'roof_swing') });
    if (mutation === 'typo') Object.assign(recipe, { functions: [...recipe.functions, { function_id: 'roof_swng', kind: 'moving', window_id: 'work', policy_id: 'policy:equipment:eaf', semantic_need: 'invalid' }] });
    if (mutation === 'other-kind') {
      const bof = input.recipes.find(row => row.id === 'motion:source:cs-bof');
      if (!bof) throw new RangeError('BOF recipe missing');
      Object.assign(bof, { functions: [...bof.functions, { function_id: 'roof_swing', kind: 'moving', window_id: 'work', policy_id: 'policy:equipment:bof', semantic_need: 'invalid' }] });
    }
    // When / Then
    expect(() => parseMotionRegistryValue(input)).toThrow(expect.objectContaining({ code: 'registry_coverage' }));
  });
});
