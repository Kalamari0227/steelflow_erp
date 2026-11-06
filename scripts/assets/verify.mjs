import { readFileSync, realpathSync, statSync } from 'node:fs';
import { resolve, sep } from 'node:path';
import { fileURLToPath } from 'node:url';
import { canonical, hash, readGlb, requireProof, validateAssetGlb, png } from './glb.mjs';
import { productionParser } from './production-parser.mjs';

export function localArtifact(root, artifact) {
  requireProof(artifact?.status==='built'&&typeof artifact.path==='string'&&/^[A-Za-z0-9_./-]+$/.test(artifact.path)&&!artifact.path.startsWith('/')&&!artifact.path.split('/').includes('..'),'path','local artifact only');
  const realRoot=realpathSync(root),path=realpathSync(resolve(realRoot,artifact.path));
  requireProof(path.startsWith(realRoot+sep)&&statSync(path).isFile(),'path','escaped root or not file');
  const bytes=readFileSync(path);requireProof(hash(bytes)===artifact.sha256,'hash',artifact.path);return bytes;
}
export async function verify(root) {
  const parse=await productionParser();
  const manifest=parse(readFileSync(resolve(root,'public/assets/steelworks/manifest.json'),'utf8'));
  const tool=JSON.parse(readFileSync(resolve(root,'assets/toolchain.json'),'utf8'));
  const trustedTool=JSON.parse(readFileSync(fileURLToPath(new URL('../../assets/toolchain.json',import.meta.url)),'utf8'));
  requireProof(tool.executable_path===trustedTool.executable_path&&tool.executable_sha256===trustedTool.executable_sha256,'toolchain','trusted local executable pin');
  requireProof(tool.version==='4.5.15'&&tool.architecture==='arm64'&&tool.archive_sha256==='bfbc0bda099d1ab7aef0992a584f872f58bed9bb491210ad45f9ca071aa2e688','toolchain','exact official tool');
  requireProof(hash(readFileSync(tool.executable_path))===tool.executable_sha256,'toolchain','actual executable hash');
  requireProof(tool.tool_license_path===trustedTool.tool_license_path&&tool.tool_license_sha256===trustedTool.tool_license_sha256&&hash(readFileSync(tool.tool_license_path))===tool.tool_license_sha256,'license','actual retained tool license');
  const recipe=JSON.parse(readFileSync(resolve(root,'assets/source/recipe.json'),'utf8'));
  const projectMarkers={axis_origin:[0,0,0],axis_front:[1,0,0],axis_up:[0,1,0],axis_side:[0,0,-1]};
  requireProof(canonical(recipe.axis_markers)===canonical(projectMarkers),'axis','immutable project metre marker convention');
  const inventory=JSON.parse(readFileSync(resolve(root,'assets/source/inventory.json'),'utf8'));
  requireProof(inventory.external_asset_count===0&&recipe.external_asset_count===0,'license','external asset inventory');
  for(const entry of [inventory.license,...inventory.inputs,...inventory.authored_assets,...inventory.textures])localArtifact(root,entry);
  const results=[];
  for(const asset of manifest.assets) {
    const source=localArtifact(root,asset.source.artifact);
    // Compressed .blend files use zstd; Blender itself reopens them during the manual source proof.
    requireProof(source.length>1000,'source','nonempty editable Blender artifact');
    localArtifact(root,asset.export.tool_artifact);localArtifact(root,asset.export.recipe);
    for(const resource of [asset.source,...asset.materials,...asset.textures]) {
      requireProof(resource.provenance.origin==='self_created'&&resource.provenance.third_party_inputs.length===0,'license','original tracked authorship');
      localArtifact(root,resource.provenance.recipe);
    }
    const textureHashes=new Map(asset.textures.map(texture=>{const bytes=localArtifact(root,texture.artifact);png(bytes);return[texture.id,hash(bytes)];}));
    const lods=[];
    for(const lod of asset.lods) {
      const parsed=readGlb(localArtifact(root,lod.artifact));
      const proof=validateAssetGlb(asset,parsed,projectMarkers);
      requireProof(parsed.gltf.materials.length===asset.materials.length,'material','exact declared material set');
      for(const material of asset.materials) {
        const matches=parsed.gltf.materials.filter(m=>m.name===material.id&&m.extras?.semantic_id===material.id);
        requireProof(matches.length===1,'material','unique semantic material '+material.id);
        const pbr=matches[0].pbrMetallicRoughness;
        requireProof((pbr.baseColorFactor??[1,1,1,1]).every((v,i)=>Math.abs(v-material.base_color[i])<1e-5),'material','base color factor');
        requireProof(Math.abs((pbr.metallicFactor??1)-material.metallic)<1e-5&&Math.abs((pbr.roughnessFactor??1)-material.roughness)<1e-5,'material','PBR factors');
        for(const slot of material.textures) {
          requireProof(slot.slot==='baseColor'&&pbr.baseColorTexture,'texture','declared baseColor slot');
          const image=parsed.gltf.textures[pbr.baseColorTexture.index].source;
          requireProof(parsed.textures[image].sha256===textureHashes.get(slot.texture_id),'texture','embedded bytes match authored texture');
        }
      }
      requireProof(parsed.semantic===lod.semantic_geometry_sha256,'semantic',lod.artifact.path);
      lods.push({level:lod.level,artifact:lod.artifact.path,semantic_geometry_sha256:parsed.semantic,...proof});
    }
    requireProof(lods.length===3&&lods[0].triangles>lods[1].triangles&&lods[1].triangles>lods[2].triangles,'lod','three decreasing actual geometries');
    results.push({id:asset.id,kind:asset.kind,variant:asset.variant,lods});
  }
  return {status:'PASS',toolchain:{version:tool.version,architecture:tool.architecture,executable_sha256:tool.executable_sha256},external_asset_count:0,assets:results,limits:['T6 operational runtime and T13 loader integration are pending','Representative pipeline proof only; no family-wide visual approval']};
}
if(process.argv[1]&&resolve(process.argv[1])===fileURLToPath(import.meta.url)) {
  try {
    requireProof(process.argv.length===4&&process.argv[2]==='--root','usage','node scripts/assets/verify.mjs --root OUTPUT_ROOT');
    console.log(JSON.stringify(await verify(resolve(process.argv[3])),null,2));
  } catch(error) {console.error(error instanceof Error?error.message:String(error));process.exitCode=1;}
}
