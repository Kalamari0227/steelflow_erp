import { afterEach, describe, expect, it, vi } from 'vitest';
import { fixture } from './testFixtures';
import { parseMotionRequest, parseMotionRequestValue } from './request';
import { admitProfile, preflight } from './structure';
import * as errors from './errors';

afterEach(() => vi.restoreAllMocks());
const request = () => { const value = fixture(); return { envelope: value.envelope, context: value.context }; };
const structuralFaults = [
  (v: ReturnType<typeof request>) => Object.assign(v, { unexpected: 'inert instruction' }),
  (v: ReturnType<typeof request>) => Object.assign(v.envelope, { schema_version: true }),
  (v: ReturnType<typeof request>) => Object.assign(v.context, { unexpected: 1 }),
  (v: ReturnType<typeof request>) => Object.assign(v.context.snapshot.run, { revision: true }),
  (v: ReturnType<typeof request>) => Object.assign(v.context.snapshot.run, { bundle_hash: undefined }),
  (v: ReturnType<typeof request>) => Object.assign(v.context.world.owners[0]?.pose ?? {}, { position: [0, 'bad', 0] }),
  (v: ReturnType<typeof request>) => Object.assign(v.context.world, { spatial: { unexpected: [] } }),
  (v: ReturnType<typeof request>) => Object.assign(v.context.authorizations[0] ?? {}, { attachment_id: undefined }),
  (v: ReturnType<typeof request>) => Object.assign(v.context.asset_bindings[0] ?? {}, { unexpected: 1 }),
  (v: ReturnType<typeof request>) => Object.assign(v.context.asset_bindings[0]?.functions[0] ?? {}, { axis: [0, 'bad', 0] }),
];
describe('whole request shape before semantic callbacks', () => {
  it.each(structuralFaults.map((edit, index) => ({ edit, index })))('rejects sibling $index before a callback', ({ edit }) => {
    // Given
    const value = request(); value.envelope.material.orientation_xyzw = [2, 0, 0, 0]; edit(value);
    const callback = vi.spyOn(errors, 'requireMotion');
    // When
    expect(() => parseMotionRequestValue(value)).toThrow(expect.objectContaining({ code: 'invalid_contract' }));
    // Then
    expect(callback).not.toHaveBeenCalled();
  });
  it.each(['reference', 'mass'])('completes actual snapshot %s semantics before binding axis', fault => {
    // Given
    const value = request(), material = value.context.snapshot.materials[0], binding = value.context.asset_bindings[0];
    if (material === undefined || binding?.functions[0] === undefined) throw new RangeError('fixture missing');
    binding.functions[0].axis = [2, 0, 0];
    if (fault === 'reference') material.current_version_id = 'missing-version'; else material.weight_kg += 1;
    preflight(value);
    // When / Then
    expect(() => parseMotionRequestValue(value)).toThrow(expect.objectContaining({ code: 'invalid_contract', reference: 'snapshot' }));
  });
  it.each([{ not: {} }, { $ref: 'https://invalid/schema' }, { $ref: '#/$defs/missing' }, { $ref: '#/$defs/__proto__' }, { $defs: { loop: { $ref: '#/$defs/loop' } } }, { pattern: '.*' }, { additionalProperties: true }])('fails closed on unsupported schema %j', value => {
    // Given / When / Then
    expect(() => admitProfile(value)).toThrow(expect.objectContaining({ code: 'invalid_contract' }));
  });
  it.each([
    ['{"x":1,"x":2} trailing', 'json'], ['{"x":1,"x":2}', 'duplicate'],
    ['{"revision":1,"\\u0072evision":1.0}', 'duplicate'], ['{"x":NaN}', 'json'],
  ])('finishes syntax before duplicate/strict tokens %s', (raw, code) => {
    // Given / When / Then
    expect(() => parseMotionRequest(raw ?? '')).toThrow(expect.objectContaining({ code }));
  });
  it('keeps parsed nested data readonly and caller input unchanged', () => {
    // Given
    const value = request(), before = JSON.stringify(value);
    // When
    const result = parseMotionRequestValue(value);
    // Then
    expect(JSON.stringify(value)).toBe(before);
    expect(Object.isFrozen(result)).toBe(true);
    expect(Object.isFrozen(result.context.authorizations)).toBe(true);
    expect(Object.isFrozen(result.context.snapshot.materials)).toBe(true);
    expect(Object.isFrozen(result.envelope.material.dimensions)).toBe(true);
  });
});

it('checks anchor binding before recipe channel completeness', async () => {
  // Given
  const { evaluateMotion, parseMotionRegistry } = await import('./contracts');
  const { readFileSync } = await import('node:fs');
  const value = request(); value.envelope.anchor.position_m = [7, 0, 0]; value.envelope.channels = [];
  value.context.authorizations = [structuredClone(value.envelope)];
  const parsed = parseMotionRequestValue(value);
  const registry = parseMotionRegistry(new Uint8Array(readFileSync('shared/motion-recipes.json')));
  // When / Then
  expect(() => evaluateMotion(parsed.envelope, parsed.context, registry)).toThrow(expect.objectContaining({ code: 'binding' }));
});


it('rejects decoded prototype-like keys before semantic callbacks', () => {
  // Given
  const value = request(); value.envelope.material.orientation_xyzw = [2, 0, 0, 0];
  const raw = JSON.stringify(value).replace('"snapshot":{', '"snapshot":{"__proto__":{},');
  const callback = vi.spyOn(errors, 'requireMotion');
  // When
  expect(() => parseMotionRequest(raw)).toThrow(expect.objectContaining({ code: 'invalid_contract' }));
  // Then
  expect(callback).not.toHaveBeenCalled();
});
