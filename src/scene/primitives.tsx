import { createContext, useContext } from 'react';
import type { ReactNode, RefObject } from 'react';
import { Html } from '@react-three/drei';

export const palette = {
  paper: '#f6f7f9', concrete: '#e3e7eb', ink: '#202a35', muted: '#697582',
  white: '#ffffff', roof: '#697582', steel: '#697582', road: '#697582',
  orange: '#e86c42', teal: '#278b78', grass: '#e8f4ee', water: '#e8f4ee',
  amber: '#be8527', critical: '#c15345', rail: '#202c36',
} as const;

export type Point = [number, number, number];
export const LabelPortalContext = createContext<RefObject<HTMLElement> | undefined>(undefined);

export function Block({ position = [0, 0, 0], size, color = palette.concrete, rotation = [0, 0, 0], children }: {
  readonly position?: Point; readonly size: Point; readonly color?: string;
  readonly rotation?: Point; readonly children?: ReactNode;
}) {
  return <mesh position={position} rotation={rotation} castShadow receiveShadow>
    <boxGeometry args={size} />
    <meshStandardMaterial color={color} roughness={0.85} />
    {children}
  </mesh>;
}

export function Pillar({ position, radius = 0.12, height, color = palette.rail }: {
  readonly position: Point; readonly radius?: number; readonly height: number; readonly color?: string;
}) {
  return <mesh position={position} castShadow receiveShadow>
    <cylinderGeometry args={[radius, radius, height, 12]} />
    <meshStandardMaterial color={color} roughness={0.8} />
  </mesh>;
}

export function SiteLabel({ position, children }: { readonly position: Point; readonly children: ReactNode }) {
  const portal = useContext(LabelPortalContext);
  return <Html portal={portal} position={position} center style={{ pointerEvents: 'none', whiteSpace: 'nowrap' }}>
    <span style={{ display: 'block', color: palette.ink, background: '#ffffffeb', padding: '4px 8px',
      border: `1px solid ${palette.concrete}`, borderRadius: 6, fontSize: 10, fontWeight: 650,
      fontFamily: '-apple-system, BlinkMacSystemFont, Segoe UI, sans-serif', letterSpacing: '0.02em' }}>
      {children}
    </span>
  </Html>;
}
