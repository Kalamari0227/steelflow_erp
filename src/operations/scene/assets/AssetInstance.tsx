import type { ThreeEvent } from '@react-three/fiber';
import type { AssetEntity, AssetIdentity } from './registry';

/** The registry owns this tree and its shared resources, including across unmounts. */
export function AssetInstance({ entity, onPick, onHover }: { readonly entity: AssetEntity; readonly onPick: (identity: AssetIdentity) => void; readonly onHover?: (identity: AssetIdentity | null) => void }) {
  const pick = (event: ThreeEvent<MouseEvent>): void => { event.stopPropagation(); onPick(entity.identity); };
  const over = (event: ThreeEvent<PointerEvent>): void => { event.stopPropagation(); onHover?.(entity.identity); };
  const out = (event: ThreeEvent<PointerEvent>): void => { event.stopPropagation(); onHover?.(null); };
  return <group dispose={null} onClick={pick} onPointerOver={over} onPointerOut={out}><primitive object={entity.root} /></group>;
}
