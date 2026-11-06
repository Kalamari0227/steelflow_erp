import { CylinderGeometry, RingGeometry } from 'three';
import type { BufferGeometry } from 'three';

export const coilBoreRadius = 0.28;
export const coilOuterRadius = 0.7;
const originalPositions = new WeakMap<BufferGeometry, Float32Array>();

/** Wound cross-section changes; mandrel clearance and strip width do not. */
export function updateCoilGeometry(geometry: BufferGeometry, amount: number): void {
  if (!(geometry instanceof CylinderGeometry) && !(geometry instanceof RingGeometry)) return;
  const position = geometry.getAttribute('position');
  let original = originalPositions.get(geometry);
  if (!original) { original = Float32Array.from(position.array); originalPositions.set(geometry, original); }
  const outer = Math.sqrt(coilBoreRadius ** 2 + (coilOuterRadius ** 2 - coilBoreRadius ** 2) * Math.max(0, Math.min(1, amount)));
  const radialAxis = geometry instanceof CylinderGeometry ? 2 : 1;
  for (let index = 0; index < position.count; index += 1) {
    const x = original[index * 3] ?? 0, y = original[index * 3 + radialAxis] ?? 0;
    const radius = Math.hypot(x, y);
    const fraction = Math.max(0, Math.min(1, (radius - coilBoreRadius) / (coilOuterRadius - coilBoreRadius)));
    const scale = radius > 0 ? (coilBoreRadius + fraction * (outer - coilBoreRadius)) / radius : 1;
    position.setComponent(index, 0, x * scale); position.setComponent(index, radialAxis, y * scale);
  }
  position.needsUpdate = true;
  geometry.computeBoundingBox(); geometry.computeBoundingSphere();
}
