import { z } from 'zod';
import rawLayout from '../../../shared/factory-layout.json' with { type: 'json' };

const id = z.string().min(1);
const pointSchema = z.tuple([z.number().finite(), z.number().finite(), z.number().finite()]).readonly();
const anchorSchema = z.strictObject({ location_id: id, position: pointSchema }).readonly();
const transformSchema = { position: pointSchema, rotation: z.number().finite() };
const capabilitySchema = z.strictObject({
  input_forms: z.array(id).min(1).readonly(), output_forms: z.array(id).min(1).readonly(),
  material_family: z.enum(['carbon', 'stainless', 'titanium']), grade_scope: z.literal('fixture'),
  width_mm: z.tuple([z.number().nonnegative(), z.number().positive()]).readonly(),
}).readonly();
const equipmentSchema = z.strictObject({
  id, stage_id: id, kind: id, ...transformSchema,
  anchors: z.strictObject({ entry: anchorSchema, work: anchorSchema, exit: anchorSchema, buffer: anchorSchema }).readonly(),
  capacity_kg: z.number().int().positive(), concurrency: z.literal(1), reserve: z.boolean(), capability: capabilitySchema,
}).readonly();
const networkSchema = z.enum(['road', 'rail', 'roller', 'sea']);
const modeSchema = z.enum(['flatbed', 'hot_metal_car', 'ladle_car', 'roller', 'ship']);
const shape = z.strictObject({
  version: z.literal(1), units: z.literal('scene'),
  stages: z.array(z.strictObject({ id, ...transformSchema }).readonly()).min(1).readonly(),
  equipment: z.array(equipmentSchema).min(1).readonly(),
  locations: z.array(z.strictObject({ id, position: pointSchema, owner_id: id }).readonly()).min(1).readonly(),
  cranes: z.array(z.strictObject({ id, location_id: id, pick_location_id: id, drop_location_id: id, capacity_kg: z.number().int().positive() }).readonly()).readonly(),
  vehicles: z.array(z.strictObject({ id, mode: modeSchema, network: networkSchema, capacity_kg: z.number().int().positive(), cargo_anchor: pointSchema, location_id: id }).readonly()).readonly(),
  paths: z.array(z.strictObject({ id, from_location_id: id, to_location_id: id, mode: modeSchema, network: networkSchema, vehicle_id: id.nullable(), pickup_crane_id: id.nullable(), drop_crane_id: id.nullable(), custody_location_id: id.nullable().default(null), points: z.array(pointSchema).min(2).readonly() }).readonly()).readonly(),
  source_bindings: z.array(z.strictObject({ source_step_id: id, equipment_id: id }).readonly()).readonly(),
  routes: z.array(z.strictObject({ product_id: id, equipment_ids: z.array(id).min(2).readonly(), path_ids: z.array(id).min(1).readonly() }).readonly()).min(1).readonly(),
}).readonly();
export type FactoryLayout = z.infer<typeof shape>;
export type Point = z.infer<typeof pointSchema>;
export type Equipment = z.infer<typeof equipmentSchema>;
export type AnchorKind = keyof Equipment['anchors'];
export const ENDPOINT_TOLERANCE = 0.01;
export const transportNetworks = { flatbed: 'road', hot_metal_car: 'rail', ladle_car: 'rail', roller: 'roller', ship: 'sea' } as const;

export class LayoutReferenceError extends Error {
  constructor(readonly reference: string) { super(`Unknown layout reference: ${reference}`); }
}
function required<T>(value: T | undefined, reference: string): T {
  if (value === undefined) throw new LayoutReferenceError(reference);
  return value;
}
export function distance(a: Point, b: Point): number { return Math.hypot(a[0] - b[0], a[1] - b[1], a[2] - b[2]); }
function transform(point: Point, pose: { readonly position: Point; readonly rotation: number }): Point {
  const c = Math.cos(pose.rotation), s = Math.sin(pose.rotation);
  return [pose.position[0] + c * point[0] + s * point[2], pose.position[1] + point[1], pose.position[2] - s * point[0] + c * point[2]];
}
export function stationAnchorPosition(layout: FactoryLayout, equipmentId: string, anchor: AnchorKind): Point {
  const equipment = required(layout.equipment.find(item => item.id === equipmentId), equipmentId);
  const stage = required(layout.stages.find(item => item.id === equipment.stage_id), equipment.stage_id);
  return transform(transform(equipment.anchors[anchor].position, equipment), stage);
}

