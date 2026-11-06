/** Decoded lower-roll supports and the complete conserved 4m-to-8m sheet. */
import {readFileSync,writeFileSync} from 'node:fs';
import {resolve} from 'node:path';
import {Matrix4} from 'three';
import {hash,readGlb,requireProof} from './oracle.mjs';
import {decodedScene,geometryTriangles,contact,sheetClearance} from './mesh-check.mjs';
import {coldReduction,coldLaw} from '../../../tests/fixtures/finishing/forming.ts';
const args=process.argv.slice(2),v=k=>args[args.indexOf(k)+1],root=resolve(v('--root')),path=resolve(root,'public/assets/steelworks/finishing/manifest.json'),expected=v('--expected-sha');
requireProof(hash(readFileSync(path))===expected,'preflight','exact candidate SHA');
const manifest=JSON.parse(readFileSync(path)),recipe=JSON.parse(readFileSync(resolve(root,'assets/source/finishing/recipe.json'))),results=[],owners=v('--owners').split(',').sort();
requireProof(JSON.stringify(manifest.assets.map(a=>a.placement_ids[0].replace('equipment:','')).sort())===JSON.stringify(owners),'preflight','exact owner set');
requireProof(manifest.assets.length===58&&manifest.assets.every(a=>a.family==='finishing'&&a.lods.length===3&&a.lods.every((l,i)=>l.level===i)),'preflight','Exact58 finishing owners and174LODs');
const samples=args.includes('--samples')?Number(v('--samples')):0;requireProof(Number.isInteger(samples)&&samples>=0&&samples<=4096,'preflight','Bounded explicit scalar sample count');
let failed=false;
for(const asset of manifest.assets.filter(a=>a.kind==='cold_mill')){const spec=recipe.models.find(s=>s.variant===asset.variant),nip=spec.cold_reduction.nip_x_m,angles=[...new Set([0,coldLaw.biteAreaM/.36,coldLaw.maximumRad*.25,coldLaw.maximumRad*.5,coldLaw.maximumRad*.75,coldLaw.entryHandoffRad,(coldLaw.entryHandoffRad+coldLaw.nipHandoffRad)/2,coldLaw.nipHandoffRad,coldLaw.maximumRad,...(samples?Array.from({length:samples+1},(_,i)=>i===samples?coldLaw.maximumRad:coldLaw.maximumRad*i/samples):[])])].sort((a,b)=>a-b);
  for(const lod of asset.lods){const bytes=readFileSync(resolve(root,lod.artifact.path));requireProof(hash(bytes)===lod.artifact.sha256,'preflight','exact LOD bytes');const parsed=readGlb(bytes);
    for(const scalar of angles){for(const socketId of scalar===coldLaw.entryHandoffRad?['cold_entry_support','cold_bite_roll_support']:scalar===coldLaw.nipHandoffRad?['cold_bite_roll_support','cold_nip_support']:[scalar<coldLaw.entryHandoffRad?'cold_entry_support':scalar<coldLaw.nipHandoffRad?'cold_bite_roll_support':'cold_nip_support']){const scene=decodedScene(asset,parsed,{cold_reduction_roll:scalar,line_feed_lift:0}),socket=scene.socket(socketId),p=coldReduction(scalar),matrix=new Matrix4().makeTranslation(nip,2.001,0),body=contact(geometryTriangles(p.geometry,matrix),socket.point,socket.normal.clone().negate()),machine=contact(scene.trianglesOf('cold_reduction_roll_barrel'),socket.point,socket.normal),clearance=sheetClearance(scene,p.geometry,matrix),pass=body.aligned?.distance<=.01&&machine.aligned?.distance<=.01&&Math.abs(body.aligned.distance-body.nearestAny.distance)<=1e-6&&Math.abs(p.volumeM3-.0192)<3e-7&&clearance.hits.length===0;
      results.push({asset:asset.id,lod:lod.level,scalar,socketId,pass,body,machine,clearance,volumeM3:p.volumeM3,centerlineM:p.centerlineM,tailXM:p.tailXM,tipXM:p.tipXM});if(!pass)failed=true;p.geometry.dispose();}
    }
  }
}
writeFileSync(v('--output'),JSON.stringify({status:failed?'FAIL':'PASS_ACTUAL_COLD_GEOMETRY_NOT_TYPED_CONTINUITY',manifestSha256:expected,results},null,2)+'\n');console.log(JSON.stringify({status:failed?'FAIL':'PASS',states:results.length,failed:results.filter(r=>!r.pass).map(r=>({asset:r.asset,lod:r.lod,scalar:r.scalar,socketId:r.socketId,body:r.body.aligned,machine:r.machine.aligned,firstHit:r.clearance.hits[0]}))},null,2));process.exitCode=failed?1:0;
