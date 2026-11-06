import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { ProductDefinition } from './contracts';
import { useJourneyStore } from './store';
import { useWorldStore } from '../store';
import { initialNavigation, useNavigationStore } from '../operations/navigation';
import { testWorld } from '../operations/testWorld';

const api = vi.hoisted(() => ({ getProducts: vi.fn<() => Promise<ProductDefinition[]>>() }));
vi.mock('./api', () => api);

beforeEach(() => {
  useNavigationStore.setState({ ...initialNavigation, issue: null });
  useWorldStore.setState({ world: testWorld(), busy: false, fetching: false, error: null, stale: false, revision: 0 });
});
describe('journey read selectors', () => {
  it('selects a product locally without resetting or mutating the world', async () => {
    const fetch = vi.spyOn(globalThis, 'fetch');
    const command = vi.spyOn(useWorldStore.getState(), 'command');
    const before = useWorldStore.getState().world;
    await useJourneyStore.getState().command({ action: 'select', product_id: 'GA' });
    expect(command).not.toHaveBeenCalled();
    expect(fetch).not.toHaveBeenCalled();
    expect(useWorldStore.getState().world).toBe(before);
    expect(useJourneyStore.getState().snapshot?.material.lineage_id).toBe('MAT-ga');
    expect(useJourneyStore.getState().snapshot?.run_id).toBe(before?.run.id);
    command.mockRestore();
    fetch.mockRestore();
  });
  it('derives material revisions and outage status from the one world store', async () => {
    await useJourneyStore.getState().command({ action: 'select', product_id: 'ga' });
    useWorldStore.setState({ world: testWorld(5), error: 'offline', stale: true });
    expect(useJourneyStore.getState().snapshot?.revision).toBe(5);
    expect(useJourneyStore.getState().error).toBe('offline');
    useWorldStore.setState({ world: testWorld(6), error: null, stale: false });
    expect(useJourneyStore.getState().snapshot?.revision).toBe(6);
    expect(useJourneyStore.getState().error).toBeNull();
  });
  it('loads the static product catalog once and does not poll world per tab', async () => {
    api.getProducts.mockResolvedValue([]);
    const refresh = vi.spyOn(useWorldStore.getState(), 'refresh');
    await useJourneyStore.getState().refresh();
    await useJourneyStore.getState().refresh();
    expect(api.getProducts).toHaveBeenCalledTimes(1);
    expect(refresh).not.toHaveBeenCalled();
    refresh.mockRestore();
  });
  it('keeps selection and reports unavailable product without changing run', async () => {
    await useJourneyStore.getState().command({ action: 'select', product_id: 'ga' });
    const selection = useNavigationStore.getState().selection;
    await useJourneyStore.getState().command({ action: 'select', product_id: 'missing' });
    expect(useNavigationStore.getState().selection).toEqual(selection);
    expect(useJourneyStore.getState().error).not.toBeNull();
  });
});
