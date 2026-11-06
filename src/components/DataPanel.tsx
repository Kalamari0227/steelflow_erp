import type { World } from '../contracts';
import { WorkflowTimeline } from '../operations/WorkflowTimeline';
import { useNavigationStore } from '../operations/navigation';
import { selectMaterial } from '../operations/selectors';

export function InventoryTable({ world }: { readonly world: World }) {
  const { select } = useNavigationStore();
  return <div className="table-scroll" role="region" aria-label="소재 재고" tabIndex={0}><table><caption>현재 실행 소재 재고 · kg</caption><thead><tr><th>소재</th><th>형태</th><th>중량</th><th>위치</th><th>품질</th><th>재고 상태</th></tr></thead><tbody>{world.materials.map(material => <tr key={material.id}><td><button onClick={() => select({ run_id: world.run.id, material_id: material.id, order_id: selectMaterial(world, material.id)?.order.id })}>{material.id}</button></td><td>{material.form}</td><td>{material.weight_kg.toLocaleString('ko-KR')}</td><td>{material.location_id}</td><td>{material.quality_status}</td><td>{material.availability_status}</td></tr>)}</tbody></table></div>;
}
export function DataPanel({ world }: { readonly world: World }) {
  const selection = useNavigationStore(state => state.selection);
  return <WorkflowTimeline world={world} order={world.orders.find(order => order.id === selection.order_id) ?? null} detail={selection.material_id ? selectMaterial(world, selection.material_id) : null} />;
}
