import './style.css';
import {ACESFilmicToneMapping,AmbientLight,Box3,Color,DirectionalLight,Group,HemisphereLight,Mesh,MeshStandardMaterial,OrthographicCamera,PCFSoftShadowMap,PlaneGeometry,Quaternion,Scene,Vector3,WebGLRenderer} from 'three';
import {parseProductionAssetManifest} from '../../../src/operations/scene/assets/manifest';
import {assetManifestShape} from '../../../src/operations/scene/assets/manifestShape';
import type {Asset} from '../../../src/operations/scene/assets/manifest';
import {loadAsset} from '../../../src/operations/scene/assets/loader';
import type {LoadedAsset} from '../../../src/operations/scene/assets/loader';
import {sha256} from '../../../src/operations/scene/worldContractBundle';
import {coilGeometry,retainedMaterial} from './material';
import {geometryFrame,phases} from './frames';
import type {Phase} from './frames';
import {materialPenetrations,surface} from './physical';

const select=(id:string):HTMLSelectElement=>{const n=document.getElementById(id);if(!(n instanceof HTMLSelectElement))throw new TypeError('Missing select '+id);return n;};
const output=document.getElementById('proof'),status=document.getElementById('status'),host=document.getElementById('viewport'),slider=document.getElementById('progress');
if(!output||!status||!host||!(slider instanceof HTMLInputElement))throw new TypeError('Fixture markup incomplete');
const progress=slider,proofOutput=output,statusOutput=status,viewport=host;
const assetSelect=select('asset'),lodSelect=select('lod'),phaseSelect=select('phase');
for(const phase of phases){const option=document.createElement('option');option.value=phase;option.textContent=phase;phaseSelect.append(option);}
const renderer=new WebGLRenderer({antialias:true,preserveDrawingBuffer:true});renderer.toneMapping=ACESFilmicToneMapping;renderer.toneMappingExposure=.9;renderer.setPixelRatio(1.25);renderer.shadowMap.enabled=true;renderer.shadowMap.type=PCFSoftShadowMap;viewport.append(renderer.domElement);
const scene=new Scene();scene.background=new Color('#e8e0cf');const content=new Group();scene.add(content);
scene.add(new AmbientLight('#fff4df',.4),new HemisphereLight('#fff1d8','#c9b591',1.3));
for(const [x,y,z,intensity]of [[10,22,14,2.4],[-14,12,-8,1.1]]){const l=new DirectionalLight('#fff3df',intensity);l.position.set(x??0,y??0,z??0);l.castShadow=true;l.shadow.mapSize.set(2048,2048);l.shadow.camera.left=-20;l.shadow.camera.right=20;l.shadow.camera.top=20;l.shadow.camera.bottom=-20;l.shadow.bias=-.0002;scene.add(l);}
const ground=new Mesh(new PlaneGeometry(800,800),new MeshStandardMaterial({color:'#e1d5b9',roughness:.95}));ground.rotation.x=-Math.PI/2;ground.position.y=-.025;ground.receiveShadow=true;scene.add(ground);
const camera=new OrthographicCamera(-14,14,10,-10,.1,2000);let angle='front',manifestHash='',selected:Asset|undefined,loaded:LoadedAsset[]=[],assets:readonly Asset[]=[],generation=0,paused=false,playing=false,timer=0;
const cargo=new Mesh(coilGeometry(retainedMaterial.material.dimensions),new MeshStandardMaterial({color:'#8e9b9b',metalness:.8,roughness:.35}));cargo.name='material:t16:material:1';cargo.castShadow=true;cargo.receiveShadow=true;content.add(cargo);
function frame():ReturnType<typeof geometryFrame>{const phase=phases.find(p=>p===phaseSelect.value);if(!phase)throw new RangeError('Unknown phase');return geometryFrame(phase,Number(progress.value));}
function fit():void{
  renderer.setSize(viewport.clientWidth,viewport.clientHeight);const target=new Vector3(0,3,3),size=new Vector3(22,12,18);
  if(selected){const box=new Box3().setFromObject(content);box.getCenter(target);box.getSize(size);}
  const offsets=angle==='side'?[0,14,30]:angle==='rear'?[-24,16,-24]:angle==='close'?[7,8,10]:[24,18,25];camera.position.copy(target).add(new Vector3(...offsets));camera.lookAt(target);
  const width=angle==='close'?7:Math.max(20,size.x*1.1,size.z*1.3),height=width*viewport.clientHeight/viewport.clientWidth;camera.left=-width/2;camera.right=width/2;camera.top=height/2;camera.bottom=-height/2;camera.updateProjectionMatrix();renderer.render(scene,camera);
}
function pose():void{
  const f=frame();for(const object of loaded){for(const part of object.asset.moving_parts){const n=object.nodes.get(part.node_id),rest=object.asset.nodes.find(r=>r.id===part.node_id);if(!n||!rest)throw new RangeError('Source part absent');let value=part.range.rest;if(object.asset.kind==='crane'){if(part.function==='bridge_travel')value=f.bridge;if(part.function==='trolley_travel')value=f.trolley;if(part.function==='hoist')value=f.hoist;}else if(selected)value=part.range.min+(part.range.max-part.range.min)*f.progress;n.position.fromArray(rest.transform.position_m);n.quaternion.fromArray(rest.transform.rotation_xyzw);if(part.motion==='translation')n.position.addScaledVector(new Vector3(...part.axis),value-part.range.rest);else n.quaternion.premultiply(new Quaternion().setFromAxisAngle(new Vector3(...part.axis),value-part.range.rest));}}
  cargo.position.fromArray(f.material);cargo.visible=!selected;content.updateMatrixWorld(true);renderer.render(scene,camera);
  const materialFrame={root:cargo.position.toArray(),quaternion:cargo.quaternion.toArray(),materialId:'t16:material:1',versionId:'t16:version:1',dimensions:retainedMaterial.material.dimensions,support_local_mm:[0,-600,0],mass_kg:20000,volumeM3:Math.PI*(.6**2-.3**2)};
  const record={authority:f.authority,manifestHash,lod:Number(lodSelect.value),phase:f.phase,progress:f.progress,paused,frame:f,angle,material:materialFrame,actualProductLoader:true,assets:loaded.map(l=>({id:l.asset.id,nodes:l.nodes.size,parts:l.asset.moving_parts.map(p=>({id:p.id,matrix:l.nodes.get(p.node_id)?.matrixWorld.toArray()}))})),renderer:{calls:renderer.info.render.calls,triangles:renderer.info.render.triangles}};
  renderer.domElement.dataset.state=JSON.stringify(record);renderer.domElement.dataset.ready='true';proofOutput.textContent=JSON.stringify(record,null,2);
}
async function reload():Promise<void>{
  const current=++generation;renderer.domElement.dataset.ready='false';statusOutput.textContent='실제 원본을 읽는 중';for(const l of loaded){content.remove(l.scene);l.dispose();}loaded=[];
  selected=assets.find(a=>a.id===assetSelect.value);const chosen=selected?[selected]:assets.filter(a=>['truck-flatbed','crane-yard','receiving-cradle'].some(k=>a.id==='steelflow:transport:'+k));
  for(const asset of chosen){const lod=asset.lods.find(l=>l.level===Number(lodSelect.value));if(!lod)throw new RangeError('Source LOD absent');const actual=await loadAsset(asset,lod,{origin:location.origin});if(current!==generation){actual.dispose();return;}if(asset.kind==='receiving-cradle'&&!selected)actual.scene.position.z=6;actual.scene.traverse(n=>{if(n instanceof Mesh){n.castShadow=true;n.receiveShadow=true;}});content.add(actual.scene);loaded.push(actual);}
  statusOutput.textContent='실제 원본 표시 · 업무 연결 검증 전';pose();fit();
}
function fail(error:unknown):void{const message=error instanceof Error?error.message:String(error);renderer.domElement.dataset.ready='error';renderer.domElement.dataset.error=message;statusOutput.textContent=message;console.error(error);}
for(const control of [assetSelect,lodSelect])control.addEventListener('change',()=>{void reload().catch(fail);});
phaseSelect.addEventListener('change',()=>{progress.value='0';pose();});progress.addEventListener('input',pose);
for(const button of document.querySelectorAll<HTMLButtonElement>('[data-angle]'))button.addEventListener('click',()=>{angle=button.dataset.angle??'front';fit();pose();});
document.getElementById('pause')?.addEventListener('click',()=>{paused=!paused;pose();});
document.getElementById('play')?.addEventListener('click',()=>{playing=true;paused=false;phaseSelect.value='grip';progress.value='0';timer=performance.now();requestAnimationFrame(tick);});
function tick(now:number):void{if(!playing)return;const elapsed=paused?0:(now-timer)/1200;timer=now;let value=Number(progress.value)+elapsed;if(value>=1){const index=phases.indexOf(frame().phase);const next=phases[index+1];if(!next||next==='empty-return'){playing=false;value=1;}else{phaseSelect.value=next;value=0;}}progress.value=String(value);pose();if(playing)requestAnimationFrame(tick);}
window.addEventListener('resize',()=>{fit();pose();});
Object.defineProperty(window,'transportProof',{value:{sample:(phase:Phase,p:number):unknown=>{phaseSelect.value=phase;progress.value=String(p);pose();return JSON.parse(renderer.domElement.dataset.state??'null');},negatives:async()=>{const raw=await(await fetch('/assets/steelworks/transport/manifest.json')).text(),result=[];for(const mode of ['hash','pivot']){const copy=structuredClone(assetManifestShape.parse(JSON.parse(raw))),truck=copy.assets.find(a=>a.kind==='truck');if(!truck||!truck.lods[0])throw new RangeError('Truck source absent');if(mode==='hash')Reflect.set(truck.lods[0].artifact,'sha256','0'.repeat(64));else{const part=truck.moving_parts.find(p=>p.id==='wheel_rotation');if(!part)throw new RangeError('Wheel absent');Reflect.set(part.pivot_m,'0',part.pivot_m[0]+.05);}try{const admitted=parseProductionAssetManifest(JSON.stringify(copy)),asset=admitted.assets.find(a=>a.kind==='truck');if(!asset||!asset.lods[0])throw new RangeError('Truck absent');const decoded=await loadAsset(asset,asset.lods[0],{origin:location.origin});decoded.dispose();result.push({mode,rejected:false,error:null});}catch(error){result.push({mode,rejected:true,error:error instanceof Error?error.message:String(error)});}}return result;},physical:()=>{const f=frame();return{penetrations:materialPenetrations(loaded.map(l=>l.scene),f.material),hook:surface(loaded.find(l=>l.asset.kind==='crane')?.scene??content,[f.material[0],f.material[1]+.3,f.material[2]],[0,1,0]),materialBottom:surface(content,[f.material[0],f.material[1]-.6,f.material[2]],[0,1,0])};}}});
async function start():Promise<void>{const raw=await(await fetch('/assets/steelworks/transport/manifest.json')).text();parseProductionAssetManifest(raw);manifestHash=await sha256(new TextEncoder().encode(raw));const candidate=await(await fetch('/assets/steelworks/transport/manifest-candidate.json')).text();assets=assetManifestShape.parse(JSON.parse(candidate)).assets;for(const a of assets){const option=document.createElement('option');option.value=a.id;option.textContent=a.id.split(':').at(-1)??a.id;assetSelect.append(option);}await reload();}
void start().catch(fail);
