import { Component, useEffect, useRef, useState } from 'react';
import type { ComponentRef, ReactNode } from 'react';
import { Canvas, useThree } from '@react-three/fiber';
import { OrbitControls } from '@react-three/drei';
import { Equipment } from './Equipment';
import { equipmentStepIndex } from './equipmentSteps';
import { Block, Label, MaterialShape, palette, Selectable } from './parts';
import { sites, TransportRoads, Transports, visibleTransports } from './Transport';
import type { ProductionSceneProps } from './types';
export type { ProductionSceneProps } from './types';

const statusNames: Record<string, string> = { queued: '대기', running: '진행 중', active: '가동 중', completed: '완료', idle: '작업 없음', paused: '일시 정지' };
function Overview(props: ProductionSceneProps) {
  return <group>
    <Block position={[1, -0.18, 1]} size={[35, 0.3, 19]} color="#edf0f2" />
    <TransportRoads />
    {props.stages.map((stage, index) => {
      const point = sites[stage.id]; if (!point) return null;
      return <group key={stage.id} position={point}>
        <Selectable onSelect={() => props.onSelectStage(stage.id)} size={[7, 0.12, 5.4]}
          label={`${String(index + 1).padStart(2, '0')}  ${stage.name}`} labelPosition={[0, 0.4, Math.sign(point[2]) * 3.5]}>
          {[0, 1, 2].map((zone) => <group key={zone} position={[(zone - 1) * 2, 0.12, 0]} scale={0.68}>
            <Equipment stageId={stage.id} zone={zone} />
          </group>)}
          <Label text={`${stage.active_batches}개 진행 · ${statusNames[stage.status] ?? stage.status}`} position={[0, 0.4, 2.35]} width={4} />
        </Selectable>
        {props.materials.filter((material) => material.stage_id === stage.id && !props.transports.some((leg) => leg.status === 'in_transit' && leg.batch_id === material.id)).slice(0, 3).map((material, i) =>
          <group key={material.id} position={[(i - 1) * 1.2, 0.18, 1.6]} scale={0.52}>
            <Selectable selected={props.selectedMaterialId === material.id} size={[1.9, 0.08, 1.6]}
              onSelect={() => props.onSelectMaterial(material.id)}>
              <MaterialShape form={material.form} position={[0, 0.7, 0]} />
            </Selectable>
          </group>)}
      </group>;
    })}
  </group>;
}

function Detail(props: ProductionSceneProps & { stageId: string }) {
  const laneCount = Math.max(1, visibleTransports(props).length);
  const materials = props.materials.filter((material) => material.stage_id === props.stageId && !props.transports.some((leg) => leg.status === 'in_transit' && leg.batch_id === material.id));
  return <group>
    <Block position={[0, -0.16, 1.1 + (laneCount - 1) * 1.15]} size={[14, 0.3, 15 + (laneCount - 1) * 2.3]} color="#edf0f2" />
    <Block position={[0, 0.12, 0]} size={[11, 0.05, 0.7]} color="#cbd5db" />
    {[0, 1, 2].map((zone) => {
      const step = equipmentStepIndex(props.stageId, zone, props.stepDescriptors);
      return <group key={zone} position={[(zone - 1) * 3.5, 0.05, 0]}>
        {step >= 0 ? <Selectable onSelect={() => props.onSelectStep(step)}
          selected={props.selectedStep === step} size={[3.2, 0.08, 3.5]}>
          <Equipment stageId={props.stageId} zone={zone} detailed />
        </Selectable> : <group onClick={(event) => event.stopPropagation()}>
          <Block size={[3.2, 0.08, 3.5]} color="#e3e7eb" />
          <Equipment stageId={props.stageId} zone={zone} detailed />
          <Label text="참고 설비 · 단계 선택 없음" position={[0, 0.25, 1.8]} width={3} />
        </group>}
      </group>;
    })}
    {props.stepNames.map((name, index) => {
      const columns = Math.min(props.stepNames.length, 4);
      const x = (index % 4 - (columns - 1) / 2) * 3.2;
      return <group key={`${index}-${name}`} position={[x, 0.07, -2.8 - Math.floor(index / 4) * 0.85]}>
        <Selectable onSelect={() => props.onSelectStep(index)} selected={props.selectedStep === index}
          size={[3, 0.1, 0.6]} label={`${index + 1}. ${name}`} labelPosition={[0, 0.3, 0]} />
      </group>;
    })}
    {materials.slice(0, 8).map((material, index) => <group key={material.id}
      position={[(index % 4 - 1.5) * 2.8, 0.08, 3.1 + Math.floor(index / 4) * 1.7]}>
      <Selectable selected={props.selectedMaterialId === material.id} size={[2.4, 0.1, 1.45]}
        onSelect={() => props.onSelectMaterial(material.id)} label={material.id} labelPosition={[0, 1.5, 0]}>
        <MaterialShape form={material.form} position={[0, 0.8, 0]} />
      </Selectable>
    </group>)}
    {materials.length === 0 && <Label text="이 공정에 배치가 없습니다" position={[0, 0.5, 3.5]} width={4} />}
    <TransportRoads detail lanes={laneCount} />
  </group>;
}

