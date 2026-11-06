import type { z } from 'zod';
import type { FactoryMaterialDetailShape, FactoryCommandShape, TransitionDeltaShape } from './contractsV3';
import { isActiveJob, validateBatches } from './contractsV3Validation';

type Row = { readonly run_id: string; readonly id: string };
type Projection = { readonly run_id: string; readonly revision: number; readonly schema_version: 3 };
export function validateProjectionScope(p: Projection & Readonly<Record<string, unknown>>, ctx: z.RefinementCtx): void {
  for (const [key, value] of Object.entries(p)) {
    if (['schema_version', 'run_id', 'revision'].includes(key) || value === null) continue;
    const rows: unknown[] = Array.isArray(value) ? value : [value];
    const ids = new Set<string>();
    for (const row of rows) {
      if (typeof row === 'object' && row !== null && 'run_id' in row && 'id' in row) {
        if (row.run_id !== p.run_id || typeof row.id !== 'string' || ids.has(row.id)) ctx.addIssue({ code: 'custom', message: `invalid projection scope or duplicate ${key}` });
        if (typeof row.id === 'string') ids.add(row.id);
      }
    }
  }
}

export function validateMaterialDetail(d: z.infer<typeof FactoryMaterialDetailShape>, ctx: z.RefinementCtx): void {
  validateProjectionScope(d, ctx);
  validateBatches({ ...d, material_versions: d.versions }, ctx);
  const check = (condition: boolean, message: string): void => { if (!condition) ctx.addIssue({ code: 'custom', message }); };
  const same = (a: Row | null, b: Row | undefined): boolean => a === null ? b === undefined : b !== undefined && JSON.stringify(a) === JSON.stringify(b);
  const m = d.material;
  check(same(m, d.lineage_materials.find(r => r.id === m.id)), 'selected material absent from lineage');
  check(same(d.current_version, d.versions.find(r => r.id === m.current_version_id)) && d.current_version.material_id === m.id && d.current_version.weight_kg === m.weight_kg && d.current_version.grade === m.grade && d.current_version.form === m.form && JSON.stringify(d.current_version.dimensions) === JSON.stringify(m.dimensions), 'current version mismatch');
  check(d.allocations.every(r => r.material_id === m.id) && d.allocations.filter(r => r.active).length <= 1, 'allocation membership');
  check(same(d.current_allocation, d.allocations.find(r => r.active)), 'current allocation mismatch');
  check(d.current_allocation === null ? d.order === null && d.work_order === null : d.current_allocation.order_id === d.order?.id && d.current_allocation.work_order_id === d.work_order?.id && d.work_order?.order_id === d.order?.id, 'provenance mismatch');
  check((d.production_lot?.id ?? null) === m.production_lot_id && (d.origin_stock_lot?.id ?? null) === m.origin_stock_lot_id, 'origin mismatch');
  check(d.attachments.every(r => r.material_id === m.id) && d.attachments.filter(r => r.released_at_ms === null).length <= 1 && same(d.current_attachment, d.attachments.find(r => r.released_at_ms === null)), 'current custody mismatch');
  check(d.transport_jobs.every(r => r.material_id === m.id) && d.transport_jobs.filter(r => isActiveJob(r.status)).length <= 1 && same(d.current_job, d.transport_jobs.find(r => isActiveJob(r.status))), 'current job mismatch');
  check(d.shipment_legs.every(r => d.shipments.some(s => s.id === r.shipment_id)), 'shipment leg mismatch');
  check(d.quality.every(r => r.material_id === m.id && d.versions.some(v => v.id === r.material_version_id && v.material_id === m.id)), 'quality membership');
  check(d.versions.every(v => d.lineage_materials.some(r => r.id === v.material_id)), 'lineage material missing');
  check(d.batch_io.every(r => d.process_batches.some(b => b.id === r.batch_id) && (r.material_version_id === null || d.versions.some(v => v.id === r.material_version_id))), 'batch IO reference');
  check(d.version_edges.every(e => d.process_batches.some(b => b.id === e.batch_id) && d.versions.some(v => v.id === e.input_version_id) && d.versions.some(v => v.id === e.output_version_id)), 'edge reference');
  for (const b of d.process_batches) {
    const io = d.batch_io.filter(r => r.batch_id === b.id);
    const inputs = io.filter(r => ['INPUT', 'STOCK_ADDITION', 'EXTERNAL_ADDITION'].includes(r.role)).reduce((total, r) => total + r.quantity_kg, 0);
    const outputs = io.filter(r => ['OUTPUT', 'BYPRODUCT', 'LOSS'].includes(r.role)).reduce((total, r) => total + r.quantity_kg, 0);
    check(b.status !== 'COMPLETED' || (io.length > 0 && inputs === outputs), 'detail batch mass mismatch');
  }
}

