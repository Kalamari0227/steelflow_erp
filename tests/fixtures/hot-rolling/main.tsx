import { useEffect, useMemo, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { Canvas } from '@react-three/fiber';
import { AssetRegistry } from '../../../src/operations/scene/assets/registry';
import { AssetInstance } from '../../../src/operations/scene/assets/AssetInstance';
import { requireAsset } from '../../../src/operations/scene/assets/errors';
import { sha256 } from '../../../src/operations/scene/worldContractBundle';
import { frames, coilerContactFrames, layingContactFrames, bedBoundaryFrames, phaseSample, preparePhase, internalFeedContactFrames } from './frames';
import { Diagnostics } from './diagnostics';
import { MaterialEntity } from './material';
import { Studio } from './lighting';
import './style.css';

const query = new URLSearchParams(location.search);
const attempt = query.get('qa-attempt') ?? 'manual-family-inspection';

function Viewer({ registry, manifestHash }: { readonly registry: AssetRegistry; readonly manifestHash: string }) {
  const first = registry.manifest.assets[0]; requireAsset(first, 'binding', 'hot-rolling family');
  const [id, setId] = useState(query.get('asset') ?? first.id), asset = registry.asset(id);
  const availableFrames=asset.kind==='coiler' ? [...frames,...coilerContactFrames] : asset.kind==='laying_head' ? [...frames,...layingContactFrames] : asset.kind==='cooling_bed' ? [...frames,...bedBoundaryFrames] : asset.internal_feeds ? [...frames,...internalFeedContactFrames(asset)] : frames;
  const [index, setIndex] = useState(()=>{const wanted=query.get('phase') ?? 'idle',found=availableFrames.findIndex(f=>f.name===wanted);requireAsset(found>=0,'binding','registered phase');return found;}), frame = availableFrames[index]; requireAsset(frame, 'binding', 'explicit phase frame');
  const [speed,setSpeed]=useState<1|2|4>(1);
  const produce=useMemo(()=>preparePhase(registry.manifest,asset,manifestHash,speed),[registry,asset,manifestHash,speed]);
  const sample=useMemo(()=>produce(frame),[produce,frame]);
  const entity = useMemo(() => registry.entity({ run_id: sample.pose.run_id, entity_type: 'equipment', entity_id: sample.pose.owner_id, bundle_hash: sample.envelope.bundle_hash }, asset.id), [registry, asset, sample.pose.run_id, sample.pose.owner_id, sample.envelope.bundle_hash]);
  const [lod, setLod] = useState(0), [angle, setAngle] = useState('front'), [cutaway, setCutaway] = useState(true), [hidden, setHidden] = useState(false);
  const [rebind,setRebind]=useState(0);
  const [revision, setRevision] = useState(0), [status, setStatus] = useState('읽는 중'), [error, setError] = useState('');
  useEffect(() => {
    let active = true;
    setStatus('읽는 중'); setError('');
    entity.applyPose(sample.pose);
    entity.show(lod).then(() => { if (active) { setStatus('실제 모델 표시'); setRevision(n => n+1); } }).catch((failure: unknown) => { if (active) { setError(failure instanceof Error ? failure.message : String(failure)); setStatus('자산 오류'); } });
    return () => { active = false; };
  }, [entity, lod]);
  useEffect(() => { entity.applyPose(sample.pose); setRevision(n => n+1); }, [entity, sample]);
  useEffect(() => { entity.setCutaway(cutaway); setRevision(n => n+1); }, [entity, cutaway]);
  useEffect(() => () => entity.hide(), [entity]);
  useEffect(() => () => registry.dispose(), [registry]);
  const authority = { source: 't58-fixed-contract', runId: sample.pose.run_id, revision: sample.pose.revision, bundleHash: sample.envelope.bundle_hash, authoritativeElapsedMs: sample.envelope.confirmed_sim_ms, stale: false };
  return <main><header><div><div className="eyebrow">SteelFlow · miniature machinery</div><h1>열간 공정 자산 · 21개 변형</h1></div><span className="status" data-testid="load-status">{status}</span></header>
    <p className="notice">명시된 합성 공정 샘플입니다. 버튼으로 선택한 단계에서만 작업부와 소재가 바뀝니다. 실제 업무 서버의 공정 실행을 의미하지 않습니다. 코일러 complete는 4m 스트립의 한 회전 합성 기구 단계 종료이며, 남은 이송 꼬리가 보입니다. 완전 권취·업무 형상 전환·외부 인계를 뜻하지 않습니다.</p>
    <div className="toolbar"><label>설비 <select aria-label="실제 자산" value={id} onChange={e => { setId(e.target.value); setIndex(0); }}>{registry.manifest.assets.map(a => <option key={a.id} value={a.id}>{a.placement_ids[0]?.replace('equipment:','')} · {a.kind}</option>)}</select></label>{[0,1,2].map(level => <button key={level} aria-pressed={level===lod} onClick={() => setLod(level)}>LOD {level}</button>)}<button aria-pressed={cutaway} onClick={() => setCutaway(v => !v)}>지붕 절개</button><button aria-pressed={hidden} onClick={() => { setHidden(v => !v); setRevision(n => n+1); }}>기하 숨김 · 메타데이터 유지</button><button onClick={() => {setRebind(n => n+1);setRevision(n => n+1);}}>같은 단계 재연결</button>{([1,2,4] as const).map(value=><button key={value} aria-pressed={speed===value} onClick={()=>setSpeed(value)}>샘플 속도 x{value}</button>)}</div>
    {error && <p role="alert">{error}</p>}
    <div className="layout"><section><div className="viewport"><Canvas aria-label="실제 열간 GLB 검증" orthographic shadows frameloop="demand" dpr={1.5} camera={{ position: [16,11,16], zoom:70,near:.1,far:1000 }} gl={{ preserveDrawingBuffer:true }}>
      <color attach="background" args={['#e9e0cd']} /><Studio /><ambientLight intensity={.4} /><hemisphereLight args={['#eff7ff','#c3ac83',.7]} /><directionalLight position={[2,12,6]} intensity={2.3} castShadow shadow-mapSize={[2048,2048]} /><directionalLight position={[-8,7,-10]} intensity={1.0} />
      <mesh rotation={[-Math.PI/2,0,0]} receiveShadow><planeGeometry args={[100,100]} /><meshStandardMaterial color="#d5c8ae" roughness={.9} /></mesh>
      <group key={rebind} visible={!hidden} dispose={null}><AssetInstance entity={entity} onPick={() => entity.setSelected(true)} />{entity.level!==null && <MaterialEntity pose={sample.pose} kind={asset.kind} feed={frame.feed} heat={frame.heat} formingRange={(() => {const p=asset.moving_parts.find(p => ['winding_mandrel','laying_rotation'].includes(p.function) && p.binding.type!=='mechanical_follower');return p ? {function:p.function,...p.range} : undefined;})()} />}</group>
      <Diagnostics entity={entity} sample={sample} angle={angle} revision={revision} bindingRevision={rebind} />
    </Canvas></div><div className="toolbar">{[['front','정면'],['side','측면'],['rear','후면'],['close','근접']].map(([key,label]) => <button key={key} aria-pressed={angle===key} onClick={() => setAngle(key ?? 'front')}>{label}</button>)}</div>
    <div className="toolbar"><button disabled={index===0} onClick={() => setIndex(i => i-1)}>이전 단계</button><label>공정 샘플 <select aria-label="공정 샘플" value={index} onChange={e => setIndex(Number(e.target.value))}>{availableFrames.map((f,i) => <option key={f.name} value={i}>{f.name}</option>)}</select></label><button disabled={index===availableFrames.length-1} onClick={() => setIndex(i => i+1)}>다음 단계</button><strong className="phase" data-testid="phase-name">{frame.name}</strong></div></section>
    <aside><h2>{asset.placement_ids[0]?.replace('equipment:','')}</h2><div className="field"><span>기구</span>{asset.kind}</div><div className="field"><span>합성 공정</span>{frame.clock} · {Math.round(frame.progress*100)}%</div><div className="field"><span>소재 · 단일 custody</span>{sample.pose.material.form}<br/>{sample.pose.attachment_id}</div><div className="field"><span>기능부</span>{asset.moving_parts.filter(p => p.binding.type !== 'mechanical_follower').map(p => <div key={p.id}>{p.function}</div>)}</div><div className="field"><span>검증 실행</span><small data-testid="visible-attempt">{attempt}</small></div><p data-testid="step-counter">Step {index} · 연속 영상 카운터</p><details><summary>합성 샘플 근거</summary><pre data-testid="fixture-contract">{JSON.stringify({authority,manifestSha256:manifestHash,envelope:sample.envelope,snapshot:sample.snapshot,context:sample.context,frame},null,2)}</pre></details></aside></div>
    <footer>공개 기능 개념을 바탕으로 직접 제작한 합성 미니어처입니다. 치수·축·속도·배치는 실제 사업장의 사양이 아닙니다.</footer>
  </main>;
}

async function start() {
  const container = document.getElementById('root'); requireAsset(container, 'binding', 'root');
  const root = createRoot(container);
  try {
    const response = await fetch('/assets/steelworks/hot-rolling/manifest.json', { redirect:'error' });
    requireAsset(response.ok, 'network', 'hot-rolling manifest');
    const raw = await response.text(), registry = new AssetRegistry(raw, { origin:location.origin });
    const first = registry.manifest.assets[0]; requireAsset(first, 'binding', 'hot-rolling family');
    const manifestHash=await sha256(new TextEncoder().encode(raw));
    const sample = phaseSample(registry.manifest, first, frames[0],manifestHash); registry.beginRun(sample.pose.run_id, sample.envelope.bundle_hash);
    root.render(<Viewer registry={registry} manifestHash={manifestHash} />);
  } catch (failure) { root.render(<main><h1>열간 자산 검증 준비 오류</h1><p role="alert">{failure instanceof Error ? failure.message : String(failure)}</p></main>); }
}
void start();
