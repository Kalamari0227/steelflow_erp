import { createHash } from 'node:crypto';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { z } from 'zod';
import type { Asset } from '../../../src/operations/scene/assets/manifest';

const record = z.record(z.string(), z.unknown());
const rows = (value: unknown) => z.array(record).parse(value);
const hash = (value: Uint8Array) => createHash('sha256').update(value).digest('hex');
function canonical(value: unknown): string {
  if (Array.isArray(value)) return `[${value.map((v: unknown) => canonical(v)).join(',')}]`;
  if (value !== null && typeof value === 'object') return `{${Object.keys(value).sort().map(k => `${JSON.stringify(k)}:${canonical(Reflect.get(value,k))}`).join(',')}}`;
  const encoded = JSON.stringify(value); if (encoded === undefined) throw new Error('Corruption fixture received non-JSON'); return encoded;
}

/** Re-sign only this intentional test response, leaving all source and installed bytes untouched. */
export function corruptAsset(asset: Asset, mode: 'pivot'|'binding', root='.') {
  const lod = asset.lods[0], part = asset.moving_parts[0];
  if (!lod || !part || lod.artifact.status !== 'built') throw new Error('Actual family LOD/part missing');
  const original = readFileSync(resolve(root,lod.artifact.path)), length = original.readUInt32LE(12);
  const raw = record.parse(JSON.parse(original.subarray(20,20+length).toString('utf8'))), binary = original.subarray(28+length);
  switch (mode) {
    case 'pivot': {
      const nodes = rows(raw.nodes), node = nodes.find(n => record.parse(n.extras).semantic_id === part.node_id);
      if (!node) throw new Error('Actual corruption target absent');
      const position = z.array(z.number()).length(3).parse(node.translation ?? [0,0,0]);
      node.translation = [position[0],(position[1] ?? 0)+.2,position[2]]; raw.nodes = nodes; break;
    }
    case 'binding': {
      const animations = rows(raw.animations), clip = animations.find(a => part.binding.type === 'clip' && a.name === part.binding.clip_id);
      if (!clip) throw new Error('Actual corruption clip absent'); clip.name = 'intentional-invalid-binding'; raw.animations = animations; break;
    }
  }
  const json = Buffer.from(JSON.stringify(raw)), padded = Buffer.alloc(Math.ceil(json.length/4)*4,32); json.copy(padded);
  const bytes = Buffer.alloc(28+padded.length+binary.length);
  bytes.write('glTF'); bytes.writeUInt32LE(2,4); bytes.writeUInt32LE(bytes.length,8); bytes.writeUInt32LE(padded.length,12); bytes.writeUInt32LE(0x4e4f534a,16); padded.copy(bytes,20);
  bytes.writeUInt32LE(binary.length,20+padded.length); bytes.writeUInt32LE(0x004e4942,24+padded.length); binary.copy(bytes,28+padded.length);
  return { bytes, asset: { ...asset, lods: asset.lods.map(l => l.level === 0 ? { ...l, artifact:{ ...l.artifact,sha256:hash(bytes) },semantic_geometry_sha256:hash(Buffer.concat([Buffer.from(`${canonical(raw)}\0`),binary])) } : l) }, originalSha256:hash(original), changedSha256:hash(bytes) };
}
