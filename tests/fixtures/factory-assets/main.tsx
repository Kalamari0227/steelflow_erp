import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { Canvas, useFrame, useThree } from '@react-three/fiber';
import { Box3, Mesh, Vector3 } from 'three';
import ky from 'ky';
import { AssetRegistry } from '../../../src/operations/scene/assets/registry';
import type { AssetEntity, AssetIdentity } from '../../../src/operations/scene/assets/registry';
import { AssetInstance } from '../../../src/operations/scene/assets/AssetInstance';
import { AssetLoadError, requireAsset } from '../../../src/operations/scene/assets/errors';
import { parseProductionAssetManifest } from '../../../src/operations/scene/assets/manifest';
import { sha256 } from '../../../src/operations/scene/worldContractBundle';
import { representativePose } from './poses';
import type { MotionPose } from '../../../src/operations/scene/motion/contracts';
import { useWorldStore } from '../../../src/store';
import { SimulationControls } from '../../../src/components/SimulationControls';
import { chooseLod } from '../../../src/operations/scene/assets/lod';

const manifestHash = 'b38745a8f648ec00ba683242d14cb66a008961ab1aba95c1df78e3e1a44a0e01';
const query = new URLSearchParams(location.search);
const style = `*{box-sizing:border-box}body{margin:0;background:#f7f5ef;color:#25313d;font:15px/1.5 system-ui,sans-serif}main{padding:24px;max-width:1600px;margin:auto}h1{font-size:24px;margin:0}h2{font-size:17px}button,select{font:inherit;min-height:44px;padding:8px 16px;border:1px solid #7895a5;border-radius:6px;background:#fffefa;color:#25313d;margin:4px}button:focus-visible,select:focus-visible{outline:3px solid #b86b00;outline-offset:3px}button[aria-pressed=true]{background:#dfe9e8;border-color:#317f82}button:disabled{opacity:.5}.layout{display:grid;grid-template-columns:minmax(0,1fr) 310px;gap:20px}.viewport{height:650px;background:#e8e4d9;border:1px solid #ccc;position:relative;border-radius:8px}.viewport.selected{border:3px solid #b86b00}aside{overflow-wrap:anywhere;background:#fffefa;padding:16px;border-radius:8px}.notice{padding:12px;border-left:4px solid #b86b00;background:#fffefa}.toolbar{display:flex;flex-wrap:wrap;align-items:center;margin:16px 0}table{border-collapse:collapse;width:100%;background:#fffefa}th,td{text-align:left;border-bottom:1px solid #d8dedf;padding:12px;overflow-wrap:anywhere}small{color:#52606b}pre{white-space:pre-wrap;font-size:12px;overflow-wrap:anywhere}@media(max-width:900px){.layout{grid-template-columns:1fr}.viewport{height:450px}main{padding:12px}}`;

function LegacyClock() {
  const { world, acquirePolling } = useWorldStore();
  useEffect(() => acquirePolling(), [acquirePolling]);
  return <section aria-label="분리된 로컬 QA 서버 시계"><h2>별도 legacy QA 서버 제어</h2><p>이 시계는 위의 고정 T58 pose와 별개입니다. 자산 로딩은 서버 명령을 보내지 않습니다.</p><SimulationControls /><p data-testid="legacy-clock">{world?.run.id} · {world?.run.elapsed_ms ?? '확인 중'} ms</p></section>;
}

