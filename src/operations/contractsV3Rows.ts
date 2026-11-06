import { z } from 'zod';
import { MaterialDimensionsSchema, utcSchema } from './contractsV3Core';

export const BatchIOSchema = z.strictObject({
  run_id: z.string().min(1),
  id: z.string().min(1),
  batch_id: z.string().min(1),
  role: z.enum(["INPUT", "STOCK_ADDITION", "EXTERNAL_ADDITION", "OUTPUT", "BYPRODUCT", "LOSS"]),
  material_version_id: z.string().min(1).nullable(),
  quantity_kg: z.number().int().safe().max(9007199254740991).gt(0),
  source_id: z.string().min(1).nullable(),
}).readonly();

export const EventContextSchema = z.strictObject({
  reason_code: z.string().min(1).nullable().default(null),
  reason: z.string().min(1).nullable().default(null),
  material_ids: z.array(z.string().min(1)).readonly().prefault(() => []),
  order_id: z.string().min(1).nullable().default(null),
  work_order_id: z.string().min(1).nullable().default(null),
  process_id: z.string().min(1).nullable().default(null),
  batch_id: z.string().min(1).nullable().default(null),
  job_id: z.string().min(1).nullable().default(null),
  shipment_leg_id: z.string().min(1).nullable().default(null),
  resource_id: z.string().min(1).nullable().default(null),
  reservation_id: z.string().min(1).nullable().default(null),
  from_attachment_id: z.string().min(1).nullable().default(null),
  to_attachment_id: z.string().min(1).nullable().default(null),
  from_owner_id: z.string().min(1).nullable().default(null),
  to_owner_id: z.string().min(1).nullable().default(null),
}).readonly();

export const FactoryEventSchema = z.strictObject({
  run_id: z.string().min(1),
  id: z.string().min(1),
  sequence: z.number().int().safe().max(9007199254740991).gt(0),
  event_type: z.enum(["RUN_CREATED", "CLOCK_ADVANCED", "PLAYING_CHANGED", "SPEED_CHANGED", "STOCK_RECEIVED", "MATERIAL_ALLOCATED", "BATCH_STARTED", "BATCH_COMPLETED", "ATTACHMENT_ACQUIRED", "ATTACHMENT_RELEASED", "JOB_ASSIGNED", "JOB_EMPTY_APPROACH", "JOB_QUEUED", "JOB_LOADING", "JOB_DISPATCHED", "JOB_UNLOADING", "JOB_RETURNING", "JOB_IDLE", "JOB_BLOCKED", "JOB_COMPLETED", "RESERVATION_ACQUIRED", "RESERVATION_RELEASED", "MOTION_PHASE_STARTED", "MOTION_PHASE_COMPLETED", "QUALITY_RECORDED", "PLAN_RELEASED", "WORK_ORDER_RELEASED", "PROCESS_STARTED", "PROCESS_BLOCKED", "PROCESS_COMPLETED", "MATERIAL_TRANSFORMED", "MATERIAL_SPLIT", "MATERIAL_MERGED", "TRANSFER_STARTED", "TRANSFER_LOADING", "TRANSFER_DEPARTED", "TRANSFER_UNLOADING", "TRANSFER_ARRIVED", "INSPECTION_STARTED", "INSPECTION_PASSED", "INSPECTION_HELD", "INSPECTION_FAILED", "PACKAGING_STARTED", "PACKAGING_COMPLETED", "MATERIAL_AVAILABLE", "SHIPMENT_ALLOCATED", "SHIPMENT_LOADING", "MATERIAL_LOADED", "SHIPMENT_LOADED", "SHIPMENT_DISPATCHED", "SHIPMENT_AT_PORT", "SHIPMENT_SAILING", "SHIPMENT_DELIVERED", "ORDER_DELIVERED", "RESOURCE_DOWN", "RESOURCE_RESTORED", "RECOVERY_ROUTED"]),
  entity_type: z.enum(["run", "order", "work_order", "production_lot", "stock_lot", "receipt", "material", "material_version", "batch", "process", "fleet", "job", "attachment", "shipment", "shipment_leg", "quality"]),
  entity_id: z.string().min(1),
  at_ms: z.number().int().safe().min(0).max(4193483039999),
  occurred_at: utcSchema,
  source_id: z.string().min(1),
  payload: EventContextSchema.prefault(() => ({})),
}).readonly();

