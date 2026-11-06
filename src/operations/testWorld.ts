import { CommandReplySchema, WorldSchema } from '../contracts';
import type { CommandReply, World } from '../contracts';

export function testWorld(revision = 0, runId = 'run-test'): World {
  const order = { run_id: runId, id: 'ORD-ga', customer_id: 'CUSTOMER', product_id: 'ga', grade: 'SYNTHETIC', width_mm: null, thickness_mm: null, quantity_kg: 20000, due_at: '2026-10-30T00:12:00Z', status: 'IN_PRODUCTION', produced_kg: 0, dispatched_kg: 0, delivered_kg: 0, remaining_dispatch_kg: 20000, remaining_delivery_kg: 20000, work_order_ids: ['WO-ga'], material_ids: ['MAT-ga'], shipment_ids: [] };
  const lot = { run_id: runId, id: 'LOT-ga', work_order_id: 'WO-ga', planned_kg: 20000, order_id: 'ORD-ga', actual_kg: 0, status: 'RELEASED' };
  const material = { run_id: runId, id: 'MAT-ga', lot_id: 'LOT-ga', lineage_id: 'MAT-ga', current_version_id: 'MAT-ga:V1', form: 'ORE', weight_kg: 20000, location_id: 'ORE-SOURCE', quality_status: 'PENDING', availability_status: 'WIP', active: true };
  const processes = [{ run_id: runId, id: 'PROC-ga', material_id: 'MAT-ga', route_step_id: 'ga:charge', source_step_id: 'charge', step_ordinal: 0, equipment_id: 'CHARGE-A', predecessor_id: null, status: 'QUEUED', planned_duration_ms: 10000, input_form: 'ORE', output_form: 'HOT_METAL' }];
  return WorldSchema.parse({
    schema_version: 2,
    run: { id: runId, scenario_id: 'NORMAL', elapsed_ms: revision * 100, duration_ms: 20000, revision, event_sequence: 0, playing: false, speed: 1, epoch_at: '2026-10-30T00:00:00Z', started_at: '2026-10-24T00:00:00Z', plan_revision: 0 },
    orders: [order], lots: [lot], materials: [material], processes,
    work_orders: [{ run_id: runId, id: 'WO-ga', order_id: 'ORD-ga', route_id: 'ga', route_version: 1, planned_kg: 20000 }],
    material_versions: [{ run_id: runId, id: 'MAT-ga:V1', material_id: 'MAT-ga', ordinal: 1, parent_version_id: null, form: 'ORE', weight_kg: 20000, cause_event_id: null }],
    mass_balance: { initial_kg: 20000, additions_kg: 0, active_kg: 20000, loss_kg: 0 },
    production: { run_id: runId, revision, orders: [order], lots: [lot], materials: [material], processes, transfers: [], batches: [], stages: [{ id: 'ironmaking', equipment_ids: ['CHARGE-A'], process_ids: ['PROC-ga'], batch_ids: [] }] },
    simulation: { run_id: runId, scenario_id: 'NORMAL', tick: revision, max_tick: 48, elapsed_ms: revision * 100, revision, step_ms: 1000, simulated_at: '2026-10-30T00:00:00Z', playing: false, speed: 1, tick_seconds: 0.1 },
    kpis: { total_orders: 1, active_orders: 1, total_mass_kg: 20000, produced_kg: 0, dispatched_kg: 0, in_transit_kg: 0, delivered_kg: 0, throughput_kg: 0, coil_count: 0, available_kg: 0 },
    customers: [{ id: 'CUSTOMER', name: 'Synthetic', country: 'KR' }], coils: [], locations: [], inventory: [], inventory_materials: [material], shipment_coils: [], risks: [], ai: { enabled: false, available: false, provider: 'disabled' },
  });
}
export function testReply(world: World, replayed = false): CommandReply {
  return CommandReplySchema.parse({ ...world, applied_revision: world.run.revision, replayed });
}
export function deferred<T>() {
  let resolve: (value: T) => void = () => { throw new Error('Promise not initialized'); };
  let reject: (reason: Error) => void = () => { throw new Error('Promise not initialized'); };
  const promise = new Promise<T>((success, failure) => { resolve = success; reject = failure; });
  return { promise, resolve, reject };
}
