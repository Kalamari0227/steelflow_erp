import type { APIRequestContext, BrowserContext, Route } from '@playwright/test';
import { readFile } from 'node:fs/promises';
import { z } from 'zod';
import { assertAllowedPort, assertOwnedHealth, type OwnedIdentity } from '../../tools/qa/ownership.mjs';

const IdentitySchema = z.object({
  attempt_id: z.string().min(1),
  db_fingerprint: z.string().regex(/^[a-f0-9]{64}$/),
  pid: z.number().int().positive(),
  web_pid: z.number().int().positive(),
  api_origin: z.string().url(),
  web_origin: z.string().url(),
}).strict();

export class QaOwnershipError extends Error {
  constructor(message: string) { super(`QA ownership refused: ${message}`); }
}

function allowedOrigin(value: string): string {
  const url = new URL(value);
  if (url.protocol !== 'http:' || url.hostname !== '127.0.0.1' || url.username || url.password) {
    throw new QaOwnershipError('only the owned loopback HTTP origin is allowed');
  }
  assertAllowedPort(Number(url.port));
  return url.origin;
}

export async function readQaIdentity(): Promise<OwnedIdentity> {
  const path = process.env.STEELFLOW_QA_IDENTITY_PATH;
  if (!path || !process.env.STEELFLOW_QA_ATTEMPT_ID) throw new QaOwnershipError('runner receipt and attempt are required');
  const identity = IdentitySchema.parse(JSON.parse(await readFile(path, 'utf8')));
  if (identity.attempt_id !== process.env.STEELFLOW_QA_ATTEMPT_ID) throw new QaOwnershipError('stale runner attempt');
  for (const origin of [identity.api_origin, identity.web_origin]) {
    if (allowedOrigin(origin) !== origin) throw new QaOwnershipError('receipt must contain canonical origins');
  }
  return identity;
}

export async function assertOwnedMutation(request: APIRequestContext, target?: string): Promise<string> {
  const identity = await readQaIdentity();
  if (target) {
    const origin = allowedOrigin(target);
    if (![identity.api_origin, identity.web_origin].includes(origin)) throw new QaOwnershipError('target is outside the runner receipt');
  }
  const health = await request.get(target ? new URL('/health', target).href : '/health', { maxRedirects: 0, timeout: 10_000 });
  const origin = allowedOrigin(health.url());
  if (![identity.api_origin, identity.web_origin].includes(origin)) throw new QaOwnershipError('health is outside the runner receipt');
  if (!health.ok()) throw new QaOwnershipError(`health HTTP ${health.status()}`);
  assertOwnedHealth(await health.json(), identity);
  return origin;
}

export async function postOwnedOperation(request: APIRequestContext, endpoint: string, data?: Readonly<Record<string, unknown>>) {
  if (!endpoint.startsWith('/api/v1/')) throw new QaOwnershipError('operation must use an API path');
  const origin = await assertOwnedMutation(request);
  return request.post(`${origin}${endpoint}`, { data, maxRedirects: 0 });
}

export async function guardBrowserMutations(context: BrowserContext) {
  const refused: { url: string; reason: string }[] = [];
  const guard = async (route: Route): Promise<void> => {
    const request = route.request();
    if (['GET', 'HEAD', 'OPTIONS'].includes(request.method())) { await route.fallback(); return; }
    try {
      await assertOwnedMutation(context.request, request.url());
    } catch (error) {
      if (!(error instanceof Error)) throw error;
      refused.push({ url: request.url(), reason: error.message });
      await route.abort('blockedbyclient');
      return;
    }
    await route.fallback();
  };
  await context.route('**/*', guard);
  return { refused, dispose: () => context.unroute('**/*', guard) };
}
