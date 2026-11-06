import { z } from "zod";

export const ProductIdSchema = z.enum(["slab", "bloom", "billet", "hr", "plate", "wire", "cr", "gi", "ga", "hgi", "eg", "go", "ngo", "sts-hr", "sts-cr", "sts-plate", "ti-hr", "ti-cr", "ti-sheet", "ti-plate"]);
export type ProductId = z.infer<typeof ProductIdSchema>;

export const MaterialFormSchema = z.enum(["ORE", "HOT_METAL", "LIQUID_STEEL", "SCRAP", "SLAB", "BLOOM", "BILLET", "HOT_SLAB", "HOT_BLOOM", "HOT_BILLET", "HOT_STRIP", "HOT_PLATE", "STRIP", "THIN_STRIP", "COATED_STRIP", "HR_COIL", "CR_COIL", "GI_COIL", "GA_COIL", "HGI_COIL", "EG_COIL", "GO_COIL", "NGO_COIL", "WIRE", "WIRE_COIL", "PLATE", "STS_HR_COIL", "STS_CR_COIL", "STS_PLATE", "TI_INGOT", "TI_SLAB", "TI_HR_COIL", "TI_CR_COIL", "TI_SHEET", "TI_PLATE"]);
export type MaterialForm = z.infer<typeof MaterialFormSchema>;

export const ScenarioIdSchema = z.enum(["NORMAL", "DELAY", "RECOVERY"]);
export type ScenarioId = z.infer<typeof ScenarioIdSchema>;

export const ProcessStatusSchema = z.enum(["QUEUED", "RUNNING", "BLOCKED", "COMPLETED"]);
export type ProcessStatus = z.infer<typeof ProcessStatusSchema>;

export const TransferStatusSchema = z.enum(["WAITING", "LOADING", "IN_TRANSIT", "UNLOADING", "ARRIVED"]);
export type TransferStatus = z.infer<typeof TransferStatusSchema>;

export const TransferModeSchema = z.enum(["roller", "flatbed", "hot_metal_car", "ladle_car"]);
export type TransferMode = z.infer<typeof TransferModeSchema>;

export const QualityStatusSchema = z.enum(["PENDING", "PASSED", "HOLD", "FAILED"]);
export type QualityStatus = z.infer<typeof QualityStatusSchema>;

export const AvailabilityStatusSchema = z.enum(["WIP", "QUARANTINED", "AVAILABLE", "RESERVED", "SHIPPED", "CONSUMED"]);
export type AvailabilityStatus = z.infer<typeof AvailabilityStatusSchema>;

export const ShipmentStatusSchema = z.enum(["PLANNED", "RELEASED", "COMPLETED"]);
export type ShipmentStatus = z.infer<typeof ShipmentStatusSchema>;

// Immutable wire records shared with backend/app/operations/contracts.py.
export const UtcDateTimeSchema = z.iso.datetime({ offset: true }).refine(value => /(?:Z|\+00:00)$/.test(value), "UTC offset required");
export const RunIdSchema = z.string().min(1).brand("RunId");
export const EntityIdSchema = z.string().min(1).brand("EntityId");
export type RunId = z.infer<typeof RunIdSchema>;
export type EntityId = z.infer<typeof EntityIdSchema>;

export const OperationsRunSchema = z.strictObject({
  id: RunIdSchema,
  fixture_version: z.literal("erp-v1").default("erp-v1"),
  seed: z.number().int().min(0).max(9007199254740991).default(30),
  scenario_id: ScenarioIdSchema,
  elapsed_ms: z.number().int().min(0).max(9007199254740991),
  duration_ms: z.number().int().gt(0).max(9007199254740991),
  revision: z.number().int().min(0).max(9007199254740991),
  event_sequence: z.number().int().min(0).max(9007199254740991),
  playing: z.boolean(),
  speed: z.union([z.literal(1), z.literal(2), z.literal(4)]),
  epoch_at: UtcDateTimeSchema,
  started_at: UtcDateTimeSchema,
  plan_revision: z.number().int().min(0).max(9007199254740991),
}).refine(row => row.elapsed_ms <= row.duration_ms && Date.parse(row.epoch_at) === Date.parse("2026-10-30T00:00:00Z"), "invalid authoritative clock").readonly();
export type OperationsRun = z.infer<typeof OperationsRunSchema>;

