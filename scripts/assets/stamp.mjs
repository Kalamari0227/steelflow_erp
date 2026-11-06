import { readFileSync, writeFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { readGlb, requireProof } from './glb.mjs';
import { localArtifact, verify } from './verify.mjs';

try {
requireProof(process.argv.length===4&&process.argv[2]==='--root','usage','stamp --root OUTPUT_ROOT');
const root=resolve(process.argv[3]);const path=resolve(root,'public/assets/steelworks/manifest.json');
const manifest=JSON.parse(readFileSync(path,'utf8'));
for(const asset of manifest.assets)for(const lod of asset.lods) {
  requireProof(lod.semantic_geometry_sha256===null,'stamp','refuse to restamp an existing semantic digest');
  lod.semantic_geometry_sha256=readGlb(localArtifact(root,lod.artifact)).semantic;
}
writeFileSync(path,JSON.stringify(manifest,null,2)+'\n');
const result=await verify(root);
writeFileSync(resolve(root,'public/assets/steelworks/verification.json'),JSON.stringify(result,null,2)+'\n');
console.log('STEELFLOW_VERIFIED '+result.assets.length+' actual assets');

} catch(error) { console.error(error instanceof Error ? error.message : String(error)); process.exitCode=1; }
