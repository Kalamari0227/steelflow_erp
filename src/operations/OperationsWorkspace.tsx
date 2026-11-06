import { useCallback, useEffect, useRef, useState, type ReactNode } from 'react';
import { Box, Factory, List, ChevronRight, Search, Layers, PanelLeft, ScanLine } from 'lucide-react';
import type { World } from '../contracts';
import { SimulationControls } from '../components/SimulationControls';
import { useWorldStore } from '../store';
import { useNavigationStore, type OperationsSelection } from './navigation';
import { selectMaterial } from './selectors';
import { formLabel, locationLabel, processLabel, statusLabel } from './presentation';
import { OrderNavigator } from './OrderNavigator';
import { MaterialInspector } from './MaterialInspector';
import { WorkflowTimeline } from './WorkflowTimeline';
import { RecoveryPanel } from './RecoveryPanel';
import { OperationsTable } from './OperationsTable';
import './operations.css';

export type OperationsSceneProps = { readonly world: World; readonly selectedMaterialId: string | null; readonly onFallback: () => void };
export type OperationsWorkspaceProps = { readonly world: World; readonly renderScene?: (props: OperationsSceneProps) => ReactNode };
const stageNames: Readonly<Record<string, string>> = { 'carbon-upstream': '제선·제강', 'casting-slab': '슬래브 주조', 'casting-bloom': '블룸 주조', 'casting-billet': '빌렛 주조', hr: '열연', plate: '후판', wire: '선재', cr: '냉연', gi: '용융아연', ga: '합금화아연', hgi: '열연도금', eg: '전기아연', go: '방향성 전기강판', ngo: '무방향성 전기강판', 'sts-hr': '스테인리스 열연', 'sts-cr': '스테인리스 냉연', 'sts-plate': '스테인리스 후판', 'ti-hr': '티타늄 열연', 'ti-cr': '티타늄 냉연', 'ti-sheet': '티타늄 박판', 'ti-plate': '티타늄 후판', 'hot-rolling-reserve': '열연 예비 설비', logistics: '검사·재고·출하', sources: '원료 공급', ironmaking: '제선' };

