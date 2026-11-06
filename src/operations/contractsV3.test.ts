import { readFileSync, writeFileSync } from 'node:fs';
import { describe, expect, expectTypeOf, it } from 'vitest';
import { z } from 'zod';
import { factorySnapshotSchema, factoryWorldSchema, factoryMaterialDetailSchema, factoryCommandSchema, factoryDeltaSchema, factoryEventsSchema } from './contractsV3';
import { EventContextSchema, FactoryEventSchema } from './contractsV3Rows';
import { utcSchema } from './contractsV3Core';

const raw: unknown = JSON.parse(readFileSync('shared/fixtures/factory-contract-test-v3/domain.json', 'utf8'));
const fixture = () => factorySnapshotSchema.parse(raw);

describe('schema3 wire boundary', () => {
  it('preserves nullable stock and N:M when parsing real shared fixture', () => {
    // Given / When
    const result = fixture();
    // Then
    expect(result.materials.find(r => r.id === 'stock-coil')?.production_lot_id).toBeNull();
    expect(result.version_edges).toHaveLength(4);
    expect(result.batch_io).toHaveLength(5);
  });
  it.each([
    ['cross_run', { run_id: 'another' }], ['unsafe_integer', { weight_kg: 9007199254740992 }],
    ['unknown_enum', { form: 'FAKE' }], ['numeric_string', { weight_kg: '500' }],
    ['unknown_field', { parent_version_id: 'fake' }], ['current_version', { current_version_id: 'in-a-v1' }],
  ])('rejects malformed material %s', (_name, changes) => {
    // Given
    const state = fixture();
    // When
    const result = factorySnapshotSchema.safeParse({ ...state, materials: state.materials.map((r, i) => i === 0 ? { ...r, ...changes } : r) });
    // Then
    expect(result.success).toBe(false);
  });
  it.each(['2026-10-30T00:00:00', '2026-10-30T09:00:00.000+09:00', '0000-10-30T00:00:00.000Z', '2026-02-30T00:00:00.000Z'])('rejects invalid UTC %s', started_at => {
    // Given
    const state = fixture();
    // When
    const result = factorySnapshotSchema.safeParse({ ...state, run: { ...state.run, started_at } });
    // Then
    expect(result.success).toBe(false);
  });
  it('rejects corrupt N:M mass when one output changes', () => {
    // Given
    const state = fixture();
    // When
    const result = factorySnapshotSchema.safeParse({ ...state, batch_io: state.batch_io.map(r => r.role === 'LOSS' ? { ...r, quantity_kg: 101 } : r) });
    // Then
    expect(result.success).toBe(false);
  });
  const proof = process.env['T5D_PYTHON_PROOF'];
  if (proof) it('parses actual Python output and records nullable stock and N:M', () => {
    // Given
    const worldRaw: unknown = JSON.parse(readFileSync(`${proof}/world.json`, 'utf8'));
    const detailRaw: unknown = JSON.parse(readFileSync(`${proof}/stock-detail.json`, 'utf8'));
    const lineageRaw: unknown = JSON.parse(readFileSync(`${proof}/lineage-detail.json`, 'utf8'));
    // When
    const world = factoryWorldSchema.parse(worldRaw);
    const stock = factoryMaterialDetailSchema.parse(detailRaw);
    const lineage = factoryMaterialDetailSchema.parse(lineageRaw);
    // Then
    expect(stock.order).toBeNull();
    expect(lineage.version_edges).toHaveLength(4);
    writeFileSync(`${proof}/typescript-proof.json`, JSON.stringify({ world, stock, lineage }, null, 2));
  });
});

describe('schema3 consistency guards', () => {
  it.each([
    ['missing_version', (s: ReturnType<typeof fixture>) => ({ ...s, material_versions: s.material_versions.slice(1) })],
    ['duplicate_custody', (s: ReturnType<typeof fixture>) => ({ ...s, attachments: [...s.attachments, { ...s.attachments[0], id: 'duplicate' }] })],
    ['mass_ledger', (s: ReturnType<typeof fixture>) => ({ ...s, mass_ledger: s.mass_ledger.map(r => r.kind === 'OPENING_STOCK' ? { ...r, quantity_kg: r.quantity_kg + 1 } : r) })],
    ['edge_mass', (s: ReturnType<typeof fixture>) => ({ ...s, version_edges: s.version_edges.map(r => ({ ...r, transferred_kg: 999 })) })],
    ['unknown_event', (s: ReturnType<typeof fixture>) => ({ ...s, events: [{ id: 'e', run_id: s.run.id, sequence: 1, event_type: 'FAKE' }] })],
    ['time_overflow', (s: ReturnType<typeof fixture>) => ({ ...s, run: { ...s.run, elapsed_ms: 4193483040000 } })],
  ])('rejects %s on actual fixture', (_name, mutate) => {
    // Given / When
    const result = factorySnapshotSchema.safeParse(mutate(fixture()));
    // Then
    expect(result.success).toBe(false);
  });
  it('freezes rows and nested dimensions when parsed', () => {
    // Given / When
    const state = fixture();
    // Then
    expect(Object.isFrozen(state)).toBe(true);
    expect(Object.isFrozen(state.materials)).toBe(true);
    expect(Object.isFrozen(state.materials[0]?.dimensions)).toBe(true);
  });
});


