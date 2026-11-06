import { z } from 'zod';
import { parseMotionContext } from './context';
import { MotionError } from './errors';
import { motionJson } from './json';
import { envelopeShape } from './shapes';
import type { MotionEnvelope } from './shapes';
import { preflight } from './structure';

const requestShape = z.strictObject({ envelope: z.unknown(), context: z.unknown() });
export function parseEnvelopeValue(value: unknown): MotionEnvelope {
  preflight(value, 'envelope');
  const parsed = envelopeShape.safeParse(value);
  if (!parsed.success) throw new MotionError('invalid_contract', 'envelope');
  return parsed.data;
}
export function parseMotionRequestValue(value: unknown) {
  preflight(value);
  const input = requestShape.parse(value);
  const envelope = parseEnvelopeValue(input.envelope);
  const context = parseMotionContext(input.context);
  return Object.freeze({ envelope, context });
}
export function parseMotionRequest(raw: string | Uint8Array) {
  return parseMotionRequestValue(motionJson(raw));
}
