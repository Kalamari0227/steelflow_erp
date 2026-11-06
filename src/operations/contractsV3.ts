import { validateSnapshot, validateWorld } from './contractsV3Validation';
import { validateMaterialDetail, validateProjectionScope, validateCommand, validateDelta, validateOrderDetail, validateShipments, validateProduction, validateCoils } from './contractsV3Projection';
import { z } from 'zod';
import { FactoryRunSchema } from './contractsV3Core';
import { BatchIOSchema, FactoryEventSchema, FactoryOrderSchema, MassLedgerEntrySchema, MaterialSchema, MaterialAllocationSchema, MaterialVersionSchema, ProcessBatchSchema, ProcessExecutionSchema, ProductionLotSchema, QualityRecordSchema, StockLotSchema, StockReceiptSchema, VersionEdgeSchema, WorkOrderSchema } from './contractsV3Rows';
import { AttachmentSchema, ConsistSchema, ConsistMemberSchema, FleetAssetSchema, MovementSegmentSchema, ResourceReservationSchema, ShipmentSchema, ShipmentLegSchema, ShipmentMaterialSchema, TransportJobSchema, VehicleStateSchema } from './contractsV3Transport';

export const FactoryKpisShape = z.strictObject({
  schema_version: z.literal(3),
  run_id: z.string().min(1),
  revision: z.number().int().safe().min(0).max(9007199254740991),
  active_material_count: z.number().int().safe().min(0).max(9007199254740991),
  active_kg: z.number().int().safe().min(0).max(9007199254740991),
  available_kg: z.number().int().safe().min(0).max(9007199254740991),
  allocated_kg: z.number().int().safe().min(0).max(9007199254740991),
  shipped_kg: z.number().int().safe().min(0).max(9007199254740991),
  opening_kg: z.number().int().safe().min(0).max(9007199254740991),
  received_kg: z.number().int().safe().min(0).max(9007199254740991),
  additions_kg: z.number().int().safe().min(0).max(9007199254740991),
  byproduct_kg: z.number().int().safe().min(0).max(9007199254740991),
  loss_kg: z.number().int().safe().min(0).max(9007199254740991),
});

export const FactoryCollectionsShape = z.strictObject({
  orders: z.array(FactoryOrderSchema).readonly(),
  work_orders: z.array(WorkOrderSchema).readonly(),
  production_lots: z.array(ProductionLotSchema).readonly(),
  stock_lots: z.array(StockLotSchema).readonly(),
  receipts: z.array(StockReceiptSchema).readonly(),
  materials: z.array(MaterialSchema).readonly(),
  material_versions: z.array(MaterialVersionSchema).readonly(),
  version_edges: z.array(VersionEdgeSchema).readonly(),
  allocations: z.array(MaterialAllocationSchema).readonly(),
  process_batches: z.array(ProcessBatchSchema).readonly(),
  batch_io: z.array(BatchIOSchema).readonly(),
  processes: z.array(ProcessExecutionSchema).readonly(),
  fleet: z.array(FleetAssetSchema).readonly(),
  vehicle_states: z.array(VehicleStateSchema).readonly(),
  transport_jobs: z.array(TransportJobSchema).readonly(),
  movement_segments: z.array(MovementSegmentSchema).readonly(),
  reservations: z.array(ResourceReservationSchema).readonly(),
  consists: z.array(ConsistSchema).readonly(),
  consist_members: z.array(ConsistMemberSchema).readonly(),
  attachments: z.array(AttachmentSchema).readonly(),
  shipments: z.array(ShipmentSchema).readonly(),
  shipment_legs: z.array(ShipmentLegSchema).readonly(),
  shipment_materials: z.array(ShipmentMaterialSchema).readonly(),
  quality: z.array(QualityRecordSchema).readonly(),
  events: z.array(FactoryEventSchema).readonly(),
  mass_ledger: z.array(MassLedgerEntrySchema).readonly(),
});

export const FactorySnapshotShape = z.strictObject({
  ...FactoryCollectionsShape.shape,
  schema_version: z.literal(3),
  run: FactoryRunSchema,
});

