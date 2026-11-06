import { z } from 'zod';
import { finiteNumber, pointSchema, sizeSchema } from './worldContractMath';
import { requireContract } from './worldContractJson';
import type { FactoryWorld } from './worldContract';

const id = z.string().regex(/^[A-Za-z0-9][A-Za-z0-9_.:-]*(?![\s\S])/);
const location = z.string().regex(/^v2:[A-Za-z0-9][A-Za-z0-9_.:-]*(?![\s\S])/);
const ids = z.array(id).readonly(), refs = z.array(id).min(1).readonly();
const locations = z.array(location).min(1).readonly();
const mode = z.enum(['road', 'rail', 'hot_metal', 'ladle', 'roller', 'conveyor', 'sea']);
const positive = finiteNumber.positive(), nonnegative = finiteNumber.nonnegative();
const zone = z.strictObject({ id, name: z.string().min(1), owner_ids: ids }).readonly();
const hall = z.strictObject({ id, zone_id: id, footprint_id: id }).readonly();
const opening = z.strictObject({ id, hall_id: id, interior_id: id, node_id: location, width_m: positive, height_m: positive, mode, profile_ids: refs }).readonly();
const profile = z.strictObject({
  id, kind: z.enum(['truck', 'slab-carrier', 'coil-carrier', 'forklift', 'torpedo', 'ladle-car', 'locomotive', 'railcar', 'ship', 'conveyor', 'roller']),
  mode, size_m: sizeSchema, load_size_m: sizeSchema, body_offset_m: pointSchema, load_offset_m: pointSchema, clearance_m: nonnegative, min_turn_radius_m: nonnegative,
  consist_length_m: positive, reverse_allowed: z.boolean(),
}).readonly();
const policy = z.strictObject({ id, segment_id: id, width_m: positive, height_m: positive, profile_ids: refs, stop_ids: ids, rail_block_ids: ids, berth_ids: ids }).readonly();
const access = z.strictObject({ id, interior_id: id, opening_ids: refs, segment_ids: refs, profile_ids: refs, mode }).readonly();
const stop = z.strictObject({ id, node_id: location, kind: z.enum(['stop', 'gate', 'staging', 'holding', 'loading', 'unloading']), profile_ids: refs }).readonly();
const block = z.strictObject({ id, segment_ids: refs, usable_length_m: positive, clearance_m: nonnegative, reverse_allowed: z.boolean() }).readonly();
const berth = z.strictObject({ id, segment_ids: refs, port_ids: locations, usable_length_m: positive, depth_m: positive }).readonly();
const reach = z.strictObject({ id, owner_id: id, socket_id: id, pick_port_ids: locations, drop_port_ids: locations, max_radius_m: positive, min_height_m: finiteNumber, max_height_m: finiteNumber }).readonly();
const parking = z.strictObject({ id, slot_id: location, profile_id: id, capacity_positions: z.number().int().positive().max(Number.MAX_SAFE_INTEGER) }).readonly();
const coverage = z.strictObject({
  id, kind: z.enum(['equipment', 'stage', 'hall', 'source_function', 'compiled_step', 'connection', 'asset_kind']), source_id: z.string().min(1),
  product_ids: ids, owner_id: id, socket_id: id, port_ids: z.array(location).readonly(), segment_ids: ids,
}).readonly();
const route = z.strictObject({ id, profile_id: id, kind: z.enum(['loaded', 'empty_return', 'holding']), from_node_id: location, to_node_id: location, segment_ids: refs }).readonly();
export const worldSpatialSchema = z.strictObject({
  schema_version: z.literal(1), zones: z.array(zone).readonly(), halls: z.array(hall).readonly(), openings: z.array(opening).readonly(),
  profiles: z.array(profile).readonly(), segment_policies: z.array(policy).readonly(), interior_access: z.array(access).readonly(),
  stops: z.array(stop).readonly(), rail_blocks: z.array(block).readonly(), berths: z.array(berth).readonly(), crane_reaches: z.array(reach).readonly(),
  parking: z.array(parking).readonly(), coverage: z.array(coverage).readonly(), routes: z.array(route).readonly(),
}).readonly();
export type WorldSpatial = z.infer<typeof worldSpatialSchema>;

function unique(values: readonly unknown[], reference: string): void {
  requireContract(new Set(values).size === values.length, 'duplicate', reference);
}
function lookup<T extends { readonly id: string }>(rows: readonly T[], key: string): T {
  const row = rows.find(item => item.id === key);
  requireContract(row !== undefined, 'reference', key);
  return row;
}

