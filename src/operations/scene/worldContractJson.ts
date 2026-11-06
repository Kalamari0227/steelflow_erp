export class WorldContractError extends Error {
  readonly name = 'WorldContractError';
  constructor(readonly code: string, readonly reference: string) { super(`${code}: ${reference}`); }
}

export function requireContract(condition: boolean, code: string, reference: string): asserts condition {
  if (!condition) throw new WorldContractError(code, reference);
}

/** Native syntax checking plus duplicate decoded object-key rejection. */
export function parseContractJson(raw: string): unknown {
  let parsed: unknown;
  try { parsed = JSON.parse(raw); }
  catch (error) {
    if (error instanceof SyntaxError) throw new WorldContractError('json', error.message);
    throw error;
  }
  const objects: Set<string>[] = [];
  for (const token of raw.matchAll(/"(?:\\.|[^"\\])*"|[{}]/g)) {
    const text = token[0];
    switch (text) {
      case '{': objects.push(new Set()); break;
      case '}': objects.pop(); break;
      default: {
        if (!raw.slice(token.index + text.length).trimStart().startsWith(':')) break;
        const key: unknown = JSON.parse(text);
        const current = objects.at(-1);
        if (typeof key === 'string' && current) {
          requireContract(!current.has(key), 'json', `duplicate key: ${key}`);
          current.add(key);
        }
      }
    }
  }
  return parsed;
}
