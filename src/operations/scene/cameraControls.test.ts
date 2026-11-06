import { beforeEach, describe, expect, it, vi } from 'vitest';
import { OrthographicCamera, Vector3 } from 'three';
import { initialNavigation, useNavigationStore } from '../navigation';
import { useWorldStore } from '../../store';
import { testWorld } from '../testWorld';
import { cameraFrame, moveOperationsCamera, saveManualCamera } from './cameraControls';
import { factoryLayout, stationAnchorPosition } from './layout';
import { fitOperationsCamera } from './CameraRig';

beforeEach(() => useNavigationStore.setState({ ...initialNavigation, issue: null }));
function cameraAt(x: number, z: number) {
  const camera = new OrthographicCamera(-400, 400, 300, -300, 0.1, 1500);
  camera.position.set(x, 50, z); camera.lookAt(0, 0, 0); camera.zoom = 4; camera.updateMatrixWorld(true);
  return camera;
}
describe('manual camera navigation', () => {
  it.each([[0, 60], [60, 0], [-45, -60]])('pans relative to a rotated camera (%i, %i), preserving height and look direction', (x, z) => {
    const camera = cameraAt(x, z), target = new Vector3();
    const position = camera.position.clone(), offset = camera.position.clone().sub(target);
    const screenRight = new Vector3(1, 0, 0).applyQuaternion(camera.quaternion).setY(0).normalize();
    moveOperationsCamera(camera, target, 'right', 600);
    expect(target.dot(screenRight)).toBeCloseTo(18);
    expect(target.y).toBe(0); expect(camera.position.y).toBe(50);
    expect(camera.position.clone().sub(target).distanceTo(offset)).toBeLessThan(1e-10);
    moveOperationsCamera(camera, target, 'left', 600);
    expect(camera.position.distanceTo(position)).toBeLessThan(1e-10);
    moveOperationsCamera(camera, target, 'up', 600);
    expect(target.clone().project(camera).x).toBeCloseTo(0);
    expect(target.y).toBe(0);
    moveOperationsCamera(camera, target, 'down', 600);
    expect(camera.position.distanceTo(position)).toBeLessThan(1e-10);
  });
  it('scales pan with zoom and clamps zoom without changing the target', () => {
    const camera = cameraAt(30, 60), target = new Vector3();
    moveOperationsCamera(camera, target, 'right', 600); const first = target.length();
    camera.zoom *= 2; const before = target.clone();
    moveOperationsCamera(camera, target, 'right', 600);
    expect(target.distanceTo(before)).toBeCloseTo(first / 2);
    const fixed = target.clone();
    for (let i = 0; i < 100; i++) moveOperationsCamera(camera, target, 'zoom-in', 600);
    expect(camera.zoom).toBe(65);
    for (let i = 0; i < 100; i++) moveOperationsCamera(camera, target, 'zoom-out', 600);
    expect(camera.zoom).toBe(0.25); expect(target.equals(fixed)).toBe(true);
  });
  it('saves manual navigation while paused, disables follow, and never commands or mutates the World', () => {
    const world = testWorld(), camera = cameraAt(30, 60), target = new Vector3();
    useWorldStore.setState({ world }); const before = JSON.stringify(world);
    const command = vi.spyOn(useWorldStore.getState(), 'command');
    useNavigationStore.setState({ followMaterial: true, level: 'stage', selection: { run_id: world.run.id, stage_id: 'ironmaking', material_id: world.materials[0]?.id } });
    const selection = useNavigationStore.getState().selection;
    moveOperationsCamera(camera, target, 'up', 600); saveManualCamera(camera, target);
    expect(useNavigationStore.getState().followMaterial).toBe(false);
    expect(useNavigationStore.getState().cameraByScope['stage:ironmaking']?.target).toEqual(target.toArray());
    expect(useNavigationStore.getState().selection).toEqual(selection);
    expect(JSON.stringify(useWorldStore.getState().world)).toBe(before);
    expect(command).not.toHaveBeenCalled(); command.mockRestore();
  });
  it('fits every canonical location and path point in the overview viewport', () => {
    const viewport = { width: 800, height: 500 }, frame = cameraFrame(factoryLayout, initialNavigation);
    const camera = new OrthographicCamera(-400, 400, 250, -250, 0.1, 1500);
    camera.zoom = fitOperationsCamera(camera, frame, viewport); camera.updateProjectionMatrix();
    for (const point of [...factoryLayout.locations.map(row => row.position), ...factoryLayout.paths.flatMap(row => row.points)]) {
      const projected = new Vector3(...point).project(camera);
      expect(Math.abs(projected.x)).toBeLessThan(1); expect(Math.abs(projected.y)).toBeLessThan(1);
    }
  });
  it('derives stage bounds from transformed anchors instead of a uniform stage footprint', () => {
    const stage = factoryLayout.stages[0]; if (!stage) throw new Error('fixture stage missing');
    const frame = cameraFrame(factoryLayout, { level: 'stage', selection: { run_id: '', stage_id: stage.id } });
    for (const row of factoryLayout.equipment.filter(row => row.stage_id === stage.id)) for (const anchor of ['entry', 'work', 'exit', 'buffer'] as const) {
      const point = stationAnchorPosition(factoryLayout, row.id, anchor);
      expect(Math.abs(point[0] - frame.target[0])).toBeLessThan(frame.width / 2);
      expect(Math.abs(point[2] - frame.target[2])).toBeLessThan(frame.depth / 2);
    }
  });
});
