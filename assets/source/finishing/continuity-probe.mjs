/** Actual finite auxiliary winding and lifted roller mesh proof. */
import {readFileSync,writeFileSync} from 'node:fs';
import {resolve} from 'node:path';
import {Matrix4,Vector3} from 'three';
import {readGlb,hash,requireProof} from './oracle.mjs';
import {decodedScene,geometryTriangles,contact,sheetClearance} from './mesh-check.mjs';
import {woundStrip} from '../../../tests/fixtures/finishing/forming.ts';
const args=process.argv.slice(2),value=k=>args[args.indexOf(k)+1],root=resolve(value('--root')),path=resolve(root,'public/assets/steelworks/finishing/manifest.json'),expected=value('--expected-sha'),owners=['CS-CR-05','CS-GO-05','CS-GO-08','CS-NGO-05'];
requireProof(hash(readFileSync(path))===expected,'preflight','independent raw manifest SHA');
const manifest=JSON.parse(readFileSync(path)),recipe=JSON.parse(readFileSync(resolve(root,'assets/source/finishing/recipe.json'))),results=[];
requireProof(JSON.stringify(manifest.assets.map(a=>a.placement_ids[0].replace('equipment:','')).sort())===JSON.stringify(owners),'preflight','four exact independent owners');
let failed=false;
for(const asset of manifest.assets){const cfg=recipe.models.find(s=>s.variant===asset.variant).source_internal_sequence,t=cfg.thickness_m??(asset.placement_ids[0].includes('CR-05')||asset.placement_ids[0].includes('GO-08')?.002:.004),part=asset.moving_parts.find(p=>p.function==='line_unwinding_mandrel');
  for(const lod of asset.lods){const bytes=readFileSync(resolve(root,lod.artifact.path));requireProof(hash(bytes)===lod.artifact.sha256,'preflight','actual sealed LOD');const parsed=readGlb(bytes);
    for(const u of [0,.25,.5,.75,1]){const scalar=part.range.max*u,scene=decodedScene(asset,parsed,{line_unwinding_mandrel:scalar,line_feed_lift:-.02}),socket=scene.socket('line_coil_support'),matrix=scene.matrix(scene.indexed.get(part.node_id)).clone().multiply(new Matrix4().makeTranslation(0,.44+t/2,0)),proof=woundStrip(scalar,1.2,t,part.range.max),material=geometryTriangles(proof.geometry,matrix),machine=contact(scene.trianglesOf('line_unwinding_mandrel_clamp_jaw'),socket.point,socket.normal),body=contact(material,socket.point,socket.normal.clone().negate()),clearance=sheetClearance(scene,proof.geometry,matrix),pass=machine.aligned?.distance<=.01&&body.aligned?.distance<=.01&&Math.abs(body.aligned.distance-body.nearestAny.distance)<=1e-6&&clearance.hits.length===0;
      results.push({asset:asset.id,lod:lod.level,phase:'unwind-lowered',u,scalar,pass,machine,body,clearance,centerlineM:proof.centerlineM,volumeM3:proof.volumeM3});if(!pass)failed=true;proof.geometry.dispose();
    }
    const scene=decodedScene(asset,parsed,{line_feed_lift:0,line_unwinding_mandrel:0}),profile=asset.internal_feeds[0];for(const progress of [0,.25,.5,.75,1]){const max=asset.moving_parts.find(p=>p.function===cfg.driver).range.max,active=decodedScene(asset,parsed,{line_feed_lift:0,[cfg.driver]:max*progress}),g=woundStrip(0,1.2,t,part.range.max).geometry,k=(t+.0002)/(2*Math.PI),alpha=Math.PI+Math.atan(k/(.44+t/2)),matrix=scene.matrix(scene.indexed.get(part.node_id)).clone().multiply(new Matrix4().makeTranslation(0,.44+t/2,0));matrix.premultiply(new Matrix4().makeTranslation(cfg.stroke_m*progress,0,0));const clearance=sheetClearance(active,g,matrix);results.push({asset:asset.id,lod:lod.level,phase:'raised-feed',progress,pass:clearance.hits.length===0,clearance,alpha,rollers:profile.rollers.length});if(clearance.hits.length)failed=true;g.dispose();}
  }
}
writeFileSync(value('--output'),JSON.stringify({status:failed?'FAIL':'PASS_ACTUAL_4OWNER_3LOD_GEOMETRY_NOT_TYPED_CONTINUITY',manifestSha256:expected,results},null,2)+'\n');
console.log(JSON.stringify({status:failed?'FAIL':'PASS',states:results.length,failed:results.filter(r=>!r.pass).map(r=>({asset:r.asset,lod:r.lod,phase:r.phase,u:r.u,progress:r.progress,firstHit:r.clearance.hits[0],machine:r.machine?.aligned,body:r.body?.aligned}))},null,2));process.exitCode=failed?1:0;
