import { readFileSync, writeFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';
import { z } from 'zod';
import { OperationsSnapshotSchema, SimulationCommandSchema, PlanSeedSchema } from './contracts';

function validPayload() {
  return {
    schema_version: 2,
    run: { id: 'run-contract', fixture_version: 'erp-v1', seed: 30, scenario_id: 'NORMAL',
      elapsed_ms: 0, duration_ms: 10000, revision: 0, event_sequence: 0, playing: false, speed: 1,
      epoch_at: '2026-10-30T00:00:00Z', started_at: '2026-10-24T00:00:00Z', plan_revision: 0 },
    orders: [{ run_id: 'run-contract', id: 'ORD-slab', customer_id: 'OPS-CUSTOMER', product_id: 'slab',
      grade: 'SYNTHETIC', width_mm: null, thickness_mm: null, quantity_kg: 20000, due_at: '2026-10-30T00:12:00Z' }],
    work_orders: [{ run_id: 'run-contract', id: 'WO-slab-01', order_id: 'ORD-slab', route_id: 'slab', route_version: 1, planned_kg: 20000, status: 'PLANNED' }],
    lots: [{ run_id: 'run-contract', id: 'LOT-slab-01', work_order_id: 'WO-slab-01', planned_kg: 20000 }],
    materials: [{ run_id: 'run-contract', id: 'MAT-slab-01', lot_id: 'LOT-slab-01', lineage_id: 'MAT-slab-01',
      current_version_id: 'MAT-slab-01:V01', form: 'ORE', weight_kg: 20000, location_id: 'OPS-SOURCE',
      quality_status: 'PENDING', availability_status: 'WIP', active: true }],
    material_versions: [{ run_id: 'run-contract', id: 'MAT-slab-01:V01', material_id: 'MAT-slab-01', ordinal: 1,
      parent_version_id: null, form: 'ORE', weight_kg: 20000, cause_event_id: null }],
    lineage_edges: [], allocations: [], processes: [], transfers: [], inspections: [], shipments: [],
    shipment_materials: [], mass_movements: [], events: [],
    mass_balance: { initial_kg: 20000, additions_kg: 0, active_kg: 20000, loss_kg: 0 }, forecast: [],
  };
}

describe('operations contracts', () => {
  it.each([undefined, 1, 2, 4])('accepts atomic play speed %s', speed => {
    // Given / When
    const result = SimulationCommandSchema.safeParse({ action: 'play', ...(speed === undefined ? {} : { speed }) });
    // Then
    expect(result.success).toBe(true);
  });
  it('parses a noncoil with null dimensions when the run-scoped world is valid', () => {
    // Given
    const payload = validPayload();
    // When
    const parsed = OperationsSnapshotSchema.parse(payload);
    // Then
    expect(parsed.orders[0]?.width_mm).toBeNull();
    expect(parsed.materials[0]?.weight_kg).toBe(20000);
    expect(Object.isFrozen(parsed.materials)).toBe(true);
  });

  it.each([
    ['unknown_quality', 'quality_status', 'GOOD'], ['negative_kg', 'weight_kg', -1],
    ['fractional_kg', 'weight_kg', 1.5], ['boolean_kg', 'weight_kg', true],
    ['numeric_string_kg', 'weight_kg', '20000'], ['cross_run', 'run_id', 'other-run'],
    ['missing_lot', 'lot_id', 'LOT-missing'], ['unknown_form', 'form', 'HR'],
  ])('reject invalid operation payloads: %s', (_name, field, value) => {
    // Given
    const payload = validPayload();
    const changed = { ...payload, materials: payload.materials.map(row => ({ ...row, [String(field)]: value })) };
    // When
    const result = OperationsSnapshotSchema.safeParse(changed);
    // Then
    expect(result.success).toBe(false);
  });

  it.each([
    ['zero_dimension', 'width_mm', 0], ['naive_due', 'due_at', '2026-10-30T00:12:00'],
    ['offset_due', 'due_at', '2026-10-30T09:12:00+09:00'], ['missing_due', 'due_at', null],
    ['unknown_product', 'product_id', 'unknown'],
  ])('reject invalid operation payloads: %s', (_name, field, value) => {
    // Given
    const payload = validPayload();
    // When
    const result = OperationsSnapshotSchema.safeParse({ ...payload, orders: payload.orders.map(row => ({ ...row, [String(field)]: value })) });
    // Then
    expect(result.success).toBe(false);
  });

  it('rejects current-version mass disagreement when both weights are positive', () => {
    // Given
    const payload = validPayload();
    // When
    const result = OperationsSnapshotSchema.safeParse({ ...payload, material_versions: payload.material_versions.map(row => ({ ...row, weight_kg: 19900 })) });
    // Then
    expect(result.success).toBe(false);
  });

  it('allows unresolved due dates only when parsing a plan seed', () => {
    // Given
    const { schema_version: _schema, run, events: _events, mass_balance: _mass, forecast: _forecast, ...rows } = validPayload();
    // When
    const seed = PlanSeedSchema.parse({ ...rows, run_id: run.id, orders: rows.orders.map(row => ({ ...row, due_at: null })) });
    // Then
    expect(seed.orders[0]?.due_at).toBeNull();
  });

  it.each([
    { action: 'step', steps: 0 }, { action: 'step', steps: 49 }, { action: 'speed', speed: 3 },
    { action: 'select', product_id: 'ga' }, { action: 'play', journey_clock: 5 },
    { action: 'pause', steps: 2 }, { action: 'speed' },
  ])('rejects a command when its payload is invalid: %j', command => {
    // Given / When
    const result = SimulationCommandSchema.safeParse(command);
    // Then
    expect(result.success).toBe(false);
  });

  it('accepts a legacy bodyless-equivalent step when metadata is omitted', () => {
    // Given / When
    const command = SimulationCommandSchema.parse({ action: 'step' });
    // Then
    expect(command.run_id).toBeNull();
    expect(command.steps).toBeNull();
  });

  const exportedPath = process.env['T01_PAYLOADS'];
  if (exportedPath) {
    it('parses the exact exported Python payloads through the real Zod boundary', () => {
      // Given
      const payloads = z.object({ valid: z.unknown(), invalid: z.record(z.string(), z.unknown()) }).parse(JSON.parse(readFileSync(exportedPath, 'utf8')));
      // When
      const valid = OperationsSnapshotSchema.safeParse(payloads.valid);
      const invalid = Object.fromEntries(Object.entries(payloads.invalid).map(([name, payload]) => {
        const result = OperationsSnapshotSchema.safeParse(payload);
        return [name, { accepted: result.success, issues: result.success ? [] : result.error.issues }];
      }));
      const outputPath = process.env['T01_TS_RESULT'];
      if (outputPath) writeFileSync(outputPath, JSON.stringify({ valid: { accepted: valid.success, parsed: valid.success ? valid.data : valid.error.issues }, invalid }, null, 2));
      // Then
      expect(valid.success).toBe(true);
      expect(Object.values(invalid).every(result => !result.accepted)).toBe(true);
    });
  }
});
