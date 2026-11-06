import { z } from 'zod';

export const JourneyStepSchema = z.object({
  id: z.string(), name: z.string(), equipment_kind: z.string(),
  duration_ms: z.number().int().positive(), input_form: z.string(), output_form: z.string(), description: z.string(),
});
export const ProductDefinitionSchema = z.object({
  id: z.string(), family: z.string(), name: z.string(), description: z.string(),
  source_url: z.string().url(), source_title: z.string(), input_form: z.string(), output_form: z.string(),
  mass_kg: z.number().int().positive(), steps: z.array(JourneyStepSchema).min(1),
});
export const JourneyCatalogSchema = z.object({ products: z.array(ProductDefinitionSchema) });
export const JourneySnapshotSchema = z.object({
  data_scope: z.literal('synthetic_product_journey'), run_id: z.string(), revision: z.number().int(),
  product_id: z.string(), playing: z.boolean(), speed: z.union([z.literal(1), z.literal(2), z.literal(4)]),
  elapsed_ms: z.number().nonnegative(), duration_ms: z.number().positive(),
  active_step_id: z.string(), step_elapsed_ms: z.number().nonnegative(), step_duration_ms: z.number().positive(), completed: z.boolean(),
  material: z.object({
    lineage_id: z.string(), version_id: z.string(), parent_version_id: z.string().nullable(),
    form: z.string(), role: z.enum(['feedstock', 'sale_product']), location_id: z.string(), mass_kg: z.number().positive(),
  }),
  history: z.array(z.object({ version_id: z.string(), parent_version_id: z.string().nullable(), form: z.string(), step_id: z.string(), at_ms: z.number() })),
});
export type JourneyStep = z.infer<typeof JourneyStepSchema>;
export type ProductDefinition = z.infer<typeof ProductDefinitionSchema>;
export type JourneySnapshot = z.infer<typeof JourneySnapshotSchema>;
export type JourneyCommand = { action: 'play' | 'pause' | 'reset' | 'step' }
  | { action: 'select'; product_id: string } | { action: 'speed'; speed: 1 | 2 | 4 };
