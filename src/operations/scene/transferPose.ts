import type { World } from '../../contracts';
import type { Material, OperationsShipment, Transfer } from '../contracts';
import { factoryLayout, pointOnPolyline, LayoutReferenceError } from './layout';
import type { Point } from './layout';
import { shipmentSlot, storagePosition } from './materialSlots';

export type TransportPose = { readonly position: Point; readonly rotationY: number; readonly carrierId: string | null; readonly custody: 'source' | 'hook' | 'cargo' | 'destination' | 'roller' };
type Window = { readonly phase_start_ms: number | null; readonly phase_end_ms: number | null };
export function locationPosition(id: string): Point {
  const location = factoryLayout.locations.find(row => row.id === id);
  if (!location) throw new LayoutReferenceError(id);
  return location.position;
}
export function transportPhase(window: Window, elapsedMs: number): number {
  if (window.phase_start_ms === null || window.phase_end_ms === null) return 0;
  if (window.phase_end_ms <= window.phase_start_ms) throw new Error('Transport phase must have positive duration');
  const t = Math.max(0, Math.min(1, (elapsedMs - window.phase_start_ms) / (window.phase_end_ms - window.phase_start_ms)));
  if (t < 0.1) return t * t / 0.18;
  if (t > 0.9) return 1 - (1 - t) ** 2 / 0.18;
  return (t - 0.05) / 0.9;
}
const raised = (point: Point): Point => [point[0], point[1] + 0.31, point[2]];
function pose(points: readonly Point[], phase: number, custody: TransportPose['custody'], carrierId: string | null): TransportPose {
  const position = pointOnPolyline(points, phase);
  const ahead = pointOnPolyline(points, Math.min(1, phase + 0.01));
  const behind = pointOnPolyline(points, Math.max(0, phase - 0.01));
  return { position, rotationY: -Math.atan2(ahead[2] - behind[2], ahead[0] - behind[0]), custody, carrierId };
}
function lift(from: Point, to: Point, phase: number, carrier: string | null): TransportPose {
  const height = Math.max(from[1], to[1]) + 2.2;
  return pose([from, [from[0], height, from[2]], [to[0], height, to[2]], to], phase, 'hook', carrier);
}
export function internalTransferPose(transfer: Transfer, elapsedMs: number, sourceSlot?: Point, destinationSlot?: Point): TransportPose {
  const path = factoryLayout.paths.find(row => row.from_location_id === transfer.from_location_id && row.to_location_id === transfer.to_location_id);
  if (!path) throw new LayoutReferenceError(transfer.id);
  const source = locationPosition(transfer.from_location_id), destination = locationPosition(transfer.to_location_id);
  const phase = transportPhase(transfer, elapsedMs);
  switch (transfer.status) {
    case 'WAITING': return pose([sourceSlot ?? source], 0, 'source', null);
    case 'LOADING': return lift(sourceSlot ?? source, raised(source), phase, transfer.crane_id);
    case 'IN_TRANSIT': return pose(transfer.mode === 'roller' ? [sourceSlot ?? source, ...path.points.slice(1, -1), destinationSlot ?? destination] : path.points.map(raised), phase, transfer.mode === 'roller' ? 'roller' : 'cargo', transfer.vehicle_id);
    case 'UNLOADING': return lift(raised(destination), destinationSlot ?? destination, phase, transfer.crane_id);
    case 'ARRIVED': return pose([destinationSlot ?? destination], 0, 'destination', null);
    default: return unreachable(transfer.status);
  }
}
function unreachable(value: never): never { throw new Error(`Unexpected transport state: ${String(value)}`); }
function shipmentPath(kind: 'road' | 'sea'): readonly Point[] {
  const id = kind === 'road' ? 'PATH-WAREHOUSE--PORT' : 'PATH-SHIP--CUSTOMER';
  const path = factoryLayout.paths.find(row => row.id === id);
  if (!path) throw new LayoutReferenceError(id);
  // Road custody ends at the port buffer, where the backend hands it to the port hook.
  return kind === 'road' ? [...path.points.map(raised), locationPosition('OPS-PORT-BUFFER')] : path.points.map(raised);
}
export function shipmentVehiclePose(shipment: OperationsShipment, elapsedMs: number): TransportPose | null {
  const phase = transportPhase(shipment, elapsedMs);
  switch (shipment.status) {
    case 'PLANNED': case 'ALLOCATED': case 'DELIVERED': return null;
    case 'LOADING': case 'LOADED': return pose(shipmentPath('road'), 0, 'cargo', 'FLATBED-A');
    case 'DISPATCHED': return pose(shipmentPath('road'), phase, 'cargo', 'FLATBED-A');
    case 'AT_PORT': return shipment.phase_end_ms === null ? null : pose(shipmentPath('sea'), 0, 'cargo', 'SHIP-A');
    case 'IN_TRANSIT': return pose(shipmentPath('sea'), shipment.location_id === 'OPS-CUSTOMER-ENTRY' ? 1 : phase, 'cargo', 'SHIP-A');
    default: return unreachable(shipment.status);
  }
}
function outboundPose(material: Material, context: { readonly world: World; readonly shipment: OperationsShipment }, elapsedMs: number): TransportPose {
  const { world, shipment } = context;
  const phase = transportPhase(shipment, elapsedMs);
  const slot = shipmentSlot(material, world);
  const storage = (id: string) => storagePosition(material, world, { id, position: locationPosition(id) });
  const road = shipmentPath('road'), sea = shipmentPath('sea');
  const deck = (carrier: TransportPose): TransportPose => ({ ...carrier, position: [carrier.position[0] + Math.cos(carrier.rotationY) * slot[0] + Math.sin(carrier.rotationY) * slot[2], carrier.position[1] + slot[1], carrier.position[2] - Math.sin(carrier.rotationY) * slot[0] + Math.cos(carrier.rotationY) * slot[2]] });
  const roadStart = deck(pose(road, 0, 'cargo', 'FLATBED-A'));
  const portSlot = deck(pose(road, 1, 'cargo', 'FLATBED-A')).position;
  const seaStart = deck(pose(sea, 0, 'cargo', 'SHIP-A'));
  const seaEnd = deck(pose(sea, 1, 'cargo', 'SHIP-A'));
  const at = (id: string, custody: TransportPose['custody']) => pose([id === 'OPS-PORT-BUFFER' ? portSlot : storage(id)], 0, custody, null);
  // The member's current location, never another member or its previous-leg loaded flag, owns custody.
  switch (material.location_id) {
    case 'OPS-CRANE-WAREHOUSE-HOOK': return lift(storage('OPS-WAREHOUSE-BUFFER'), roadStart.position, phase, 'CRANE-WAREHOUSE');
    case 'OPS-CRANE-PORT-HOOK': return lift(portSlot, seaStart.position, phase, 'CRANE-PORT');
    case 'OPS-CRANE-CUSTOMER-HOOK': return lift(seaEnd.position, storage('OPS-CUSTOMER-BUFFER'), phase, 'CRANE-CUSTOMER');
    case 'OPS-FLATBED-A-CARGO': return deck(shipmentVehiclePose(shipment, elapsedMs) ?? pose(road, 0, 'cargo', 'FLATBED-A'));
    case 'OPS-SHIP-A-CARGO': return deck(shipmentVehiclePose(shipment, elapsedMs) ?? pose(sea, 0, 'cargo', 'SHIP-A'));
    case 'OPS-CUSTOMER-BUFFER': return at(material.location_id, 'destination');
    default: return at(material.location_id, 'source');
  }
}
export function transferPose(material: Material, world: World, elapsedMs: number): TransportPose | null {
  if (!material.active) return null;
  const transfer = world.transfers.find(row => row.material_id === material.id && row.status !== 'ARRIVED');
  if (transfer) {
    const destination = transfer.to_location_id === 'OPS-WAREHOUSE-ENTRY' ? 'OPS-WAREHOUSE-BUFFER' : transfer.to_location_id;
    return internalTransferPose(transfer, elapsedMs,
      storagePosition(material, world, { id: transfer.from_location_id, position: locationPosition(transfer.from_location_id) }, transfer.status === 'WAITING' ? elapsedMs : transfer.phase_start_ms ?? elapsedMs),
      storagePosition(material, world, { id: destination, position: locationPosition(destination) }, transfer.phase_end_ms ?? elapsedMs));
  }
  const member = world.shipment_materials.find(row => row.material_id === material.id && row.active);
  const shipment = member && world.shipments.find(row => row.id === member.shipment_id);
  return shipment ? outboundPose(material, { world, shipment }, elapsedMs) : null;
}
export function transferVehiclePose(transfer: Transfer, elapsedMs: number): TransportPose | null {
  if (transfer.mode === 'roller' || transfer.status === 'WAITING' || transfer.status === 'ARRIVED') return null;
  if (transfer.status === 'IN_TRANSIT') return internalTransferPose(transfer, elapsedMs);
  const path = factoryLayout.paths.find(row => row.from_location_id === transfer.from_location_id && row.to_location_id === transfer.to_location_id);
  if (!path) throw new LayoutReferenceError(transfer.id);
  return pose(path.points.map(raised), transfer.status === 'LOADING' ? 0 : 1, 'cargo', transfer.vehicle_id);
}
