import { z } from 'zod';
import coverageJson from '../../../shared/coverage-registry.json';
import requirementsJson from '../../../shared/asset-requirements.json';
import campusJson from '../../../shared/factory-campus.json';
import { parseContractJson } from './worldContractJson';

const coverage = structuredClone(coverageJson);
const requirements = structuredClone(requirementsJson);
const campus = structuredClone(campusJson);
const id = z.string().trim().min(1);
const ids = z.array(id);
const hash = z.string().regex(/^[a-f0-9]{64}$/);
const artifact = z.strictObject({ path: z.string().regex(/^\.omo\/evidence\/(?!.*(?:^|\/)\.\.(?:\/|$))[^\\]+$/), sha256: hash });
const profile = z.enum(['physical_asset', 'spatial_view', 'operational_flow', 'reference_link']);
const targetShape = z.strictObject({ id, target_id: id, profile, requirement_ids: ids.min(1), qa_row_ids: ids.min(1), source_ids: ids.min(1), policy_ids: ids, family_ids: ids });
export type VisualTarget = z.infer<typeof targetShape>;
const stamp = z.strictObject({ run_id: id, bundle_sha256: hash, source_sha256: hash, seed: id, revision: z.number().int().nonnegative(), sim_ms: z.number().int().nonnegative() });
const capture = z.strictObject({ id, stamp, view: z.enum(['overview', 'detail', 'follow', 'cutaway']),
  angle: z.enum(['front', 'side', 'rear', 'context']), state: z.enum(['normal', 'waiting', 'blocked', 'paused', 'resumed']),
  image: artifact, api: artifact, scene_nodes: artifact });
const submission = z.strictObject({ author_id: id, reviewer_id: id, target_id: id,
  source_bundle_sha256: hash, captured_at: z.iso.datetime(), captures: z.array(capture).min(1), video: artifact,
  independent_report: artifact, artifact_manifest: artifact, rubric_ids: ids, verdict: z.literal('awaiting_artifact_and_pixel_verification') });
const review = z.discriminatedUnion('status', [
  z.strictObject({ status: z.literal('pending'), evidence: z.tuple([]) }),
  z.strictObject({ status: z.literal('evidence_submitted'), evidence: z.array(submission).min(1) }),
]);
const shape = z.strictObject({ schema_version: z.literal(1), visual_approval: z.literal('pending_actual_evidence'),
  basis: z.tuple([z.literal('mockup:A'), z.literal('mockup:B'), z.literal('mockup:C'), z.literal('doc:FACTORY_PROCESS_REFERENCES'), z.literal('doc:ASSET_STANDARD')]),
  rows: z.array(targetShape.extend({ review })) });
export type VisualReviewMatrix = z.infer<typeof shape>;
export class VisualReviewError extends Error {
  readonly name = 'VisualReviewError';
  constructor(readonly code: 'schema' | 'coverage' | 'correspondence' | 'evidence', readonly reference: string) { super(`${code}: ${reference}`); }
}
function requireReview(condition: boolean, code: VisualReviewError['code'], reference: string): asserts condition {
  if (!condition) throw new VisualReviewError(code, reference);
}
const unique = (values: readonly string[]): string[] => [...new Set(values)].sort();
const sameIds = (actual: readonly string[], expected: readonly string[]): boolean => actual.length === new Set(actual).size && JSON.stringify(unique(actual)) === JSON.stringify(unique(expected));
const sourceRequirements = [...coverage.source_requirements, ...coverage.approved_scope_requirements];
const sourceByRequirement = new Map(sourceRequirements.map(row => [row.id, row.source_ids]));
const inventory = coverage.observed_inventory;
const linkedRows = [...sourceRequirements.map(row => ({ id: row.id, requirement_ids: [row.id] })), ...coverage.source_step_dispositions,
  ...inventory.products, ...inventory.compiled_steps, ...inventory.compiled_connections, ...inventory.equipment,
  ...inventory.kinds, ...inventory.semantic_variants, ...inventory.stages, ...inventory.source_bindings, ...inventory.paths, ...inventory.cranes, ...inventory.vehicles];
const requirementsByTarget = new Map(linkedRows.map(row => [row.id, row.requirement_ids]));
const physicalTypes = new Set(['equipment', 'semantic_variants', 'kinds', 'cranes', 'vehicles']);
const referenceTypes = new Set(['requirement', 'source_step_disposition', 'source_bindings']);

