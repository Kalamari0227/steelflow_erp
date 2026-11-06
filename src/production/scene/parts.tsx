import { useEffect, useMemo, useState } from 'react';
import type { ReactNode } from 'react';
import { CanvasTexture, SRGBColorSpace } from 'three';
import { Block, palette } from '../../scene/primitives';
import type { Point } from '../../scene/primitives';

export { Block, palette };
export type { Point };
export const steel = '#7c98aa';

export function Cylinder({ position, radius = 0.5, top = radius, height = 1, color = steel,
  rotation = [0, 0, 0] }: { position: Point; radius?: number; top?: number; height?: number;
  color?: string; rotation?: Point }) {
  return <mesh position={position} rotation={rotation} castShadow receiveShadow>
    <cylinderGeometry args={[top, radius, height, 20]} />
    <meshStandardMaterial color={color} roughness={0.54} metalness={0.25} />
  </mesh>;
}

export function Label({ text, position, width = 3, accent = false }: {
  text: string; position: Point; width?: number; accent?: boolean;
}) {
  const texture = useMemo(() => {
    const canvas = document.createElement('canvas');
    canvas.width = 512; canvas.height = 80;
    const context = canvas.getContext('2d');
    if (context) {
      context.fillStyle = accent ? '#fff0e9' : '#ffffff';
      context.fillRect(0, 0, 512, 80);
      context.strokeStyle = accent ? palette.orange : palette.concrete;
      context.lineWidth = 4; context.strokeRect(2, 2, 508, 76);
      context.font = '600 29px -apple-system, BlinkMacSystemFont, Segoe UI, sans-serif';
      context.fillStyle = accent ? '#a94825' : palette.ink;
      context.textAlign = 'center'; context.textBaseline = 'middle';
      context.fillText(text, 256, 42, 486);
    }
    const result = new CanvasTexture(canvas); result.colorSpace = SRGBColorSpace;
    return result;
  }, [text, accent]);
  useEffect(() => () => texture.dispose(), [texture]);
  return <sprite position={position} scale={[width, width * 80 / 512, 1]}>
    <spriteMaterial map={texture} depthTest={false} toneMapped={false} />
  </sprite>;
}

export function Selectable({ children, onSelect, selected = false, size = [4, 0.1, 3], label,
  labelPosition = [0, 4.8, 0] }: { children?: ReactNode; onSelect: () => void; selected?: boolean;
  size?: Point; label?: string; labelPosition?: Point }) {
  const [hovered, setHovered] = useState(false);
  return <group onClick={(event) => { event.stopPropagation(); onSelect(); }}
    onPointerOver={(event) => { event.stopPropagation(); setHovered(true); }}
    onPointerOut={() => setHovered(false)}>
    <Block position={[0, 0.06, 0]} size={size} color={selected || hovered ? '#ffcfb8' : '#e3e7eb'} />
    {children}
    {label && <Label text={label} position={labelPosition} width={size[0] * 0.93} accent={selected || hovered} />}
  </group>;
}

export function Coil({ position, color = steel }: { position: Point; color?: string }) {
  return <group position={position}>
    <mesh rotation={[0, Math.PI / 2, 0]} castShadow>
      <torusGeometry args={[0.5, 0.22, 10, 24]} />
      <meshStandardMaterial color={color} roughness={0.4} metalness={0.4} />
    </mesh>
    <Block position={[0, -0.65, 0]} size={[0.8, 0.13, 1.15]} color={palette.rail} />
  </group>;
}

export function MaterialShape({ form, position, hot = false }: { form: string; position: Point; hot?: boolean }) {
  const color = hot ? palette.orange : steel;
  const normalized = form.toLowerCase();
  if (normalized.includes('coil') || ['hr', 'cr', 'gi', 'ga', 'eg', 'hgi'].includes(normalized)) return <Coil position={position} color={color} />;
  if (normalized === 'hot_metal' || normalized.includes('liquid') || normalized.includes('molten') || normalized.includes('iron')) {
    return <group position={position}><Cylinder position={[0, 0, 0]} radius={0.55} top={0.7} height={0.85} color={palette.rail} />
      <Cylinder position={[0, 0.44, 0]} radius={0.6} height={0.03} color={palette.orange} /></group>;
  }
  const size: Point = normalized.includes('slab') ? [1.6, 0.23, 0.85]
    : normalized.includes('bloom') ? [1.6, 0.55, 0.55] : normalized.includes('billet') ? [1.6, 0.25, 0.25] : [1.5, 0.15, 0.8];
  return <Block position={position} size={size} color={color} />;
}

export function Rollers({ x = 0, z = 0, count = 5, width = 1.7 }: { x?: number; z?: number; count?: number; width?: number }) {
  return <group>{Array.from({ length: count }, (_, index) => <Cylinder key={index}
    position={[x + index * 0.48, 0.58, z]} radius={0.16} height={width} rotation={[Math.PI / 2, 0, 0]} />)}</group>;
}
