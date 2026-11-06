import { useEffect, useState } from 'react';
import type { RefObject } from 'react';
import { useThree } from '@react-three/fiber';
import type { ThreeEvent } from '@react-three/fiber';
import { Mesh, MeshStandardMaterial } from 'three';
import type { Group } from 'three';

export function useSceneHover(id: string, body?: RefObject<Group | null>) {
  const [hovered, setHovered] = useState(false);
  const { gl, invalidate } = useThree();
  useEffect(() => {
    if (!hovered || !body?.current) return;
    const surfaces: { material: MeshStandardMaterial; color: number; intensity: number }[] = [];
    body.current.traverse(object => {
      if (!(object instanceof Mesh) || !(object.material instanceof MeshStandardMaterial)) return;
      surfaces.push({ material: object.material, color: object.material.emissive.getHex(), intensity: object.material.emissiveIntensity });
      object.material.emissive.set('#7ea9bb'); object.material.emissiveIntensity = 0.25;
    });
    invalidate();
    return () => { for (const surface of surfaces) { surface.material.emissive.set(surface.color); surface.material.emissiveIntensity = surface.intensity; } invalidate(); };
  }, [hovered, body, invalidate]);
  useEffect(() => () => {
    if (gl.domElement.dataset.hoverTarget === id) { delete gl.domElement.dataset.hoverTarget; gl.domElement.style.cursor = ''; }
  }, [gl, id]);
  const events = {
    onPointerOver: (event: ThreeEvent<PointerEvent>) => {
      event.stopPropagation(); setHovered(true); gl.domElement.dataset.hoverTarget = id; gl.domElement.style.cursor = 'pointer'; invalidate();
    },
    onPointerOut: () => {
      setHovered(false);
      if (gl.domElement.dataset.hoverTarget === id) { delete gl.domElement.dataset.hoverTarget; gl.domElement.style.cursor = ''; }
      invalidate();
    },
  };
  return { hovered, events };
}
