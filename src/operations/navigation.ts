import { create } from 'zustand';
import { z } from 'zod';
import type { ApiWorld } from '../contracts';

const SelectionSchema = z.object({ run_id: z.string().default(''), bundle_hash: z.string().regex(/^[0-9a-f]{64}$/).optional(), entity_type: z.enum(['material', 'batch', 'stock_lot', 'attachment', 'order']).optional(), entity_id: z.string().optional(), order_id: z.string().optional(), material_id: z.string().optional(), stage_id: z.string().optional(), equipment_id: z.string().optional(), shipment_id: z.string().optional() });
const CameraSchema = z.object({ position: z.tuple([z.number().finite(), z.number().finite(), z.number().finite()]), target: z.tuple([z.number().finite(), z.number().finite(), z.number().finite()]), zoom: z.number().positive() });
const NavigationSchema = z.object({ selection: SelectionSchema, level: z.enum(['overview', 'stage', 'equipment']), followMaterial: z.boolean(), cameraByScope: z.record(z.string(), CameraSchema), view: z.enum(['3d', '2d']) });
export type OperationsSelection = z.infer<typeof SelectionSchema>;
export type CameraState = z.infer<typeof CameraSchema>;
export type Navigation = z.infer<typeof NavigationSchema>;
export type NavigationIssue = { readonly code: 'invalid_url' | 'missing_id' | 'run_changed' | 'identity_mismatch'; readonly message: string; readonly ids: readonly string[] };
export const initialNavigation: Navigation = { selection: { run_id: '' }, level: 'overview', followMaterial: false, cameraByScope: {}, view: '3d' };

