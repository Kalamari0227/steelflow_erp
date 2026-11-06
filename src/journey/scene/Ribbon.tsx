import { useEffect, useMemo, useRef } from 'react';
import type { RefObject } from 'react';
import { useFrame } from '@react-three/fiber';
import { BufferAttribute, BufferGeometry, DoubleSide } from 'three';
import type { Mesh } from 'three';
import type { PhaseClock } from './Equipment';
import { phasePosition, stepPose } from './path';
import type { makeLine } from './path';
import { colors } from './parts';

export function Ribbon({ line, clock, enabled, kind, hot }: { readonly line: ReturnType<typeof makeLine>; readonly clock: RefObject<PhaseClock>; readonly enabled: boolean; readonly kind: string; readonly hot: boolean }) {
  const mesh = useRef<Mesh>(null);
  const geometry = useMemo(() => {
    const result = new BufferGeometry();
    result.setAttribute('position', new BufferAttribute(new Float32Array(49 * 2 * 3), 3));
    result.setAttribute('normal', new BufferAttribute(Float32Array.from({ length: 49 * 2 * 3 }, (_, i) => i % 3 === 1 ? 1 : 0), 3));
    result.setIndex(Array.from({ length: 48 }, (_, i) => [i * 2, i * 2 + 1, i * 2 + 2, i * 2 + 1, i * 2 + 3, i * 2 + 2]).flat());
    return result;
  }, []);
  useEffect(() => () => geometry.dispose(), [geometry]);
  useFrame(() => {
    if (!mesh.current) return;
    const { index, phase } = clock.current;
    const winding = kind === 'coiler' ? Math.max(0, (phase - 0.28) / 0.72) : kind === 'uncoiler' ? Math.max(0, 1 - phase * 1.6) : 0;
    mesh.current.visible = enabled && winding < 0.99;
    if (!enabled) return;
    const center = phasePosition(index, phase, line.stations.length), pose = stepPose(line, index, phase);
    const positions = geometry.getAttribute('position');
    for (let i = 0; i <= 48; i++) {
      const t = Math.max(0, Math.min(1, center + (i / 48 - 0.5) * 1.3 / line.stations.length * (1 - winding)));
      const point = line.curve.getPoint(t), tangent = line.curve.getTangent(t);
      const stationPhase = t * line.stations.length - index;
      const guideHeight = (kind === 'galvanizing' || kind === 'looper') && stationPhase > 0 && stationPhase < 1 ? Math.sin(stationPhase * Math.PI) * 2.05 : 0;
      for (let side = 0; side < 2; side++) {
        const width = (side === 0 ? -1 : 1) * 0.54;
        const dx = point.x - pose.position.x - tangent.z * width, dz = point.z - pose.position.z + tangent.x * width;
        positions.setXYZ(i * 2 + side, Math.cos(pose.rotation) * dx - Math.sin(pose.rotation) * dz, 0.065 + guideHeight, Math.sin(pose.rotation) * dx + Math.cos(pose.rotation) * dz);
      }
    }
    positions.needsUpdate = true; geometry.computeBoundingSphere();
  }, -1);
  return <mesh ref={mesh} geometry={geometry} castShadow receiveShadow><meshStandardMaterial color={hot ? colors.hot : colors.steel} metalness={0.65} roughness={0.35} side={DoubleSide} emissive={hot ? colors.hot : '#000000'} emissiveIntensity={hot ? 0.45 : 0} /></mesh>;
}
