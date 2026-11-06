import { Block, palette, Pillar } from './primitives';
import type { Point } from './primitives';

function Wheels({ length = 2.4, width = 1.25 }: { readonly length?: number; readonly width?: number }) {
  return <>{[-length / 2, length / 2].flatMap((x) => [-width / 2, width / 2].map((z) =>
    <mesh key={`${x}-${z}`} position={[x, 0.37, z]} rotation={[Math.PI / 2, 0, 0]} castShadow>
      <cylinderGeometry args={[0.34, 0.34, 0.2, 12]} />
      <meshStandardMaterial color={palette.rail} roughness={0.9} />
    </mesh>))}</>;
}

export function Truck({ position, rotation = 0, color = palette.white }: {
  readonly position: Point; readonly rotation?: number; readonly color?: string;
}) {
  return <group position={position} rotation={[0, rotation, 0]}>
    <Block position={[0, 0.7, 0]} size={[4.3, 0.35, 1.4]} color={palette.rail} />
    <Block position={[-1.6, 1.35, 0]} size={[1.25, 1.3, 1.45]} color={color} />
    <Block position={[-2.24, 1.55, 0]} size={[0.025, 0.6, 1.2]} color={palette.rail} />
    <Block position={[-1.65, 1.6, 0.735]} size={[0.7, 0.5, 0.03]} color={palette.muted} />
    <Block position={[-1.65, 1.6, -0.735]} size={[0.7, 0.5, 0.03]} color={palette.muted} />
    <Block position={[0.6, 0.97, 0]} size={[2.9, 0.15, 1.4]} color={palette.concrete} />
    <Wheels length={3.1} />
    {[-0.52, 0.52].map((z) => <Block key={z} position={[-2.24, 1, z]} size={[0.04, 0.18, 0.22]} color={palette.paper} />)}
  </group>;
}

export function Forklift({ position, rotation = 0 }: { readonly position: Point; readonly rotation?: number }) {
  return <group position={position} rotation={[0, rotation, 0]}>
    <Block position={[0, 0.65, 0]} size={[1.7, 0.7, 1.15]} color={palette.orange} />
    <Wheels length={1.2} width={1.05} />
    <Block position={[-0.3, 1.13, 0]} size={[0.5, 0.45, 0.65]} color={palette.rail} />
    {[-0.52, 0.52].map((z) => <Block key={z} position={[0.3, 1.6, z]} size={[0.09, 1.5, 0.09]} color={palette.rail} />)}
    <Block position={[0, 2.3, 0]} size={[1.4, 0.13, 1.3]} color={palette.orange} />
    {[-0.42, 0.42].map((z) => <group key={z}>
      <Block position={[1, 1.05, z]} size={[0.13, 2, 0.13]} color={palette.rail} />
      <Block position={[1.55, 0.2, z]} size={[1.25, 0.12, 0.2]} color={palette.rail} />
    </group>)}
  </group>;
}

export function Gantry({ position, width = 6, depth = 4, height = 6 }: {
  readonly position: Point; readonly width?: number; readonly depth?: number; readonly height?: number;
}) {
  return <group position={position}>
    {[-width / 2, width / 2].flatMap((x) => [-depth / 2, depth / 2].map((z) => <group key={`${x}-${z}`}>
      <Block position={[x, height / 2, z]} size={[0.28, height, 0.28]} color={palette.orange} />
      <Block position={[x, 0.2, z]} size={[0.65, 0.3, 0.8]} color={palette.rail} />
    </group>))}
    {[-depth / 2, depth / 2].map((z) => <Block key={z} position={[0, height, z]} size={[width + 1, 0.45, 0.45]} color={palette.orange} />)}
    {[-width / 2, width / 2].map((x) => <Block key={x} position={[x, height, 0]} size={[0.4, 0.4, depth]} color={palette.orange} />)}
    <Block position={[0, height - 0.1, 0]} size={[0.65, 0.5, depth]} color={palette.rail} />
    <Pillar position={[0, height - 1.1, 0]} radius={0.035} height={1.7} />
    <Block position={[0, height - 2, 0]} size={[0.5, 0.25, 0.45]} color={palette.orange} />
  </group>;
}

export function Ship({ position }: { readonly position: Point }) {
  return <group position={position}>
    <mesh position={[0, 0.35, 0]} castShadow>
      <cylinderGeometry args={[1, 0.8, 0.9, 6]} />
      <meshStandardMaterial color={palette.rail} roughness={0.85} />
    </mesh>
    <Block position={[0, 0.45, 0]} size={[8.5, 0.9, 3.3]} color={palette.rail} />
    <Block position={[0, 0.94, 0]} size={[8.1, 0.12, 3.05]} color={palette.concrete} />
    <mesh position={[-4.3, 0.45, 0]} rotation={[0, Math.PI / 2, 0]} scale={[1.65, 1, 1.4]} castShadow>
      <cylinderGeometry args={[1, 0.8, 0.9, 3]} />
      <meshStandardMaterial color={palette.rail} roughness={0.85} />
    </mesh>
    <Block position={[3, 1.7, 0]} size={[1.7, 1.5, 2.6]} color={palette.white} />
    <Block position={[3, 2.7, 0]} size={[1.9, 0.5, 2.8]} color={palette.white} />
    <Block position={[2.03, 2.72, 0]} size={[0.03, 0.22, 2.5]} color={palette.rail} />
    <Block position={[3.4, 3.4, 0.5]} size={[0.55, 0.9, 0.55]} color={palette.orange} />
    <Pillar position={[2.7, 3.8, -0.5]} height={2} radius={0.04} />
    {[-1.55, 1.55].map((z) => <Block key={z} position={[0, 1.13, z]} size={[7.8, 0.22, 0.1]} color={palette.white} />)}
    {[-2.9, -0.4].map((x) => <Block key={x} position={[x, 1.2, 0]} size={[2.1, 0.5, 2.7]} color={palette.muted} />)}
  </group>;
}
