import { readFileSync } from 'node:fs';
import { createHash } from 'node:crypto';
import { z } from 'zod';
import { parseProductionAssetManifest } from '../../../src/operations/scene/assets/manifest';
import { required } from '../../../src/operations/scene/assets/manifestTestFixtures';

const root = 'tests/fixtures/mechanical-followers/generated';
const record = z.record(z.string(), z.unknown());
export function rows(raw: Record<string, unknown>, key: string): Record<string, unknown>[] {
  const parsed = z.array(record).parse(raw[key]); raw[key] = parsed; return parsed;
}
function canonical(value: unknown): string {
  if (Array.isArray(value)) return `[${value.map((child: unknown) => canonical(child)).join(',')}]`;
  if (value !== null && typeof value === 'object') return `{${Object.keys(value).sort().map(key => `${JSON.stringify(key)}:${canonical(Reflect.get(value, key))}`).join(',')}}`;
  const result = JSON.stringify(value); if (result === undefined) throw new RangeError('Not JSON'); return result;
}
/** Re-sign only this test's declared checksums so semantic validation observes actual corrupt bytes. */
export function mutateMiniature(change: (raw: Record<string, unknown>, binary: Buffer) => void) {
  const manifest = parseProductionAssetManifest(readFileSync(`${root}/public/assets/steelworks/manifest.json`, 'utf8'));
  const asset = required(manifest.assets[0]), lod = required(asset.lods[0]);
  const input = readFileSync(`${root}/${lod.artifact.path}`), length = input.readUInt32LE(12);
  const raw = record.parse(JSON.parse(input.subarray(20, 20 + length).toString('utf8'))), binary = Buffer.from(input.subarray(28 + length));
  change(raw, binary);
  const encoded = Buffer.from(JSON.stringify(raw)), padding = Buffer.alloc(Math.ceil(encoded.length / 4) * 4, 32); encoded.copy(padding);
  const output = Buffer.alloc(28 + padding.length + binary.length);
  output.write('glTF'); output.writeUInt32LE(2, 4); output.writeUInt32LE(output.length, 8); output.writeUInt32LE(padding.length, 12); output.writeUInt32LE(0x4e4f534a, 16); padding.copy(output, 20);
  output.writeUInt32LE(binary.length, 20 + padding.length); output.writeUInt32LE(0x004e4942, 24 + padding.length); binary.copy(output, 28 + padding.length);
  const hash = (bytes: Uint8Array) => createHash('sha256').update(bytes).digest('hex');
  const updated = { ...lod, artifact: { status: 'built', path: lod.artifact.path, sha256: hash(output) }, semantic_geometry_sha256: hash(Buffer.concat([Buffer.from(`${canonical(raw)}\0`), binary])) };
  const changed = required(parseProductionAssetManifest(JSON.stringify({ ...manifest, assets: [{ ...asset, lods: asset.lods.map(row => row.level === 0 ? updated : row) }] })).assets[0]);
  return { bytes: new Uint8Array(output).buffer, asset: changed, lod: required(changed.lods[0]) };
}
