/** Read actual T10 receipts through the unchanged canonical motion boundary. */
import {build} from 'esbuild';
import {readFileSync,writeFileSync,mkdirSync,existsSync} from 'node:fs';
import {resolve} from 'node:path';
import {hash} from './oracle.mjs';
const args=process.argv.slice(2),value=k=>args[args.indexOf(k)+1],root=resolve(value('--root')),out=resolve(value('--out')),sql=resolve(value('--sql'));
const raw=readFileSync(resolve(root,'public/assets/steelworks/finishing/manifest.json'));if(hash(raw)!==value('--expected-sha'))throw new Error('Exact manifest root required');mkdirSync(out);
await build({stdin:{contents:"export {parseProductionAssetManifest} from './src/operations/scene/assets/manifest.ts';export {phaseRequest,sampleRequest} from './tests/fixtures/finishing/poses.ts';",resolveDir:resolve('.')},outfile:resolve(out,'api.mjs'),bundle:true,packages:'external',platform:'node',format:'esm',loader:{'.json':'json','.ts':'ts'}});
const api=await import(resolve(out,'api.mjs')),manifest=api.parseProductionAssetManifest(raw.toString()),results=[];
for(const asset of manifest.assets){const owner=asset.placement_ids[0].replace('equipment:','');for(const operation of ['weld','cut']){const folder=resolve(sql,owner+'-'+operation);if(!existsSync(resolve(folder,'receipt.json')))continue;const snapshot=JSON.parse(readFileSync(resolve(folder,'after.json'))),world=JSON.parse(readFileSync(resolve(folder,'world.json'))),binding=JSON.parse(readFileSync(resolve(folder,'binding.json')));
for(const material of snapshot.materials.filter(m=>m.active)){const attachment=snapshot.attachments.find(a=>a.material_id===material.id&&a.released_at_ms===null),port=world.ports.find(p=>p.id===attachment.owner_id),socket=binding.sockets.find(s=>s.socket_id===attachment.socket_id),base=api.phaseRequest(manifest,asset,{name:'idle',progress:0,clock:'paused'},hash(raw)),e=base.envelope;
Object.assign(e,{run_id:snapshot.run.id,bundle_id:snapshot.run.bundle_id,bundle_hash:snapshot.run.bundle_hash,revision:snapshot.run.revision,confirmed_sim_ms:10000,effective_sim_ms:10000,execution_id:snapshot.processes[0].id,phase_start_ms:0,phase_end_ms:10000,frozen_progress:1,clock_state:'paused',attachment_id:attachment.id,boundary:null});
e.material={material_id:material.id,material_version_id:material.current_version_id,form:material.form,dimensions:material.dimensions,support_local_mm:[0,-material.dimensions.thickness_mm/2,0],orientation_xyzw:[0,0,0,1]};
e.anchor={owner_id:owner,socket_id:socket.socket_id,position_m:socket.position_m,orientation_xyzw:socket.orientation_xyzw};for(const c of e.channels)c.start_value=c.end_value=0;
if(!port||port.owner_id!==owner)throw new Error('Actual admitted child destination port absent');const request={...base,envelope:e,context:{...base.context,snapshot,world,asset_bindings:[binding],authorizations:[structuredClone(e)]}};
try{const sample=api.sampleRequest(request);results.push({owner,operation,material_id:material.id,status:'PASS',request,pose:sample.pose});}catch(error){results.push({owner,operation,material_id:material.id,status:'REJECTED',error:String(error),request});}
writeFileSync(resolve(out,'results.json'),JSON.stringify({manifest_sha256:hash(raw),scope:'Actual completed T10 output snapshots at rest; later winding not yet asserted',results},null,2)+'\n');
}}}
console.log(JSON.stringify({outputs:results.length,rejected:results.filter(r=>r.status!=='PASS').map(r=>({owner:r.owner,operation:r.operation,error:r.error}))}));process.exitCode=results.some(r=>r.status!=='PASS')?1:0;
