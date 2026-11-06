import boundaryFixture from './fixtures/real-outfeed-boundaries.json';
import splitFixture from './fixtures/real-split-boundaries.json';
import { z } from 'zod';
import { expect, it } from 'vitest';
import { MaterialSchema, OperationsRunSchema, ProcessExecutionSchema, TransferSchema, MaterialLineageEdgeSchema, OperationsShipmentSchema, ShipmentMaterialSchema } from '../contracts';
import { testWorld } from '../testWorld';
import { processPose } from './processPose';
import { transferPose } from './transferPose';
import { distance } from './layout';
const worldSchema = z.object({ run: OperationsRunSchema, materials: z.array(MaterialSchema), processes: z.array(ProcessExecutionSchema), transfers: z.array(TransferSchema), lineage_edges: z.array(MaterialLineageEdgeSchema), shipments: z.array(OperationsShipmentSchema), shipment_materials: z.array(ShipmentMaterialSchema) });
const records = z.array(z.object({ materialId: z.string(), before: worldSchema, after: worldSchema })).parse(boundaryFixture);
it('keeps real fixture untimed outfeed boundaries continuous', () => {
  const settled = new Map<string, (typeof records)[number]>();
  for (const row of records) {
    const key = `${row.materialId}:${row.after.run.elapsed_ms}`;
    const previous = settled.get(key);
    settled.set(key, { ...row, before: previous?.before ?? row.before });
  }
  const observations = [...settled.values()].flatMap(row => {
    const before = { ...testWorld(), ...row.before }, after = { ...testWorld(), ...row.after };
    const materialBefore = before.materials.find(m => m.id === row.materialId), materialAfter = after.materials.find(m => m.id === row.materialId);
    const process = before.processes.find(p => p.status === 'RUNNING');
    if (!materialBefore || !materialAfter || !materialAfter.active || !process || transferPose(materialBefore, before, before.run.elapsed_ms)) return [];
    if (after.processes.some(p => p.id === process.id && p.status === 'RUNNING')) return [];
    const end = processPose(materialBefore, before, process.end_ms ?? after.run.elapsed_ms);
    const start = transferPose(materialAfter, after, after.run.elapsed_ms) ?? processPose(materialAfter, after, after.run.elapsed_ms);
    return [{ materialId: row.materialId, equipment: process.equipment_id, beforeAt: before.run.elapsed_ms, afterAt: after.run.elapsed_ms, from: materialBefore.location_id, to: materialAfter.location_id, end: end.position, start: start.position, distance: distance(end.position, start.position) }];
  });
  expect(observations.length).toBeGreaterThan(15);
  expect(observations.filter(row => row.distance >= 0.01)).toEqual([]);
});

it('starts both actual split children at the confirmed parent outfeed endpoint', () => {
  const splits = z.array(z.object({ materialId: z.string(), before: worldSchema, after: worldSchema })).parse(splitFixture);
  for (const row of splits) {
    const before = { ...testWorld(), ...row.before }, after = { ...testWorld(), ...row.after };
    const parent = before.materials.find(m => m.id === row.materialId);
    const process = before.processes.find(p => p.status === 'RUNNING');
    if (!parent || !process) throw new Error('Missing real split parent');
    const end = processPose(parent, before, process.end_ms ?? after.run.elapsed_ms).position;
    for (const child of after.materials.filter(m => m.lineage_id === parent.lineage_id && m.active)) {
      const start = transferPose(child, after, after.run.elapsed_ms) ?? processPose(child, after, after.run.elapsed_ms);
      expect(distance(end, start.position), child.id).toBeLessThan(0.01);
    }
  }
});
