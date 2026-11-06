import { ArrowRight, Check, CircleDot, Truck } from 'lucide-react';
import type { ProductionBatch, ProductionStage, ProductionTransport, StageId } from './contracts';
import { phaseFor, stageShortNames, statusNames } from './presentation';

type RouteProps = { readonly batch: ProductionBatch; readonly transport: ProductionTransport | undefined; readonly activeStage: StageId | null; readonly onStage: (id: StageId) => void };
export function MaterialRoute({ batch, transport, activeStage, onStage }: RouteProps) {
  return <section className="production-route" aria-label="선택 배치 생산 경로"><div className="production-route-label"><span className="eyebrow">MATERIAL ROUTE</span><strong>{batch.id}</strong></div>
    <ol>{batch.route.map((id, index) => {
      const phase = phaseFor(batch, id);
      return <li key={id}><button aria-pressed={activeStage === id} className={`route-stop ${phase}`} onClick={() => onStage(id)}>{phase === 'completed' ? <Check size={12} /> : <CircleDot size={12} />}{stageShortNames[id]}<span className="sr-only"> · {statusNames[phase]}</span></button>{transport?.from_stage === id ? <span className="route-transport"><Truck size={15} aria-hidden="true" /><span className="sr-only">{stageShortNames[transport.to_stage]}까지 운송 중</span></span> : index < batch.route.length - 1 && <ArrowRight size={12} aria-hidden="true" />}</li>;
    })}</ol>
  </section>;
}

type StepProps = { stage: ProductionStage; batch: ProductionBatch | undefined; selectedStep: number | null; onStep: (index: number) => void; simulatedAt: string; tick: number };
export function StageSteps({ stage, batch, selectedStep, onStep, simulatedAt, tick }: StepProps) {
  const batchSteps = batch?.steps.filter(step => step.stage_id === stage.id) ?? [];
  const names = batchSteps.length > 0 ? batchSteps.map(step => step.name) : stage.substeps;
  const selected = selectedStep === null ? undefined : batchSteps[selectedStep];
  const clockTime = (step: number) => new Intl.DateTimeFormat('ko-KR', { timeZone: 'UTC', hour: '2-digit', minute: '2-digit', hourCycle: 'h23' }).format(new Date(Date.parse(simulatedAt) + (step - tick) * 30 * 60_000));
  return <section className="production-substeps" aria-label="공정 내부 작업 흐름">
    <div className="production-panel-heading"><h2>공정 내부 흐름</h2><span>{batchSteps.length ? batch?.id : '공정별 작업 종류'}</span></div>
    <ol>{names.map((name, index) => {
      const step = batchSteps[index];
      return <li key={name}><button aria-pressed={selectedStep === index} className={`substep-button ${step?.status ?? ''}`} onClick={() => onStep(index)}><span className="substep-index">{String(index + 1).padStart(2, '0')}</span><span><strong>{name}</strong><small>{step ? `${step.equipment_id} · ${statusNames[step.status]}` : '제품 경로에 따라 적용'}</small></span>{step?.status === 'completed' && <Check size={16} />}</button></li>;
    })}</ol>
    {selected && <p className="substep-detail" role="status">{selected.name} · 설비 {selected.equipment_id} · {statusNames[selected.status]} · 작업 구간 {clockTime(selected.start_tick)}–{clockTime(selected.end_tick)} UTC</p>}
  </section>;
}
