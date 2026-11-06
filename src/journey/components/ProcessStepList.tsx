import type { JourneySnapshot, ProductDefinition } from '../contracts';
import { stepStatus } from '../presentation';

type Props = {
  readonly product: ProductDefinition;
  readonly snapshot: JourneySnapshot;
  readonly focusedStepId: string | null;
  readonly onSelect: (id: string) => void;
};

export function ProcessStepList({ product, snapshot, focusedStepId, onSelect }: Props) {
  return <nav className="journey-step-list" aria-label="제품 제조 단계"><ol>{product.steps.map((step, index) => <li key={step.id}>
    <button aria-pressed={focusedStepId === step.id} aria-current={snapshot.active_step_id === step.id ? 'step' : undefined} onClick={() => onSelect(step.id)}>
      <span className="journey-step-number">{String(index + 1).padStart(2, '0')}</span><strong>{step.name}</strong><small>{stepStatus(product, snapshot, index)}</small>
    </button>
  </li>)}</ol></nav>;
}

export function JourneyTable({ product, snapshot, focusedStepId, onSelect }: Props) {
  return <div className="journey-table-wrap" role="region" aria-label="2D 제품 제조 공정" tabIndex={0}><table>
    <caption>{product.name} · 서버에서 확인한 공정 상태</caption>
    <thead><tr><th scope="col">공정</th><th scope="col">투입 소재</th><th scope="col">산출 소재</th><th scope="col">상태</th></tr></thead>
    <tbody>{product.steps.map((step, index) => <tr key={step.id} aria-current={snapshot.active_step_id === step.id ? 'step' : undefined}>
      <th scope="row"><button aria-pressed={focusedStepId === step.id} onClick={() => onSelect(step.id)}>{index + 1}. {step.name}</button></th><td>{step.input_form}</td><td>{step.output_form}</td><td>{stepStatus(product, snapshot, index)}</td>
    </tr>)}</tbody>
  </table><div className="journey-table-material"><strong>현재 소재: {snapshot.material.form}</strong><span>{snapshot.material.lineage_id} · {snapshot.material.mass_kg.toLocaleString('ko-KR')} kg</span><span>현재 위치: {snapshot.completed ? '제품 출고' : product.steps.find(step => step.id === snapshot.material.location_id)?.name ?? snapshot.material.location_id}</span></div></div>;
}
