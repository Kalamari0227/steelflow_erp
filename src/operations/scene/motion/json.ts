import { parseContractJson, WorldContractError } from '../worldContractJson';
import { MotionError } from './errors';

const motionIntegers = new Set(['schema_version', 'revision', 'confirmed_sim_ms', 'phase_start_ms', 'phase_end_ms', 'effective_sim_ms', 'at_ms']);
/** Retain integer lexical strictness before JavaScript erases 1 versus 1.0. */
export function motionJson(input: string | Uint8Array, scope: 'request' | 'envelope' | 'context' | 'registry' = 'request'): unknown {
  let raw: string;
  try { raw = typeof input === 'string' ? input : new TextDecoder('utf-8', { fatal: true }).decode(input); }
  catch (error) {
    if (error instanceof TypeError) throw new MotionError('json', 'UTF-8');
    throw error;
  }
  let parsed: unknown;
  try { parsed = parseContractJson(raw); }
  catch (error) {
    if (error instanceof WorldContractError) throw new MotionError(error.reference.startsWith('duplicate key:') ? 'duplicate' : 'json', error.reference);
    throw error;
  }
  checkIntegerTokens(raw, scope);
  return parsed;
}

// T5 strict scalar aliases: Ms/Duration, NonNegative/Positive, Kg/PositiveKg, Speed.
// T3's json_integer accepts integral decimal/exponent spellings; its floats stay floats.
const snapshotIntegers = new Set([
  'seed', 'elapsed_ms', 'duration_ms', 'revision', 'event_sequence', 'speed',
  'quantity_kg', 'route_version', 'planned_kg', 'received_at_ms', 'weight_kg',
  'ordinal', 'transferred_kg', 'start_ms', 'end_ms', 'ready_at_ms',
  'planned_duration_ms', 'at_ms', 'sequence', 'capacity_kg', 'available_at_ms',
  'acquired_at_ms', 'released_at_ms', 'eta_ms',
]);

function checkIntegerTokens(raw: string, scope: 'request' | 'envelope' | 'context' | 'registry'): void {
  const tokens = [...raw.matchAll(/"(?:\\.|[^"\\])*"|[{}\[\]:,]|-?(?:0|[1-9]\d*)(?:\.\d+)?(?:[eE][+-]?\d+)?|true|false|null/g)].map(match => match[0]);
  let cursor = 0;
  function value(path: readonly string[]): void {
    const token = tokens[cursor++];
    if (token === '{') {
      while (tokens[cursor] !== '}') {
        const key: unknown = JSON.parse(tokens[cursor++] ?? 'null');
        cursor++; // Colon; syntax was already checked by parseContractJson.
        if (typeof key !== 'string') throw new MotionError('json', 'object key');
        value([...path, key]);
        if (tokens[cursor] !== ',') break;
        cursor++;
      }
      cursor++;
    } else if (token === '[') {
      while (tokens[cursor] !== ']') {
        value(path);
        if (tokens[cursor] !== ',') break;
        cursor++;
      }
      cursor++;
    } else if (token !== undefined && /^-?\d/.test(token)) {
      const key = path.at(-1) ?? '';
      const snapshot = path[0] === 'context' && path[1] === 'snapshot';
      const world = path[0] === 'context' && path[1] === 'world';
      const strict = snapshot ? snapshotIntegers.has(key) : !world && motionIntegers.has(key);
      if (strict && !/^-?(?:0|[1-9]\d*)$/.test(token)) throw new MotionError('invalid_contract', path.join('.'));
    }
  }
  value(scope === 'context' ? ['context'] : []);
}
