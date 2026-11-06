import { useEffect, useMemo } from 'react';
import { BufferGeometry, DoubleSide, Float32BufferAttribute } from 'three';
import { SceneParts } from './SceneParts';
import type { SitePart } from './SceneParts';
import { colors } from '../../journey/scene/parts';
import { factoryLayout, stationAnchorPosition } from './layout';
import type { Point } from './layout';
import { factoryCampus } from './campus';

type Segment = { readonly a: Point; readonly b: Point; readonly width: number };
const asphalt = '#69777c', concrete = '#d5d8d4', grass = '#a4b294';

function segments(paths: readonly { readonly points: readonly Point[]; readonly width: number }[]): Segment[] {
  const seen = new Set<string>();
  return paths.flatMap(path => path.points.slice(1).flatMap((b, index) => {
    const a = path.points[index];
    if (!a || Math.hypot(b[0] - a[0], b[2] - a[2]) < 0.01) return [];
    const key = [a.map(v => v.toFixed(3)).join(','), b.map(v => v.toFixed(3)).join(',')].sort().join('|');
    if (seen.has(key)) return [];
    seen.add(key);
    return [{ a, b, width: path.width }];
  }));
}

function RoadSurface({ rows }: { readonly rows: readonly Segment[] }) {
  const geometry = useMemo(() => {
    const vertices: number[] = [];
    for (const { a, b, width } of rows) {
      const dx = b[0] - a[0], dz = b[2] - a[2], length = Math.hypot(dx, dz);
      const nx = -dz / length * width / 2, nz = dx / length * width / 2;
      const corners = [[a[0] + nx, 0.02, a[2] + nz], [a[0] - nx, 0.02, a[2] - nz], [b[0] + nx, 0.02, b[2] + nz], [b[0] - nx, 0.02, b[2] - nz]];
      for (const index of [0, 1, 2, 2, 1, 3]) vertices.push(...(corners[index] ?? []));
    }
    const result = new BufferGeometry();
    result.setAttribute('position', new Float32BufferAttribute(vertices, 3)); result.computeVertexNormals();
    return result;
  }, [rows]);
  useEffect(() => () => geometry.dispose(), [geometry]);
  return <mesh geometry={geometry} receiveShadow raycast={() => null}><meshStandardMaterial color={asphalt} side={DoubleSide} roughness={0.95} /></mesh>;
}

