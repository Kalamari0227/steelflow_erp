import { useMemo } from 'react';
import { factoryLayout, stationAnchorPosition } from './layout';
import type { Point } from './layout';
import { SceneParts } from './SceneParts';
import type { SitePart } from './SceneParts';

/** Fixed structures at the existing blast furnace and port; no additional operational actors. */
export function SteelworksLandmarks({ upstreamCutaway }: { readonly upstreamCutaway: boolean }) {
  const blast = stationAnchorPosition(factoryLayout, 'BF-A', 'work');
  const port = stationAnchorPosition(factoryLayout, 'PORT', 'work');
  const parts = useMemo(() => {
    const beams: SitePart[] = [];
    const pipes: SitePart[] = [];
    const beam = (a: Point, b: Point, width: number, color: string, pipe = false) => {
      const dx = b[0] - a[0], dy = b[1] - a[1], dz = b[2] - a[2];
      const part: SitePart = {
        position: [(a[0] + b[0]) / 2, (a[1] + b[1]) / 2, (a[2] + b[2]) / 2],
        size: [width, Math.hypot(dx, dy, dz), width],
        color,
        rotation: Math.atan2(dx, dz),
        tilt: Math.atan2(Math.hypot(dx, dz), dy),
      };
      (pipe ? pipes : beams).push(part);
    };
    const bf = (x: number, y: number, z: number): Point => [blast[0] + x, y, blast[2] + z];
    // Tall framed furnace tower, maintenance decks and diagonal steel bracing.
    for (const x of [-4.7, 4.7]) for (const z of [-4.5, 3.4]) {
      beam(bf(x, 0, z), bf(x, 24, z), 0.45, '#485b64');
    }
    for (const y of [5, 10, 15, 20, 24]) {
      for (const z of [-4.5, 3.4]) {
        beam(bf(-5.2, y, z), bf(5.2, y, z), 0.35, '#617781');
        if (!upstreamCutaway || z < 0) beam(bf(-4.7, y - 5, z), bf(4.7, y, z), 0.2, '#819297');
        beam(bf(-5.2, y + 1, z), bf(5.2, y + 1, z), 0.1, '#c89c3f');
      }
      for (const x of [-5.2, 5.2]) {
        beam(bf(x, y, -5), bf(x, y, 4), 0.4, '#617781');
        beam(bf(x, y + 1, -5), bf(x, y + 1, 4), 0.1, '#c89c3f');
      }
    }
    // External gas downcomer and inclined charging bridge are structural utilities.
    beam(bf(0, 24, -1), bf(7, 19, -8), 1.1, '#a8b2b0', true);
    beam(bf(7, 19, -8), bf(7, 3, -8), 1.1, '#a8b2b0', true);
    for (const side of [-1, 1]) {
      beam(bf(-22, 1.2, side * 1.2 - 1), bf(-1, 23, side * 1.2 - 1), 0.5, '#647b83');
    }
    for (let t = 0; t < 1; t += 0.13) {
      const x = -22 + t * 21, y = 1.2 + t * 21.8;
      beam(bf(x, y, -2.2), bf(x, y, 0.2), 0.24, '#b89b54');
    }
    for (const x of [-17, -10]) beam(bf(x, 0, -1), bf(x, 2 + (x + 22), -1), 0.45, '#647b83');
    // Existing berth gains large portal crane structures, rigging and a clearly bounded quay.
    for (const z of [-23, 23]) {
      const point = (x: number, y: number, localZ: number): Point => [port[0] + x, y, port[2] + z + localZ];
      for (const x of [4, 16]) for (const side of [-2, 2]) {
        beam(point(x, 0, side), point(x, 17, side * 0.45), 0.65, '#c8943d');
      }
      beam(point(-4, 17, 0), point(39, 17, 0), 0.85, '#dca548');
      beam(point(4, 17, 0), point(12, 25, 0), 0.6, '#c8943d');
      beam(point(12, 25, 0), point(35, 17, 0), 0.18, '#64777b');
      beam(point(12, 25, 0), point(-4, 17, 0), 0.18, '#64777b');
      for (const x of [23, 24]) beam(point(x, 17, 0), point(x, 8, 0), 0.07, '#566a71');
      beam(point(21, 8, 0), point(26, 8, 0), 0.35, '#c8943d');
      beams.push({ position: point(7, 18, 0), size: [4, 2.5, 3.4], color: '#476e81', rotation: 0 });
    }
    return { beams, pipes };
  }, [blast, port, upstreamCutaway]);
  return <group userData={{ landmarkEquipment: ['BF-A', 'PORT'] }}>
    {!upstreamCutaway && <group position={[blast[0], 0, blast[2] - 0.7]}>
      <mesh position={[0, 9, 0]} castShadow receiveShadow>
        <cylinderGeometry args={[2.5, 3.4, 10, 24]} />
        <meshStandardMaterial color="#9eaaa6" roughness={0.55} metalness={0.55} />
      </mesh>
      <mesh position={[0, 16.2, 0]} castShadow>
        <cylinderGeometry args={[1.1, 2.5, 4.4, 24]} />
        <meshStandardMaterial color="#7c9198" roughness={0.6} metalness={0.45} />
      </mesh>
      <mesh position={[0, 20, 0]} castShadow>
        <cylinderGeometry args={[1.1, 1.1, 4, 20]} />
        <meshStandardMaterial color="#596e77" metalness={0.45} roughness={0.6} />
      </mesh>
    </group>}
    <SceneParts parts={parts.beams} metalness={0.45} />
    <SceneParts parts={parts.pipes} shape="cylinder" metalness={0.55} />
  </group>;
}
