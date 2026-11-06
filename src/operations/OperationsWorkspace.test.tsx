import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, within } from '@testing-library/react';
import { WorldSchema } from '../contracts';
import { useWorldStore } from '../store';
import { fetchEventHistory } from '../api';
import { OperationsWorkspace } from './OperationsWorkspace';
import { WorkflowTimeline } from './WorkflowTimeline';
import { initialNavigation, useNavigationStore } from './navigation';
import { testWorld, testReply } from './testWorld';
import { commandWorld } from '../../tests/helpers/commandReply';

vi.mock('../api', async importOriginal => ({ ...await importOriginal<typeof import('../api')>(), fetchEventHistory: vi.fn() }));
beforeEach(() => { useNavigationStore.setState({ ...initialNavigation, issue: null }); useWorldStore.setState({ world: testWorld(), stale: false, error: null, receivedAt: Date.now() }); vi.clearAllMocks(); });
afterEach(cleanup);

describe('canonical operations workspace', () => {
  it('parses command receipts with the POST schema and returns a strict World for subsequent helpers', () => {
    const world = testWorld(3);
    const payload = testReply(world, true);
    expect(WorldSchema.safeParse(payload).success).toBe(false);
    const parsed = commandWorld(payload);
    expect(WorldSchema.parse(parsed)).toEqual(world);
    expect(parsed).not.toHaveProperty('applied_revision');
    expect(parsed).not.toHaveProperty('replayed');
    expect(() => commandWorld({ ...payload, applied_revision: '3' })).toThrow();
    expect(() => commandWorld({ ...payload, unrelated: true })).toThrow();
  });
  it('links order, material, work order and equipment without commands or changing the run', () => {
    const world = testWorld(3);
    const command = vi.spyOn(useWorldStore.getState(), 'command');
    render(<OperationsWorkspace world={world} />);
    fireEvent.click(screen.getByTestId('order-ORD-ga'));
    expect(screen.getByTestId('material-inspector')).toHaveTextContent('MAT-ga');
    expect(screen.getByTestId('material-inspector')).toHaveTextContent('WO-ga');
    expect(screen.getByTestId('material-inspector')).toHaveTextContent('LOT-ga');
    fireEvent.click(screen.getByTestId('process-PROC-ga'));
    expect(useNavigationStore.getState().level).toBe('equipment');
    expect(useNavigationStore.getState().selection.material_id).toBe('MAT-ga');
    fireEvent.click(screen.getByRole('button', { name: '공장 전경' }));
    fireEvent.click(screen.getByRole('button', { name: '2D' }));
    expect(useNavigationStore.getState().selection.run_id).toBe(world.run.id);
    expect(world.run.revision).toBe(3);
    expect(command).not.toHaveBeenCalled();
    command.mockRestore();
  });
  it('keeps drilldown camera when changing same-order material and clears an incompatible shipment', () => {
    const base = testWorld();
    const world = WorldSchema.parse({ ...base, materials: [...base.materials.map(row => ({ ...row, active: false, availability_status: 'CONSUMED' })), { ...base.materials[0], id: 'MAT-other', current_version_id: 'MAT-other:V1' }], material_versions: [...base.material_versions, { ...base.material_versions[0], id: 'MAT-other:V1', material_id: 'MAT-other' }] });
    const camera = { position: [10, 20, 30] as [number, number, number], target: [1, 2, 3] as [number, number, number], zoom: 24 };
    useNavigationStore.setState({ selection: { run_id: world.run.id, order_id: 'ORD-ga', material_id: 'MAT-ga', stage_id: 'ironmaking', equipment_id: 'CHARGE-A', shipment_id: 'SHIP-ga' }, level: 'equipment', cameraByScope: { 'equipment:CHARGE-A': camera } });
    const command = vi.spyOn(useWorldStore.getState(), 'command');
    render(<OperationsWorkspace world={world} />);
    fireEvent.click(screen.getByTestId('material-MAT-other'));
    expect(useNavigationStore.getState().selection).toEqual({ run_id: world.run.id, order_id: 'ORD-ga', material_id: 'MAT-other', stage_id: 'ironmaking', equipment_id: 'CHARGE-A', shipment_id: undefined });
    expect(useNavigationStore.getState().level).toBe('equipment');
    expect(useNavigationStore.getState().cameraByScope['equipment:CHARGE-A']).toEqual(camera);
    expect(command).not.toHaveBeenCalled();
    command.mockRestore();
  });
  it('searches compact stage navigation and keeps selected material when opening its actual process', () => {
    const world = testWorld();
    render(<OperationsWorkspace world={world} />);
    fireEvent.click(screen.getByTestId('order-ORD-ga'));
    fireEvent.click(screen.getByText('공정 선택', { selector: 'summary' }));
    fireEvent.change(screen.getByRole('textbox', { name: '공정 검색' }), { target: { value: 'not-a-stage' } });
    expect(screen.getByText('일치하는 공정이 없습니다.')).toBeInTheDocument();
    fireEvent.change(screen.getByRole('textbox', { name: '공정 검색' }), { target: { value: '' } });
    const route = screen.getByRole('navigation', { name: '선택 소재 공정 경로' });
    const process = world.processes.find(row => row.material_id === 'MAT-ga');
    if (!process) throw new Error('Missing material process fixture');
    fireEvent.click(within(route).getAllByRole('button')[0]!);
    expect(useNavigationStore.getState().selection).toMatchObject({ material_id: 'MAT-ga', equipment_id: process.equipment_id });
    expect(useNavigationStore.getState().level).toBe('equipment');
  });
  it('shows explicit empty search and recovers without losing selection', () => {
    render(<OperationsWorkspace world={testWorld()} />);
    fireEvent.click(screen.getByTestId('order-ORD-ga'));
    fireEvent.change(screen.getByRole('textbox', { name: '주문 검색' }), { target: { value: 'not-an-order' } });
    expect(screen.getByRole('status')).toHaveTextContent('검색 결과가 없습니다');
    expect(useNavigationStore.getState().selection.material_id).toBe('MAT-ga');
    fireEvent.change(screen.getByRole('textbox', { name: '주문 검색' }), { target: { value: '' } });
    expect(screen.getByTestId('order-ORD-ga')).toHaveAttribute('aria-pressed', 'true');
  });
  it('keeps consumed parents inspectable and links their split children', () => {
    const base = testWorld();
    const parent = base.materials[0];
    if (!parent) throw new Error('Missing fixture parent');
    const world = WorldSchema.parse({ ...base,
      materials: [{ ...parent, active: false, availability_status: 'CONSUMED' }, { ...parent, id: 'MAT-child', current_version_id: 'MAT-child:V1' }],
      material_versions: [...base.material_versions, { ...base.material_versions[0], id: 'MAT-child:V1', material_id: 'MAT-child', parent_version_id: parent.current_version_id }],
      lineage_edges: [{ run_id: base.run.id, id: 'EDGE', parent_material_id: parent.id, child_material_id: 'MAT-child', process_id: 'PROC-ga', transferred_kg: 20000 }],
    });
    render(<OperationsWorkspace world={world} />);
    fireEvent.click(screen.getByTestId('material-MAT-ga'));
    expect(screen.getByTestId('material-inspector')).toHaveTextContent('소비된 부모');
    fireEvent.click(within(screen.getByTestId('material-inspector')).getByRole('button', { name: 'MAT-child' }));
    expect(useNavigationStore.getState().selection.material_id).toBe('MAT-child');
    expect(screen.getByTestId('material-inspector')).toHaveTextContent('현재 소재');
  });
  it('surfaces invalid addresses and retains useful server state through connection failure', () => {
    useNavigationStore.getState().restore('?nav=%7Bbroken');
    useWorldStore.setState({ stale: true, error: '연결 실패', receivedAt: 1000 });
    render(<OperationsWorkspace world={testWorld()} />);
    expect(screen.getAllByRole('alert').some(node => node.textContent?.includes('탐색 주소'))).toBe(true);
    expect(screen.getAllByRole('alert').some(node => node.textContent?.includes('1970-01-01T00:00:01.000Z'))).toBe(true);
    expect(screen.getByTestId('simulation-step')).toBeDisabled();
    fireEvent.click(screen.getByRole('button', { name: '전체로 돌아가기' }));
    expect(useNavigationStore.getState().issue).toBeNull();
  });
  it('loads archive only on request and returns without mutating the current run', async () => {
    vi.mocked(fetchEventHistory).mockResolvedValue([{ id: 'legacy-event', scenario_id: 'NORMAL', run_id: 'archived-run', sequence: 1, entity_type: 'order', entity_id: 'OLD-ORDER', event_type: 'OLD_EVENT', occurred_at: '2026-10-20T00:00:00Z', payload: {} }]);
    render(<OperationsWorkspace world={testWorld()} />);
    expect(fetchEventHistory).not.toHaveBeenCalled();
    fireEvent.click(screen.getByTestId('order-ORD-ga'));
    const before = useNavigationStore.getState().selection;
    fireEvent.click(screen.getByRole('button', { name: '실행 이력 불러오기' }));
    const selector = await screen.findByRole('combobox', { name: '보관 실행 선택' });
    fireEvent.change(selector, { target: { value: 'archived-run' } });
    expect(screen.getByText('OLD_EVENT')).toBeInTheDocument();
    expect(useNavigationStore.getState().selection).toEqual(before);
    fireEvent.change(selector, { target: { value: '' } });
    expect(screen.queryByText('OLD_EVENT')).not.toBeInTheDocument();
    expect(fetchEventHistory).toHaveBeenCalledTimes(1);
  });
  it('keeps produced, dispatched, delivered and both remaining quantities separate', () => {
    const base = testWorld();
    const world = WorldSchema.parse({ ...base, orders: base.orders.map(order => ({ ...order, produced_kg: 20000, dispatched_kg: 12000, delivered_kg: 4000, remaining_dispatch_kg: 8000, remaining_delivery_kg: 16000 })) });
    render(<OperationsWorkspace world={world} />);
    fireEvent.click(screen.getByTestId('order-ORD-ga'));
    const workflow = screen.getByRole('region', { name: '주문 이행과 이벤트' });
    for (const value of ['20,000', '12,000', '4,000', '8,000', '16,000']) expect(workflow).toHaveTextContent(value);
  });
  it('distinguishes intermediate HR from final HR for the selected order', () => {
    const base = testWorld();
    const world = WorldSchema.parse({ ...base, materials: base.materials.map(row => ({ ...row, form: 'HR_COIL' })), material_versions: base.material_versions.map(row => ({ ...row, form: 'HR_COIL' })) });
    const rendered = render(<OperationsWorkspace world={world} />);
    fireEvent.click(screen.getByTestId('material-MAT-ga'));
    expect(screen.getByText('HR_COIL · 다음 공정 투입용 중간 HR')).toBeInTheDocument();
    const finalHr = WorldSchema.parse({ ...world, orders: world.orders.map(row => ({ ...row, product_id: 'hr' })) });
    rendered.rerender(<OperationsWorkspace world={finalHr} />);
    expect(screen.getByText('HR_COIL · 판매용 최종 HR')).toBeInTheDocument();
  });
  it('follows a shipment manifest back to its material and exposes unknown dates honestly', () => {
    const base = testWorld();
    const world = WorldSchema.parse({ ...base, shipments: [{ run_id: base.run.id, id: 'SHIP-ga', order_id: 'ORD-ga', mode: 'SEA', status: 'PLANNED', location_id: 'YARD', capacity_kg: 20000 }], shipment_materials: [{ run_id: base.run.id, id: 'SM-ga', shipment_id: 'SHIP-ga', material_id: 'MAT-ga', loaded: false }] });
    render(<OperationsWorkspace world={world} />);
    fireEvent.click(screen.getByTestId('material-MAT-ga'));
    fireEvent.click(within(screen.getByTestId('material-inspector')).getByRole('button', { name: /SHIP-ga/ }));
    expect(screen.getByText('출발 미확정 · 예상 도착 미확정 · UTC')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'MAT-ga · 적재 대기' }));
    expect(useNavigationStore.getState().selection).toMatchObject({ material_id: 'MAT-ga', shipment_id: 'SHIP-ga', order_id: 'ORD-ga' });
  });
  it.each([
    ['DELIVERED', null, '2026-10-30T07:26:00Z', '실제 도착 2026-10-30T07:26:00Z'],
    ['IN_TRANSIT', '2026-10-30T08:00:00Z', null, '예상 도착 2026-10-30T08:00:00Z'],
    ['DELIVERED', '2026-10-30T08:00:00Z', null, '실제 도착 미확정'],
  ])('renders shipment arrival honestly for %s with ETA %s and actual %s', (status, eta_at, delivered_at, arrival) => {
    const base = testWorld();
    const world = WorldSchema.parse({ ...base, shipments: [{ run_id: base.run.id, id: 'SHIP-ga', order_id: 'ORD-ga', status, location_id: 'PORT', capacity_kg: 20000, eta_at, delivered_at }] });
    render(<WorkflowTimeline world={world} order={null} detail={null} />);
    fireEvent.click(screen.getByRole('button', { name: /SHIP-ga/ }));
    expect(screen.getByText(`출발 미확정 · ${arrival} · UTC`)).toBeInTheDocument();
  });
  it('changing shipment orders immediately selects a matching material and clears equipment scope', () => {
    const base = testWorld();
    const world = WorldSchema.parse({ ...base,
      orders: [...base.orders, { ...base.orders[0], id: 'ORD-other', work_order_ids: ['WO-other'], material_ids: ['MAT-other'], shipment_ids: ['SHIP-other'] }],
      work_orders: [...base.work_orders, { ...base.work_orders[0], id: 'WO-other', order_id: 'ORD-other' }],
      lots: [...base.lots, { ...base.lots[0], id: 'LOT-other', work_order_id: 'WO-other', order_id: 'ORD-other' }],
      materials: [...base.materials, { ...base.materials[0], id: 'MAT-other', lot_id: 'LOT-other', current_version_id: 'MAT-other:V1' }],
      material_versions: [...base.material_versions, { ...base.material_versions[0], id: 'MAT-other:V1', material_id: 'MAT-other' }],
      mass_balance: { initial_kg: 40000, additions_kg: 0, active_kg: 40000, loss_kg: 0 },
      shipments: [{ run_id: base.run.id, id: 'SHIP-other', order_id: 'ORD-other', status: 'PLANNED', location_id: 'YARD', capacity_kg: 20000 }],
      shipment_materials: [{ run_id: base.run.id, id: 'SM-other', shipment_id: 'SHIP-other', material_id: 'MAT-other' }],
    });
    useNavigationStore.setState({ selection: { run_id: world.run.id, order_id: 'ORD-ga', material_id: 'MAT-ga', equipment_id: 'CHARGE-A', stage_id: 'ironmaking' }, level: 'equipment' });
    render(<WorkflowTimeline world={world} order={null} detail={null} />);
    fireEvent.click(screen.getByRole('button', { name: /SHIP-other/ }));
    expect(useNavigationStore.getState().selection).toEqual({ run_id: world.run.id, order_id: 'ORD-other', material_id: 'MAT-other', shipment_id: 'SHIP-other', equipment_id: undefined, stage_id: undefined });
    expect(useNavigationStore.getState().level).toBe('overview');
  });
  it.each([['DELIVERED', '배송 완료 · 하역됨'], ['AT_PORT', '항만 대기 · 재적재 예정']])('describes unloaded %s cargo by shipment state', (status, label) => {
    const base = testWorld();
    const world = WorldSchema.parse({ ...base, shipments: [{ run_id: base.run.id, id: 'SHIP-ga', order_id: 'ORD-ga', status, location_id: 'PORT', capacity_kg: 20000 }], shipment_materials: [{ run_id: base.run.id, id: 'SM-ga', shipment_id: 'SHIP-ga', material_id: 'MAT-ga', loaded: false }] });
    render(<WorkflowTimeline world={world} order={null} detail={null} />);
    fireEvent.click(screen.getByRole('button', { name: /SHIP-ga/ }));
    expect(screen.getByRole('button', { name: `MAT-ga · ${label}` })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'MAT-ga · 적재 대기' })).not.toBeInTheDocument();
  });
});
