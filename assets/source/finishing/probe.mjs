/** Early actual geometry checks against an explicit immutable family candidate. */
import {readFileSync,writeFileSync} from 'node:fs';
import {resolve} from 'node:path';
import {Matrix4,Quaternion,Vector3} from 'three';
import {readGlb,hash,requireProof} from './oracle.mjs';
import {decodedScene,geometryTriangles,contact,sheetClearance,contains} from './mesh-check.mjs';
import {woundStrip,batchCoil} from '../../../tests/fixtures/finishing/forming.ts';

const args=process.argv.slice(2),value=k=>args[args.indexOf(k)+1],root=resolve(value('--root')),manifestPath=resolve(root,'public/assets/steelworks/finishing/manifest.json'),expected=value('--expected-sha');
requireProof(args.includes('--expected-sha')&&hash(readFileSync(manifestPath))===expected,'preflight','exact candidate manifest SHA');
const manifest=JSON.parse(readFileSync(manifestPath,'utf8')),owners=value('--owners').split(',').sort(),actual=manifest.assets.map(a=>a.placement_ids[0].replace('equipment:','')).sort();
requireProof(JSON.stringify(owners)===JSON.stringify(actual)&&manifest.assets.every(a=>a.family==='finishing'&&a.lods.length===3),'preflight','exact independent candidate owner/LOD/family');
const mechanics=JSON.parse(readFileSync(resolve(root,'assets/source/finishing/mechanics.json'),'utf8')),results=[];
for(const asset of manifest.assets){
  if(args.includes('--focus')&&asset.placement_ids[0]!=='equipment:'+value('--focus'))continue;
  const mechanism=mechanics.models.find(m=>m.variant===asset.variant),forming=mechanism.forming;
  for(const lod of asset.lods){
    const bytes=readFileSync(resolve(root,lod.artifact.path));requireProof(hash(bytes)===lod.artifact.sha256,'preflight','actual LOD bytes');
    const parsed=readGlb(bytes);
    if(['winding','unwinding'].includes(forming?.mode)){
      for(const u of [0,.25,.5,.75,1]){
        const scalar=forming.maximum_rad*u,scene=decodedScene(asset,parsed,{[forming.driver]:scalar}),socket=scene.socket('work'),q=new Quaternion().setFromRotationMatrix(socket.transform),position=socket.point.clone().add(new Vector3(0,forming.thickness_m/2,0).applyQuaternion(q)),matrix=new Matrix4().compose(position,q,new Vector3(1,1,1)),proof=woundStrip(scalar,1.2,forming.thickness_m,forming.maximum_rad),material=geometryTriangles(proof.geometry,matrix),machine=contact(scene.trianglesOf(forming.driver+'_clamp_jaw'),socket.point,socket.normal),body=contact(material,socket.point,socket.normal.clone().negate()),clearance=sheetClearance(scene,proof.geometry,matrix);
        results.push({asset:asset.id,lod:lod.level,u,scalar,machine,body,centerlineM:proof.centerlineM,volumeM3:proof.volumeM3,targetVolumeM3:proof.targetVolumeM3,tailM:proof.tailM,clearance});
        requireProof(machine.aligned?.distance<=.01&&body.aligned?.distance<=.01,'contact',asset.id+' actual dual contact');
        requireProof(body.aligned&&Math.abs(body.aligned.distance-body.nearestAny.distance)<=1e-6,'outward_normal','The opposing face must be an actual nearest material surface, not the other side of a thin sheet');
        requireProof(Math.abs(proof.centerlineM-4)<=1e-6&&Math.abs(proof.volumeM3-proof.targetVolumeM3)<=3e-7,'conservation',asset.id);
        requireProof(clearance.hits.length===0,'stock_intersection',JSON.stringify(clearance.hits[0]));
        proof.geometry.dispose();
      }
    }
    if(forming?.mode==='batch-coil'){
      const scene=decodedScene(asset,parsed,{treatment_feed:0,bell_lift:0}),car=scene.meshes.filter(m=>m.id.startsWith('charge_car_')&&(m.id.endsWith('fork')||m.id.endsWith('plate'))),base=scene.trianglesOf('batch_base'),penetration=[];
      for(const mesh of car)for(const p of mesh.vertices)if(contains(base,p))penetration.push({mesh:mesh.id,point:p.toArray()});
      results.push({asset:asset.id,lod:lod.level,carBasePenetration:penetration});
      requireProof(penetration.length===0,'car_base_overlap',JSON.stringify(penetration[0]));
      const g=batchCoil(),coil=geometryTriangles(g,new Matrix4().makeTranslation(.5,2.3,0)),s=scene.socket('work'),body=contact(coil,s.point,s.normal.clone().negate()),machine=contact(scene.trianglesOf('treatment_feed'),s.point,s.normal),fixed=contact(base,s.point,s.normal);
      results.push({asset:asset.id,lod:lod.level,carContact:machine,baseContact:fixed,coilContact:body});
      requireProof(machine.aligned?.distance<=.01&&body.aligned?.distance<=.01&&fixed.aligned?.distance<=.01,'batch_handoff',JSON.stringify({machine,body,fixed}));
      g.dispose();
    }
  }
}
console.log(JSON.stringify({status:'EARLY_GEOMETRY_PROBE_PASS_NOT_PRODUCT_COMPLETION',manifestSha256:expected,results},null,2));
