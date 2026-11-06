import { Vector3 } from 'three';
import type { OrthographicCamera, PerspectiveCamera } from 'three';
import { useNavigationStore } from '../navigation';
import type { Navigation } from '../navigation';
import { stationAnchorPosition } from './layout';
import type { FactoryLayout, Point } from './layout';

export type CameraAction = 'up' | 'down' | 'left' | 'right' | 'zoom-in' | 'zoom-out' | 'fit';
export type CameraCommand = { readonly sequence: number; readonly action: CameraAction };
export const cameraZoomLimits = { min: 0.25, max: 65 };

export function cameraFrame(layout: FactoryLayout, navigation: Pick<Navigation, 'level' | 'selection'>) {
  const equipment = layout.equipment.filter(row => navigation.level === 'equipment' ? row.id === navigation.selection.equipment_id : row.stage_id === navigation.selection.stage_id);
  const points: readonly Point[] = navigation.level === 'overview' || !equipment.length
    ? [...layout.stages.map(row => row.position), ...layout.locations.map(row => row.position), ...layout.paths.flatMap(row => row.points)]
    : equipment.flatMap(row => (['entry', 'work', 'exit', 'buffer'] as const).map(anchor => stationAnchorPosition(layout, row.id, anchor)));
  const minX = Math.min(...points.map(p => p[0])), maxX = Math.max(...points.map(p => p[0]));
  const minZ = Math.min(...points.map(p => p[2])), maxZ = Math.max(...points.map(p => p[2]));
  const padding = navigation.level === 'overview' ? 24 : 8;
  const width = maxX - minX + padding * 2, depth = maxZ - minZ + padding * 2;
  return { target: [(minX + maxX) / 2, 0, (minZ + maxZ) / 2] as Point, width, depth, distance: Math.max(1, Math.max(width, depth) / 60) };
}

/** Move the viewing target along the camera's screen axes projected onto the floor. */
export function moveOperationsCamera(camera: OrthographicCamera | PerspectiveCamera, target: Vector3, action: Exclude<CameraAction, 'fit'>, viewportHeight: number): void {
  if (action === 'zoom-in' || action === 'zoom-out') {
    camera.zoom = Math.max(cameraZoomLimits.min, Math.min(cameraZoomLimits.max, camera.zoom * (action === 'zoom-in' ? 1.25 : 0.8)));
    camera.updateProjectionMatrix();
    return;
  }
  const right = new Vector3(1, 0, 0).applyQuaternion(camera.quaternion);
  right.y = 0; right.normalize();
  const up = new Vector3().crossVectors(new Vector3(0, 1, 0), right).normalize();
  const direction = action === 'left' || action === 'right' ? right : up;
  const sign = action === 'left' || action === 'down' ? -1 : 1;
  const delta = direction.multiplyScalar(sign * viewportHeight * 0.12 / camera.zoom);
  camera.position.add(delta); target.add(delta);
  camera.updateMatrixWorld(true);
}

export function saveManualCamera(camera: OrthographicCamera | PerspectiveCamera, target: Vector3): void {
  const navigation = useNavigationStore.getState();
  navigation.setFollowMaterial(false);
  navigation.saveCamera({ position: [camera.position.x, camera.position.y, camera.position.z], target: [target.x, target.y, target.z], zoom: camera.zoom });
}