export function FactoryGround({ focus }: { readonly focus: string | undefined }) {
  const roads = useMemo(() => segments([...factoryCampus.roads, ...factoryLayout.paths.filter(path => path.network === 'road').map(path => ({ points: path.points, width: 5.6 }))]), []);
  const { boxes, cylinders, cones } = useMemo(() => {
    const boxes: SitePart[] = [], cylinders: SitePart[] = [], cones: SitePart[] = [];
    const box = (position: Point, size: Point, color: string, rotation = 0) => boxes.push({ position, size, color, rotation });
    const cylinder = (position: Point, size: Point, color: string) => cylinders.push({ position, size, color, rotation: 0 });
    const cone = (position: Point, size: Point, color: string) => cones.push({ position, size, color, rotation: 0 });
    const { land, water } = factoryCampus;
    const coast = water.center[0] - water.size[0] / 2;
    const west = land.center[0] - land.size[0] / 2;
    box([(west + coast) / 2, -1.35, land.center[2]], [coast - west, 2.4, land.size[2]], colors.base);
    box([(west + coast) / 2, -0.12, land.center[2]], [coast - west - 1, 0.06, land.size[2] - 1], grass);
    box([coast + 280, -0.4, land.center[2]], [560, 0.25, 760], '#2e819c');
    for (const z of [-62, 233]) {
      box([coast + 35, -0.05, z], [74, 0.9, 5], '#a6b2b0');
      box([coast + 35, 0.5, z], [74, 0.25, 1], '#c7ceca');
    }
    box([coast - 1.5, -0.15, water.center[2]], [4, 1.8, water.size[2]], '#89928d');
    for (let z = water.center[2] - water.size[2] / 2; z < water.center[2] + water.size[2] / 2; z += 5) {
      box([coast + 0.7, 0.45, z], [0.8, 0.7, 1.5], '#596c70');
      box([coast - 1.1, 0.85, z], [0.3, 0.3, 1.2], '#e0b858');
    }
    for (const hall of factoryCampus.halls) {
      const [width, , depth] = hall.size;
      const put = (local: Point, size: Point, color: string) => {
        const c = Math.cos(hall.rotation), s = Math.sin(hall.rotation);
        box([hall.center[0] + c * local[0] + s * local[2], local[1], hall.center[2] - s * local[0] + c * local[2]], size, color, hall.rotation);
      };
      const architecturalDepth = hall.kind === 'yard' || hall.id === 'hall-hot-rolling-reserve' ? depth : Math.max(depth, 25);
      put([0, -0.04, 0], [width + 5, 0.06, architecturalDepth + 9], concrete);
      if (hall.kind === 'yard') {
        for (let x = -width / 2 + 3; x < width / 2; x += 7) put([x, 0.06, 2], [0.12, 0.05, depth - 4], '#e9e6d6');
        continue;
      }
    }
    for (const { a, b, width } of roads) {
      const dx = b[0] - a[0], dz = b[2] - a[2], length = Math.hypot(dx, dz), rotation = -Math.atan2(dz, dx);
      for (const side of [-1, 1]) {
        const offset = (width / 2 + 0.2) * side;
        box([(a[0] + b[0]) / 2 - dz / length * offset, 0.06, (a[2] + b[2]) / 2 + dx / length * offset], [length, 0.12, 0.25], '#d9d8c9', rotation);
      }
      if (length < 8) continue;
      for (let d = 2; d < length - 2; d += 7) box([a[0] + dx * d / length, 0.05, a[2] + dz * d / length], [2.4, 0.025, 0.12], '#f1e6be', rotation);
    }
    for (const network of ['rail', 'roller'] as const) {
      const rows = segments(factoryLayout.paths.filter(path => path.network === network).map(path => ({ points: path.points, width: 1.6 })));
      for (const { a, b } of rows) {
        const dx = b[0] - a[0], dz = b[2] - a[2], length = Math.hypot(dx, dz), rotation = -Math.atan2(dz, dx);
        const mx = (a[0] + b[0]) / 2, mz = (a[2] + b[2]) / 2;
        box([mx, network === 'rail' ? -0.01 : 0.45, mz], [length, network === 'rail' ? 0.14 : 0.35, network === 'rail' ? 2.3 : 1.7], network === 'rail' ? '#a09e96' : colors.frame, rotation);
        for (const side of [-1, 1]) box([mx - dz / length * side * 0.7, network === 'rail' ? 0.16 : 0.78, mz + dx / length * side * 0.7], [length, 0.12, 0.09], colors.steel, rotation);
        for (let d = 0.4; d < length; d += network === 'rail' ? 1.8 : 0.6) box([a[0] + dx * d / length, network === 'rail' ? 0.07 : 0.84, a[2] + dz * d / length], [network === 'rail' ? 0.28 : 0.18, 0.12, network === 'rail' ? 1.9 : 1.6], network === 'rail' ? colors.frame : colors.steel, rotation);
      }
    }
    const blast = stationAnchorPosition(factoryLayout, 'BF-A', 'work');
    for (const dx of [-7, -3, 1]) {
      cylinder([blast[0] + dx, 8, blast[2] - 15], [3.4, 16, 3.4], '#ad9480');
      cone([blast[0] + dx, 17, blast[2] - 15], [3.4, 2, 3.4], colors.shadow);
      box([blast[0] + dx, 2, blast[2] - 7.5], [0.5, 0.5, 7], colors.steel);
    }
    cylinder([blast[0] + 7, 14, blast[2] - 16], [1.65, 28, 1.65], '#9d7866');
    for (const y of [21, 24, 27]) cylinder([blast[0] + 7, y, blast[2] - 16], [1.75, 1, 1.75], '#d1c9be');
    const ore = stationAnchorPosition(factoryLayout, 'ORE-SOURCE', 'work');
    for (let i = 0; i < 5; i += 1) {
      cone([ore[0] - 18 + i * 8, 2, ore[2] - 12], [8, 4, 12], i < 3 ? '#a97450' : '#525958');
      box([ore[0] - 18 + i * 8, 4, ore[2] - 20], [7.8, 0.6, 1.5], colors.frame);
    }
    for (const id of ['WAREHOUSE', 'PORT', 'CUSTOMER']) {
      const anchor = stationAnchorPosition(factoryLayout, id, 'buffer');
      for (const offset of [-24, 24]) box([anchor[0] + offset, 0.06, anchor[2] + 9], [0.2, 0.1, 22], colors.rail);
    }
    const port = stationAnchorPosition(factoryLayout, 'PORT', 'work');
    box([port[0] + 15, -0.05, port[2]], [12, 0.7, 68], concrete);
    for (let z = -30; z <= 30; z += 6) box([port[0] + 20, 0.35, port[2] + z], [0.8, 1, 2], colors.frame);
    for (const z of [-21, 21]) {
      for (const x of [4, 15]) box([port[0] + x, 6, port[2] + z], [0.65, 12, 0.65], '#ae8b52');
      box([port[0] + 13, 12, port[2] + z], [30, 0.6, 0.65], '#ae8b52');
      box([port[0] + 4, 13.4, port[2] + z], [4, 2.4, 3], colors.panel);
    }
    const customer = stationAnchorPosition(factoryLayout, 'CUSTOMER', 'work');
    box([customer[0], -0.1, customer[2] + 7], [64, 0.6, 45], concrete);
    return { boxes, cylinders, cones };
  }, [focus, roads]);
  return <group userData={{ campusLayout: 'integrated-coastal-works' }}><SceneParts parts={boxes} /><SceneParts parts={cylinders} shape="cylinder" /><SceneParts parts={cones} shape="cone" /><RoadSurface rows={roads} /></group>;
}