export const FactoryCommandShape = z.strictObject({
  action: z.enum(["play", "pause", "step", "speed", "reset", "scenario"]),
  run_id: z.string().min(1),
  expected_revision: z.number().int().safe().min(0).max(9007199254740991).nullable().default(null),
  command_id: z.string().min(1),
  speed: z.union([z.literal(1), z.literal(2), z.literal(4)]).nullable().default(null),
  steps: z.number().int().safe().min(1).max(48).nullable().default(null),
  scenario_id: z.enum(["NORMAL", "DELAY", "RECOVERY"]).nullable().default(null),
});

export const TransitionDeltaShape = z.strictObject({
  run_id: z.string().min(1),
  bundle_hash: z.string().regex(/^[0-9a-f]{64}$/),
  from_revision: z.number().int().safe().min(0).max(9007199254740991),
  to_revision: z.number().int().safe().min(0).max(9007199254740991),
  upserts: FactoryCollectionsShape.readonly(),
  event_sequence_from: z.number().int().safe().min(0).max(9007199254740991),
  event_sequence_to: z.number().int().safe().min(0).max(9007199254740991),
});

export const CommandResultShape = z.strictObject({
  run: FactoryRunSchema,
  command_id: z.string().min(1),
  replayed: z.boolean(),
  delta: TransitionDeltaShape.nullable(),
});

export const FactoryWorldShape = z.strictObject({
  ...FactoryCollectionsShape.shape,
  schema_version: z.literal(3),
  run: FactoryRunSchema,
  kpis: FactoryKpisShape,
});

export const FactoryMaterialDetailShape = z.strictObject({
  schema_version: z.literal(3),
  run_id: z.string().min(1),
  revision: z.number().int().safe().min(0).max(9007199254740991),
  material: MaterialSchema,
  current_version: MaterialVersionSchema,
  versions: z.array(MaterialVersionSchema).readonly(),
  lineage_materials: z.array(MaterialSchema).readonly(),
  version_edges: z.array(VersionEdgeSchema).readonly(),
  process_batches: z.array(ProcessBatchSchema).readonly(),
  batch_io: z.array(BatchIOSchema).readonly(),
  allocations: z.array(MaterialAllocationSchema).readonly(),
  current_allocation: MaterialAllocationSchema.nullable(),
  order: FactoryOrderSchema.nullable(),
  work_order: WorkOrderSchema.nullable(),
  production_lot: ProductionLotSchema.nullable(),
  origin_stock_lot: StockLotSchema.nullable(),
  attachments: z.array(AttachmentSchema).readonly(),
  current_attachment: AttachmentSchema.nullable(),
  transport_jobs: z.array(TransportJobSchema).readonly(),
  current_job: TransportJobSchema.nullable(),
  shipments: z.array(ShipmentSchema).readonly(),
  shipment_legs: z.array(ShipmentLegSchema).readonly(),
  quality: z.array(QualityRecordSchema).readonly(),
  events: z.array(FactoryEventSchema).readonly(),
});


export const FactoryProductionShape = z.strictObject({
  schema_version: z.literal(3),
  run_id: z.string().min(1),
  revision: z.number().int().safe().min(0).max(9007199254740991),
  work_orders: z.array(WorkOrderSchema).readonly(),
  production_lots: z.array(ProductionLotSchema).readonly(),
  processes: z.array(ProcessExecutionSchema).readonly(),
  process_batches: z.array(ProcessBatchSchema).readonly(),
  batch_io: z.array(BatchIOSchema).readonly(),
  material_versions: z.array(MaterialVersionSchema).readonly(),
  version_edges: z.array(VersionEdgeSchema).readonly(),
});

export const FactoryOrdersShape = z.strictObject({
  schema_version: z.literal(3),
  run_id: z.string().min(1),
  revision: z.number().int().safe().min(0).max(9007199254740991),
  orders: z.array(FactoryOrderSchema).readonly(),
  work_orders: z.array(WorkOrderSchema).readonly(),
  allocations: z.array(MaterialAllocationSchema).readonly(),
});

export const FactoryCoilsShape = z.strictObject({
  schema_version: z.literal(3),
  run_id: z.string().min(1),
  revision: z.number().int().safe().min(0).max(9007199254740991),
  materials: z.array(MaterialSchema).readonly(),
});

