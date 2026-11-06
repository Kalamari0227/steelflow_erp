import { useEffect, useRef, useState } from 'react';
import { fetchEventHistory } from '../api';
import type { MaterialView, Order, World } from '../contracts';
import { useNavigationStore, type OperationsSelection } from './navigation';
import { statusLabel, locationLabel, eventLabel } from './presentation';

export function WorkflowTimeline({ world, order, detail }: { readonly world: World; readonly order: Order | null; readonly detail: MaterialView | null }) {
  const { selection, select: selectNavigation, setLevel } = useNavigationStore();
  const select = (next: OperationsSelection): void => {
    const manifest = world.shipment_materials.filter(row => row.shipment_id === next.shipment_id);
    const materialId = manifest.some(row => row.material_id === next.material_id) ? next.material_id : manifest[0]?.material_id;
    selectNavigation({ ...next, material_id: materialId, stage_id: undefined, equipment_id: undefined });
    setLevel('overview');
  };
  const [history, setHistory] = useState<Awaited<ReturnType<typeof fetchEventHistory>> | null>(null);
  const [archiveRun, setArchiveRun] = useState('');
  const [historyError, setHistoryError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const mounted = useRef(true);
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; }; }, []);
  const loadHistory = async (): Promise<void> => {
    setLoading(true); setHistoryError(null);
    try { const rows = await fetchEventHistory(); if (mounted.current) setHistory(rows); }
    catch { if (mounted.current) setHistoryError('실행 이력을 불러오지 못했습니다. 다시 시도해 주세요.'); }
    finally { if (mounted.current) setLoading(false); }
  };
  const archivedEvents = history?.filter(event => event.run_id === archiveRun) ?? [];
  const shipments = world.shipments.filter(row => !order || row.order_id === order.id);
  const events = world.events.filter(row => !detail || row.material_id === detail.material.id || row.entity_id === detail.material.id);
  const selectedShipment = shipments.find(row => row.id === selection.shipment_id);
  return <section className="ops-workflow" aria-label="주문 이행과 이벤트"><div className="ops-panel-heading"><h2>주문 이행 · {order?.id ?? '전체 실행'}</h2><span>생산 → 품질 → 재고 → 출고 → 배송</span></div>
    {order && <div className="ops-fulfillment">{[['주문량', order.quantity_kg], ['생산 완료', order.produced_kg], ['출고 완료', order.dispatched_kg], ['배송 완료', order.delivered_kg], ['출고 잔량', order.remaining_dispatch_kg], ['배송 잔량', order.remaining_delivery_kg]].map(([label, value]) => <div key={label}><span>{label}</span><strong>{typeof value === 'number' ? value.toLocaleString('ko-KR') : value} <small>kg</small></strong></div>)}</div>}
    <div className="ops-workflow-grid"><div><h3>출하 연결</h3><div className="ops-shipment-list">{shipments.map(shipment => <button key={shipment.id} aria-pressed={selection.shipment_id === shipment.id} onClick={() => select({ ...selection, run_id: world.run.id, order_id: shipment.order_id, shipment_id: shipment.id })}><strong>{shipment.id}</strong><span>{shipment.mode === 'SEA' ? '해상' : '육상'} · {statusLabel(shipment.status)} ({shipment.status})</span><small>{locationLabel(shipment.location_id, world)}</small><small>{shipment.location_id}</small></button>)}</div>{shipments.length === 0 && <p className="ops-empty">아직 연결된 출하가 없습니다.</p>}{selectedShipment && <div className="ops-shipment-detail"><h3>{selectedShipment.id} 적재 명세</h3><p>출발 {selectedShipment.etd_at ?? '미확정'} · {selectedShipment.status === 'DELIVERED' ? `실제 도착 ${selectedShipment.delivered_at ?? '미확정'}` : `예상 도착 ${selectedShipment.eta_at ?? '미확정'}`} · UTC</p>{world.shipment_materials.filter(row => row.shipment_id === selectedShipment.id).map(row => <button key={row.id} onClick={() => select({ run_id: world.run.id, order_id: selectedShipment.order_id, shipment_id: selectedShipment.id, material_id: row.material_id })}>{row.material_id} · {selectedShipment.status === 'DELIVERED' ? '배송 완료 · 하역됨' : row.loaded ? '적재 확인' : selectedShipment.status === 'AT_PORT' ? '항만 대기 · 재적재 예정' : selectedShipment.status === 'IN_TRANSIT' || selectedShipment.status === 'DISPATCHED' ? '운송 인계 상태 확인' : '적재 대기'}</button>)}</div>}</div>
    <div><h3>현재 실행 이벤트</h3><ol className="ops-events">{[...events].reverse().slice(0, 80).map(event => <li key={event.id}><span>#{event.sequence}</span><div><strong>{eventLabel(event.event_type)}</strong>{eventLabel(event.event_type) !== event.event_type && <small>{event.event_type}</small>}<small>{event.entity_id}</small></div><time>{event.occurred_at.replace('T', ' ').replace('Z', '')} UTC</time></li>)}</ol>{events.length === 0 && <p className="ops-empty">선택한 소재의 이벤트가 아직 없습니다.</p>}</div></div>
    <div className="ops-archive"><div className="ops-panel-heading"><h3>보관된 실행 이력</h3><button className="secondary-button" disabled={loading} onClick={() => void loadHistory()}>{loading ? '이력 불러오는 중' : '실행 이력 불러오기'}</button></div>{historyError && <p role="alert" className="ops-warning">{historyError}</p>}{history && <><label>조회 실행 <select aria-label="보관 실행 선택" value={archiveRun} onChange={event => setArchiveRun(event.target.value)}><option value="">현재 실행으로 돌아가기</option>{[...new Set(history.map(event => event.run_id))].filter(id => id !== world.run.id).map(id => <option key={id} value={id}>{id}</option>)}</select></label>{archiveRun && <><p>보관 이력 조회 중 · 현재 운영 실행과 선택은 유지됩니다.</p><ol className="ops-events">{archivedEvents.map(event => <li key={event.id}><span>#{event.sequence}</span><div><strong>{eventLabel(event.event_type)}</strong>{eventLabel(event.event_type) !== event.event_type && <small>{event.event_type}</small>}<small>{event.entity_id}</small></div><time>{event.occurred_at} UTC</time></li>)}</ol></>}</>}</div>
  </section>;
}
