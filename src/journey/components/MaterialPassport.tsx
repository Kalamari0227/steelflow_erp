import { ArrowRight, Package } from 'lucide-react';
import type { JourneySnapshot, ProductDefinition } from '../contracts';

export function MaterialPassport({ snapshot, product }: { readonly snapshot: JourneySnapshot; readonly product: ProductDefinition }) {
  const material = snapshot.material;
  return <section className="journey-passport" aria-label="소재 이력" id="journey-material-passport" tabIndex={-1}>
    <div className="journey-passport-heading"><Package size={18} /><h2>하나의 소재, 이어지는 이력</h2><span>{material.role === 'sale_product' ? '완성 제품' : '공정 소재'}</span></div>
    <div className="journey-passport-current"><strong>{material.form}</strong><span>{material.mass_kg.toLocaleString('ko-KR')} kg</span><span>{snapshot.completed ? '제품 출고' : product.steps.find(step => step.id === material.location_id)?.name ?? material.location_id}</span></div>
    <dl><div><dt>동일 소재 ID</dt><dd>{material.lineage_id}</dd></div><div><dt>현재 버전</dt><dd>{material.version_id}</dd></div><div><dt>이전 버전</dt><dd>{material.parent_version_id ?? '최초 투입 소재'}</dd></div></dl>
    <div className="journey-lineage" role="region" aria-label="소재 변환 이력" tabIndex={0}>
      <ol>{snapshot.history.map(version => <li key={version.version_id}><ArrowRight size={13} /><div><strong>{version.form}</strong><small>{version.version_id}</small></div></li>)}</ol>
    </div>
  </section>;
}
