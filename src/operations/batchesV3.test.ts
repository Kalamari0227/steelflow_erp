import { readFileSync, writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { describe, expect, it } from 'vitest';
import { z } from 'zod';
import {
  factoryMaterialDetailSchema, factoryProductionSchema, factoryWorldSchema,
} from './contractsV3';
import type { FactoryWorld } from './contractsV3';
import { BatchIOSchema, VersionEdgeSchema } from './contractsV3Rows';

const proof = process.env['T10_HTTP_PROOF'];

function proofFile(name: string): string {
  if (proof === undefined) throw new Error('T10_HTTP_PROOF is required for actual HTTP evidence');
  return join(proof, name);
}

function parseWorld(): FactoryWorld {
  const raw: unknown = JSON.parse(readFileSync(proofFile('world.json'), 'utf8'));
  return factoryWorldSchema.parse(raw);
}

function requiredId(id: string | null): string {
  if (id === null) throw new Error('Physical IO must have a version');
  return id;
}

function integerEdgeOracle(world: FactoryWorld): readonly string[] {
  const sources = world.batch_io.filter(row => row.role === 'INPUT' || row.role === 'STOCK_ADDITION')
    .map(row => ({ id: requiredId(row.material_version_id), kg: BigInt(row.quantity_kg), physical: true }))
    .sort((a, b) => a.id.localeCompare(b.id));
  sources.push(...world.batch_io.filter(row => row.role === 'EXTERNAL_ADDITION')
    .map(row => ({ id: requiredId(row.source_id), kg: BigInt(row.quantity_kg), physical: false }))
    .sort((a, b) => a.id.localeCompare(b.id)));
  const materials = new Map(world.material_versions.map(row => [row.id, row.material_id]));
  const sinks = world.batch_io.filter(row => row.role === 'OUTPUT')
    .map(row => ({ id: materials.get(requiredId(row.material_version_id)) ?? '', version: row.material_version_id, kg: BigInt(row.quantity_kg) }))
    .sort((a, b) => a.id.localeCompare(b.id));
  for (const role of ['BYPRODUCT', 'LOSS']) {
    sinks.push(...world.batch_io.filter(row => row.role === role)
      .map(row => ({ id: requiredId(row.source_id), version: null, kg: BigInt(row.quantity_kg) }))
      .sort((a, b) => a.id.localeCompare(b.id)));
  }
  const remaining = sources.map(row => row.kg);
  const edges: string[] = [];
  for (const sink of sinks) {
    const total = remaining.reduce((sum, kg) => sum + kg, 0n);
    const shares = remaining.map(kg => sink.kg * kg / total);
    let remainder = sink.kg - shares.reduce((sum, kg) => sum + kg, 0n);
    remaining.forEach((kg, index) => {
      const share = shares[index];
      if (share === undefined) throw new Error('Oracle share missing');
      if (remainder > 0n && share < kg) {
        shares[index] = share + 1n;
        remainder -= 1n;
      }
    });
    expect(remainder).toBe(0n);
    sources.forEach((source, index) => {
      const share = shares[index];
      const available = remaining[index];
      if (share === undefined || available === undefined) throw new Error('Oracle source missing');
      remaining[index] = available - share;
      if (source.physical && sink.version !== null && share > 0n) edges.push(`${source.id}|${sink.version}|${share}`);
    });
  }
  expect(remaining).toEqual(sources.map(() => 0n));
  return edges.sort();
}

describe.skipIf(proof === undefined)('T10 actual SQLite -> HTTP -> TypeScript batch contract', () => {
  it('parses three outputs and two orders with exact mass and admitted port custody', () => {
    // Given / When: these bytes came from the owned real loopback server.
    const world = parseWorld();
    const detailRaw: unknown = JSON.parse(readFileSync(proofFile('material-A.json'), 'utf8'));
    const productionRaw: unknown = JSON.parse(readFileSync(proofFile('production.json'), 'utf8'));
    const detail = factoryMaterialDetailSchema.parse(detailRaw);
    const production = factoryProductionSchema.parse(productionRaw);
    // Then
    expect(world.materials.filter(row => row.active).map(row => [row.id, row.weight_kg])).toEqual([['A', 668], ['B', 667], ['C', 667]]);
    expect(world.orders).toHaveLength(2);
    expect(world.allocations.filter(row => row.active)).toHaveLength(3);
    expect(new Set(world.allocations.map(row => row.order_id)).size).toBe(2);
    expect(world.kpis.received_kg + world.kpis.additions_kg - world.kpis.active_kg - world.kpis.byproduct_kg - world.kpis.loss_kg).toBe(0);
    expect(world.kpis).toMatchObject({ received_kg: 2001, additions_kg: 7, active_kg: 2002, byproduct_kg: 4, loss_kg: 2 });
    expect(detail.material).toMatchObject({ id: 'A', origin_stock_lot_id: null, production_lot_id: null, quality_status: 'PENDING', availability_status: 'WIP' });
    expect(detail.current_attachment).toMatchObject({ kind: 'slot', owner_id: 'v2:p:receipt:HR_COIL:work', socket_id: 'work' });
    expect(detail.lineage_materials).toHaveLength(5);
    expect(detail.versions).toHaveLength(5);
    expect(production.version_edges).toEqual(world.version_edges);
    expect(production.batch_io).toEqual(world.batch_io);
    expect(detail.version_edges).toEqual(world.version_edges);
    expect(detail.batch_io).toEqual(world.batch_io);
    writeFileSync(proofFile('typescript-proof.json'), JSON.stringify({ outputs: world.materials.filter(row => row.active), order_count: world.orders.length, kpis: world.kpis, current_custody: detail.current_attachment, connected_material_count: detail.lineage_materials.length, public_allocation_rejection: JSON.parse(readFileSync(proofFile('allocation-rejected.json'), 'utf8')) }, null, 2));
  });

  it('matches every positive N:M edge against an independent BigInt transport table', () => {
    // Given
    const world = parseWorld();
    // When
    const expected = integerEdgeOracle(world);
    const actual = world.version_edges.map(row => `${row.input_version_id}|${row.output_version_id}|${BigInt(row.transferred_kg)}`).sort();
    const sqlRaw: unknown = JSON.parse(readFileSync(proofFile('sql.json'), 'utf8'));
    const sql = z.object({ independent_rows: z.object({ version_edges: z.array(VersionEdgeSchema), batch_io: z.array(BatchIOSchema) }), integrity: z.object({ foreign_key_check: z.array(z.unknown()), integrity_check: z.literal('ok') }) }).parse(sqlRaw);
    // Then
    expect(actual).toEqual(expected);
    expect(actual).toHaveLength(6);
    const external = world.batch_io.filter(row => row.role === 'EXTERNAL_ADDITION');
    expect(external).toHaveLength(1);
    expect(external[0]?.material_version_id).toBeNull();
    expect(world.material_versions).toHaveLength(5);
    expect(sql.independent_rows.version_edges).toEqual(world.version_edges);
    expect(sql.independent_rows.batch_io).toEqual(world.batch_io);
    expect(sql.integrity.foreign_key_check).toEqual([]);
    writeFileSync(proofFile('typescript-edges.json'), JSON.stringify({ arithmetic: 'BigInt integer transport, safe-number wire output', expected, actual }, null, 2));
  });

  it('includes active customer stock in global mass without fabricating delivery', () => {
    // Given
    const raw: unknown = JSON.parse(readFileSync(join(dirname(proofFile('world.json')), '../customer-stock/world.json'), 'utf8'));
    // When
    const world = factoryWorldSchema.parse(raw);
    // Then
    expect(world.materials.find(row => row.id === 'C')).toMatchObject({ active: true, availability_status: 'WIP', weight_kg: 667 });
    expect(world.attachments.find(row => row.material_id === 'C' && row.released_at_ms === null)?.owner_id).toBe('v2:p:CUSTOMER:work');
    expect(world.kpis.active_kg).toBe(2002);
    expect(world.shipments).toHaveLength(0);
    expect(world.events.some(row => row.event_type === 'SHIPMENT_DELIVERED')).toBe(false);
    writeFileSync(proofFile('typescript-customer-stock.json'), JSON.stringify({ active_kg: world.kpis.active_kg, customer_stock_kg: 667, delivery_workflow_proven: false }, null, 2));
  });
});
