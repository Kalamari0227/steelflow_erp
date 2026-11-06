/** Inspect every actual LOD and preserve all failures without certifying admission. */
import {readFileSync,writeFileSync} from 'node:fs';
import {resolve} from 'node:path';
import {readGlb,validateAssetGlb,hash,requireProof} from './oracle.mjs';
const args=process.argv.slice(2),value=k=>args[args.indexOf(k)+1],root=resolve(value('--root')),bytes=readFileSync(resolve(root,'public/assets/steelworks/finishing/manifest.json'));
requireProof(args.includes('--expected-sha')&&hash(bytes)===value('--expected-sha'),'preflight','exact independent actual manifest SHA');
const manifest=JSON.parse(bytes),expected=JSON.parse(readFileSync('.omo/evidence/uniform-fidelity/uf-20261030-resume06/task-21/preparation/inventory.json','utf8')).rows.map(r=>r.owner_id).sort();
requireProof(manifest.assets.length===58&&JSON.stringify(manifest.assets.map(a=>a.placement_ids[0].replace('equipment:','')).sort())===JSON.stringify(expected)&&manifest.assets.every(a=>a.family==='finishing'&&a.lods.length===3),'preflight','full 58 owner/174LOD universe');
const recipe=JSON.parse(readFileSync(resolve(root,'assets/source/finishing/recipe.json'),'utf8')),results=[];
for(const asset of manifest.assets)for(const lod of asset.lods){const file=readFileSync(resolve(root,lod.artifact.path));requireProof(hash(file)===lod.artifact.sha256,'preflight','actual LOD SHA');try{const decoded=readGlb(file),result=validateAssetGlb(asset,decoded,recipe.axis_markers);requireProof(decoded.semantic===lod.semantic_geometry_sha256,'semantic',asset.id);results.push({owner:asset.placement_ids[0],lod:lod.level,status:'GEOMETRY_ORACLE_PASS',...result});}catch(error){results.push({owner:asset.placement_ids[0],lod:lod.level,status:'FAIL',error:error instanceof Error?error.message:String(error)});}}
const failed=results.filter(r=>r.status==='FAIL'),report={status:failed.length?'FAIL':'GEOMETRY_ONLY_PASS',manifestSha256:hash(bytes),admissionClaim:false,checkedLods:results.length,failedLods:failed.length,results};
writeFileSync(value('--out'),JSON.stringify(report,null,2)+'\n');console.log(JSON.stringify({checked:results.length,failed:failed.map(r=>({owner:r.owner,lod:r.lod,error:r.error}))}));process.exitCode=failed.length?1:0;
