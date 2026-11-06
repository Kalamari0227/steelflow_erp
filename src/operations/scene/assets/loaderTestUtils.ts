import { readFileSync } from 'node:fs';
import { createHash } from 'node:crypto';
import { z } from 'zod';
import { parseProductionAssetManifest } from './manifest';
import type { AssetReader } from './loader';

export const rawManifest = readFileSync('public/assets/steelworks/manifest.json', 'utf8');
export const actualManifest = parseProductionAssetManifest(rawManifest);
export const origin = 'http://127.0.0.1:4176';
export const identity = { run_id: 'test-run', entity_type: 'equipment', entity_id: 'CUT-SLAB', bundle_hash: 'a'.repeat(64) } as const;
export const readActual: AssetReader = async url => new Uint8Array(readFileSync(`public${new URL(url).pathname}`)).buffer;
export function shear() {
  const asset = actualManifest.assets.find(a => a.kind === 'shear');
  if (!asset) throw new RangeError('Actual shear missing');
  return asset;
}
export function deferred<T>() {
  let resolve: (value: T) => void = () => { throw new RangeError('Deferred not initialized'); };
  const promise = new Promise<T>(accept => { resolve = accept; });
  return { promise, resolve };
}
const record = z.record(z.string(), z.unknown());
export function glbRows(raw: Record<string, unknown>, key: string): Record<string, unknown>[] {
  const rows = z.array(record).parse(raw[key]); raw[key] = rows; return rows;
}
function sortedJson(value: unknown): string {
  if (Array.isArray(value)) return `[${value.map((item: unknown) => sortedJson(item)).join(',')}]`;
  if (value !== null && typeof value === 'object') return `{${Object.keys(value).sort().map(key => `${JSON.stringify(key)}:${sortedJson(Reflect.get(value, key))}`).join(',')}}`;
  const result = JSON.stringify(value); if (result === undefined) throw new RangeError('Not JSON'); return result;
}
/** Mutate actual GLB bytes and re-sign only the test's declared checksums to exercise structure admission. */
export function mutateActual(change: (raw: Record<string, unknown>) => void) {
  const asset = shear(), lod = asset.lods[0];
  if (!lod || lod.artifact.status !== 'built') throw new RangeError('Actual LOD missing');
  const input = readFileSync(lod.artifact.path), jsonLength = input.readUInt32LE(12);
  const raw = record.parse(JSON.parse(input.subarray(20, 20 + jsonLength).toString('utf8')));
  const binary = input.subarray(28 + jsonLength); change(raw);
  const json = Buffer.from(JSON.stringify(raw)), padding = Buffer.alloc(Math.ceil(json.length / 4) * 4, 32); json.copy(padding);
  const output = Buffer.alloc(28 + padding.length + binary.length);
  output.write('glTF'); output.writeUInt32LE(2, 4); output.writeUInt32LE(output.length, 8); output.writeUInt32LE(padding.length, 12); output.writeUInt32LE(0x4e4f534a, 16); padding.copy(output, 20);
  output.writeUInt32LE(binary.length, 20 + padding.length); output.writeUInt32LE(0x004e4942, 24 + padding.length); binary.copy(output, 28 + padding.length);
  const digest = (bytes: Uint8Array) => createHash('sha256').update(bytes).digest('hex');
  const updated = { ...lod, artifact: { ...lod.artifact, sha256: digest(output) }, semantic_geometry_sha256: digest(Buffer.concat([Buffer.from(`${sortedJson(raw)}\0`), binary])) };
  const admitted = parseProductionAssetManifest(JSON.stringify({ ...actualManifest, assets: actualManifest.assets.map(row => row.id === asset.id ? { ...row, lods: row.lods.map(level => level.level === 0 ? updated : level) } : row) }));
  const changedAsset = admitted.assets.find(row => row.id === asset.id), changedLod = changedAsset?.lods[0];
  if (!changedAsset || !changedLod) throw new RangeError('Mutated asset missing');
  return { bytes: new Uint8Array(output).buffer, asset: changedAsset, lod: changedLod };
}