export const CurrentRunSchema = z.strictObject({ id: z.literal(1).default(1), run_id: RunIdSchema }).readonly();
export type CurrentRun = z.infer<typeof CurrentRunSchema>;

export const OrderPlanSchema = z.strictObject({
  run_id: RunIdSchema,
  id: EntityIdSchema,
  customer_id: EntityIdSchema,
  product_id: ProductIdSchema,
  grade: z.string(),
  width_mm: z.union([z.number().gt(0), z.null()]).default(null),
  thickness_mm: z.union([z.number().gt(0), z.null()]).default(null),
  quantity_kg: z.number().int().gt(0).max(9007199254740991),
  due_at: z.union([UtcDateTimeSchema, z.null()]).default(null),
}).readonly();
export type OrderPlan = z.infer<typeof OrderPlanSchema>;

export const OperationsOrderSchema = z.strictObject({
  run_id: RunIdSchema,
  id: EntityIdSchema,
  customer_id: EntityIdSchema,
  product_id: ProductIdSchema,
  grade: z.string(),
  width_mm: z.union([z.number().gt(0), z.null()]).default(null),
  thickness_mm: z.union([z.number().gt(0), z.null()]).default(null),
  quantity_kg: z.number().int().gt(0).max(9007199254740991),
  due_at: UtcDateTimeSchema,
}).readonly();
export type OperationsOrder = z.infer<typeof OperationsOrderSchema>;

export const WorkOrderSchema = z.strictObject({
  run_id: RunIdSchema,
  id: EntityIdSchema,
  order_id: EntityIdSchema,
  route_id: EntityIdSchema,
  route_version: z.number().int().gt(0).max(9007199254740991),
  planned_kg: z.number().int().gt(0).max(9007199254740991),
  status: ShipmentStatusSchema.default("PLANNED"),
}).readonly();
export type WorkOrder = z.infer<typeof WorkOrderSchema>;

export const OperationsLotSchema = z.strictObject({
  run_id: RunIdSchema,
  id: EntityIdSchema,
  work_order_id: EntityIdSchema,
  planned_kg: z.number().int().gt(0).max(9007199254740991),
}).readonly();
export type OperationsLot = z.infer<typeof OperationsLotSchema>;

export const MaterialSchema = z.strictObject({
  run_id: RunIdSchema,
  id: EntityIdSchema,
  lot_id: EntityIdSchema,
  lineage_id: EntityIdSchema,
  current_version_id: EntityIdSchema,
  form: MaterialFormSchema,
  weight_kg: z.number().int().gt(0).max(9007199254740991),
  location_id: EntityIdSchema,
  quality_status: QualityStatusSchema,
  availability_status: AvailabilityStatusSchema,
  active: z.boolean(),
}).refine(row => row.active !== (row.availability_status === "CONSUMED"), "only consumed material is inactive").readonly();
export type Material = z.infer<typeof MaterialSchema>;

export const MaterialVersionSchema = z.strictObject({
  run_id: RunIdSchema,
  id: EntityIdSchema,
  material_id: EntityIdSchema,
  ordinal: z.number().int().gt(0).max(9007199254740991),
  parent_version_id: EntityIdSchema.nullable(),
  form: MaterialFormSchema,
  weight_kg: z.number().int().gt(0).max(9007199254740991),
  cause_event_id: EntityIdSchema.nullable(),
}).readonly();
export type MaterialVersion = z.infer<typeof MaterialVersionSchema>;

export const MaterialLineageEdgeSchema = z.strictObject({
  run_id: RunIdSchema,
  id: EntityIdSchema,
  parent_material_id: EntityIdSchema,
  child_material_id: EntityIdSchema,
  process_id: EntityIdSchema,
  transferred_kg: z.number().int().gt(0).max(9007199254740991),
}).readonly();
export type MaterialLineageEdge = z.infer<typeof MaterialLineageEdgeSchema>;

