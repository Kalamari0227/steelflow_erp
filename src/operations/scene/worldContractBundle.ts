import { z } from 'zod';
import { parseWorld } from './worldContract';
import { parseContractJson, requireContract } from './worldContractJson';

const identifier = z.string().regex(/^[A-Za-z0-9][A-Za-z0-9_.:-]*(?![\s\S])/);
const digest = z.string().regex(/^[a-f0-9]{64}(?![\s\S])/);
const artifactSchema = z.strictObject({
  role: z.enum(['world', 'asset', 'motion', 'recipe', 'coverage', 'fixture', 'scenario']),
  path: z.string().regex(/^[A-Za-z0-9_-][A-Za-z0-9_.-]*(?:\/[A-Za-z0-9_-][A-Za-z0-9_.-]*)*(?![\s\S])/),
  version: identifier, sha256: digest,
}).readonly();
const manifestSchema = z.strictObject({
  format: z.literal('factory-bundle-v1'), bundle_id: identifier, world_version: z.literal(2),
  artifacts: z.array(artifactSchema).min(1).readonly(), bundle_hash: digest,
}).readonly();
export type BundleManifest = z.infer<typeof manifestSchema>;

export function parseManifest(raw: string): BundleManifest {
  const manifest = manifestSchema.parse(parseContractJson(raw));
  requireContract(new Set(manifest.artifacts.map(row => row.path)).size === manifest.artifacts.length, 'duplicate', 'artifact paths');
  requireContract(manifest.artifacts.filter(row => row.role === 'world').length === 1, 'reference', 'world artifact');
  for (const row of manifest.artifacts) if (row.role === 'world') requireContract(row.version === '2', 'version', row.path);
  return manifest;
}

export function canonicalManifest(manifest: BundleManifest): string {
  const entries = [...manifest.artifacts].sort((a, b) => a.path < b.path ? -1 : a.path > b.path ? 1 : 0);
  return `factory-bundle-v1\n${manifest.bundle_id}\n2\n${entries.map(row => `${row.role}\t${row.path}\t${row.version}\t${row.sha256}\n`).join('')}`;
}
export async function sha256(bytes: Uint8Array): Promise<string> {
  const hash = await globalThis.crypto.subtle.digest('SHA-256', new Uint8Array(bytes));
  return Array.from(new Uint8Array(hash), byte => byte.toString(16).padStart(2, '0')).join('');
}
export async function parseBundle(rawManifest: string, artifacts: ReadonlyMap<string, Uint8Array>) {
  const manifest = parseManifest(rawManifest);
  // Snapshot caller-owned bytes before any await: verification and parsing use the same bytes.
  const snapshots = new Map(manifest.artifacts.map(row => {
    const bytes = artifacts.get(row.path);
    requireContract(bytes !== undefined, 'reference', row.path);
    return [row.path, new Uint8Array(bytes)] as const;
  }));
  requireContract(await sha256(new TextEncoder().encode(canonicalManifest(manifest))) === manifest.bundle_hash, 'bundle_hash', manifest.bundle_id);
  for (const row of manifest.artifacts) {
    const bytes = snapshots.get(row.path);
    requireContract(bytes !== undefined, 'reference', row.path);
    requireContract(await sha256(bytes) === row.sha256, 'artifact_hash', row.path);
  }
  const worldEntry = manifest.artifacts.find(row => row.role === 'world');
  requireContract(worldEntry !== undefined, 'reference', 'world artifact');
  const bytes = snapshots.get(worldEntry.path);
  requireContract(bytes !== undefined, 'reference', worldEntry.path);
  const world = parseWorld(new TextDecoder('utf-8', { fatal: true }).decode(bytes));
  return Object.freeze({ manifest, world });
}
