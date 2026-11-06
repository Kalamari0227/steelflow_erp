import { useRef } from 'react';
import type { RefObject } from 'react';
import { useFrame } from '@react-three/fiber';
import type { Group } from 'three';
import { Box, colors, Cylinder, Rail, RollerBed } from './parts';

export type PhaseClock = { phase: number; index: number; localX: number; localZ: number; localRotation: number };
function Mill({ count = 1, clock, index, cutaway = false }: { readonly count?: number; readonly clock: RefObject<PhaseClock>; readonly index: number; readonly cutaway?: boolean }) {
  const drive = useRef<Group>(null);
  useFrame(() => { if (drive.current) drive.current.rotation.z = clock.current.index === index ? clock.current.phase * Math.PI * 18 : 0; });
  return <group>{Array.from({ length: count }, (_, i) => <group key={i} position={[(i - (count - 1) / 2) * 1.12, 0, 0]}>
    <Box at={[0, 0.15, 0]} size={[1.05, 0.3, 2.55]} color={colors.shadow} />
    {[-1, 1].map(side => <group key={side}><Box at={[0, cutaway ? 0.45 : 1.35, side * 0.98]} size={[0.65, cutaway ? 0.4 : 2.1, 0.38]} color={colors.blue} />{!cutaway && <><Cylinder at={[0, 2.52, side * 0.98]} radius={0.15} length={0.35} rotation={[0, 0, 0]} /><Box at={[0, 2.77, side * 0.98]} size={[0.48, 0.1, 0.5]} color={colors.shadow} /></>}</group>)}
    {!cutaway && <Box at={[0, 2.4, 0]} size={[0.9, 0.32, 2.3]} color={colors.blue} />}
    {[0.55, 1.24, 1.7].map(y => <group key={y}><Cylinder at={[0, y, 0]} radius={y === 1.24 ? 0.19 : 0.27} length={1.85} /><Cylinder at={[0, y, 1.27]} radius={0.19} length={0.35} color={colors.panel} /><Cylinder at={[0, y, 1.5]} radius={0.095} length={0.16} color={colors.frame} /></group>)}
    <Cylinder at={[0, 0.68, -1.65]} radius={0.36} length={0.75} color={colors.blue} />
    <group position={[0, 1.24, 1.65]} ref={i === 0 ? drive : undefined}><Box size={[0.37, 0.055, 0.05]} color={colors.frame} /><Box size={[0.055, 0.37, 0.05]} color={colors.frame} /></group>
  </group>)}</group>;
}
function Furnace({ long = false, color = colors.panel, cutaway = false }: { readonly long?: boolean; readonly color?: string; readonly cutaway?: boolean }) {
  const length = long ? 4.6 : 3.8;
  return <group>{[-1, 1].map(side => <Box key={side} at={[0, cutaway ? 0.55 : 1.45, side * 1.03]} size={[length, cutaway ? 0.6 : 2.4, 0.38]} color={color} />)}
    {cutaway ? <><Box at={[0, 2.7, -1.03]} size={[length, 0.3, 0.45]} color={color} />{[-1, 1].map(side => <Box key={side} at={[side * (length / 2 - 0.15), 1.45, -1.03]} size={[0.2, 2.4, 0.2]} color={color} />)}</> : <Box at={[0, 2.7, 0]} size={[length, 0.3, 2.5]} color={color} />}
    <Box at={[0, 0.4, 0]} size={[length, 0.2, 2.1]} color={colors.hot} glow />
    {[-1, 1].map(side => <group key={side} position={[side * length / 2, 0, 0]}><Box at={[0, 2.04, 0]} size={[0.18, 0.9, 2.4]} color={colors.steel} /><Box at={[0, 1.6, 0]} size={[0.22, 0.1, 1.9]} color={colors.hot} glow /></group>)}
    {[0, 1, 2].map(i => <group key={i}><Cylinder at={[-1.2 + i * 1.15, 3, -0.75]} radius={0.15} length={0.6} color={colors.frame} rotation={[0, 0, 0]} /><Box at={[-1.2 + i * 1.15, 2.87, 0]} size={[0.1, 0.1, 1.8]} color={colors.frame} /></group>)}
    <Rail length={length} z={1.65} />
  </group>;
}
function Cooling({ clock, index, bed = false }: { readonly clock: RefObject<PhaseClock>; readonly index: number; readonly bed?: boolean }) {
  const jets = useRef<Group>(null);
  useFrame(() => { if (jets.current) { jets.current.visible = clock.current.index === index; jets.current.scale.y = 0.9 + Math.sin(clock.current.phase * 70) * 0.1; } });
  if (bed) return <group>{Array.from({ length: 18 }, (_, i) => <Box key={i} at={[-2.5 + i * 0.3, 0.8, 0]} size={[0.08, 0.2, 3.6]} color={colors.shadow} />)}<Box at={[0, 0.3, 0]} size={[5.4, 0.45, 3.8]} color={colors.frame} /></group>;
  return <group>{Array.from({ length: 7 }, (_, i) => <group key={i} position={[-2.25 + i * 0.75, 0, 0]}><Cylinder at={[0, 1.78, 0]} radius={0.09} length={2.3} /><Cylinder at={[0, 1.17, -1.15]} radius={0.08} length={1.3} rotation={[0, 0, 0]} />{[-0.6, 0, 0.6].map(z => <Cylinder key={z} at={[0, 1.65, z]} radius={0.045} length={0.2} rotation={[0, 0, 0]} color={colors.shadow} />)}</group>)}
    <group ref={jets}>{Array.from({ length: 21 }, (_, i) => <mesh key={i} position={[-2.25 + Math.floor(i / 3) * 0.75, 1.28, ((i % 3) - 1) * 0.6]}><coneGeometry args={[0.14, 0.55, 6]} /><meshStandardMaterial color={colors.water} transparent opacity={0.38} depthWrite={false} /></mesh>)}</group>
    <Cylinder at={[0, 0.5, -1.5]} radius={0.16} length={5.4} rotation={[0, 0, Math.PI / 2]} color={colors.water} />
  </group>;
}
function Bath({ tall = false, zinc = false }: { readonly tall?: boolean; readonly zinc?: boolean }) {
  return <group><Box at={[0, 0.4, 0]} size={[4.8, 0.7, 2.7]} color={zinc ? colors.zinc : colors.treatment} /><Box at={[0, 0.78, 0]} size={[4.5, 0.04, 2.4]} color={zinc ? colors.steel : colors.water} />
    {[-1, 1].map(side => <group key={side}><Box at={[0, 0.95, side * 1.3]} size={[5, 0.55, 0.18]} color={colors.panel} /><Cylinder at={[side * 2.1, 1.1, 0]} radius={0.2} length={2.2} /><Box at={[side * 2.1, tall ? 2 : 1.4, -1.3]} size={[0.15, tall ? 3 : 1.5, 0.15]} color={colors.frame} /></group>)}
    {tall && <group><Box at={[0, 3.6, -1.3]} size={[4.5, 0.18, 0.18]} color={colors.frame} />{[-1.8, -0.6, 0.6, 1.8].map(x => <Cylinder key={x} at={[x, 3.3, 0]} radius={0.18} length={1.8} />)}</group>}
    <Rail length={4.8} z={1.65} />
  </group>;
}
function Coiler({ wire = false, contactHeight = 0.4 }: { readonly wire?: boolean; readonly contactHeight?: number }) {
  return <group><Box at={[0, 0.25, 0]} size={[2.6, 0.5, 2.7]} color={colors.blue} /><Cylinder at={[0, contactHeight + 0.7, 0]} radius={0.21} length={2.2} /><Box at={[0, 0.88 + (contactHeight - 0.4) / 2, -1.3]} size={[1, 1.3 + contactHeight - 0.4, 0.6]} color={colors.shadow} />
    <Cylinder at={[0, contactHeight + 0.8, -1.9]} radius={0.43} length={0.65} color={colors.blue} />
    <group position={[1.4, 1.2, 0]}><Cylinder radius={wire ? 0.35 : 0.17} length={1.9} /><Box at={[0, -0.45, -1.1]} size={[0.2, 0.9, 0.2]} color={colors.frame} /></group>
  </group>;
}
function Looper() {
  return <group>{[-1, 1].map(side => <group key={side}><Box at={[0, 0.2, side * 1.16]} size={[4.6, 0.25, 0.24]} color={colors.frame} />{[-2, 2].map(x => <Box key={x} at={[x, 1.9, side * 1.16]} size={[0.12, 3.4, 0.12]} color={colors.panel} />)}<Box at={[0, 3.55, side * 1.16]} size={[4.4, 0.16, 0.16]} color={colors.panel} /></group>)}
    {[-1.8, -0.6, 0.6, 1.8].map(x => <group key={x}><Cylinder at={[x, 3.15, 0]} radius={0.22} length={2.2} /><Cylinder at={[x, 1.1, 0]} radius={0.22} length={2.2} /><Cylinder at={[x, 2.1, -1.3]} radius={0.04} length={2.4} rotation={[0, 0, 0]} color={colors.frame} /></group>)}
  </group>;
}
function Gate({ cut = false, clock, index }: { readonly cut?: boolean; readonly clock: RefObject<PhaseClock>; readonly index: number }) {
  const blade = useRef<Group>(null);
  useFrame(() => { if (blade.current) blade.current.position.y = cut && clock.current.index === index ? -Math.sin(clock.current.phase * Math.PI) * 0.65 : 0; });
  return <group>{[-1, 1].map(side => <Box key={side} at={[0, 1.3, side * 1.2]} size={[0.5, 2.4, 0.45]} color={cut ? colors.rail : colors.blue} />)}<Box at={[0, 2.5, 0]} size={[0.6, 0.35, 2.8]} color={colors.frame} />
    <group ref={blade}><Box at={[0, 1.7, 0]} size={[0.12, 0.5, 2.2]} color={cut ? colors.steel : colors.panel} /></group>
    {!cut && <Box at={[0, 1.13, 0]} size={[0.03, 0.02, 2]} color={colors.water} glow />}
    <Box at={[0.75, 0.6, 1.8]} size={[0.55, 1.2, 0.4]} color={colors.panel} /><Box at={[0.75, 0.93, 2.02]} size={[0.4, 0.3, 0.03]} color={colors.shadow} />
  </group>;
}
function Truck({ clock, index }: { readonly clock: RefObject<PhaseClock>; readonly index: number }) {
  const vehicle = useRef<Group>(null);
  useFrame(() => { if (vehicle.current) { const active = clock.current.index === index; vehicle.current.position.set(active ? clock.current.localX : 0, 0, active ? clock.current.localZ : 0); vehicle.current.rotation.y = active ? clock.current.localRotation : 0; } });
  return <group ref={vehicle}><Box at={[0, 0.84, 0]} size={[4.5, 0.2, 2.2]} color={colors.blue} /><Box at={[2.65, 1.05, 0]} size={[1, 1.5, 2.1]} color={colors.panel} /><Box at={[3.16, 1.4, 0]} size={[0.025, 0.5, 1.65]} color={colors.shadow} />{[-1.3, 1.5, 2.6].flatMap(x => [-1, 1].map(z => <Cylinder key={`${x}-${z}`} at={[x, 0.4, z]} radius={0.4} length={0.25} color={colors.frame} />))}</group>;
}
function Electroplating() {
  return <group>{[-1.8, -0.6, 0.6, 1.8].map(x => <group key={x} position={[x, 0, 0]}><Box at={[0, 0.55, 0]} size={[1.05, 0.9, 2.5]} color={colors.zinc} /><Box at={[0, 1.02, 0]} size={[0.88, 0.035, 2.1]} color={colors.water} />{[-0.75, 0, 0.75].map(z => <Box key={z} at={[0, 1.4, z]} size={[0.08, 0.7, 0.08]} color={colors.steel} />)}<Box at={[0, 1.8, 0]} size={[0.1, 0.1, 2]} color={colors.rail} /></group>)}<Rail length={4.8} z={1.7} /></group>;
}
function CoatingStand() {
  return <group>{[-1, 1].map(z => <Box key={z} at={[0, 1, z]} size={[1.5, 1.7, 0.25]} color={colors.zinc} />)}{[0.72, 1.3, 1.85].map(y => <Cylinder key={y} at={[0, y, 0]} radius={0.2} length={1.9} color={y === 1.3 ? colors.water : colors.steel} />)}<Box at={[-1.5, 0.6, -1.4]} size={[1, 1.1, 0.7]} color={colors.zinc} /><Cylinder at={[-0.65, 1.45, -1.4]} radius={0.06} length={1.5} rotation={[0, 0, Math.PI / 2]} /><Box at={[0, 0.2, 0]} size={[2.7, 0.3, 2.6]} color={colors.shadow} /></group>;
}
function Caster({ clock, index }: { readonly clock: RefObject<PhaseClock>; readonly index: number }) {
  const stream = useRef<Group>(null);
  useFrame(() => { if (stream.current) stream.current.visible = clock.current.index === index; });
  return <group><group position={[-1.5, 0, 0]}><Cylinder at={[0, 2.4, 0]} radius={0.83} length={1.1} color={colors.panel} rotation={[0, 0, 0]} /><Cylinder at={[0, 2.98, 0]} radius={0.7} length={0.03} color={colors.hot} rotation={[0, 0, 0]} />{[-1, 1].map(z => <Box key={z} at={[0, 1.25, z]} size={[0.18, 2.5, 0.18]} color={colors.shadow} />)}<group ref={stream}><mesh position={[0, 1.45, 0]}><cylinderGeometry args={[0.08, 0.1, 1.5, 12]} /><meshStandardMaterial color={colors.hot} emissive={colors.hot} emissiveIntensity={1} /></mesh></group><Box at={[0, 0.95, 0]} size={[1.6, 0.2, 1.7]} color={colors.steel} /></group><group position={[1.2, 0, 0]} scale={[0.75, 0.7, 0.9]}><Mill count={2} clock={clock} index={index} /></group></group>;
}
function VacuumFurnace() {
  return <group><Cylinder at={[0, 0.2, 0]} radius={1.35} length={0.25} color={colors.shadow} rotation={[0, 0, 0]} /><Cylinder at={[0, 1.2, 0]} radius={1.05} length={1.85} color={colors.blue} rotation={[0, 0, 0]} /><Cylinder at={[0, 2.2, 0]} radius={1.24} length={0.22} color={colors.steel} rotation={[0, 0, 0]} /><Cylinder at={[0, 2.42, 0]} radius={0.65} length={0.25} color={colors.panel} rotation={[0, 0, 0]} /><Box at={[0.9, 2.8, -0.8]} size={[0.18, 0.7, 0.18]} color={colors.frame} /><Box at={[0.35, 3.1, -0.8]} size={[1.3, 0.15, 0.18]} color={colors.frame} /><Cylinder at={[1.25, 1, 0]} radius={0.13} length={1.4} color={colors.steel} rotation={[0, 0, Math.PI / 2]} /><Box at={[2.1, 0.6, 0]} size={[0.9, 1.1, 1]} color={colors.shadow} /></group>;
}
function ForgingPress({ clock, index }: { readonly clock: RefObject<PhaseClock>; readonly index: number }) {
  const ram = useRef<Group>(null);
  useFrame(() => { if (ram.current) ram.current.position.y = clock.current.index === index ? -Math.abs(Math.sin(clock.current.phase * Math.PI * 4)) * 0.7 : 0; });
  return <group>{[-1, 1].flatMap(x => [-1, 1].map(z => <Cylinder key={`${x}-${z}`} at={[x, 1.8, z]} radius={0.13} length={3.5} rotation={[0, 0, 0]} />))}<Box at={[0, 3.55, 0]} size={[2.8, 0.45, 2.7]} color={colors.blue} /><Cylinder at={[0, 3, 0]} radius={0.38} length={1.1} rotation={[0, 0, 0]} /><group ref={ram}><Box at={[0, 2.2, 0]} size={[2.2, 0.5, 1.9]} color={colors.steel} /></group><Box at={[0, 0.65, 0]} size={[2.8, 0.5, 2.7]} color={colors.shadow} /></group>;
}
export function Equipment({ kind, clock, index, contactHeight = 0.4, cutaway = false }: { readonly kind: string; readonly clock: RefObject<PhaseClock>; readonly index: number; readonly contactHeight?: number; readonly cutaway?: boolean }) {
  switch (kind) {
    case 'forging': return <ForgingPress clock={clock} index={index} />;
    case 'vacuum_annealing': return <VacuumFurnace />;
    case 'annealing': case 'decarburizing': return <group><group position={[-1.7, 0, 0]} scale={[0.48, 0.75, 0.8]}><Looper /></group><group position={[0.9, 0, 0]} scale={[0.72, 1, 1]}><Furnace color={colors.annealing} cutaway={cutaway} /></group></group>;
    case 'furnace': return <Furnace cutaway={cutaway} />;
    case 'heat_treatment': case 'alloying': return <Furnace long color={colors.annealing} cutaway={cutaway} />;
    case 'roughing': case 'bloom_mill': return <Mill count={2} clock={clock} index={index} cutaway={cutaway} />;
    case 'finishing_mill': case 'cold_mill': case 'wire_mill': return <Mill count={4} clock={clock} index={index} cutaway={cutaway} />;
    case 'leveler': case 'temper': return <Mill count={2} clock={clock} index={index} cutaway={cutaway} />;
    case 'cooling': return <Cooling clock={clock} index={index} />;
    case 'cooling_bed': return <Cooling clock={clock} index={index} bed />;
    case 'pickling': case 'electrocleaning': return <Bath />;
    case 'electroplating': return <Electroplating />;
    case 'coating': case 'oiling': return <CoatingStand />;
    case 'galvanizing': return <Bath tall zinc />;
    case 'looper': return <Looper />;
    case 'coiler': case 'uncoiler': return <Coiler contactHeight={contactHeight} />;
    case 'laying_head': return <Coiler wire contactHeight={contactHeight} />;
    case 'shear': case 'slitter': return <Gate cut clock={clock} index={index} />;
    case 'inspection': case 'grinder': return <Gate clock={clock} index={index} />;
    case 'aod': return <group><group position={[0, 1.4, 0]} rotation={[0, 0, -0.2]}><Cylinder radius={1.05} length={1.8} color={colors.frame} rotation={[0, 0, 0]} /><Cylinder at={[0, 0.95, 0]} radius={0.72} length={0.18} color={colors.steel} rotation={[0, 0, 0]} /><Cylinder at={[0, 1.06, 0]} radius={0.6} length={0.03} color={colors.hot} rotation={[0, 0, 0]} /></group>{[-1, 1].map(z => <Box key={z} at={[0, 0.7, z * 1.25]} size={[0.45, 1.4, 0.35]} color={colors.blue} />)}<Cylinder at={[0, 1.2, 0]} radius={0.16} length={3} color={colors.steel} /><Cylinder at={[1.4, 0.45, 0]} radius={0.12} length={1.5} rotation={[0, 0, Math.PI / 2]} color={colors.water} /><Cylinder at={[2.1, 0.8, 0]} radius={0.12} length={0.8} rotation={[0, 0, 0]} color={colors.water} /><Rail /></group>;
    case 'eaf': return <group><Cylinder at={[0, 1.2, 0]} radius={1.2} length={1.8} color={colors.frame} rotation={[0, 0, 0]} /><Cylinder at={[0, 2.11, 0]} radius={1.05} length={0.03} color={colors.hot} rotation={[0, 0, 0]} />{[-0.5, 0, 0.5].map(x => <Cylinder key={x} at={[x, 3, 0]} radius={0.11} length={1.7} color={colors.frame} rotation={[0, 0, 0]} />)}<Rail /></group>;
    case 'caster': return <Caster clock={clock} index={index} />;
    case 'truck_in': case 'truck_out': return <Truck clock={clock} index={index} />;
    case 'packaging': return <group><Gate clock={clock} index={index} /><Rail length={4} /></group>;
    case 'stock': return <group>{[-1, 1].map(z => <Box key={z} at={[0, 0.42, z]} size={[4.7, 0.3, 0.16]} color={colors.rail} />)}</group>;
    default: return <group><RollerBed length={4} /><Rail length={4} /></group>;
  }
}
