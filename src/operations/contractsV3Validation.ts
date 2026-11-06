import type { z } from 'zod';
import type { FactorySnapshotShape, FactoryWorldShape } from './contractsV3';

type Snapshot = z.infer<typeof FactorySnapshotShape>;
type World = z.infer<typeof FactoryWorldShape>;
type Row = { readonly id: string; readonly run_id: string };
const activeJobs = new Set(['ASSIGNED', 'EMPTY_APPROACH', 'QUEUED', 'LOADING', 'MOVING', 'UNLOADING', 'RETURNING', 'BLOCKED']);
export const isActiveJob = (status: string): boolean => activeJobs.has(status);
const unique = (values: readonly (string | number)[]): boolean => new Set(values).size === values.length;
const sum = <T>(rows: readonly T[], weight: (row: T) => number): number => rows.reduce((total, row) => total + weight(row), 0);

export function validateSnapshot(s: Snapshot, ctx: z.RefinementCtx): void {
  const check = (condition: boolean, message: string): void => { if (!condition) ctx.addIssue({ code: 'custom', message }); };
  const { run, schema_version: _schema, ...collections } = s;
  const groups: Readonly<Record<string, readonly Row[]>> = collections;
  for (const [name, rows] of Object.entries(groups)) {
    check(unique(rows.map(r => r.id)), `duplicate ${name} id`);
    check(rows.every(r => r.run_id === run.id), `cross-run ${name}`);
  }
  const ref = (rows: readonly Row[], id: string | null): boolean => id === null || rows.some(r => r.id === id);
  const refs: boolean[] = [];
  for (const r of s.work_orders) refs.push(ref(s.orders, r.order_id));
  for (const r of s.production_lots) refs.push(ref(s.work_orders, r.work_order_id));
  for (const r of s.receipts) refs.push(ref(s.stock_lots, r.stock_lot_id), ref(s.events, r.event_id));
  for (const r of s.materials) refs.push(ref(s.stock_lots, r.origin_stock_lot_id), ref(s.production_lots, r.production_lot_id), ref(s.material_versions, r.current_version_id));
  for (const r of s.material_versions) refs.push(ref(s.materials, r.material_id), ref(s.events, r.cause_event_id));
  for (const r of s.version_edges) refs.push(ref(s.process_batches, r.batch_id), ref(s.material_versions, r.input_version_id), ref(s.material_versions, r.output_version_id));
  for (const r of s.allocations) refs.push(ref(s.materials, r.material_id), ref(s.orders, r.order_id), ref(s.work_orders, r.work_order_id));
  for (const r of s.process_batches) refs.push(ref(s.processes, r.process_id));
  for (const r of s.batch_io) refs.push(ref(s.process_batches, r.batch_id), ref(s.material_versions, r.material_version_id));
  for (const r of s.processes) refs.push(ref(s.work_orders, r.work_order_id));
  for (const r of s.vehicle_states) refs.push(ref(s.fleet, r.fleet_id), ref(s.transport_jobs, r.current_job_id));
  for (const r of s.transport_jobs) refs.push(ref(s.fleet, r.fleet_id), ref(s.materials, r.material_id), ref(s.shipment_legs, r.shipment_leg_id));
  for (const r of s.movement_segments) refs.push(ref(s.transport_jobs, r.job_id));
  for (const r of s.reservations) refs.push(ref(s.transport_jobs, r.job_id));
  for (const r of s.consists) refs.push(ref(s.fleet, r.locomotive_id));
  for (const r of s.consist_members) refs.push(ref(s.consists, r.consist_id), ref(s.fleet, r.fleet_id));
  for (const r of s.attachments) { refs.push(ref(s.materials, r.material_id)); if (['vehicle', 'railcar', 'ship'].includes(r.kind)) refs.push(ref(s.fleet, r.owner_id)); }
  for (const r of s.shipments) refs.push(ref(s.orders, r.order_id));
  for (const r of s.shipment_legs) refs.push(ref(s.shipments, r.shipment_id));
  for (const r of s.shipment_materials) refs.push(ref(s.shipments, r.shipment_id), ref(s.materials, r.material_id));
  for (const r of s.quality) refs.push(ref(s.materials, r.material_id), ref(s.material_versions, r.material_version_id), ref(s.events, r.event_id));
  for (const r of s.mass_ledger) refs.push(ref(s.materials, r.material_id), ref(s.process_batches, r.batch_id), ref(s.events, r.event_id));
  const entityGroups = { run: [run], order: s.orders, work_order: s.work_orders, production_lot: s.production_lots, stock_lot: s.stock_lots, receipt: s.receipts, material: s.materials, material_version: s.material_versions, batch: s.process_batches, process: s.processes, fleet: s.fleet, job: s.transport_jobs, attachment: s.attachments, shipment: s.shipments, shipment_leg: s.shipment_legs, quality: s.quality };
  for (const r of s.events) {
    check(entityGroups[r.entity_type].some(entity => entity.id === r.entity_id), 'missing event entity');
    const p = r.payload;
    refs.push(...p.material_ids.map(id => ref(s.materials, id)), ref(s.orders, p.order_id), ref(s.work_orders, p.work_order_id), ref(s.processes, p.process_id), ref(s.process_batches, p.batch_id), ref(s.transport_jobs, p.job_id), ref(s.shipment_legs, p.shipment_leg_id), ref(s.attachments, p.from_attachment_id), ref(s.attachments, p.to_attachment_id));
    check(r.at_ms <= run.elapsed_ms && Date.parse(r.occurred_at) === Date.parse(run.epoch_at) + r.at_ms * 60, 'event clock mismatch');
  }
  check(refs.every(Boolean), 'missing domain reference');
  check(run.elapsed_ms <= run.duration_ms && run.epoch_at === '2026-10-30T00:00:00.000Z' && [1, 2, 4].includes(run.speed), 'invalid run clock');
  check(s.events.length === run.event_sequence && [...s.events].sort((a, b) => a.sequence - b.sequence).every((r, i) => r.sequence === i + 1), 'event sequence gap');
  for (const rows of [s.events, s.receipts, s.mass_ledger]) check(unique(rows.map(r => r.source_id)), 'duplicate source');
  check(unique(s.material_versions.map(r => `${r.material_id}\0${r.ordinal}`)), 'duplicate version ordinal');
  check(unique(s.allocations.filter(r => r.active).map(r => r.material_id)), 'multiple active allocations');
  check(unique(s.attachments.filter(r => r.released_at_ms === null).map(r => r.material_id)), 'multiple current attachments');
  for (const m of s.materials) {
    const v = s.material_versions.find(r => r.id === m.current_version_id);
    check(v !== undefined && v.material_id === m.id && v.grade === m.grade && v.form === m.form && v.weight_kg === m.weight_kg && JSON.stringify(v.dimensions) === JSON.stringify(m.dimensions), 'current version mismatch');
    check(m.active !== (m.availability_status === 'CONSUMED'), 'material activity mismatch');
  }
  for (const a of s.allocations) {
    const m = s.materials.find(r => r.id === a.material_id);
    check(s.work_orders.find(r => r.id === a.work_order_id)?.order_id === a.order_id, 'allocation order mismatch');
    check(m !== undefined && a.quantity_kg <= m.weight_kg && (!a.active || m.active), 'allocation physical mass mismatch');
  }
  for (const q of s.quality) check(s.material_versions.find(r => r.id === q.material_version_id)?.material_id === q.material_id, 'quality version mismatch');
  for (const a of s.attachments) check(a.released_at_ms === null ? s.materials.some(r => r.id === a.material_id && r.active) : a.released_at_ms >= a.acquired_at_ms, 'invalid custody');
  for (const p of [...s.processes, ...s.process_batches]) {
    check(p.end_ms === null || (p.start_ms !== null && p.end_ms > p.start_ms), 'process time window');
    check(!['RUNNING', 'COMPLETED'].includes(p.status) || (p.start_ms !== null && p.end_ms !== null), 'process window required');
  }
  for (const p of s.processes) check(p.start_ms === null || p.start_ms >= p.ready_at_ms, 'process before ready');
  validateBatches(s, ctx);
  validateLogistics(s, ctx);
  validateReservations(s, ctx);
  const incoming = sum(s.mass_ledger.filter(r => ['OPENING_STOCK', 'EXTERNAL_RECEIPT', 'EXTERNAL_ADDITION'].includes(r.kind)), r => r.quantity_kg);
  const outgoing = sum(s.mass_ledger.filter(r => ['BYPRODUCT', 'IRRECOVERABLE_LOSS'].includes(r.kind)), r => r.quantity_kg);
  check(Number.isSafeInteger(incoming) && Number.isSafeInteger(outgoing) && incoming === sum(s.materials.filter(r => r.active), r => r.weight_kg) + outgoing, 'global mass imbalance or unsafe total');
}