function Camera({ detail, resetKey, lanes }: { detail: boolean; resetKey: number; lanes: number }) {
  const controls = useRef<ComponentRef<typeof OrbitControls>>(null);
  const { camera, size, invalidate } = useThree();
  useEffect(() => {
    const targetZ = detail ? (lanes - 1) * 1.15 + 1 : 0;
    camera.position.set(detail ? 15 : 35, detail ? 15 : 34, detail ? 18 + targetZ : 42);
    camera.zoom = Math.min(size.width / (detail ? 18 : 42), size.height / (detail ? 18 + (lanes - 1) * 2.3 : 29));
    camera.lookAt(0, 0, targetZ); camera.updateProjectionMatrix();
    controls.current?.target.set(0, 0, targetZ); controls.current?.update(); invalidate();
  }, [camera, size.width, size.height, detail, resetKey, lanes, invalidate]);
  return <OrbitControls ref={controls} makeDefault enableDamping minZoom={4} maxZoom={85}
    minPolarAngle={0.25} maxPolarAngle={Math.PI / 2.2} />;
}

function Fallback({ onFallback }: { onFallback: () => void }) {
  return <div role="status" style={{ display: 'grid', placeContent: 'center', height: '100%', minHeight: 300, textAlign: 'center' }}>
    <strong>3D 생산 화면을 사용할 수 없습니다</strong><p>생산 공정과 배치는 목록에서 계속 확인할 수 있습니다.</p>
    <button type="button" onClick={onFallback}>생산 목록 열기</button>
  </div>;
}
class Boundary extends Component<{ children: ReactNode; onFallback: () => void }, { failed: boolean }> {
  state = { failed: false };
  static getDerivedStateFromError() { return { failed: true }; }
  render() { return this.state.failed ? <Fallback onFallback={this.props.onFallback} /> : this.props.children; }
}
function Monitor({ onLost }: { onLost: () => void }) {
  const gl = useThree((s) => s.gl);
  useEffect(() => {
    const lost = (event: Event) => { event.preventDefault(); onLost(); };
    gl.domElement.addEventListener('webglcontextlost', lost);
    return () => gl.domElement.removeEventListener('webglcontextlost', lost);
  }, [gl, onLost]);
  return null;
}

export function ProductionScene(props: ProductionSceneProps) {
  const [lost, setLost] = useState(false);
  const [reduced, setReduced] = useState(() => window.matchMedia('(prefers-reduced-motion: reduce)').matches);
  useEffect(() => {
    const media = window.matchMedia('(prefers-reduced-motion: reduce)');
    const change = () => setReduced(media.matches);
    media.addEventListener('change', change); return () => media.removeEventListener('change', change);
  }, []);
  if (lost) return <Fallback onFallback={props.onFallback} />;
  return <Boundary onFallback={props.onFallback}>
    <Canvas orthographic frameloop="demand" dpr={[1, 1.5]} shadows camera={{ position: [35, 34, 42], zoom: 15, near: 0.1, far: 150 }}
      gl={{ antialias: true, alpha: false }} fallback={<Fallback onFallback={props.onFallback} />}
      style={{ width: '100%', height: '100%', background: palette.paper }}
      aria-label="대화형 생산 모형. 설비 또는 배치를 선택하세요. 드래그로 회전하고 스크롤로 확대합니다. 공정과 배치는 화면 옆 목록에서도 선택할 수 있습니다.">
      <color attach="background" args={[palette.paper]} />
      <ambientLight intensity={1.5} /><hemisphereLight args={['#ffffff', '#697582', 1.5]} />
      <directionalLight position={[-12, 26, 16]} intensity={2.3} castShadow shadow-mapSize={[1024, 1024]}
        shadow-camera-left={-27} shadow-camera-right={27} shadow-camera-top={22} shadow-camera-bottom={-22}
        shadow-camera-far={80} shadow-bias={-0.0007} />
      {props.stageId ? <Detail {...props} stageId={props.stageId} playing={props.playing && !reduced} /> : <Overview {...props} />}
      <Transports {...props} reduced={reduced} />
      <Camera detail={Boolean(props.stageId)} resetKey={props.resetKey} lanes={props.stageId ? 3 : 1} />
      <Monitor onLost={() => setLost(true)} />
    </Canvas>
  </Boundary>;
}
