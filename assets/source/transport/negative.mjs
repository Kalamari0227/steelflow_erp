/** Counterexamples use re-signed actual source metadata; parser receives the real assembly. */
import {readFileSync,writeFileSync} from 'node:fs';
import {resolve} from 'node:path';
import {productionParser} from '../../../scripts/assets/production-parser.mjs';
import {readGlb,hash,requireProof} from '../../../scripts/assets/glb.mjs';
import {checkSolidCoverage} from './verify.mjs';
import {productionLoader} from './production-loader.mjs';
const root=resolve(process.argv[2]),out=resolve(process.argv[3]),parse=await productionParser();
const raw=JSON.parse(readFileSync(resolve(root,'public/assets/steelworks/transport/manifest.json')));
const inv=JSON.parse(readFileSync(resolve(root,'assets/source/transport/solid-inventory.json')));
const truck=raw.assets.find(a=>a.kind==='truck');requireProof(truck,'fixture','real truck missing');
const results=[];const {loadAsset}=await productionLoader();
async function rejection(name,action){try{await action();throw new Error('UNEXPECTED_ACCEPT');}catch(error){if(!(error instanceof Error)||error.message==='UNEXPECTED_ACCEPT')throw error;results.push({name,error:error.message});}}
const nested=structuredClone(raw),t=nested.assets.find(a=>a.kind==='truck'),front='wheel_2_left_roll';
const driver=t.moving_parts.find(p=>p.id==='wheel_rotation'),node=t.nodes.find(n=>n.id===front);requireProof(driver&&node&&node.parent_id==='steering','fixture','actual steered rolling parent');
t.moving_parts.push({...structuredClone(driver),id:front,node_id:front,pivot_m:node.transform.position_m,binding:{type:'mechanical_follower',driver_part_id:'wheel_rotation',ratio:1}});
t.collision_proxies.push({...structuredClone(t.collision_proxies.find(p=>p.part_id==='wheel_rotation')),id:front+'_sweep',part_id:front});for(const l of t.lods)l.part_ids.push(front);
await rejection('truthful-front-wheel-nested-composition-current-capability-gap',()=>parse(JSON.stringify(nested)));
writeFileSync(resolve(out,'nested-wheel-current-red.json'),JSON.stringify({fixture:nested,result:results.at(-1),topology:{driver:'root/wheel_rotation',steering:'root/steering',front:'root/steering/'+front,axes:{driver:[0,0,1],steering:[0,1,0],front:[0,0,1]}},classification:'Expected current contract capability rejection. No parser weakening or omitted front rolling acceptance.'},null,2)+'\n');
const badPivot=structuredClone(raw),badTruck=badPivot.assets.find(a=>a.kind==='truck');badTruck.moving_parts.find(p=>p.id==='wheel_rotation').pivot_m[0]+=.05;
await rejection('bad-pivot-actual-product-loader',async()=>{const admitted=parse(JSON.stringify(badPivot)),asset=admitted.assets.find(a=>a.kind==='truck'),lod=asset.lods[0];await loadAsset(asset,lod,{origin:'http://127.0.0.1:43128',read:async()=>{const b=readFileSync(resolve(root,lod.artifact.path));return b.buffer.slice(b.byteOffset,b.byteOffset+b.byteLength);}});});
const missing=structuredClone(raw),missingTruck=missing.assets.find(a=>a.kind==='truck');missingTruck.moving_parts.splice(0,1);await rejection('missing-binding',()=>parse(JSON.stringify(missing)));
const lod=truck.lods[0],bytes=readFileSync(resolve(root,lod.artifact.path)),g=readGlb(bytes),solid=inv.assets.find(i=>i.asset_id===truck.id&&i.lod===0);
for(const[name,change]of[['omitted-solid',s=>s.source_body_mesh_nodes.splice(0,1)],['under-covering-box',s=>s.boxes[0].size_m=[.0001,.0001,.0001]],['wrong-glb-hash',s=>s.glb_sha256='0'.repeat(64)],['forged-exclusion',s=>{s.excluded_mesh_nodes.push({node_id:s.source_body_mesh_nodes.shift(),reason:'forged'});}]]){const s=structuredClone(solid);change(s);await rejection(name,()=>checkSolidCoverage(truck,lod,g,s));}
writeFileSync(resolve(out,'source-negatives.json'),JSON.stringify({sourceManifestSha256:hash(readFileSync(resolve(root,'public/assets/steelworks/transport/manifest.json'))),results},null,2)+'\n');console.log(JSON.stringify(results));
