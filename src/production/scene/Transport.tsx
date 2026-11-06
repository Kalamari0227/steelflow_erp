import { useEffect, useRef } from 'react';
import { useFrame, useThree } from '@react-three/fiber';
import type { Group } from 'three';
import type { ProductionTransport } from '../contracts';
import { Block, Cylinder, Label, MaterialShape, palette } from './parts';
import type { Point } from './parts';
import type { ProductionSceneProps } from './types';

export const sites: Record<string, Point> = {
  ironmaking: [-12, 0, -5], steelmaking: [-4, 0, -5], casting: [4, 0, -5], hot_rolling: [12, 0, -5],
  cold_rolling: [12, 0, 5], coating: [4, 0, 5], finishing: [-4, 0, 5], stock: [-12, 0, 5],
};

export function transportRoute(leg: ProductionTransport, detail: string | null, lane = 0): readonly Point[] {
  if (detail) return [[-5.5, 0.18, 6.6 + lane * 2.3], [5.5, 0.18, 6.6 + lane * 2.3]];
  const from = sites[leg.from_stage]; const to = sites[leg.to_stage];
  if (!from || !to) return [];
  return [[from[0], 0.18, Math.sign(from[2]) * 1.7], [from[0], 0.18, 0],
    [to[0], 0.18, 0], [to[0], 0.18, Math.sign(to[2]) * 1.7]];
}

function routePose(points: readonly Point[], progress: number) {
  const lengths = points.slice(1).map((to, i) => {
    const from = points[i]; return from ? Math.hypot(to[0] - from[0], to[2] - from[2]) : 0;
  });
  let remaining = lengths.reduce((sum, length) => sum + length, 0) * progress;
  for (let i = 0; i < lengths.length; i++) {
    const length = lengths[i]; const from = points[i]; const to = points[i + 1];
    if (!from || !to || !length) continue;
    if (remaining <= length || i === lengths.length - 1) {
      const ratio = Math.min(1, remaining / length);
      return { position: [from[0] + (to[0] - from[0]) * ratio, from[1], from[2] + (to[2] - from[2]) * ratio] satisfies Point,
        angle: -Math.atan2(to[2] - from[2], to[0] - from[0]) };
    }
    remaining -= length;
  }
  return { position: points[0] ?? [0, 0, 0] satisfies Point, angle: 0 };
}

export function TransportRoads({ detail = false, lanes = 1 }: { readonly detail?: boolean; readonly lanes?: number }) {
  if (detail) return <group>{Array.from({ length: Math.max(1, lanes) }, (_, index) =>
    <Block key={index} position={[0, 0.1, 6.6 + index * 2.3]} size={[12, 0.08, 1.8]} color="#697582" />)}</group>;
  return <group>
    <Block position={[0, 0.1, 0]} size={[27, 0.08, 1.7]} color="#697582" />
    {[-12, -4, 4, 12].map((x) => <Block key={x} position={[x, 0.1, 0]} size={[1.7, 0.08, 4.2]} color="#697582" />)}
    {Array.from({ length: 13 }, (_, index) => <Block key={index} position={[(index - 6) * 2, 0.15, 0]}
      size={[0.7, 0.02, 0.06]} color={palette.paper} />)}
  </group>;
}

function Vehicle({ leg }: { readonly leg: ProductionTransport }) {
  const specialist = leg.vehicle_kind !== 'flatbed_truck';
  return <group>
    <Block position={[-0.35, 0.48, 0]} size={[2.8, 0.2, 1.1]} color={palette.rail} />
    {[-1.35, -0.8, 0.6, 1.25].flatMap((x) => [-0.59, 0.59].map((z) =>
      <Cylinder key={`${x}-${z}`} position={[x, 0.32, z]} radius={0.3} height={0.18}
        rotation={[Math.PI / 2, 0, 0]} color={palette.ink} />))}
    {specialist ? <>
      <Block position={[1.12, 0.7, 0]} size={[0.7, 0.55, 0.8]} color={palette.orange} />
      {leg.vehicle_kind === 'hot_metal_car' ? <group position={[-0.45, 1, 0]}>
        <Cylinder position={[0, 0, 0]} radius={0.58} height={1.6} rotation={[0, 0, Math.PI / 2]} color={palette.rail} />
        <Cylinder position={[-1, 0, 0]} radius={0.58} top={0.18} height={0.4} rotation={[0, 0, Math.PI / 2]} color={palette.rail} />
        <Cylinder position={[1, 0, 0]} radius={0.58} top={0.18} height={0.4} rotation={[0, 0, -Math.PI / 2]} color={palette.rail} />
        <Cylinder position={[0, 0.58, 0]} radius={0.26} height={0.14} color={palette.orange} />
        <Block position={[-0.7, -0.35, 0]} size={[0.16, 0.8, 1.15]} color={palette.orange} />
        <Block position={[0.7, -0.35, 0]} size={[0.16, 0.8, 1.15]} color={palette.orange} />
      </group> : <MaterialShape form={leg.material_form} position={[-0.4, 1.05, 0]} hot />}
    </> : <>
      <Block position={[1.15, 0.98, 0]} size={[0.85, 1.05, 1.1]} color={palette.orange} />
      <Block position={[1.59, 1.18, 0]} size={[0.03, 0.37, 0.85]} color={palette.ink} />
      {[-0.57, 0.57].map((z) => <Block key={z} position={[1.13, 1.2, z]} size={[0.5, 0.35, 0.02]} color={palette.ink} />)}
      <MaterialShape form={leg.material_form} position={[-0.5, 1.15, 0]} />
    </>}
  </group>;
}

