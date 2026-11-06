import {useEffect,useLayoutEffect,useMemo,useState} from 'react';
import {createRoot} from 'react-dom/client';
import {Canvas,useThree} from '@react-three/fiber';
import {Box3,Group,Matrix4,Mesh,OrthographicCamera,Quaternion,Vector3} from 'three';
import type {Object3D} from 'three';
import {GLTFLoader} from 'three/addons/loaders/GLTFLoader.js';
import {z} from 'zod';
import world from '../../../shared/factory-world-v2.json';
import sourceRecipe from '../../../assets/source/finishing/recipe.json';
import {sha256} from '../../../src/operations/scene/worldContractBundle';
import {frames,batchBell,batchCar,loadContinuityCorpus} from './poses';
import type {Frame} from './poses';
import {batchCoil,woundStrip} from './forming';
import {Studio} from './lighting';
import {AdmittedScene} from './admitted';
import {LoaderProbe} from './loader';
import './style.css';

const vector=z.tuple([z.number(),z.number(),z.number()]),quaternion=z.tuple([z.number(),z.number(),z.number(),z.number()]);
const part=z.object({id:z.string(),node_id:z.string(),function:z.string(),motion:z.enum(['rotation','translation']),axis:vector,pivot_m:vector,range:z.object({min:z.number(),max:z.number(),rest:z.number()}),binding:z.discriminatedUnion('type',[z.object({type:z.literal('clip'),clip_id:z.string()}),z.object({type:z.literal('mechanical_follower'),driver_part_id:z.string(),ratio:z.number()})])});
const rawAsset=z.object({id:z.string(),kind:z.string(),variant:z.string(),placement_ids:z.array(z.string()),nodes:z.array(z.object({id:z.string(),transform:z.object({position_m:vector,rotation_xyzw:quaternion})})),moving_parts:z.array(part),sockets:z.array(z.object({id:z.string(),node_id:z.string(),transform:z.object({position_m:vector,rotation_xyzw:quaternion}),normal:vector})),lods:z.array(z.object({level:z.number(),artifact:z.object({path:z.string(),sha256:z.string()})})),cutaway:z.object({roof_node_ids:z.array(z.string())})});
type PreviewAsset=z.infer<typeof rawAsset>;
type Point=readonly [number,number,number];
type PreviewMaterial={readonly geometry:ReturnType<typeof batchCoil>;readonly position:Point;readonly quaternion:readonly [number,number,number,number];readonly proof:Readonly<Record<string,number|string>>};
const query=new URLSearchParams(location.search),authoring=query.get('authoring')==='1';

function Camera({root,angle,revision}:{readonly root:Object3D;readonly angle:string;readonly revision:number}){
  const {camera,invalidate,gl}=useThree();
  useLayoutEffect(()=>{root.updateMatrixWorld(true);const box=new Box3().setFromObject(root),target=box.getCenter(new Vector3()),size=box.getSize(new Vector3());target.y=2;const offsets=angle==='side'?[0,9,20]:angle==='rear'?[-15,11,-16]:[14,11,16];camera.position.copy(target).add(new Vector3(...offsets));camera.lookAt(target);if(camera instanceof OrthographicCamera)camera.zoom=angle==='close'?125:Math.min(75,650/Math.max(8,size.x,size.z));camera.updateProjectionMatrix();camera.updateMatrixWorld(true);gl.domElement.dataset.cameraState=JSON.stringify({angle,matrixWorld:camera.matrixWorld.toArray(),projectionMatrix:camera.projectionMatrix.toArray()});invalidate();},[root,angle,revision,camera,invalidate,gl]);return null;
}

