import { readFileSync } from 'node:fs';
import { z } from 'zod';
import { evaluateMotion, MotionError, parseMotionRegistry } from './contracts';
import { parseMotionRequest } from './request';

try {
  const path = process.argv[2];
  if (path === undefined) throw new MotionError('invalid_contract', 'request path required');
  const input = parseMotionRequest(new Uint8Array(readFileSync(path)));
  const registry = parseMotionRegistry(new Uint8Array(readFileSync('shared/motion-recipes.json')));
  console.log(JSON.stringify(evaluateMotion(input.envelope, input.context, registry)));
} catch (error) {
  if (error instanceof MotionError) { console.log(JSON.stringify({ error: { code: error.code, reference: error.reference } })); process.exitCode = 2; }
  else if (error instanceof z.ZodError) { console.log(JSON.stringify({ error: { code: 'invalid_contract', reference: 'request' } })); process.exitCode = 2; }
  else throw error;
}
