import type { ProductionBatch, ProductionTransport, StageId } from './contracts';
import { mass, materialName, phaseFor, productNames, stageShortNames, statusNames } from './presentation';

type Props = { readonly batches: readonly ProductionBatch[]; readonly transports: readonly ProductionTransport[]; readonly stageId: StageId | null; readonly selectedId: string | null; readonly onSelect: (id: string) => void };

export function ProductionWorklist({ batches, transports, stageId, selectedId, onSelect }: Props) {
  return <section className="panel production-worklist" aria-label="생산 작업 목록">
    <div className="production-panel-heading"><h2>{stageId ? `${stageShortNames[stageId]} 작업 목록` : '전체 생산 배치'}</h2><span>{batches.length}개 배치 · {mass(batches.reduce((sum, batch) => sum + batch.mass_kg, 0))} t</span></div>
    <div className="production-table-scroll" role="region" aria-label="생산 소재 표" tabIndex={0}><table>
      <caption className="sr-only">합성 생산 배치. 배치 선택으로 경로와 소재 계보를 확인합니다.</caption>
      <thead><tr><th scope="col">생산 배치</th><th scope="col">현재 소재</th><th scope="col">용도</th><th scope="col">목표 제품</th><th scope="col">{stageId ? '이 공정 상태' : '현재 공정'}</th><th scope="col">질량</th><th scope="col">생산 진행</th></tr></thead>
      <tbody>{batches.map(batch => {
        const transport = transports.find(leg => leg.id === batch.active_transport_id);
        return <tr key={batch.id} className={selectedId === batch.id ? 'is-selected' : ''}>
        <td><button className="text-link" aria-pressed={selectedId === batch.id} onClick={() => onSelect(batch.id)}>{batch.id}</button></td>
        <td><strong>{materialName(batch.material_form)}</strong><small>{batch.material_id}</small></td>
        <td><span className={`production-badge ${batch.material_role === 'sale_product' ? 'completed' : 'queued'}`}>{batch.material_role === 'sale_product' ? '판매 제품' : '후공정 소재'}</span></td>
        <td>{productNames[batch.product]}</td>
        <td>{stageId ? <span className={`production-badge ${phaseFor(batch, stageId)}`}>{statusNames[phaseFor(batch, stageId)]}</span> : transport ? <span className="production-badge in_transit">운송 중</span> : stageShortNames[batch.current_stage]}{transport && <small>{stageShortNames[transport.from_stage]} → {stageShortNames[transport.to_stage]} · {transport.vehicle_id}</small>}</td>
        <td className="mono">{mass(batch.mass_kg)} t</td>
        <td><div className="production-completion"><span>{Math.round(batch.route_progress * 100)}%</span><progress aria-label={`${batch.id} 생산 진행률`} value={batch.route_progress} max={1} /></div></td>
      </tr>;})}</tbody>
    </table></div>
    {batches.length === 0 && <div className="production-empty">선택한 제품은 이 공정을 거치지 않습니다. 다른 제품 또는 전체 제품을 선택하세요.</div>}
    <div className="production-table-note">생산 전용 합성 배치 · 소재 변환 이력은 중복 재고로 합산하지 않습니다.</div>
  </section>;
}
