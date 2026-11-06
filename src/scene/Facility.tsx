import { memo } from 'react';
import type { Selection } from '../contracts';
import { Block, palette, Pillar } from './primitives';
import type { Point } from './primitives';
import { Forklift, Gantry, Ship, Truck } from './vehicles';

function ProductionHall({ position, secondary = false }: { readonly position: Point; readonly secondary?: boolean }) {
  return <group position={position}>
    <Block position={[0, 0.02, 0]} size={[9.3, 0.18, 5.8]} color={palette.concrete} />
    <Block position={[0, 1.6, -1.8]} size={[9, 3, 1.8]} color={palette.white} />
    <Block position={[0, 2.15, -0.88]} size={[8.6, 0.65, 0.04]} color={palette.muted} />
    {[-3.6, -1.8, 0, 1.8, 3.6].map((x) => <group key={x}>
      <Block position={[x, 3.22, -1.8]} size={[1.75, 0.16, 2.2]} rotation={[0, 0, -0.2]} color={palette.roof} />
      <Block position={[x - 0.82, 3.25, -1.8]} size={[0.1, 0.48, 2.1]} color={palette.muted} />
      <Block position={[x, 1.4, -0.84]} size={[0.08, 2.6, 0.09]} color={palette.concrete} />
    </group>)}
    <Block position={[-4.1, 1.35, 0.4]} size={[0.65, 2.5, 3.6]} color={palette.white} />
    <Block position={[0, 0.4, 1.5]} size={[8, 0.55, 1.35]} color={palette.muted} />
    {Array.from({ length: 13 }, (_, index) => <mesh key={index} position={[-3.6 + index * 0.6, 0.75, 1.5]} rotation={[Math.PI / 2, 0, 0]} castShadow>
      <cylinderGeometry args={[0.12, 0.12, 1.25, 8]} />
      <meshStandardMaterial color={palette.concrete} metalness={0.35} roughness={0.55} />
    </mesh>)}
    <Block position={[-2.8, 1.4, 1.4]} size={[0.8, 1.8, 1.65]} color={secondary ? palette.teal : palette.orange} />
    <Block position={[-2.8, 1.3, 2.25]} size={[0.45, 0.6, 0.05]} color={palette.rail} />
    <Pillar position={[-3.3, 4, -2.1]} height={2.8} radius={0.25} color={palette.concrete} />
    <Pillar position={[-3.3, 5.4, -2.1]} height={0.2} radius={0.32} color={palette.rail} />
    <Block position={[3.4, 0.5, -0.25]} size={[1.2, 0.8, 1]} color={palette.muted} />
    {[-3, -1, 1, 3].map((x) => <Block key={x} position={[x, 0.13, 2.7]} size={[1, 0.02, 0.08]} color={palette.amber} />)}
  </group>;
}

function Tree({ position }: { readonly position: Point }) {
  return <group position={position}>
    <Pillar position={[0, 0.7, 0]} height={1.3} radius={0.1} color={palette.muted} />
    <mesh position={[0, 1.7, 0]} castShadow>
      <icosahedronGeometry args={[0.75, 0]} />
      <meshStandardMaterial color={palette.teal} roughness={1} />
    </mesh>
  </group>;
}

function Yard() {
  return <group>
    <Block position={[0, 0.04, -5]} size={[8, 0.12, 7]} color={palette.paper} />
    {[-3.2, 0, 3.2].map((x) => <Block key={x} position={[x, 0.11, -5]} size={[0.05, 0.025, 6.5]} color={palette.muted} />)}
    {[-7.8, -5.2, -2.6].map((z) => <group key={z}>
      <Block position={[0, 0.11, z]} size={[7.2, 0.025, 0.055]} color={palette.muted} />
      {[-1.25, 1.25].map((x) => <Block key={x} position={[x, 0.2, z + 0.4]} size={[0.12, 0.15, 1.7]} color={palette.rail} />)}
    </group>)}
    <Gantry position={[0, 0.12, -5.2]} width={7.2} depth={5.9} height={4.6} />
    <Forklift position={[-2.2, 0.1, -0.2]} rotation={0.4} />
  </group>;
}

