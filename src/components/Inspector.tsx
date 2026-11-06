import type { Shipment, World } from '../contracts';
import { MaterialInspector } from '../operations/MaterialInspector';
import { useNavigationStore } from '../operations/navigation';
import { selectMaterial } from '../operations/selectors';

export function ShipmentTimeline({ shipment }: { readonly shipment: Shipment }) {
  return <dl><dt>출하 상태</dt><dd>{shipment.status}</dd><dt>출발 · UTC</dt><dd>{shipment.etd_at ?? '미확정'}</dd><dt>도착 · UTC</dt><dd>{shipment.delivered_at ?? shipment.eta_at ?? '미확정'}</dd></dl>;
}
export function Inspector({ world }: { readonly world: World }) {
  const materialId = useNavigationStore(state => state.selection.material_id);
  return <MaterialInspector world={world} detail={materialId ? selectMaterial(world, materialId) : null} />;
}
