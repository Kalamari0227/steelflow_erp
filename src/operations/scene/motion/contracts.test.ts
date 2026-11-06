import { describe, expect, it } from 'vitest';
import { MotionError, parseMotionEnvelope, parseMotionEnvelopeValue } from './contracts';
import { authorize, boundaryCase, evaluate, fixture, sampled } from './testFixtures';
import type { Fixture } from './testFixtures';

const closePoint = (values: readonly number[]) => values.map(v => expect.closeTo(v, 10));

describe('boundary actual pure evaluator', () => {
  it('moves the support contact with the admitted mechanical channel and preserves full roll', () => {
    // Given
    const input = fixture();
    // When
    const pose = evaluate(input);
    // Then: independent analytic translation 1m; roll turns downward support toward -Z.
    expect(pose.contact_m).toEqual(closePoint([1, 0, 0]));
    expect(pose.position_m).toEqual(closePoint([1, 0, 0.5]));
    expect(pose.orientation_xyzw).toEqual(closePoint([Math.SQRT1_2, 0, 0, Math.SQRT1_2]));
  });
  it.each([[0, 0], [500, 0], [1499, 0.4995], [1500, 0.5], [2499, 0.9995], [2500, 1], [2600, 1]])('clamps confirmed sim time %s to progress %s', (time, progress) => {
    // Given
    const input = sampled(time);
    // When
    const pose = evaluate(input);
    // Then
    expect(pose.progress).toBe(progress);
    expect(pose.phase_complete).toBe(false);
    expect(pose.contact_m[0]).toBeCloseTo(Math.min(2, Math.max(0, (progress - 0.2) / 0.6 * 2)), 10);
  });
  it.each([1, 2, 4])('returns the same confirmed-time pose at speed %s', speed => {
    // Given
    const input = sampled(1500); input.context.snapshot.run.speed = speed;
    // When
    const pose = evaluate(input);
    // Then
    expect(pose.contact_m).toEqual(closePoint([1, 0, 0]));
  });
  it('reaches the same pose with fine stepping and one large jump', () => {
    // Given
    const times = [500, 750, 1000, 1250, 1500];
    // When
    const poses = times.map(time => evaluate(sampled(time)));
    // Then
    expect(poses.at(-1)).toEqual(evaluate(sampled(1500)));
  });
  it.each(['paused', 'stale', 'blocked'])('holds authoritative progress while global elapsed advances in %s', clock_state => {
    // Given
    const input = fixture(); Object.assign(input.envelope, { clock_state, confirmed_sim_ms: 1800 });
    input.context.snapshot.run.elapsed_ms = 1800;
    // When
    const pose = evaluate(authorize(input));
    // Then
    expect(pose.progress).toBe(0.5); expect(pose.contact_m).toEqual(closePoint([1, 0, 0]));
  });
  it('preserves input bytes and freezes all projected material properties', () => {
    // Given
    const input = fixture(), before = JSON.stringify(input);
    // When
    const pose = evaluate(input);
    // Then
    expect(JSON.stringify(input)).toBe(before);
    expect(Object.isFrozen(pose)).toBe(true); expect(Object.isFrozen(pose.material.dimensions)).toBe(true);
    expect(pose.material).toEqual(input.envelope.material);
  });
  it('accepts 1cm support-contact handoff despite changed shape and support offset', () => {
    // Given
    const input = boundaryCase(0.01);
    // When
    const pose = evaluate(input);
    // Then
    expect(pose.position_m).toEqual(closePoint([1, 0, 0.1]));
    expect(pose.material.form).toBe('SLAB'); expect(pose.attachment_id).toBe('custody-stock-coil');
  });
  it('refuses contact discontinuity 0.010001m', () => {
    // Given
    const input = boundaryCase(0.010001);
    // When
    const action = () => evaluate(input);
    // Then
    expect(action).toThrow(expect.objectContaining({ code: 'contact' }));
  });
});