function Diagnostics({ entity, comparison, registry, pose, revision, angle }: {
  readonly entity: AssetEntity; readonly comparison: AssetEntity; readonly registry: AssetRegistry; readonly pose: MotionPose;
  readonly revision: number; readonly angle: string;
}) {
  const { gl, scene, camera, invalidate } = useThree();
  useLayoutEffect(() => {
    const position = angle === 'side' ? [1, 6, 16] : angle === 'rear' ? [-10, 7, -12] : [12, 9, 13];
    const [x, y, z] = position; if (x === undefined || y === undefined || z === undefined) return;
    camera.position.set(x, y, z); camera.lookAt(2, 1.2, 0); camera.updateProjectionMatrix(); invalidate();
  }, [angle, camera, invalidate]);
  useLayoutEffect(() => { invalidate(); }, [revision, invalidate]);
  useFrame(() => {
    scene.updateMatrixWorld(true); camera.updateMatrixWorld(true);
    const rect = gl.domElement.getBoundingClientRect();
    const targetNode = entity.nodes.get('cutting_tool') ?? entity.nodes.get('sink_roll');
    const target = targetNode?.getWorldPosition(new Vector3()) ?? new Vector3();
    const projection = target.clone().project(camera);
    const parts = [...entity.nodes].filter(([id]) => entity.asset.moving_parts.some(p => p.node_id === id) || entity.asset.fixed_parts.some(p => p.node_id === id)).map(([id, node]) => ({ id, uuid: node.uuid, position: node.position.toArray(), quaternion: node.quaternion.toArray(), matrix: [...node.matrixWorld.elements], state: node.userData.operationalState ?? null }));
    let triangles = 0;
    entity.root.traverse(node => { if (node instanceof Mesh) triangles += (node.geometry.index?.count ?? node.geometry.getAttribute('position')?.count ?? 0) / 3; });
    const handles = (value: AssetEntity) => {
      const output: { readonly node: string; readonly geometry: string; readonly materials: readonly string[] }[] = [];
      value.root.traverse(node => { if (node instanceof Mesh) output.push({ node: String(node.userData.semantic_id), geometry: node.geometry.uuid, materials: (Array.isArray(node.material) ? node.material : [node.material]).map(material => material.uuid) }); });
      return output;
    };
    const materialNodes: { readonly id: string; readonly attachmentId: string; readonly versionId: string; readonly position: readonly number[]; readonly matrix: readonly number[]; readonly min: readonly number[]; readonly max: readonly number[] }[] = [];
    scene.traverse(node => { if (node instanceof Mesh && node.userData.poseMaterial === true) { const bounds = new Box3().setFromObject(node); materialNodes.push({ id: String(node.userData.materialId), attachmentId: String(node.userData.attachmentId), versionId: String(node.userData.versionId), position: node.getWorldPosition(new Vector3()).toArray(), matrix: [...node.matrixWorld.elements], min: bounds.min.toArray(), max: bounds.max.toArray() }); } });
    gl.domElement.dataset.assetState = JSON.stringify({ key: entity.key, identity: entity.identity, rootUuid: entity.root.uuid, lod: entity.level, selected: entity.root.userData.selected, cutaway: entity.cutaway, roofs: entity.asset.cutaway.roof_node_ids, parts, sockets: entity.level === null ? [] : entity.sockets(), handles: handles(entity), materialNodes, comparison: { key: comparison.key, lod: comparison.level, handles: handles(comparison), parts: [...comparison.nodes].filter(([id]) => comparison.asset.moving_parts.some(p => p.node_id === id)).map(([id, node]) => ({ id, position: node.position.toArray(), quaternion: node.quaternion.toArray() })) }, resourceLeases: registry.resources(), pose, authorityElapsedMs: 1000, triangles, renderer: { calls: gl.info.render.calls, geometries: gl.info.memory.geometries, textures: gl.info.memory.textures }, camera: { position: camera.position.toArray(), matrixWorld: camera.matrixWorld.toArray(), projectionMatrix: camera.projectionMatrix.toArray() }, pick: { x: rect.left + (projection.x + 1) * rect.width / 2, y: rect.top + (1 - projection.y) * rect.height / 2, world: target.toArray() } });
  });
  return null;
}

