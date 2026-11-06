import { useMemo } from 'react';
import { factoryCampus } from './campus';
import type { Point } from './layout';
import { SceneParts } from './SceneParts';
import type { SitePart } from './SceneParts';

const finish = { roof: '#34738f', wall: '#b6c2c4', frame: '#536870', window: '#476875', sill: '#d8d9cd', rail: '#d5a342' } as const;

/** Architectural shells only; every process and material remains an independent World entity. */
export function IndustrialHalls({ focus, materialFocus }: { readonly focus: string | undefined; readonly materialFocus: string | undefined }) {
  const parts = useMemo(() => {
    const result: SitePart[] = [];
    for (const hall of factoryCampus.halls) {
      if (hall.kind === 'yard') continue;
      if (hall.id === 'hall-hot-rolling-reserve' && (focus === 'hr' || materialFocus === 'hr')) continue;
      const [width, processHeight, processDepth] = hall.size;
      const depth = hall.id === 'hall-hot-rolling-reserve' ? processDepth : Math.max(processDepth, 25);
      const height = processHeight * (hall.kind === 'hot' ? 1.55 : 1.5);
      const cutaway = hall.stage_id === focus || hall.stage_id === materialFocus;
      const hot = hall.kind === 'hot';
      const roof = hot ? '#5c7f8c' : hall.kind === 'warehouse' ? '#91a4a8' : finish.roof;
      const wall = hot ? '#a9aaa2' : finish.wall;
      const put = (at: Point, size: Point, color: string, tilt = 0) => {
        const c = Math.cos(hall.rotation), s = Math.sin(hall.rotation);
        result.push({ position: [hall.center[0] + c * at[0] + s * at[2], at[1], hall.center[2] - s * at[0] + c * at[2]], size, color, rotation: hall.rotation, tilt });
      };
      const back = -depth / 2, front = depth / 2;
      put([0, 0.35, back], [width, 0.7, 0.6], '#79878a');
      put([0, height / 2, back], [width, height, 0.28], wall);
      put([0, height * 0.73, back - 0.18], [width - 0.5, 1.05, 0.1], finish.window);
      put([0, height * 0.73 + 0.58, back - 0.2], [width, 0.13, 0.2], finish.sill);
      put([0, height * 0.73 - 0.58, back - 0.2], [width, 0.13, 0.2], finish.sill);
      for (let x = -width / 2 + 0.5; x <= width / 2; x += 4) {
        put([x, height / 2, back - 0.23], [0.13, height, 0.18], '#899ea3');
        put([x, height * 0.73, back - 0.28], [0.12, 1.1, 0.1], finish.sill);
      }
      // Open bays along the camera-facing facade expose the production line in a selected hall.
      for (let x = -width / 2 + 1; x < width / 2; x += 7) {
        for (const z of [back + 0.3, front - 0.3]) put([x, height / 2, z], [0.32, height, 0.36], finish.frame);
        put([x, height - 0.25, 0], [0.26, 0.35, depth], finish.frame);
        if (!cutaway) {
          put([x, height * 0.79, front], [6.6, height * 0.42, 0.28], wall);
          put([x, height * 0.79, front + 0.18], [5.9, 0.75, 0.08], finish.window);
          put([x, height * 0.32, front], [2.1, height * 0.64, 0.3], wall);
        }
        put([x, height - 1.2, back + 1], [0.18, 0.18, depth - 2], finish.rail);
      }
      for (const x of [-width / 2, width / 2]) {
        put([x, height / 2, (back - 3) / 2], [0.3, height, depth / 2 - 3], wall);
        put([x, height - 0.5, front / 2], [0.4, 0.8, depth / 2], wall);
        put([x, height * 0.5, front - 0.4], [0.4, height, 0.4], finish.frame);
      }
      // Selected cutaway retains the rear roof strip and steel structure, never a transparent veil.
      const roofDepth = cutaway ? depth * 0.24 : depth * 0.52;
      for (const side of cutaway ? [-1] : [-1, 1]) {
        const z = cutaway ? back + roofDepth / 2 : side * depth / 4;
        const tilt = side * 0.13;
        put([0, height + 0.45, z], [width + 1.2, 0.22, roofDepth + 0.5], roof, tilt);
        for (let x = -width / 2; x <= width / 2; x += 0.85) put([x, height + 0.62, z], [0.055, 0.09, roofDepth + 0.55], '#789aa8', tilt);
      }
      if (!cutaway) {
        put([0, height + 1.1, 0], [width * 0.82, 0.9, 1.9], wall);
        put([0, height + 1.6, 0], [width * 0.84, 0.16, 2.5], roof);
        for (let x = -width / 2 + 5; x < width / 2 - 2; x += 9) {
          put([x, height + 0.95, -depth / 3], [2.4, 0.7, 1.3], '#b3bdba');
          put([x, height + 1.35, -depth / 3], [2.7, 0.14, 1.6], '#6b7e82');
        }
      }
      put([0, 0.08, front + 1.1], [width + 2, 0.16, 2.2], '#b8bcb3');
      for (let x = -width / 2 + 2; x < width / 2; x += 8) {
        put([x, 0.65, front + 1.5], [0.17, 1.3, 0.17], '#d2a138');
        put([x, 1.16, front + 1.5], [0.2, 0.18, 0.2], '#4b5556');
      }
    }
    return result;
  }, [focus, materialFocus]);
  return <group userData={{ architecturalShells: 'corrugated-industrial-halls', cutawayStage: focus ?? null }}><SceneParts parts={parts} metalness={0.38} /></group>;
}
