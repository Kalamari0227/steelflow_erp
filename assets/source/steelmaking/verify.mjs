/** Inspect family artifacts through the production parser and established GLB geometry oracle. */
import { readFileSync, writeFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { productionParser } from '../../../scripts/assets/production-parser.mjs';
import { readGlb, validateAssetGlb, requireProof, hash } from '../../../scripts/assets/glb.mjs';
import { localArtifact } from '../../../scripts/assets/verify.mjs';

export async function verifyFamily(root, family, { stamp = false } = {}) {
  requireProof(['steelmaking','stainless'].includes(family),'family',family);
  const path=resolve(root,`public/assets/steelworks/${family}/manifest.json`);
  const raw=JSON.parse(readFileSync(path,'utf8'));
  if(stamp){
    for(const asset of raw.assets)for(const lod of asset.lods){
      requireProof(lod.semantic_geometry_sha256===null,'stamp','refuse existing semantic digest');
      lod.semantic_geometry_sha256=readGlb(localArtifact(root,lod.artifact)).semantic;
    }
    writeFileSync(path,JSON.stringify(raw,null,2)+'\n');
    writeFileSync(resolve(root,'public/assets/steelworks/manifest.json'),JSON.stringify(raw,null,2)+'\n');
  }
  const parse=await productionParser(),manifest=parse(readFileSync(path,'utf8'));
  const recipe=JSON.parse(readFileSync(resolve(root,`assets/source/${family}/recipe.json`),'utf8'));
  const inventory=JSON.parse(readFileSync(resolve(root,`assets/source/${family}/inventory.json`),'utf8'));
  const tool=JSON.parse(readFileSync(resolve(root,'assets/toolchain.json'),'utf8'));
  requireProof(tool.version==='4.5.15'&&hash(readFileSync(tool.executable_path))===tool.executable_sha256,'toolchain','exact pinned Blender');
  requireProof(inventory.external_asset_count===0&&recipe.external_asset_count===0,'license','original sources only');
  for(const resource of [inventory.license,...inventory.inputs,...inventory.authored_assets,...inventory.textures])localArtifact(root,resource);
  const assets=[];
  for(const asset of manifest.assets){
    requireProof(asset.family===family,'family',asset.id);
    localArtifact(root,asset.source.artifact);localArtifact(root,asset.export.recipe);localArtifact(root,asset.export.tool_artifact);
    for(const material of asset.materials)localArtifact(root,material.provenance.recipe);
    const lods=asset.lods.map(lod=>{
      const parsed=readGlb(localArtifact(root,lod.artifact));
      const proof=validateAssetGlb(asset,parsed,recipe.axis_markers);
      const fixedSupports=asset.fixed_parts.filter(p=>p.binding===null).map(part=>{
        const index=parsed.gltf.nodes.findIndex(n=>n.extras?.semantic_id===part.node_id),node=parsed.gltf.nodes[index];
        requireProof(node,'fixed-support',part.id);
        const parents=new Map();parsed.gltf.nodes.forEach((n,i)=>(n.children??[]).forEach(c=>parents.set(c,i)));
        let ancestor=index;
        while(ancestor!==undefined){requireProof(!(parsed.gltf.animations??[]).some(a=>a.channels.some(c=>c.target.node===ancestor)),'fixed-support','stationary ancestor '+part.id);ancestor=parents.get(ancestor);}
        requireProof(node.mesh!==undefined||(node.children??[]).some(i=>parsed.gltf.nodes[i].mesh!==undefined),'fixed-support','actual support mesh '+part.id);
        return {id:part.id,binding:null,physicalMotion:false};
      });
      requireProof(parsed.semantic===lod.semantic_geometry_sha256,'semantic',asset.id);
      requireProof(parsed.gltf.materials.length===asset.materials.length,'materials','exact semantic PBR set');
      for(const material of asset.materials){
        const actual=parsed.gltf.materials.find(m=>m.name===material.id&&m.extras?.semantic_id===material.id)?.pbrMetallicRoughness;
        requireProof(actual&&(actual.baseColorFactor??[1,1,1,1]).every((v,i)=>Math.abs(v-material.base_color[i])<1e-5)&&Math.abs(actual.metallicFactor-material.metallic)<1e-5&&Math.abs(actual.roughnessFactor-material.roughness)<1e-5,'material',material.id);
      }
      return {level:lod.level,...proof,fixedSupports};
    });
    requireProof(lods.length===3&&lods[0].triangles>lods[1].triangles&&lods[1].triangles>lods[2].triangles,'lod',asset.id);
    assets.push({id:asset.id,variant:asset.variant,placements:asset.placement_ids,lods});
  }
  return {status:'PASS',family,variants:assets.length,placements:assets.flatMap(a=>a.placements).length,manifestSha256:hash(readFileSync(path)),assets,limits:['Synthetic family contract fixture; independent visual review and T28/T31 production integration remain separate.']};
}
if(process.argv[1]&&resolve(process.argv[1])===fileURLToPath(import.meta.url)){
  try{const args=process.argv.slice(2),root=args[args.indexOf('--root')+1],family=args[args.indexOf('--family')+1];requireProof(root&&family,'usage','verify.mjs --root ROOT --family steelmaking|stainless [--stamp]');console.log(JSON.stringify(await verifyFamily(resolve(root),family,{stamp:args.includes('--stamp')}),null,2));}
  catch(error){console.error(error instanceof Error?error.message:String(error));process.exitCode=1;}
}
