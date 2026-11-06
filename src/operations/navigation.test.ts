import { beforeEach, describe, expect, it, vi } from 'vitest';
import { WorldSchema } from '../contracts';
import { cameraScope, connectNavigationUrl, initialNavigation, navigationSearch, parseNavigation, useNavigationStore, validateSelection } from './navigation';
import { selectMaterial } from './selectors';
import { testWorld } from './testWorld';

beforeEach(() => useNavigationStore.setState({ ...initialNavigation, issue: null }));
describe('persistent operations navigation', () => {
  it('restores browser history locally and removes its listener on cleanup', () => {
    window.history.replaceState(null, '', '/?workspace=production&material_id=MAT-ga');
    const fetch = vi.spyOn(globalThis, 'fetch');
    const disconnect = connectNavigationUrl();
    useNavigationStore.getState().setView('2d');
    expect(parseNavigation(window.location.search).navigation.view).toBe('2d');
    window.history.replaceState(null, '', '/?workspace=journey&material_id=MAT-ga');
    window.dispatchEvent(new PopStateEvent('popstate'));
    expect(useNavigationStore.getState().level).toBe('equipment');
    disconnect();
    window.history.replaceState(null, '', '/?workspace=production');
    window.dispatchEvent(new PopStateEvent('popstate'));
    expect(useNavigationStore.getState().level).toBe('equipment');
    expect(fetch).not.toHaveBeenCalled();
    fetch.mockRestore();
  });
  it('round trips selection, scope cameras, follow and 2D through the URL', () => {
    const store = useNavigationStore.getState();
    store.select({ run_id: 'run-test', order_id: 'ORD-ga', material_id: 'MAT-ga', stage_id: 'ironmaking', equipment_id: 'CHARGE-A' });
    store.saveCamera({ position: [10, 20, 30], target: [0, 0, 0], zoom: 1 });
    store.setLevel('equipment');
    store.saveCamera({ position: [1, 2, 3], target: [4, 5, 6], zoom: 2 });
    store.setView('2d');
    store.setFollowMaterial(true);
    const state = useNavigationStore.getState();
    const parsed = parseNavigation(navigationSearch(state));
    expect(parsed.issue).toBeNull();
    expect(parsed.navigation.selection).toEqual(state.selection);
    expect(parsed.navigation.cameraByScope).toEqual({ overview: { position: [10, 20, 30], target: [0, 0, 0], zoom: 1 }, 'equipment:CHARGE-A': { position: [1, 2, 3], target: [4, 5, 6], zoom: 2 } });
    expect([parsed.navigation.view, parsed.navigation.followMaterial, cameraScope(parsed.navigation)]).toEqual(['2d', true, 'equipment:CHARGE-A']);
  });
  it.each([['production', 'stage'], ['journey', 'equipment']])('maps legacy workspace %s to unified level %s', (workspace, level) => {
    const parsed = parseNavigation(`?workspace=${workspace}&material_id=MAT-ga`);
    expect(parsed.navigation.level).toBe(level);
    expect(parsed.navigation.selection.material_id).toBe('MAT-ga');
  });
  it('preserves surviving IDs after reset and explicitly explains missing selection', () => {
    const result = validateSelection({ run_id: 'old-run', order_id: 'ORD-ga', material_id: 'deleted-material' }, testWorld());
    expect(result.selection).toEqual({ run_id: 'run-test', order_id: 'ORD-ga' });
    expect(result.issue?.code).toBe('missing_id');
    expect(result.issue?.ids).toEqual(['deleted-material']);
  });
  it('retains the same identity across run replacement with an explanation', () => {
    const result = validateSelection({ run_id: 'old-run', order_id: 'ORD-ga', material_id: 'MAT-ga' }, testWorld());
    expect(result.selection).toEqual({ run_id: 'run-test', order_id: 'ORD-ga', material_id: 'MAT-ga' });
    expect(result.issue?.code).toBe('run_changed');
  });
  it('rejects malformed URL cameras instead of accepting invalid coordinates', () => {
    const parsed = parseNavigation(`?nav=${encodeURIComponent(JSON.stringify({ ...initialNavigation, cameraByScope: { overview: { position: ['bad', 0, 0], target: [0, 0, 0], zoom: 1 } } }))}`);
    expect(parsed.issue?.code).toBe('invalid_url');
  });
  it('keeps consumed split parents inspectable and selects children explicitly', () => {
    const base = testWorld();
    const parent = base.materials[0];
    const version = base.material_versions[0];
    if (!parent || !version) throw new Error('Missing fixture material');
    const children = ['A', 'B'].map(suffix => ({ ...parent, id: `MAT-${suffix}`, current_version_id: `V-${suffix}`, weight_kg: 10000 }));
    const world = WorldSchema.parse({ ...base,
      materials: [{ ...parent, active: false, availability_status: 'CONSUMED' }, ...children],
      material_versions: [version, ...children.map(row => ({ ...version, id: row.current_version_id, material_id: row.id, parent_version_id: version.id, weight_kg: 10000 }))],
      lineage_edges: children.map(row => ({ run_id: base.run.id, id: `EDGE-${row.id}`, parent_material_id: parent.id, child_material_id: row.id, process_id: 'PROC-ga', transferred_kg: 10000 })),
    });
    const selected = validateSelection({ run_id: world.run.id, material_id: parent.id }, world);
    expect(selected.selection.material_id).toBe(parent.id);
    expect(selectMaterial(world, parent.id)?.lineage.map(row => row.child_material_id)).toEqual(['MAT-A', 'MAT-B']);
    expect(selectMaterial(world, 'MAT-A')?.material.weight_kg).toBe(10000);
    expect(selectMaterial(world, 'MAT-A')?.material.id).toBe('MAT-A');
  });
});

it('keeps idle standby equipment selectable from authoritative stage inventory', () => {
  const base = testWorld();
  const world = { ...base, production: { ...base.production, stages: [...base.production.stages, { id: 'hot-rolling-reserve', equipment_ids: ['HSM-B'], process_ids: [], batch_ids: [] }] } };
  expect(world.processes.some(row => row.equipment_id === 'HSM-B')).toBe(false);
  const selected = validateSelection({ run_id: world.run.id, equipment_id: 'HSM-B', stage_id: 'hot-rolling-reserve' }, world);
  expect(selected.issue).toBeNull();
  expect(selected.selection.equipment_id).toBe('HSM-B');
  const unknown = validateSelection({ run_id: world.run.id, equipment_id: 'HSM-MISSING' }, world);
  expect(unknown.issue?.code).toBe('missing_id');
  expect(unknown.selection.equipment_id).toBeUndefined();
});
