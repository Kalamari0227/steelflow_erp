import { z } from 'zod';
import { validateSpatial, worldSpatialSchema } from './worldSpatialContract';
import { parseContractJson, requireContract } from './worldContractJson';
import { CONTACT_TOLERANCE_M, composePose, distance, finiteNumber, insideEnvelope, pointSchema, poseSchema, sizeSchema, transformPoint } from './worldContractMath';

export { WorldContractError } from './worldContractJson';
export { businessEpochMs, composePose, contactDistance, contactWithinTolerance, DATE_LIMIT_MS, EPOCH_MS, CONTACT_TOLERANCE_M, mmToM, phaseAt, supportPose, transformPoint, wallToSimMs } from './worldContractMath';
export type { Point, Pose } from './worldContractMath';
export { canonicalManifest, parseBundle, parseManifest, sha256 } from './worldContractBundle';

export const entityIdSchema = z.string().regex(/^[A-Za-z0-9][A-Za-z0-9_.:-]*(?![\s\S])/).brand('EntityId');
const locationId = z.string().regex(/^v2:[A-Za-z0-9][A-Za-z0-9_.:-]*(?![\s\S])/).brand('EntityId');
const modeSchema = z.enum(['road', 'rail', 'hot_metal', 'ladle', 'roller', 'conveyor', 'sea']);
const modes = z.array(modeSchema).min(1).readonly();
const socketSchema = z.strictObject({ id: entityIdSchema, pose: poseSchema }).readonly();
const ownerSchema = z.strictObject({
  id: entityIdSchema, kind: z.enum(['equipment', 'vehicle', 'railcar', 'ship', 'hook', 'customer']),
  pose: poseSchema, sockets: z.array(socketSchema).min(1).readonly(), modes,
}).readonly();
const slotFields = {
  id: locationId, owner_id: entityIdSchema, socket_id: entityIdSchema, node_id: locationId,
  capacity_kg: z.number().int().positive().max(Number.MAX_SAFE_INTEGER).brand('Kilograms'),
};
const footprintFields = { id: entityIdSchema, owner_id: entityIdSchema, pose: poseSchema, size_m: sizeSchema };
const worldShape = z.strictObject({
  spatial: worldSpatialSchema.optional(),
  version: z.literal(2), units: z.literal('m'), up_axis: z.literal('Y'), forward_axis: z.literal('+X'), yaw_unit: z.literal('rad'),
  nodes: z.array(z.strictObject({ id: locationId, position: pointSchema, modes }).readonly()).min(1).readonly(),
  segments: z.array(z.strictObject({
    id: entityIdSchema, from_node_id: locationId, to_node_id: locationId, mode: modeSchema,
    points: z.array(pointSchema).min(2).readonly(), conflict_zone_ids: z.array(entityIdSchema).readonly(), speed_m_per_sim_s: finiteNumber.positive(),
  }).readonly()).readonly(),
  conflict_zones: z.array(z.strictObject({ id: entityIdSchema, segment_ids: z.array(entityIdSchema).min(1).readonly() }).readonly()).readonly(),
  owners: z.array(ownerSchema).min(1).readonly(),
  slots: z.array(z.strictObject(slotFields).readonly()).readonly(),
  ports: z.array(z.strictObject({ ...slotFields, modes }).readonly()).readonly(),
  footprints: z.array(z.strictObject(footprintFields).readonly()).min(1).readonly(),
  allowed_interiors: z.array(z.strictObject({ ...footprintFields, footprint_id: entityIdSchema }).readonly()).readonly(),
}).readonly();
export type FactoryWorld = z.infer<typeof worldShape>;
export type Mode = z.infer<typeof modeSchema>;
export type Owner = z.infer<typeof ownerSchema>;
const ownerModes = {
  equipment: modeSchema.options, hook: modeSchema.options, customer: modeSchema.options,
  vehicle: ['road', 'rail', 'hot_metal', 'ladle'], railcar: ['rail', 'hot_metal', 'ladle'], ship: ['sea'],
} as const satisfies Record<Owner['kind'], readonly Mode[]>;

