import { useEffect, useState } from 'react';
import { Pause, Play, RotateCcw, SkipForward } from 'lucide-react';
import { getFactoryMaterial } from '../api';
import { ScenarioIdSchema } from '../contracts';
import { useWorldStore } from '../store';
import type { FactoryMaterialDetail, FactoryWorld } from './contractsV3';
import { useNavigationStore } from './navigation';
import type { OperationsSelection } from './navigation';
import './FactoryWorkspace.css';

type Select = (type: NonNullable<OperationsSelection['entity_type']>, id: string) => void;
const kg = (value: number) => `${value.toLocaleString('ko-KR')} kg`;

function MaterialDetail({ world, id, select }: { readonly world: FactoryWorld; readonly id: string; readonly select: Select }) {
  const [result, setResult] = useState<{ readonly detail: FactoryMaterialDetail | null; readonly error: string | null }>({ detail: null, error: null });
  useEffect(() => {
    let ignore = false;
    void getFactoryMaterial(id).then(detail => {
      if (!ignore) setResult(detail.run_id === world.run.id && detail.material.id === id && detail.revision >= world.run.revision
        ? { detail, error: null } : { detail: null, error: '소재 응답의 실행 또는 리비전이 변경되었습니다. 현재 상태를 다시 확인합니다.' });
    }).catch((error: unknown) => {
      if (!(error instanceof Error)) throw error;
      if (!ignore) setResult({ detail: null, error: '소재 상세를 확인하지 못했습니다. 현재 실행 연결을 확인해 주세요.' });
    });
    return () => { ignore = true; };
  }, [id, world.run.id, world.run.revision]);
  const detail = result.detail;
  if (result.error) return <p role="alert">{result.error}</p>;
  if (!detail || detail.material.id !== id || detail.run_id !== world.run.id || detail.revision < world.run.revision) return <p role="status">소재 상세를 확인하는 중입니다.</p>;
  const material = detail.material;
  const orderId = detail.order?.id;
  const stockId = detail.origin_stock_lot?.id;
  const attachmentId = detail.current_attachment?.id;
  return <section aria-label="소재 상세">
    <h2>{material.id}</h2><p>{material.grade} · {material.form} · {kg(material.weight_kg)}</p>
    <dl className="factory-fields">
      <dt>주문</dt><dd>{orderId ? <button onClick={() => select('order', orderId)}>{orderId}</button> : '없음 (null)'}</dd>
      <dt>생산 로트</dt><dd>{detail.production_lot?.id ?? '없음 (null)'}</dd>
      <dt>작업 지시</dt><dd>{detail.work_order?.id ?? '없음 (null)'}</dd>
      <dt>원재고 로트</dt><dd>{stockId ? <button onClick={() => select('stock_lot', stockId)}>{stockId}</button> : '없음 (null)'}</dd>
      <dt>품질 / 가용성</dt><dd>{material.quality_status} / {material.availability_status}</dd>
      <dt>치수 (mm)</dt><dd>{Object.entries(material.dimensions).map(([key, value]) => <span className="factory-value" key={key}>{key}: {value ?? '없음'}</span>)}</dd>
      <dt>현재 보관 위치</dt><dd>{detail.current_attachment && attachmentId ? <button onClick={() => select('attachment', attachmentId)}>{detail.current_attachment.kind} · {detail.current_attachment.owner_id} / {detail.current_attachment.socket_id}</button> : '없음 (null)'}</dd>
      <dt>현재 운송 작업</dt><dd>{detail.current_job ? `${detail.current_job.id} · ${detail.current_job.status} · ${detail.current_job.from_node_id} → ${detail.current_job.to_node_id} · ${detail.current_job.fleet_id ?? detail.current_job.equipment_id ?? '운반 자원 없음'}` : '없음 (null)'}</dd>
    </dl>
    <h3>연결된 배치</h3><div className="factory-links">{detail.process_batches.map(batch => <button key={batch.id} onClick={() => select('batch', batch.id)}>{batch.id} · {batch.status}</button>)}{!detail.process_batches.length && <p>연결된 배치 없음</p>}</div>
    <h3>소재 계보</h3><ul>{detail.version_edges.map(edge => {
      const input = detail.versions.find(row => row.id === edge.input_version_id);
      const output = detail.versions.find(row => row.id === edge.output_version_id);
      return <li key={edge.id}>{input ? <button onClick={() => select('material', input.material_id)}>{input.material_id}</button> : edge.input_version_id} → {output ? <button onClick={() => select('material', output.material_id)}>{output.material_id}</button> : edge.output_version_id} · {kg(edge.transferred_kg)}</li>;
    })}</ul>{!detail.version_edges.length && <p>연결된 계보 없음</p>}
    <h3>출하 구간</h3>{detail.shipment_legs.map(leg => <p key={leg.id}>{leg.id} · {leg.mode} · {leg.status} · {leg.from_node_id} → {leg.to_node_id}</p>)}{!detail.shipment_legs.length && <p>연결된 출하 구간 없음</p>}
    <small>상세 응답 리비전 {detail.revision}</small>
  </section>;
}