export const MaterialAllocationSchema = z.strictObject({
  run_id: RunIdSchema,
  id: EntityIdSchema,
  order_id: EntityIdSchema,
  work_order_id: EntityIdSchema,
  material_id: EntityIdSchema,
  final_planned_kg: z.number().int().gt(0).max(9007199254740991),
  active: z.boolean(),
}).readonly();
export type MaterialAllocation = z.infer<typeof MaterialAllocationSchema>;

export const ProcessExecutionSchema = z.strictObject({
  run_id: RunIdSchema,
  id: EntityIdSchema,
  material_id: EntityIdSchema,
  route_step_id: EntityIdSchema,
  source_step_id: EntityIdSchema,
  step_ordinal: z.number().int().min(0).max(9007199254740991),
  equipment_id: EntityIdSchema,
  predecessor_id: EntityIdSchema.nullable(),
  status: ProcessStatusSchema,
  planned_duration_ms: z.number().int().gt(0).max(9007199254740991),
  ready_at_ms: z.number().int().min(0).max(9007199254740991).default(0),
  start_ms: z.union([z.number().int().min(0).max(9007199254740991), z.null()]).default(null),
  end_ms: z.union([z.number().int().min(0).max(9007199254740991), z.null()]).default(null),
  input_form: MaterialFormSchema,
  output_form: MaterialFormSchema,
  additions_kg: z.number().int().min(0).max(9007199254740991).default(0),
  loss_kg: z.number().int().min(0).max(9007199254740991).default(0),
  split_count: z.union([z.literal(1), z.literal(2)]).default(1),
  blocked_reason: z.union([z.string(), z.null()]).default(null),
}).refine(row => (row.start_ms === null || row.end_ms === null || row.end_ms > row.start_ms) && (!(row.status === "RUNNING" || row.status === "COMPLETED") || (row.start_ms !== null && row.end_ms !== null)), "invalid process time window").readonly();
export type ProcessExecution = z.infer<typeof ProcessExecutionSchema>;

export const TransferSchema = z.strictObject({
  run_id: RunIdSchema,
  id: EntityIdSchema,
  material_id: EntityIdSchema,
  from_location_id: EntityIdSchema,
  to_location_id: EntityIdSchema,
  mode: TransferModeSchema,
  vehicle_id: EntityIdSchema.nullable().default(null),
  crane_id: EntityIdSchema.nullable().default(null),
  status: TransferStatusSchema,
  phase_start_ms: z.union([z.number().int().min(0).max(9007199254740991), z.null()]).default(null),
  phase_end_ms: z.union([z.number().int().min(0).max(9007199254740991), z.null()]).default(null),
  capacity_kg: z.number().int().gt(0).max(9007199254740991),
  process_id: EntityIdSchema.nullable().default(null),
  travel_duration_ms: z.number().int().gt(0).max(9007199254740991).default(3000),
}).refine(row => (row.mode === "roller" || row.vehicle_id !== null) && (row.phase_start_ms === null || row.phase_end_ms === null || row.phase_end_ms > row.phase_start_ms), "invalid carrier or transfer time").readonly();
export type Transfer = z.infer<typeof TransferSchema>;

export const InspectionSchema = z.strictObject({
  run_id: RunIdSchema,
  id: EntityIdSchema,
  material_id: EntityIdSchema,
  status: QualityStatusSchema,
  inspected_version_id: EntityIdSchema,
  reason: z.union([z.string(), z.null()]).default(null),
  release_event_id: EntityIdSchema.nullable().default(null),
  start_ms: z.union([z.number().int().min(0).max(9007199254740991), z.null()]).default(null),
  end_ms: z.union([z.number().int().min(0).max(9007199254740991), z.null()]).default(null),
  packaging_end_ms: z.union([z.number().int().min(0).max(9007199254740991), z.null()]).default(null),
}).readonly();
export type Inspection = z.infer<typeof InspectionSchema>;