export function validateBatches(s: Pick<Snapshot, 'batch_io' | 'process_batches' | 'material_versions' | 'version_edges'>, ctx: z.RefinementCtx): void {
  const check = (condition: boolean, message: string): void => { if (!condition) ctx.addIssue({ code: 'custom', message }); };
  const input = new Set(['INPUT', 'STOCK_ADDITION', 'EXTERNAL_ADDITION']);
  check(unique(s.batch_io.map(r => `${r.batch_id}\0${r.role}\0${r.material_version_id}\0${r.source_id}`)), 'duplicate batch source');
  check(unique(s.batch_io.filter(r => r.material_version_id !== null && ['INPUT', 'STOCK_ADDITION'].includes(r.role)).map(r => r.material_version_id ?? '')), 'version consumed twice');
  check(unique(s.version_edges.map(r => `${r.batch_id}\0${r.input_version_id}\0${r.output_version_id}`)), 'duplicate edge');
  for (const r of s.batch_io) {
    check(r.material_version_id !== null || (!['INPUT', 'STOCK_ADDITION', 'OUTPUT'].includes(r.role) && r.source_id !== null), 'batch source required');
    if (r.material_version_id !== null) check(s.material_versions.some(v => v.id === r.material_version_id && r.quantity_kg <= v.weight_kg), 'IO exceeds version mass');
    const edges = s.version_edges.filter(e => e.batch_id === r.batch_id);
    check(sum(edges.filter(e => e.input_version_id === r.material_version_id), e => e.transferred_kg) <= r.quantity_kg && sum(edges.filter(e => e.output_version_id === r.material_version_id), e => e.transferred_kg) <= r.quantity_kg, 'edge totals exceed IO');
  }
  for (const b of s.process_batches) {
    const rows = s.batch_io.filter(r => r.batch_id === b.id);
    if (b.status === 'COMPLETED') check(rows.length > 0 && sum(rows.filter(r => input.has(r.role)), r => r.quantity_kg) === sum(rows.filter(r => !input.has(r.role)), r => r.quantity_kg), 'batch mass imbalance');
  }
  const adjacency = new Map<string, Set<string>>();
  const indegree = new Map(s.material_versions.map(v => [v.id, 0]));
  for (const e of s.version_edges) {
    const inputs = s.batch_io.filter(r => r.batch_id === e.batch_id && r.material_version_id === e.input_version_id && input.has(r.role));
    const outputs = s.batch_io.filter(r => r.batch_id === e.batch_id && r.material_version_id === e.output_version_id && ['OUTPUT', 'BYPRODUCT'].includes(r.role));
    check(inputs.length > 0 && outputs.length > 0 && e.transferred_kg <= Math.min(sum(inputs, r => r.quantity_kg), sum(outputs, r => r.quantity_kg)), 'edge missing IO or exceeds mass');
    const targets = adjacency.get(e.input_version_id) ?? new Set<string>();
    if (!targets.has(e.output_version_id)) indegree.set(e.output_version_id, (indegree.get(e.output_version_id) ?? 0) + 1);
    targets.add(e.output_version_id); adjacency.set(e.input_version_id, targets);
  }
  const ready = [...indegree].filter(([, count]) => count === 0).map(([id]) => id);
  let visited = 0;
  while (ready.length) {
    const id = ready.pop();
    if (id === undefined) break;
    visited++;
    for (const target of adjacency.get(id) ?? []) {
      const count = (indegree.get(target) ?? 0) - 1;
      indegree.set(target, count); if (count === 0) ready.push(target);
    }
  }
  check(visited === s.material_versions.length, 'lineage cycle');
}