export function validateCommand(c: z.infer<typeof FactoryCommandShape>, ctx: z.RefinementCtx): void {
  if ((c.speed !== null && !['play', 'speed'].includes(c.action)) || (c.steps !== null && c.action !== 'step') || (c.scenario_id !== null && c.action !== 'scenario') || (c.action === 'speed' && c.speed === null) || (c.action === 'scenario' && c.scenario_id === null)) ctx.addIssue({ code: 'custom', message: 'action payload mismatch' });
}

export function validateDelta(d: z.infer<typeof TransitionDeltaShape>, ctx: z.RefinementCtx): void {
  if (d.to_revision < d.from_revision || d.event_sequence_to < d.event_sequence_from || Object.values(d.upserts).some(rows => rows.some(r => r.run_id !== d.run_id)) || d.upserts.events.some(e => e.sequence <= d.event_sequence_from || e.sequence > d.event_sequence_to)) ctx.addIssue({ code: 'custom', message: 'invalid delta bounds or run scope' });
}

export function validateOrderDetail(d: z.infer<typeof import('./contractsV3').FactoryOrderDetailShape>, ctx: z.RefinementCtx): void {
  validateProjectionScope(d, ctx);
  if (d.work_orders.some(r => r.order_id !== d.order.id) || d.allocations.some(r => r.order_id !== d.order.id || !d.work_orders.some(w => w.id === r.work_order_id) || !d.materials.some(m => m.id === r.material_id)) || d.shipments.some(r => r.order_id !== d.order.id) || d.shipment_legs.some(r => !d.shipments.some(s => s.id === r.shipment_id))) ctx.addIssue({ code: 'custom', message: 'order detail relationship mismatch' });
}

export function validateShipments(d: z.infer<typeof import('./contractsV3').FactoryShipmentsShape>, ctx: z.RefinementCtx): void {
  validateProjectionScope(d, ctx);
  if ([...d.shipment_legs, ...d.shipment_materials].some(r => !d.shipments.some(s => s.id === r.shipment_id))) ctx.addIssue({ code: 'custom', message: 'shipment relationship mismatch' });
}

export function validateProduction(d: z.infer<typeof import('./contractsV3').FactoryProductionShape>, ctx: z.RefinementCtx): void {
  validateProjectionScope(d, ctx);
  validateBatches(d, ctx);
  if (d.production_lots.some(r => !d.work_orders.some(w => w.id === r.work_order_id)) || d.processes.some(r => r.work_order_id !== null && !d.work_orders.some(w => w.id === r.work_order_id)) || d.process_batches.some(r => r.process_id !== null && !d.processes.some(p => p.id === r.process_id))) ctx.addIssue({ code: 'custom', message: 'production relationship mismatch' });
}

export function validateCoils(d: z.infer<typeof import('./contractsV3').FactoryCoilsShape>, ctx: z.RefinementCtx): void {
  validateProjectionScope(d, ctx);
  const forms = new Set(['HR_COIL', 'CR_COIL', 'GI_COIL', 'GA_COIL', 'HGI_COIL', 'EG_COIL', 'GO_COIL', 'NGO_COIL', 'WIRE_COIL', 'STS_HR_COIL', 'STS_CR_COIL', 'TI_HR_COIL', 'TI_CR_COIL']);
  if (d.materials.some(r => !forms.has(r.form))) ctx.addIssue({ code: 'custom', message: 'noncoil in coil projection' });
}
