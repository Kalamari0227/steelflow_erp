import { mkdirSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import { describe, expect, it } from 'vitest';
import raw from '../../../shared/factory-layout.json';
import { distance, factoryLayout, parseFactoryLayout, pointOnPolyline, stationAnchorPosition, stationProcessPosition } from './layout';

const products = ['slab', 'bloom', 'billet', 'hr', 'plate', 'wire', 'cr', 'gi', 'ga', 'hgi', 'eg', 'go', 'ngo', 'sts-hr', 'sts-cr', 'sts-plate', 'ti-hr', 'ti-cr', 'ti-sheet', 'ti-plate'];
function fixture() { return structuredClone(raw); }
function required<T>(value: T | undefined): T { expect(value).toBeDefined(); if (value === undefined) throw new RangeError('Missing test fixture'); return value; }
function artifact(name: string, data: unknown) {
  const directory = process.env['T04_EVIDENCE_DIR'];
  if (directory) { mkdirSync(directory, { recursive: true }); writeFileSync(join(directory, name), JSON.stringify(data, null, 2)); }
}

describe('shared physical factory layout', () => {
  it('gives the recovery roller a real path-owned custody location', () => {
    const path = required(factoryLayout.paths.find(item => item.id === 'PATH-HSM-A--HSM-B'));
    const custody = 'custody_location_id' in path ? path.custody_location_id : undefined;
    const location = factoryLayout.locations.find(item => item.id === custody);
    expect(location?.owner_id).toBe(path.id);
    expect(custody).not.toBe(path.to_location_id);
  });

  it.each(['OPS-MISSING', 'OPS-HSM-A-ENTRY'])('rejects invalid recovery custody %s', custody => {
    const invalid = fixture();
    const path = required(invalid.paths.find(item => item.id === 'PATH-HSM-A--HSM-B'));
    Object.assign(path, { custody_location_id: custody });
    expect(() => parseFactoryLayout(invalid)).toThrow();
  });
  it('parses every product into connected upstream, processing and delivery stations', () => {
    // Given: the real shared file. When: parsing at the runtime boundary.
    const layout = parseFactoryLayout(raw);
    // Then: each route is complete and every declared endpoint is physically coincident.
    expect(layout.routes.map(route => route.product_id).sort()).toEqual([...products].sort());
    const endpoints = layout.paths.map(path => {
      const from = required(layout.locations.find(location => location.id === path.from_location_id));
      const to = required(layout.locations.find(location => location.id === path.to_location_id));
      return { id: path.id, start_distance: distance(required(path.points[0]), from.position), end_distance: distance(required(path.points.at(-1)), to.position) };
    });
    expect(endpoints.every(endpoint => endpoint.start_distance < 0.01 && endpoint.end_distance < 0.01)).toBe(true);
    for (const route of layout.routes) expect(route.equipment_ids.at(-1)).toBe('CUSTOMER');
    artifact('T04-layout-ts.json', { parser: 'TypeScript/Zod', equipment: layout.equipment.length, anchors: layout.equipment.length * 4, locations: layout.locations.length, links: endpoints, routes: layout.routes });
  });

  it('places material on every station work anchor at mid-process including returning rows', () => {
    // Given: all actual station transforms. When: traversing entry/work/exit.
    const contacts = factoryLayout.equipment.map(equipment => ({ id: equipment.id,
      entry: distance(stationProcessPosition(factoryLayout, equipment.id, 0), stationAnchorPosition(factoryLayout, equipment.id, 'entry')),
      work: distance(stationProcessPosition(factoryLayout, equipment.id, 0.5), stationAnchorPosition(factoryLayout, equipment.id, 'work')),
      exit: distance(stationProcessPosition(factoryLayout, equipment.id, 1), stationAnchorPosition(factoryLayout, equipment.id, 'exit')),
    }));
    // Then: mesh-local work points remain on the physical route in world coordinates.
    expect(contacts.every(contact => Math.max(contact.entry, contact.work, contact.exit) < 0.01)).toBe(true);
    artifact('T04-contact.json', contacts);
  });

  it('composes rotated stage and station transforms without moving their local work anchor', () => {
    // Given: a rotated station inside a rotated stage.
    const layout = { ...factoryLayout, stages: [{ id: 'test', position: [10, 2, 20] as const, rotation: Math.PI / 2 }], equipment: [{ ...required(factoryLayout.equipment[0]), stage_id: 'test', position: [4, 0, 0] as const, rotation: Math.PI / 2 }] };
    // When: the entry anchor crosses both transforms.
    const point = stationAnchorPosition(layout, required(layout.equipment[0]).id, 'entry');
    // Then: known independently calculated coordinates survive both rotations.
    expect(point[0]).toBeCloseTo(12.6); expect(point[1]).toBeCloseTo(2.94); expect(point[2]).toBeCloseTo(16);
  });

  it('keeps transfers on explicit polyline segments at corners and clamps endpoints', () => {
    // Given: a 3-by-4 right-angle handoff. When: moving exactly three units.
    const points = [[0, 0, 0], [3, 0, 0], [3, 0, 4]] as const;
    const corner = pointOnPolyline(points, 3 / 7);
    // Then: no spline cuts the corner or extrapolates beyond handoff.
    expect(corner).toEqual([3, 0, 0]);
    expect(pointOnPolyline(points, -1)).toEqual([0, 0, 0]);
    expect(pointOnPolyline(points, 2)).toEqual([3, 0, 4]);
  });

  it('routes shared carbon work through HSM-A and retains a physically separate compatible reserve', () => {
    // Given: the real loaded layout. When: resolving the hr-04 source binding and reserve.
    const binding = required(factoryLayout.source_bindings.find(item => item.source_step_id === 'hr-04'));
    const primary = required(factoryLayout.equipment.find(item => item.id === binding.equipment_id));
    const reserve = required(factoryLayout.equipment.find(item => item.id === 'HSM-B'));
    // Then: all inherited carbon HR routes share one primary and roller-connected reserve.
    expect(primary.id).toBe('HSM-A'); expect(reserve.capability).toEqual(primary.capability);
    expect(reserve.capability.input_forms).toContain('HOT_STRIP'); expect(reserve.capacity_kg).toBe(25000);
    expect(reserve.reserve).toBe(true); expect(primary.reserve).toBe(false);
    expect(distance(stationAnchorPosition(factoryLayout, primary.id, 'work'), stationAnchorPosition(factoryLayout, reserve.id, 'work'))).toBeGreaterThan(1);
    for (const product of ['hr', 'cr', 'gi', 'ga', 'hgi', 'eg', 'go', 'ngo']) expect(required(factoryLayout.routes.find(route => route.product_id === product)).equipment_ids).toContain('HSM-A');
    const bypass = required(factoryLayout.paths.find(path => path.id === 'PATH-HSM-A--HSM-B'));
    expect(bypass.mode).toBe('roller');
    expect(distance(required(bypass.points[0]), stationAnchorPosition(factoryLayout, primary.id, 'entry'))).toBeLessThan(0.01);
    expect(distance(required(bypass.points.at(-1)), stationAnchorPosition(factoryLayout, reserve.id, 'entry'))).toBeLessThan(0.01);
  });

  it.each([
    ['missing anchor', (value: ReturnType<typeof fixture>) => { const station = required(value.equipment[0]); Reflect.deleteProperty(station.anchors, 'work'); }],
    ['disconnected path', (value: ReturnType<typeof fixture>) => { const point = required(required(value.paths[0]).points[0]); point[0] = required(point[0]) + 0.02; }],
    ['duplicate location', (value: ReturnType<typeof fixture>) => { value.locations.push(required(value.locations[0])); }],
    ['invalid vehicle path', (value: ReturnType<typeof fixture>) => { required(value.paths.find(path => path.mode === 'flatbed')).vehicle_id = 'LADLE-A'; }],
    ['molten on road', (value: ReturnType<typeof fixture>) => { const path = required(value.paths.find(path => path.mode === 'hot_metal_car')); path.mode = 'flatbed'; path.network = 'road'; path.vehicle_id = 'FLATBED-A'; }],
    ['missing crane custody', (value: ReturnType<typeof fixture>) => { Reflect.deleteProperty(required(value.cranes[0]), 'location_id'); }],
    ['undersized vehicle', (value: ReturnType<typeof fixture>) => { required(value.vehicles.find(vehicle => vehicle.mode === 'flatbed')).capacity_kg = 1; }],
    ['missing cargo anchor', (value: ReturnType<typeof fixture>) => { Reflect.deleteProperty(required(value.vehicles[0]), 'cargo_anchor'); }],
    ['wrong crane handoff', (value: ReturnType<typeof fixture>) => { required(value.paths.find(path => path.mode === 'flatbed')).pickup_crane_id = 'CRANE-HSM-A'; }],
    ['disconnected route', (value: ReturnType<typeof fixture>) => { required(value.routes[0]).path_ids[0] = 'PATH-HSM-A--HSM-B'; }],
    ['nonfinite anchor', (value: ReturnType<typeof fixture>) => { required(value.equipment[0]).anchors.work.position[0] = NaN; }],
    ['duplicate source', (value: ReturnType<typeof fixture>) => { value.source_bindings.push(required(value.source_bindings[0])); }],
  ])('rejects %s before a scene can use the layout', (name, mutate) => {
    // Given: an independently damaged copy of the actual file.
    const invalid = fixture(); mutate(invalid);
    // When/Then: the public parser rejects it, preserving the actual structured error.
    expect(() => parseFactoryLayout(invalid)).toThrow();
    artifact(`T04-invalid-ts-${name.replaceAll(' ', '-')}.json`, { fixture: name, rejected: true });
  });
});
