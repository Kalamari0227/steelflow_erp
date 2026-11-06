import { useEffect, useLayoutEffect, useMemo, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { Canvas, useFrame, useThree } from '@react-three/fiber';
import ky from 'ky';
import { AssetRegistry } from '../../../src/operations/scene/assets/registry';
import type { AssetEntity } from '../../../src/operations/scene/assets/registry';
import { AssetInstance } from '../../../src/operations/scene/assets/AssetInstance';
import { requireAsset } from '../../../src/operations/scene/assets/errors';
import { sha256 } from '../../../src/operations/scene/worldContractBundle';
import { isQaProbeEnabled, QaProbe } from '../../../src/operations/scene/qaProbe';
import type { QaAuthority } from '../../../src/operations/scene/qaProbe';
import { miniatureRequest } from './poses';
import identity from './identity.json';

const attempt = new URLSearchParams(location.search).get('qa-attempt') ?? 'unbound';
const style = '*{box-sizing:border-box}body{margin:0;background:#f7f5ef;color:#25313d;font:16px/1.5 system-ui}main{padding:24px;max-width:1420px;margin:auto}h1{font-size:25px;margin:0}p{margin:8px 0}.notice{padding:12px;background:#fffefa;border-left:4px solid #b87526}.toolbar{display:flex;flex-wrap:wrap;align-items:center;gap:8px;margin:12px 0}button,select,input{font:inherit;min-height:44px}button,select{padding:8px 14px;border:1px solid #8b9da3;border-radius:5px;background:#fffefa;color:#25313d}button[aria-pressed=true]{background:#d5e4e5;border-color:#327e85}button:focus-visible,select:focus-visible,input:focus-visible{outline:3px solid #b87526;outline-offset:2px}#viewport{height:620px;width:1120px;max-width:100%;border:1px solid #bac4c5;background:#e8e4d9}code{overflow-wrap:anywhere}pre{white-space:pre-wrap;overflow-wrap:anywhere;font-size:12px}.parts{display:flex;gap:20px;flex-wrap:wrap;font-size:14px}label{display:flex;align-items:center;gap:8px}';

function BoundObserver({ entity, authority, hidden, angle, version }: { readonly entity: AssetEntity; readonly authority: QaAuthority; readonly hidden: boolean; readonly angle: string; readonly version: number }) {
  const { gl, camera, invalidate } = useThree();
  const [probe] = useState(() => new QaProbe(isQaProbeEnabled(location.search, import.meta.env.VITE_STEELFLOW_QA_PROBE === '1')));
  useLayoutEffect(() => {
    switch (angle) {
      case 'side': camera.position.set(8, 4, 2); break;
      case 'rear': camera.position.set(-7, 5, -9); break;
      default: camera.position.set(7, 5, 11); break;
    }
    camera.lookAt(0, 1.1, 0); camera.updateProjectionMatrix(); invalidate();
  }, [angle, camera, invalidate]);
  useLayoutEffect(() => { invalidate(); }, [version, authority, hidden, invalidate]);
  useFrame(() => {
    if (hidden || !probe.enabled || entity.level === null) return;
    gl.domElement.dataset.qaBoundState = JSON.stringify(probe.observeAssets([entity], authority, camera));
  });
  return null;
}

function Viewer({ registry }: { readonly registry: AssetRegistry }) {
  const asset = registry.manifest.assets[0]; requireAsset(asset, 'binding', 'miniature');
  const [sample, setSample] = useState(0), [clock, setClock] = useState<'running' | 'paused' | 'blocked'>('running');
  const [lod, setLod] = useState(0), [loaded, setLoaded] = useState(false), [scope, setScope] = useState(true), [hidden, setHidden] = useState(false), [angle, setAngle] = useState('front');
  const [step, setStep] = useState(0), [step0AtMs] = useState(Date.now), [version, setVersion] = useState(0);
  const fixed = useMemo(() => miniatureRequest(registry.manifest, .2 + .6 * sample / 48, clock), [registry, sample, clock]);
  const entity = useMemo(() => registry.entity({ run_id: fixed.pose.run_id, entity_type: 'equipment', entity_id: fixed.pose.owner_id, bundle_hash: fixed.envelope.bundle_hash }, asset.id), [registry, asset, fixed.pose.run_id, fixed.pose.owner_id, fixed.envelope.bundle_hash]);
  const authority: QaAuthority = { source: 't58-fixed-contract', runId: fixed.pose.run_id, revision: fixed.envelope.revision, bundleHash: fixed.envelope.bundle_hash, authoritativeElapsedMs: fixed.envelope.confirmed_sim_ms, stale: false };
  const action = (update: () => void) => { update(); setStep(value => value + 1); };
  useEffect(() => {
    let active = true; setLoaded(false);
    if (!scope) { entity.hide(); return; }
    entity.show(lod).then(() => { if (active) { setLoaded(true); setVersion(value => value + 1); } }).catch((error: unknown) => { if (!(error instanceof Error)) throw error; document.getElementById('load-error')?.replaceChildren(error.message); });
    return () => { active = false; };
  }, [entity, lod, scope]);
  useLayoutEffect(() => { entity.applyPose(fixed.pose); setVersion(value => value + 1); }, [entity, fixed]);
  useEffect(() => () => registry.dispose(), [registry]);
  return <main><style>{style}</style><h1>독립 롤 · 공유 기구 검증</h1>
    <p className="notice">Blender 원본에서 만든 미니어처입니다. 승인된 합성 계약 샘플 49개를 순서대로 확인합니다. 실제 생산 스케줄러 실행을 뜻하지 않습니다.</p>
    <p data-testid="visible-attempt">QA attempt {attempt}</p><p data-testid="visible-authority">{authority.runId} · revision {authority.revision} · {authority.authoritativeElapsedMs} ms</p>
    <p data-testid="step-counter" data-step0-at-ms={step0AtMs}>Step {step} · 연속 영상 카운터</p><p role="alert" id="load-error" />
    <div className="toolbar"><label>승인 샘플 <input aria-label="승인 샘플" type="range" min="0" max="48" step="1" value={sample} onChange={event => action(() => setSample(Number(event.target.value)))} /></label><span data-testid="sample-index">{sample}</span><button onClick={() => action(() => setSample(value => Math.min(48, value + 1)))} disabled={sample === 48}>다음 승인 샘플</button>
      {(['running', 'paused', 'blocked'] as const).map(state => <button key={state} aria-pressed={clock === state} onClick={() => action(() => setClock(state))}>{state === 'running' ? '진행 상태' : state === 'paused' ? '일시 정지' : '차단 상태'}</button>)}
      {[0, 1, 2].map(level => <button key={level} aria-pressed={lod === level} onClick={() => action(() => setLod(level))}>LOD {level}</button>)}
      <button onClick={() => action(() => setScope(value => !value))}>{scope ? '범위 나가기' : '같은 개체 재진입'}</button><button aria-pressed={hidden} onClick={() => action(() => setHidden(value => !value))}>기하 숨김 · 메타데이터 유지</button>
    </div><p data-testid="observer-status">{loaded ? '실제 모델 표시' : scope ? '로딩 중' : '범위 밖'}</p>
    <div id="viewport"><Canvas aria-label="독립 롤 실제 GLB" frameloop="demand" dpr={1} camera={{ position: [7, 5, 11], fov: 40 }} gl={{ preserveDrawingBuffer: true }}>
      <color attach="background" args={['#e8e4d9']} /><ambientLight intensity={1.4} /><hemisphereLight intensity={1.3} /><directionalLight position={[-4, 8, 7]} intensity={2.5} />
      <mesh rotation={[-Math.PI / 2, 0, 0]}><planeGeometry args={[30, 20]} /><meshStandardMaterial color="#e8e4d9" roughness={.94} /></mesh>
      {loaded && scope && <group visible={!hidden}><AssetInstance entity={entity} onPick={() => undefined} />
        <mesh position={[...fixed.pose.position_m]} quaternion={[...fixed.pose.orientation_xyzw]}><boxGeometry args={[1, .2, .5]} /><meshStandardMaterial color="#b4bdc2" metalness={.85} roughness={.42} /></mesh>
      </group>}
      <BoundObserver entity={entity} authority={authority} hidden={hidden || !scope} angle={angle} version={version} />
    </Canvas></div>
    <div className="toolbar">{[['front', '정면'], ['side', '측면'], ['rear', '후면']].map(([id, label]) => <button key={id} onClick={() => action(() => setAngle(id ?? 'front'))}>{label}</button>)}</div>
    <div className="parts"><span>구동 롤: <strong data-testid="canonical-value">{fixed.pose.channels[0]?.value.toFixed(6)} rad</strong></span><span>종속 롤: 반대 방향 ×1 · 같은 방향 ×½ · 반대 방향 ×½</span><span data-testid="clock-state">{clock}</span></div>
    <details><summary>합성 계약 원본과 출처</summary><pre data-testid="observer-contract">{JSON.stringify({ authority, envelope: fixed.envelope, snapshot: fixed.context.snapshot, manifestSha256: identity.manifestSha256, source: identity, pose: fixed.pose, lod: entity.level }, null, 2)}</pre></details>
  </main>;
}

async function start(): Promise<void> {
  const container = document.getElementById('root'); requireAsset(container, 'binding', 'fixture root');
  const raw = await ky('/assets/steelworks/manifest.json', { retry: 0, timeout: 15000, redirect: 'error' }).text();
  requireAsset(await sha256(new TextEncoder().encode(raw)) === identity.manifestSha256, 'hash', 'miniature manifest');
  const registry = new AssetRegistry(raw, { origin: location.origin }), fixed = miniatureRequest(registry.manifest, .2, 'running');
  registry.beginRun(fixed.pose.run_id, fixed.envelope.bundle_hash);
  createRoot(container).render(<Viewer registry={registry} />);
}
void start();