export const FactoryOrderSchema = z.strictObject({
  run_id: z.string().min(1),
  id: z.string().min(1),
  customer_id: z.string().min(1),
  product_id: z.enum(["slab", "bloom", "billet", "hr", "plate", "wire", "cr", "gi", "ga", "hgi", "eg", "go", "ngo", "sts-hr", "sts-cr", "sts-plate", "ti-hr", "ti-cr", "ti-sheet", "ti-plate"]),
  grade: z.string().min(1),
  quantity_kg: z.number().int().safe().max(9007199254740991).gt(0),
  due_at: utcSchema,
}).readonly();

export const MassLedgerEntrySchema = z.strictObject({
  run_id: z.string().min(1),
  id: z.string().min(1),
  source_id: z.string().min(1),
  kind: z.enum(["OPENING_STOCK", "EXTERNAL_RECEIPT", "EXTERNAL_ADDITION", "BYPRODUCT", "IRRECOVERABLE_LOSS"]),
  quantity_kg: z.number().int().safe().max(9007199254740991).gt(0),
  at_ms: z.number().int().safe().min(0).max(4193483039999),
  material_id: z.string().min(1).nullable(),
  batch_id: z.string().min(1).nullable(),
  event_id: z.string().min(1).nullable(),
}).readonly();

export const MaterialSchema = z.strictObject({
  run_id: z.string().min(1),
  id: z.string().min(1),
  grade: z.string().min(1),
  form: z.enum(["ORE", "HOT_METAL", "LIQUID_STEEL", "SCRAP", "SLAB", "BLOOM", "BILLET", "HOT_SLAB", "HOT_BLOOM", "HOT_BILLET", "HOT_STRIP", "HOT_PLATE", "STRIP", "THIN_STRIP", "COATED_STRIP", "HR_COIL", "CR_COIL", "GI_COIL", "GA_COIL", "HGI_COIL", "EG_COIL", "GO_COIL", "NGO_COIL", "WIRE", "WIRE_COIL", "PLATE", "STS_HR_COIL", "STS_CR_COIL", "STS_PLATE", "TI_INGOT", "TI_SLAB", "TI_HR_COIL", "TI_CR_COIL", "TI_SHEET", "TI_PLATE", "COKE", "COAL", "LIMESTONE", "ALLOY", "SLAG", "BYPRODUCT"]),
  dimensions: MaterialDimensionsSchema,
  weight_kg: z.number().int().safe().max(9007199254740991).gt(0),
  current_version_id: z.string().min(1),
  origin_stock_lot_id: z.string().min(1).nullable(),
  production_lot_id: z.string().min(1).nullable(),
  quality_status: z.enum(["PENDING", "PASSED", "HOLD", "FAILED"]),
  availability_status: z.enum(["WIP", "QUARANTINED", "AVAILABLE", "RESERVED", "SHIPPED", "CONSUMED"]),
  active: z.boolean(),
}).readonly();

export const MaterialAllocationSchema = z.strictObject({
  run_id: z.string().min(1),
  id: z.string().min(1),
  material_id: z.string().min(1),
  order_id: z.string().min(1),
  work_order_id: z.string().min(1),
  quantity_kg: z.number().int().safe().max(9007199254740991).gt(0),
  active: z.boolean(),
}).readonly();

export const MaterialVersionSchema = z.strictObject({
  run_id: z.string().min(1),
  id: z.string().min(1),
  material_id: z.string().min(1),
  ordinal: z.number().int().safe().max(9007199254740991).gt(0),
  grade: z.string().min(1),
  form: z.enum(["ORE", "HOT_METAL", "LIQUID_STEEL", "SCRAP", "SLAB", "BLOOM", "BILLET", "HOT_SLAB", "HOT_BLOOM", "HOT_BILLET", "HOT_STRIP", "HOT_PLATE", "STRIP", "THIN_STRIP", "COATED_STRIP", "HR_COIL", "CR_COIL", "GI_COIL", "GA_COIL", "HGI_COIL", "EG_COIL", "GO_COIL", "NGO_COIL", "WIRE", "WIRE_COIL", "PLATE", "STS_HR_COIL", "STS_CR_COIL", "STS_PLATE", "TI_INGOT", "TI_SLAB", "TI_HR_COIL", "TI_CR_COIL", "TI_SHEET", "TI_PLATE", "COKE", "COAL", "LIMESTONE", "ALLOY", "SLAG", "BYPRODUCT"]),
  dimensions: MaterialDimensionsSchema,
  weight_kg: z.number().int().safe().max(9007199254740991).gt(0),
  cause_event_id: z.string().min(1).nullable(),
}).readonly();

