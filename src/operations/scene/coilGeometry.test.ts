import { CylinderGeometry, RingGeometry } from 'three';
import { expect, it } from 'vitest';
import { updateCoilGeometry } from './coilGeometry';

it('keeps actual bore above the mandrel and external width fixed throughout winding', () => {
  const exterior = new CylinderGeometry(0.7, 0.7, 1.1, 64, 1, true);
  const bore = new CylinderGeometry(0.28, 0.28, 1.1, 48, 1, true);
  const face = new RingGeometry(0.28, 0.7, 64);
  for (const amount of [1, 0.5, 0.02, 0.97, 0.2, 1]) {
    for (const geometry of [exterior, bore, face]) updateCoilGeometry(geometry, amount);
    const radii = Array.from({ length: face.attributes.position?.count ?? 0 }, (_, index) => Math.hypot(face.attributes.position?.getX(index) ?? 0, face.attributes.position?.getY(index) ?? 0));
    expect(Math.min(...radii)).toBeCloseTo(0.28, 6);
    expect(Math.min(...radii)).toBeGreaterThan(0.21);
    expect(Math.max(...radii)).toBeCloseTo(Math.sqrt(0.28 ** 2 + (0.7 ** 2 - 0.28 ** 2) * amount), 6);
    expect((exterior.boundingBox?.max.y ?? 0) - (exterior.boundingBox?.min.y ?? 0)).toBeCloseTo(1.1, 6);
    expect((bore.boundingBox?.max.x ?? 0) - (bore.boundingBox?.min.x ?? 0)).toBeCloseTo(0.56, 6);
  }
  expect(exterior.boundingBox?.max.x).toBeCloseTo(0.7, 6);
  exterior.dispose(); bore.dispose(); face.dispose();
});