function AuthoringScene({asset,level,frame,angle,cutaway,manifest,manifestHash}:{readonly asset:PreviewAsset;readonly level:number;readonly frame:Frame;readonly angle:string;readonly cutaway:boolean;readonly manifest:string;readonly manifestHash:string}){
  const [root,setRoot]=useState<Group>(),[error,setError]=useState(''),[material,setMaterial]=useState<PreviewMaterial>(),[state,setState]=useState<Readonly<Record<string,unknown>>>({}),{invalidate,gl}=useThree();
  useEffect(()=>{
    let active=true;const group=new Group(),ownerFound=world.owners.find(o=>asset.placement_ids.includes('equipment:'+o.id));
    if(!ownerFound)throw new Error('Canonical owner absent');const owner=ownerFound;group.position.fromArray(owner.pose.position);group.quaternion.setFromAxisAngle(new Vector3(0,1,0),owner.pose.yaw_rad);
    const lodFound=asset.lods.find(l=>l.level===level);if(!lodFound)throw new Error('Actual LOD missing');const lod=lodFound;
    setError('');setRoot(undefined);
    async function load(){
      const loaded=await new GLTFLoader().loadAsync('/'+lod.artifact.path.replace(/^public\//,''));if(!active)return;
      group.add(loaded.scene);const nodes=new Map<string,Object3D>();loaded.scene.traverse(n=>{if(typeof n.userData.semantic_id==='string')nodes.set(n.userData.semantic_id,n);if(n instanceof Mesh){n.castShadow=true;n.receiveShadow=true;}});
      const values:Record<string,number>={};
      for(const p of asset.moving_parts.filter(p=>p.binding.type==='clip')){let value=p.range.rest;if(p.function.includes('mandrel'))value=p.range.max*(asset.kind==='uncoiler'?1-frame.progress:frame.progress);if(asset.kind==='heat_treatment'&&p.function==='treatment_feed')value=batchCar(frame.progress);if(p.function==='bell_lift')value=batchBell(frame.progress);values[p.function]=value;}
      const internal=sourceRecipe.models.find(s=>s.variant===asset.variant)?.source_internal_sequence;
      if(internal){const winding=asset.moving_parts.find(p=>p.function==='line_unwinding_mandrel');if(!winding)throw new RangeError('Auxiliary winding absent');values.line_feed_lift=-.02;values.line_unwinding_mandrel=winding.range.max*(1-frame.progress);}
      for(const p of asset.moving_parts){const node=nodes.get(p.node_id),rest=asset.nodes.find(n=>n.id===p.node_id),binding=p.binding,driver=binding.type==='mechanical_follower'?asset.moving_parts.find(d=>d.id===binding.driver_part_id):p;if(!node||!rest||!driver)throw new Error('Actual authored part missing');const scalar=values[driver.function]??0,value=p.binding.type==='mechanical_follower'?p.binding.ratio*scalar:scalar;node.position.fromArray(rest.transform.position_m);node.quaternion.fromArray(rest.transform.rotation_xyzw);if(p.motion==='rotation')node.quaternion.premultiply(new Quaternion().setFromAxisAngle(new Vector3(...p.axis),value));else node.position.addScaledVector(new Vector3(...p.axis),value);}
      for(const id of asset.cutaway.roof_node_ids){const n=nodes.get(id);if(n)n.visible=!cutaway;}
      group.updateMatrixWorld(true);
      let body:PreviewMaterial|undefined;
      if(asset.kind==='uncoiler'||asset.kind==='coiler'){
        const functionId=asset.kind==='uncoiler'?'unwinding_mandrel':'winding_mandrel',part=asset.moving_parts.find(p=>p.function===functionId&&p.binding.type==='clip'),socket=asset.sockets.find(s=>s.id==='work');if(!part||!socket)throw new Error('Coil source mechanics absent');const node=nodes.get(socket.node_id);if(!node)throw new Error('Actual clamp node absent');const transform=node.matrixWorld.clone().multiply(new Matrix4().compose(new Vector3(...socket.transform.position_m),new Quaternion(...socket.transform.rotation_xyzw),new Vector3(1,1,1))),q=new Quaternion().setFromRotationMatrix(transform),point=new Vector3().applyMatrix4(transform),thickness=part.range.max>9?.002:part.range.max<8.96?.006:.004,proof=woundStrip(values[functionId]??0,1.2,thickness,part.range.max),position=point.add(new Vector3(0,thickness/2,0).applyQuaternion(q));body={geometry:proof.geometry,position:[position.x,position.y,position.z],quaternion:[q.x,q.y,q.z,q.w],proof:{centerlineM:proof.centerlineM,volumeM3:proof.volumeM3,tailM:proof.tailM,scalar:values[functionId]??0}};
      }
      if(asset.kind==='heat_treatment'){const received=frame.progress>=.25,position=new Vector3(.5+(received?0:batchCar(frame.progress)),2.3,0).applyMatrix4(group.matrixWorld),q=group.quaternion;body={geometry:batchCoil(),position:[position.x,position.y,position.z],quaternion:[q.x,q.y,q.z,q.w],proof:{outerDiameterM:1.4,innerDiameterM:.6,axis:'Y',custody:received?'batch-base':'charge-car'}};}
      if(internal){const node=nodes.get('line_unwinding_mandrel'),part=asset.moving_parts.find(p=>p.function==='line_unwinding_mandrel');if(!node||!part)throw new RangeError('Actual auxiliary source absent');const transform=node.matrixWorld.clone().multiply(new Matrix4().makeTranslation(0,.44+internal.thickness_m/2,0)),position=new Vector3().applyMatrix4(transform),q=new Quaternion().setFromRotationMatrix(transform),p=woundStrip(values.line_unwinding_mandrel??0,1.2,internal.thickness_m,part.range.max);body={geometry:p.geometry,position:[position.x,position.y,position.z],quaternion:[q.x,q.y,q.z,q.w],proof:{mode:'auxiliary-authoring-not-typed-sequence',centerlineM:p.centerlineM,volumeM3:p.volumeM3,tailM:p.tailM}};}
      setMaterial(body);setRoot(group);setState({authority:'authoring-scalar-preview-not-T58',ownerPose:owner.pose,values,material:body?.proof??null});
    }
    void load().catch((e:unknown)=>{if(active)setError(e instanceof Error?e.message:String(e));});
    return()=>{active=false;group.traverse(n=>{if(n instanceof Mesh){n.geometry.dispose();const materials=Array.isArray(n.material)?n.material:[n.material];for(const m of materials)m.dispose();}});};
  },[asset,level,frame,cutaway,manifest,manifestHash]);
  useEffect(()=>{if(!root)return;root.updateMatrixWorld(true);let triangles=0;const nodes:Readonly<Record<string,unknown>>[]=[];root.traverse(n=>{if(n instanceof Mesh)triangles+=(n.geometry.index?.count??n.geometry.getAttribute('position').count)/3;if(typeof n.userData.semantic_id==='string')nodes.push({id:n.userData.semantic_id,matrixWorld:n.matrixWorld.toArray(),visible:n.visible});});gl.domElement.dataset.assetState=JSON.stringify({assetId:asset.id,variant:asset.variant,lod:level,phase:frame.name,manifestSha256:manifestHash,triangles,nodes,...state});gl.domElement.dataset.ready='true';invalidate();},[root,state,asset,level,frame,manifestHash,gl,invalidate]);
  useEffect(()=>{gl.domElement.dataset.ready=error?'error':'false';gl.domElement.dataset.error=error;invalidate();},[error,asset,level,frame,gl,invalidate]);
  useEffect(()=>()=>material?.geometry.dispose(),[material]);
  if(!root)return null;
  return <><primitive object={root}/>{material&&<mesh name="material:synthetic-finishing-stock" position={[...material.position]} quaternion={[...material.quaternion]} castShadow><primitive object={material.geometry} attach="geometry"/><meshStandardMaterial color="#8799a0" metalness={.8} roughness={.38}/></mesh>}<Camera root={root} angle={angle} revision={frame.progress}/></>;
}

function Viewer({manifest,manifestHash}:{readonly manifest:string;readonly manifestHash:string}){
  const assets=useMemo(()=>z.object({assets:z.array(rawAsset)}).parse(JSON.parse(manifest)).assets,[manifest]),[id,setId]=useState(query.get('asset')??assets[0]?.id),asset=assets.find(a=>a.id===id),[level,setLevel]=useState(0),[index,setIndex]=useState(0),[angle,setAngle]=useState('front'),[cutaway,setCutaway]=useState(false),frame=frames[index];
  if(!asset||!frame)throw new Error('Exact selected owner/frame absent');
  return <main><header><div><div className="eyebrow">SteelFlow · finishing miniatures</div><h1>냉연 · 도금 · 전기강판 설비</h1></div><span className="badge">{authoring?'제작 중 · 계약 승인 전':'T58 고정 공정 샘플'}</span></header><p className="notice">{authoring?'실제 제작 GLB의 형상·축·범위를 확인하는 화면입니다. 이 제작용 미리보기는 공정 계약 승인이나 제품 완성을 뜻하지 않습니다.':'정해진 합성 공정 단계에서 실제 자산과 한 소재를 표시합니다. 작업·정지·재개는 같은 서버 계약의 값으로 평가하며 실제 업무 서버의 공정 실행을 뜻하지 않습니다.'}</p><div className="toolbar"><label>설비<select aria-label="실제 자산" value={id} onChange={e=>{setId(e.target.value);setIndex(0);}}>{assets.map(a=><option key={a.id} value={a.id}>{a.placement_ids[0]?.replace('equipment:','')} · {a.kind}</option>)}</select></label>{[0,1,2].map(l=><button key={l} aria-pressed={l===level} onClick={()=>setLevel(l)}>LOD {l}</button>)}<button aria-pressed={cutaway} onClick={()=>setCutaway(v=>!v)}>지붕 절개</button></div><div className="layout"><section><div className="viewport"><Canvas aria-label="실제 finishing GLB 검증" orthographic shadows frameloop="demand" dpr={1.5} camera={{position:[14,12,16],zoom:60,near:.1,far:12000}} gl={{preserveDrawingBuffer:true}}><color attach="background" args={['#e9e0cd']}/><Studio/><ambientLight intensity={.7}/><hemisphereLight args={['#fff2db','#c3ac83',1.2]}/><directionalLight position={[0,20,10]} intensity={2.4}/><directionalLight position={[-10,10,-10]} intensity={1.1}/>{authoring?<AuthoringScene asset={asset} level={level} frame={frame} angle={angle} cutaway={cutaway} manifest={manifest} manifestHash={manifestHash}/>:<AdmittedScene assetId={asset.id} level={level} frame={frame} angle={angle} cutaway={cutaway} manifest={manifest} manifestHash={manifestHash}/>}</Canvas></div><div className="toolbar">{[['front','정면'],['side','측면'],['rear','후면'],['close','근접']].map(([key,label])=><button key={key} aria-pressed={angle===key} onClick={()=>setAngle(key??'front')}>{label}</button>)}</div><div className="toolbar"><label>공정 샘플<select aria-label="공정 샘플" value={index} onChange={e=>{const next=Number(e.target.value),selected=frames[next];if(selected&&(selected.name.startsWith('main:')||selected.name.startsWith('continuity:')||selected.name.startsWith('sequence:')||selected.name.startsWith('replay:')))void loadContinuityCorpus().then(()=>setIndex(next));else setIndex(next);}}>{frames.map((f,i)=><option value={i} key={f.name}>{f.name}</option>)}</select></label><span data-testid="phase-name">{frame.name}</span></div></section><aside><h2>{asset.placement_ids[0]?.replace('equipment:','')}</h2><div className="field"><span>기구</span>{asset.kind}</div><div className="field"><span>독립 작업부</span>{asset.moving_parts.filter(p=>p.binding.type==='clip').map(p=><div key={p.id}>{p.function}</div>)}</div><div className="field"><span>소재와 시간</span>한 물리 소재 · 고정 샘플</div><div className="field"><span>실제 원본</span>Blender 4.5.15 · LOD {level}</div><div className="field"><span>검증 범위</span>{authoring?'제작용 형상 검토':'동일 세계 · canonical pose'}</div></aside></div><footer>공개 기능 개념을 바탕으로 직접 제작한 합성 미니어처입니다. 치수·축·속도는 실제 사업장의 사양이 아닙니다.</footer></main>;
}

async function start(){const container=document.getElementById('root');if(!container)throw new Error('Root absent');const root=createRoot(container);try{const response=await fetch('/assets/steelworks/finishing/manifest.json',{redirect:'error'});if(!response.ok)throw new Error('Exact finishing candidate manifest absent');const manifest=await response.text(),manifestHash=await sha256(new TextEncoder().encode(manifest));if(manifestHash!==query.get('expected-sha'))throw new Error('Pinned raw manifest SHA mismatch');root.render(query.get('loader')==='1'?<LoaderProbe manifest={manifest} manifestHash={manifestHash}/>:<Viewer manifest={manifest} manifestHash={manifestHash}/>);}catch(e){root.render(<main><h1>Finishing 검증 준비 오류</h1><p role="alert">{e instanceof Error?e.message:String(e)}</p></main>);}}
void start();