function Viewer({ registry }: { readonly registry: AssetRegistry }) {
  const first = registry.manifest.assets[0]; requireAsset(first, 'binding', 'representative assets');
  const [assetId, setAssetId] = useState(query.get('asset') ?? first.id);
  const asset = registry.asset(assetId);
  const fixed = useMemo(() => representativePose(registry.manifest, asset), [registry, asset]);
  const entity = useMemo(() => registry.entity({ run_id: fixed.pose.run_id, entity_type: 'equipment', entity_id: fixed.pose.owner_id, bundle_hash: fixed.envelope.bundle_hash }, asset.id), [registry, fixed, asset]);
  const comparison = useMemo(() => registry.entity({ ...entity.identity, entity_type: 'qa_comparison', entity_id: `comparison:${entity.identity.entity_id}` }, asset.id), [registry, entity, asset]);
  const [lod, setLod] = useState(query.get('lod') === '1' ? 1 : query.get('lod') === '2' ? 2 : 0);
  const [selected, setSelected] = useState(query.get('selected') === '1');
  const [hovered, setHovered] = useState<AssetIdentity | null>(null);
  const [cutaway, setCutaway] = useState(query.get('cutaway') === '1');
  const [inScope, setInScope] = useState(true), [version, setVersion] = useState(0), [reload, setReload] = useState(0);
  const [error, setError] = useState<AssetLoadError | null>(null), [view, setView] = useState<'3d' | '2d'>('3d');
  const [status, setStatus] = useState('로딩 중'), [angle, setAngle] = useState('front');
  const fallback = useRef<HTMLParagraphElement>(null);
  const pick = useCallback((picked: AssetIdentity) => { setSelected(picked.entity_type === entity.identity.entity_type && picked.entity_id === entity.identity.entity_id); }, [entity]);
  useEffect(() => {
    const search = new URLSearchParams({ asset: assetId, lod: String(lod), selected: selected ? '1' : '0', cutaway: cutaway ? '1' : '0' });
    history.replaceState(null, '', `${location.pathname}?${search}`);
  }, [assetId, lod, selected, cutaway]);
  useEffect(() => { entity.setSelected(selected); entity.setCutaway(cutaway); setVersion(v => v + 1); }, [entity, selected, cutaway]);
  useEffect(() => {
    let active = true;
    if (!inScope) { entity.hide(); comparison.hide(); setStatus('범위 밖 · 같은 선택 유지'); setVersion(v => v + 1); return; }
    setStatus('실제 로컬 GLB 로딩 중'); setError(null);
    entity.applyPose(fixed.pose); comparison.root.position.set(7, 0, 0);
    Promise.all([entity.show(lod), comparison.show(lod)]).then(() => {
      if (active) { setStatus('실제 모델 표시'); setVersion(v => v + 1); }
    }).catch((failure: unknown) => {
      if (!active) return;
      if (!(failure instanceof AssetLoadError)) throw failure;
      entity.hide(); comparison.hide(); setError(failure); setView('2d'); setStatus('자산 오류');
    });
    return () => { active = false; };
  }, [entity, comparison, fixed, lod, inScope, reload]);
  useEffect(() => () => { entity.hide(); comparison.hide(); }, [entity, comparison]);
  useEffect(() => { if (error && view === '2d') fallback.current?.focus(); }, [error, view]);
  useEffect(() => () => registry.dispose(), [registry]);
  const dimensions = fixed.pose.material.dimensions;
  return <main><style>{style}</style><h1>실제 자산 · 로더 검증</h1><p>절단기·도금 설비 2종의 실제 GLB 검증입니다. 전체 공장 배치와 실시간 v3 실행은 후속 작업입니다.</p>
    <p className="notice">T58 고정 계약 fixture · 일시 정지 · 확인 시간 <strong data-testid="authority-time">1000 ms</strong>. 서버 스케줄러 실행이 아닙니다. 오른쪽 복제본은 공유 자원·독립 부품 상태 비교용입니다.</p><LegacyClock />
    <div className="toolbar" aria-label="자산 보기"><label>실제 자산 <select aria-label="실제 자산" value={assetId} onChange={event => { setAssetId(event.target.value); setSelected(false); }}>{registry.manifest.assets.map(row => <option key={row.id} value={row.id}>{row.kind} · {row.placement_ids[0]}</option>)}</select></label>{[0, 1, 2].map(level => <button key={level} aria-pressed={lod === level} title={`검증용 거리 밴드 ${level === 0 ? 0 : level === 1 ? 350 : 1000}m`} onClick={() => setLod(current => chooseLod(level === 0 ? 0 : level === 1 ? 350 : 1000, current === 0 ? 0 : current === 1 ? 1 : 2, false))}>LOD {level}</button>)}<button aria-pressed={cutaway} onClick={() => setCutaway(v => !v)}>지붕 절개 · 지붕 없음</button><button onClick={() => setInScope(v => !v)}>{inScope ? '범위 나가기' : '같은 개체 재진입'}</button><button onClick={() => { entity.hide(); comparison.hide(); setReload(v => v + 1); }}>로컬 자산 다시 읽기</button><button aria-pressed={view === '2d'} onClick={() => setView(v => v === '2d' ? '3d' : '2d')}>2D 자료</button></div>
    {error && <p role="alert" data-testid="asset-error">자산을 표시하지 못했습니다. {error.code} · {error.reference}</p>}
    {error && view === '2d' && <p role="status" tabIndex={-1} ref={fallback} className="notice">2D 계약 자료로 전환했습니다. 같은 실행·번들·개체 선택을 유지합니다. 로딩 오류는 작업 완료가 아닙니다.</p>}
    <div className="layout"><section aria-label="실제 3D 자산">{view === '3d' ? <><div className={`viewport ${selected ? 'selected' : ''}`}><Canvas aria-label="실제 GLB 3D 검증" shadows frameloop="demand" dpr={1} camera={{ position: [12, 9, 13], fov: 42 }} gl={{ preserveDrawingBuffer: true }}>
      <color attach="background" args={['#e8e4d9']} /><ambientLight intensity={1.5} /><hemisphereLight intensity={1.4} /><directionalLight position={[-6, 12, 8]} intensity={2.4} castShadow />
      <mesh rotation={[-Math.PI / 2, 0, 0]} receiveShadow><planeGeometry args={[30, 22]} /><meshStandardMaterial color="#e8e4d9" roughness={0.92} /></mesh>
      {inScope && <><AssetInstance entity={entity} onPick={pick} onHover={setHovered} /><AssetInstance entity={comparison} onPick={pick} onHover={setHovered} />{entity.level !== null && <mesh name={`material:${fixed.pose.material.material_id}`} userData={{ poseMaterial: true, materialId: fixed.pose.material.material_id, attachmentId: fixed.pose.attachment_id, versionId: fixed.pose.material.material_version_id }} position={[...fixed.pose.position_m]} quaternion={[...fixed.pose.orientation_xyzw]} castShadow><boxGeometry args={[(dimensions.length_mm ?? 1000) / 1000, (dimensions.thickness_mm ?? 1) / 1000, (dimensions.width_mm ?? 500) / 1000]} /><meshStandardMaterial color="#c6cdd0" metalness={0.9} roughness={0.38} /></mesh>}</>}
      <Diagnostics entity={entity} comparison={comparison} registry={registry} pose={fixed.pose} revision={version} angle={angle} />
    </Canvas></div><div className="toolbar">{[['front', '정면'], ['side', '측면'], ['rear', '후면']].map(([id, label]) => <button key={id} onClick={() => setAngle(id ?? 'front')} aria-pressed={angle === id}>{label}</button>)}</div></> : <table data-testid="asset-2d"><caption>같은 개체의 확인된 계약 자료 · GLB 오류와 별개로 유지</caption><thead><tr><th>항목</th><th>값</th></tr></thead><tbody><tr><th>개체</th><td>{entity.identity.entity_id}</td></tr><tr><th>형태</th><td>{fixed.pose.material.form}</td></tr><tr><th>확인 시간</th><td>1000 ms · 일시 정지</td></tr>{fixed.pose.channels.map(channel => <tr key={channel.function_id}><th>{channel.function_id}</th><td>{channel.kind} · {channel.value}</td></tr>)}</tbody></table>}</section>
    <aside aria-label="선택 자료"><p data-testid="hovered-entity" data-hover-identity={JSON.stringify(hovered)}>가리킨 개체: {hovered?.entity_id ?? '없음'}</p><h2>{selected ? '선택됨' : '선택 대기'}</h2><button onClick={() => setSelected(true)} aria-pressed={selected}>이 개체 선택</button><p data-testid="load-status" role="status">{status}</p><dl><dt>개체</dt><dd data-testid="selected-entity">{entity.identity.entity_id}</dd><dt>실행</dt><dd>{entity.identity.run_id}</dd><dt>번들</dt><dd>{entity.identity.bundle_hash}</dd><dt>원본 manifest SHA256</dt><dd>{manifestHash}</dd><dt>지붕 노드</dt><dd>0 · 실제 절개 대상 없음</dd><dt>기능 상태</dt><dd>{fixed.pose.channels.map(channel => <p key={channel.function_id}>{channel.function_id}: {channel.value.toFixed(3)} {channel.kind === 'state' ? '· 고정 nozzle 상태, 물리 이동 없음' : ''}</p>)}</dd></dl><details><summary>고정 pose 근거</summary><pre data-testid="fixed-pose">{JSON.stringify({ source: 'T58 evaluateMotion, explicit synthetic contract fixture', envelope: fixed.envelope, pose: fixed.pose }, null, 2)}</pre></details></aside></div>
  </main>;
}

async function start(): Promise<void> {
  const container = document.getElementById('root'); requireAsset(container, 'binding', 'fixture root');
  const root = createRoot(container);
  try {
    const raw = await ky('/assets/steelworks/manifest.json', { retry: 0, timeout: 15_000, redirect: 'error' }).text();
    requireAsset(await sha256(new TextEncoder().encode(raw)) === manifestHash, 'hash', 'production manifest');
    const manifest = parseProductionAssetManifest(raw), asset = manifest.assets[0]; requireAsset(asset, 'binding', 'actual model');
    const fixed = representativePose(manifest, asset), registry = new AssetRegistry(raw, { origin: location.origin });
    registry.beginRun(fixed.pose.run_id, fixed.envelope.bundle_hash);
    root.render(<Viewer registry={registry} />);
  } catch (error) {
    if (!(error instanceof Error)) throw error;
    root.render(<main><style>{style}</style><h1>자산 검증 준비 오류</h1><p role="alert">{error.message}</p></main>);
  }
}
void start();
