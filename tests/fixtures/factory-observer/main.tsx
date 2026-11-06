import { useEffect, useLayoutEffect, useMemo, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { Canvas, useFrame, useThree } from '@react-three/fiber';
import { AssetRegistry } from '../../../src/operations/scene/assets/registry';
import type { AssetEntity } from '../../../src/operations/scene/assets/registry';
import { AssetInstance } from '../../../src/operations/scene/assets/AssetInstance';
import { requireAsset } from '../../../src/operations/scene/assets/errors';
import { sha256 } from '../../../src/operations/scene/worldContractBundle';
import { isQaProbeEnabled, QaProbe } from '../../../src/operations/scene/qaProbe';
import type { QaAuthority } from '../../../src/operations/scene/qaProbe';
import { representativePose } from '../factory-assets/poses';

const qaAttempt = new URLSearchParams(location.search).get('qa-attempt') ?? 'unbound';
const manifestSha256 = 'b38745a8f648ec00ba683242d14cb66a008961ab1aba95c1df78e3e1a44a0e01';
const style = '*{box-sizing:border-box}body{margin:0;padding:24px;background:#f7f5ef;color:#25313d;font:16px/1.5 system-ui}h1{font-size:24px;margin:0}button,select{font:inherit;padding:10px;margin:8px 8px 8px 0;min-height:44px}button:focus-visible,select:focus-visible{outline:3px solid #b86b00}#viewport{width:960px;height:600px;border:1px solid #999}pre{font-size:12px;max-width:960px;white-space:pre-wrap;overflow-wrap:anywhere}';
function BoundObserver({ entity, authority, freeze }: { readonly entity: AssetEntity; readonly authority: QaAuthority; readonly freeze: boolean }) {
  const { gl, camera, invalidate } = useThree();
  const [probe] = useState(() => new QaProbe(isQaProbeEnabled(location.search, import.meta.env.VITE_STEELFLOW_QA_PROBE === '1')));
  useLayoutEffect(() => { invalidate(); }, [freeze, entity, invalidate]);
  useFrame(() => {
    if (freeze || !probe.enabled || entity.level === null) return;
    const sample = probe.observeAssets([entity], authority, camera);
    gl.domElement.dataset.qaBoundState = JSON.stringify(sample);
    gl.domElement.dataset.qaObserverWork = JSON.stringify(probe.work);
  });
  return null;
}
function Viewer({ registry }: { readonly registry: AssetRegistry }) {
  const first = registry.manifest.assets[0]; requireAsset(first, 'binding', 'observer asset');
  const [assetId, setAssetId] = useState<string>(first.id), [loaded, setLoaded] = useState(false), [hidden, setHidden] = useState(false);
  const [step, setStep] = useState(0), [step0AtMs] = useState(Date.now);
  const asset = registry.asset(assetId), fixed = useMemo(() => representativePose(registry.manifest, asset), [registry, asset]);
  const entity = useMemo(() => registry.entity({ run_id: fixed.pose.run_id, entity_type: 'equipment', entity_id: fixed.pose.owner_id, bundle_hash: fixed.envelope.bundle_hash }, asset.id), [registry, fixed, asset]);
  const authority: QaAuthority = { source: 't58-fixed-contract', runId: fixed.pose.run_id, revision: fixed.envelope.revision, bundleHash: fixed.envelope.bundle_hash, authoritativeElapsedMs: fixed.envelope.confirmed_sim_ms, stale: false };
  useEffect(() => {
    let active = true; setLoaded(false); entity.applyPose(fixed.pose);
    entity.show(0).then(() => { if (active) setLoaded(true); }).catch((error: unknown) => { if (!(error instanceof Error)) throw error; document.getElementById('load-error')?.replaceChildren(error.message); });
    return () => { active = false; entity.hide(); };
  }, [entity, fixed]);
  useEffect(() => () => registry.dispose(), [registry]);
  const dimensions = fixed.pose.material.dimensions;
  return <main><style>{style}</style><h1>실제 프레임 관찰기 · 두 자산의 로컬 어댑터</h1>
    <p>현재 T13 실제 GLB · T58 고정 합성 계약 fixture 1000 ms. 별도 legacy API 자료를 receipt에 함께 보존하며 통합 v3 스케줄러 검증은 아닙니다.</p>
    <p data-testid="visible-attempt">QA attempt {qaAttempt}</p><p data-testid="visible-authority">{authority.runId} · revision {authority.revision} · {authority.authoritativeElapsedMs} ms · bundle {authority.bundleHash}</p><p data-testid="step-counter" data-step0-at-ms={step0AtMs}>Step {step} · 연속 영상 카운터</p><p id="load-error" role="alert" /><p data-testid="observer-status">{loaded ? '실제 모델 표시' : '로딩 중'}</p>
    <label>실제 자산 <select aria-label="실제 자산" value={assetId} onChange={event => { setAssetId(event.target.value); setHidden(false); setStep(value => value + 1); }}>{registry.manifest.assets.map(item => <option key={item.id} value={item.id}>{item.kind}</option>)}</select></label>
    <button onClick={() => { setHidden(value => !value); setStep(value => value + 1); }} aria-pressed={hidden}>기하 숨김 · 메타데이터 유지</button>
    <div id="viewport"><Canvas aria-label="실제 자산 관찰 캔버스" frameloop="demand" dpr={1} camera={{ position: [9, 7, 11], fov: 42 }} gl={{ preserveDrawingBuffer: true }}>
      <color attach="background" args={['#e8e4d9']} /><ambientLight intensity={1.5} /><hemisphereLight intensity={1.4} /><directionalLight position={[-6, 12, 8]} intensity={2.4} />
      {loaded && <group visible={!hidden}><AssetInstance entity={entity} onPick={() => undefined} />
        <mesh position={[...fixed.pose.position_m]} quaternion={[...fixed.pose.orientation_xyzw]}><boxGeometry args={[(dimensions.length_mm ?? 1000) / 1000, (dimensions.thickness_mm ?? 1) / 1000, (dimensions.width_mm ?? 500) / 1000]} /><meshStandardMaterial color="#c6cdd0" metalness={0.9} roughness={0.38} /></mesh>
      </group>}
      <BoundObserver entity={entity} authority={authority} freeze={hidden} />
    </Canvas></div>
    <details><summary>T58 evaluator 고정 계약 원본 · 업무 시계 생성 없음</summary><pre data-testid="observer-contract">{JSON.stringify({ authority, envelope: fixed.envelope, snapshot: fixed.context.snapshot, manifestSha256 }, null, 2)}</pre></details>
  </main>;
}
async function start() {
  const container = document.getElementById('root'); requireAsset(container, 'binding', 'observer root');
  const response = await fetch('/assets/steelworks/manifest.json');
  requireAsset(response.ok, 'network', 'actual manifest');
  const raw = await response.text(); requireAsset(await sha256(new TextEncoder().encode(raw)) === manifestSha256, 'hash', 'actual manifest');
  const registry = new AssetRegistry(raw, { origin: location.origin }), first = registry.manifest.assets[0]; requireAsset(first, 'binding', 'actual family');
  const fixed = representativePose(registry.manifest, first); registry.beginRun(fixed.pose.run_id, fixed.envelope.bundle_hash);
  createRoot(container).render(<Viewer registry={registry} />);
}
void start();
