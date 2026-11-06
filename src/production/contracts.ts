import { z } from 'zod';

export const StageIdSchema = z.enum(['ironmaking', 'steelmaking', 'casting', 'hot_rolling', 'cold_rolling', 'coating', 'finishing', 'stock']);
export const ProductSchema = z.enum(['SLAB', 'BLOOM', 'BILLET', 'HR', 'CR', 'GI', 'GA', 'EG', 'HGI']);
const StatusSchema = z.enum(['queued', 'running', 'completed']);
const BatchStatusSchema = z.enum(['queued', 'running', 'in_transit', 'completed']);
const RoleSchema = z.enum(['feedstock', 'sale_product']);
export const ProductionTransportSchema = z.object({
  id: z.string(), batch_id: z.string(), vehicle_id: z.string(),
  vehicle_kind: z.enum(['flatbed_truck', 'hot_metal_car', 'ladle_car']),
  material_id: z.string(), material_form: z.string(), mass_kg: z.number(),
  from_stage: StageIdSchema, to_stage: StageIdSchema,
  start_tick: z.number(), end_tick: z.number(), status: z.enum(['queued', 'in_transit', 'completed']),
});
export const ProductionStepSchema = z.object({ id: z.string(), stage_id: StageIdSchema, name: z.string(), equipment_id: z.string(), start_tick: z.number(), end_tick: z.number(), status: StatusSchema });
const MaterialVersionSchema = z.object({ id: z.string(), parent_id: z.string().nullable(), form: z.string(), role: RoleSchema, stage_id: StageIdSchema, created_tick: z.number() });
export const ProductionBatchSchema = z.object({
  id: z.string(), source_fixture_id: z.string(), product: ProductSchema, mass_kg: z.number(),
  material_id: z.string(), parent_material_id: z.string().nullable(), material_form: z.string(), material_role: RoleSchema,
  current_stage: StageIdSchema, current_step: z.string(), equipment_id: z.string(), status: BatchStatusSchema,
  current_location_id: z.string(), active_transport_id: z.string().nullable(),
  route: z.array(StageIdSchema), route_progress: z.number(), steps: z.array(ProductionStepSchema), material_history: z.array(MaterialVersionSchema),
});
export const ProductionStageSchema = z.object({
  id: StageIdSchema, name: z.string(), equipment_ids: z.array(z.string()), substeps: z.array(z.string()),
  queued_count: z.number(), running_count: z.number(), completed_count: z.number(),
  queued_mass_kg: z.number(), running_mass_kg: z.number(), completed_mass_kg: z.number(), batch_ids: z.array(z.string()),
});
export const ProductionSchema = z.object({
  tick: z.number(), scenario_id: z.enum(['NORMAL', 'DELAY', 'RECOVERY']), data_scope: z.literal('synthetic_production_only'),
  total_mass_kg: z.number(), completed_mass_kg: z.number(), batches: z.array(ProductionBatchSchema), stages: z.array(ProductionStageSchema), transports: z.array(ProductionTransportSchema),
});
export type StageId = z.infer<typeof StageIdSchema>;
export type Product = z.infer<typeof ProductSchema>;
export type Production = z.infer<typeof ProductionSchema>;
export type ProductionStage = z.infer<typeof ProductionStageSchema>;
export type ProductionBatch = z.infer<typeof ProductionBatchSchema>;
export type ProductionStep = z.infer<typeof ProductionStepSchema>;
export type ProductionTransport = z.infer<typeof ProductionTransportSchema>;
