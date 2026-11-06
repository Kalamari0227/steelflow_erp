import { ArrowDown, ArrowLeft, ArrowRight, ArrowUp, Maximize, Minus, Plus } from 'lucide-react';
import type { CameraAction } from './cameraControls';

const actions = [
  { action: 'up', label: '시점 위로 이동', icon: ArrowUp },
  { action: 'down', label: '시점 아래로 이동', icon: ArrowDown },
  { action: 'left', label: '시점 왼쪽으로 이동', icon: ArrowLeft },
  { action: 'right', label: '시점 오른쪽으로 이동', icon: ArrowRight },
  { action: 'zoom-in', label: '확대', icon: Plus },
  { action: 'zoom-out', label: '축소', icon: Minus },
  { action: 'fit', label: '현재 범위 맞춤', icon: Maximize },
] as const;
const keyboardActions: Readonly<Record<string, CameraAction>> = { ArrowUp: 'up', ArrowDown: 'down', ArrowLeft: 'left', ArrowRight: 'right', '+': 'zoom-in', '=': 'zoom-in', '-': 'zoom-out', Home: 'fit' };

export function CameraToolbar({ onAction }: { readonly onAction: (action: CameraAction) => void }) {
  return <div className="ops-camera-toolbar" role="group" aria-label="3D 시점 조절" onKeyDown={event => {
    const action = keyboardActions[event.key];
    if (!action || event.altKey || event.ctrlKey || event.metaKey) return;
    event.preventDefault(); event.stopPropagation(); onAction(action);
  }}>
    <span>시점 이동</span>
    {actions.map(({ action, label, icon: Icon }) => <button key={action} type="button" aria-label={label} title={label} onClick={() => onAction(action)}><Icon size={16} aria-hidden="true" />{action === 'fit' && <span>맞춤</span>}</button>)}
    <small>방향키 이동 · +/− 확대 · Home 맞춤</small>
  </div>;
}
