import { useEffect, useMemo, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { Canvas } from '@react-three/fiber';
import ky from 'ky';
import { AssetRegistry } from '../../../src/operations/scene/assets/registry';
import { AssetInstance } from '../../../src/operations/scene/assets/AssetInstance';
import { requireAsset } from '../../../src/operations/scene/assets/errors';
import { parseProductionAssetManifest } from '../../../src/operations/scene/assets/manifest';
import { sha256 } from '../../../src/operations/scene/worldContractBundle';
import policyBytes from '../../../shared/asset-requirements.json?raw';
import recipeBytes from '../../../shared/motion-recipes.json?raw';
import { frameAt, phaseSample } from './poses';
import type { Clock } from './poses';
import { Diagnostics } from './diagnostics';
import { FixtureCarrier, MaterialEntity } from './material';
import './style.css';

const query=new URLSearchParams(location.search),attempt=query.get('qa-attempt')??'manual-steelmaking-inspection';
type SourceProof={readonly manifestSha256:string;readonly familyHashes:readonly string[];readonly policySha256:string;readonly recipesSha256:string};

function Viewer({registry,source}:{readonly registry:AssetRegistry;readonly source:SourceProof}){
  const first=registry.manifest.assets[0];requireAsset(first,'binding','steelmaking family');
  const [id,setId]=useState(query.get('asset')??first.id),asset=registry.asset(id);
  const [index,setIndex]=useState(0),[clock,setClock]=useState<Clock>('paused'),frame=frameAt(index,clock);
  const sample=useMemo(()=>phaseSample(registry.manifest,asset,frame),[registry,asset,index,clock]);
  const entity=useMemo(()=>registry.entity({run_id:sample.pose.run_id,entity_type:'equipment',entity_id:sample.pose.owner_id,bundle_hash:sample.envelope.bundle_hash},asset.id),[registry,asset,sample.pose.run_id,sample.pose.owner_id,sample.envelope.bundle_hash]);
  const [lod,setLod]=useState(0),[angle,setAngle]=useState('front'),[cutaway,setCutaway]=useState(false),[hidden,setHidden]=useState(false);
  const [revision,setRevision]=useState(0),[status,setStatus]=useState('읽는 중'),[error,setError]=useState(''),[step,setStep]=useState(0),[step0AtMs]=useState(Date.now);
  const action=(update:()=>void)=>{update();setStep(n=>n+1);};
  useEffect(()=>{
    let active=true;setStatus('읽는 중');setError('');entity.applyPose(sample.pose);
    entity.show(lod).then(()=>{if(active){setStatus('실제 모델 표시');setRevision(n=>n+1);}}).catch((failure:unknown)=>{if(!(failure instanceof Error))throw failure;if(active){setError(failure.message);setStatus('자산 오류');}});
    return()=>{active=false;};
  },[entity,lod]);
  useEffect(()=>{entity.applyPose(sample.pose);setRevision(n=>n+1);},[entity,sample]);
  useEffect(()=>{entity.setCutaway(cutaway);setRevision(n=>n+1);},[entity,cutaway]);
  useEffect(()=>()=>entity.hide(),[entity]);useEffect(()=>()=>registry.dispose(),[registry]);
  const authority={source:'t58-fixed-contract',runId:sample.pose.run_id,revision:sample.pose.revision,bundleHash:sample.envelope.bundle_hash,authoritativeElapsedMs:sample.envelope.confirmed_sim_ms,stale:false};
  return <main><header><div><div className="eyebrow">SteelFlow · miniature steelmaking</div><h1>제선·제강 설비 · 14개 변형</h1></div><span className="status" data-testid="load-status">{status}</span></header>
    <p className="notice">직접 제작한 Blender 원본과 실제 GLB를 표시합니다. 각 단계는 명시된 합성 계약 샘플이며 실제 생산 스케줄러·운송 업무의 완료를 뜻하지 않습니다.</p>
    <div className="toolbar"><label>설비 <select aria-label="실제 자산" value={id} onChange={e=>action(()=>{setId(e.target.value);setIndex(0);setClock('paused');})}>{registry.manifest.assets.map(a=><option key={a.id} value={a.id}>{a.placement_ids[0]?.replace('equipment:','')} · {a.kind}</option>)}</select></label>{[0,1,2].map(level=><button key={level} aria-pressed={level===lod} onClick={()=>action(()=>setLod(level))}>LOD {level}</button>)}<button aria-pressed={cutaway} onClick={()=>action(()=>setCutaway(v=>!v))}>지붕 절개</button><button aria-pressed={hidden} onClick={()=>action(()=>{setHidden(v=>!v);setRevision(n=>n+1);})}>기하 숨김 · 메타데이터 유지</button></div>
    {error&&<p role="alert">{error}</p>}
    <div className="layout"><section><div className="viewport"><Canvas aria-label="실제 제선·제강 GLB 검증" shadows frameloop="demand" dpr={1.5} camera={{position:[16,12,18],fov:42}} gl={{preserveDrawingBuffer:true}}>
      <color attach="background" args={['#e8e4d9']}/><ambientLight intensity={1.1}/><hemisphereLight args={['#e6eff6','#e8e4d9',1.1]}/><directionalLight position={[-6,14,8]} intensity={2.4} castShadow shadow-mapSize={[2048,2048]}/><directionalLight position={[7,6,-8]} intensity={1.1}/>
      <mesh rotation={[-Math.PI/2,0,0]} receiveShadow><planeGeometry args={[100,100]}/><meshStandardMaterial color="#e8e4d9" roughness={.92}/></mesh>
      <group visible={!hidden}><AssetInstance entity={entity} onPick={()=>entity.setSelected(true)}/>{entity.level!==null&&<><FixtureCarrier kind={asset.kind}/><MaterialEntity pose={sample.pose} kind={asset.kind} progress={frame.progress}/></>}</group>
      <Diagnostics entity={entity} sample={sample} angle={angle} revision={revision}/>
    </Canvas></div><div className="toolbar">{[['front','정면'],['side','측면'],['rear','후면'],['close','근접']].map(([key,label])=><button key={key} aria-pressed={angle===key} onClick={()=>action(()=>setAngle(key??'front'))}>{label}</button>)}</div>
    <div className="toolbar"><label>승인 샘플 <input type="range" aria-label="승인 샘플" min="0" max="64" step="1" value={index} onChange={e=>action(()=>setIndex(Number(e.target.value)))}/></label><button disabled={index===64} onClick={()=>action(()=>setIndex(i=>Math.min(64,i+1)))}>다음 승인 샘플</button>{(['running','paused','blocked'] as const).map(state=><button key={state} aria-pressed={clock===state} onClick={()=>action(()=>setClock(state))}>{state==='running'?'진행 상태':state==='paused'?'일시 정지':'차단 상태'}</button>)}</div><strong className="phase" data-testid="phase-name">{sample.stage} · {index}/64 · {clock}</strong></section>
    <aside><h2>{asset.placement_ids[0]?.replace('equipment:','')}</h2><div className="field"><span>소재 · 한 개의 custody</span>{sample.pose.material.form}<br/>{sample.pose.attachment_id}</div><div className="field"><span>확인된 합성 시각</span>{authority.authoritativeElapsedMs} ms · {clock}</div><div className="field"><span>실제 기능부</span>{asset.moving_parts.filter(p=>p.binding.type!=='mechanical_follower').map(p=><div key={p.id}>{p.function}</div>)}</div>{asset.fixed_parts.map(part=><div className="field" key={part.id}><span>{part.function==='gas_tuyere'?'정련 가스 노즐':'래들 받침'}</span>{part.binding===null?'독립 이동 없는 받침':sample.pose.channels.find(c=>c.function_id===part.function)?.value===1?'가스 공급 중':'가스 공급 대기'}</div>)}<div className="field"><span>기계식 동기 부품</span>{asset.moving_parts.filter(p=>p.binding.type==='mechanical_follower').length}개 독립 피벗</div><p data-testid="visible-attempt">{attempt}</p><p data-testid="step-counter" data-step0-at-ms={step0AtMs}>Step {step} · 연속 영상 카운터</p><details><summary>현재 바이트와 합성 계약</summary><pre data-testid="fixture-contract">{JSON.stringify({authority,...source,envelope:sample.envelope,snapshot:sample.snapshot,frame,stage:sample.stage},null,2)}</pre></details></aside></div>
    <footer>밝은 바닥·청회색 구조·따뜻한 안전색은 승인 시안 A/B/C와 프로젝트 토큰을 따릅니다. 치수·기구 범위는 합성 설계이며 실측 사업장 사양이 아닙니다.</footer>
  </main>;
}

async function start(){
  const container=document.getElementById('root');requireAsset(container,'binding','root');const root=createRoot(container);
  try{
    const raws=await Promise.all(['steelmaking','stainless'].map(f=>ky.get(`/assets/steelworks/${f}/manifest.json`,{redirect:'error',timeout:15000,retry:0}).text()));
    const manifests=raws.map(parseProductionAssetManifest),merged={schema_version:1,purpose:'production',assets:manifests.flatMap(m=>m.assets)};
    requireAsset(merged.assets.length===14,'binding','exact T19 14 variants');
    const registry=new AssetRegistry(JSON.stringify(merged),{origin:location.origin}),first=registry.manifest.assets[0];requireAsset(first,'binding','first');
    const sample=phaseSample(registry.manifest,first,frameAt(0,'paused'));registry.beginRun(sample.pose.run_id,sample.envelope.bundle_hash);
    const digest=(text:string)=>sha256(new TextEncoder().encode(text));
    const source={manifestSha256:await digest(raws.join('\n')),familyHashes:await Promise.all(raws.map(digest)),policySha256:await digest(policyBytes),recipesSha256:await digest(recipeBytes)};
    root.render(<Viewer registry={registry} source={source}/>);
  }catch(failure){if(!(failure instanceof Error))throw failure;root.render(<main><h1>제선·제강 자산 준비 오류</h1><p role="alert">{failure.message}</p></main>);}
}
void start();