export const FactoryShipmentsShape = z.strictObject({
  schema_version: z.literal(3),
  run_id: z.string().min(1),
  revision: z.number().int().safe().min(0).max(9007199254740991),
  shipments: z.array(ShipmentSchema).readonly(),
  shipment_legs: z.array(ShipmentLegSchema).readonly(),
  shipment_materials: z.array(ShipmentMaterialSchema).readonly(),
});

export const FactoryEventsShape = z.strictObject({
  schema_version: z.literal(3),
  run_id: z.string().min(1),
  revision: z.number().int().safe().min(0).max(9007199254740991),
  events: z.array(FactoryEventSchema).readonly(),
});

export const FactoryCommandReplyShape = z.strictObject({
  ...FactoryCollectionsShape.shape,
  schema_version: z.literal(3),
  run: FactoryRunSchema,
  kpis: FactoryKpisShape,
  command_id: z.string().min(1),
  replayed: z.boolean(),
  applied_revision: z.number().int().safe().min(0).max(9007199254740991),
  applied_run_id: z.string().min(1),
});

export const FactoryOrderDetailShape = z.strictObject({
  schema_version: z.literal(3), run_id: z.string().min(1), revision: z.number().int().safe().min(0),
  order: FactoryOrderSchema, work_orders: z.array(WorkOrderSchema).readonly(),
  allocations: z.array(MaterialAllocationSchema).readonly(), materials: z.array(MaterialSchema).readonly(),
  shipments: z.array(ShipmentSchema).readonly(), shipment_legs: z.array(ShipmentLegSchema).readonly(),
});

export const factorySnapshotSchema = FactorySnapshotShape.superRefine(validateSnapshot).readonly();
export const factoryWorldSchema = FactoryWorldShape.superRefine(validateWorld).readonly();
export const factoryMaterialDetailSchema = FactoryMaterialDetailShape.superRefine(validateMaterialDetail).readonly();
export const factoryCommandSchema = FactoryCommandShape.superRefine(validateCommand).readonly();
export const factoryDeltaSchema = TransitionDeltaShape.superRefine(validateDelta).readonly();
export const factoryCommandResultSchema = CommandResultShape.extend({ delta: factoryDeltaSchema.nullable() }).readonly();
export const factoryCommandReplySchema = FactoryCommandReplyShape.superRefine((reply, ctx) => {
  const { command_id: _id, replayed: _replayed, applied_revision: _revision, applied_run_id: _run, ...world } = reply;
  validateWorld(world, ctx);
}).readonly();
export const factoryKpisSchema = FactoryKpisShape.readonly();
export const factoryProductionSchema = FactoryProductionShape.superRefine(validateProduction).readonly();
export const factoryOrdersSchema = FactoryOrdersShape.superRefine(validateProjectionScope).readonly();
export const factoryOrderDetailSchema = FactoryOrderDetailShape.superRefine(validateOrderDetail).readonly();
export const factoryShipmentsSchema = FactoryShipmentsShape.superRefine(validateShipments).readonly();
export const factoryEventsSchema = FactoryEventsShape.superRefine(validateProjectionScope).readonly();
export const factoryCoilsSchema = FactoryCoilsShape.superRefine(validateCoils).readonly();
export type FactorySnapshot = z.infer<typeof factorySnapshotSchema>;
export type FactoryWorld = z.infer<typeof factoryWorldSchema>;
export type FactoryMaterialDetail = z.infer<typeof factoryMaterialDetailSchema>;
export type FactoryCommand = z.infer<typeof factoryCommandSchema>;
export type FactoryCommandReply = z.infer<typeof factoryCommandReplySchema>;
export type FactoryOrderDetail = z.infer<typeof factoryOrderDetailSchema>;
export type FactoryKpis = z.infer<typeof factoryKpisSchema>;

export type FactoryProduction = z.infer<typeof factoryProductionSchema>;
export type FactoryOrders = z.infer<typeof factoryOrdersSchema>;
export type FactoryShipments = z.infer<typeof factoryShipmentsSchema>;
export type FactoryEvents = z.infer<typeof factoryEventsSchema>;
export type FactoryCoils = z.infer<typeof factoryCoilsSchema>;
export type FactoryDelta = z.infer<typeof factoryDeltaSchema>;
export type FactoryCommandResult = z.infer<typeof factoryCommandResultSchema>;