function Carrier({ leg, reduced, lane, convoyIndex, convoyCount, ...props }: ProductionSceneProps & { readonly leg: ProductionTransport; readonly reduced: boolean; readonly lane: number; readonly convoyIndex: number; readonly convoyCount: number }) {
  const body = useRef<Group>(null);
  const offset = (convoyIndex - (convoyCount - 1) / 2) * 0.28;
  const limit = 0.94 - (convoyCount - convoyIndex - 1) * 0.28;
  const progress = useRef(props.playing && !reduced ? 0.08 + convoyIndex * 0.28 : 0.5 + offset);
  const firstFrame = useRef(true);
  const invalidate = useThree((state) => state.invalidate);
  const points = transportRoute(leg, props.stageId, lane);
  const pose = routePose(points, progress.current);
  useEffect(() => { firstFrame.current = true; invalidate(); }, [props.playing, props.speed, reduced, invalidate]);
  useFrame((_, delta) => {
    if (!props.playing || reduced || !body.current || progress.current >= limit) return;
    if (firstFrame.current) { firstFrame.current = false; invalidate(); return; }
    progress.current = Math.min(limit, progress.current + Math.min(delta, 0.1) * props.speed /
      (props.tickDurationSeconds * Math.max(1, leg.end_tick - leg.start_tick)));
    const next = routePose(points, progress.current);
    body.current.position.set(...next.position); body.current.rotation.y = next.angle;
    invalidate();
  });
  const from = props.stages.find((stage) => stage.id === leg.from_stage)?.name ?? leg.from_stage;
  const to = props.stages.find((stage) => stage.id === leg.to_stage)?.name ?? leg.to_stage;
  return <group>
    <group ref={body} position={pose.position} rotation={[0, pose.angle, 0]} scale={props.stageId ? 0.9 : 0.68}
      name={`transport-${leg.id}`} userData={{ transportId: leg.id, batchId: leg.batch_id }}
      onClick={(event) => { event.stopPropagation(); props.onSelectMaterial(leg.batch_id); }}>
      <Block position={[0, 0.02, 0]} size={[3.6, 0.03, 1.5]} color={props.selectedMaterialId === leg.batch_id ? '#ffcfb8' : '#697582'} />
      <Vehicle leg={leg} />
      <Label text={`${leg.batch_id} · ${leg.material_form}`} position={[0, 2.25, 0]} width={4.6} />
    </group>
    {props.stageId && <Label text={`${leg.to_stage === props.stageId ? '입고' : '출고'} · ${from} → ${to}`}
      position={[0, 0.1, 8.4 + lane * 2.3]} width={5} />}
  </group>;
}

export function visibleTransports(props: ProductionSceneProps) {
  return props.transports.filter((leg) => leg.status === 'in_transit' &&
    (!props.stageId || leg.from_stage === props.stageId || leg.to_stage === props.stageId));
}

export function Transports(props: ProductionSceneProps & { readonly reduced: boolean }) {
  const visible = visibleTransports(props);
  return <group>{visible.map((leg, lane) => {
    const convoy = props.stageId ? [leg] : visible.filter((other) => other.from_stage === leg.from_stage && other.to_stage === leg.to_stage);
    return <Carrier key={`${props.runId}:${leg.id}`} {...props} leg={leg} lane={lane}
      convoyIndex={convoy.findIndex((other) => other.id === leg.id)} convoyCount={convoy.length} />;
  })}</group>;
}
