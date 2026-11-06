import { Component, useEffect, useMemo, useRef, useState } from 'react';
import type { ComponentRef, ReactNode, RefObject } from 'react';
import { Canvas, useFrame, useThree } from '@react-three/fiber';
import { OrbitControls } from '@react-three/drei';
import { Vector3 } from 'three';
import type { Group } from 'three';
import type { JourneySnapshot, ProductDefinition } from '../contracts';
import { Equipment } from './Equipment';
import type { PhaseClock } from './Equipment';
import { makeLine, MAX_EXTRAPOLATION_MS, phasePosition, projectedPhase, stepPose } from './path';
import { Box, Coil, colors, Label, Pickable } from './parts';
import { Ribbon } from './Ribbon';

export type JourneySceneProps = {
  readonly product: ProductDefinition; readonly snapshot: JourneySnapshot;
  readonly focusedStepId: string | null; readonly followMaterial: boolean; readonly resetKey: number;
  readonly onSelectStep: (id: string) => void; readonly onSelectMaterial: () => void; readonly onFallback: () => void; readonly stale: boolean;
};
type Line = ReturnType<typeof makeLine>;
function Material({ props, line, clock, reduced }: { readonly props: JourneySceneProps; readonly line: Line; readonly clock: RefObject<PhaseClock>; readonly reduced: boolean }) {
  const root = useRef<Group>(null), flat = useRef<Group>(null), coil = useRef<Group>(null);
  const { invalidate } = useThree();
  const snapshot = props.snapshot;
  const index = Math.max(0, props.product.steps.findIndex(step => step.id === snapshot.active_step_id));
  const step = props.product.steps[index];
  const ribbon = /strip/i.test(snapshot.material.form) || ['uncoiler', 'coiler'].includes(step?.equipment_kind ?? '');
  const timing = useRef({ key: '', phase: 0, received: 0 });
  const key = `${snapshot.run_id}:${snapshot.active_step_id}`;
  useEffect(() => {
    const raw = snapshot.step_elapsed_ms / snapshot.step_duration_ms;
    timing.current = { key, phase: raw, received: performance.now() };
    invalidate();
  }, [key, snapshot.step_elapsed_ms, snapshot.step_duration_ms, snapshot.playing, snapshot.speed, props.stale, invalidate]);
  useFrame(() => {
    const moving = snapshot.playing && !props.stale && !reduced && !snapshot.completed;
    const sinceSnapshot = moving ? performance.now() - timing.current.received : 0;
    const phase = snapshot.completed ? 1 : projectedPhase(timing.current.phase * snapshot.step_duration_ms, snapshot.step_duration_ms, sinceSnapshot, snapshot.speed);
    const { position, rotation, localX, localZ, localRotation } = stepPose(line, index, phase);
    clock.current = { index, phase, localX, localZ, localRotation };
    if (root.current) { root.current.position.copy(position); root.current.rotation.y = rotation; }
    const form = snapshot.material.form.toLowerCase();
    const kind = step?.equipment_kind ?? '';
    const isCoil = form.includes('coil') || form.includes('코일') || form.includes('wire_rod');
    const winding = kind === 'coiler' || kind === 'laying_head';
    const unwinding = kind === 'uncoiler';
    const mix = winding ? Math.max(0, (phase - 0.28) / 0.72) : unwinding ? Math.max(0, 1 - phase * 1.6) : isCoil ? 1 : 0;
    if (coil.current) { coil.current.visible = mix > 0.02; coil.current.scale.setScalar(Math.max(0.05, mix)); coil.current.rotation.z = winding || unwinding ? phase * Math.PI * 5 : 0; }
    if (flat.current) {
      flat.current.visible = mix < 0.99 && !ribbon;
      const rolling = ['roughing', 'finishing_mill', 'cold_mill', 'bloom_mill', 'wire_mill'].includes(kind);
      const thin = form.includes('strip') || form.includes('sheet') || form.includes('plate') || isCoil;
      const thickness = thin ? 0.075 : form.includes('ingot') ? 0.7 : form.includes('bloom') || form.includes('billet') ? 0.36 : 0.24;
      flat.current.scale.set((thin ? 1.8 : 1) * (rolling ? 1 + phase * 0.7 : 1) * (1 - mix * 0.8), rolling ? thickness * (1 - phase * 0.7) : thickness, form.includes('wire') ? 0.07 : form.includes('billet') || form.includes('bloom') ? 0.27 : form.includes('plate') ? 1.5 : 1);
    }
    if (moving && phase < 0.97 && sinceSnapshot < MAX_EXTRAPOLATION_MS) invalidate();
  }, -2);
  const hot = ['furnace', 'roughing', 'finishing_mill', 'wire_mill', 'bloom_mill', 'heat_treatment', 'caster', 'eaf', 'aod'].includes(step?.equipment_kind ?? '') || /hot_|liquid_steel/i.test(snapshot.material.form);
  return <group ref={root}><Pickable onSelect={props.onSelectMaterial}>
    <Ribbon line={line} clock={clock} enabled={ribbon} kind={step?.equipment_kind ?? ''} hot={hot} />
    <group ref={flat}>{snapshot.material.form === 'SCRAP' ? <group>{[-0.6, 0, 0.6].map((x, i) => <group key={x} rotation={[0, i * 0.6, 0]}><Box at={[x, 0.5, i % 2 * 0.3]} size={[0.8, 1.2, 0.5]} color={colors.frame} /></group>)}</group> : snapshot.material.form === 'LIQUID_STEEL' ? <mesh position={[0, 0.45, 0]}><cylinderGeometry args={[0.65, 0.65, 0.8, 24]} /><meshStandardMaterial color={colors.hot} emissive={colors.hot} emissiveIntensity={0.8} /></mesh> : <Box at={[0, 0.5, 0]} size={[2.1, 1, 1.14]} color={hot ? colors.hot : colors.steel} glow={hot} />}</group>
    <group ref={coil} position={[0, 0.65, 0]}><Coil wire={props.product.family === 'wire_rod' || /wire/i.test(props.product.output_form)} color={hot ? colors.hot : colors.steel} /></group>
    <mesh position={[0, 3.65, 0]} renderOrder={10}><coneGeometry args={[0.13, 0.35, 16]} /><meshBasicMaterial color={colors.blue} depthTest={false} /></mesh>
    <Label text="추적 소재" at={[0, 4.1, 0]} active />
    <mesh visible={false}><boxGeometry args={[2.3, 1.4, 1.5]} /><meshBasicMaterial /></mesh>
  </Pickable></group>;
}
function Track({ line, product }: { readonly line: Line; readonly product: ProductDefinition }) {
  const stripLine = /coil/i.test(product.input_form);
  const samples = useMemo(() => Array.from({ length: line.stations.length * 22 }, (_, i) => {
    const t = i / (line.stations.length * 22 - 1); const p = line.curve.getPoint(t); const d = line.curve.getTangent(t);
    return { position: p, angle: -Math.atan2(d.z, d.x), kind: product.steps[Math.min(product.steps.length - 1, Math.floor(t * product.steps.length))]?.equipment_kind };
  }), [line, product.steps]);
  return <group>{samples.map(({ position, angle, kind }, i) => kind === 'truck_in' || kind === 'truck_out' ? <group key={i} position={[position.x, 0, position.z]} rotation={[0, angle, 0]}><Box at={[0, 0.03, 0]} size={[0.5, 0.04, 2.9]} color={colors.frame} /></group> : stripLine && kind !== 'cold_mill' ? <group key={i} position={[position.x, 0, position.z]} rotation={[0, angle, 0]}><Box at={[0, 0.08, 0]} size={[0.5, 0.05, 2.0]} color={colors.frame} />{i % 5 === 0 && <group>{[-1, 1].map(side => <Box key={side} at={[0, 0.46, side * 0.85]} size={[0.08, 0.75, 0.08]} color={colors.steel} />)}<mesh position={[0, 0.78, 0]} rotation={[Math.PI / 2, 0, 0]} castShadow><cylinderGeometry args={[0.15, 0.15, 1.7, 16]} /><meshStandardMaterial color={colors.steel} metalness={0.6} roughness={0.4} /></mesh></group>}</group> : <group key={i} position={[position.x, 0, position.z]} rotation={[0, angle, 0]}><Box at={[0, 0.36, 0]} size={[0.48, 0.32, 1.9]} color={colors.frame} /><mesh position={[0, 0.78, 0]} rotation={[Math.PI / 2, 0, 0]} castShadow receiveShadow><cylinderGeometry args={[0.1, 0.1, 1.7, 10]} /><meshStandardMaterial color={colors.steel} metalness={0.6} roughness={0.4} /></mesh></group>)}</group>;
}
function Camera({ props, line, clock }: { readonly props: JourneySceneProps; readonly line: Line; readonly clock: RefObject<PhaseClock> }) {
  const controls = useRef<ComponentRef<typeof OrbitControls>>(null);
  const { camera, size, invalidate } = useThree();
  const previous = useRef(new Vector3());
  const previousStep = useRef(props.snapshot.active_step_id);
  useEffect(() => {
    const focusedIndex = props.product.steps.findIndex(step => step.id === props.focusedStepId);
    const station = line.stations[focusedIndex];
    const target = station ? new Vector3(...station.position) : new Vector3();
    camera.position.copy(target).add(new Vector3(13, 24, 29));
    camera.zoom = Math.min(size.width / (station ? 12 : line.width * 1.05), size.height / (station ? 10 : line.depth * 1.06));
    camera.lookAt(target); camera.updateProjectionMatrix(); controls.current?.target.copy(target); controls.current?.update();
    previous.current.copy(line.curve.getPoint(phasePosition(clock.current.index, clock.current.phase, props.product.steps.length)));
    invalidate();
  }, [camera, size.width, size.height, props.product.id, props.focusedStepId, props.resetKey, line, invalidate, clock, props.product.steps]);
  useEffect(() => {
    if (props.followMaterial && !props.focusedStepId && controls.current) {
      const index = Math.max(0, props.product.steps.findIndex(step => step.id === props.snapshot.active_step_id));
      const point = line.curve.getPoint(phasePosition(index, props.snapshot.step_elapsed_ms / props.snapshot.step_duration_ms, props.product.steps.length));
      camera.position.add(point.clone().sub(controls.current.target)); controls.current.target.copy(point); controls.current.update(); previous.current.copy(point); invalidate();
    }
  }, [props.followMaterial, props.focusedStepId, props.product.id, props.resetKey, camera, line, invalidate]);
  useFrame(() => {
    const p = line.curve.getPoint(phasePosition(clock.current.index, clock.current.phase, props.product.steps.length));
    const jumped = previousStep.current !== props.snapshot.active_step_id && !props.snapshot.playing;
    if (props.followMaterial && !props.focusedStepId && controls.current && !jumped) { const delta = p.clone().sub(previous.current); camera.position.add(delta); controls.current.target.add(delta); controls.current.update(); }
    previousStep.current = props.snapshot.active_step_id;
    previous.current.copy(p);
  });
  return <OrbitControls ref={controls} makeDefault enableDamping={false} minZoom={4} maxZoom={100} minPolarAngle={0.2} maxPolarAngle={Math.PI / 2.15} />;
}
function Model({ props, reduced }: { readonly props: JourneySceneProps; readonly reduced: boolean }) {
  const line = useMemo(() => makeLine(props.product.steps.length), [props.product.steps.length]);
  const clock = useRef<PhaseClock>({ index: 0, phase: 0, localX: 0, localZ: 0, localRotation: 0 });
  return <group><Box at={[0, -0.3, 0]} size={[line.width, 0.5, line.depth]} color={colors.base} />
    <Track line={line} product={props.product} />
    <Material props={props} line={line} clock={clock} reduced={reduced} />
    {props.product.steps.map((step, i) => { const station = line.stations[i]; if (!station) return null; return <group key={step.id} position={[...station.position]} rotation={[0, station.rotation, 0]}>
      <Pickable onSelect={() => props.onSelectStep(step.id)}><Equipment kind={step.equipment_kind} clock={clock} index={i} /></Pickable>
      <Label text={`${String(i + 1).padStart(2, '0')}  ${step.name}`} at={[0, 0.2, Math.cos(station.rotation) * 2.8]} active={step.id === props.snapshot.active_step_id} />
      <mesh position={[0, 0.07, 0]} rotation={[-Math.PI / 2, 0, 0]}><planeGeometry args={[5.8, 4.3]} /><meshStandardMaterial color={step.id === props.snapshot.active_step_id ? colors.panel : colors.base} roughness={0.9} /></mesh>
    </group>; })}
    <Camera props={props} line={line} clock={clock} />
  </group>;
}
function Fallback({ onFallback }: { readonly onFallback: () => void }) {
  return <div role="status" style={{ display: 'grid', placeContent: 'center', height: '100%', minHeight: 360, textAlign: 'center' }}><strong>3D 제조 모형을 사용할 수 없습니다</strong><p>공정 목록에서 소재의 이동과 변환을 확인할 수 있습니다.</p><button type="button" onClick={onFallback}>2D 공정 보기</button></div>;
}
class Boundary extends Component<{ readonly children: ReactNode; readonly onFallback: () => void }, { failed: boolean }> {
  state = { failed: false };
  static getDerivedStateFromError() { return { failed: true }; }
  render() { return this.state.failed ? <Fallback onFallback={this.props.onFallback} /> : this.props.children; }
}
function Monitor({ onLost }: { readonly onLost: () => void }) {
  const gl = useThree(s => s.gl);
  useEffect(() => { const lost = (event: Event) => { event.preventDefault(); onLost(); }; gl.domElement.addEventListener('webglcontextlost', lost); return () => gl.domElement.removeEventListener('webglcontextlost', lost); }, [gl, onLost]);
  return null;
}
export function JourneyScene(props: JourneySceneProps) {
  const [lost, setLost] = useState(false);
  const [reduced, setReduced] = useState(() => window.matchMedia('(prefers-reduced-motion: reduce)').matches);
  useEffect(() => { const media = window.matchMedia('(prefers-reduced-motion: reduce)'); const update = () => setReduced(media.matches); media.addEventListener('change', update); return () => media.removeEventListener('change', update); }, []);
  if (lost) return <Fallback onFallback={props.onFallback} />;
  return <Boundary onFallback={props.onFallback}><Canvas orthographic frameloop="demand" dpr={[1, 1.5]} shadows camera={{ position: [13, 24, 29], zoom: 20, near: 0.1, far: 200 }} gl={{ antialias: true, alpha: false }} style={{ width: '100%', height: '100%' }} fallback={<Fallback onFallback={props.onFallback} />} aria-label={`${props.product.name} 제조 미니어처. 소재와 설비를 선택할 수 있습니다. 드래그로 회전, 스크롤로 확대합니다.`}>
    <color attach="background" args={[colors.ground]} /><ambientLight intensity={1.3} /><hemisphereLight args={[colors.panel, colors.base, 1.5]} />
    <directionalLight position={[-15, 30, 12]} intensity={3} castShadow shadow-mapSize={[2048, 2048]} shadow-camera-left={-35} shadow-camera-right={35} shadow-camera-top={30} shadow-camera-bottom={-30} shadow-camera-far={100} shadow-bias={-0.0003} shadow-normalBias={0.03} />
    <Model props={props} reduced={reduced} /><Monitor onLost={() => setLost(true)} />
  </Canvas></Boundary>;
}
