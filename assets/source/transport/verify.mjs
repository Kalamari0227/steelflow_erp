/** Inspect exact authored bytes through the production parser and established GLB oracle. */
import { readFileSync, writeFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { Matrix4, Quaternion, Vector3 } from 'three';
import { productionParser } from '../../../scripts/assets/production-parser.mjs';
import { readGlb, requireProof, hash } from '../../../scripts/assets/glb.mjs';
import { localArtifact } from '../../../scripts/assets/verify.mjs';
import { productionLoader } from './production-loader.mjs';

export function checkSolidCoverage(asset, lod, parsed, inventory) {
  requireProof(inventory.asset_id===asset.id && inventory.lod===lod.level && inventory.glb_sha256===lod.artifact.sha256,'solid-binding','exact asset/lod/glb');
  const {gltf,accessor}=parsed,parents=new Map(),byName=new Map();
  gltf.nodes.forEach((node,i)=>{requireProof(!byName.has(node.name),'solid-node','duplicate name');byName.set(node.name,i);for(const child of node.children??[])parents.set(child,i);});
  const matrices=new Map();
  function matrix(i){if(matrices.has(i))return matrices.get(i);const n=gltf.nodes[i];const m=new Matrix4().compose(new Vector3(...(n.translation??[0,0,0])),new Quaternion(...(n.rotation??[0,0,0,1])),new Vector3(...(n.scale??[1,1,1])));const result=parents.has(i)?matrix(parents.get(i)).clone().multiply(m):m;matrices.set(i,result);return result;}
  const actual=gltf.nodes.filter(n=>n.mesh!==undefined).map(n=>n.name).sort();
  requireProof(JSON.stringify(actual)===JSON.stringify([...inventory.all_mesh_nodes].sort()),'solid-coverage','actual mesh universe');
  const exclusions=inventory.excluded_mesh_nodes.map(n=>n.node_id);
  const union=[...inventory.source_body_mesh_nodes,...exclusions].sort();
  requireProof(new Set(union).size===union.length && JSON.stringify(union)===JSON.stringify(actual),'solid-coverage','exhaustive disjoint physical/diagnostic inventory');
  requireProof(exclusions.every(n=>['axis_origin','axis_front','axis_up','axis_side'].includes(n)),'solid-coverage','only explicit diagnostic exclusions are proposed');
  const assigned=inventory.boxes.flatMap(b=>b.mesh_node_ids);
  requireProof(new Set(assigned).size===assigned.length && JSON.stringify([...assigned].sort())===JSON.stringify([...inventory.source_body_mesh_nodes].sort()),'solid-coverage','each solid exactly one covering convex box');
  let vertices=0,triangles=0;
  for(const box of inventory.boxes){
    requireProof(box.size_m.every(v=>Number.isFinite(v)&&v>0)&&box.center_m.every(Number.isFinite)&&Number.isFinite(box.yaw_rad),'solid-box','finite positive dimensions');
    const inverse=new Matrix4().compose(new Vector3(...box.center_m),new Quaternion().setFromAxisAngle(new Vector3(0,1,0),box.yaw_rad),new Vector3(1,1,1)).invert();
    for(const name of box.mesh_node_ids){const i=byName.get(name);requireProof(i!==undefined,'solid-node',name);const node=gltf.nodes[i];for(const primitive of gltf.meshes[node.mesh].primitives){
      requireProof((primitive.mode??4)===4,'solid-triangle','TRIANGLES only');const positions=accessor(primitive.attributes.POSITION);const indices=primitive.indices===undefined?positions.map((_,k)=>[k]):accessor(primitive.indices);requireProof(indices.length%3===0,'solid-triangle','whole triangles');
      for(const index of indices){const p=positions[index[0]];requireProof(p?.length===3,'solid-triangle','valid index');const world=new Vector3(...p).applyMatrix4(matrix(i)).applyMatrix4(inverse);requireProof(world.toArray().every((v,k)=>Math.abs(v)<=box.size_m[k]/2+1e-6),'solid-undercoverage',name);vertices++;}triangles+=indices.length/3;
    }}
  }
  return {assetId:asset.id,lod:lod.level,solidMeshes:inventory.source_body_mesh_nodes.length,excludedDiagnosticMeshes:exclusions.length,triangleCorners:vertices,triangles,classificationApproval:'PENDING_INDEPENDENT_REVIEW'};
}

export async function verifyTransport(root,{stamp=false}={}) {
  const dir=resolve(root,'public/assets/steelworks/transport'),path=resolve(dir,'manifest.json');
  const raw=JSON.parse(readFileSync(path,'utf8')),candidatePath=resolve(dir,'manifest-candidate.json'),candidate=JSON.parse(readFileSync(candidatePath,'utf8'));
  if(stamp){for(const manifest of [raw,candidate])for(const asset of manifest.assets)for(const lod of asset.lods){requireProof(lod.semantic_geometry_sha256===null,'stamp','refuse restamp');lod.semantic_geometry_sha256=readGlb(localArtifact(root,lod.artifact)).semantic;}writeFileSync(path,JSON.stringify(raw,null,2)+'\n');writeFileSync(candidatePath,JSON.stringify(candidate,null,2)+'\n');}
  const manifest=(await productionParser())(readFileSync(path,'utf8'));
  const recipe=JSON.parse(readFileSync(resolve(root,'assets/source/transport/recipe.json'),'utf8'));
  const inventory=JSON.parse(readFileSync(resolve(root,'assets/source/transport/solid-inventory.json'),'utf8'));
  const sources=JSON.parse(readFileSync(resolve(root,'assets/source/transport/inventory.json'),'utf8'));
  for(const a of [sources.license,...sources.inputs,...sources.authored_assets])localArtifact(root,a);
  const reports=[];const {loadAsset}=await productionLoader();
  for(const asset of candidate.assets){
    const admitted=manifest.assets.some(a=>a.id===asset.id);const lods=[];
    for(const lod of asset.lods){const parsed=readGlb(localArtifact(root,lod.artifact));requireProof(parsed.semantic===lod.semantic_geometry_sha256,'semantic','exact GLB');const loaded=await loadAsset(asset,lod,{origin:'http://127.0.0.1:43128',read:async()=>{const bytes=localArtifact(root,lod.artifact);return bytes.buffer.slice(bytes.byteOffset,bytes.byteOffset+bytes.byteLength);}});const proof={nodes:loaded.nodes.size,triangles:parsed.triangles,animations:loaded.animations.map(c=>({name:c.name,duration:c.duration})),actualProductLoader:true};loaded.dispose();const solid=inventory.assets.find(i=>i.asset_id===asset.id&&i.lod===lod.level);requireProof(solid,'solid-binding',asset.id);lods.push({...proof,...checkSolidCoverage(asset,lod,parsed,solid)});}
    requireProof(lods.length===3&&lods[0].triangles>lods[1].triangles&&lods[1].triangles>lods[2].triangles,'lod',asset.id);
    reports.push({assetId:asset.id,productionParserAdmitted:admitted,lods});
  }
  return {status:'ACTUAL_GEOMETRY_CHECKED_INDEPENDENT_PHYSICAL_ADMISSION_PENDING',manifestSha256:hash(readFileSync(path)),sourceInventorySha256:hash(readFileSync(resolve(root,'assets/source/transport/solid-inventory.json'))),assets:reports,limits:['Producer source solid classifications require independent approval.','Pending nested wheel composition and C-hook custody datum contract are not a physical runtime PASS.','No derived world or T16 integration admitted; priority subset is not full T28.']};
}
if(process.argv[1]&&resolve(process.argv[1])===fileURLToPath(import.meta.url)){
  try {const args=process.argv.slice(2);const root=args[args.indexOf('--root')+1];requireProof(root&&args.includes('--root'),'usage','verify --root ROOT [--stamp]');console.log(JSON.stringify(await verifyTransport(resolve(root),{stamp:args.includes('--stamp')}),null,2));}
  catch(error){console.error(error instanceof Error?error.message:String(error));process.exitCode=1;}
}