export const ProcessBatchSchema = z.strictObject({
  run_id: z.string().min(1),
  id: z.string().min(1),
  process_id: z.string().min(1).nullable(),
  recipe_id: z.string().min(1),
  status: z.enum(["QUEUED", "RUNNING", "BLOCKED", "COMPLETED"]),
  start_ms: z.number().int().safe().min(0).max(4193483039999).nullable(),
  end_ms: z.number().int().safe().min(0).max(4193483039999).nullable(),
}).readonly();

export const ProcessExecutionSchema = z.strictObject({
  run_id: z.string().min(1),
  id: z.string().min(1),
  work_order_id: z.string().min(1).nullable(),
  route_step_id: z.string().min(1),
  equipment_id: z.string().min(1),
  status: z.enum(["QUEUED", "RUNNING", "BLOCKED", "COMPLETED"]),
  ready_at_ms: z.number().int().safe().min(0).max(4193483039999),
  start_ms: z.number().int().safe().min(0).max(4193483039999).nullable(),
  end_ms: z.number().int().safe().min(0).max(4193483039999).nullable(),
  planned_duration_ms: z.number().int().safe().max(4193483039999).gt(0),
  blocked_reason: z.string().min(1).nullable(),
}).readonly();

export const ProductionLotSchema = z.strictObject({
  run_id: z.string().min(1),
  id: z.string().min(1),
  work_order_id: z.string().min(1),
  planned_kg: z.number().int().safe().max(9007199254740991).gt(0),
}).readonly();

export const QualityRecordSchema = z.strictObject({
  run_id: z.string().min(1),
  id: z.string().min(1),
  material_id: z.string().min(1),
  material_version_id: z.string().min(1),
  status: z.enum(["PENDING", "PASSED", "HOLD", "FAILED"]),
  at_ms: z.number().int().safe().min(0).max(4193483039999),
  event_id: z.string().min(1).nullable(),
}).readonly();

export const StockLotSchema = z.strictObject({
  run_id: z.string().min(1),
  id: z.string().min(1),
  source_kind: z.enum(["OPENING", "PURCHASED", "RETURNED"]),
  grade: z.string().min(1),
  form: z.enum(["ORE", "HOT_METAL", "LIQUID_STEEL", "SCRAP", "SLAB", "BLOOM", "BILLET", "HOT_SLAB", "HOT_BLOOM", "HOT_BILLET", "HOT_STRIP", "HOT_PLATE", "STRIP", "THIN_STRIP", "COATED_STRIP", "HR_COIL", "CR_COIL", "GI_COIL", "GA_COIL", "HGI_COIL", "EG_COIL", "GO_COIL", "NGO_COIL", "WIRE", "WIRE_COIL", "PLATE", "STS_HR_COIL", "STS_CR_COIL", "STS_PLATE", "TI_INGOT", "TI_SLAB", "TI_HR_COIL", "TI_CR_COIL", "TI_SHEET", "TI_PLATE", "COKE", "COAL", "LIMESTONE", "ALLOY", "SLAG", "BYPRODUCT"]),
  quantity_kg: z.number().int().safe().max(9007199254740991).gt(0),
  received_at_ms: z.number().int().safe().min(0).max(4193483039999),
}).readonly();

export const StockReceiptSchema = z.strictObject({
  run_id: z.string().min(1),
  id: z.string().min(1),
  stock_lot_id: z.string().min(1),
  source_id: z.string().min(1),
  quantity_kg: z.number().int().safe().max(9007199254740991).gt(0),
  received_at_ms: z.number().int().safe().min(0).max(4193483039999),
  event_id: z.string().min(1).nullable(),
}).readonly();

export const VersionEdgeSchema = z.strictObject({
  run_id: z.string().min(1),
  id: z.string().min(1),
  batch_id: z.string().min(1),
  input_version_id: z.string().min(1),
  output_version_id: z.string().min(1),
  transferred_kg: z.number().int().safe().max(9007199254740991).gt(0),
}).readonly();

export const WorkOrderSchema = z.strictObject({
  run_id: z.string().min(1),
  id: z.string().min(1),
  order_id: z.string().min(1),
  route_id: z.string().min(1),
  route_version: z.number().int().safe().max(9007199254740991).gt(0),
  planned_kg: z.number().int().safe().max(9007199254740991).gt(0),
  status: z.enum(["PLANNED", "RELEASED", "COMPLETED"]),
}).readonly();