export function FactoryWorkspace({ world }: { readonly world: FactoryWorld }) {
  const { busy, stale, error, receivedAt, command, refresh, appliedRevision, appliedRunId, replayed } = useWorldStore();
  const { selection, issue, select: navigate } = useNavigationStore();
  const select: Select = (entity_type, entity_id) => navigate({ run_id: world.run.id, bundle_hash: world.run.bundle_hash, entity_type, entity_id });
  const disabled = busy || stale;
  const run = world.run;
  const complete = run.elapsed_ms >= run.duration_ms;
  const batch = selection.entity_type === 'batch' ? world.process_batches.find(row => row.id === selection.entity_id) : undefined;
  const stock = selection.entity_type === 'stock_lot' ? world.stock_lots.find(row => row.id === selection.entity_id) : undefined;
  const attachment = selection.entity_type === 'attachment' ? world.attachments.find(row => row.id === selection.entity_id) : undefined;
  const order = selection.entity_type === 'order' ? world.orders.find(row => row.id === selection.entity_id) : undefined;
  return <div className="ops-workspace factory-workspace">
    <div className="ops-heading"><div><h1>소재·재고 조회</h1><p>{run.profile === 'v3_contract_test' ? '계약 검증용 실행 · 제어 메커니즘과 저장된 관계를 확인합니다.' : '확인된 공장 실행 상태'} 전체 공장 시뮬레이션 화면은 준비 중입니다.</p></div><div className="ops-run"><span data-testid="factory-run">{run.id}</span><small data-testid="factory-revision">리비전 {run.revision} · {run.elapsed_ms} ms</small><details><summary>번들 정보</summary>{run.bundle_id}<small>{run.bundle_hash}</small></details></div></div>
    {(error || stale) && <div className="ops-warning" role="alert"><span>{error ?? '연결 확인 중입니다.'} 마지막 수신: {receivedAt === null ? '없음' : new Date(receivedAt).toISOString()}</span><button onClick={() => void refresh()}>다시 연결</button></div>}
    {issue && <p role="status">{issue.message}</p>}
    <div className="ops-controls" aria-label="공통 실행 제어">
      <button disabled={disabled || (!run.playing && complete)} onClick={() => void command({ action: run.playing ? 'pause' : 'play' })}>{run.playing ? <Pause size={16} /> : <Play size={16} />}{run.playing ? '일시 정지' : '재생'}</button>
      <button disabled={disabled || run.playing || complete} onClick={() => void command({ action: 'step' })}><SkipForward size={16} />한 단계</button>
      <button disabled={disabled} onClick={() => void command({ action: 'reset' })}><RotateCcw size={16} />초기화</button>
      <label>속도 <select aria-label="실행 속도" disabled={disabled} value={run.speed} onChange={event => { const speed = Number(event.target.value); if (speed === 1 || speed === 2 || speed === 4) void command({ action: 'speed', speed }); }}><option value={1}>1×</option><option value={2}>2×</option><option value={4}>4×</option></select></label>
      <label>시나리오 <select aria-label="시나리오" disabled={disabled} value={run.scenario_id} onChange={event => void command({ action: 'scenario', scenario: ScenarioIdSchema.parse(event.target.value) })}><option value="NORMAL">NORMAL · 제어 검증</option><option value="DELAY">DELAY · 제어 검증</option><option value="RECOVERY">RECOVERY · 제어 검증</option></select></label>
      <span className="ops-control-note">초기화·시나리오 변경은 새 실행을 만듭니다.</span>
    </div>
    {appliedRevision !== null && <p className="factory-receipt" role="status">명령 영수증: {appliedRunId} / 리비전 {appliedRevision}{replayed ? ' · 재전송 결과' : ''}</p>}
    <div className="ops-kpis"><div><span>활성 소재</span><strong>{world.kpis.active_material_count}</strong></div><div><span>활성 질량</span><strong>{kg(world.kpis.active_kg)}</strong></div><div><span>가용 재고</span><strong>{kg(world.kpis.available_kg)}</strong></div><div><span>할당 질량</span><strong>{kg(world.kpis.allocated_kg)}</strong></div></div>
    <div className="factory-grid"><section className="ops-main-panel" aria-label="소재 목록"><div className="ops-panel-heading"><h2>전체 소재</h2><span>소비된 소재 포함 · {world.materials.length}개</span></div><div className="ops-table-scroll" tabIndex={0} aria-label="소재 표"><table><thead><tr><th>소재</th><th>강종 / 형태</th><th>질량</th><th>상태</th></tr></thead><tbody>{world.materials.map(material => <tr key={material.id} data-selected={selection.entity_type === 'material' && selection.entity_id === material.id}><th><button onClick={() => select('material', material.id)}>{material.id}</button></th><td>{material.grade}<br />{material.form}</td><td>{kg(material.weight_kg)}</td><td>{material.active ? '활성' : '소비됨'} · {material.availability_status}</td></tr>)}</tbody></table></div><div className="factory-links" aria-label="재고 로트">{world.stock_lots.map(row => <button key={row.id} onClick={() => select('stock_lot', row.id)}>재고 {row.id}</button>)}</div><div className="factory-links" aria-label="배치 목록">{world.process_batches.map(row => <button key={row.id} onClick={() => select('batch', row.id)}>배치 {row.id}</button>)}</div></section>
      <aside className="factory-detail" aria-label="선택 상세">
        {!selection.entity_id && <p>소재를 선택하면 주문 연결, 보관 위치와 배치 계보를 확인할 수 있습니다.</p>}
        {selection.entity_type === 'material' && selection.entity_id && <MaterialDetail world={world} id={selection.entity_id} select={select} />}
        {batch && <section><h2>배치 {batch.id}</h2><p>{batch.recipe_id} · {batch.status}</p><h3>실제 입출력</h3><ul>{world.batch_io.filter(row => row.batch_id === batch.id).map(row => {
          const version = world.material_versions.find(v => v.id === row.material_version_id);
          return <li key={row.id}>{row.role} · {kg(row.quantity_kg)} · {version ? <button onClick={() => select('material', version.material_id)}>{version.material_id} ({version.id})</button> : row.source_id ?? '소재 버전 없음'}</li>;
        })}</ul></section>}
        {stock && <section><h2>재고 {stock.id}</h2><p>{stock.grade} · {stock.form} · {kg(stock.quantity_kg)} · {stock.source_kind}</p><div className="factory-links">{world.materials.filter(row => row.origin_stock_lot_id === stock.id).map(row => <button key={row.id} onClick={() => select('material', row.id)}>{row.id}</button>)}</div></section>}
        {attachment && <section><h2>보관 {attachment.id}</h2><p>{attachment.kind} · {attachment.owner_id} / {attachment.socket_id}</p><p>{attachment.released_at_ms === null ? '현재 보관 중' : `해제 ${attachment.released_at_ms} ms`}</p><button onClick={() => select('material', attachment.material_id)}>{attachment.material_id}</button></section>}
        {order && <section><h2>주문 {order.id}</h2><p>고객 ID: {order.customer_id}</p><p>{order.grade} · {kg(order.quantity_kg)}</p><div className="factory-links">{world.allocations.filter(row => row.order_id === order.id).map(row => <button key={row.id} onClick={() => select('material', row.material_id)}>{row.material_id} · {row.active ? '현재 할당' : '과거 할당'}</button>)}</div></section>}
      </aside></div>
  </div>;
}