export function validateSpatial(spatial: WorldSpatial, world: FactoryWorld): void {
  for (const [name, rows] of Object.entries(spatial)) {
    if (typeof rows === 'number') continue;
    unique(rows.map(row => row.id), name);
    for (const row of rows) for (const [field, values] of Object.entries(row)) {
      if (field.endsWith('_ids') && Array.isArray(values) && !(name === 'routes' && field === 'segment_ids')) unique(values, row.id);
    }
  }
  const modes = { truck: 'road', 'slab-carrier': 'road', 'coil-carrier': 'road', forklift: 'road', torpedo: 'hot_metal', 'ladle-car': 'ladle', locomotive: 'rail', railcar: 'rail', ship: 'sea', conveyor: 'conveyor', roller: 'roller' } as const;
  for (const row of spatial.profiles) {
    requireContract(row.mode === modes[row.kind], 'mode', row.id);
    requireContract(row.consist_length_m >= row.size_m[0], 'dimension', row.id);
  }
  for (const row of spatial.zones) for (const key of row.owner_ids) lookup(world.owners, key);
  unique(spatial.halls.map(row => row.footprint_id), 'hall footprint');
  for (const row of spatial.halls) {
    const zone = lookup(spatial.zones, row.zone_id), footprint = lookup(world.footprints, row.footprint_id);
    requireContract(zone.owner_ids.includes(footprint.owner_id), 'reference', row.id);
  }
  for (const row of spatial.openings) {
    const hall = lookup(spatial.halls, row.hall_id), interior = lookup(world.allowed_interiors, row.interior_id);
    requireContract(interior.footprint_id === hall.footprint_id, 'reference', row.id);
    requireContract(lookup(world.nodes, row.node_id).modes.includes(row.mode), 'mode', row.id);
    for (const key of row.profile_ids) requireContract(lookup(spatial.profiles, key).mode === row.mode, 'mode', row.id);
  }
  for (const row of spatial.stops) {
    const node = lookup(world.nodes, row.node_id);
    for (const key of row.profile_ids) requireContract(node.modes.includes(lookup(spatial.profiles, key).mode), 'mode', row.id);
  }
  for (const row of spatial.rail_blocks) {
    const modes = new Set(row.segment_ids.map(key => lookup(world.segments, key).mode));
    requireContract(modes.size === 1 && [...modes].every(mode => ['rail', 'hot_metal', 'ladle'].includes(mode)), 'mode', row.id);
  }
  for (const row of spatial.berths) {
    for (const key of row.segment_ids) requireContract(lookup(world.segments, key).mode === 'sea', 'mode', row.id);
    for (const key of row.port_ids) requireContract(lookup(world.ports, key).modes.includes('sea'), 'mode', row.id);
  }
  unique(spatial.segment_policies.map(row => row.segment_id), 'segment policy');
  for (const row of spatial.segment_policies) {
    const segment = lookup(world.segments, row.segment_id);
    for (const key of row.profile_ids) requireContract(lookup(spatial.profiles, key).mode === segment.mode, 'mode', row.id);
    for (const key of row.stop_ids) {
      const stop = lookup(spatial.stops, key);
      requireContract(stop.node_id === segment.from_node_id || stop.node_id === segment.to_node_id, 'reference', row.id);
      requireContract(row.profile_ids.every(key => stop.profile_ids.includes(key)), 'reference', row.id);
    }
    for (const key of row.rail_block_ids) requireContract(lookup(spatial.rail_blocks, key).segment_ids.includes(segment.id), 'reference', row.id);
    for (const key of row.berth_ids) requireContract(lookup(spatial.berths, key).segment_ids.includes(segment.id), 'reference', row.id);
  }
  for (const row of spatial.interior_access) {
    lookup(world.allowed_interiors, row.interior_id);
    const endpoints = new Set<string>();
    for (const key of row.segment_ids) {
      const segment = lookup(world.segments, key);
      requireContract(segment.mode === row.mode, 'mode', row.id);
      endpoints.add(segment.from_node_id); endpoints.add(segment.to_node_id);
    }
    for (const key of row.profile_ids) requireContract(lookup(spatial.profiles, key).mode === row.mode, 'mode', row.id);
    for (const key of row.opening_ids) {
      const opening = lookup(spatial.openings, key);
      requireContract(opening.interior_id === row.interior_id && endpoints.has(opening.node_id), 'reference', row.id);
      requireContract(opening.mode === row.mode, 'mode', row.id);
      requireContract(row.profile_ids.every(key => opening.profile_ids.includes(key)), 'reference', row.id);
    }
  }
  for (const row of spatial.crane_reaches) {
    const owner = lookup(world.owners, row.owner_id);
    requireContract(owner.kind === 'equipment' || owner.kind === 'hook', 'reference', row.id);
    lookup(owner.sockets, row.socket_id);
    requireContract(row.max_height_m >= row.min_height_m, 'dimension', row.id);
    for (const key of [...row.pick_port_ids, ...row.drop_port_ids]) lookup(world.ports, key);
  }
  unique(spatial.parking.map(row => row.slot_id), 'parking slot');
  for (const row of spatial.parking) {
    const slot = lookup(world.slots, row.slot_id), profile = lookup(spatial.profiles, row.profile_id);
    requireContract(lookup(world.nodes, slot.node_id).modes.includes(profile.mode), 'mode', row.id);
  }
  for (const row of spatial.coverage) {
    lookup(lookup(world.owners, row.owner_id).sockets, row.socket_id);
    for (const key of row.port_ids) lookup(world.ports, key);
    for (const key of row.segment_ids) lookup(world.segments, key);
  }
  for (const row of spatial.routes) {
    const profile = lookup(spatial.profiles, row.profile_id);
    requireContract(lookup(world.nodes, row.from_node_id).modes.includes(profile.mode) && lookup(world.nodes, row.to_node_id).modes.includes(profile.mode), 'mode', row.id);
    let current = row.from_node_id;
    for (const key of row.segment_ids) {
      const segment = lookup(world.segments, key);
      requireContract(segment.mode === profile.mode, 'mode', row.id);
      requireContract(segment.from_node_id === current, 'endpoint', row.id);
      current = segment.to_node_id;
    }
    requireContract(current === row.to_node_id, 'endpoint', row.id);
  }
}
