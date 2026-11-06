import { useLayoutEffect, useRef } from 'react';
import { Color, Object3D } from 'three';
import type { InstancedMesh } from 'three';
import type { Point } from './layout';

export type SitePart = {
  readonly position: Point;
  readonly size: Point;
  readonly color: string;
  readonly rotation: number;
  readonly tilt?: number;
};

export function SceneParts({ parts, shape = 'box', metalness = 0.2 }: { readonly parts: readonly SitePart[]; readonly shape?: 'box' | 'cylinder' | 'cone' | 'sphere'; readonly metalness?: number }) {
  const mesh = useRef<InstancedMesh>(null);
  useLayoutEffect(() => {
    if (!mesh.current) return;
    const transform = new Object3D();
    for (const [index, part] of parts.entries()) {
      transform.position.set(...part.position);
      transform.scale.set(...part.size);
      transform.rotation.set(0, part.rotation, 0);
      transform.rotateX(part.tilt ?? 0);
      transform.updateMatrix();
      mesh.current.setMatrixAt(index, transform.matrix);
      mesh.current.setColorAt(index, new Color(part.color));
    }
    mesh.current.instanceMatrix.needsUpdate = true;
    if (mesh.current.instanceColor) mesh.current.instanceColor.needsUpdate = true;
    mesh.current.computeBoundingSphere();
  }, [parts]);
  return <instancedMesh key={`${shape}:${parts.length}`} ref={mesh} args={[undefined, undefined, parts.length]} receiveShadow castShadow raycast={() => null}>
    {shape === 'box' ? <boxGeometry /> : shape === 'sphere' ? <sphereGeometry args={[0.5, 8, 6]} /> : <cylinderGeometry args={[shape === 'cone' ? 0 : 0.5, 0.5, 1, 12]} />}
    <meshStandardMaterial roughness={0.7} metalness={metalness} />
  </instancedMesh>;
}
