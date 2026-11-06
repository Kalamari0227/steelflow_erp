import { useEffect, useRef } from 'react';
import type { ComponentRef, RefObject } from 'react';
import { OrbitControls } from '@react-three/drei';
import { useFrame, useThree } from '@react-three/fiber';
import { Vector3 } from 'three';
import type { Camera } from 'three';
import type { Point } from './layout';
import type { World } from '../../contracts';
import { cameraScope, useNavigationStore } from '../navigation';
import { factoryLayout } from './layout';
import { cameraFrame, cameraZoomLimits, moveOperationsCamera, saveManualCamera } from './cameraControls';
import type { CameraCommand } from './cameraControls';
import { processPose } from './processPose';
import { transferPose } from './transferPose';

export function fitOperationsCamera(camera: Camera, frame: { readonly target: Point; readonly width: number; readonly depth: number; readonly distance: number }, viewport: { readonly width: number; readonly height: number }): number {
  const target = new Vector3(...frame.target);
  camera.position.copy(target).add(new Vector3(22, 40, 64).multiplyScalar(frame.distance));
  camera.lookAt(target); camera.updateMatrixWorld(true);
  const corners = [-1, 1].flatMap(x => [-1, 1].flatMap(z => [0, 8].map(y => new Vector3(target.x + x * frame.width / 2, y, target.z + z * frame.depth / 2).applyMatrix4(camera.matrixWorldInverse))));
  const halfWidth = Math.max(...corners.map(point => Math.abs(point.x)));
  const halfHeight = Math.max(...corners.map(point => Math.abs(point.y)));
  return Math.min(viewport.width / (halfWidth * 2.04), viewport.height / (halfHeight * 2.04));
}
function fitWorkspaceCamera(camera: Camera, frame: Parameters<typeof fitOperationsCamera>[1], viewport: Parameters<typeof fitOperationsCamera>[2]) {
  if (useNavigationStore.getState().level === 'overview') {
    return { zoom: fitOperationsCamera(camera, frame, viewport), target: new Vector3(...frame.target), offset: new Vector3() };
  }
  const wide = viewport.width >= 1000;
  const inset = wide ? { left: 224, right: 294, top: 58, bottom: 144 } : { left: 20, right: 20, top: 48, bottom: 126 };
  const zoom = fitOperationsCamera(camera, frame, {
    width: Math.max(200, viewport.width - inset.left - inset.right),
    height: Math.max(180, viewport.height - inset.top - inset.bottom),
  });
  const right = new Vector3(1, 0, 0).applyQuaternion(camera.quaternion);
  const up = new Vector3(0, 1, 0).applyQuaternion(camera.quaternion);
  const offset = right.multiplyScalar((inset.right - inset.left) / (2 * zoom))
    .add(up.multiplyScalar((inset.top - inset.bottom) / (2 * zoom)));
  camera.position.add(offset);
  return { zoom, target: new Vector3(...frame.target).add(offset), offset };
}
export function CameraRig({ world, elapsed, selectedMaterialId, command }: { readonly command?: CameraCommand | null; readonly world: World; readonly elapsed: RefObject<number>; readonly selectedMaterialId: string | null }) {
  const controls = useRef<ComponentRef<typeof OrbitControls>>(null);
  const { camera, size, invalidate, gl } = useThree();
  const level = useNavigationStore(state => state.level);
  const equipmentId = useNavigationStore(state => state.selection.equipment_id), stageId = useNavigationStore(state => state.selection.stage_id);
  const follow = useNavigationStore(state => state.followMaterial);
  const previous = useRef(new Vector3());
  const safeOffset = useRef(new Vector3());
  const dragging = useRef(false);
  const scope = cameraScope(useNavigationStore.getState());
  useEffect(() => {
    const saved = useNavigationStore.getState().cameraByScope[scope];
    const frame = cameraFrame(factoryLayout, useNavigationStore.getState());
    const fitted = fitWorkspaceCamera(camera, frame, size);
    safeOffset.current.copy(saved ? new Vector3() : fitted.offset);
    if (saved) camera.position.set(...saved.position);
    camera.zoom = saved?.zoom ?? fitted.zoom;
    const finalTarget = saved ? new Vector3(...saved.target) : fitted.target;
    camera.lookAt(finalTarget); camera.updateProjectionMatrix(); controls.current?.target.copy(finalTarget); controls.current?.update();
    previous.current.copy(finalTarget); invalidate();
  }, [scope, level, stageId, equipmentId, camera, size.width, size.height, invalidate]);
  const appliedCommand = useRef<number | null>(null);
  useEffect(() => {
    const control = controls.current;
    if (!command || !control || appliedCommand.current === command.sequence) return;
    appliedCommand.current = command.sequence;
    if (command.action === 'fit') {
      const frame = cameraFrame(factoryLayout, useNavigationStore.getState());
      const fitted = fitWorkspaceCamera(camera, frame, size);
      camera.zoom = fitted.zoom;
      safeOffset.current.copy(fitted.offset);
      control.target.copy(fitted.target); camera.updateProjectionMatrix();
    } else moveOperationsCamera(camera, control.target, command.action, size.height);
    saveManualCamera(camera, control.target);
    previous.current.copy(control.target); control.update(); invalidate();
  }, [command, camera, size, invalidate]);
  useFrame(() => {
    const control = controls.current;
    if (!control) return;
    const material = follow ? world.materials.find(row => row.id === selectedMaterialId && row.active) : undefined;
    if (material && !dragging.current) {
      const pose = transferPose(material, world, elapsed.current) ?? processPose(material, world, elapsed.current);
      const target = new Vector3(...pose.position).add(safeOffset.current);
      const delta = target.clone().sub(previous.current);
      camera.position.add(delta); control.target.add(delta); control.update(); previous.current.copy(target);
    } else previous.current.copy(control.target);
    gl.domElement.dataset.camera = JSON.stringify({ position: camera.position.toArray(), target: control.target.toArray(), zoom: camera.zoom });
  });
  const save = () => { const control = controls.current; if (control) useNavigationStore.getState().saveCamera({ position: [camera.position.x, camera.position.y, camera.position.z], target: [control.target.x, control.target.y, control.target.z], zoom: camera.zoom }); };
  return <OrbitControls ref={controls} makeDefault enableDamping={false} minZoom={cameraZoomLimits.min} maxZoom={cameraZoomLimits.max} maxPolarAngle={Math.PI / 2.05} onStart={() => { dragging.current = true; useNavigationStore.getState().setFollowMaterial(false); }} onEnd={() => { dragging.current = false; save(); }} />;
}