export const OperationsShipmentSchema = z.strictObject({
  run_id: RunIdSchema,
  id: EntityIdSchema,
  order_id: EntityIdSchema,
  mode: z.enum(["SEA", "ROAD"]).default("SEA"),
  status: z.enum(["PLANNED", "ALLOCATED", "LOADING", "LOADED", "DISPATCHED", "AT_PORT", "IN_TRANSIT", "DELIVERED"]),
  location_id: EntityIdSchema,
  capacity_kg: z.number().int().gt(0).max(9007199254740991),
  etd_at: z.union([UtcDateTimeSchema, z.null()]).default(null),
  eta_at: z.union([UtcDateTimeSchema, z.null()]).default(null),
  phase_start_ms: z.union([z.number().int().min(0).max(9007199254740991), z.null()]).default(null),
  phase_end_ms: z.union([z.number().int().min(0).max(9007199254740991), z.null()]).default(null),
  delivered_at: z.union([UtcDateTimeSchema, z.null()]).default(null),
}).readonly();
export type OperationsShipment = z.infer<typeof OperationsShipmentSchema>;

export const ShipmentMaterialSchema = z.strictObject({
  run_id: RunIdSchema,
  id: EntityIdSchema,
  shipment_id: EntityIdSchema,
  material_id: EntityIdSchema,
  active: z.boolean().default(true),
  loaded: z.boolean().default(false),
}).readonly();
export type ShipmentMaterial = z.infer<typeof ShipmentMaterialSchema>;

export const MassMovementSchema = z.strictObject({
  run_id: RunIdSchema,
  id: EntityIdSchema,
  cause_event_id: EntityIdSchema,
  process_id: EntityIdSchema,
  input_material_ids: z.array(EntityIdSchema).readonly(),
  output_material_ids: z.array(EntityIdSchema).readonly(),
  input_kg: z.number().int().min(0).max(9007199254740991),
  output_kg: z.number().int().min(0).max(9007199254740991),
  additions_kg: z.number().int().min(0).max(9007199254740991),
  loss_kg: z.number().int().min(0).max(9007199254740991),
}).refine(row => row.input_kg + row.additions_kg === row.output_kg + row.loss_kg, "mass imbalance").readonly();
export type MassMovement = z.infer<typeof MassMovementSchema>;

export const OperationEventSchema = z.strictObject({
  run_id: RunIdSchema,
  id: EntityIdSchema,
  sequence: z.number().int().gt(0).max(9007199254740991),
  event_type: z.enum(["PLAN_RELEASED", "WORK_ORDER_RELEASED", "MATERIAL_ALLOCATED", "PROCESS_STARTED", "PROCESS_BLOCKED", "PROCESS_COMPLETED", "MATERIAL_TRANSFORMED", "MATERIAL_SPLIT", "TRANSFER_STARTED", "TRANSFER_LOADING", "TRANSFER_DEPARTED", "TRANSFER_UNLOADING", "TRANSFER_ARRIVED", "INSPECTION_STARTED", "INSPECTION_PASSED", "INSPECTION_HELD", "INSPECTION_FAILED", "PACKAGING_STARTED", "PACKAGING_COMPLETED", "MATERIAL_AVAILABLE", "SHIPMENT_ALLOCATED", "SHIPMENT_LOADING", "MATERIAL_LOADED", "SHIPMENT_LOADED", "SHIPMENT_DISPATCHED", "SHIPMENT_AT_PORT", "SHIPMENT_SAILING", "SHIPMENT_DELIVERED", "ORDER_DELIVERED", "RESOURCE_DOWN", "RESOURCE_RESTORED", "RECOVERY_ROUTED"]),
  entity_type: z.enum(["run", "order", "work_order", "lot", "material", "process", "transfer", "inspection", "shipment", "resource"]),
  entity_id: EntityIdSchema,
  at_ms: z.number().int().min(0).max(9007199254740991),
  occurred_at: UtcDateTimeSchema,
  recorded_at: z.union([UtcDateTimeSchema, z.null()]).default(null),
  material_id: EntityIdSchema.nullable().default(null),
  order_id: EntityIdSchema.nullable().default(null),
  process_id: EntityIdSchema.nullable().default(null),
  from_location_id: EntityIdSchema.nullable().default(null),
  to_location_id: EntityIdSchema.nullable().default(null),
  reason: z.union([z.string(), z.null()]).default(null),
}).readonly();
export type OperationEvent = z.infer<typeof OperationEventSchema>;