/** Proposed semantic splits required by ASSET_STANDARD; not registered T4 assets or implemented models. */
export const plannedVisualVariants = Object.freeze(([
  ['fleet', 'truck', 'dump'], ['fleet', 'truck', 'flatbed'],
  ['fleet', 'railcar', 'coil'], ['fleet', 'railcar', 'slab'], ['fleet', 'railcar', 'bulk'],
  ['fleet', 'ship', 'bulk'], ['fleet', 'ship', 'product'],
  ['fleet', 'crane', 'overhead'], ['fleet', 'crane', 'yard'], ['fleet', 'crane', 'port'],
  ['campus', 'berth', 'raw'], ['campus', 'berth', 'product'],
  ['campus', 'hall', 'receiving'], ['campus', 'hall', 'production'], ['campus', 'hall', 'warehouse'],
  ['campus', 'customer-dock', 'road'], ['campus', 'customer-dock', 'rail'], ['campus', 'customer-dock', 'sea'],
] as const).map(variant => Object.freeze(variant)));

function target(value: Omit<VisualTarget, 'source_ids' | 'family_ids'>): VisualTarget {
  const existing = requirements.existing_bindings.find(row => row.variant === value.target_id || row.placement_ids.includes(value.target_id));
  const planned = requirements.planned_bindings.find(row => row.variant === value.target_id || row.placement_ids.includes(value.target_id));
  return { ...value, requirement_ids: unique(value.requirement_ids), qa_row_ids: unique(value.qa_row_ids), policy_ids: unique(value.policy_ids),
    family_ids: unique(existing?.allowed_families ?? (planned ? [planned.family] : requirements.policies.filter(row => value.policy_ids.includes(row.id)).flatMap(row => row.families))),
    source_ids: unique(value.requirement_ids.flatMap(key => {
      const sources = sourceByRequirement.get(key);
      requireReview(sources !== undefined, 'correspondence', `unknown requirement ${key}`);
      return sources;
    })) };
}

/** Current registries are a lower bound. New IDs require explicit matrix registration; no count exemption. */
export function expectedVisualTargets(): VisualTarget[] {
  for (const row of [...inventory.equipment, ...inventory.semantic_variants, ...inventory.kinds, ...inventory.stages, ...inventory.cranes, ...inventory.vehicles]) {
    requireReview(row.qa_row_ids.length > 0 && row.qa_row_ids.every(key => coverage.qa_rows.some(qa => qa.id === key && qa.target_id === row.id)), 'coverage', `unreviewed_variant or placement: ${row.id}`);
  }
  for (const row of inventory.semantic_variants) requireReview(requirements.existing_bindings.some(binding => binding.variant === row.id), 'coverage', `unreviewed_variant policy: ${row.id}`);
  const rows = coverage.qa_rows.map(row => target({ id: `visual:${row.id}`, target_id: row.target_id,
    profile: physicalTypes.has(row.target_type) ? 'physical_asset' : row.target_type === 'stages' ? 'spatial_view' : referenceTypes.has(row.target_type) ? 'reference_link' : 'operational_flow',
    requirement_ids: requirementsByTarget.get(row.target_id) ?? coverage.products.find(product => `approved-product:${product.id}` === row.target_id)?.requirement_ids ?? [],
    qa_row_ids: [row.id], policy_ids: [] }));
  for (const policy of requirements.policies) rows.push(target({ id: `visual:${policy.id}`, target_id: policy.id, profile: 'physical_asset',
    requirement_ids: policy.requirement_ids, qa_row_ids: policy.requirement_ids.map(key => `qa:${key}`), policy_ids: [policy.id] }));
  for (const binding of [...requirements.existing_bindings, ...requirements.planned_bindings]) {
    rows.push(target({ id: `visual:binding:${binding.variant}`, target_id: binding.variant, profile: 'physical_asset',
      requirement_ids: binding.requirement_ids, qa_row_ids: binding.qa_row_ids, policy_ids: [binding.policy_group_id] }));
  }
  for (const binding of requirements.planned_bindings) for (const placement of binding.placement_ids)
    rows.push(target({ id: `visual:placement:${placement}`, target_id: placement, profile: 'physical_asset', requirement_ids: binding.requirement_ids, qa_row_ids: binding.qa_row_ids, policy_ids: [binding.policy_group_id] }));
  for (const hall of campus.halls) rows.push(target({ id: `visual:hall:${hall.id}`, target_id: hall.id, profile: 'spatial_view',
    requirement_ids: ['scope:uniform-fidelity'], qa_row_ids: [`qa:stage:${hall.stage_id}`], policy_ids: ['policy:campus:hall'] }));
  for (const [category, kind, variant] of plannedVisualVariants) {
    const binding = requirements.planned_bindings.find(row => row.category === category && row.kind === kind);
    requireReview(binding !== undefined, 'correspondence', `proposal:${category}:${kind}`);
    rows.push(target({ id: `visual:proposal:${category}:${kind}:${variant}`, target_id: `proposed-variant:${category}:${kind}:${variant}`, profile: 'physical_asset',
      requirement_ids: binding.requirement_ids, qa_row_ids: binding.qa_row_ids, policy_ids: [binding.policy_group_id] }));
  }
  return rows;
}

