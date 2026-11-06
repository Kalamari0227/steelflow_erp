export class MotionError extends Error {
  readonly name = 'MotionError';
  constructor(readonly code: string, readonly reference: string) { super(`${code}: ${reference}`); }
}
export function requireMotion(condition: boolean, code: string, reference: string): asserts condition {
  if (!condition) throw new MotionError(code, reference);
}
export function unique(values: readonly string[], reference: string): void {
  requireMotion(new Set(values).size === values.length, 'duplicate', reference);
}
export function assertNever(value: never): never { throw new MotionError('invalid_contract', String(value)); }
export function equalData(a: unknown, b: unknown): boolean {
  if (Object.is(a, b)) return true;
  if (typeof a !== 'object' || a === null || typeof b !== 'object' || b === null) return false;
  if (Array.isArray(a) !== Array.isArray(b)) return false;
  const entries = Object.entries(a), other = Object.entries(b);
  return entries.length === other.length && entries.every(([key, value]) => Object.hasOwn(b, key) && equalData(value, Reflect.get(b, key)));
}
