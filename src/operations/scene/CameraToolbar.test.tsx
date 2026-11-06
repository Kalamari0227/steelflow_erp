import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { CameraToolbar } from './CameraToolbar';

afterEach(cleanup);
describe('camera toolbar', () => {
  it('provides seven named native buttons and dispatches each manual action once', () => {
    const action = vi.fn(); render(<CameraToolbar onAction={action} />);
    expect(screen.getByRole('group', { name: '3D 시점 조절' })).toBeVisible();
    for (const name of ['시점 위로 이동', '시점 아래로 이동', '시점 왼쪽으로 이동', '시점 오른쪽으로 이동', '확대', '축소', '현재 범위 맞춤']) fireEvent.click(screen.getByRole('button', { name }));
    expect(action.mock.calls.flat()).toEqual(['up', 'down', 'left', 'right', 'zoom-in', 'zoom-out', 'fit']);
  });
  it('supports tab/Enter and scoped arrow/zoom/Home keys without capturing keys elsewhere', async () => {
    const action = vi.fn(), user = userEvent.setup();
    render(<><input aria-label="다른 입력" /><CameraToolbar onAction={action} /></>);
    await user.tab(); await user.keyboard('{ArrowUp}'); expect(action).not.toHaveBeenCalled();
    await user.tab(); expect(screen.getByRole('button', { name: '시점 위로 이동' })).toHaveFocus();
    await user.keyboard('{Enter}{ArrowRight}+{Home}');
    expect(action.mock.calls.flat()).toEqual(['up', 'right', 'zoom-in', 'fit']);
    fireEvent.keyDown(screen.getByRole('group'), { key: 'ArrowLeft', ctrlKey: true });
    expect(action).toHaveBeenCalledTimes(4);
  });
});
