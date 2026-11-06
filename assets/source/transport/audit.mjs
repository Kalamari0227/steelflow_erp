/** Exhaustive retained source audit. A rejected row stays RED; no variant substitution. */
import {readFileSync,writeFileSync} from 'node:fs';
import {resolve} from 'node:path';
import {productionParser} from '../../../scripts/assets/production-parser.mjs';
import {readGlb,hash,requireProof} from '../../../scripts/assets/glb.mjs';
import {productionLoader} from './production-loader.mjs';
import {checkSolidCoverage} from './verify.mjs';
import {contractModule} from './contracts.mjs';
const root=resolve(process.argv[2]),output=resolve(process.argv[3]),dir=resolve(root,'public/assets/steelworks/transport');
const candidatePath=resolve(dir,'manifest-candidate.json'),registeredPath=resolve(dir,'manifest.json'),candidate=JSON.parse(readFileSync(candidatePath)),registered=JSON.parse(readFileSync(registeredPath));
if(process.argv.includes('--stamp'))for(const [path,manifest]of [[candidatePath,candidate],[registeredPath,registered]]){for(const a of manifest.assets)for(const l of a.lods){requireProof(l.semantic_geometry_sha256===null,'stamp','refuse restamp');l.semantic_geometry_sha256=readGlb(readFileSync(resolve(root,l.artifact.path))).semantic;}writeFileSync(path,JSON.stringify(manifest,null,2)+'\n');}
const inventory=JSON.parse(readFileSync(resolve(root,'assets/source/transport/solid-inventory.json'))),parse=(process.argv.includes('--contract-root')?(await contractModule(process.argv[process.argv.indexOf('--contract-root')+1],'src/operations/scene/assets/manifest.ts')).parseProductionAssetManifest:await productionParser()),{loadAsset}=process.argv.includes('--contract-root')?await contractModule(process.argv[process.argv.indexOf('--contract-root')+1],'src/operations/scene/assets/loader.ts'):await productionLoader(),rows=[];
for(const asset of candidate.assets){let admissionError=null;try{parse(JSON.stringify({schema_version:1,purpose:'production',assets:[asset]}));}catch(error){if(!(error instanceof Error))throw error;admissionError=error.message;}
  const lods=[];
  for(const lod of asset.lods){const actual=readFileSync(resolve(root,lod.artifact.path));requireProof(hash(actual)===lod.artifact.sha256,'hash',lod.artifact.path);const parsed=readGlb(actual),solid=inventory.assets.find(s=>s.asset_id===asset.id&&s.lod===lod.level);requireProof(solid,'solid','missing source inventory');let loaderError=null;
    try{const loaded=await loadAsset(asset,lod,{origin:'http://127.0.0.1:43128',read:async()=>actual.buffer.slice(actual.byteOffset,actual.byteOffset+actual.byteLength)});loaded.dispose();}catch(error){if(!(error instanceof Error))throw error;loaderError=error.message;}
    const pbr=[];for(const m of asset.materials){const raw=parsed.gltf.materials.find(r=>r.name===m.id&&r.extras?.semantic_id===m.id),p=raw?.pbrMetallicRoughness;requireProof(p,'PBR','missing '+m.id);requireProof((p.baseColorFactor??[1,1,1,1]).every((v,i)=>Math.abs(v-m.base_color[i])<1e-5)&&Math.abs(p.metallicFactor-m.metallic)<1e-5&&Math.abs(p.roughnessFactor-m.roughness)<1e-5,'PBR','actual exact material factors');pbr.push(m.id);}
    lods.push({level:lod.level,sha256:hash(actual),triangles:parsed.triangles,semantic:parsed.semantic,sourceCoverage:checkSolidCoverage(asset,lod,parsed,solid),loaderError,pbr});
  }
  requireProof(lods.length===3&&lods[0].triangles>lods[1].triangles&&lods[1].triangles>lods[2].triangles,'LOD','strictly decreasing actual triangles '+asset.id);
  rows.push({assetId:asset.id,variant:asset.variant,kind:asset.kind,placementIds:asset.placement_ids,admissionError,lods,physicalCycle:'NOT_PROVEN',independentVisualReview:'PENDING',runtimeInstalled:false});
}
const failures=rows.filter(r=>r.admissionError||r.lods.some(l=>l.loaderError)),result={status:failures.length?'INCOMPLETE_SOURCE_CAPABILITY_GAPS':'SOURCE_GEOMETRY_CHECKED_PHYSICAL_ACCEPTANCE_PENDING',candidateManifestSha256:hash(readFileSync(candidatePath)),assets:rows.length,lods:rows.reduce((n,r)=>n+r.lods.length,0),rejectedAssets:failures.length,rows,unmet:['All-family finite material operations and actual runtime remain mandatory.','No independent allvariant visual approval or installed T66/T16 chain.','Every unregistered/unsupported row remains a failure; generic siblings cannot replace it.']};writeFileSync(output,JSON.stringify(result,null,2)+'\n');console.log(JSON.stringify({status:result.status,assets:result.assets,lods:result.lods,rejected:failures.map(r=>({id:r.assetId,admission:r.admissionError,loader:r.lods.find(l=>l.loaderError)?.loaderError??null}))}));process.exitCode=failures.length?1:0;
