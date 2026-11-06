import { useState } from 'react';
import { ArrowRight, Truck } from 'lucide-react';
import type { ProductionTransport, StageId } from './contracts';
import { mass, materialName, stageShortNames, vehicleNames } from './presentation';

type Props = {
  readonly transports: readonly ProductionTransport[];
  readonly selectedId: string | null;
  readonly onSelect: (batchId: string) => void;
  readonly onStage: (id: StageId) => void;
};
const transportStatuses = { queued: '운송 예정', in_transit: '운송 중', completed: '도착 완료' };

export function TransportList({ transports, selectedId, onSelect, onStage }: Props) {
  const [mode, setMode] = useState<'active' | 'batch'>('active');
  const active = transports.filter(leg => leg.status === 'in_transit');
  const rows = mode === 'active' ? active : transports.filter(leg => leg.batch_id === selectedId);
  return <section className="panel production-worklist production-transports" aria-label="공정 간 운송">
    <div className="production-panel-heading"><h2><Truck size={16} />공정 간 운송</h2><span>운송 중 {active.length}대 · {mass(active.reduce((total, leg) => total + leg.mass_kg, 0))} t</span></div>
    <div className="transport-toolbar"><div className="view-toggle"><button aria-pressed={mode === 'active'} onClick={() => setMode('active')}>운송 중</button><button aria-pressed={mode === 'batch'} onClick={() => setMode('batch')}>선택 배치 경로</button></div><span>차량을 선택해 적재 소재를 추적하세요</span></div>
    <div className="production-table-scroll" role="region" aria-label="생산 운송 표" tabIndex={0}><table>
      <caption className="sr-only">공정 간 소재 운송. 현재 차량, 화물, 출발지와 도착지를 확인합니다.</caption>
      <thead><tr><th scope="col">운반 차량</th><th scope="col">적재 소재</th><th scope="col">운송 경로</th><th scope="col">질량</th><th scope="col">상태</th></tr></thead>
      <tbody>{rows.map(leg => <tr key={leg.id} className={selectedId === leg.batch_id ? 'is-selected' : ''}>
        <td><button className="text-link" aria-label={`${leg.vehicle_id} 적재 소재 선택`} aria-pressed={selectedId === leg.batch_id} onClick={() => onSelect(leg.batch_id)}>{vehicleNames[leg.vehicle_kind]}</button><small>{leg.vehicle_id}</small></td>
        <td><strong>{materialName(leg.material_form)}{leg.status === 'queued' && ' · 적재 예정'}</strong><small>{leg.batch_id} · {leg.material_id}</small></td>
        <td><div className="transport-route"><button onClick={() => onStage(leg.from_stage)} aria-label={`${leg.id} 출발 ${stageShortNames[leg.from_stage]}`}>{stageShortNames[leg.from_stage]}</button><ArrowRight size={12} aria-hidden="true" /><button onClick={() => onStage(leg.to_stage)} aria-label={`${leg.id} 도착 ${stageShortNames[leg.to_stage]}`}>{stageShortNames[leg.to_stage]}</button></div></td>
        <td>{mass(leg.mass_kg)} t</td><td><span className={`production-badge ${leg.status}`}>{transportStatuses[leg.status]}</span></td>
      </tr>)}</tbody>
    </table></div>
    {rows.length === 0 && <p className="production-empty">{mode === 'active' ? '현재 운송 중인 차량이 없습니다. 다음 공정으로 이동할 때 운송 상태가 표시됩니다.' : '이 공정과 연결된 선택 배치의 운송 경로가 없습니다.'}</p>}
    <p className="production-table-note">공정 간 이동은 서버가 관리합니다. 도착이 확인된 뒤 다음 작업을 시작합니다.</p>
  </section>;
}
