import { beforeEach, describe, expect, it } from 'vitest';
import { cleanup, render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { WorldSchema } from './contracts';
import { useWorldStore } from './store';
import { OperationsWorkspace } from './operations/OperationsWorkspace';
import { initialNavigation, useNavigationStore } from './operations/navigation';
import { testWorld } from './operations/testWorld';

const base = testWorld();
const world = WorldSchema.parse({ ...base,
  locations: [{ id: 'ORE-SOURCE', type: 'source', name: '원료 공급 구역', x: 0, y: 0, z: 0 }],
  shipments: [{ run_id: base.run.id, id: 'SHIP-ga', order_id: 'ORD-ga', mode: 'SEA', status: 'PLANNED', location_id: 'ORE-SOURCE', capacity_kg: 20000, etd_at: '2026-10-30T00:06:00Z', eta_at: '2026-10-30T00:10:00Z' }],
  shipment_materials: [{ run_id: base.run.id, id: 'SM-ga', shipment_id: 'SHIP-ga', material_id: 'MAT-ga', loaded: false }],
});

describe('linked canonical material inspection', () => {
  beforeEach(() => {
    cleanup();
    useWorldStore.setState({ world, stale: false, error: null });
    useNavigationStore.setState({ ...initialNavigation, selection: { run_id: world.run.id, order_id: 'ORD-ga', material_id: 'MAT-ga' }, issue: null });
  });

  it('follows material to shipment dates and manifest and back through customer order', async () => {
    const user = userEvent.setup();
    render(<OperationsWorkspace world={world} />);
    const inspector = screen.getByTestId('material-inspector');
    expect(within(inspector).getByRole('heading', { name: 'MAT-ga' })).toBeVisible();
    expect(within(inspector).getByText('Synthetic')).toBeVisible();
    expect(within(inspector).getByText('LOT-ga')).toBeVisible();
    expect(within(inspector).getByText('WO-ga')).toBeVisible();
    expect(within(inspector).getByRole('button', { name: '원료 공급 구역' })).toBeVisible();
    await user.click(within(inspector).getByRole('button', { name: /SHIP-ga/ }));
    expect(screen.getByRole('heading', { name: 'SHIP-ga 적재 명세' })).toBeVisible();
    expect(screen.getByText('출발 2026-10-30T00:06:00Z · 예상 도착 2026-10-30T00:10:00Z · UTC')).toBeVisible();
    await user.click(screen.getByRole('button', { name: 'MAT-ga · 적재 대기' }));
    expect(useNavigationStore.getState().selection).toMatchObject({ material_id: 'MAT-ga', shipment_id: 'SHIP-ga', order_id: 'ORD-ga' });
    await user.click(within(inspector).getByRole('button', { name: 'ORD-ga' }));
    expect(screen.getByTestId('order-ORD-ga')).toHaveAttribute('aria-pressed', 'true');
    expect(screen.getByRole('region', { name: '주문 이행과 이벤트' })).toHaveTextContent('20,000 kg');
    await user.click(screen.getByTestId('material-MAT-ga'));
    expect(within(inspector).getByRole('heading', { name: 'MAT-ga' })).toBeVisible();
  });

  it('shows current location inventory and supports clearing selection', async () => {
    const user = userEvent.setup();
    render(<OperationsWorkspace world={world} />);
    await user.click(screen.getByRole('button', { name: '원료 공급 구역' }));
    const inventory = screen.getByRole('region', { name: '현재 위치 소재 재고' });
    expect(within(inventory).getByRole('heading', { name: '원료 공급 구역' })).toBeVisible();
    expect(within(inventory).getByText('1개 소재')).toBeVisible();
    await user.click(within(inventory).getByRole('button', { name: 'MAT-ga · 20,000 kg' }));
    expect(useNavigationStore.getState().selection.material_id).toBe('MAT-ga');
    await user.click(screen.getByRole('button', { name: '소재 선택 해제' }));
    expect(screen.getByText('주문에서 소재를 선택하면 생산·품질·출하 연결을 확인할 수 있습니다.')).toBeVisible();
    expect(screen.queryByRole('heading', { name: '원료 공급 구역' })).toBeNull();
    expect(useNavigationStore.getState().selection).toEqual({ run_id: world.run.id });
  });
});