export function OperationsWorkspace({ world, renderScene }: OperationsWorkspaceProps) {
  const { selection, level, view, issue, followMaterial, select: selectNavigation, setLevel, setView, setFollowMaterial } = useNavigationStore();
  const select = (next: OperationsSelection): void => { selectNavigation(next); setLevel('overview'); };
  const { stale, error, receivedAt, refresh } = useWorldStore();
  const [sceneUnavailable, setSceneUnavailable] = useState(false);
  const [stageQuery, setStageQuery] = useState('');
  const [ordersOpen, setOrdersOpen] = useState(() => typeof window === 'undefined' || window.innerWidth > 760);
  const [inspectorOpen, setInspectorOpen] = useState(() => typeof window === 'undefined' || window.innerWidth > 760);
  useEffect(() => {
    if (selection.material_id && window.innerWidth <= 760) { setInspectorOpen(true); setOrdersOpen(false); }
  }, [selection.material_id]);
  useEffect(() => {
    let compact = window.innerWidth <= 760;
    const onResize = (): void => {
      const nextCompact = window.innerWidth <= 760;
      if (nextCompact && !compact) { setOrdersOpen(false); setInspectorOpen(false); }
      compact = nextCompact;
    };
    window.addEventListener('resize', onResize);
    return () => window.removeEventListener('resize', onResize);
  }, []);
  const fallbackNotice = useRef<HTMLParagraphElement>(null);
  const onSceneFallback = useCallback(() => { setSceneUnavailable(true); setView('2d'); }, [setView]);
  useEffect(() => { if (sceneUnavailable && view === '2d') fallbackNotice.current?.focus(); }, [sceneUnavailable, view]);
  const detail = selection.material_id ? selectMaterial(world, selection.material_id) : null;
  const order = world.orders.find(row => row.id === selection.order_id) ?? detail?.order;
  const materials = order ? world.materials.filter(material => world.lots.some(lot => lot.id === material.lot_id && lot.order_id === order.id)) : world.materials;
  const pickMaterial = (id: string): void => {
    const linked = selectMaterial(world, id);
    const next = { run_id: world.run.id, order_id: linked?.order.id, material_id: id };
    if (linked?.order.id === selection.order_id) {
      const shipmentId = world.shipment_materials.some(row => row.shipment_id === selection.shipment_id && row.material_id === id) ? selection.shipment_id : undefined;
      selectNavigation({ ...selection, ...next, shipment_id: shipmentId });
    } else select(next);
  };
  const processes = detail?.processes ?? world.processes;
  const stage = world.production.stages.find(row => row.id === selection.stage_id);
  const visibleProcesses = processes.filter(process => level === 'overview' || (level === 'equipment' ? process.equipment_id === selection.equipment_id : stage?.process_ids.includes(process.id)));
  const matchingStages = world.production.stages.filter(row => `${stageNames[row.id] ?? row.id} ${row.id}`.toLowerCase().includes(stageQuery.trim().toLowerCase()));
  return <div className="ops-workspace" data-testid="operations-workspace">
    <div className="ops-hud">
      <div className="ops-heading"><Factory size={17} aria-hidden="true" /><h1>통합 운영</h1><span className="ops-live-state" data-playing={world.run.playing && !stale}>{stale ? '마지막 확인 상태' : world.run.playing ? '실행 중' : '일시 정지'}</span></div>
      <section className="ops-kpis" aria-label="전체 운영 지표">{[['진행 주문', world.kpis.active_orders, '건'], ['생산', world.kpis.produced_kg, 'kg'], ['출고', world.kpis.dispatched_kg, 'kg'], ['배송', world.kpis.delivered_kg, 'kg']].map(([label, value, unit]) => <div key={label}><span>{label}</span><strong>{typeof value === 'number' ? value.toLocaleString('ko-KR') : value}<small>{unit}</small></strong></div>)}</section>
      <div className="ops-run"><time title="서버 시뮬레이션 시간">{world.simulation.simulated_at.replace('T', ' ').replace(/(?:Z|\+00:00)$/, '')} UTC</time><details><summary>실행 정보</summary><small data-testid="current-run">{world.run.id} · rev {world.run.revision}</small><small>{receivedAt === null ? '수신 시각 없음' : `수신 ${new Date(receivedAt).toISOString()}`}</small></details></div>
      <SimulationControls />
    </div>
    {(error || stale) && <div className="ops-warning" role="alert"><strong>연결 상태 확인 필요</strong><span>{error ?? '서버 응답을 기다리는 중입니다.'} {receivedAt !== null && `마지막 수신 ${new Date(receivedAt).toISOString()}`}</span><button onClick={() => void refresh()}>다시 연결</button></div>}
    {issue && <div className="ops-warning" role="alert">{issue.message}<button onClick={() => { select({ run_id: world.run.id }); setLevel('overview'); }}>전체로 돌아가기</button></div>}
    <div className={`ops-grid ${view === '2d' || !renderScene ? 'ops-grid-2d' : ''}`}>
      <section className="ops-main-panel" aria-label="공장 운영">
        <div className="ops-scene-navigation">
          <nav className="ops-breadcrumb" aria-label="공장 탐색 경로"><button onClick={() => setLevel('overview')}><Factory size={14} />공장 전경</button>{level !== 'overview' && <><ChevronRight size={12} /><button onClick={() => setLevel('stage')}>{stageNames[selection.stage_id ?? ''] ?? selection.stage_id ?? '공정'}</button></>}{level === 'equipment' && <><ChevronRight size={12} /><span>{selection.equipment_id}</span></>}</nav>
          <details className="ops-stage-picker"><summary><Layers size={14} />공정 선택</summary><div className="ops-stage-popover"><label className="ops-search"><Search size={14} /><input aria-label="공정 검색" placeholder="공정명 검색" value={stageQuery} onChange={event => setStageQuery(event.target.value)} /></label><div className="ops-stage-strip" aria-label="공정 선택">{matchingStages.map(row => <button key={row.id} aria-pressed={level === 'stage' && selection.stage_id === row.id} onClick={event => { select({ ...selection, run_id: world.run.id, stage_id: row.id, equipment_id: undefined }); setLevel('stage'); event.currentTarget.closest('details')?.removeAttribute('open'); }}>{stageNames[row.id] ?? row.id}</button>)}</div>{matchingStages.length === 0 && <p className="ops-empty">일치하는 공정이 없습니다.</p>}</div></details>
          <label className="ops-follow"><input type="checkbox" checked={followMaterial} onChange={event => setFollowMaterial(event.target.checked)} /><ScanLine size={14} />소재 따라가기</label>
          <div className="ops-view-switch"><button aria-pressed={view === '3d'} onClick={() => setView('3d')}><Box size={14} />3D</button><button aria-pressed={view === '2d'} onClick={() => setView('2d')}><List size={14} />2D</button></div>
        </div>
        {sceneUnavailable && view === '2d' && <p className="ops-fallback-notice" role="status" tabIndex={-1} ref={fallbackNotice}>3D 장면을 사용할 수 없어 2D 운영 자료로 전환했습니다. 선택한 주문과 소재는 그대로 유지됩니다.</p>}
        {view === '3d' && renderScene ? <div className="ops-scene" data-testid="operations-scene">{renderScene({ world, selectedMaterialId: detail?.material.id ?? null, onFallback: onSceneFallback })}</div> : <OperationsTable world={world} processIds={visibleProcesses.map(process => process.id)} />}
      </section>
      <details className="ops-side-panel ops-orders-panel" open={ordersOpen} onToggle={event => { const expanded = event.currentTarget.open; setOrdersOpen(expanded); if (expanded && window.innerWidth <= 760) setInspectorOpen(false); }}><summary><PanelLeft size={14} />주문 탐색 <span>{world.orders.length}건</span></summary><OrderNavigator world={world} /></details>
      <details className="ops-side-panel ops-inspector-panel" open={inspectorOpen} onToggle={event => { const expanded = event.currentTarget.open; setInspectorOpen(expanded); if (expanded && window.innerWidth <= 760) setOrdersOpen(false); }}><summary><Box size={14} />선택 소재 <span>{detail ? '여권' : '선택 대기'}</span></summary><MaterialInspector detail={detail} world={world} /></details>
      <section className="ops-materials" aria-label="소재와 공정 경로"><div className="ops-material-context"><span className="eyebrow">MATERIAL JOURNEY</span><strong>{detail?.material.id ?? order?.id ?? '전체 소재'}</strong><span>{detail ? locationLabel(detail.material.location_id, world) : '주문 또는 소재를 선택하세요'}</span></div><div className="ops-material-track">{detail && <nav className="ops-journey" aria-label="선택 소재 공정 경로">{detail.processes.map(process => <button key={process.id} data-status={process.status} title={`${processLabel(process.source_step_id)} · ${statusLabel(process.status)}`} onClick={() => { const nextStage = world.production.stages.find(row => row.process_ids.includes(process.id)); selectNavigation({ ...selection, stage_id: nextStage?.id, equipment_id: process.equipment_id }); setLevel('equipment'); }}><span>{processLabel(process.source_step_id)}</span><small>{statusLabel(process.status)}</small><ChevronRight size={12} /></button>)}</nav>}<div className="ops-material-list">{materials.map(material => <button key={material.id} data-testid={`material-${material.id}`} aria-pressed={selection.material_id === material.id} onClick={() => pickMaterial(material.id)}><strong>{material.id}</strong><span>{formLabel(material.form)}</span><small>{material.active ? locationLabel(material.location_id, world) : '분할·소비된 부모'} · {material.weight_kg.toLocaleString('ko-KR')} kg</small></button>)}</div></div><a className="ops-records-link" href="#operations-records">운영 자료<ChevronRight size={14} /></a></section>
    </div>
    <details className="ops-records" id="operations-records" open><summary><List size={16} />운영 자료 · 납기 / 출하 / 이벤트 <span>펼치기·접기</span></summary><RecoveryPanel world={world} orderId={order?.id ?? null} /><WorkflowTimeline world={world} order={order ?? null} detail={detail} /></details>
    <footer className="ops-footer"><span>하나의 실행 · 서버 기준 시간 · kg / UTC</span><span>AI {world.ai.enabled && world.ai.available ? '연결됨' : '미사용'} · 핵심 운영 독립 실행</span></footer>
  </div>;
}
