import { useContext, useEffect, useMemo, useRef, useState } from 'react';
import { Html } from '@react-three/drei';
import { useFrame, useThree } from '@react-three/fiber';
import type { ThreeEvent } from '@react-three/fiber';
import { DoubleSide, Vector3 } from 'three';
import type { Group } from 'three';
import type { Coil, Location, Selection, World } from '../contracts';
import { LabelPortalContext, palette, SiteLabel } from './primitives';
import type { Point } from './primitives';

type EntityProps = {
  readonly world: World; readonly selection: Selection | null;
  readonly onSelect: (selection: Selection) => void; readonly labels: boolean;
};

function CoilMesh({ coil, position, selected, playing, onSelect }: {
  readonly coil: Coil; readonly position: Point; readonly selected: boolean;
  readonly playing: boolean; readonly onSelect: (selection: Selection) => void;
}) {
  const [hovered, setHovered] = useState(false);
  const group = useRef<Group>(null);
  const initialPosition = useRef(position);
  const target = useMemo(() => new Vector3(...position), [position]);
  const invalidate = useThree((state) => state.invalidate);
  const reducedMotion = useMemo(() => window.matchMedia('(prefers-reduced-motion: reduce)').matches, []);
  useEffect(() => {
    if (group.current && (!playing || reducedMotion)) group.current.position.copy(target);
    invalidate();
  }, [target, playing, reducedMotion, invalidate]);
  useFrame((_, delta) => {
    if (!group.current || group.current.position.distanceToSquared(target) < 0.0001) return;
    group.current.position.lerp(target, Math.min(1, delta * 7));
    invalidate();
  });
  const color = selected ? palette.orange : hovered ? palette.teal : palette.steel;
  const hover = (event: ThreeEvent<PointerEvent>, value: boolean) => {
    event.stopPropagation();
    setHovered(value);
  };
  return <group ref={group} position={initialPosition.current} name={coil.id}
    onPointerOver={(event) => hover(event, true)} onPointerOut={(event) => hover(event, false)}
    onClick={(event) => { event.stopPropagation(); onSelect({ type: 'coil', id: coil.id }); }}>
    <group rotation={[0, Math.PI / 2, 0]}>
      <mesh castShadow receiveShadow rotation={[Math.PI / 2, 0, 0]}>
        <cylinderGeometry args={[0.47, 0.47, 0.75, 24, 1, true]} />
        <meshStandardMaterial color={color} metalness={0.55} roughness={0.38} />
      </mesh>
      {[-0.37, 0.37].map((z) => <mesh key={z} position={[0, 0, z]} castShadow>
        <torusGeometry args={[0.335, 0.135, 8, 24]} />
        <meshStandardMaterial color={color} metalness={0.45} roughness={0.5} />
      </mesh>)}
      {[-0.22, 0, 0.22].map((z) => <mesh key={z} position={[0, 0, z]}>
        <torusGeometry args={[0.471, 0.012, 4, 24]} />
        <meshStandardMaterial color={palette.concrete} metalness={0.5} roughness={0.6} />
      </mesh>)}
      <mesh rotation={[Math.PI / 2, 0, 0]}>
        <cylinderGeometry args={[0.2, 0.2, 0.72, 20, 1, true]} />
        <meshStandardMaterial color={palette.rail} side={DoubleSide} />
      </mesh>
    </group>
    {(selected || hovered) && <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, -0.46, 0]}>
      <ringGeometry args={[0.64, 0.72, 32]} />
      <meshBasicMaterial color={selected ? palette.orange : palette.teal} />
    </mesh>}
    {(selected || hovered) && <SiteLabel position={[0, 1, 0]}>{coil.id} · {(coil.weight_kg / 1000).toFixed(0)} t</SiteLabel>}
  </group>;
}

