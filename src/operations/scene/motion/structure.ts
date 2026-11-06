import { z } from 'zod';
import generated from '../../../../shared/motion-request.schema.json';
import { MotionError, assertNever } from './errors';

type Primitive = string | number | boolean | null;
type SchemaNode = {
  readonly $defs?: Readonly<Record<string, SchemaNode>>;
  readonly $ref?: string;
  readonly type?: 'object' | 'array' | 'string' | 'null' | 'boolean' | 'number' | 'integer';
  readonly properties?: Readonly<Record<string, SchemaNode>>;
  readonly required?: readonly string[];
  readonly additionalProperties?: boolean | SchemaNode;
  readonly items?: SchemaNode;
  readonly prefixItems?: readonly SchemaNode[];
  readonly anyOf?: readonly SchemaNode[];
  readonly const?: Primitive;
  readonly enum?: readonly Primitive[];
  readonly minItems?: number;
  readonly maxItems?: number;
  readonly minLength?: number;
  readonly minimum?: number;
  readonly maximum?: number;
  readonly exclusiveMinimum?: number;
  readonly gt?: number;
  readonly le?: number;
  readonly pattern?: string;
  readonly title?: string;
  readonly default?: unknown;
  readonly format?: 'date-time';
};
const primitive = z.union([z.string(), z.number().finite(), z.boolean(), z.null()]);
const node: z.ZodType<SchemaNode> = z.lazy(() => z.strictObject({
  $defs: z.record(z.string(), node).readonly().optional(), $ref: z.string().optional(),
  type: z.enum(['object', 'array', 'string', 'null', 'boolean', 'number', 'integer']).optional(),
  properties: z.record(z.string(), node).readonly().optional(), required: z.array(z.string()).readonly().optional(),
  additionalProperties: z.union([z.boolean(), node]).optional(), items: node.optional(),
  prefixItems: z.array(node).readonly().optional(), anyOf: z.array(node).readonly().optional(),
  const: primitive.optional(), enum: z.array(primitive).readonly().optional(),
  minItems: z.number().int().nonnegative().optional(), maxItems: z.number().int().nonnegative().optional(),
  minLength: z.number().int().nonnegative().optional(), minimum: z.number().finite().optional(),
  maximum: z.number().finite().optional(), exclusiveMinimum: z.number().finite().optional(),
  gt: z.number().finite().optional(), le: z.number().finite().optional(), pattern: z.string().optional(),
  title: z.string().optional(), default: z.unknown().optional(), format: z.literal('date-time').optional(),
}).readonly());
const patterns = new Set([
  '^[A-Za-z0-9][A-Za-z0-9_.:-]*$', '^v2:[A-Za-z0-9][A-Za-z0-9_.:-]*$', '^[0-9a-f]{64}$',
  '^(?!0000)[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(?:\\.[0-9]{1,3}0{0,3})?(?:Z|\\+00:00)(?![\\s\\S])',
]);

function own<T>(values: Readonly<Record<string, T>> | undefined, key: string): T | undefined {
  return values !== undefined && Object.hasOwn(values, key) ? values[key] : undefined;
}

/** Admit exactly the generated profile. No remote resolution or silent new keywords. */
export function admitProfile(input: unknown): SchemaNode {
  const result = node.safeParse(input);
  if (!result.success) throw new MotionError('invalid_contract', 'unsupported motion schema profile');
  const schema = result.data;
  function visit(current: SchemaNode, refs: ReadonlySet<string>): void {
    if (current.additionalProperties === true) throw new MotionError('invalid_contract', 'open motion schema object');
    if (current.pattern !== undefined && !patterns.has(current.pattern)) throw new MotionError('invalid_contract', 'unsupported motion schema pattern');
    if (current.$ref !== undefined) {
      const target = own(schema.$defs, current.$ref.slice('#/$defs/'.length));
      if (!current.$ref.startsWith('#/$defs/') || refs.has(current.$ref) || target === undefined) throw new MotionError('invalid_contract', 'nonlocal, missing or cyclic motion schema');
      visit(target, new Set([...refs, current.$ref]));
    }
    for (const child of [...Object.values(current.properties ?? {}), ...Object.values(current.$defs ?? {}), ...current.prefixItems ?? [], ...current.anyOf ?? []]) visit(child, refs);
    if (current.items !== undefined) visit(current.items, refs);
    if (typeof current.additionalProperties === 'object') visit(current.additionalProperties, refs);
  }
  visit(schema, new Set());
  return schema;
}
const schema = admitProfile(generated);
const record = (value: unknown): value is Readonly<Record<string, unknown>> => typeof value === 'object' && value !== null && !Array.isArray(value);

function matches(value: unknown, current: SchemaNode): boolean {
  if (current.$ref !== undefined) {
    const target = own(schema.$defs, current.$ref.slice('#/$defs/'.length));
    if (target === undefined || !matches(value, target)) return false;
  }
  if (current.anyOf !== undefined && !current.anyOf.some(child => matches(value, child))) return false;
  const numeric = typeof value === 'number' && Number.isFinite(value);
  switch (current.type) {
    case 'object': if (!record(value)) return false; break;
    case 'array': if (!Array.isArray(value)) return false; break;
    case 'string': if (typeof value !== 'string') return false; break;
    case 'null': if (value !== null) return false; break;
    case 'boolean': if (typeof value !== 'boolean') return false; break;
    case 'number': if (!numeric) return false; break;
    case 'integer': if (!numeric || !Number.isInteger(value)) return false; break;
    case undefined: break;
    default: return assertNever(current.type);
  }
  if ('const' in current && value !== current.const) return false;
  if (current.enum !== undefined && !current.enum.some(option => value === option)) return false;
  if (record(value)) {
    if (current.required?.some(key => !Object.hasOwn(value, key))) return false;
    for (const [key, item] of Object.entries(value)) {
      const child = own(current.properties, key);
      if (child !== undefined) { if (!matches(item, child)) return false; }
      else if (current.additionalProperties === false) return false;
      else if (typeof current.additionalProperties === 'object' && !matches(item, current.additionalProperties)) return false;
    }
  }
  if (Array.isArray(value)) {
    if (value.length < (current.minItems ?? 0) || (current.maxItems !== undefined && value.length > current.maxItems)) return false;
    for (let index = 0; index < value.length; index++) {
      const child = current.prefixItems?.[index] ?? current.items;
      if (child !== undefined && !matches(value[index], child)) return false;
    }
  }
  if (typeof value === 'string' && ([...value].length < (current.minLength ?? 0) || (current.pattern !== undefined && !new RegExp(current.pattern).test(value)))) return false;
  if (typeof value === 'number' && numeric) {
    if (current.minimum !== undefined && value < current.minimum) return false;
    if (current.maximum !== undefined && value > current.maximum) return false;
    if (current.exclusiveMinimum !== undefined && value <= current.exclusiveMinimum) return false;
    if (current.gt !== undefined && value <= current.gt) return false;
    if (current.le !== undefined && value > current.le) return false;
  }
  return true;
}

/** Shape barrier only: real public parsers must still perform every semantic check. */
export function preflight(value: unknown, scope: 'request' | 'envelope' | 'context' = 'request'): void {
  const target = scope === 'request' ? schema : own(schema.properties, scope);
  if (target === undefined || !matches(value, target)) throw new MotionError('invalid_contract', scope);
}