export const factoryLayoutSchema = shape.superRefine((layout, context) => {
  const issue = (message: string) => context.addIssue({ code: 'custom', message });
  const unique = (values: readonly string[], label: string) => { if (new Set(values).size !== values.length) issue(`duplicate ${label}`); };
  for (const key of ['stages', 'equipment', 'locations', 'cranes', 'vehicles', 'paths'] as const) unique(layout[key].map(item => item.id), key);
  unique(layout.source_bindings.map(item => item.source_step_id), 'source_step_id');
  unique(layout.routes.map(item => item.product_id), 'product_id');
  const stages = new Map(layout.stages.map(item => [item.id, item]));
  const equipment = new Map(layout.equipment.map(item => [item.id, item]));
  const locations = new Map(layout.locations.map(item => [item.id, item]));
  const vehicles = new Map(layout.vehicles.map(item => [item.id, item]));
  const cranes = new Map(layout.cranes.map(item => [item.id, item]));
  const paths = new Map(layout.paths.map(item => [item.id, item]));
  const anchorIds: string[] = [];
  for (const item of layout.equipment) {
    const stage = stages.get(item.stage_id);
    if (!stage) { issue(`missing stage: ${item.id}`); continue; }
    if (item.capability.width_mm[0] >= item.capability.width_mm[1]) issue(`invalid width range: ${item.id}`);
    for (const anchor of Object.values(item.anchors)) {
      anchorIds.push(anchor.location_id);
      const location = locations.get(anchor.location_id);
      if (!location || location.owner_id !== item.id || distance(location.position, transform(transform(anchor.position, item), stage)) >= ENDPOINT_TOLERANCE) issue(`invalid anchor: ${item.id}/${anchor.location_id}`);
    }
  }
  unique(anchorIds, 'anchor location');
  for (const item of layout.locations) {
    const path = paths.get(item.owner_id);
    if (!equipment.has(item.owner_id) && !vehicles.has(item.owner_id) && !cranes.has(item.owner_id) && !(path?.mode === 'roller' && path.custody_location_id === item.id)) issue(`missing location owner: ${item.id}`);
  }
  for (const item of layout.source_bindings) if (!equipment.has(item.equipment_id)) issue(`missing source equipment: ${item.source_step_id}`);
  for (const item of layout.cranes) {
    if (!locations.has(item.pick_location_id) || !locations.has(item.drop_location_id) || locations.get(item.location_id)?.owner_id !== item.id) issue(`missing crane anchor: ${item.id}`);
  }
  for (const item of layout.vehicles) {
    const location = locations.get(item.location_id);
    if (!location || location.owner_id !== item.id || item.mode === 'roller' || transportNetworks[item.mode] !== item.network) issue(`invalid vehicle: ${item.id}`);
  }
  for (const path of layout.paths) {
    const source = locations.get(path.from_location_id), destination = locations.get(path.to_location_id);
    const first = path.points[0], last = path.points.at(-1);
    if (!source || !destination || !first || !last || distance(first, source.position) >= ENDPOINT_TOLERANCE || distance(last, destination.position) >= ENDPOINT_TOLERANCE) issue(`disconnected path: ${path.id}`);
    if (path.points.every(point => first && distance(point, first) < ENDPOINT_TOLERANCE)) issue(`zero length path: ${path.id}`);
    if (transportNetworks[path.mode] !== path.network) issue(`invalid path network: ${path.id}`);
    if (path.custody_location_id !== null) {
      const custody = locations.get(path.custody_location_id);
      if (path.mode !== 'roller' || !custody || custody.owner_id !== path.id || !path.points.slice(1, -1).some(point => distance(point, custody.position) < ENDPOINT_TOLERANCE)) issue(`invalid roller custody: ${path.id}`);
    }
    const outputForms = (source && equipment.get(source.owner_id)?.capability.output_forms) ?? [];
    if ((outputForms.includes('HOT_METAL') && path.mode !== 'hot_metal_car') || (outputForms.includes('LIQUID_STEEL') && path.mode !== 'ladle_car')) issue(`molten material requires rail carrier: ${path.id}`);
    if (path.mode === 'roller') {
      if (path.vehicle_id || path.pickup_crane_id || path.drop_crane_id) issue(`roller cannot use vehicle/crane: ${path.id}`);
    } else {
      const vehicle = vehicles.get(path.vehicle_id ?? ''), pick = cranes.get(path.pickup_crane_id ?? ''), drop = cranes.get(path.drop_crane_id ?? '');
      if (!vehicle || vehicle.mode !== path.mode || vehicle.network !== path.network) issue(`invalid vehicle path: ${path.id}`);
      if (!pick || !drop || pick.pick_location_id !== path.from_location_id || drop.drop_location_id !== path.to_location_id) issue(`invalid crane handoff: ${path.id}`);
      const producer = source && equipment.get(source.owner_id);
      if (producer && (!vehicle || !pick || !drop || Math.min(vehicle.capacity_kg, pick.capacity_kg, drop.capacity_kg) < producer.capacity_kg)) issue(`insufficient transfer capacity: ${path.id}`);
      if (producer?.capability.output_forms.some(form => ['HOT_STRIP', 'STRIP', 'THIN_STRIP', 'COATED_STRIP', 'WIRE'].includes(form))) issue(`strip requires roller: ${path.id}`);
    }
  }
  for (const route of layout.routes) {
    if (route.path_ids.length !== route.equipment_ids.length - 1) issue(`incomplete route: ${route.product_id}`);
    route.equipment_ids.forEach((equipmentId, index) => {
      const station = equipment.get(equipmentId);
      if (!station) { issue(`missing route equipment: ${route.product_id}/${equipmentId}`); return; }
      if (index === route.equipment_ids.length - 1) return;
      const next = equipment.get(route.equipment_ids[index + 1] ?? ''), path = paths.get(route.path_ids[index] ?? '');
      if (!next || !path || ![station.anchors.exit.location_id, station.anchors.buffer.location_id].includes(path.from_location_id) || path.to_location_id !== next.anchors.entry.location_id) issue(`disconnected route: ${route.product_id}/${equipmentId}`);
    });
  }
});
export function parseFactoryLayout(input: unknown): FactoryLayout { return factoryLayoutSchema.parse(input); }
export const factoryLayout = parseFactoryLayout(rawLayout);

/** Interpolates each physical segment by distance; never fits a spline across equipment. */
export function pointOnPolyline(points: readonly Point[], phase: number): Point {
  const first = required(points[0], 'polyline start');
  const lengths = points.slice(1).map((point, index) => distance(required(points[index], 'polyline point'), point));
  let remaining = Math.max(0, Math.min(1, phase)) * lengths.reduce((sum, length) => sum + length, 0);
  for (let index = 0; index < lengths.length; index++) {
    const length = required(lengths[index], 'segment length');
    const a = required(points[index], 'segment start'), b = required(points[index + 1], 'segment end');
    if (remaining <= length && length > 0) {
      const t = remaining / length;
      return [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t];
    }
    remaining -= length;
  }
  return points.at(-1) ?? first;
}
export function stationProcessPosition(layout: FactoryLayout, equipmentId: string, phase: number): Point {
  return pointOnPolyline((['entry', 'work', 'exit'] as const).map(anchor => stationAnchorPosition(layout, equipmentId, anchor)), phase);
}