function unique(values: readonly string[], reference: string): void {
  requireContract(new Set(values).size === values.length, 'duplicate', reference);
}
function lookup<T extends { readonly id: string }>(rows: readonly T[], id: string): T {
  const row = rows.find(item => item.id === id);
  requireContract(row !== undefined, 'reference', id);
  return row;
}

export function parseFactoryWorld(input: unknown): FactoryWorld {
  const world = worldShape.parse(input);
  for (const key of ['nodes', 'segments', 'conflict_zones', 'owners', 'slots', 'ports', 'footprints', 'allowed_interiors'] as const) unique(world[key].map(row => row.id), key);
  unique([...world.nodes, ...world.slots, ...world.ports].map(row => row.id), 'locations');
  for (const node of world.nodes) unique(node.modes, node.id);
  for (const owner of world.owners) {
    unique(owner.sockets.map(socket => socket.id), owner.id);
    unique(owner.modes, owner.id);
    const allowed: readonly Mode[] = ownerModes[owner.kind];
    requireContract(owner.modes.every(mode => allowed.includes(mode)), 'mode', owner.id);
    requireContract(world.footprints.some(row => row.owner_id === owner.id), 'reference', `${owner.id}:footprint`);
  }
  for (const segment of world.segments) {
    const from = lookup(world.nodes, segment.from_node_id), to = lookup(world.nodes, segment.to_node_id);
    requireContract(from.id !== to.id, 'endpoint', segment.id);
    requireContract(from.modes.includes(segment.mode) && to.modes.includes(segment.mode), 'mode', segment.id);
    const first = segment.points[0], last = segment.points.at(-1);
    requireContract(first !== undefined && last !== undefined, 'endpoint', segment.id);
    requireContract(distance(first, from.position) <= CONTACT_TOLERANCE_M && distance(last, to.position) <= CONTACT_TOLERANCE_M, 'endpoint', segment.id);
    requireContract(segment.points.some(point => distance(point, first) > 0), 'endpoint', segment.id);
    unique(segment.conflict_zone_ids, segment.id);
    for (const id of segment.conflict_zone_ids) requireContract(lookup(world.conflict_zones, id).segment_ids.includes(segment.id), 'reference', id);
  }
  for (const zone of world.conflict_zones) {
    unique(zone.segment_ids, zone.id);
    for (const id of zone.segment_ids) requireContract(lookup(world.segments, id).conflict_zone_ids.includes(zone.id), 'reference', id);
  }
  for (const location of [...world.slots, ...world.ports]) {
    const owner = lookup(world.owners, location.owner_id), node = lookup(world.nodes, location.node_id);
    const socket = lookup(owner.sockets, location.socket_id);
    requireContract(node.modes.every(mode => owner.modes.includes(mode)), 'mode', location.id);
    requireContract(distance(composePose(socket.pose, owner.pose).position, node.position) <= CONTACT_TOLERANCE_M, 'contact', location.id);
  }
  for (const port of world.ports) {
    unique(port.modes, port.id);
    const owner = lookup(world.owners, port.owner_id), node = lookup(world.nodes, port.node_id);
    requireContract(port.modes.every(mode => owner.modes.includes(mode) && node.modes.includes(mode)), 'mode', port.id);
  }
  for (const footprint of world.footprints) lookup(world.owners, footprint.owner_id);
  for (const interior of world.allowed_interiors) {
    const footprint = lookup(world.footprints, interior.footprint_id);
    requireContract(interior.owner_id === footprint.owner_id, 'reference', interior.id);
    for (const x of [-1, 1]) for (const y of [-1, 1]) for (const z of [-1, 1]) {
      const corner = transformPoint([x * interior.size_m[0] / 2, y * interior.size_m[1] / 2, z * interior.size_m[2] / 2], interior.pose);
      requireContract(insideEnvelope(corner, footprint.pose, footprint.size_m), 'envelope', interior.id);
    }
  }
  if (world.spatial !== undefined) validateSpatial(world.spatial, world);
  return world;
}

export function parseWorld(raw: string): FactoryWorld { return parseFactoryWorld(parseContractJson(raw)); }
