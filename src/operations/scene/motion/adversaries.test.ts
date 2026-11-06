import { describe, expect, it } from 'vitest';
import { authorize, boundaryCase, evaluate, fixture, sampled, furnaceCase, chainCase } from './testFixtures';
import { parseMotionEnvelopeValue } from './contracts';

const closePoint = (values: readonly number[]) => values.map(v => expect.closeTo(v, 10));
describe('mechanical and identity adversaries', () => {
  it('composes parent yaw after child translation in a noncommuting joint chain', () => {
    // Given: parent tap yaw90 and child charge translation +X1 at phase midpoint.
    const input = chainCase();
    // When
    const pose = evaluate(input);
    // Then: parent carries translated contact to -Z; reversing order would wrongly yield +X.
    expect(pose.contact_m).toEqual(closePoint([0, 0, -1]));
    expect(pose.position_m).toEqual(closePoint([0.5, 0, -1]));
    expect(pose.orientation_xyzw).toEqual(closePoint([0.5, 0.5, -0.5, 0.5]));
  });
  it('rotates contact around the declared pivot and retains material roll', () => {
    // Given: rest contact origin, pivot +X1, joint yaw90 at midpoint.
    const input = fixture();
    for (const c of input.envelope.channels) if (c.function_id === 'charge_gate') Object.assign(c, { kind: 'rotation', axis: [0, 1, 0], pivot_m: [1, 0, 0], end_value: Math.PI });
    for (const b of input.context.asset_bindings) for (const f of b.functions) if (f.function_id === 'charge_gate') Object.assign(f, { kind: 'rotation', axis: [0, 1, 0], pivot_m: [1, 0, 0], max_value: Math.PI });
    // When
    const pose = evaluate(authorize(input));
    // Then
    expect(pose.contact_m).toEqual(closePoint([1, 0, 1]));
    expect(pose.position_m).toEqual(closePoint([1.5, 0, 1]));
    expect(pose.orientation_xyzw).toEqual(closePoint([0.5, 0.5, -0.5, 0.5]));
  });
  it('composes root yaw with full internal rotation in the actual evaluator', () => {
    // Given: rotate the whole valid graph 90 degrees around Y.
    const input = fixture();
    const rotate = (p: number[]) => [p[2] ?? 0, p[1] ?? 0, -(p[0] ?? 0)];
    for (const node of input.context.world.nodes) node.position = rotate(node.position);
    for (const segment of input.context.world.segments) segment.points = segment.points.map(rotate);
    for (const owner of input.context.world.owners) { owner.pose.position = rotate(owner.pose.position); owner.pose.yaw_rad += Math.PI / 2; }
    for (const box of [...input.context.world.footprints, ...input.context.world.allowed_interiors]) { box.pose.position = rotate(box.pose.position); box.pose.yaw_rad += Math.PI / 2; }
    // When
    const pose = evaluate(input);
    // Then
    expect(pose.contact_m).toEqual(closePoint([0, 0, -1]));
    expect(pose.position_m).toEqual(closePoint([0.5, 0, -1]));
  });
  it('evaluates thermal work as stationary state rather than fake mechanical motion', () => {
    // Given
    const input = furnaceCase();
    // When
    const pose = evaluate(input);
    // Then
    expect(pose.channels.find(c => c.function_id === 'thermal_chamber')).toMatchObject({ kind: 'state', value: expect.closeTo(0.5, 10) });
    expect(pose.contact_m).toEqual(closePoint([0, 0, 0]));
  });
  it('refuses reclassifying fixed thermal work as rotation', () => {
    // Given
    const input = furnaceCase();
    for (const c of input.envelope.channels) if (c.function_id === 'thermal_chamber') c.kind = 'rotation';
    for (const b of input.context.asset_bindings) for (const f of b.functions) if (f.function_id === 'thermal_chamber') f.kind = 'rotation';
    // When
    const action = () => evaluate(authorize(input));
    // Then
    expect(action).toThrow();
  });
  it('refuses a consumed parent even when requested with its real old version', () => {
    // Given
    const input = fixture(), parent = input.context.snapshot.materials.find(m => m.id === 'in-a');
    if (parent === undefined) throw new RangeError('Consumed fixture missing');
    Object.assign(input.envelope.material, { material_id: parent.id, material_version_id: parent.current_version_id, form: parent.form, dimensions: parent.dimensions });
    // When
    const action = () => evaluate(authorize(input));
    // Then
    expect(action).toThrow(expect.objectContaining({ code: 'consumed_material' }));
  });
  it('refuses duplicate authoritative current custodians', () => {
    // Given
    const input = fixture(), current = input.context.snapshot.attachments[0];
    if (current === undefined) throw new RangeError('Attachment fixture missing');
    input.context.snapshot.attachments.push({ ...current, id: 'duplicate-owner' });
    // When
    const action = () => evaluate(input);
    // Then
    expect(action).toThrow(expect.objectContaining({ code: 'invalid_contract' }));
  });
  it('refuses elapsed-based projection while the actual process is blocked', () => {
    // Given
    const input = sampled(1500); for (const p of input.context.snapshot.processes) p.status = 'BLOCKED';
    // When
    const action = () => evaluate(input);
    // Then
    expect(action).toThrow(expect.objectContaining({ code: 'held_progress_required' }));
  });
  it('refuses omitted authoritative hold when effective time differs from confirmed time', () => {
    // Given
    const input = sampled(1500); input.envelope.effective_sim_ms = 1000;
    // When
    const action = () => evaluate(authorize(input));
    // Then
    expect(action).toThrow(expect.objectContaining({ code: 'held_progress_required' }));
  });
  it('refuses a historical handoff without historical owner transforms', () => {
    // Given
    const input = boundaryCase(0); input.envelope.confirmed_sim_ms = 1100; input.context.snapshot.run.elapsed_ms = 1100;
    // When
    const action = () => evaluate(authorize(input));
    // Then
    expect(action).toThrow(expect.objectContaining({ code: 'boundary' }));
  });
  it('refuses a forged descriptor that relocates a known graph socket', () => {
    // Given
    const input = fixture(); input.envelope.anchor.position_m = [100, 0, 0];
    for (const b of input.context.asset_bindings) for (const s of b.sockets) s.position_m = [100, 0, 0];
    // When
    const action = () => evaluate(authorize(input));
    // Then
    expect(action).toThrow(expect.objectContaining({ code: 'binding' }));
  });
  it.each([
    ['zero phase duration', { phase_end_ms: 0 }], ['reversed phase', { phase_start_ms: 3000 }], ['future effective time', { effective_sim_ms: 1001 }],
    ['unknown field', { wall_delta_ms: 100 }], ['nonunit quaternion', { anchor: { ...fixture().envelope.anchor, orientation_xyzw: [0, 0, 0, 2] } }],
  ])('refuses %s at parse boundary', (_name, changes) => {
    // Given
    const input = { ...fixture().envelope, ...changes };
    // When
    const action = () => parseMotionEnvelopeValue(input);
    // Then
    expect(action).toThrow();
  });
});