export function parseNavigation(search: string): { readonly navigation: Navigation; readonly issue: NavigationIssue | null } {
  const query = new URLSearchParams(search);
  try {
    const stored = query.get('nav');
    if (stored) return { navigation: NavigationSchema.parse(JSON.parse(stored)), issue: null };
    const workspace = query.get('workspace');
    const selection = SelectionSchema.parse(Object.fromEntries([...query].filter(([key]) => key.endsWith('_id'))));
    return { navigation: { ...initialNavigation, selection, level: workspace === 'journey' ? 'equipment' : workspace === 'production' ? 'stage' : 'overview', view: query.get('view') === '2d' ? '2d' : '3d' }, issue: null };
  } catch (error) {
    if (!(error instanceof Error)) throw error;
    const workspace = query.get('workspace');
    if (!query.has('nav') && ![...query.keys()].some(key => key.endsWith('_id'))) return { navigation: { ...initialNavigation, level: workspace === 'journey' ? 'equipment' : workspace === 'production' ? 'stage' : 'overview' }, issue: null };
    return { navigation: initialNavigation, issue: { code: 'invalid_url', message: '저장된 탐색 주소가 올바르지 않습니다. 대상을 다시 선택해 주세요.', ids: [] } };
  }
}
export function navigationSearch(navigation: Navigation): string {
  return `?${new URLSearchParams({ nav: JSON.stringify(navigation) })}`;
}
export function cameraScope(navigation: Navigation): string {
  switch (navigation.level) {
    case 'overview': return 'overview';
    case 'stage': return `stage:${navigation.selection.stage_id ?? ''}`;
    case 'equipment': return `equipment:${navigation.selection.equipment_id ?? ''}`;
    default: { const unreachable: never = navigation.level; return unreachable; }
  }
}
export function validateSelection(selection: OperationsSelection, world: ApiWorld): { readonly selection: OperationsSelection; readonly issue: NavigationIssue | null } {
  if (world.schema_version === 3) {
    const next = { ...selection, run_id: world.run.id, bundle_hash: world.run.bundle_hash };
    const groups = { material: world.materials, batch: world.process_batches, stock_lot: world.stock_lots, attachment: world.attachments, order: world.orders };
    const entityType = selection.entity_type ?? (selection.material_id ? 'material' : selection.order_id ? 'order' : undefined);
    const entityId = selection.entity_id ?? selection.material_id ?? selection.order_id;
    const changedBundle = selection.bundle_hash !== undefined && selection.bundle_hash !== world.run.bundle_hash;
    if (changedBundle || (entityId && (!entityType || !groups[entityType].some(row => row.id === entityId)))) {
      return { selection: { run_id: world.run.id, bundle_hash: world.run.bundle_hash }, issue: { code: changedBundle ? 'identity_mismatch' : 'missing_id', message: '현재 실행과 번들에 없는 대상입니다. 다시 선택해 주세요.', ids: entityId ? [entityId] : [] } };
    }
    if (entityType && entityId) { next.entity_type = entityType; next.entity_id = entityId; }
    return { selection: next, issue: selection.run_id && selection.run_id !== world.run.id ? { code: 'run_changed', message: '실행이 변경되어 선택한 ID를 현재 실행에서 다시 확인했습니다.', ids: [] } : null };
  }
  const next = { ...selection, run_id: world.run.id };
  const missing: string[] = [];
  const groups = [
    ['order_id', world.orders], ['material_id', world.materials], ['shipment_id', world.shipments], ['stage_id', world.production.stages],
    ['equipment_id', world.production.stages.flatMap(row => row.equipment_ids.map(id => ({ id })))],
  ] as const;
  for (const [key, rows] of groups) {
    const id = next[key];
    if (id !== undefined && !rows.some(row => row.id === id)) { missing.push(id); delete next[key]; }
  }
  if (missing.length) return { selection: next, issue: { code: 'missing_id', message: `현재 실행에 없는 대상입니다: ${missing.join(', ')}. 대상을 다시 선택해 주세요.`, ids: missing } };
  const material = world.materials.find(row => row.id === next.material_id);
  const lot = world.lots.find(row => row.id === material?.lot_id);
  if (next.order_id && lot && lot.order_id !== next.order_id) {
    delete next.material_id;
    return { selection: next, issue: { code: 'identity_mismatch', message: '선택한 소재와 주문이 서로 다릅니다. 소재를 다시 선택해 주세요.', ids: [material?.id ?? ''] } };
  }
  return { selection: next, issue: selection.run_id && selection.run_id !== world.run.id ? { code: 'run_changed', message: '실행이 변경되어 선택한 ID를 현재 실행에서 다시 확인했습니다.', ids: [] } : null };
}
type NavigationState = Navigation & {
  readonly issue: NavigationIssue | null;
  readonly select: (selection: OperationsSelection) => void;
  readonly setLevel: (level: Navigation['level']) => void;
  readonly setView: (view: Navigation['view']) => void;
  readonly setFollowMaterial: (followMaterial: boolean) => void;
  readonly saveCamera: (camera: CameraState) => void;
  readonly restore: (search: string) => void;
  readonly revalidate: (world: ApiWorld) => void;
};
export const useNavigationStore = create<NavigationState>(set => ({
  ...initialNavigation, issue: null,
  select: selection => set({ selection, issue: null }), setLevel: level => set({ level }),
  setView: view => set({ view }), setFollowMaterial: followMaterial => set({ followMaterial }),
  saveCamera: camera => set(state => ({ cameraByScope: { ...state.cameraByScope, [cameraScope(state)]: camera } })),
  restore: search => { const parsed = parseNavigation(search); set({ ...parsed.navigation, issue: parsed.issue }); },
  revalidate: world => set(state => {
    const result = validateSelection(state.selection, world);
    return { ...result, issue: result.issue ?? state.issue };
  }),
}));
export function connectNavigationUrl(browser: Pick<Window, 'location' | 'history' | 'addEventListener' | 'removeEventListener'> = window): () => void {
  useNavigationStore.getState().restore(browser.location.search);
  const unsubscribe = useNavigationStore.subscribe(state => browser.history.replaceState(null, '', `${browser.location.pathname}${navigationSearch(state)}${browser.location.hash}`));
  const restore = (): void => useNavigationStore.getState().restore(browser.location.search);
  browser.addEventListener('popstate', restore);
  return () => { unsubscribe(); browser.removeEventListener('popstate', restore); };
}
