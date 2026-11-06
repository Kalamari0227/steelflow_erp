import coverageJson from '../../../../shared/coverage-registry.json';
import { PHASE_POLICIES } from './phasePolicies';
import { requireMotion } from './errors';

const coverage = structuredClone(coverageJson);
const steps = coverage.observed_inventory.compiled_steps;
const families: Readonly<Record<string, string>> = {
  truck: 'road', 'slab-carrier': 'internal', 'coil-carrier': 'internal', forklift: 'internal', torpedo: 'internal',
  'ladle-car': 'internal', locomotive: 'rail', railcar: 'rail', ship: 'sea', crane: 'internal', unloader: 'raw-sea',
  stacker: 'raw-sea', reclaimer: 'raw-sea', conveyor: 'internal',
  "dump-truck": "road",
  "ship-bulk": "sea",
  "overhead-crane": "internal",
  "port-crane": "internal",
  "railcar-coil": "rail",
  "railcar-bulk": "rail",
};
const scopePrefixes: Readonly<Record<string, readonly string[]>> = {
  'scope:receiving': ['receiving:'], 'scope:dispatch': ['road:', 'rail:', 'sea:'], 'scope:ti-purchased-ingot': ['receiving:'],
  'scope:intermediate-sale': ['receiving:downstream-feed', 'quality:inspect', 'quality:package', 'road:dispatch', 'rail:consist', 'sea:quay-transfer'],
  "scope:handling:receiving-cradle": ["internal:load", "internal:unload"],
};
const assetScopes: Readonly<Record<string, readonly string[]>> = {
  stock: ['quality:store', 'receiving:store'], port: ['sea:quay-transfer', 'sea:berth-wait', 'sea:load-survey'],
  ship: ['sea:voyage', 'sea:unload-survey', 'sea:load-survey', 'raw-sea:bulk-voyage'],
  delivery: ['road:customer-unload', 'road:customer-accept', 'rail:customer-delivery', 'sea:customer-delivery'],
};
export function dimensionRecipes(id: string, semantics: readonly string[]): readonly string[] {
  const family = id.startsWith('scope:receipt:') ? 'receiving' : families[id.slice('scope:fleet:'.length)];
  requireMotion(family !== undefined, 'registry_coverage', id);
  return semantics.filter(s => s.startsWith(`scope:${family}:`)).map(s => `motion:${s}`);
}

/** Derive applicability from the independent coverage registry, never recipe output. */
export function requirementRecipes(id: string, semantics: readonly string[]): readonly string[] {
  const requirement = [...coverage.source_requirements, ...coverage.approved_scope_requirements].find(r => r.id === id);
  requireMotion(requirement !== undefined, 'registry_coverage', id);
  const selected = new Set<string>();
  const entities: readonly string[] = requirement.implementation_mapping.observed_entity_ids;
  for (const step of steps) {
    const source: string[] = step.requirement_ids;
    if (source.includes(id) || entities.includes(step.id)) selected.add(`motion:source:${step.source_step_id}`);
    if (id.startsWith('scope:product:') && step.product_id === id.slice('scope:product:'.length)) selected.add(`motion:source:${step.source_step_id}`);
    if (id.startsWith('scope:asset-family:') && step.equipment_kind === id.slice('scope:asset-family:'.length)) selected.add(`motion:source:${step.source_step_id}`);
  }
  if (id.startsWith('scope:asset-family:')) {
    const policyId = `policy:equipment:${id.slice('scope:asset-family:'.length)}`;
    for (const [semantic, alternatives] of Object.entries(PHASE_POLICIES)) if (alternatives.includes(policyId)) selected.add(`motion:${semantic}`);
  }
  if (semantics.includes(id)) selected.add(`motion:${id}`);
  for (const scope of assetScopes[id.slice('scope:asset-family:'.length)] ?? []) if (id.startsWith('scope:asset-family:')) selected.add(`motion:scope:${scope}`);
  for (const prefix of scopePrefixes[id] ?? []) for (const semantic of semantics) if (semantic.startsWith(`scope:${prefix}`)) selected.add(`motion:${semantic}`);
  if (id === 'scope:uniform-fidelity' || id === 'scope:material-ledger') for (const semantic of semantics) selected.add(`motion:${semantic}`);
  if (id.startsWith('scope:receipt:') || id.startsWith('scope:fleet:')) for (const recipe of dimensionRecipes(id, semantics)) selected.add(recipe);
  requireMotion(selected.size > 0, 'registry_coverage', id);
  return [...selected];
}
