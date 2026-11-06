import { mkdirSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { describe, expect, it } from 'vitest';
import { TransferSchema, MaterialSchema, OperationsShipmentSchema, ShipmentMaterialSchema } from '../contracts';
import { testWorld } from '../testWorld';
import { factoryLayout, distance } from './layout';
import { processPose } from './processPose';
import { internalTransferPose, locationPosition, shipmentVehiclePose, transferPose, transportPhase, transferVehiclePose } from './transferPose';

function transfer(path = factoryLayout.paths.find(row => row.mode === 'flatbed')) {
  if (!path) throw new Error('Missing layout path');
  return TransferSchema.parse({ run_id: 'run-test', id: path.id, material_id: 'MAT-ga', from_location_id: path.from_location_id, to_location_id: path.to_location_id, mode: path.mode, vehicle_id: path.vehicle_id, crane_id: path.pickup_crane_id, status: 'LOADING', phase_start_ms: 0, phase_end_ms: 1000, capacity_kg: 25000 });
}
function outbound(status: string, location: string, memberLocation: string) {
  const base = testWorld();
  const shipment = OperationsShipmentSchema.parse({ run_id: base.run.id, id: 'SHIPMENT-ga-01', order_id: 'ORD-ga', status, location_id: location, capacity_kg: 50000, phase_start_ms: 0, phase_end_ms: 1000 });
  const material = MaterialSchema.parse({ ...base.materials[0], location_id: memberLocation });
  const member = ShipmentMaterialSchema.parse({ run_id: base.run.id, id: 'member', shipment_id: shipment.id, material_id: material.id, active: true, loaded: false });
  return { material, world: { ...base, materials: [material], shipments: [shipment], shipment_materials: [member] } };
}

describe('canonical transport poses', () => {
  it('unloads packaged cargo into its own warehouse slot without jumping on stock receipt', () => {
    const base = testWorld();
    const first = base.materials[0];
    if (!first) throw new Error('Missing fixture material');
    const path = factoryLayout.paths.find(row => row.id === 'PATH-PACKAGING--WAREHOUSE');
    expect(path?.mode).toBe('flatbed');
    const row = { ...transfer(path), material_id: first.id, status: 'UNLOADING' as const };
    const material = MaterialSchema.parse({ ...base.materials[0], location_id: 'OPS-CRANE-WAREHOUSE-HOOK' });
    const world = { ...base, materials: [material], processes: [], transfers: [row], shipments: [], shipment_materials: [] };
    const moving = transferPose(material, world, 1000);
    const stocked = MaterialSchema.parse({ ...material, location_id: 'OPS-WAREHOUSE-BUFFER' });
    const after = processPose(stocked, { ...world, materials: [stocked], transfers: [] }, 1000);
    expect(moving?.position).toEqual(after.position);
    expect(transferPose(material, world, 500)?.custody).toBe('hook');
  });
  it('travels steadily between acceleration and braking, with exact handoff endpoints', () => {
    const window = { phase_start_ms: 0, phase_end_ms: 1000 };
    expect(transportPhase(window, -100)).toBe(0);
    expect(transportPhase(window, 1000)).toBe(1);
    const intervals = [200, 400, 600].map(time => transportPhase(window, time + 200) - transportPhase(window, time));
    intervals.forEach(value => expect(value).toBeCloseTo(2 / 9));
    expect(transportPhase(window, 50)).toBeLessThan(transportPhase(window, 150) / 2);
  });
  it('keeps all five phase endpoints continuous on every non-roller path', () => {
    const anchors = factoryLayout.paths.filter(path => path.mode !== 'roller' && path.mode !== 'ship').map(path => {
      const row = transfer(path);
      const waiting = internalTransferPose({ ...row, status: 'WAITING' }, 0);
      const loadingStart = internalTransferPose(row, 0), loadingEnd = internalTransferPose(row, 1000);
      const transitStart = internalTransferPose({ ...row, status: 'IN_TRANSIT' }, 0), transitEnd = internalTransferPose({ ...row, status: 'IN_TRANSIT' }, 1000);
      const unloadingStart = internalTransferPose({ ...row, status: 'UNLOADING' }, 0), unloadingEnd = internalTransferPose({ ...row, status: 'UNLOADING' }, 1000);
      const arrived = internalTransferPose({ ...row, status: 'ARRIVED' }, 1000);
      const gaps = [distance(waiting.position, loadingStart.position), distance(loadingEnd.position, transitStart.position), distance(transitEnd.position, unloadingStart.position), distance(unloadingEnd.position, arrived.position)];
      expect(Math.max(...gaps)).toBeLessThan(0.01);
      expect(internalTransferPose(row, 500).position[1]).toBeGreaterThan(waiting.position[1] + 2);
      return { path: path.id, gaps, phases: [waiting, loadingStart, transitStart, unloadingStart, arrived] };
    });
    const directory = process.env['T15_EVIDENCE_DIR'];
    if (directory) { mkdirSync(directory, { recursive: true }); writeFileSync(join(directory, 'T15-anchor-distance.json'), JSON.stringify(anchors, null, 2)); }
  });
  it('distinguishes torpedo, ladle and flatbed and never places roller material on a truck', () => {
    for (const mode of ['hot_metal_car', 'ladle_car', 'flatbed', 'roller'] as const) {
      const row = { ...transfer(factoryLayout.paths.find(path => path.mode === mode)), status: 'IN_TRANSIT' as const };
      const material = internalTransferPose(row, 500);
      expect(material.carrierId).toBe(row.vehicle_id);
      expect(material.custody).toBe(mode === 'roller' ? 'roller' : 'cargo');
      expect(transferVehiclePose(row, 500) === null).toBe(mode === 'roller');
    }
  });
  it('holds a blocked waiting material at source and rejects zero-duration phases', () => {
    const row = transfer();
    expect(internalTransferPose({ ...row, status: 'WAITING' }, 999999).position).toEqual(locationPosition(row.from_location_id));
    expect(() => transportPhase({ phase_start_ms: 10, phase_end_ms: 10 }, 10)).toThrow('positive duration');
    expect(() => TransferSchema.parse({ ...row, phase_end_ms: 0 })).toThrow();
    expect(internalTransferPose(row, 1000)).toEqual(internalTransferPose(row, 999999));
  });
  it('keeps shipment members at their own current-leg hook, cargo or buffer', () => {
    const rows = [
      ['LOADING', 'OPS-WAREHOUSE-BUFFER', 'OPS-CRANE-WAREHOUSE-HOOK', 'hook', 'CRANE-WAREHOUSE'],
      ['LOADING', 'OPS-WAREHOUSE-BUFFER', 'OPS-FLATBED-A-CARGO', 'cargo', 'FLATBED-A'],
      ['AT_PORT', 'OPS-PORT-BUFFER', 'OPS-CRANE-PORT-HOOK', 'hook', 'CRANE-PORT'],
      ['AT_PORT', 'OPS-PORT-BUFFER', 'OPS-SHIP-A-CARGO', 'cargo', 'SHIP-A'],
      ['AT_PORT', 'OPS-PORT-BUFFER', 'OPS-PORT-BUFFER', 'source', null],
      ['IN_TRANSIT', 'OPS-CUSTOMER-ENTRY', 'OPS-CRANE-CUSTOMER-HOOK', 'hook', 'CRANE-CUSTOMER'],
      ['IN_TRANSIT', 'OPS-CUSTOMER-ENTRY', 'OPS-CUSTOMER-BUFFER', 'destination', null],
      ['DELIVERED', 'OPS-CUSTOMER-BUFFER', 'OPS-CUSTOMER-BUFFER', 'destination', null],
    ];
    for (const [status, location, memberLocation, custody, carrier] of rows) {
      if (!status || !location || !memberLocation) throw new Error('Missing test row');
      const { material, world } = outbound(status, location, memberLocation);
      const result = transferPose(material, world, 500);
      expect(result?.custody).toBe(custody); expect(result?.carrierId).toBe(carrier);
      const loadedWorld = { ...world, shipment_materials: world.shipment_materials.map(member => ({ ...member, loaded: true })) };
      expect(transferPose(material, loadedWorld, 500)).toEqual(result);
    }
  });
  it('does not duplicate the ship for port shipments awaiting the occupied carrier', () => {
    const waiting = outbound('AT_PORT', 'OPS-PORT-BUFFER', 'OPS-PORT-BUFFER').world.shipments[0];
    const sailing = outbound('IN_TRANSIT', 'OPS-SHIP-A-CARGO', 'OPS-SHIP-A-CARGO').world.shipments[0];
    if (!waiting || !sailing) throw new Error('Missing shipment fixture');
    const poses = [{ ...waiting, phase_end_ms: null }, sailing].map(row => shipmentVehiclePose(row, 500)).filter(row => row !== null);
    expect(poses).toHaveLength(1);
    expect(poses[0]?.carrierId).toBe('SHIP-A');
  });
  it('connects factory, port and customer member handoffs without inferring from the first member', () => {
    const stages = [
      ['LOADING', 'OPS-WAREHOUSE-BUFFER', 'OPS-CRANE-WAREHOUSE-HOOK'],
      ['DISPATCHED', 'OPS-FLATBED-A-CARGO', 'OPS-FLATBED-A-CARGO'],
      ['AT_PORT', 'OPS-PORT-BUFFER', 'OPS-CRANE-PORT-HOOK'],
      ['IN_TRANSIT', 'OPS-SHIP-A-CARGO', 'OPS-SHIP-A-CARGO'],
      ['IN_TRANSIT', 'OPS-CUSTOMER-ENTRY', 'OPS-CRANE-CUSTOMER-HOOK'],
      ['DELIVERED', 'OPS-CUSTOMER-BUFFER', 'OPS-CUSTOMER-BUFFER'],
    ];
    const poses = stages.map(([state, location, member]) => {
      if (!state || !location || !member) throw new Error('Missing stage');
      const { material, world } = outbound(state, location, member);
      const start = transferPose(material, world, 0), end = transferPose(material, world, 1000);
      if (!start || !end) throw new Error('Missing pose');
      return { start, end };
    });
    poses.slice(1).forEach((row, index) => { const previous = poses[index]; if (!previous) throw new Error('Missing pose'); expect(distance(previous.end.position, row.start.position)).toBeLessThan(0.01); });
    const { world } = outbound('DELIVERED', 'OPS-CUSTOMER-BUFFER', 'OPS-CUSTOMER-BUFFER');
    const shipment = world.shipments[0]; if (!shipment) throw new Error('Missing shipment');
    expect(shipmentVehiclePose(shipment, 1000)).toBeNull();
  });
});