export const Facility = memo(function Facility({ onSelect }: { readonly onSelect: (selection: Selection) => void }) {
  return <group>
    <Block position={[0, -0.5, 0]} size={[44, 0.75, 30]} color={palette.concrete} />
    <Block position={[0, -0.1, -3.5]} size={[44, 0.12, 23]} color={palette.grass} />
    <Block position={[0, -0.07, 11.25]} size={[44, 0.16, 7.5]} color={palette.water} />
    <Block position={[-4, 0, -3]} size={[34, 0.12, 19.5]} color={palette.concrete} />
    <Block position={[0, 0.08, 3.5]} size={[43, 0.1, 3]} color={palette.road} />
    <Block position={[6, 0.09, -4]} size={[3, 0.1, 17]} color={palette.road} />
    {Array.from({ length: 21 }, (_, index) => <Block key={index} position={[-20 + index * 2, 0.145, 3.5]} size={[0.9, 0.02, 0.08]} color={palette.paper} />)}
    {Array.from({ length: 8 }, (_, index) => <Block key={index} position={[6, 0.15, -11 + index * 2]} size={[0.08, 0.02, 0.9]} color={palette.paper} />)}
    <group onClick={(event) => { event.stopPropagation(); onSelect({ type: 'location', id: 'LINE-A' }); }}>
      <ProductionHall position={[-12, 0, -7]} />
    </group>
    <group onClick={(event) => { event.stopPropagation(); onSelect({ type: 'location', id: 'LINE-B' }); }}>
      <ProductionHall position={[-12, 0, 0]} secondary />
    </group>
    <group onClick={(event) => { event.stopPropagation(); onSelect({ type: 'location', id: 'YARD' }); }}><Yard /></group>
    <Block position={[10, 0.11, -5]} size={[5, 0.16, 7]} color={palette.paper} />
    {[-7.4, -5.5, -3.6].map((z) => <Block key={z} position={[10, 0.21, z]} size={[4, 0.02, 0.05]} color={palette.muted} />)}
    <group onClick={(event) => { event.stopPropagation(); onSelect({ type: 'location', id: 'DISPATCH' }); }}>
      <Truck position={[10, 0.2, -1.1]} color={palette.orange} />
    </group>
    <Truck position={[-6.4, 0.15, 3.5]} color={palette.white} />
    <group onClick={(event) => { event.stopPropagation(); onSelect({ type: 'location', id: 'CUSTOMER' }); }}>
    <Block position={[17, 0.12, -4.5]} size={[7.5, 0.2, 10]} color={palette.paper} />
    <Block position={[17, 1.7, -7.2]} size={[6, 3.2, 3]} color={palette.white} />
    <Block position={[17, 3.35, -7.2]} size={[6.4, 0.18, 3.4]} color={palette.roof} />
    <Block position={[17, 1.2, -5.66]} size={[3.4, 2.1, 0.06]} color={palette.muted} />
    </group>
    <Block position={[10, 0.16, 7.1]} size={[12, 0.5, 4]} color={palette.concrete} />
    <Block position={[10, 0.46, 8.95]} size={[12, 0.12, 0.2]} color={palette.amber} />
    <group onClick={(event) => { event.stopPropagation(); onSelect({ type: 'location', id: 'PORT' }); }}>
      <Gantry position={[10, 0.4, 7.1]} width={6} depth={3} height={7} />
    </group>
    <Block position={[10, 7.4, 10.1]} size={[0.4, 0.4, 5.5]} color={palette.orange} />
    <Pillar position={[10, 5.5, 12.1]} height={3.3} radius={0.04} />
    <Forklift position={[5.4, 0.4, 6.9]} rotation={Math.PI} />
    <group onClick={(event) => { event.stopPropagation(); onSelect({ type: 'location', id: 'SEA' }); }}>
      <Ship position={[16.5, 0, 11.5]} />
    </group>
    {[-17, -12, -7, -2].map((x) => <Tree key={x} position={[x, 0, 6.2]} />)}
    {[-10, -6, -2, 2].map((z) => <Tree key={z} position={[-20, 0, z]} />)}
    {[-18, -14, -10, -6, -2, 2, 10, 14, 18].map((x) => <Block key={x} position={[x, 0.6, -13.7]} size={[0.08, 1.1, 0.08]} color={palette.muted} />)}
    {[0.35, 0.9].map((y) => <Block key={y} position={[0, y, -13.7]} size={[41, 0.05, 0.05]} color={palette.muted} />)}
    {[-18, -12, -6, 0, 6].map((x) => <Block key={x} position={[x, 0.04, 11.5]} size={[2.3, 0.015, 0.04]} color={palette.white} />)}
  </group>;
});
