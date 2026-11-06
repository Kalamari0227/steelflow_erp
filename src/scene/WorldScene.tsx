import { Component, useCallback, useEffect, useRef, useState } from 'react';
import type { ComponentRef, ReactNode } from 'react';
import { Canvas, useThree } from '@react-three/fiber';
import { OrbitControls } from '@react-three/drei';
import type { Selection, World } from '../contracts';
import { Facility } from './Facility';
import { WorldEntities } from './WorldEntities';
import { LabelPortalContext, palette } from './primitives';

type WorldSceneProps = {
  readonly world: World; readonly selection: Selection | null;
  readonly onSelect: (selection: Selection) => void;
  readonly resetKey: number; readonly labels: boolean;
  readonly onOpenInventory?: () => void;
};

function SceneFallback({ onOpenInventory }: { readonly onOpenInventory: () => void }) {
  return <div role="status" style={{ display: 'grid', placeContent: 'center', minHeight: 300,
    height: '100%', padding: 24, textAlign: 'center', color: palette.ink, background: palette.paper }}>
    <strong>3D view is unavailable</strong>
    <p>Your operational data and simulation controls remain available.</p>
    <button type="button" onClick={onOpenInventory} style={{ justifySelf: 'center', color: palette.teal,
      background: palette.white, border: `1px solid ${palette.concrete}`, borderRadius: 6, padding: '8px 12px', cursor: 'pointer' }}>
      Open 2D inventory
    </button>
  </div>;
}

class SceneBoundary extends Component<{ readonly children: ReactNode; readonly onOpenInventory: () => void }, { readonly failed: boolean }> {
  state = { failed: false };
  static getDerivedStateFromError() { return { failed: true }; }
  render() { return this.state.failed ? <SceneFallback onOpenInventory={this.props.onOpenInventory} /> : this.props.children; }
}

function CameraRig({ resetKey }: { readonly resetKey: number }) {
  const controls = useRef<ComponentRef<typeof OrbitControls>>(null);
  const { camera, size, invalidate } = useThree();
  useEffect(() => {
    camera.position.set(36, 32, 38);
    camera.zoom = Math.min(size.width / 54, size.height / 36);
    camera.lookAt(0, 0, 0);
    camera.updateProjectionMatrix();
    controls.current?.target.set(0, 0, 0);
    controls.current?.update();
    invalidate();
  }, [camera, size.width, size.height, resetKey, invalidate]);
  return <OrbitControls ref={controls} makeDefault enableDamping dampingFactor={0.12}
    minZoom={5} maxZoom={50} minPolarAngle={0.2} maxPolarAngle={Math.PI / 2.25}
    maxDistance={100} minDistance={10} />;
}

function ContextMonitor({ onLost }: { readonly onLost: () => void }) {
  const renderer = useThree((state) => state.gl);
  useEffect(() => {
    const handleLost = (event: Event) => { event.preventDefault(); onLost(); };
    renderer.domElement.addEventListener('webglcontextlost', handleLost);
    return () => renderer.domElement.removeEventListener('webglcontextlost', handleLost);
  }, [renderer, onLost]);
  return null;
}

export function WorldScene({ world, selection, onSelect, resetKey, labels,
  onOpenInventory = () => { window.location.hash = 'inventory'; },
}: WorldSceneProps) {
  const [contextLost, setContextLost] = useState(false);
  const [labelPortal] = useState(() => ({ current: document.createElement('div') }));
  const attachLabels = useCallback((host: HTMLDivElement | null) => {
    // Keep the portal target stable until the R3F reconciler has cleaned up its nested HTML roots.
    if (host) host.appendChild(labelPortal.current);
  }, [labelPortal]);
  if (contextLost) return <SceneFallback onOpenInventory={onOpenInventory} />;
  return <SceneBoundary onOpenInventory={onOpenInventory}>
    <div style={{ position: 'relative', width: '100%', height: '100%' }}>
    <div ref={attachLabels} style={{ position: 'absolute', inset: 0, pointerEvents: 'none', zIndex: 1 }} />
    <Canvas orthographic frameloop="demand" dpr={[1, 1.5]} shadows
      camera={{ position: [36, 32, 38], zoom: 14, near: 0.1, far: 160 }}
      gl={{ antialias: true, alpha: false, powerPreference: 'high-performance' }}
      fallback={<SceneFallback onOpenInventory={onOpenInventory} />}
      style={{ width: '100%', height: '100%', background: palette.paper }}
      aria-label="Interactive synthetic steel factory. Drag to orbit, scroll to zoom, select coils for details. Use inventory table for keyboard access.">
      <color attach="background" args={[palette.paper]} />
      <ambientLight intensity={1.4} />
      <hemisphereLight args={[palette.white, palette.muted, 1.6]} />
      <directionalLight position={[-15, 35, 22]} intensity={2.5} castShadow
        shadow-mapSize={[2048, 2048]} shadow-camera-left={-35} shadow-camera-right={35}
        shadow-camera-top={30} shadow-camera-bottom={-30} shadow-camera-far={90}
        shadow-bias={-0.0006} />
      <LabelPortalContext.Provider value={labelPortal}>
        <Facility onSelect={onSelect} />
        <WorldEntities world={world} selection={selection} onSelect={onSelect} labels={labels} />
      </LabelPortalContext.Provider>
      <CameraRig resetKey={resetKey} />
      <ContextMonitor onLost={() => setContextLost(true)} />
    </Canvas>
    </div>
  </SceneBoundary>;
}