function validateLogistics(s: Snapshot, ctx: z.RefinementCtx): void {
  const check = (condition: boolean, message: string): void => { if (!condition) ctx.addIssue({ code: 'custom', message }); };
  check(unique(s.vehicle_states.map(r => r.fleet_id)), 'duplicate vehicle state');
  for (const field of ['fleet_id', 'equipment_id', 'material_id'] as const) check(unique(s.transport_jobs.filter(r => isActiveJob(r.status) && r[field] !== null).map(r => r[field] ?? '')), 'multiple active jobs');
  check(unique(s.movement_segments.map(r => `${r.job_id}\0${r.ordinal}`)), 'duplicate movement ordinal');
  check(unique(s.consist_members.map(r => `${r.consist_id}\0${r.ordinal}`)) && unique(s.consist_members.map(r => r.fleet_id)), 'duplicate consist member');
  check(unique(s.shipment_legs.map(r => `${r.shipment_id}\0${r.ordinal}`)), 'duplicate leg ordinal');
  for (const r of s.vehicle_states) check(r.current_job_id === null || s.transport_jobs.some(j => j.id === r.current_job_id && j.fleet_id === r.fleet_id), 'vehicle job mismatch');
  for (const r of s.consists) check(s.fleet.some(f => f.id === r.locomotive_id && f.kind === 'locomotive'), 'consist locomotive mismatch');
  for (const r of s.consist_members) check(s.fleet.some(f => f.id === r.fleet_id && f.kind === 'railcar'), 'consist railcar mismatch');
  for (const r of [...s.movement_segments, ...s.reservations]) check(r.end_ms > r.start_ms, 'invalid reservation window');
  for (const r of s.transport_jobs) {
    check(r.start_ms === null || r.start_ms >= r.ready_at_ms, 'job before ready');
    check(r.end_ms === null || (r.start_ms !== null && r.end_ms > r.start_ms), 'job window');
    check(r.fleet_id === null || r.equipment_id === null, 'multiple job owners');
    check(!isActiveJob(r.status) || r.fleet_id !== null || r.equipment_id !== null, 'job owner required');
    check(r.status !== 'STRUCTURAL_BLOCKED' || r.blocked_resource_id !== null, 'blocked resource required');
  }
  for (const r of s.shipment_legs) check(r.end_ms === null || (r.start_ms !== null && r.end_ms > r.start_ms), 'leg window');
}

