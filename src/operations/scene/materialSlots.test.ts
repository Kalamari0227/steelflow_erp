import { describe, expect, it } from 'vitest';
import { testWorld } from '../testWorld';
import { processPose } from './processPose';
import { shipmentVehiclePose, transferPose } from './transferPose';
import { distance } from './layout';
import { MaterialSchema, OperationsShipmentSchema, ShipmentMaterialSchema } from '../contracts';

describe('actual persistent material slots', () => {
  it('separates source bodies and keeps remaining bodies fixed when one leaves', () => {
    const base = testWorld(), first = base.materials[0];
    if (!first) throw new Error('Missing fixture');
    const materials = [first, { ...first, id: 'other-material', lineage_id: 'other-lineage' }].map(row => MaterialSchema.parse({ ...row, location_id: 'OPS-ORE-SOURCE-BUFFER' }));
    const world = { ...base, materials, processes: [], transfers: [] };
    const positions = materials.map(row => processPose(row, world, 0).position);
    expect(distance(positions[0] ?? [0, 0, 0], positions[1] ?? [0, 0, 0])).toBeGreaterThan(1.5);
    const remaining = materials[1];
    if (!remaining) throw new Error('Missing second material');
    const moved = { ...world, materials: materials.map((row, index) => index === 0 ? MaterialSchema.parse({ ...row, location_id: 'OPS-CHARGE-A-ENTRY' }) : row) };
    expect(processPose(remaining, moved, 0).position).toEqual(positions[1]);
  });
  it('gives two actual shipment bodies separate deck slots', () => {
    const base = testWorld(), first = base.materials[0];
    if (!first) throw new Error('Missing fixture');
    const materials = [first, { ...first, id: 'second', lineage_id: 'second-lineage' }].map(row => MaterialSchema.parse({ ...row, location_id: 'OPS-FLATBED-A-CARGO', form: 'GA_COIL' }));
    const shipment = OperationsShipmentSchema.parse({ run_id: base.run.id, id: 'shipment', order_id: 'order', status: 'DISPATCHED', location_id: 'OPS-FLATBED-A-CARGO', capacity_kg: 50000, phase_start_ms: 0, phase_end_ms: 1000 });
    const members = materials.map(row => ShipmentMaterialSchema.parse({ run_id: base.run.id, id: row.id, shipment_id: shipment.id, material_id: row.id, active: true, loaded: true }));
    const world = { ...base, materials, processes: [], transfers: [], shipments: [shipment], shipment_materials: members };
    const positions = materials.map(row => transferPose(row, world, 500)?.position);
    expect(distance(positions[0] ?? [0, 0, 0], positions[1] ?? [0, 0, 0])).toBeGreaterThan(1.4);
    for (const [status, location] of [['DISPATCHED', 'OPS-FLATBED-A-CARGO'], ['IN_TRANSIT', 'OPS-SHIP-A-CARGO']]) {
      const moving = OperationsShipmentSchema.parse({ ...shipment, status, location_id: location });
      for (let time = 0; time <= 1000; time += 5) {
        const vehicle = shipmentVehiclePose(moving, time);
        if (!vehicle) throw new Error('Missing moving carrier');
        for (const material of materials) {
          const cargo = transferPose(MaterialSchema.parse({ ...material, location_id: location }), { ...world, shipments: [moving] }, time);
          if (!cargo) throw new Error('Missing cargo');
          const dx = cargo.position[0] - vehicle.position[0], dz = cargo.position[2] - vehicle.position[2];
          const localX = Math.cos(vehicle.rotationY) * dx - Math.sin(vehicle.rotationY) * dz;
          const localZ = Math.sin(vehicle.rotationY) * dx + Math.cos(vehicle.rotationY) * dz;
          expect(Math.abs(localX)).toBeCloseTo(0.75, 8);
          expect(localZ).toBeCloseTo(0, 8);
          expect(cargo.position[1]).toBe(vehicle.position[1]);
        }
      }
    }
    for (const material of materials) {
      const stages = [
        ['LOADING', 'OPS-WAREHOUSE-BUFFER', 'OPS-CRANE-WAREHOUSE-HOOK'],
        ['DISPATCHED', 'OPS-FLATBED-A-CARGO', 'OPS-FLATBED-A-CARGO'],
        ['AT_PORT', 'OPS-PORT-BUFFER', 'OPS-CRANE-PORT-HOOK'],
        ['IN_TRANSIT', 'OPS-SHIP-A-CARGO', 'OPS-SHIP-A-CARGO'],
        ['IN_TRANSIT', 'OPS-CUSTOMER-ENTRY', 'OPS-CRANE-CUSTOMER-HOOK'],
        ['DELIVERED', 'OPS-CUSTOMER-BUFFER', 'OPS-CUSTOMER-BUFFER'],
      ];
      const endpoints = stages.map(([status, location, custody]) => {
        const current = MaterialSchema.parse({ ...material, location_id: custody });
        const state = { ...world, shipments: [OperationsShipmentSchema.parse({ ...shipment, status, location_id: location })] };
        const start = transferPose(current, state, 0), end = transferPose(current, state, 1000);
        if (!start || !end) throw new Error('Missing body pose');
        return { start, end };
      });
      endpoints.slice(1).forEach((endpoint, index) => {
        const previous = endpoints[index];
        if (!previous) throw new Error('Missing endpoint');
        expect(distance(previous.end.position, endpoint.start.position)).toBeLessThan(0.01);
      });
    }
  });
});