export const MassBalanceSchema = z.strictObject({
  initial_kg: z.number().int().min(0).max(9007199254740991),
  additions_kg: z.number().int().min(0).max(9007199254740991),
  active_kg: z.number().int().min(0).max(9007199254740991),
  loss_kg: z.number().int().min(0).max(9007199254740991),
}).refine(row => row.initial_kg + row.additions_kg === row.active_kg + row.loss_kg, "mass imbalance").readonly();
export type MassBalance = z.infer<typeof MassBalanceSchema>;

export const OrderForecastSchema = z.strictObject({
  order_id: EntityIdSchema,
  status: z.enum(["ON_TIME", "LATE", "BLOCKED"]),
  eta_at: z.union([UtcDateTimeSchema, z.null()]),
  completion_ms: z.union([z.number().int().min(0).max(9007199254740991), z.null()]),
  reason: z.union([z.string(), z.null()]).default(null),
  plan_revision: z.number().int().min(0).max(9007199254740991),
}).readonly();
export type OrderForecast = z.infer<typeof OrderForecastSchema>;

export const RecoveryComparisonSchema = z.strictObject({
  basis: z.literal('INITIAL_PLAN'), horizon_ms: z.literal(3600000), baseline_hash: z.string(),
  plan_revision: z.number().int().nonnegative(),
  orders: z.array(z.strictObject({
    order_id: EntityIdSchema, delay_eta_at: UtcDateTimeSchema.nullable(), recovery_eta_at: UtcDateTimeSchema.nullable(),
    delay_completion_ms: z.number().int().nonnegative().nullable(), recovery_completion_ms: z.number().int().nonnegative().nullable(),
    improvement_ms: z.number().int(),
  }).refine(row => row.improvement_ms === (row.delay_completion_ms !== null && row.recovery_completion_ms !== null ? row.delay_completion_ms - row.recovery_completion_ms : 0)
    && (row.delay_eta_at === null) === (row.delay_completion_ms === null) && (row.recovery_eta_at === null) === (row.recovery_completion_ms === null), 'inconsistent recovery comparison').readonly()).readonly(),
  routed_material_ids: z.array(EntityIdSchema).readonly(), outage_ms: z.number().int().nonnegative().nullable(),
  roller_duration_ms: z.array(z.number().int().nonnegative()).readonly(), current_available: z.boolean(), current_reason: z.string(),
  recommendation: z.enum(['NO_BENEFIT', 'UNAVAILABLE', 'REVIEW_BENEFIT']),
}).readonly();
export type RecoveryComparison = z.infer<typeof RecoveryComparisonSchema>;

export const ResourceSpecSchema = z.strictObject({
  id: EntityIdSchema,
  location_id: EntityIdSchema,
  capacity_kg: z.number().int().gt(0).max(9007199254740991),
  parallel_capacity: z.number().int().gt(0).max(9007199254740991).default(1),
  compatible_forms: z.array(MaterialFormSchema).readonly(),
  compatible_grades: z.array(z.string()).readonly().default([]),
  min_width_mm: z.union([z.number().gt(0), z.null()]).default(null),
  max_width_mm: z.union([z.number().gt(0), z.null()]).default(null),
  reserve: z.boolean().default(false),
  available_at_ms: z.number().int().min(0).max(9007199254740991).default(0),
  unavailable_from_ms: z.union([z.number().int().min(0).max(9007199254740991), z.null()]).default(null),
  unavailable_until_ms: z.union([z.number().int().min(0).max(9007199254740991), z.null()]).default(null),
  reserved_by: z.union([z.string().min(1), z.null()]).default(null),
}).readonly();
export type ResourceSpec = z.infer<typeof ResourceSpecSchema>;