export function validateWorld(s: World, ctx: z.RefinementCtx): void {
  const { kpis: k, ...snapshot } = s;
  validateSnapshot(snapshot, ctx);
  const active = s.materials.filter(r => r.active);
  const expected = { schema_version: 3, run_id: s.run.id, revision: s.run.revision,
    active_material_count: active.length, active_kg: sum(active, r => r.weight_kg),
    available_kg: sum(active.filter(r => r.availability_status === 'AVAILABLE'), r => r.weight_kg),
    allocated_kg: sum(s.allocations.filter(r => r.active), r => r.quantity_kg),
    shipped_kg: sum(active.filter(r => r.availability_status === 'SHIPPED'), r => r.weight_kg),
    opening_kg: sum(s.mass_ledger.filter(r => r.kind === 'OPENING_STOCK'), r => r.quantity_kg),
    received_kg: sum(s.mass_ledger.filter(r => r.kind === 'EXTERNAL_RECEIPT'), r => r.quantity_kg),
    additions_kg: sum(s.mass_ledger.filter(r => r.kind === 'EXTERNAL_ADDITION'), r => r.quantity_kg),
    byproduct_kg: sum(s.mass_ledger.filter(r => r.kind === 'BYPRODUCT'), r => r.quantity_kg),
    loss_kg: sum(s.mass_ledger.filter(r => r.kind === 'IRRECOVERABLE_LOSS'), r => r.quantity_kg) };
  if (Object.entries(expected).some(([key, value]) => Reflect.get(k, key) !== value)) ctx.addIssue({ code: 'custom', message: 'KPI mismatch' });
}

function validateReservations(s: Snapshot, ctx: z.RefinementCtx): void {
  const check = (condition: boolean, message: string): void => { if (!condition) ctx.addIssue({ code: 'custom', message }); };
  const occupied = new Map<string, { start: number; end: number }[]>();
  for (const row of s.reservations) {
    check(row.released_at_ms === null || row.released_at_ms <= s.run.elapsed_ms, 'future reservation release');
    const end = row.released_at_ms === null ? row.end_ms : Math.min(row.end_ms, row.released_at_ms);
    if (row.start_ms < end) {
      const intervals = occupied.get(row.resource_id) ?? [];
      intervals.push({ start: row.start_ms, end }); occupied.set(row.resource_id, intervals);
    }
  }
  for (const intervals of occupied.values()) {
    let previousEnd = -1;
    for (const interval of intervals.sort((a, b) => a.start - b.start)) {
      check(interval.start >= previousEnd, 'reservation intervals overlap'); previousEnd = interval.end;
    }
  }
  for (const event of s.events) {
    const context = event.payload;
    if (context.reservation_id === null) continue;
    const row = s.reservations.find(item => item.id === context.reservation_id);
    check(row !== undefined, 'missing reservation event reference');
    if (row === undefined) continue;
    check(context.job_id === row.job_id && context.resource_id === row.resource_id, 'reservation event owner mismatch');
    if (event.event_type === 'RESERVATION_RELEASED') check(row.released_at_ms === event.at_ms, 'reservation release event time mismatch');
  }
}
