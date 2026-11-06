import { useMemo } from 'react';
import { factoryCampus } from './campus';
import { factoryLayout } from './layout';
import type { Point } from './layout';
import { SceneParts } from './SceneParts';
import type { SitePart } from './SceneParts';

/** Fixed site utilities and landscaping: no stock, vehicle, or production state is invented here. */
export function SiteInfrastructure({ reserveCutaway }: { readonly reserveCutaway: boolean }) {
  const site = useMemo(() => {
    const boxes: SitePart[] = [];
    const cylinders: SitePart[] = [];
    const foliage: SitePart[] = [];
    const box = (position: Point, size: Point, color: string, rotation = 0) => {
      boxes.push({ position, size, color, rotation });
    };
    const cylinder = (position: Point, size: Point, color: string) => {
      cylinders.push({ position, size, color, rotation: 0 });
    };
    const tree = (x: number, z: number, index: number) => {
      const height = 2.8 + (index % 5) * 0.28;
      cylinder([x, height * 0.38, z], [0.25, height * 0.76, 0.25], '#7e7562');
      foliage.push({ position: [x, height, z], size: [2.2 + (index % 3) * 0.3, height * 0.92, 2.3], color: ['#4c704a', '#64834e', '#45684b'][index % 3] ?? '#6b8052', rotation: index });
    };
    for (const [index, hall] of factoryCampus.halls.entries()) {
      if (hall.kind === 'yard') continue;
      if (hall.id === 'hall-hot-rolling-reserve' && reserveCutaway) continue;
      const [width, height, processDepth] = hall.size;
      const depth = hall.id === 'hall-hot-rolling-reserve' ? processDepth : Math.max(processDepth, 25);
      const c = Math.cos(hall.rotation);
      const s = Math.sin(hall.rotation);
      const at = (x: number, y: number, z: number): Point => [hall.center[0] + c * x + s * z, y, hall.center[2] - s * x + c * z];
      const back = -depth / 2;
      // Lean-to service range gives each long mill a layered, substantial industrial silhouette.
      box(at(0, 2.6, back - 2.5), [width * 0.84, 5.2, 4.4], '#a5b0ad', hall.rotation);
      box(at(0, 5.35, back - 2.5), [width * 0.86, 0.24, 4.9], '#6b8791', hall.rotation);
      for (let x = -width / 2 + 5; x < width / 2 - 2; x += 10) {
        box(at(x, 1.6, back - 4.76), [2, 2.8, 0.16], '#6d8186', hall.rotation);
        box(at(x, 5.2, back - 6), [0.25, 10.4, 0.25], '#687e84', hall.rotation);
        box(at(x, 8.3, back - 5.5), [0.35, 0.3, 3.8], '#687e84', hall.rotation);
      }
      // Three real 3D utility pipes on the rear service rack; independent of material transport.
      for (const offset of [-0.65, 0, 0.65]) box(at(0, 8.5, back - 5.3 + offset), [width * 0.95, 0.22, 0.22], offset === 0 ? '#acb7b6' : '#87999d', hall.rotation);
      if (width > 50) {
        const x = -width / 2 + 3;
        cylinder(at(x, height * 0.5, back - 2.5), [1.1, height + 2.5, 1.1], '#a2adaa');
        cylinder(at(x, height + 1.4, back - 2.5), [1.4, 0.3, 1.4], '#67797c');
      }
      if (index % 3 === 0) {
        for (let n = 0; n < 3; n++) {
          tree(hall.center[0] - width / 3 + n * 7, hall.center[2] + depth / 2 + 6, index + n);
        }
      }
    }
    // Fixed energy/service structures keep the canonical road at z=60 clear.
    box([108, -0.035, 77], [82, 0.06, 46], '#d4d8d3');
    box([92, 3.4, 76], [38, 6.8, 22], '#b6c1bf');
    box([92, 6.95, 76], [39, 0.3, 23], '#476f83');
    box([92, 4.9, 87.1], [34, 1, 0.1], '#547c8b');
    box([93, 1.6, 87.2], [7, 3.2, 0.2], '#647e87');
    box([118, 2.5, 71], [11, 5, 14], '#a5b5b4');
    box([118, 5.15, 71], [12, 0.3, 15], '#78929c');
    for (let x = 77; x < 109; x += 3) {
      box([x, 7.15, 76], [0.08, 0.09, 23], '#6c8f9c');
    }
    for (const x of [134, 143]) {
      cylinder([x, 4.1, 75], [5.4, 8.2, 5.4], '#aab9b7');
      cylinder([x, 8.3, 75], [5.8, 0.35, 5.8], '#738d94');
      for (let y = 1; y < 8; y += 1.5) {
        cylinder([x, y, 75], [5.5, 0.12, 5.5], '#879e9f');
      }
    }
    cylinder([113, 8.5, 67], [1.4, 17, 1.4], '#829b9f');
    box([132, 5.1, 72], [30, 0.3, 0.3], '#8fa6a7');
    box([132, 5.8, 72], [30, 0.3, 0.3], '#a5b8b7');
    box([177, -0.025, 87], [18, 0.07, 35], '#82996d');
    for (let n = 0; n < 15; n++) {
      tree(171 + (n % 3) * 5, 72 + Math.floor(n / 3) * 7, n + 2);
    }
    for (let n = 0; n < 9; n++) {
      tree(78 + (n % 3) * 6, 105 + Math.floor(n / 3) * 5, n);
    }
    const [lx, , lz] = factoryCampus.land.center, [lw, , ld] = factoryCampus.land.size;
    for (let x = lx - lw / 2 + 5, i = 0; x < 305; x += 7, i++) {
      tree(x, lz - ld / 2 + 5, i);
      tree(x, lz + ld / 2 - 5, i + 3);
    }
    for (let z = lz - ld / 2 + 10, i = 0; z < lz + ld / 2; z += 7, i++) tree(lx - lw / 2 + 5, z, i);
    // Quay lighting and mooring infrastructure, with quiet geometric water glints.
    for (let z = -50; z < 220; z += 22) {
      cylinder([305, 4.5, z], [0.18, 9, 0.18], '#71838a');
      box([305, 9, z], [2.1, 0.14, 0.4], '#e0e1cb');
    }
    for (let x = 318, i = 0; x < 458; x += 4.5, i++) for (let z = -62; z < 232; z += 6) {
      const drift = Math.sin(x * 0.17 + z * 0.13) * 1.8;
      box([x, -0.255, z + drift], [1.2 + (i % 4) * 0.4, 0.018, 0.055], i % 3 === 0 ? '#72a8b3' : '#4a93a6', 0.12);
    }
    // Lighting follows the real service road geometry without adding moving traffic.
    for (const path of factoryLayout.paths.filter(row => row.network === 'road')) {
      for (let i = 1; i < path.points.length; i++) {
        const a = path.points[i - 1], b = path.points[i];
        if (!a || !b) continue;
        const dx = b[0] - a[0], dz = b[2] - a[2], length = Math.hypot(dx, dz);
        if (length < 24) continue;
        for (let d = 12; d < length; d += 36) {
          const x = a[0] + dx * d / length - dz / length * 3.9;
          const z = a[2] + dz * d / length + dx / length * 3.9;
          cylinder([x, 2.9, z], [0.12, 5.8, 0.12], '#657c83');
          box([x, 5.85, z], [1.2, 0.14, 0.4], '#d8dac9');
        }
      }
    }
    return { boxes, cylinders, foliage };
  }, [reserveCutaway]);
  return <group userData={{ siteScenery: 'fixed-utilities-and-landscaping' }}>
    <SceneParts parts={site.boxes} />
    <SceneParts parts={site.cylinders} shape="cylinder" />
    <SceneParts parts={site.foliage} shape="sphere" metalness={0} />
  </group>;
}