const refusals: readonly { readonly name: string; readonly code: string; readonly edit: (input: Fixture) => void; readonly authorize?: boolean }[] = [
  { name: 'old run', code: 'stale_run', edit: c => { c.envelope.run_id = 'old'; } },
  { name: 'old bundle', code: 'stale_bundle', edit: c => { c.envelope.bundle_hash = 'a'.repeat(64); } },
  { name: 'old revision', code: 'stale_revision', edit: c => { c.envelope.revision = 99; } },
  { name: 'old timestamp', code: 'stale_time', edit: c => { c.envelope.confirmed_sim_ms = 1001; } },
  { name: 'unauthorized support', code: 'unauthorized', edit: c => { c.envelope.material.support_local_mm = [0, 0, 0]; } },
  { name: 'old material version', code: 'material_version', authorize: true, edit: c => { c.envelope.material.material_version_id = 'in-a-v1'; } },
  { name: 'unknown socket', code: 'attachment', authorize: true, edit: c => { c.envelope.anchor.socket_id = 'missing'; } },
  { name: 'unknown recipe', code: 'unknown_recipe', authorize: true, edit: c => { c.envelope.recipe_id = 'missing'; } },
  { name: 'missing process', code: 'execution', authorize: true, edit: c => { c.envelope.execution_id = 'missing'; } },
  { name: 'missing batchIO relation', code: 'execution', edit: c => { c.context.snapshot.process_batches = c.context.snapshot.process_batches.map(b => ({ ...b, process_id: null })); } },
  { name: 'future acquisition', code: 'attachment', edit: c => { for (const a of c.context.snapshot.attachments) if (a.id === c.envelope.attachment_id) a.acquired_at_ms = 1001; } },
  { name: 'future release', code: 'attachment', edit: c => { for (const a of c.context.snapshot.attachments) if (a.id === c.envelope.attachment_id) Object.assign(a, { released_at_ms: 1001 }); } },
  { name: 'wrong socket family', code: 'form', edit: c => { for (const b of c.context.asset_bindings) for (const s of b.sockets) s.family = 'COIL'; } },
  { name: 'unknown channel', code: 'unknown_function', authorize: true, edit: c => { const ch = c.envelope.channels[0]; if (ch) ch.function_id = 'generic_loop'; } },
  { name: 'fake fixed-state motion', code: 'binding', authorize: true, edit: c => { for (const ch of c.envelope.channels) ch.kind = 'state'; } },
  { name: 'missing moving support channel', code: 'unknown_function', authorize: true, edit: c => { c.envelope.channels = []; } },
];
describe('stale_or_missing refusal', () => {
  it.each(refusals)('rejects $name without mutating authority', row => {
    // Given
    const input = fixture(); row.edit(input); if (row.authorize) authorize(input); const before = JSON.stringify(input);
    // When
    const action = () => evaluate(input);
    // Then
    expect(action).toThrow(expect.objectContaining({ code: row.code })); expect(JSON.stringify(input)).toBe(before);
  });
  it.each(['paused', 'stale', 'blocked'])('rejects missing held progress in %s', clock_state => {
    // Given
    const input = fixture(); Object.assign(input.envelope, { clock_state, frozen_progress: null });
    // When
    const action = () => parseMotionEnvelopeValue(input.envelope);
    // Then
    expect(action).toThrow(expect.objectContaining({ code: 'held_progress_required' }));
  });
  it.each([NaN, Infinity, '1000', true, -1, 4193483040000])('rejects malformed timestamp %s', confirmed_sim_ms => {
    // Given
    const input = fixture(); Object.assign(input.envelope, { confirmed_sim_ms });
    // When
    const action = () => parseMotionEnvelopeValue(input.envelope);
    // Then
    expect(action).toThrow(MotionError);
  });
  it('rejects duplicate decoded JSON keys', () => {
    // Given
    const raw = JSON.stringify(fixture().envelope).replace('{', '{"run_id":"duplicate",');
    // When
    const action = () => parseMotionEnvelope(raw);
    // Then
    expect(action).toThrow(expect.objectContaining({ code: 'duplicate' }));
  });
});

