import { z } from 'zod';

// The final guard excludes trailing newlines as well as ordinary extra characters.
const utcInput = /^(?!0000)([0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2})(?:\.([0-9]{1,3})0{0,3})?(?:Z|\+00:00)(?![\s\S])/;

export const utcSchema = z.string().transform((value, context) => {
  const parts = utcInput.exec(value);
  if (!parts) {
    context.addIssue({ code: 'custom', message: 'UTC string with exact millisecond precision required' });
    return z.NEVER;
  }
  const canonical = `${parts[1]}.${(parts[2] ?? '').padEnd(3, '0')}Z`;
  const date = new Date(canonical);
  if (!Number.isFinite(date.valueOf()) || date.toISOString() !== canonical) {
    context.addIssue({ code: 'custom', message: 'valid UTC calendar value required' });
    return z.NEVER;
  }
  return canonical;
});

export const MaterialDimensionsSchema = z.strictObject({
  length_mm: z.number().finite().gt(0).nullable(),
  width_mm: z.number().finite().gt(0).nullable(),
  thickness_mm: z.number().finite().gt(0).nullable(),
  diameter_mm: z.number().finite().gt(0).nullable(),
  inner_diameter_mm: z.number().finite().gt(0).nullable(),
}).readonly();

export const FactoryRunSchema = z.strictObject({
  id: z.string().min(1),
  fixture_version: z.literal("factory-v2"),
  bundle_id: z.string().min(1),
  bundle_hash: z.string().regex(/^[0-9a-f]{64}$/),
  profile: z.enum(["v3_contract_test", "demo", "scale"]),
  scenario_id: z.enum(["NORMAL", "DELAY", "RECOVERY"]),
  seed: z.number().int().safe().min(0).max(9007199254740991),
  elapsed_ms: z.number().int().safe().min(0).max(4193483039999),
  duration_ms: z.number().int().safe().max(4193483039999).gt(0),
  revision: z.number().int().safe().min(0).max(9007199254740991),
  event_sequence: z.number().int().safe().min(0).max(9007199254740991),
  playing: z.boolean(),
  speed: z.union([z.literal(1), z.literal(2), z.literal(4)]),
  epoch_at: utcSchema,
  started_at: utcSchema,
}).readonly();
