import { z } from 'zod';

export const AttachmentSchema = z.strictObject({
  run_id: z.string().min(1),
  id: z.string().min(1),
  material_id: z.string().min(1),
  kind: z.enum(["slot", "equipment", "hook", "vehicle", "railcar", "ship", "customer"]),
  owner_id: z.string().min(1),
  socket_id: z.string().min(1),
  acquired_at_ms: z.number().int().safe().min(0).max(4193483039999),
  released_at_ms: z.number().int().safe().min(0).max(4193483039999).nullable(),
}).readonly();

export const ConsistSchema = z.strictObject({
  run_id: z.string().min(1),
  id: z.string().min(1),
  locomotive_id: z.string().min(1),
  status: z.enum(["IDLE", "MOVING", "BLOCKED"]),
}).readonly();

export const ConsistMemberSchema = z.strictObject({
  run_id: z.string().min(1),
  id: z.string().min(1),
  consist_id: z.string().min(1),
  fleet_id: z.string().min(1),
  ordinal: z.number().int().safe().min(0).max(9007199254740991),
  coupler_distance_m: z.number().finite().min(0),
}).readonly();

export const FleetAssetSchema = z.strictObject({
  run_id: z.string().min(1),
  id: z.string().min(1),
  kind: z.enum(["truck", "carrier", "forklift", "torpedo", "ladle", "locomotive", "railcar", "ship"]),
  variant: z.string().min(1),
  capacity_kg: z.number().int().safe().max(9007199254740991).gt(0),
  length_m: z.number().finite().gt(0),
  load_envelope_m: z.tuple([z.number().finite().gt(0), z.number().finite().gt(0), z.number().finite().gt(0)]).readonly(),
  turn_radius_m: z.number().finite().min(0),
  mode: z.enum(["road", "rail", "hot_metal_rail", "water"]),
  load_socket_id: z.string().min(1),
}).readonly();

export const MovementSegmentSchema = z.strictObject({
  run_id: z.string().min(1),
  id: z.string().min(1),
  start_ms: z.number().int().safe().min(0).max(4193483039999),
  end_ms: z.number().int().safe().min(0).max(4193483039999),
  job_id: z.string().min(1),
  ordinal: z.number().int().safe().min(0).max(9007199254740991),
  segment_id: z.string().min(1),
  from_position_m: z.tuple([z.number().finite(), z.number().finite(), z.number().finite()]).readonly(),
  to_position_m: z.tuple([z.number().finite(), z.number().finite(), z.number().finite()]).readonly(),
}).readonly();

export const ResourceReservationSchema = z.strictObject({
  run_id: z.string().min(1),
  id: z.string().min(1),
  start_ms: z.number().int().safe().min(0).max(4193483039999),
  end_ms: z.number().int().safe().min(0).max(4193483039999),
  resource_id: z.string().min(1),
  job_id: z.string().min(1),
  released_at_ms: z.number().int().safe().min(0).max(4193483039999).nullable().default(null),
}).readonly();

export const ShipmentSchema = z.strictObject({
  run_id: z.string().min(1),
  id: z.string().min(1),
  order_id: z.string().min(1),
  mode: z.enum(["ROAD", "RAIL", "SEA"]),
  status: z.enum(["PLANNED", "ALLOCATED", "LOADING", "DISPATCHED", "IN_TRANSIT", "DELIVERED"]),
  capacity_kg: z.number().int().safe().max(9007199254740991).gt(0),
}).readonly();

export const ShipmentLegSchema = z.strictObject({
  run_id: z.string().min(1),
  id: z.string().min(1),
  shipment_id: z.string().min(1),
  ordinal: z.number().int().safe().min(0).max(9007199254740991),
  mode: z.enum(["ROAD", "RAIL", "SEA"]),
  from_node_id: z.string().min(1),
  to_node_id: z.string().min(1),
  status: z.enum(["PLANNED", "LOADING", "IN_TRANSIT", "UNLOADING", "DELIVERED"]),
  eta_ms: z.number().int().safe().min(0).max(4193483039999).nullable(),
  start_ms: z.number().int().safe().min(0).max(4193483039999).nullable(),
  end_ms: z.number().int().safe().min(0).max(4193483039999).nullable(),
}).readonly();

export const ShipmentMaterialSchema = z.strictObject({
  run_id: z.string().min(1),
  id: z.string().min(1),
  shipment_id: z.string().min(1),
  material_id: z.string().min(1),
  active: z.boolean(),
}).readonly();

export const TransportJobSchema = z.strictObject({
  run_id: z.string().min(1),
  id: z.string().min(1),
  fleet_id: z.string().min(1).nullable(),
  equipment_id: z.string().min(1).nullable(),
  material_id: z.string().min(1).nullable(),
  shipment_leg_id: z.string().min(1).nullable(),
  from_node_id: z.string().min(1),
  to_node_id: z.string().min(1),
  status: z.enum(["IDLE", "ASSIGNED", "EMPTY_APPROACH", "QUEUED", "LOADING", "MOVING", "UNLOADING", "RETURNING", "BLOCKED", "COMPLETED", "STRUCTURAL_BLOCKED"]),
  ready_at_ms: z.number().int().safe().min(0).max(4193483039999),
  start_ms: z.number().int().safe().min(0).max(4193483039999).nullable(),
  end_ms: z.number().int().safe().min(0).max(4193483039999).nullable(),
  blocked_resource_id: z.string().min(1).nullable(),
}).readonly();

export const VehicleStateSchema = z.strictObject({
  run_id: z.string().min(1),
  id: z.string().min(1),
  fleet_id: z.string().min(1),
  status: z.enum(["IDLE", "ASSIGNED", "EMPTY_APPROACH", "QUEUED", "LOADING", "MOVING", "UNLOADING", "RETURNING", "BLOCKED"]),
  node_id: z.string().min(1),
  position_m: z.tuple([z.number().finite(), z.number().finite(), z.number().finite()]).readonly(),
  yaw_rad: z.number().finite(),
  current_job_id: z.string().min(1).nullable(),
  available_at_ms: z.number().int().safe().min(0).max(4193483039999),
}).readonly();