// These seeds exercise the public parser, authorization, binding and output validation.
function scalarCase(start: number, end: number, min: number, max: number, progress: number, clock = 'paused', speed = 1): Fixture {
  const input = fixture();
  for (const attachment of input.context.snapshot.attachments) attachment.acquired_at_ms = 0;
  Object.assign(input.envelope, { clock_state: clock, confirmed_sim_ms: 1300, effective_sim_ms: 1300, frozen_progress: clock === 'running' ? null : progress });
  Object.assign(input.context.snapshot.run, { elapsed_ms: 1300, playing: clock === 'running', speed });
  const channel = input.envelope.channels[0], mechanic = input.context.asset_bindings[0]?.functions[0];
  if (!channel || !mechanic) throw new RangeError('Scalar fixture missing');
  Object.assign(channel, { start_value: start, end_value: end }); Object.assign(mechanic, { min_value: min, max_value: max });
  return authorize(input);
}

import scalarSeeds from '../../../../shared/fixtures/motion-held-scalars.json';
import { furnaceCase } from './testFixtures';
describe('exact held scalar and endpoint contract', () => {
  it('accepts actual furnace ranges at held 1.45 and .65 through public evaluation', () => {
    const input = furnaceCase();
    for (const channel of input.envelope.channels) {
      Object.assign(channel, { start_value: channel.function_id === 'furnace_door' ? 1.45 : .65, end_value: channel.function_id === 'furnace_door' ? 1.45 : .65 });
      if (channel.function_id === 'furnace_door') channel.kind = 'rotation';
    }
    for (const binding of input.context.asset_bindings) for (const mechanic of binding.functions) {
      if (mechanic.function_id === 'furnace_door') Object.assign(mechanic, { kind: 'rotation', max_value: 1.45 });
    }
    Object.assign(input.envelope, { frozen_progress: .65 });
    const pose = evaluate(authorize(input));
    expect(pose.channels.map(c => c.value)).toEqual([1.45, .65, .65]);
  });
  it.each(scalarSeeds.held)('preserves $id exactly with all clocks and speeds', row => {
    for (const clock of ['running', 'paused', 'blocked']) for (const speed of [1, 2, 4]) {
      expect(evaluate(scalarCase(row.value, row.value, row.min, row.max, .65, clock, speed)).channels[0]?.value).toBe(row.value);
    }
  });
  it('preserves exact endpoints, adjacent classifications and existing interior arithmetic', () => {
    const results = [];
    for (const row of scalarSeeds.moving) for (const progress of scalarSeeds.progresses) {
      const local = Math.min(1, Math.max(0, (progress - scalarSeeds.window[0]!) / (scalarSeeds.window[1]! - scalarSeeds.window[0]!)));
      const expected = local === 0 ? row.start : local === 1 ? row.end : (1 - local) * row.start + local * row.end;
      const value = evaluate(scalarCase(row.start, row.end, -.75, 1.45, progress)).channels[0]?.value;
      expect(value).toBe(expected); results.push({ id: row.id, progress, local, value });
    }
    console.log('T63_RESULTS=' + JSON.stringify(results));
  });
  it.each(scalarSeeds.invalid)('keeps $id outside strict binding limits', row => {
    expect(() => evaluate(scalarCase(row.start, row.end, -.75, 1.45, .65))).toThrow(expect.objectContaining({ code: 'binding' }));
  });
  it.each([NaN, Infinity, -Infinity])('rejects nonfinite held %s before evaluation', value => {
    expect(() => evaluate(scalarCase(value, value, -.75, 1.45, .65))).toThrow(expect.objectContaining({ code: 'invalid_contract' }));
  });
  it('keeps strict unknown channel fields and authority validation', () => {
    const input = scalarCase(1.45, 1.45, 0, 1.45, .65);
    Object.assign(input.envelope.channels[0]!, { extra_scalar: 1 });
    expect(() => evaluate(authorize(input))).toThrow(expect.objectContaining({ code: 'invalid_contract' }));
    const unauthorized = scalarCase(1.45, 1.45, 0, 1.45, .65); unauthorized.context.authorizations = [];
    expect(() => evaluate(unauthorized)).toThrow(expect.objectContaining({ code: 'unauthorized' }));
  });
});
