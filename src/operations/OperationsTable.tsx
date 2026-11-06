import { useLayoutEffect, useRef, useState } from 'react';
import type { World } from '../contracts';
import { useNavigationStore, type OperationsSelection } from './navigation';
import { statusLabel, formLabel, locationLabel, processLabel, equipmentLabel, reasonLabel } from './presentation';

const sections = ['주문', '소재', '공정', '운송', '검사', '출하'] as const;
type Section = typeof sections[number];
type RecordRow = { readonly id: string; readonly label: string; readonly status: string; readonly location: string; readonly quantity: string; readonly description: string; readonly selection: OperationsSelection; readonly equipment: boolean };
const kg = (value: number): string => `${value.toLocaleString('ko-KR')} kg`;

export function OperationsTable({ world, processIds }: { readonly world: World; readonly processIds?: readonly string[] }) {
  const { selection, select, setLevel } = useNavigationStore();
  const [section, setSection] = useState<Section>('공정');
  const [recordId, setRecordId] = useState<string | null>(null);
  const recordRef = useRef<HTMLElement>(null);
  const materialSelection = (id: string): OperationsSelection => {
    const material = world.materials.find(row => row.id === id);
    const lot = world.lots.find(row => row.id === material?.lot_id);
    return { run_id: world.run.id, order_id: lot?.order_id, material_id: id };
  };
  const locationName = (id: string): string => locationLabel(id, world);
  const included = (materialId: string): boolean => selection.material_id ? materialId === selection.material_id : !selection.order_id || materialSelection(materialId).order_id === selection.order_id;
  const weight = (materialId: string): string => { const material = world.materials.find(row => row.id === materialId); return material ? kg(material.weight_kg) : '소재 확인 필요'; };
  const processSelection = (id: string, materialId: string, equipmentId: string): OperationsSelection => ({ ...materialSelection(materialId), equipment_id: equipmentId, stage_id: world.production.stages.find(row => row.process_ids.some(processId => processId === id))?.id });
  const rows: readonly RecordRow[] = (() => {
    switch (section) {
      case '주문': return world.orders.map(row => ({ id: row.id, label: row.id, status: row.status, location: world.customers.find(customer => customer.id === row.customer_id)?.name ?? row.customer_id, quantity: kg(row.quantity_kg), description: `출고 잔량 ${kg(row.remaining_dispatch_kg)} · 배송 잔량 ${kg(row.remaining_delivery_kg)}`, selection: { run_id: world.run.id, order_id: row.id, material_id: row.material_ids.find(id => world.materials.some(material => material.id === id && material.active)) ?? row.material_ids[0] }, equipment: false }));
      case '소재': return world.materials.filter(row => !selection.order_id || materialSelection(row.id).order_id === selection.order_id).map(row => ({ id: row.id, label: row.id, status: row.availability_status, location: locationName(row.location_id), quantity: kg(row.weight_kg), description: `${formLabel(row.form)} (${row.form}) · ${row.active ? '현재 소재' : '소비된 부모 · 현재 재고에서 제외'} · 품질 ${statusLabel(row.quality_status)} (${row.quality_status})`, selection: materialSelection(row.id), equipment: false }));
      case '공정': return world.processes.filter(row => included(row.material_id) && (!processIds || processIds.includes(row.id))).map(row => ({ id: row.id, label: `${row.step_ordinal + 1}. ${processLabel(row.source_step_id)}`, status: row.status, location: `${equipmentLabel(row.equipment_id)} (${row.equipment_id})`, quantity: weight(row.material_id), description: `${row.material_id} · ${formLabel(row.input_form)} → ${formLabel(row.output_form)} · ${row.source_step_id}${row.blocked_reason ? ` · ${reasonLabel(row.blocked_reason)} (${row.blocked_reason})` : ''}`, selection: processSelection(row.id, row.material_id, row.equipment_id), equipment: true }));
      case '운송': return world.transfers.filter(row => included(row.material_id)).map(row => { const process = world.processes.find(item => item.id === row.process_id); return { id: row.id, label: `소재 운송 · ${row.material_id}`, status: row.status, location: `${locationName(row.from_location_id)} → ${locationName(row.to_location_id)}`, quantity: weight(row.material_id), description: `${row.material_id} · ${row.vehicle_id ? `${equipmentLabel(row.vehicle_id)} (${row.vehicle_id})` : '롤러 이송'} · 현재 위치 ${locationName(world.materials.find(item => item.id === row.material_id)?.location_id ?? row.from_location_id)}`, selection: process ? processSelection(process.id, row.material_id, process.equipment_id) : materialSelection(row.material_id), equipment: Boolean(process) }; });
      case '검사': return world.inspections.filter(row => included(row.material_id)).map(row => ({ id: row.id, label: `제품 검사 · ${row.material_id}`, status: row.status, location: locationName(world.materials.find(item => item.id === row.material_id)?.location_id ?? ''), quantity: weight(row.material_id), description: `${row.material_id} · 검사 대상 버전 ${row.inspected_version_id}${row.reason ? ` · ${reasonLabel(row.reason)} (${row.reason})` : ''}`, selection: materialSelection(row.material_id), equipment: false }));
      case '출하': return world.shipments.filter(row => !selection.order_id || row.order_id === selection.order_id).map(row => { const members = world.shipment_materials.filter(item => item.shipment_id === row.id && item.active); const order = world.orders.find(item => item.id === row.order_id); return { id: row.id, label: row.id, status: row.status, location: locationName(row.location_id), quantity: kg(members.reduce((sum, item) => sum + (world.materials.find(material => material.id === item.material_id)?.weight_kg ?? 0), 0)), description: `${row.mode === 'SEA' ? '해상' : '육상'} · ${members.map(item => item.material_id).join(', ') || '소재 배정 전'} · 주문 출고 잔량 ${kg(order?.remaining_dispatch_kg ?? 0)} · 배송 잔량 ${kg(order?.remaining_delivery_kg ?? 0)}`, selection: { run_id: world.run.id, order_id: row.order_id, material_id: members[0]?.material_id, shipment_id: row.id }, equipment: false }; });
      default: { const exhaustive: never = section; return exhaustive; }
    }
  })();
  const selectedRecord = rows.find(row => row.id === recordId);
  const selectedRecordId = selectedRecord?.id;
  useLayoutEffect(() => { if (selectedRecordId) recordRef.current?.focus(); }, [selectedRecordId, section]);
  const openRecord = (row: RecordRow): void => { setRecordId(row.id); select(row.selection); setLevel(row.equipment ? 'equipment' : 'overview'); if (row.id === recordId) recordRef.current?.focus(); };
  return <section className="ops-table-view" aria-label="2D 운영 자료" data-testid="operations-table">
    <div className="ops-table-sections" aria-label="운영 자료 종류">{sections.map(name => <button key={name} aria-pressed={section === name} onClick={() => { setSection(name); setRecordId(null); }}>{name}</button>)}</div>
    <div className="ops-table-context"><span>{selection.order_id ?? '전체 주문'}{selection.material_id && ` · ${selection.material_id}`}</span><span>{rows.length}건</span></div>
    <div className="ops-table-scroll" role="region" aria-label={`${section} 표 스크롤`} tabIndex={0}><table><caption>{section} 운영 현황</caption><thead><tr><th scope="col">대상</th><th scope="col">상태</th><th scope="col">위치 / 연결</th><th scope="col">중량</th></tr></thead><tbody>{rows.map(row => <tr key={row.id} data-selected={row.id === recordId}><th scope="row"><button data-testid={section === '공정' ? `process-${row.id}` : `table-${section}-${row.id}`} aria-label={`${section} ${row.id} 상세`} aria-pressed={row.id === recordId} onClick={() => openRecord(row)}>{row.label}</button></th><td>{statusLabel(row.status)}<small className="ops-code">{row.status}</small></td><td>{row.location}</td><td>{row.quantity}</td></tr>)}</tbody></table>{rows.length === 0 && <p className="ops-empty">선택한 대상의 {section} 기록이 아직 없습니다.</p>}</div>
    {selectedRecord && <section className="ops-table-detail" aria-label={`${section} 선택 기록`} tabIndex={-1} ref={recordRef}><h3>{section} 선택 기록</h3><small className="ops-code">{selectedRecord.id}</small><p>{statusLabel(selectedRecord.status)} ({selectedRecord.status}) · {selectedRecord.quantity}</p><p>{selectedRecord.description}</p><p>{selectedRecord.location}</p></section>}
  </section>;
}