const PlanSeedShape = z.strictObject({
  work_orders: z.array(WorkOrderSchema).readonly().default([]),
  lots: z.array(OperationsLotSchema).readonly().default([]),
  materials: z.array(MaterialSchema).readonly().default([]),
  material_versions: z.array(MaterialVersionSchema).readonly().default([]),
  lineage_edges: z.array(MaterialLineageEdgeSchema).readonly().default([]),
  allocations: z.array(MaterialAllocationSchema).readonly().default([]),
  processes: z.array(ProcessExecutionSchema).readonly().default([]),
  transfers: z.array(TransferSchema).readonly().default([]),
  inspections: z.array(InspectionSchema).readonly().default([]),
  shipments: z.array(OperationsShipmentSchema).readonly().default([]),
  shipment_materials: z.array(ShipmentMaterialSchema).readonly().default([]),
  mass_movements: z.array(MassMovementSchema).readonly().default([]),
  fixture_version: z.literal("erp-v1").default("erp-v1"),
  seed: z.number().int().min(0).max(9007199254740991).default(30),
  run_id: RunIdSchema,
  orders: z.array(OrderPlanSchema).readonly(),
  resources: z.array(ResourceSpecSchema).readonly().default([]),
}).readonly();
export type PlanSeed = z.infer<typeof PlanSeedShape>;
export const PlanSeedSchema = PlanSeedShape.superRefine((seed, ctx) => {
  for (const rows of [seed.orders, seed.work_orders, seed.lots, seed.materials, seed.material_versions, seed.lineage_edges, seed.allocations, seed.processes, seed.transfers, seed.inspections, seed.shipments, seed.shipment_materials, seed.mass_movements]) {
    if (rows.some(row => row.run_id !== seed.run_id) || new Set(rows.map(row => row.id)).size !== rows.length) ctx.addIssue({ code: "custom", message: "cross_run or duplicate_id" });
  }
});

const OperationsSnapshotShape = z.strictObject({
  work_orders: z.array(WorkOrderSchema).readonly().default([]),
  lots: z.array(OperationsLotSchema).readonly().default([]),
  materials: z.array(MaterialSchema).readonly().default([]),
  material_versions: z.array(MaterialVersionSchema).readonly().default([]),
  lineage_edges: z.array(MaterialLineageEdgeSchema).readonly().default([]),
  allocations: z.array(MaterialAllocationSchema).readonly().default([]),
  processes: z.array(ProcessExecutionSchema).readonly().default([]),
  transfers: z.array(TransferSchema).readonly().default([]),
  inspections: z.array(InspectionSchema).readonly().default([]),
  shipments: z.array(OperationsShipmentSchema).readonly().default([]),
  shipment_materials: z.array(ShipmentMaterialSchema).readonly().default([]),
  mass_movements: z.array(MassMovementSchema).readonly().default([]),
  schema_version: z.literal(2).default(2),
  run: OperationsRunSchema,
  orders: z.array(OperationsOrderSchema).readonly(),
  events: z.array(OperationEventSchema).readonly().default([]),
  mass_balance: MassBalanceSchema,
  forecast: z.array(OrderForecastSchema).readonly().default([]),
}).readonly();
export type OperationsSnapshot = z.infer<typeof OperationsSnapshotShape>;
export const OperationsSnapshotSchema = OperationsSnapshotShape.superRefine(checkSnapshotRelations);

export const SimulationCommandSchema = z.strictObject({
  action: z.enum(["play", "pause", "reset", "step", "speed", "scenario"]),
  run_id: RunIdSchema.nullable().default(null),
  expected_revision: z.union([z.number().int().min(0).max(9007199254740991), z.null()]).default(null),
  command_id: EntityIdSchema.nullable().default(null),
  steps: z.union([z.number().int().min(1).max(48), z.null()]).default(null),
  speed: z.union([z.union([z.literal(1), z.literal(2), z.literal(4)]), z.null()]).default(null),
  scenario_id: z.union([ScenarioIdSchema, z.null()]).default(null),
}).refine(row => (row.action === "step" || row.steps === null) && (row.action === "speed" ? row.speed !== null : row.action === "play" || row.speed === null) && (row.action === "scenario" ? row.scenario_id !== null : row.scenario_id === null), "payload does not match action").readonly();
export type SimulationCommand = z.infer<typeof SimulationCommandSchema>;

export const CommandReceiptSchema = z.strictObject({
  run_id: RunIdSchema,
  command_id: EntityIdSchema,
  action: z.enum(["play", "pause", "reset", "step", "speed", "scenario"]),
  payload_digest: z.string().regex(new RegExp("^[a-f0-9]{64}$")),
  applied_revision: z.number().int().min(0).max(9007199254740991),
}).readonly();
export type CommandReceipt = z.infer<typeof CommandReceiptSchema>;

