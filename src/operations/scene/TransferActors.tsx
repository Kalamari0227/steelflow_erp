import { useSceneHover } from './useSceneHover';
import { useRef } from 'react';
import type { RefObject } from 'react';
import { useFrame } from '@react-three/fiber';
import type { Group } from 'three';
import { useNavigationStore } from '../navigation';
import type { World } from '../../contracts';
import { Truck, Ship } from '../../scene/vehicles';
import { Block, Cylinder, palette } from '../../production/scene/parts';
import { factoryLayout } from './layout';
import { transferPose, locationPosition, transferVehiclePose } from './transferPose';
import type { TransportPose } from './transferPose';

export type TransportActorProps = { readonly world: World; readonly elapsed: RefObject<number> };
type MovingActorProps = { readonly id: string; readonly getPose: (elapsedMs: number) => TransportPose | null; readonly elapsed: RefObject<number>; readonly onSelect: () => void };
export function VehicleActor({ id, getPose, elapsed, onSelect }: MovingActorProps) {
  const body = useRef<Group>(null);
  const hover = useSceneHover(`vehicle:${id}`, body);
  const vehicle = factoryLayout.vehicles.find(row => row.id === id);
  const initial = getPose(elapsed.current);
  useFrame(() => {
    const next = getPose(elapsed.current);
    if (!body.current || !next) return;
    body.current.position.set(...next.position);
    body.current.rotation.y = next.rotationY;
  }, -1);
  if (!vehicle || !initial) return null;
  return <group ref={body} {...hover.events} name={`vehicle-${id}`} position={[...initial.position]}
    rotation={[0, initial.rotationY, 0]} userData={{ pickKind: 'vehicle', pickId: id, carrierMode: vehicle.mode }} onClick={event => { event.stopPropagation(); onSelect(); }}>
    <group position={[0, -1.25, 0]}>
    {vehicle.mode === 'flatbed' ? <Truck position={[0.6, 0.2, 0]} rotation={Math.PI} color={palette.orange} /> : vehicle.mode === 'ship' ? <group rotation={[0, Math.PI, 0]}><Ship position={[0, 0.2, 0]} /></group> : <group>
      <Block position={[0, 0.48, 0]} size={[3.2, 0.25, 1.25]} color={palette.rail} />
      {[-1.15, 1.15].flatMap(x => [-0.65, 0.65].map(z => <Cylinder key={`${x}/${z}`} position={[x, 0.3, z]} radius={0.3} height={0.18} rotation={[Math.PI / 2, 0, 0]} color={palette.ink} />))}
      {vehicle.mode === 'hot_metal_car' ? <>
        <Cylinder position={[0, 1, 0]} radius={0.54} height={2} rotation={[0, 0, Math.PI / 2]} color={palette.rail} />
        <Cylinder position={[-1.2, 1, 0]} radius={0.54} top={0.14} height={0.4} rotation={[0, 0, Math.PI / 2]} color={palette.orange} />
        <Cylinder position={[1.2, 1, 0]} radius={0.54} top={0.14} height={0.4} rotation={[0, 0, -Math.PI / 2]} color={palette.orange} />
      </> : <Cylinder position={[0, 0.93, 0]} radius={0.66} top={0.83} height={0.9} color={palette.rail} />}
    </group>}
    </group>
  </group>;
}
export function CraneActor({ id, getPose, elapsed, onSelect }: MovingActorProps) {
  const hook = useRef<Group>(null), rope = useRef<Group>(null), bridge = useRef<Group>(null);
  const crane = factoryLayout.cranes.find(row => row.id === id);
  const anchor = crane ? locationPosition(crane.location_id) : null;
  const initial = getPose(elapsed.current);
  useFrame(() => {
    const next = getPose(elapsed.current);
    if (!hook.current || !next || !anchor) return;
    hook.current.position.set(...next.position);
    if (bridge.current) bridge.current.position.z = next.position[2] - anchor[2];
    const length = anchor[1] + 5.6 - next.position[1] - 1.2;
    if (rope.current) { rope.current.position.y = 1.2 + length / 2; rope.current.scale.y = length; }
  }, -1);
  if (!initial || !anchor) return null;
  const storageCrane = /SOURCE|WAREHOUSE|PORT|CUSTOMER/.test(id);
  const width = storageCrane ? 54 : 4.8;
  const shipReach = id === 'CRANE-PORT' ? locationPosition('OPS-SHIP-EXIT')[0] - anchor[0] : 0;
  const beamRight = Math.max(width / 2, shipReach + 3);
  const beamWidth = width / 2 + beamRight;
  const beamCenter = (beamRight - width / 2) / 2;
  const ropeLength = anchor[1] + 5.6 - initial.position[1] - 1.2;
  return <group name={`crane-${id}`} onClick={event => { event.stopPropagation(); onSelect(); }}>
    <group position={[...anchor]}>
    <group ref={bridge} position={[0, 0, initial.position[2] - anchor[2]]}><Block position={[beamCenter, 5.6, 0]} size={[beamWidth, 0.3, 0.4]} color={palette.orange} /></group>
    {[-width / 2 + 0.2, width / 2 - 0.2].map(x => <group key={x}><Block position={[x, 2.8, 0]} size={[0.2, 5.6, 0.3]} color={palette.orange} />{storageCrane && <><Block position={[x, 2.8, 16]} size={[0.2, 5.6, 0.3]} color={palette.orange} /><Block position={[x, 5.6, 8]} size={[0.3, 0.3, 17]} color={palette.rail} /></>}</group>)}
    </group>
    <group ref={hook} position={[...initial.position]} userData={{ pickKind: 'vehicle', pickId: id }}>
    <group ref={rope} position={[0, 1.2 + ropeLength / 2, 0]} scale={[1, ropeLength, 1]}><Cylinder position={[0, 0, 0]} radius={0.025} height={1} color={palette.rail} /></group>
    <Block position={[0, 1.2, 0]} size={[0.7, 0.16, 0.5]} color={palette.orange} />
    {[-0.3, 0.3].map(x => <Block key={x} position={[x, 0.8, 0]} size={[0.08, 0.75, 0.12]} color={palette.rail} />)}
    </group>
  </group>;
}
export function TransferActors({ world, elapsed }: TransportActorProps) {
  const active = world.transfers.filter(row => row.status !== 'WAITING' && row.status !== 'ARRIVED' && row.mode !== 'roller');
  return <group>{active.map(transfer => <group key={transfer.id}>
    {transfer.vehicle_id && <VehicleActor id={transfer.vehicle_id} elapsed={elapsed} onSelect={() => useNavigationStore.getState().select({ run_id: world.run.id, material_id: transfer.material_id })} getPose={time => transferVehiclePose(transfer, time)} />}
    {(transfer.status === 'LOADING' || transfer.status === 'UNLOADING') && transfer.crane_id &&
      <CraneActor id={transfer.crane_id} elapsed={elapsed} onSelect={() => useNavigationStore.getState().select({ run_id: world.run.id, material_id: transfer.material_id })} getPose={time => { const material = world.materials.find(row => row.id === transfer.material_id); return material ? transferPose(material, world, time) : null; }} />}
  </group>)}</group>;
}
