import { describe, expect, it } from 'vitest';
import registryJson from '../../../../shared/motion-recipes.json';
import { parseMotionRegistryValue } from './contracts';
import { recipes } from './testFixtures';

const fixture = () => structuredClone(registryJson);
function first<T>(rows: readonly T[]): T { const item = rows[0]; if (item === undefined) throw new RangeError('Fixture missing'); return item; }
describe('independent registry coverage', () => {
  it('preserves each semantic and every application dimension from independent catalogs', () => {
    // Given / When
    const registry = parseMotionRegistryValue(fixture());
    // Then
    expect(registry.recipes).toHaveLength(243);
    expect(registry.recipes.flatMap(r => r.compiled_step_ids)).toHaveLength(348);
    expect(registry.applicability.filter(a => a.kind === 'connection')).toHaveLength(428);
    expect(registry.applicability.filter(a => a.kind === 'disposition')).toHaveLength(187);
    expect(registry.applicability.filter(a => a.kind === 'requirement')).toHaveLength(334);
    expect(registry.applicability.filter(a => a.kind === 'receipt')).toHaveLength(13);
    expect(registry.applicability.filter(a => a.kind === 'fleet')).toHaveLength(20);
    const addedRequirementIds: readonly string[] = [
      'scope:fleet:dump-truck', 'scope:fleet:ship-bulk', 'scope:fleet:overhead-crane',
      'scope:fleet:port-crane', 'scope:fleet:railcar-coil', 'scope:fleet:railcar-bulk',
      'scope:handling:receiving-cradle',
    ];
    const addedFleetIds = addedRequirementIds.slice(0, 6);
    expect(registry.applicability.filter(a => a.kind === 'requirement' && addedRequirementIds.includes(a.reference_id)).map(a => a.reference_id).sort()).toEqual([...addedRequirementIds].sort());
    expect(registry.applicability.filter(a => a.kind === 'fleet' && addedRequirementIds.includes(a.reference_id)).map(a => a.reference_id).sort()).toEqual([...addedFleetIds].sort());
    expect(new Set(registry.applicability.map(a => JSON.stringify([a.kind, a.reference_id]))).size).toBe(registry.applicability.length);
  });
  it.each([
    ['omitted semantic', (r: ReturnType<typeof fixture>) => { r.recipes.pop(); }],
    ['duplicate semantic', (r: ReturnType<typeof fixture>) => { r.recipes.push(structuredClone(first(r.recipes))); }],
    ['omitted compiled step', (r: ReturnType<typeof fixture>) => { first(r.recipes).compiled_step_ids.pop(); }],
    ['omitted entry window', (r: ReturnType<typeof fixture>) => { first(r.recipes).windows.shift(); }],
    ['phase coverage gap', (r: ReturnType<typeof fixture>) => { first(first(r.recipes).windows).start = 0.1; }],
    ['wrong execution kind', (r: ReturnType<typeof fixture>) => { first(r.recipes).execution_kind = 'logistics'; }],
    ['omitted source function', (r: ReturnType<typeof fixture>) => { first(r.recipes).functions.pop(); }],
    ['unknown source function', (r: ReturnType<typeof fixture>) => { first([...first(r.recipes).functions]).function_id = 'fake'; }],
    ['duplicated window', (r: ReturnType<typeof fixture>) => { first(r.recipes).windows.push(structuredClone(first(first(r.recipes).windows))); }],
    ['overlapping window', (r: ReturnType<typeof fixture>) => { first(first(r.recipes).windows).end = 0.5; }],
    ['reversed window', (r: ReturnType<typeof fixture>) => { first(first(r.recipes).windows).end = 0; }],
    ['unknown window', (r: ReturnType<typeof fixture>) => { first([...first(r.recipes).functions]).window_id = 'invented'; }],
    ['miswired known application', (r: ReturnType<typeof fixture>) => { first(r.applicability).recipe_ids = ['motion:source:cs-bf']; }],
    ['omitted application', (r: ReturnType<typeof fixture>) => { r.applicability.pop(); }],
    ['duplicate application', (r: ReturnType<typeof fixture>) => { r.applicability.push(structuredClone(first(r.applicability))); }],
  ])('refuses %s', (_name, edit) => {
    // Given
    const input = fixture(); edit(input);
    // When
    const action = () => parseMotionRegistryValue(input);
    // Then
    expect(action).toThrow();
  });
  it('admits explicit known alternatives for every logistics phase while retaining only missing source needs unresolved', () => {
    // Given / When
    const registry = parseMotionRegistryValue(fixture());
    // Then
    expect(registry.recipes.filter(r => r.semantic_id.startsWith('scope:'))).toHaveLength(52);
    expect(registry.recipes.filter(r => r.semantic_id.startsWith('scope:')).every(r => r.policy_ids.length > 0 && r.functions.every(f => f.kind !== 'unresolved'))).toBe(true);
    expect(registry.recipes.filter(r => r.functions.some(f => f.kind === 'unresolved'))).toHaveLength(41);
  });
  it('keeps unresolved functions pending and fixed thermal work as state', () => {
    // Given / When
    const unresolved = recipes.recipes.find(r => r.id === 'motion:src:plate-ultrasonic');
    const furnace = recipes.recipes.find(r => r.id === 'motion:source:hr-02');
    // Then
    expect(unresolved?.functions[0]?.kind).toBe('unresolved');
    expect(unresolved?.binding_status).toBe('pending_delivery');
    expect(furnace?.functions.find(f => f.function_id === 'thermal_chamber')?.kind).toBe('state');
  });
});