export const TransitionDeltaSchema = z.strictObject({
  work_orders: z.array(WorkOrderSchema).readonly().default([]),
  lots: z.array(OperationsLotSchema).readonly().default([]),
  materials: z.array(MaterialSchema).readonly().default([]),
  material_versions: z.array(MaterialVersionSchema).readonly().default([]),
  lineage_edges: z.array(MaterialLineageEdgeSchema).readonly().default([]),
  allocations: z.array(MaterialAllocationSchema).readonly().default([]),
  processes: z.array(ProcessExecutionSchema).readonly().default([]),
  transfers: z.array(TransferSchema).readonly().default([]),
  inspections: z.array(InspectionSchema).readonly().default([]),
  shipments: z.array(OperationsShipmentSchema).readonly().default([]),
  shipment_materials: z.array(ShipmentMaterialSchema).readonly().default([]),
  mass_movements: z.array(MassMovementSchema).readonly().default([]),
  orders: z.array(OperationsOrderSchema).readonly().default([]),
  events: z.array(OperationEventSchema).readonly().default([]),
  resources: z.array(ResourceSpecSchema).readonly().default([]),
}).readonly();
export type TransitionDelta = z.infer<typeof TransitionDeltaSchema>;

export function checkSnapshotRelations(world: OperationsSnapshot, ctx: z.RefinementCtx): void {
  const issue = (message: string): void => { ctx.addIssue({ code: "custom", message }); };
  const groups = [world.orders, world.work_orders, world.lots, world.materials, world.material_versions,
    world.lineage_edges, world.allocations, world.processes, world.transfers, world.inspections,
    world.shipments, world.shipment_materials, world.mass_movements, world.events];
  for (const group of groups) {
    if (new Set(group.map(row => row.id)).size !== group.length) issue("duplicate_id");
    if (group.some(row => row.run_id !== world.run.id)) issue("cross_run");
  }
  const orders = new Map(world.orders.map(row => [row.id, row]));
  const works = new Map(world.work_orders.map(row => [row.id, row]));
  const lots = new Map(world.lots.map(row => [row.id, row]));
  const materials = new Map(world.materials.map(row => [row.id, row]));
  const versions = new Map(world.material_versions.map(row => [row.id, row]));
  const processes = new Map(world.processes.map(row => [row.id, row]));
  const shipments = new Map(world.shipments.map(row => [row.id, row]));
  const events = new Map(world.events.map(row => [row.id, row]));
  const required = (found: boolean): void => { if (!found) issue("missing_reference"); };
  for (const row of world.work_orders) required(orders.has(row.order_id));
  for (const row of world.lots) required(works.has(row.work_order_id));
  for (const row of world.materials) {
    required(lots.has(row.lot_id));
    const version = versions.get(row.current_version_id);
    required(version !== undefined);
    if (version && (version.material_id !== row.id || version.form !== row.form || version.weight_kg !== row.weight_kg)) issue("current_version");
  }
  for (const row of world.material_versions) {
    required(materials.has(row.material_id));
    if (row.parent_version_id !== null) required(versions.has(row.parent_version_id));
  }
  for (const row of world.processes) {
    required(materials.has(row.material_id));
    if (row.predecessor_id !== null) required(processes.has(row.predecessor_id));
  }
  for (const row of world.transfers) required(materials.has(row.material_id));
  for (const row of world.shipments) required(orders.has(row.order_id));
  for (const row of world.inspections) {
    required(materials.has(row.material_id));
    required(versions.has(row.inspected_version_id));
    if (versions.get(row.inspected_version_id)?.material_id !== row.material_id) issue("inspection_version");
  }
  if (new Set(world.material_versions.map(row => `${row.material_id}/${row.ordinal}`)).size !== world.material_versions.length) issue("version_ordinal");
  for (const ids of [world.allocations.filter(row => row.active).map(row => row.material_id),
    world.transfers.filter(row => row.status !== "ARRIVED").map(row => row.material_id),
    world.shipment_materials.filter(row => row.active).map(row => row.material_id)]) {
    if (new Set(ids).size !== ids.length) issue("active_assignment");
  }
  for (const row of world.allocations) {
    const material = materials.get(row.material_id);
    const work = works.get(row.work_order_id);
    required(material !== undefined && work !== undefined && orders.has(row.order_id));
    if (material && work && (work.order_id !== row.order_id || lots.get(material.lot_id)?.work_order_id !== work.id)) issue("allocation_order");
    if (material && row.active && !material.active) issue("consumed_allocation");
  }
  for (const row of world.shipment_materials) {
    const material = materials.get(row.material_id);
    const shipment = shipments.get(row.shipment_id);
    required(material !== undefined && shipment !== undefined);
    const lot = material && lots.get(material.lot_id);
    const work = lot && works.get(lot.work_order_id);
    if (shipment && work && shipment.order_id !== work.order_id) issue("shipment_order");
  }
  const pairs = world.lineage_edges.map(row => `${row.parent_material_id}/${row.child_material_id}`);
  if (new Set(pairs).size !== pairs.length) issue("lineage_duplicate");
  const adjacency = new Map<EntityId, Set<EntityId>>();
  for (const edge of world.lineage_edges) {
    required(materials.has(edge.parent_material_id) && materials.has(edge.child_material_id) && processes.has(edge.process_id));
    if (materials.get(edge.parent_material_id)?.active) issue("split_parent");
    const children = adjacency.get(edge.parent_material_id) ?? new Set<EntityId>();
    children.add(edge.child_material_id);
    adjacency.set(edge.parent_material_id, children);
  }
  for (const [origin, children] of adjacency) {
    const pending = [...children];
    const visited = new Set<EntityId>();
    while (pending.length > 0) {
      const node = pending.pop();
      if (node === undefined) break;
      if (node === origin) issue("lineage_cycle");
      if (!visited.has(node)) {
        visited.add(node);
        pending.push(...(adjacency.get(node) ?? []));
      }
    }
  }
  for (const row of world.mass_movements) {
    if (!processes.has(row.process_id) || !events.has(row.cause_event_id) || [...row.input_material_ids, ...row.output_material_ids].some(id => !materials.has(id))) issue("mass_reference");
  }
  if (new Set(world.mass_movements.map(row => row.process_id)).size !== world.mass_movements.length) issue("mass_process");
  if (world.materials.filter(row => row.active).reduce((sum, row) => sum + row.weight_kg, 0) !== world.mass_balance.active_kg) issue("active_mass");
}