describe('schema3 commands and deltas', () => {
  it.each([
    { action: 'pause', speed: 2 }, { action: 'speed' }, { action: 'scenario' },
    { action: 'step', steps: 49 }, { action: 'play', speed: true },
    { action: 'reset', profile: 'v3_contract_test' }, { action: 'scenario', scenario: 'DELAY' },
  ])('rejects invalid command payload %j', payload => {
    // Given / When
    const result = factoryCommandSchema.safeParse({ run_id: 'run', command_id: 'command', ...payload });
    // Then
    expect(result.success).toBe(false);
  });
  it('accepts minimal guarded pause when optional fields are omitted', () => {
    // Given / When
    const parsed = factoryCommandSchema.parse({ action: 'pause', run_id: 'run', command_id: 'command' });
    // Then
    expect(parsed.expected_revision).toBeNull();
  });
  it.each(['cross-run', 'reversed'])('rejects invalid delta %s', scenario => {
    // Given
    const { run, schema_version: _schema, ...upserts } = fixture();
    const delta = { run_id: run.id, bundle_hash: run.bundle_hash, from_revision: 0, to_revision: 1, event_sequence_from: 0, event_sequence_to: 0, upserts };
    // When
    const result = factoryDeltaSchema.safeParse(scenario === 'cross-run' ? { ...delta, run_id: 'other' } : { ...delta, from_revision: 2 });
    // Then
    expect(result.success).toBe(false);
  });
});

const parity = z.strictObject({
  contract: z.literal('schema3-decisions-D1-D3'),
  cases: z.array(z.strictObject({
    name: z.string(), kind: z.enum(['context', 'event', 'utc']),
    input: z.unknown(), accepted: z.boolean(), output: z.unknown().optional(),
  })),
}).parse(JSON.parse(readFileSync('shared/fixtures/contract-parity-v3.json', 'utf8')));

const eventInput = {
  run_id: 'r', id: 'e', sequence: 1, event_type: 'RUN_CREATED',
  entity_type: 'run', entity_id: 'r', at_ms: 0,
  occurred_at: '2026-10-30T00:00:00+00:00', source_id: 'source',
} as const;

describe('shared JSON contract decisions', () => {
  it.each(parity.cases)('$name', ({ kind, input, accepted, output }) => {
    // Given / When
    const result = { context: EventContextSchema, event: FactoryEventSchema, utc: utcSchema }[kind].safeParse(input);
    // Then
    expect(result.success).toBe(accepted);
    if (result.success) {
      let expected = output;
      if (kind === 'context') expected = { ...z.record(z.string(), z.unknown()).parse(output), reservation_id: null };
      if (kind === 'event') {
        const event = z.object({ payload: z.record(z.string(), z.unknown()) }).passthrough().parse(output);
        expected = { ...event, payload: { ...event.payload, reservation_id: null } };
      }
      expect(result.data).toEqual(expected);
      expect({ context: EventContextSchema, event: FactoryEventSchema, utc: utcSchema }[kind].parse(result.data)).toEqual(expected);
    }
  });

  it.each([undefined, { material_ids: ['material'], reason: 'kept' }])('freezes independent payload defaults and supplied values: %j', payload => {
    // Given
    const input = payload === undefined ? eventInput : { ...eventInput, payload };
    const original = JSON.stringify(input);
    // When
    const first = FactoryEventSchema.parse(input);
    const second = FactoryEventSchema.parse(input);
    // Then
    expect(Object.isFrozen(first)).toBe(true);
    expect(Object.isFrozen(first.payload)).toBe(true);
    expect(Object.isFrozen(first.payload.material_ids)).toBe(true);
    expect(Reflect.set(first.payload, 'reason', 'changed')).toBe(false);
    expect(Reflect.set(first.payload.material_ids, '0', 'changed')).toBe(false);
    expect(first.payload).not.toBe(second.payload);
    expect(first.payload.material_ids).not.toBe(second.payload.material_ids);
    expect(JSON.stringify(input)).toBe(original);
  });

  it('accepts sparse input types while returning complete readonly output types', () => {
    // Given
    const sparse: z.input<typeof EventContextSchema> = {};
    const event: z.input<typeof FactoryEventSchema> = eventInput;
    // When
    const parsed = FactoryEventSchema.parse(event);
    // Then
    expect(EventContextSchema.parse(sparse).material_ids).toEqual([]);
    expectTypeOf(parsed.payload).toEqualTypeOf<z.output<typeof EventContextSchema>>();
    expectTypeOf(parsed.payload.material_ids).toEqualTypeOf<readonly string[]>();
    expectTypeOf(parsed.payload.reason).toEqualTypeOf<string | null>();
  });

  it('normalizes sparse events through the public event projection', () => {
    // Given / When
    const result = factoryEventsSchema.parse({ schema_version: 3, run_id: 'r', revision: 0, events: [eventInput] });
    // Then
    expect(result.events[0]?.occurred_at).toBe('2026-10-30T00:00:00.000Z');
    expect(result.events[0]?.payload.material_ids).toEqual([]);
    expect(result.events[0]?.payload.reason).toBeNull();
    expect(Object.isFrozen(result.events[0]?.payload)).toBe(true);
  });

  it.each([{ run_id: 'other' }, { sequence: 0 }, { sequence: true }, { event_type: 'FAKE' }])('preserves projection rejection for %j', changes => {
    // Given / When
    const result = factoryEventsSchema.safeParse({ schema_version: 3, run_id: 'r', revision: 0, events: [{ ...eventInput, ...changes }] });
    // Then
    expect(result.success).toBe(false);
  });
});
