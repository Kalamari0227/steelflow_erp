import { Component, memo, useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react';
import type { ReactNode, RefObject } from 'react';
import { Canvas, useFrame, useThree } from '@react-three/fiber';
import { PCFSoftShadowMap, WebGLRenderer } from 'three';
import { isQaProbeEnabled, QaProbe } from './qaProbe';
import type { World } from '../../contracts';
import type { OperationsSceneProps } from '../OperationsWorkspace';
import { useWorldStore, renderElapsed } from '../../store';
import { colors } from '../../journey/scene/parts';
import { ProcessStations } from './ProcessStations';
import { MaterialMesh } from './MaterialMesh';
import { CameraRig } from './CameraRig';
import { CameraToolbar } from './CameraToolbar';
import type { CameraCommand } from './cameraControls';
import { TransferActors } from './TransferActors';
import { LogisticsActors } from './LogisticsActors';

class SceneBoundary extends Component<{ readonly children: ReactNode; readonly onFallback: () => void }, { readonly failed: boolean }> {
  state = { failed: false };
  static getDerivedStateFromError() { return { failed: true }; }
  componentDidCatch() { this.props.onFallback(); }
  render() { return this.state.failed ? <p role="alert">3D 장면을 표시하지 못했습니다. 2D 운영 화면으로 전환합니다.</p> : this.props.children; }
}
function SceneFrame({ props, worldRef, elapsed, reduced }: { readonly props: OperationsSceneProps; readonly worldRef: RefObject<World>; readonly elapsed: RefObject<number>; readonly reduced: boolean }) {
  const { invalidate, gl, scene, camera } = useThree();
  // Publish only with the R3F commit that installs this snapshot’s mesh forms.
  useLayoutEffect(() => { worldRef.current = props.world; }, [props.world, worldRef]);
  const stale = useWorldStore(state => state.stale);
  const receivedAt = useWorldStore(state => state.receivedAt);
  const wake = props.world.run.playing ? receivedAt : null;
  useEffect(() => { invalidate(); }, [props.world.run.id, props.world.run.revision, stale, wake, reduced, invalidate]);
  const [probe] = useState(() => {
    // Navigation canonicalizes its own query before this lazy scene mounts. The document opt-in is stable.
    const documentUrl = performance.getEntriesByType('navigation')[0]?.name ?? window.location.href;
    return new QaProbe(isQaProbeEnabled(new URL(documentUrl).search, import.meta.env.VITE_STEELFLOW_QA_PROBE === '1'));
  });
  useEffect(() => {
    const canvas = gl.domElement;
    canvas.setAttribute('aria-label', '통합 공장 3D 미니어처');
  }, [gl]);
  useFrame(() => {
    const now = Date.now();
    elapsed.current = reduced ? props.world.run.elapsed_ms : renderElapsed({ world: props.world, stale, receivedAt }, now);
    if (props.world.run.playing && !stale && !reduced && receivedAt !== null && now - receivedAt < 350) invalidate();
  }, -3);
  useFrame(() => {
    if (probe.enabled) probe.observeLegacy({ gl, scene, camera, world: props.world, elapsedMs: elapsed.current, reduced, stale });
  });
  return null;
}
type CanvasBinding = {
  readonly canvas: HTMLCanvasElement;
  readonly renderer: WebGLRenderer;
  readonly onLost: (event: Event) => void;
  adopted: boolean;
};

function releaseCanvasBinding(binding: CanvasBinding): void {
  binding.canvas.removeEventListener('webglcontextlost', binding.onLost);
  if (!binding.adopted) {
    binding.renderer.dispose();
    binding.renderer.forceContextLoss();
  }
}

export function useReducedMotion(): boolean {
  const [reduced, setReduced] = useState(() => window.matchMedia('(prefers-reduced-motion: reduce)').matches);
  useEffect(() => {
    const query = window.matchMedia('(prefers-reduced-motion: reduce)');
    const change = () => setReduced(query.matches);
    query.addEventListener('change', change);
    change();
    return () => query.removeEventListener('change', change);
  }, []);
  return reduced;
}

export const OperationsScene = memo(function OperationsScene(props: OperationsSceneProps) {
  const [cameraCommand, setCameraCommand] = useState<CameraCommand | null>(null);
  const elapsed = useRef(props.world.run.elapsed_ms);
  const worldRef = useRef(props.world);
  const canvasBinding = useRef<CanvasBinding | null>(null);
  const bindCanvas = useCallback((canvas: HTMLCanvasElement | null): void => {
    if (!canvas || canvasBinding.current?.canvas === canvas) return;
    if (canvasBinding.current) releaseCanvasBinding(canvasBinding.current);
    const renderer = new WebGLRenderer({ canvas, antialias: true, alpha: true, powerPreference: 'high-performance', preserveDrawingBuffer: true });
    renderer.shadowMap.type = PCFSoftShadowMap;
    const onLost = (event: Event): void => {
      event.preventDefault();
      if (canvas.isConnected) props.onFallback();
    };
    canvas.addEventListener('webglcontextlost', onLost);
    canvasBinding.current = { canvas, renderer, onLost, adopted: false };
  }, [props.onFallback]);
  const adoptRenderer = useCallback((): WebGLRenderer => {
    const binding = canvasBinding.current;
    if (!binding) throw new Error('The native canvas must attach before renderer configuration');
    binding.adopted = true;
    if (binding.renderer.getContext().isContextLost()) props.onFallback();
    return binding.renderer;
  }, [props.onFallback]);
  useEffect(() => () => {
    const binding = canvasBinding.current;
    if (binding && !binding.canvas.isConnected) {
      releaseCanvasBinding(binding);
      canvasBinding.current = null;
    }
  }, []);
  const [webglAvailable, setWebglAvailable] = useState<boolean | null>(null);
  const reduced = useReducedMotion();
  useEffect(() => {
    try {
      const probe = document.createElement('canvas').getContext('webgl2');
      setWebglAvailable(probe !== null);
      probe?.getExtension('WEBGL_lose_context')?.loseContext();
    } catch (error) {
      if (!(error instanceof DOMException)) throw error;
      setWebglAvailable(false);
    }
  }, []);
  useEffect(() => { if (webglAvailable === false) props.onFallback(); }, [webglAvailable, props.onFallback]);
  if (webglAvailable !== true) return <p role="status">{webglAvailable === null ? '3D 표시 기능을 확인하는 중입니다.' : '3D 장면을 사용할 수 없어 2D 운영 자료를 엽니다.'}</p>;
  return <SceneBoundary onFallback={props.onFallback}><div className="ops-scene-viewport"><div className="ops-scene-canvas"><Canvas ref={bindCanvas} orthographic shadows dpr={[1, 1.5]} frameloop="demand" camera={{ position: [100, 160, 180], zoom: 2, near: 0.1, far: 1500 }} gl={adoptRenderer} fallback={<p>3D 표시를 지원하지 않는 브라우저입니다.</p>}>
    <color attach="background" args={['#d9e5e6']} /><ambientLight intensity={0.38} /><hemisphereLight args={['#e5f4ff', '#b8a17e', 1.15]} /><directionalLight position={[-160, 320, 220]} color="#fff1d4" intensity={3.1} castShadow shadow-mapSize={[4096, 4096]} shadow-camera-left={-470} shadow-camera-right={470} shadow-camera-top={350} shadow-camera-bottom={-350} shadow-camera-far={1000} shadow-bias={-0.0003} shadow-normalBias={0.15} shadow-radius={3} />
    <mesh rotation={[-Math.PI / 2, 0, 0]} position={[30, -3, 20]} receiveShadow><planeGeometry args={[1000, 700]} /><meshStandardMaterial color={colors.ground} roughness={0.95} /></mesh>
    <ProcessStations world={props.world} elapsed={elapsed} />
    <TransferActors world={props.world} elapsed={elapsed} /><LogisticsActors world={props.world} elapsed={elapsed} />
    {props.world.materials.filter(material => material.active).map(material => <MaterialMesh key={`${props.world.run.id}:${material.id}`} material={material} worldRef={worldRef} elapsed={elapsed} selected={material.id === props.selectedMaterialId} />)}
    <CameraRig command={cameraCommand} world={props.world} elapsed={elapsed} selectedMaterialId={props.selectedMaterialId} />
    <SceneFrame props={props} worldRef={worldRef} elapsed={elapsed} reduced={reduced} />
  </Canvas></div><CameraToolbar onAction={action => setCameraCommand(previous => ({ sequence: (previous?.sequence ?? 0) + 1, action }))} /></div></SceneBoundary>;
}, (before, after) => before.world.run.id === after.world.run.id && before.world.run.revision === after.world.run.revision && before.selectedMaterialId === after.selectedMaterialId && before.onFallback === after.onFallback);
