import { beforeEach, describe, expect, it, vi } from 'vitest';
import { act, fireEvent, render, screen, within } from '@testing-library/react';
import { FactoryWorkspace } from './FactoryWorkspace';
import { factoryTestWorld as world } from './factoryTestWorld';
import { factoryMaterialDetailSchema } from './contractsV3';
import { initialNavigation, useNavigationStore } from './navigation';
import { useWorldStore } from '../store';
import { getFactoryMaterial } from '../api';
import { deferred } from './testWorld';
import type { FactoryMaterialDetail } from './contractsV3';

vi.mock('../api', async importOriginal => ({ ...await importOriginal<typeof import('../api')>(), getFactoryMaterial: vi.fn() }));
const stock = world.materials.find(row => row.id === 'stock-coil');
const stockDetail = factoryMaterialDetailSchema.parse({ schema_version: 3, run_id: world.run.id, revision: world.run.revision, material: stock, current_version: world.material_versions.find(row => row.id === stock?.current_version_id), versions: world.material_versions.filter(row => row.material_id === stock?.id), lineage_materials: [stock], version_edges: [], process_batches: [], batch_io: [], allocations: [], current_allocation: null, order: null, work_order: null, production_lot: null, origin_stock_lot: world.stock_lots.find(row => row.id === stock?.origin_stock_lot_id), attachments: world.attachments.filter(row => row.material_id === stock?.id), current_attachment: world.attachments.find(row => row.material_id === stock?.id && row.released_at_ms === null), transport_jobs: [], current_job: null, shipments: [], shipment_legs: [], quality: [], events: [] });
beforeEach(() => {
  vi.clearAllMocks();
  useNavigationStore.setState({ ...initialNavigation, issue: null });
  useWorldStore.setState({ world, stale: false, busy: false, error: null, unavailable: false, appliedRevision: null, appliedRunId: null });
  vi.mocked(getFactoryMaterial).mockResolvedValue(stockDetail);
});
describe('functional schema3 material and custody surface', () => {
  it('opens stock with null provenance, actual grade and custody, then follows custody back to stock', async () => {
    render(<FactoryWorkspace world={world} />);
    fireEvent.click(screen.getByRole('button', { name: 'stock-coil' }));
    const detail = await screen.findByRole('region', { name: '소재 상세' });
    expect(within(detail).getAllByText('없음 (null)').length).toBeGreaterThanOrEqual(3);
    expect(within(detail).getByText('SYNTHETIC · HR_COIL · 500 kg')).toBeInTheDocument();
    const custody = stockDetail.current_attachment;
    if (!custody) throw new Error('fixture custody missing');
    fireEvent.click(within(detail).getByRole('button', { name: `${custody.kind} · ${custody.owner_id} / ${custody.socket_id}` }));
    expect(screen.getByRole('heading', { name: `보관 ${custody.id}` })).toBeInTheDocument();
    expect(useNavigationStore.getState().selection).toMatchObject({ entity_type: 'attachment', entity_id: custody.id, bundle_hash: world.run.bundle_hash });
  });
  it('lists both real inputs and outputs in the N:M batch and links to a physical material', () => {
    render(<FactoryWorkspace world={world} />);
    fireEvent.click(screen.getByRole('button', { name: '배치 batch-merge-split' }));
    const detail = screen.getByRole('complementary', { name: '선택 상세' });
    expect(within(detail).getAllByRole('listitem')).toHaveLength(5);
    expect(within(detail).getByRole('button', { name: 'in-a (in-a-v1)' })).toBeInTheDocument();
    fireEvent.click(within(detail).getByRole('button', { name: 'out-b (out-b-v1)' }));
    expect(useNavigationStore.getState().selection.entity_id).toBe('out-b');
  });
  it('does not apply a late material detail after selecting another entity', async () => {
    const pending = deferred<FactoryMaterialDetail>();
    vi.mocked(getFactoryMaterial).mockReturnValueOnce(pending.promise);
    render(<FactoryWorkspace world={world} />);
    fireEvent.click(screen.getByRole('button', { name: 'stock-coil' }));
    fireEvent.click(screen.getByRole('button', { name: '배치 batch-merge-split' }));
    await act(async () => { pending.resolve(stockDetail); await pending.promise; });
    expect(screen.queryByRole('region', { name: '소재 상세' })).not.toBeInTheDocument();
    expect(screen.getByRole('heading', { name: '배치 batch-merge-split' })).toBeInTheDocument();
  });
  it('disables all business commands on stale state while retaining the material table', () => {
    useWorldStore.setState({ stale: true, error: '승인된 공장 번들이 준비되지 않았습니다.' });
    render(<FactoryWorkspace world={world} />);
    for (const name of ['재생', '한 단계', '초기화']) expect(screen.getByRole('button', { name })).toBeDisabled();
    expect(screen.getByRole('combobox', { name: '실행 속도' })).toBeDisabled();
    expect(screen.getByRole('combobox', { name: '시나리오' })).toBeDisabled();
    expect(screen.getByRole('button', { name: 'stock-coil' })).toBeEnabled();
  });
});
