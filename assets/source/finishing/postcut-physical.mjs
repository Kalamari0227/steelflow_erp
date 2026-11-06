/** New canonical winding phase over actual SQL children; final history is synthetic. */
import {readFileSync,writeFileSync} from 'node:fs';
import {resolve,dirname} from 'node:path';
import {Matrix4,Quaternion,Vector3} from 'three';
import {hash,readGlb,requireProof} from './oracle.mjs';
import {decodedScene,geometryTriangles,contact,sheetClearance} from './mesh-check.mjs';
import {woundStrip,sheet} from '../../../tests/fixtures/finishing/forming.ts';
const args=process.argv.slice(2),v=k=>args[args.indexOf(k)+1],root=resolve(v('--root')),indexPath=resolve(v('--inputs')),indexRaw=readFileSync(indexPath),raw=readFileSync(resolve(root,'public/assets/steelworks/finishing/manifest.json'));
requireProof(hash(raw)===v('--expected-sha')&&hash(indexRaw)===v('--inputs-sha'),'preflight','exact root/corpus SHA');
const manifest=JSON.parse(raw),index=JSON.parse(indexRaw),api=await import(resolve(v('--api'))),results=[],boundaries=[],count=Number(v('--samples'));
requireProof(manifest.assets.length===58&&manifest.assets.every(a=>a.family==='finishing'&&a.lods.length===3)&&index.cases.length===11&&Number.isSafeInteger(count)&&count>=64,'preflight','58/174/11 and dense finite sampling');
for(const asset of manifest.assets)for(const lod of asset.lods)requireProof(hash(readFileSync(resolve(root,lod.artifact.path)))===lod.artifact.sha256,'preflight','174 actual byte hashes');
const matrix=p=>new Matrix4().compose(new Vector3(...p.position_m),new Quaternion(...p.orientation_xyzw),new Vector3(1,1,1));
const positions=(g,m)=>Array.from({length:g.getAttribute('position').count},(_,i)=>new Vector3().fromBufferAttribute(g.getAttribute('position'),i).applyMatrix4(m));
const maxGap=(a,b)=>a.length===b.length?Math.max(...a.map((p,i)=>p.distanceTo(b[i]))):Infinity;
for(const row of index.cases){
 const bytes=readFileSync(resolve(dirname(indexPath),row.file));requireProof(hash(bytes)===row.sha256,'preflight','exact owner corpus');
 const data=JSON.parse(bytes),asset=manifest.assets.find(a=>a.placement_ids[0]==='equipment:'+row.owner),fn=data.winding_function,part=asset.moving_parts.find(p=>p.function===fn&&p.binding.type==='clip'),base=data.frames.find(f=>f.name==='start'),end=data.frames.find(f=>f.name==='end-before'),after=data.frames.find(f=>f.name==='end-after');
 const ownerM=new Matrix4().compose(new Vector3(...data.ownerPose.position),new Quaternion().setFromAxisAngle(new Vector3(0,1,0),data.ownerPose.yaw_rad),new Vector3(1,1,1)),inverse=ownerM.clone().invert(),context=api.parseMotionContext(base.request.context),t=data.thickness_m;
 const original={envelope:data.original_post_context.authorizations[0],context:data.original_post_context};
 const actualChild=data.original_post_context.snapshot.materials.find(m=>m.id===base.pose.material.material_id),originalEnvelope={...base.request.envelope,...data.original_post_context.authorizations[0],material:base.request.envelope.material,anchor:base.request.envelope.anchor,attachment_id:base.request.envelope.attachment_id};
 const actualPose=api.evaluateMotion(api.parseMotionEnvelopeValue(originalEnvelope),api.parseMotionContext({...original.context,authorizations:[originalEnvelope]}),api.recipes);
 const startShape=woundStrip(0,1.2,t,part.range.max),endShape=woundStrip(part.range.max,1.2,t,part.range.max),startWorld=positions(startShape.geometry,matrix(base.pose)),originalWorld=positions(startShape.geometry,matrix(actualPose)),endWorld=positions(endShape.geometry,matrix(end.pose)),afterWorld=positions(endShape.geometry,matrix(after.pose)),startGap=maxGap(startWorld,originalWorld),finalGap=maxGap(endWorld,afterWorld);
 requireProof(actualChild?.weight_kg===400&&actualChild.current_version_id===base.pose.material.material_version_id&&startGap<=1e-6&&finalGap<=1e-6,'retained','same actual child vertices at newphase start and final form boundary');
 requireProof(end.pose.material.material_id===after.pose.material.material_id&&end.pose.material.material_version_id!==after.pose.material.material_version_id,'retained','same material new version');
 const leftPose=api.evaluateMotion(api.parseMotionEnvelopeValue(data.left_child_envelope),api.parseMotionContext({...data.original_post_context,authorizations:[data.left_child_envelope]}),api.recipes),localStart=positions(startShape.geometry,inverse.clone().multiply(matrix(base.pose))),grip=localStart.slice(0,4).reduce((s,p)=>s.add(p),new Vector3()).multiplyScalar(.25),last=localStart.slice(-4).reduce((s,p)=>s.add(p),new Vector3()).multiplyScalar(.25),direction=last.clone().sub(grip).normalize(),normal=new Vector3(0,1,0).transformDirection(inverse.clone().multiply(matrix(base.pose))),left=sheet([{center:last,normal,thickness:t},{center:last.clone().addScaledVector(direction,4),normal,thickness:t}],1.2,4*1.2*t);
 boundaries.push({owner:row.owner,startGap,finalGap,vertexCount:endWorld.length,materialId:actualChild.id,inputVersion:actualChild.current_version_id,outputVersion:after.pose.material.material_version_id,weightKg:400,leftPose,qualification:data.qualification});
 const poses=[];
 for(let i=0;i<=count;i++){
  const p=i/count,time=10000+Math.round(10000*p),envelope=api.parseMotionEnvelopeValue({...base.request.envelope,confirmed_sim_ms:time,effective_sim_ms:time,frozen_progress:p,clock_state:'running'}),current={...context,snapshot:{...context.snapshot,run:{...context.snapshot.run,elapsed_ms:time,playing:true}},authorizations:[envelope]};
  poses.push(api.evaluateMotion(envelope,current,api.recipes));
 }
 for(const lod of asset.lods){const glb=readGlb(readFileSync(resolve(root,lod.artifact.path)));
  for(let i=0;i<=count;i++){
   const pose=poses[i],theta=pose.channels.find(c=>c.function_id===fn).value,scene=decodedScene(asset,glb,Object.fromEntries(pose.channels.map(c=>[c.function_id,c.value]))),g=woundStrip(theta,1.2,t,part.range.max),transform=inverse.clone().multiply(matrix(pose)),point=new Vector3(...pose.contact_m).applyMatrix4(inverse),socket=scene.socket(pose.socket_id),machine=contact(scene.trianglesOf(part.node_id+'_clamp_jaw'),point,socket.normal),body=contact(geometryTriangles(g.geometry,transform),point,socket.normal.clone().negate()),clearance=sheetClearance(scene,g.geometry,transform),leftClearance=sheetClearance(scene,left.geometry,new Matrix4()),pass=machine.aligned?.distance<=.01&&body.aligned?.distance<=.01&&Math.abs(body.nearestAny.distance-body.aligned.distance)<=1e-6&&Math.abs(g.centerlineM-4)<=1e-6&&Math.abs(g.volumeM3-g.targetVolumeM3)<=3e-7&&clearance.hits.length===0&&leftClearance.hits.length===0;
   results.push({owner:row.owner,lod:lod.level,phaseProgress:i/count,theta,pass,machine,body,clearance,leftClearance,centerlineM:g.centerlineM,volumeM3:g.volumeM3,targetVolumeM3:g.targetVolumeM3});g.geometry.dispose();
  }
  writeFileSync(v('--output'),JSON.stringify({manifest_sha256:hash(raw),source_corpus_sha256:hash(indexRaw),scope:'ActualSQL child; new canonical RUNNING phase + explicit synthetic retained finalCOIL history; no productionwriter claim',boundaries,results},null,2)+'\n');
 }
 startShape.geometry.dispose();endShape.geometry.dispose();left.geometry.dispose();
}
console.log(JSON.stringify({states:results.length,boundaries:boundaries.length,failed:results.filter(r=>!r.pass).map(r=>({owner:r.owner,lod:r.lod,p:r.phaseProgress,hits:r.clearance.hits.slice(0,1)}))}));process.exitCode=results.some(r=>!r.pass)?1:0;
