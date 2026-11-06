import type { World } from '../../contracts';
import type { Material, MaterialForm, ProcessExecution } from '../contracts';
import { factoryLayout, LayoutReferenceError, stationAnchorPosition, pointOnPolyline } from './layout';
import type { Equipment, Point } from './layout';
import { storagePosition } from './materialSlots';

export const equipmentKinds = ['alloying', 'annealing', 'aod', 'blast_furnace', 'bloom_mill', 'bof', 'caster', 'charge', 'coating', 'coiler', 'cold_mill', 'cooling', 'cooling_bed', 'decarburizing', 'delivery', 'eaf', 'electrocleaning', 'electroplating', 'finishing_mill', 'forging', 'furnace', 'galvanizing', 'heat_treatment', 'inspection', 'ladle_furnace', 'laying_head', 'leveler', 'oiling', 'packaging', 'pickling', 'port', 'roughing', 'shear', 'ship', 'slitter', 'stock', 'temper', 'uncoiler', 'vacuum_annealing', 'wire_mill'] as const;
export function validateEquipment(equipment: Equipment): void {
  if (!equipmentKinds.some(kind => kind === equipment.kind)) throw new LayoutReferenceError(`equipment kind ${equipment.kind}`);
}
export function processStation(id: string): Equipment {
  const station = factoryLayout.equipment.find(row => row.id === id);
  if (!station) throw new LayoutReferenceError(id);
  validateEquipment(station);
  return station;
}
export function processPhase(process: ProcessExecution, elapsedMs: number): number {
  switch (process.status) {
    case 'COMPLETED': return 1;
    case 'QUEUED': case 'BLOCKED': return 0;
    case 'RUNNING': return Math.max(0, Math.min(0.97, (elapsedMs - (process.start_ms ?? elapsedMs)) / ((process.end_ms ?? elapsedMs + 1) - (process.start_ms ?? elapsedMs))));
    default: { const exhaustive: never = process.status; return exhaustive; }
  }
}
export type ProcessPose = { readonly position: Point; readonly rotationY: number; readonly phase: number; readonly equipmentId: string | null; readonly kind: string; readonly form: MaterialForm; readonly hot: boolean };
function mix(a: Point, b: Point, phase: number): Point { return [a[0] + (b[0] - a[0]) * phase, a[1] + (b[1] - a[1]) * phase, a[2] + (b[2] - a[2]) * phase]; }
export function processContact(equipmentId: string, phase: number): Point {
  const entry = stationAnchorPosition(factoryLayout, equipmentId, 'entry');
  const work = stationAnchorPosition(factoryLayout, equipmentId, 'work');
  const exit = stationAnchorPosition(factoryLayout, equipmentId, 'exit');
  if (phase < 0.35) return mix(entry, work, phase / 0.35);
  if (phase <= 0.65) return work;
  return mix(work, exit, Math.min(1, (phase - 0.65) / 0.32));
}
export function processPose(material: Material, world: World, elapsedMs: number): ProcessPose {
  const process = world.processes.find(row => row.material_id === material.id && row.status === 'RUNNING');
  const station = process ? processStation(process.equipment_id) : factoryLayout.equipment.find(row => Object.values(row.anchors).some(anchor => anchor.location_id === material.location_id) || row.id === material.location_id);
  if (station) validateEquipment(station);
  const phase = process ? processPhase(process, elapsedMs) : 0;
  const location = factoryLayout.locations.find(row => row.id === material.location_id);
  const apiLocation = world.locations.find(row => row.id === material.location_id);
  let position = process ? processContact(process.equipment_id, phase) : location?.position ?? (station ? stationAnchorPosition(factoryLayout, station.id, 'buffer') : apiLocation ? [apiLocation.x, apiLocation.y, apiLocation.z] satisfies Point : null);
  if (!position) throw new LayoutReferenceError(material.location_id);
  if (!process) position = storagePosition(material, world, { id: material.location_id, position }, elapsedMs);
  if (process && station) {
    if (phase < 0.35) {
      const entry = stationAnchorPosition(factoryLayout, station.id, 'entry');
      const slot = storagePosition(material, world, { id: station.anchors.entry.location_id, position: entry }, process.start_ms ?? elapsedMs);
      position = mix(slot, stationAnchorPosition(factoryLayout, station.id, 'work'), phase / 0.35);
    }
    if (phase > 0.65) {
      const exit = stationAnchorPosition(factoryLayout, station.id, 'exit');
      const successor = world.processes.filter(row => row.material_id === material.id && row.step_ordinal > process.step_ordinal).sort((a, b) => a.step_ordinal - b.step_ordinal)[0];
      const nextStation = factoryLayout.equipment.find(row => row.id === successor?.equipment_id);
      const path = factoryLayout.paths.find(row => row.from_location_id === station.anchors.exit.location_id && row.to_location_id === (station.id === 'PACKAGING' ? 'OPS-WAREHOUSE-ENTRY' : nextStation?.anchors.entry.location_id));
      const untimed = path?.mode === 'roller' && !path.custody_location_id;
      const destinationId = untimed && path ? (station.id === 'PACKAGING' ? 'OPS-WAREHOUSE-BUFFER' : path.to_location_id) : station.anchors.exit.location_id;
      const destination = factoryLayout.locations.find(row => row.id === destinationId);
      const slot = storagePosition(material, world, { id: destinationId, position: destination?.position ?? exit }, process.end_ms ?? elapsedMs);
      // Untimed backend handoffs share the outgoing station's final feed segment.
      const points = [stationAnchorPosition(factoryLayout, station.id, 'work'), exit, ...(untimed && path ? path.points.slice(1) : []), slot];
      position = pointOnPolyline(points, Math.min(1, (phase - 0.65) / 0.32));
    }
  }
  const stage = factoryLayout.stages.find(row => row.id === station?.stage_id);
  return { position, rotationY: (station?.rotation ?? 0) + (stage?.rotation ?? 0), phase, equipmentId: station?.id ?? null, kind: process ? station?.kind ?? '' : '', form: material.form, hot: /^(HOT_|LIQUID)/.test(material.form) || Boolean(process && ['blast_furnace', 'bof', 'ladle_furnace', 'furnace', 'caster', 'heat_treatment', 'annealing', 'vacuum_annealing'].includes(station?.kind ?? '')) };
}