/** Backend workspace mirror for transition consumers; maps are intentionally mutable. */
export type SimulationModel = {
  run: OperationsRun;
  readonly orders: Map<EntityId, OperationsOrder>;
  readonly work_orders: Map<EntityId, WorkOrder>;
  readonly lots: Map<EntityId, OperationsLot>;
  readonly materials: Map<EntityId, Material>;
  readonly material_versions: Map<EntityId, MaterialVersion>;
  readonly lineage_edges: Map<EntityId, MaterialLineageEdge>;
  readonly allocations: Map<EntityId, MaterialAllocation>;
  readonly processes: Map<EntityId, ProcessExecution>;
  readonly transfers: Map<EntityId, Transfer>;
  readonly inspections: Map<EntityId, Inspection>;
  readonly shipments: Map<EntityId, OperationsShipment>;
  readonly shipment_materials: Map<EntityId, ShipmentMaterial>;
  readonly mass_movements: Map<EntityId, MassMovement>;
  readonly events: Map<EntityId, OperationEvent>;
  readonly resources: Map<EntityId, ResourceSpec>;
};
export type TransitionResult = { readonly model: SimulationModel; readonly delta: TransitionDelta };
export type TransportTransition = (model: SimulationModel, transferId: EntityId, atMs: number) => TransitionResult;
export type FulfillmentTransition = (model: SimulationModel, entityId: EntityId, atMs: number) => TransitionResult;
export type NextBoundary = (model: SimulationModel) => number | null;
export type ReadyTransfers = (model: SimulationModel) => readonly EntityId[];
