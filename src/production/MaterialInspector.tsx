import { ArrowDown, ArrowRight, Boxes, CornerDownRight, GitBranch, Truck } from 'lucide-react';
import type { ProductionBatch, ProductionTransport, StageId } from './contracts';
import { mass, materialName, productNames, stageShortNames, statusNames, vehicleNames } from './presentation';

type Props = { readonly batch: ProductionBatch | undefined; readonly transport: ProductionTransport | undefined; readonly onStage: (id: StageId) => void };

export function MaterialInspector({ batch, transport, onStage }: Props) {
  if (!batch) return <aside className="production-inspector panel"><div className="empty-state"><Boxes size={32} /><h3>소재를 선택하세요</h3><p>작업 목록에서 소재의 경로와 변환 이력을 확인할 수 있습니다.</p></div></aside>;
  const nextStage = batch.route[batch.route.indexOf(batch.current_stage) + 1];
  return <aside className="production-inspector panel" aria-label="선택 소재 상세">
    <div className="production-panel-heading"><span><GitBranch size={16} />소재 추적</span><span className="production-code">{batch.id}</span></div>
    <div className="material-summary">
      <span className="eyebrow">CURRENT MATERIAL</span><h2>{materialName(batch.material_form)}</h2>
      <span className={`production-badge ${batch.material_role === 'sale_product' ? 'completed' : 'queued'}`}>{batch.material_role === 'sale_product' ? '판매 제품' : '후공정 소재'}</span>
      <div className="material-target"><CornerDownRight size={16} /><span>목표 제품</span><strong>{productNames[batch.product]}</strong></div>
      <div className="production-properties"><div><span>배치 질량</span><strong>{mass(batch.mass_kg)} t</strong></div><div><span>작업 상태</span><strong>{statusNames[batch.status]}</strong></div></div>
      {transport ? <div className="material-transport" aria-label="선택 소재 운송 정보"><div><Truck size={16} /><strong>{vehicleNames[transport.vehicle_kind]} · 운송 중</strong></div><code>{transport.vehicle_id}</code><p>현재 소재는 차량에 적재되어 있습니다.</p><button className="material-location" onClick={() => onStage(transport.from_stage)}><span>출발 공정 · {stageShortNames[transport.from_stage]}</span><ArrowRight size={15} /></button><button className="material-location" onClick={() => onStage(transport.to_stage)}><span>도착 공정 · {stageShortNames[transport.to_stage]}</span><ArrowRight size={15} /></button></div> : <><button className="material-location" onClick={() => onStage(batch.current_stage)}><span>현재 공정 · {stageShortNames[batch.current_stage]}</span><ArrowRight size={15} /></button>
      <p className="material-next">{nextStage ? `다음 공정 · ${stageShortNames[nextStage]}` : batch.status === 'completed' ? '생산 완료 · 출하 인계 대상' : '최종 제품 입고 진행'}</p></>}
    </div>
    <div className="material-history"><h3>소재 변환 이력 <span>{batch.material_history.length}</span></h3>
      <ol aria-label="소재 계보" tabIndex={0}>{batch.material_history.map((item, index) => <li key={item.id} className={item.id === batch.material_id ? 'current' : ''}>
        <div className="material-history-marker">{item.id === batch.material_id ? <Boxes size={14} /> : <span />}</div>
        <div><strong>{materialName(item.form)}</strong><span>{item.role === 'sale_product' ? '판매 제품' : '소재'} · {stageShortNames[item.stage_id]}</span><small>{item.id}</small></div>
        {index < batch.material_history.length - 1 && <ArrowDown className="material-history-arrow" size={12} />}
      </li>)}</ol>
    </div>
    <p className="production-inspector-note">형태와 용도는 별개입니다. 같은 열연·냉연 코일도 생산 경로에 따라 판매 제품 또는 다음 공정의 소재가 됩니다.</p>
  </aside>;
}
