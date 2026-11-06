import { useEffect, useMemo } from 'react';
import { BackSide, CanvasTexture, DoubleSide } from 'three';
import type { ReactNode } from 'react';

export const colors = { ground: '#eeeae4', base: '#dedbd5', blue: '#47799d', shadow: '#284d68', panel: '#dce3e5', steel: '#9caeb7', frame: '#45515a', hot: '#ff7b36', core: '#ffc16a', rail: '#e8ae4f', water: '#81b6c5', annealing: '#bd776a', treatment: '#8ba79c', zinc: '#b89b68' } as const;
type Point = readonly [number, number, number];
export function Box({ at = [0, 0, 0], size, color = colors.steel, glow = false }: { readonly at?: Point; readonly size: Point; readonly color?: string; readonly glow?: boolean }) {
  return <mesh position={[...at]} castShadow receiveShadow><boxGeometry args={[...size]} /><meshStandardMaterial color={color} roughness={0.48} metalness={0.35} emissive={glow ? color : '#000000'} emissiveIntensity={glow ? 0.6 : 0} /></mesh>;
}
export function Cylinder({ at = [0, 0, 0], radius, length, color = colors.steel, rotation = [Math.PI / 2, 0, 0] }: { readonly at?: Point; readonly radius: number; readonly length: number; readonly color?: string; readonly rotation?: Point }) {
  return <mesh position={[...at]} rotation={[...rotation]} castShadow receiveShadow><cylinderGeometry args={[radius, radius, length, 16]} /><meshStandardMaterial color={color} metalness={0.6} roughness={0.38} /></mesh>;
}
export function Rail({ length = 5, z = -1.35 }: { readonly length?: number; readonly z?: number }) {
  return <group>{[-length / 2, 0, length / 2].map(x => <Box key={x} at={[x, 1.25, z]} size={[0.045, 1, 0.045]} color={colors.rail} />)}{[1.1, 1.7].map(y => <Box key={y} at={[0, y, z]} size={[length, 0.045, 0.045]} color={colors.rail} />)}</group>;
}
export function RollerBed({ length = 6, width = 1.65, contactHeight = 0.905 }: { readonly length?: number; readonly width?: number; readonly contactHeight?: number }) {
  const n = Math.ceil(length / 0.28);
  return <group><Box at={[0, 0.45, 0]} size={[length, 0.6, width + 0.22]} color={colors.frame} />
    {Array.from({ length: n }, (_, i) => <Cylinder key={i} at={[-length / 2 + (i + 0.5) * length / n, 0.79, 0]} radius={contactHeight - 0.79} length={width} />)}
    {[-1, 1].map(side => <Box key={side} at={[0, 0.69, side * (width / 2 + 0.12)]} size={[length, 0.18, 0.12]} color={colors.steel} />)}
    {[-length / 2 + 0.4, length / 2 - 0.4].map(x => <Box key={x} at={[x, 0.17, 0]} size={[0.15, 0.34, width + 0.6]} color={colors.frame} />)}
  </group>;
}
export function Label({ text, at, active = false }: { readonly text: string; readonly at: Point; readonly active?: boolean }) {
  const texture = useMemo(() => {
    const canvas = document.createElement('canvas'); canvas.width = 640; canvas.height = 100;
    const context = canvas.getContext('2d');
    if (context) { context.clearRect(0, 0, 640, 100); context.font = '500 44px -apple-system, sans-serif'; context.textAlign = 'center'; context.textBaseline = 'middle'; context.fillStyle = active ? colors.shadow : colors.frame; context.fillText(text, 320, 50); }
    return new CanvasTexture(canvas);
  }, [text, active]);
  useEffect(() => () => texture.dispose(), [texture]);
  return <sprite position={[...at]} scale={[4.4, 0.69, 1]} raycast={() => null}><spriteMaterial map={texture} transparent depthTest={false} /></sprite>;
}
export function Coil({ wire = false, color = colors.steel }: { readonly wire?: boolean; readonly color?: string }) {
  if (wire) return <group>{Array.from({ length: 13 }, (_, i) => <mesh key={i} position={[0, 0, (i - 6) * 0.065]} castShadow><torusGeometry args={[0.5, 0.05, 8, 28]} /><meshStandardMaterial color={color} metalness={0.65} roughness={0.35} /></mesh>)}</group>;
  return <group>
    <mesh rotation={[Math.PI / 2, 0, 0]} castShadow receiveShadow><cylinderGeometry args={[0.7, 0.7, 1.1, 64, 1, true]} /><meshStandardMaterial color={color} metalness={0.65} roughness={0.35} /></mesh>
    <mesh rotation={[Math.PI / 2, 0, 0]}><cylinderGeometry args={[0.28, 0.28, 1.1, 48, 1, true]} /><meshStandardMaterial color={colors.frame} side={BackSide} metalness={0.6} roughness={0.45} /></mesh>
    {[-1, 1].map(side => <group key={side} position={[0, 0, side * 0.552]}><mesh castShadow><ringGeometry args={[0.28, 0.7, 64]} /><meshStandardMaterial color={color} metalness={0.6} roughness={0.42} side={DoubleSide} /></mesh>{[0.36, 0.44, 0.52, 0.6, 0.67].map(radius => <mesh key={radius} position={[0, 0, side * 0.002]}><ringGeometry args={[radius, radius + 0.004, 64]} /><meshStandardMaterial color={colors.frame} transparent opacity={0.28} side={DoubleSide} /></mesh>)}</group>)}
  </group>;
}
export function Pickable({ children, onSelect }: { readonly children: ReactNode; readonly onSelect: () => void }) {
  return <group onClick={event => { event.stopPropagation(); onSelect(); }} onPointerOver={event => { event.stopPropagation(); document.body.style.cursor = 'pointer'; }} onPointerOut={() => { document.body.style.cursor = ''; }}>{children}</group>;
}
