import { factoryWorldSchema, factoryCommandReplySchema } from './operations/contractsV3';
import { z } from 'zod';
import * as ops from './operations/contracts';

export const ScenarioIdSchema = ops.ScenarioIdSchema;
export type ScenarioId = ops.ScenarioId;
export const CustomerSchema = z.object({ id: z.string(), name: z.string(), country: z.string() });
export const OrderSchema = ops.OperationsOrderSchema.unwrap().extend({
  status: z.enum(['RECEIVED', 'PLANNED', 'IN_PRODUCTION', 'READY', 'PARTIALLY_DISPATCHED', 'DISPATCHED', 'PARTIALLY_DELIVERED', 'DELIVERED']),
  produced_kg: z.number().nonnegative(), dispatched_kg: z.number().nonnegative(), delivered_kg: z.number().nonnegative(),
  remaining_dispatch_kg: z.number().nonnegative(), remaining_delivery_kg: z.number().nonnegative(),
  work_order_ids: z.array(ops.EntityIdSchema), material_ids: z.array(ops.EntityIdSchema), shipment_ids: z.array(ops.EntityIdSchema),
}).readonly();
export const LotSchema = ops.OperationsLotSchema.unwrap().extend({ order_id: ops.EntityIdSchema, actual_kg: z.number().nonnegative(), status: z.string() }).readonly();
export const CoilSchema = ops.MaterialSchema.unwrap().safeExtend({ grade: z.string(), width_mm: z.number().positive().nullable(), thickness_mm: z.number().positive().nullable(), order_id: ops.EntityIdSchema }).readonly();
export const LocationSchema = z.object({ id: z.string(), type: z.string(), name: z.string(), x: z.number(), y: z.number(), z: z.number() });
export const InventorySchema = z.object({ coil_id: z.string(), location_id: z.string(), availability_status: ops.AvailabilityStatusSchema });
export const ShipmentSchema = ops.OperationsShipmentSchema;
export const ShipmentCoilSchema = z.object({ shipment_id: z.string(), coil_id: z.string() });
export const EventSchema = ops.OperationEventSchema;
export const LegacyEventSchema = z.object({ id: z.string(), scenario_id: ScenarioIdSchema, run_id: z.string(), sequence: z.number(), entity_type: z.string(), entity_id: z.string(), event_type: z.string(), occurred_at: z.string(), payload: z.record(z.string(), z.unknown()) });
export const EventHistorySchema = z.array(z.union([EventSchema, LegacyEventSchema]));
export const SimulationSchema = z.object({ scenario_id: ScenarioIdSchema, run_id: z.string(), tick: z.number(), max_tick: z.number(), elapsed_ms: z.number().int().nonnegative(), revision: z.number().int().nonnegative(), step_ms: z.literal(1000), simulated_at: z.string(), playing: z.boolean(), speed: z.union([z.literal(1), z.literal(2), z.literal(4)]), tick_seconds: z.number().positive() });
export const KpisSchema = z.object({ total_orders: z.number(), active_orders: z.number(), total_mass_kg: z.number(), produced_kg: z.number(), dispatched_kg: z.number(), in_transit_kg: z.number(), delivered_kg: z.number(), throughput_kg: z.number(), coil_count: z.number(), available_kg: z.number() });
export const RiskSchema = z.object({ id: z.string(), order_id: z.string(), severity: z.enum(['warning', 'critical', 'resolved']), reason: z.string(), rule: z.string(), recommendation: z.string(), delay_hours: z.number(), recovered_hours: z.number() });
export const ScenarioSchema = z.object({ id: ScenarioIdSchema, name: z.string(), description: z.string() });
export const OperationsProductionSchema = z.object({
  run_id: ops.RunIdSchema, revision: z.number().int().nonnegative(),
  materials: z.array(ops.MaterialSchema), processes: z.array(ops.ProcessExecutionSchema), transfers: z.array(ops.TransferSchema), lots: z.array(LotSchema), orders: z.array(OrderSchema),
  batches: z.array(z.object({ id: ops.EntityIdSchema, run_id: ops.RunIdSchema, order_id: ops.EntityIdSchema, work_order_id: ops.EntityIdSchema, lot_id: ops.EntityIdSchema, product: ops.ProductIdSchema, material_id: ops.EntityIdSchema, mass_kg: z.number().positive(), material_form: ops.MaterialFormSchema, current_location_id: ops.EntityIdSchema, route: z.array(z.string()), steps: z.array(ops.ProcessExecutionSchema) })),
  stages: z.array(z.object({ id: z.string(), equipment_ids: z.array(z.string()), process_ids: z.array(ops.EntityIdSchema), batch_ids: z.array(ops.EntityIdSchema) })),
});
export const WorldSchema = ops.OperationsSnapshotSchema.unwrap().safeExtend({
  orders: z.array(OrderSchema).readonly(), lots: z.array(LotSchema).readonly(),
  production: OperationsProductionSchema, simulation: SimulationSchema, kpis: KpisSchema,
  customers: z.array(CustomerSchema), coils: z.array(CoilSchema), locations: z.array(LocationSchema), inventory: z.array(InventorySchema),
  inventory_materials: z.array(ops.MaterialSchema), shipment_coils: z.array(ShipmentCoilSchema), risks: z.array(RiskSchema),
  recovery: ops.RecoveryComparisonSchema.nullable().default(null),
  ai: z.object({ enabled: z.boolean(), available: z.boolean(), provider: z.string() }),
}).superRefine(ops.checkSnapshotRelations).readonly();
export const CommandReplySchema = WorldSchema.unwrap().safeExtend({ applied_revision: z.number().int().nonnegative(), replayed: z.boolean() }).readonly();
export const MaterialViewSchema = z.object({ run_id: ops.RunIdSchema, revision: z.number().int().nonnegative(), material: ops.MaterialSchema, order: OrderSchema, lot: ops.OperationsLotSchema, work_order: ops.WorkOrderSchema, versions: z.array(ops.MaterialVersionSchema), lineage: z.array(ops.MaterialLineageEdgeSchema), processes: z.array(ops.ProcessExecutionSchema), transfers: z.array(ops.TransferSchema), inspections: z.array(ops.InspectionSchema), shipments: z.array(ops.OperationsShipmentSchema) });
export const OrderDetailSchema = z.object({ order: OrderSchema, customer: CustomerSchema, lots: z.array(LotSchema), coils: z.array(CoilSchema), shipments: z.array(ShipmentSchema) });
export const CoilDetailSchema = z.object({ coil: CoilSchema, lot: LotSchema, order: OrderSchema, customer: CustomerSchema, location: LocationSchema, shipment: ShipmentSchema.nullable() });
export type World = z.infer<typeof WorldSchema>;
export type CommandReply = z.infer<typeof CommandReplySchema>;
export type MaterialView = z.infer<typeof MaterialViewSchema>;
export type Coil = z.infer<typeof CoilSchema>;
export type Order = z.infer<typeof OrderSchema>;
export type Shipment = z.infer<typeof ShipmentSchema>;
export type Location = z.infer<typeof LocationSchema>;
export type OperationEvent = z.infer<typeof EventSchema>;
export type Risk = z.infer<typeof RiskSchema>;
export type CoilDetail = z.infer<typeof CoilDetailSchema>;
export type Selection = { readonly type: 'coil' | 'location' | 'shipment' | 'order'; readonly id: string };

export const ApiWorldSchema = z.discriminatedUnion('schema_version', [WorldSchema.unwrap(), factoryWorldSchema.unwrap()]).readonly();
export const ApiCommandReplySchema = z.discriminatedUnion('schema_version', [CommandReplySchema.unwrap(), factoryCommandReplySchema.unwrap()]).readonly();
export type ApiWorld = z.infer<typeof ApiWorldSchema>;
export type ApiCommandReply = z.infer<typeof ApiCommandReplySchema>;
