export type AssetErrorCode = 'path' | 'network' | 'hash' | 'glb' | 'binding' | 'cancelled' | 'stale' | 'identity' | 'unsupported';
export class AssetLoadError extends Error {
  readonly name = 'AssetLoadError';
  constructor(readonly code: AssetErrorCode, readonly reference: string, options?: ErrorOptions) {
    super(`${code}: ${reference}`, options);
  }
}
export function requireAsset(condition: unknown, code: AssetErrorCode, reference: string): asserts condition {
  if (!condition) throw new AssetLoadError(code, reference);
}