describe('actual mobile root authority', () => {
  it('uses snapshot VehicleState rather than static graph root pose', () => {
    // Given
    const input = fixture(1);
    // When
    const pose = evaluate(input);
    // Then
    expect(pose.contact_m).toEqual(closePoint([5, 2, 3]));
    expect(pose.position_m).toEqual(closePoint([5, 2.5, 3]));
  });
  it('refuses a mobile root with no authoritative VehicleState', () => {
    // Given
    const input = fixture(1); input.context.snapshot.vehicle_states = [];
    // When
    const action = () => evaluate(input);
    // Then
    expect(action).toThrow(expect.objectContaining({ code: 'execution' }));
  });
});

it('rejects finite input arithmetic overflow before JSON can emit null coordinates', () => {
  // Given: two legitimate translation channels whose finite sum exceeds number range.
  const input = chainCase();
  for (const c of input.envelope.channels) Object.assign(c, { kind: 'translation', axis: [1, 0, 0], start_value: 1e308, end_value: 1e308 });
  for (const b of input.context.asset_bindings) for (const f of b.functions) Object.assign(f, { kind: 'translation', axis: [1, 0, 0], min_value: 0, max_value: 1e308 });
  // When
  const action = () => evaluate(authorize(input));
  // Then
  expect(action).toThrow(expect.objectContaining({ code: 'invalid_contract' }));
});

describe('explicit logistics policy selection', () => {
  it('evaluates all three admitted crane joints while keeping one authoritative custodian', () => {
    // Given: bridge +X2, trolley +Z3, hoist -Y1 at midpoint.
    const input = fixture(4);
    // When
    const pose = evaluate(input);
    // Then
    expect(pose.contact_m).toEqual(closePoint([2, -1, 3]));
    expect(pose.position_m).toEqual(closePoint([2, -0.5, 3]));
    expect(pose.channels).toHaveLength(3);
    expect(pose.attachment_id).toBe(input.envelope.attachment_id);
    expect(pose.owner_id).toBe(input.envelope.anchor.owner_id);
  });
  it.each(['paused', 'stale', 'blocked'])('holds all crane joints with authoritative progress in %s', clock_state => {
    // Given
    const input = fixture(4); Object.assign(input.envelope, { clock_state, confirmed_sim_ms: 1800 }); input.context.snapshot.run.elapsed_ms = 1800;
    // When
    const pose = evaluate(authorize(input));
    // Then
    expect(pose.contact_m).toEqual(closePoint([2, -1, 3]));
    expect(pose.progress).toBe(0.5);
  });
  it('admits a static warehouse policy without inventing mechanical or state channels', () => {
    // Given
    const input = fixture(3);
    // When
    const pose = evaluate(input);
    // Then
    expect(pose.channels).toEqual([]);
    expect(pose.contact_m).toEqual(closePoint([0, 0, 0]));
    expect(pose.position_m).toEqual(closePoint([0, 0.5, 0]));
  });
  it('refuses a known static warehouse policy for a crane loading phase', () => {
    // Given
    const input = fixture(3); input.envelope.recipe_id = 'motion:scope:internal:load';
    // When
    const action = () => evaluate(authorize(input));
    // Then
    expect(action).toThrow(expect.objectContaining({ code: 'binding' }));
  });
  it('refuses silently omitting the middle crane joint channel', () => {
    // Given
    const input = fixture(4); input.envelope.channels = input.envelope.channels.filter(c => c.function_id !== 'trolley_travel');
    // When
    const action = () => evaluate(authorize(input));
    // Then
    expect(action).toThrow(expect.objectContaining({ code: 'unknown_function' }));
  });
});
