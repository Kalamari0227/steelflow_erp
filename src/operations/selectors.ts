import type { MaterialView, World } from '../contracts';
import type { JourneySnapshot } from '../journey/contracts';

export function selectMaterial(world: World, materialId: string): MaterialView | null {
  const material = world.materials.find(row => row.id === materialId);
  const lot = world.lots.find(row => row.id === material?.lot_id);
  const work = world.work_orders.find(row => row.id === lot?.work_order_id);
  const order = world.orders.find(row => row.id === work?.order_id);
  if (!material || !lot || !work || !order) return null;
  const shipmentIds = new Set(world.shipment_materials.filter(row => row.material_id === materialId).map(row => row.shipment_id));
  return { run_id: world.run.id, revision: world.run.revision, material, lot, work_order: work, order,
    versions: world.material_versions.filter(row => row.material_id === materialId).sort((a, b) => a.ordinal - b.ordinal),
    lineage: world.lineage_edges.filter(row => row.parent_material_id === materialId || row.child_material_id === materialId),
    processes: world.processes.filter(row => row.material_id === materialId).sort((a, b) => a.step_ordinal - b.step_ordinal),
    transfers: world.transfers.filter(row => row.material_id === materialId), inspections: world.inspections.filter(row => row.material_id === materialId),
    shipments: world.shipments.filter(row => shipmentIds.has(row.id)),
  };
}
export function selectJourney(world: World, materialId: string): JourneySnapshot | null {
  const detail = selectMaterial(world, materialId);
  if (!detail) return null;
  const process = detail.processes.find(row => row.status === 'RUNNING') ?? detail.processes.find(row => row.status !== 'COMPLETED') ?? detail.processes.at(-1);
  const version = detail.versions.find(row => row.id === detail.material.current_version_id);
  return {
    data_scope: 'synthetic_product_journey', run_id: world.run.id, revision: world.run.revision,
    product_id: detail.order.product_id, playing: world.run.playing, speed: world.run.speed,
    elapsed_ms: world.run.elapsed_ms, duration_ms: world.run.duration_ms,
    active_step_id: process?.source_step_id ?? '', step_elapsed_ms: process?.start_ms === null || process?.start_ms === undefined ? 0 : Math.max(0, world.run.elapsed_ms - process.start_ms),
    step_duration_ms: process?.planned_duration_ms ?? 1, completed: detail.material.quality_status === 'PASSED',
    material: { lineage_id: detail.material.lineage_id, version_id: detail.material.current_version_id, parent_version_id: version?.parent_version_id ?? null, form: detail.material.form, role: detail.material.quality_status === 'PASSED' ? 'sale_product' : 'feedstock', location_id: detail.material.location_id, mass_kg: detail.material.weight_kg },
    history: detail.versions.map(row => {
      const event = world.events.find(event => event.id === row.cause_event_id);
      return { version_id: row.id, parent_version_id: row.parent_version_id, form: row.form, step_id: event?.process_id ?? '', at_ms: event?.at_ms ?? 0 };
    }),
  };
}