function LocationMarker({ location, selected, labels, onSelect }: {
  readonly location: Location; readonly selected: boolean; readonly labels: boolean;
  readonly onSelect: (selection: Selection) => void;
}) {
  const [hovered, setHovered] = useState(false);
  const portal = useContext(LabelPortalContext);
  return <group position={[location.x, location.y, location.z]}>
    <mesh position={[0, 0.16, 0]} rotation={[-Math.PI / 2, 0, 0]}
      onPointerOver={(event) => { event.stopPropagation(); setHovered(true); }}
      onPointerOut={() => setHovered(false)}
      onClick={(event) => { event.stopPropagation(); onSelect({ type: 'location', id: location.id }); }}>
      <ringGeometry args={[2.55, 2.62, 48]} />
      <meshBasicMaterial color={selected ? palette.orange : hovered ? palette.teal : palette.muted} transparent opacity={selected || hovered ? 1 : 0.3} />
    </mesh>
    {labels && <Html portal={portal} position={[0, location.type === 'production' ? 4.5 : 3.4, -1.8]} center>
      <button type="button" onClick={() => onSelect({ type: 'location', id: location.id })}
        aria-label={`Select location ${location.name}`} aria-pressed={selected}
        style={{ pointerEvents: 'auto', whiteSpace: 'nowrap', border: `1px solid ${palette.concrete}`, borderRadius: 6,
          padding: '4px 8px', background: selected ? '#fff0e9' : '#ffffffeb', color: palette.ink,
          font: '600 10px -apple-system, BlinkMacSystemFont, Segoe UI, sans-serif', cursor: 'pointer' }}>
        {location.name}
      </button>
    </Html>}
  </group>;
}

export function WorldEntities({ world, selection, onSelect, labels }: EntityProps) {
  const locations = useMemo(() => new Map(world.locations.map((location) => [location.id, location])), [world.locations]);
  const placements = useMemo(() => {
    const slots = new Map<string, number>();
    return new Map([...world.inventory].sort((a, b) => a.coil_id.localeCompare(b.coil_id)).map((inventory) => {
      const location = locations.get(inventory.location_id);
      const slot = slots.get(inventory.location_id) ?? 0;
      slots.set(inventory.location_id, slot + 1);
      const elevation = location?.type === 'sea' ? 1.95 : location?.type === 'port' ? 1.02 : 0.68;
      const position: Point = location ? [location.x + ((slot % 4) - 1.5) * 1.15, location.y + elevation,
        location.z + Math.floor(slot / 4) * 1.15] : [0, -10, 0];
      return [inventory.coil_id, position];
    }));
  }, [world.inventory, locations]);
  return <>
    {world.locations.map((location) => <LocationMarker key={location.id} location={location} labels={labels}
      selected={selection?.type === 'location' && selection.id === location.id} onSelect={onSelect} />)}
    {world.coils.map((coil) => {
      const position = placements.get(coil.id);
      return position && <CoilMesh key={coil.id} coil={coil} position={position} playing={world.simulation.playing}
        selected={selection?.type === 'coil' && selection.id === coil.id} onSelect={onSelect} />;
    })}
    {world.shipments.map((shipment, index) => {
      const assigned = world.shipment_coils.find((assignment) => assignment.shipment_id === shipment.id);
      const inventory = world.inventory.find((entry) => entry.coil_id === assigned?.coil_id);
      const location = locations.get(inventory?.location_id ?? '');
      if (!location) return null;
      const selected = selection?.type === 'shipment' && selection.id === shipment.id;
      return <group key={shipment.id} position={[location.x + 2.65, 1.1 + (index % 2) * 0.7, location.z + 1.8]}
        onClick={(event) => { event.stopPropagation(); onSelect({ type: 'shipment', id: shipment.id }); }}>
        <mesh castShadow>
          <boxGeometry args={[0.45, 0.45, 0.45]} />
          <meshStandardMaterial color={selected ? palette.orange : palette.teal} roughness={0.6} />
        </mesh>
        {selected && <SiteLabel position={[0, 0.7, 0]}>{shipment.id} · {shipment.status}</SiteLabel>}
      </group>;
    })}
  </>;
}
