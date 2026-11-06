import { create } from 'zustand';
import { getProducts } from './api';
import type { JourneyCommand, JourneySnapshot, ProductDefinition } from './contracts';
import { useWorldStore } from '../store';
import { useNavigationStore } from '../operations/navigation';
import { selectJourney } from '../operations/selectors';

type JourneyState = {
  readonly products: readonly ProductDefinition[];
  readonly snapshot: JourneySnapshot | null;
  readonly busy: boolean;
  readonly fetching: boolean;
  readonly error: string | null;
  readonly epoch: number;
  readonly refresh: () => Promise<void>;
  readonly command: (command: JourneyCommand) => Promise<void>;
};
let catalog: Promise<readonly ProductDefinition[]> | null = null;
export const useJourneyStore = create<JourneyState>(set => ({
  products: [], snapshot: null, busy: false, fetching: false, error: null, epoch: 0,
  refresh: async () => {
    set({ fetching: true });
    try {
      catalog ??= getProducts();
      set({ products: await catalog });
      syncJourney();
    } catch (error) {
      if (!(error instanceof Error)) throw error;
      catalog = null;
      set({ error: '제품 목록을 불러오지 못했습니다.' });
    } finally { set({ fetching: false }); }
  },
  command: async command => {
    if (command.action === 'select') {
      const world = useWorldStore.getState().world;
      if (!world || world.schema_version !== 2) { set({ snapshot: null, error: '이 실행은 소재·재고 화면에서 확인해 주세요.' }); return; }
      const order = world.orders.find(row => row.product_id === command.product_id.toLowerCase());
      const material = world?.materials.find(row => row.active && world.lots.some(lot => lot.id === row.lot_id && lot.order_id === order?.id));
      if (!world || !order || !material) { set({ error: '선택한 제품의 현재 소재가 없습니다. 주문에서 소재를 선택해 주세요.' }); return; }
      useNavigationStore.getState().select({ run_id: world.run.id, order_id: order.id, material_id: material.id });
      useNavigationStore.getState().setLevel('equipment');
      return;
    }
    await useWorldStore.getState().command(command);
  },
}));
function syncJourney(): void {
  const remote = useWorldStore.getState();
  const selection = useNavigationStore.getState().selection;
  const snapshot = remote.world?.schema_version === 2 && selection.material_id ? selectJourney(remote.world, selection.material_id) : null;
  useJourneyStore.setState({ snapshot, busy: remote.busy, error: remote.error, epoch: remote.revision });
}
useWorldStore.subscribe(syncJourney);
useNavigationStore.subscribe(syncJourney);