export const visualRubricIds = Object.freeze(['silhouette', 'mechanism', 'support', 'materials', 'three_angles', 'states', 'single_material', 'same_world', 'labels', 'transport_modes', 'identity_lod', 'accessibility'] as const);
function checkSubmission(row: VisualReviewMatrix['rows'][number]): void {
  switch (row.review.status) {
    case 'pending': return;
    case 'evidence_submitted': break;
    default: return unreachable(row.review);
  }
  requireReview(row.profile !== 'reference_link', 'evidence', `${row.id}: reference linkage uses T2/T40/T43/T44 reports, not asset screenshots`);
  for (const evidence of row.review.evidence) {
    requireReview(evidence.author_id !== evidence.reviewer_id && evidence.target_id === row.target_id, 'evidence', `${row.id}: independent reviewer/target`);
    const captures = evidence.captures;
    const initial = captures[0];
    requireReview(initial !== undefined, 'evidence', row.id);
    requireReview(sameIds(captures.map(item => item.id), unique(captures.map(item => item.id))), 'evidence', `${row.id}: capture ids`);
    for (const item of captures) requireReview(item.stamp.run_id === initial.stamp.run_id && item.stamp.bundle_sha256 === initial.stamp.bundle_sha256 &&
      item.stamp.source_sha256 === initial.stamp.source_sha256 && item.stamp.seed === initial.stamp.seed && item.stamp.bundle_sha256 === evidence.source_bundle_sha256,
    'evidence', `${row.id}: same run/source/bundle/seed`);
    switch (row.profile) {
      case 'physical_asset': {
        requireReview(captures.some(anchor => ['front', 'side', 'rear'].every(angle => captures.some(item => item.angle === angle && item.view === 'detail' && JSON.stringify(item.stamp) === JSON.stringify(anchor.stamp)))), 'evidence', `${row.id}: same-state three angles`);
        requireReview(['normal', 'waiting', 'blocked', 'paused', 'resumed'].every(state => captures.some(item => item.state === state)), 'evidence', `${row.id}: five states`);
        requireReview(sameIds(evidence.rubric_ids, visualRubricIds), 'evidence', `${row.id}: full rubric`);
        break;
      }
      case 'spatial_view': requireReview(captures.some(anchor => ['overview', 'detail', 'cutaway'].every(view => captures.some(item => item.view === view && JSON.stringify(item.stamp) === JSON.stringify(anchor.stamp)))), 'evidence', `${row.id}: same-state spatial views`); break;
      case 'operational_flow': requireReview(captures.some(item => item.view === 'follow'), 'evidence', `${row.id}: follow evidence`); break;
      default: unreachable(row.profile);
    }
  }
}
function unreachable(value: never): never { throw new VisualReviewError('schema', String(value)); }

/** Checks registration and submission structure only. Never certifies artifact bytes, pixels, GLB or motion. */
export function parseVisualReviewMatrix(input: unknown): VisualReviewMatrix {
  const parsed = shape.safeParse(input);
  if (!parsed.success) throw new VisualReviewError('schema', z.prettifyError(parsed.error));
  const matrix = parsed.data;
  const expected = expectedVisualTargets();
  requireReview(sameIds(matrix.rows.map(row => row.id), expected.map(row => row.id)), 'coverage', 'missing, duplicate or unreviewed_variant row');
  const byId = new Map(expected.map(row => [row.id, row]));
  for (const row of matrix.rows) {
    const canonical = byId.get(row.id);
    requireReview(canonical !== undefined && canonical.target_id === row.target_id && canonical.profile === row.profile, 'correspondence', row.id);
    for (const key of ['requirement_ids', 'qa_row_ids', 'source_ids', 'policy_ids', 'family_ids'] as const)
      requireReview(sameIds(row[key], canonical[key]), 'correspondence', `${row.id}:${key}`);
    checkSubmission(row);
  }
  return matrix;
}

export function parseVisualReviewJson(raw: string): VisualReviewMatrix { return parseVisualReviewMatrix(parseContractJson(raw)); }

/** Runtime consumers must register every actual kind/variant/placement before presenting it as covered. */
export function admitVisualInventory(input: unknown, runtimeTargetIds: readonly string[]): void {
  const matrix = parseVisualReviewMatrix(input);
  const registered = new Set(matrix.rows.map(row => row.target_id));
  for (const key of runtimeTargetIds) requireReview(registered.has(key), 'coverage', `unreviewed_variant or placement: ${key}`);
}
