import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { WorldSchema } from '../contracts';
import { useWorldStore } from '../store';
import { initialNavigation, useNavigationStore } from './navigation';
import { OperationsTable } from './OperationsTable';
import { OperationsWorkspace } from './OperationsWorkspace';
import { testWorld } from './testWorld';

function operationalWorld() {
  const base = testWorld();
  return WorldSchema.parse({ ...base,
    inspections: [{ run_id: base.run.id, id: 'INS-ga', material_id: 'MAT-ga', status: 'PASSED', inspected_version_id: 'MAT-ga:V1' }],
    transfers: [{ run_id: base.run.id, id: 'TR-ga', material_id: 'MAT-ga', from_location_id: 'ORE-SOURCE', to_location_id: 'FURNACE', mode: 'flatbed', vehicle_id: 'TRUCK-A', status: 'WAITING', process_id: 'PROC-ga', capacity_kg: 25000 }],
    shipments: [{ run_id: base.run.id, id: 'SHIP-ga', order_id: 'ORD-ga', mode: 'SEA', status: 'ALLOCATED', location_id: 'YARD', capacity_kg: 20000 }],
    shipment_materials: [{ run_id: base.run.id, id: 'SM-ga', shipment_id: 'SHIP-ga', material_id: 'MAT-ga', loaded: false }],
  });
}
beforeEach(() => { useNavigationStore.setState({ ...initialNavigation, issue: null }); useWorldStore.setState({ world: testWorld(), stale: false, error: null, receivedAt: Date.now() }); });
afterEach(cleanup);

describe('accessible canonical operations table', () => {
  it('focuses committed details immediately and does not steal focus on subsequent world refresh', () => {
    const world = operationalWorld();
    const rendered = render(<OperationsTable world={world} />);
    fireEvent.click(screen.getByTestId('process-PROC-ga'));
    expect(screen.getByRole('region', { name: '공정 선택 기록' })).toHaveFocus();
    const nextCategory = screen.getByRole('button', { name: '검사' });
    nextCategory.focus();
    rendered.rerender(<OperationsTable world={WorldSchema.parse({ ...world, run: { ...world.run, revision: 1 } })} />);
    expect(nextCategory).toHaveFocus();
    fireEvent.click(nextCategory);
    expect(screen.getByRole('button', { name: '검사 INS-ga 상세' })).toBeInTheDocument();
  });
  it('uses keyboard controls to follow order, material, inspection and shipment without business commands', async () => {
    const world = operationalWorld();
    const command = vi.spyOn(useWorldStore.getState(), 'command');
    const user = userEvent.setup();
    render(<OperationsTable world={world} />);
    const choose = async (kind: string, id: string) => {
      const section = screen.getByRole('button', { name: kind });
      section.focus(); await user.keyboard('{Enter}');
      const row = screen.getByRole('button', { name: `${kind} ${id} 상세` });
      row.focus(); await user.keyboard('{Enter}');
      expect(screen.getByRole('region', { name: `${kind} 선택 기록` })).toHaveTextContent(id);
    };
    await choose('주문', 'ORD-ga');
    expect(screen.getByRole('region', { name: '주문 선택 기록' })).toHaveTextContent('출고 잔량 20,000 kg');
    await choose('소재', 'MAT-ga');
    await choose('검사', 'INS-ga');
    expect(screen.getByRole('region', { name: '검사 선택 기록' })).toHaveTextContent('검사 대상 버전 MAT-ga:V1');
    await choose('출하', 'SHIP-ga');
    expect(useNavigationStore.getState().selection).toEqual({ run_id: world.run.id, order_id: 'ORD-ga', material_id: 'MAT-ga', shipment_id: 'SHIP-ga' });
    expect(command).not.toHaveBeenCalled(); command.mockRestore();
  });
  it('connects process and transport to the actual material, destination equipment and current location', () => {
    render(<OperationsTable world={operationalWorld()} />);
    fireEvent.click(screen.getByTestId('process-PROC-ga'));
    expect(useNavigationStore.getState().selection).toMatchObject({ material_id: 'MAT-ga', equipment_id: 'CHARGE-A', stage_id: 'ironmaking' });
    expect(useNavigationStore.getState().level).toBe('equipment');
    fireEvent.click(screen.getByRole('button', { name: '운송' }));
    fireEvent.click(screen.getByRole('button', { name: '운송 TR-ga 상세' }));
    expect(screen.getByRole('region', { name: '운송 선택 기록' })).toHaveTextContent('현재 위치 ORE-SOURCE');
    expect(screen.getByRole('region', { name: '운송 선택 기록' })).toHaveTextContent('TRUCK-A');
  });
  it('shows empty inspection state and separate consumed-parent rows without inventing inventory', () => {
    const base = testWorld();
    const world = WorldSchema.parse({ ...base, materials: [...base.materials.map(row => ({ ...row, active: false, availability_status: 'CONSUMED' })), ...base.materials.map(row => ({ ...row, id: 'MAT-child', current_version_id: 'MAT-child:V1' }))], material_versions: [...base.material_versions, ...base.material_versions.map(row => ({ ...row, id: 'MAT-child:V1', material_id: 'MAT-child', parent_version_id: row.id }))] });
    render(<OperationsTable world={world} />);
    fireEvent.click(screen.getByRole('button', { name: '검사' }));
    expect(screen.getByText('선택한 대상의 검사 기록이 아직 없습니다.')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: '소재' }));
    fireEvent.click(screen.getByRole('button', { name: '소재 MAT-ga 상세' }));
    expect(screen.getByRole('region', { name: '소재 선택 기록' })).toHaveTextContent('소비된 부모 · 현재 재고에서 제외');
    expect(within(screen.getByRole('table')).getAllByRole('row')).toHaveLength(3);
  });
  it('announces scene failure and retains selected identity in a useful table', () => {
    const world = testWorld(3);
    useNavigationStore.setState({ selection: { run_id: world.run.id, order_id: 'ORD-ga', material_id: 'MAT-ga' } });
    render(<OperationsWorkspace world={world} renderScene={({ onFallback }) => <button onClick={onFallback}>Simulate scene failure</button>} />);
    fireEvent.click(screen.getByRole('button', { name: 'Simulate scene failure' }));
    expect(screen.getByRole('status')).toHaveTextContent('선택한 주문과 소재는 그대로 유지');
    expect(screen.getByRole('status')).toHaveFocus();
    expect(screen.getByTestId('operations-table')).toHaveTextContent('ORD-ga · MAT-ga');
    expect(useNavigationStore.getState().selection.material_id).toBe('MAT-ga');
  });
});
