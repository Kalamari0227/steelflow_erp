import { createHash } from 'node:crypto';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { z } from 'zod';
import type { Asset } from '../../../src/operations/scene/assets/manifest';

const record=z.record(z.string(),z.unknown());
const rows=(value:unknown)=>z.array(record).parse(value);
const hash=(value:Uint8Array)=>createHash('sha256').update(value).digest('hex');
function canonical(value:unknown):string{
  if(Array.isArray(value))return `[${value.map((v:unknown)=>canonical(v)).join(',')}]`;
  if(value!==null&&typeof value==='object')return `{${Object.keys(value).sort().map(k=>`${JSON.stringify(k)}:${canonical(Reflect.get(value,k))}`).join(',')}}`;
  const text=JSON.stringify(value);if(text===undefined)throw new RangeError('Non-JSON mutant');return text;
}
export type FixedMutation='no-mesh'|'own-track'|'child-track'|'translation-track'|'scale-track'|'reparent';

/** Re-sign only intentional in-memory responses. Original actual LOD files remain unchanged. */
export function mutateFixed(asset:Asset,level:number,mode:FixedMutation,root:string){
  const lod=asset.lods.find(l=>l.level===level),part=asset.fixed_parts[0];if(!lod||!part||lod.artifact.status!=='built')throw new RangeError('Actual fixed-part LOD missing');
  const original=readFileSync(resolve(root,lod.artifact.path)),length=original.readUInt32LE(12),raw=record.parse(JSON.parse(original.subarray(20,20+length).toString('utf8'))),binary=original.subarray(28+length);
  const nodes=rows(raw.nodes),index=nodes.findIndex(n=>record.parse(n.extras).semantic_id===part.node_id),node=nodes[index];if(!node)throw new RangeError('Actual fixed node absent');
  const subtree=(i:number):number[]=>[i,...z.array(z.number()).parse(nodes[i]?.children??[]).flatMap(subtree)];
  switch(mode){
    case 'no-mesh':for(const i of subtree(index)){const target=nodes[i];if(!target)throw new RangeError('Missing owned fixed geometry');Reflect.deleteProperty(target,'mesh');}break;
    case 'reparent':{
      for(const n of nodes)if(n.children)n.children=z.array(z.number()).parse(n.children).filter(i=>i!==index);
      const rootNode=nodes.find(n=>record.parse(n.extras).semantic_id===asset.root_node_id);if(!rootNode)throw new RangeError('Actual root absent');rootNode.children=[...z.array(z.number()).parse(rootNode.children??[]),index];break;
    }
    case 'own-track':case 'child-track':case 'translation-track':case 'scale-track':{
      const clips=rows(raw.animations),clip=clips[0];if(!clip)throw new RangeError('Canonical animation absent');const channels=rows(clip.channels),source=channels[0];if(!source)throw new RangeError('Canonical channel absent');
      const target=mode==='child-track'?subtree(index)[1]:index;if(target===undefined)throw new RangeError('Owned child absent');
      channels.push({...source,target:{node:target,path:mode==='translation-track'?'translation':mode==='scale-track'?'scale':'rotation'}});clip.channels=channels;raw.animations=clips;break;
    }
  }
  raw.nodes=nodes;const encoded=Buffer.from(JSON.stringify(raw)),padded=Buffer.alloc(Math.ceil(encoded.length/4)*4,32);encoded.copy(padded);const bytes=Buffer.alloc(28+padded.length+binary.length);
  bytes.write('glTF');bytes.writeUInt32LE(2,4);bytes.writeUInt32LE(bytes.length,8);bytes.writeUInt32LE(padded.length,12);bytes.writeUInt32LE(0x4e4f534a,16);padded.copy(bytes,20);bytes.writeUInt32LE(binary.length,20+padded.length);bytes.writeUInt32LE(0x004e4942,24+padded.length);binary.copy(bytes,28+padded.length);
  const changed={...asset,lods:asset.lods.map(l=>l.level===level?{...l,artifact:{...l.artifact,sha256:hash(bytes)},semantic_geometry_sha256:hash(Buffer.concat([Buffer.from(`${canonical(raw)}\0`),binary]))}:l)};
  return {asset:changed,lod:changed.lods.find(l=>l.level===level),bytes:new Uint8Array(bytes).buffer,sha256:hash(bytes),originalSha256:hash(original)};
}
