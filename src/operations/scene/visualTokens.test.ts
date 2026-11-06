// @vitest-environment node
import { readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';
import matrix from '../../../shared/visual-review-matrix.json';
import requirements from '../../../shared/asset-requirements.json';
import coverage from '../../../shared/coverage-registry.json';
import { parseVisualTokens, visualTokens } from './visualTokens';
import { admitVisualInventory, expectedVisualTargets, parseVisualReviewJson, parseVisualReviewMatrix, plannedVisualVariants, visualRubricIds, VisualReviewError } from './visualReview';

const copy = () => structuredClone(matrix);
const first = <T,>(rows: readonly T[]): T => {
  const row = rows[0];
  if (row === undefined) throw new Error('fixture requires one row');
  return row;
};

describe('complete visual contract', () => {
  it('complete parses typed tokens and an honest pending matrix', () => {
    expect(parseVisualTokens(visualTokens)).toEqual(visualTokens);
    const result = parseVisualReviewMatrix(matrix);
    expect(result.rows.map(row => row.id).sort()).toEqual(expectedVisualTargets().map(row => row.id).sort());
    expect(result.rows.every(row => row.review.status === 'pending')).toBe(true);
    expect(result.visual_approval).toBe('pending_actual_evidence');
  });
  it('complete covers every current kind, variant, placement, QA target and explicit planned binding', () => {
    const ids = new Set(parseVisualReviewMatrix(matrix).rows.map(row => row.target_id));
    for (const row of coverage.qa_rows) expect(ids.has(row.target_id), row.id).toBe(true);
    for (const row of [...requirements.existing_bindings, ...requirements.planned_bindings]) {
      expect(ids.has(row.variant)).toBe(true);
      for (const id of row.placement_ids) expect(ids.has(id), id).toBe(true);
    }
    for (const row of requirements.policies) expect(ids.has(row.id), row.id).toBe(true);
  });
  it('complete keeps selection separate from heat and camera presentation separate from physical identity', () => {
    expect(visualTokens.palette.selectionAmber).not.toBe(visualTokens.palette.hotMetal);
    expect(visualTokens.motion.clock).toBe('server_sim_ms');
    expect(visualTokens.world.physicalScale).toBe(1);
    expect(visualTokens.camera.pan.buttons).toEqual(['north', 'south', 'east', 'west']);
    expect(visualTokens.labels.equipmentOverlapRatio).toBe(0);
    expect(visualTokens.lod.preserve).toContain('attachment');
  });
});

describe('unreviewed_variant admission', () => {
  it('unreviewed_variant rejects missing registered variant without mutating input', () => {
    const input = copy();
    input.rows = input.rows.filter(row => row.target_id !== first(requirements.existing_bindings).variant);
    const before = JSON.stringify(input);
    expect(() => parseVisualReviewMatrix(input)).toThrow(/coverage/);
    expect(JSON.stringify(input)).toBe(before);
  });
  it('unreviewed_variant rejects unknown new variant even with copied QA and source IDs', () => {
    const input = copy();
    input.rows.push({ ...first(input.rows), id: 'visual:new', target_id: 'variant:unreviewed' });
    expect(() => parseVisualReviewMatrix(input)).toThrow(/coverage/);
  });
  it('unreviewed_variant rejects replacement that keeps the old denominator', () => {
    const input = copy();
    first(input.rows).target_id = 'variant:unreviewed';
    expect(() => parseVisualReviewMatrix(input)).toThrow(/correspondence/);
  });
  it('unreviewed_variant rejects new runtime placements outside the registered lower bound', () => {
    const parsed = parseVisualReviewMatrix(matrix);
    expect(() => admitVisualInventory(parsed, ['equipment:UNREGISTERED-NEW'])).toThrow(/unreviewed_variant/);
    expect(() => admitVisualInventory(parsed, ['equipment:CHARGE-A'])).not.toThrow();
  });
  it('unreviewed_variant rejects a forged registration passed directly to runtime admission', () => {
    expect(() => admitVisualInventory({ rows: [{ target_id: 'equipment:UNREGISTERED-NEW' }] }, ['equipment:UNREGISTERED-NEW'])).toThrow(VisualReviewError);
  });
});

describe('adversarial boundaries', () => {
  it('rejects duplicate rows', () => {
    const input = copy(); input.rows.push(first(input.rows));
    expect(() => parseVisualReviewMatrix(input)).toThrow(/coverage/);
  });
  it('rejects missing new fleet placement', () => {
    const input = copy(); input.rows = input.rows.filter(row => row.target_id !== first(requirements.planned_bindings).placement_ids[0]);
    expect(() => parseVisualReviewMatrix(input)).toThrow(/coverage/);
  });
  it('rejects a fabricated source reference', () => {
    const input = copy(); first(input.rows).source_ids = ['fabricated:source'];
    expect(() => parseVisualReviewMatrix(input)).toThrow(/correspondence/);
  });
  it('rejects false visual PASS from metadata or reference images', () => {
    const input = copy(); Object.assign(first(input.rows).review, { status: 'complete', evidence: ['design/mockups/2026-10-25/a-miniature-overview.png'] });
    expect(() => parseVisualReviewMatrix(input)).toThrow(VisualReviewError);
  });
  it('rejects missing mechanical/material token and invalid material ranges', () => {
    expect(() => parseVisualTokens({ ...visualTokens, materials: {} })).toThrow();
    expect(() => parseVisualTokens({ ...visualTokens, materials: { ...visualTokens.materials, structuralSteel: { roughness: -1, metalness: 2 } } })).toThrow();
  });
  it('rejects fabricated completed top-level summary', () => {
    expect(() => parseVisualReviewMatrix({ ...copy(), visual_approval: 'pass' })).toThrow(VisualReviewError);
  });
  it('rejects unknown token overrides and preserves source file bytes', () => {
    expect(() => parseVisualTokens({ ...visualTokens, clock: 'wall' })).toThrow();
    expect(JSON.parse(readFileSync('shared/visual-review-matrix.json', 'utf8'))).toEqual(matrix);
  });
  it('rejects duplicate decoded JSON keys', () => {
    expect(() => parseVisualReviewJson(JSON.stringify(matrix).replace('{', '{"schema_version":1,'))).toThrow(/duplicate key/);
  });
  it('rejects family reassignment despite unchanged kind', () => {
    const input = copy();
    const row = first(input.rows.filter(item => item.target_id === 'variant:charge:CHARGE-A'));
    row.family_ids = ['finishing'];
    expect(() => parseVisualReviewMatrix(input)).toThrow(/family_ids/);
  });
});

// Synthetic submission metadata exercises the boundary; these are deliberately not actual artifact claims.
function submissionFixture() {
  const row = first(matrix.rows.filter(item => item.profile === 'physical_asset'));
  const artifact = (name: string) => ({ path: `.omo/evidence/unit-only/${name}`, sha256: 'a'.repeat(64) });
  const stamp = { run_id: 'unit-run', bundle_sha256: 'b'.repeat(64), source_sha256: 'c'.repeat(64), seed: 'test-seed', revision: 1, sim_ms: 0 };
  const captures = ['front', 'side', 'rear'].map((angle, index) => ({ id: `angle-${index}`, stamp, view: 'detail', angle, state: 'normal', image: artifact(`${index}.png`), api: artifact(`${index}-api.json`), scene_nodes: artifact(`${index}-nodes.json`) }));
  for (const [index, state] of ['waiting', 'blocked', 'paused', 'resumed'].entries()) captures.push({ ...first(captures), id: state, state, stamp: { ...stamp, revision: index + 2, sim_ms: index * 10 } });
  const submission = { author_id: 'unit-author', reviewer_id: 'unit-reviewer', target_id: row.target_id, source_bundle_sha256: stamp.bundle_sha256,
    captured_at: '2026-10-25T00:00:00Z', captures, video: artifact('cycle.webm'), independent_report: artifact('review.json'), artifact_manifest: artifact('manifest.json'),
    rubric_ids: [...visualRubricIds], verdict: 'awaiting_artifact_and_pixel_verification' };
  return { matrix: { ...copy(), rows: copy().rows.map(item => item.id === row.id ? { ...item, review: { status: 'evidence_submitted', evidence: [submission] } } : item) }, submission };
}

describe('evidence submission is never visual approval', () => {
  it('complete accepts structurally complete submissions while explicitly withholding visual approval', () => {
    const fixture = submissionFixture();
    const parsed = parseVisualReviewMatrix(fixture.matrix);
    expect(parsed.visual_approval).toBe('pending_actual_evidence');
    expect(parsed.rows.some(row => row.review.status === 'evidence_submitted')).toBe(true);
  });
  it.each(['self-review', 'wrong-target', 'cross-run', 'missing-angle', 'missing-state', 'wrong-hash', 'reference-image', 'different-time', 'missing-rubric'])('rejects submitted %s', fault => {
    const { matrix: input, submission } = submissionFixture();
    const capture = first(submission.captures);
    if (fault === 'self-review') submission.reviewer_id = submission.author_id;
    if (fault === 'wrong-target') submission.target_id = 'other';
    if (fault === 'cross-run') capture.stamp = { ...capture.stamp, run_id: 'other-run' };
    if (fault === 'missing-angle') submission.captures = submission.captures.filter(item => item.angle !== 'rear');
    if (fault === 'missing-state') submission.captures = submission.captures.filter(item => item.state !== 'paused');
    if (fault === 'wrong-hash') capture.image.sha256 = 'invalid';
    if (fault === 'reference-image') capture.image.path = 'design/mockups/2026-10-25/a-miniature-overview.png';
    if (fault === 'different-time') capture.stamp = { ...capture.stamp, sim_ms: 999 };
    if (fault === 'missing-rubric') submission.rubric_ids.pop();
    expect(() => parseVisualReviewMatrix(input)).toThrow(VisualReviewError);
  });
});

describe('authority_mutation regressions', () => {
  it.each(['#B86B00', '#b86B00'])('rejects RGB-identical heat/selection despite hex case %s', hotColor => {
    const input = { ...visualTokens, palette: { ...visualTokens.palette, hotMetal: hotColor }, heat: { ...visualTokens.heat, color: hotColor } };
    expect(() => parseVisualTokens(input)).toThrow(/separate consistent semantics/);
  });
  it('accepts equivalent case spellings within each distinct semantic color', () => {
    const input = { ...visualTokens, selection: { ...visualTokens.selection, color: '#B86B00' }, heat: { ...visualTokens.heat, color: '#FF581C' } };
    expect(() => parseVisualTokens(input)).not.toThrow();
  });
  it('cannot remove support from public rubric authority to admit incomplete evidence', () => {
    const { matrix: input, submission } = submissionFixture();
    submission.rubric_ids = submission.rubric_ids.filter(key => key !== 'support');
    expect(() => Array.prototype.splice.call(visualRubricIds, visualRubricIds.indexOf('support'), 1)).toThrow(TypeError);
    expect(Reflect.set(visualRubricIds, 'length', 0)).toBe(false);
    expect(() => parseVisualReviewMatrix(input)).toThrow(/full rubric/);
  });
  it('cannot remove or rewrite proposed variants, including every nested tuple', () => {
    const before = JSON.stringify(expectedVisualTargets());
    const input = copy(); input.rows = input.rows.filter(row => row.id !== 'visual:proposal:campus:customer-dock:sea');
    expect(() => Array.prototype.pop.call(plannedVisualVariants)).toThrow(TypeError);
    for (const tuple of plannedVisualVariants) {
      expect(Reflect.set(tuple, '2', 'unreviewed')).toBe(false);
      expect(Reflect.deleteProperty(tuple, '0')).toBe(false);
    }
    expect(JSON.stringify(expectedVisualTargets())).toBe(before);
    expect(() => parseVisualReviewMatrix(input)).toThrow(/coverage/);
  });
  it('keeps private catalog snapshots isolated from imported and returned data mutations', () => {
    const before = JSON.stringify(expectedVisualTargets());
    const qa = coverage.qa_rows.pop(); const policy = requirements.policies.pop();
    try {
      first(expectedVisualTargets()).source_ids.push('forged:source');
      expect(JSON.stringify(expectedVisualTargets())).toBe(before);
      expect(() => parseVisualReviewMatrix(matrix)).not.toThrow();
      const returned = parseVisualReviewMatrix(matrix);
      first(returned.rows).source_ids = ['forged:source'];
      expect(() => admitVisualInventory(returned, ['equipment:CHARGE-A'])).toThrow(/correspondence/);
    } finally {
      if (qa) coverage.qa_rows.push(qa);
      if (policy) requirements.policies.push(policy);
    }
  });
});
