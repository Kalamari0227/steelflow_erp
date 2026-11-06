import { describe, expect, it } from 'vitest';
import { testWorld } from '../testWorld';
import { ProcessExecutionSchema } from '../contracts';
import { factoryLayout, stationAnchorPosition } from './layout';
import { equipmentKinds, processContact, processPhase, processPose, processStation, validateEquipment } from './processPose';
import { renderElapsed } from '../../store';
import { OrthographicCamera, Vector3 } from 'three';
import { fitOperationsCamera } from './CameraRig';
import { cameraFrame } from './cameraControls';

const running = (equipmentId = 'BF-A') => ProcessExecutionSchema.parse({ ...testWorld().processes[0], equipment_id: equipmentId, status: 'RUNNING', start_ms: 1000, end_ms: 11000 });
describe('authoritative production contact', () => {
  it('all twenty routes resolve every real equipment kind', () => {
    expect(factoryLayout.routes).toHaveLength(20);
    for (const route of factoryLayout.routes) for (const id of route.equipment_ids) expect(equipmentKinds).toContain(processStation(id).kind);
  });
  it('rejects unknown equipment and unknown geometry instead of a generic box', () => {
    expect(() => processStation('MISSING')).toThrow('Unknown layout reference');
    expect(() => validateEquipment({ ...processStation('BF-A'), kind: 'invented' })).toThrow('equipment kind invented');
  });
  it.each(['BF-A', ...factoryLayout.equipment.filter(row => ['caster', 'roughing', 'uncoiler', 'coiler', 'galvanizing', 'shear'].includes(row.kind)).map(row => row.id)])('%s reaches the physical entry/work/exit in global coordinates', id => {
    for (const [phase, anchor] of [[0, 'entry'], [0.5, 'work'], [1, 'exit']] as const) expect(processContact(id, phase)).toEqual(stationAnchorPosition(factoryLayout, id, anchor));
  });
  it('does not interpolate through an unconfirmed phase end', () => {
    expect(processPhase(running(), 999999)).toBe(0.97);
    expect(processContact('BF-A', 0.97)).toEqual(stationAnchorPosition(factoryLayout, 'BF-A', 'exit'));
    expect(processPhase({ ...running(), status: 'COMPLETED' }, 0)).toBe(1);
    expect(processPhase({ ...running(), status: 'BLOCKED' }, 5000)).toBe(0);
  });
  it('only confirmed backend form/version changes reach the material renderer', () => {
    const world = testWorld(), material = world.materials[0];
    if (!material) throw new Error('fixture material missing');
    const active = { ...world, processes: [running()] };
    expect(processPose(material, active, 999999).form).toBe('ORE');
    expect(processPose({ ...material, form: 'HOT_METAL' }, active, 999999).form).toBe('HOT_METAL');
  });
  it('shows annealing heat without inventing an output form before confirmation', () => {
    const world = testWorld(), material = world.materials[0];
    const station = factoryLayout.equipment.find(row => row.kind === 'annealing');
    if (!material || !station) throw new Error('Missing annealing fixture');
    const active = { ...world, processes: [running(station.id)] };
    const pose = processPose(material, active, 6000);
    expect(pose.hot).toBe(true);
    expect(pose.form).toBe(material.form);
  });
  it('pause and stale use the exact server contact; interpolation is bounded to 350ms', () => {
    const world = { ...testWorld(), run: { ...testWorld().run, playing: true, speed: 4 as const, elapsed_ms: 6000 } };
    expect(renderElapsed({ world, stale: false, receivedAt: 1000 }, 999999)).toBe(7400);
    expect(renderElapsed({ world, stale: true, receivedAt: 1000 }, 999999)).toBe(6000);
    expect(renderElapsed({ world: { ...world, run: { ...world.run, playing: false } }, stale: false, receivedAt: 1000 }, 999999)).toBe(6000);
  });
  it('retains material identity through an actual anchored station pose', () => {
    const world = testWorld(), material = world.materials[0];
    if (!material) throw new Error('fixture material missing');
    const pose = processPose(material, { ...world, processes: [running()] }, 6000);
    expect(pose.position).toEqual(stationAnchorPosition(factoryLayout, 'BF-A', 'work'));
    expect(pose.equipmentId).toBe('BF-A');
  });
});

it('overview camera contains every actual factory contact in the frustum', () => {
  for (const viewport of [{ width: 800, height: 560 }, { width: 358, height: 440 }]) {
    const camera = new OrthographicCamera(-viewport.width / 2, viewport.width / 2, viewport.height / 2, -viewport.height / 2, 0.1, 1500);
    camera.zoom = fitOperationsCamera(camera, cameraFrame(factoryLayout, { level: 'overview', selection: { run_id: 'test' } }), viewport);
    camera.updateProjectionMatrix();
    for (const location of factoryLayout.locations) {
      const projected = new Vector3(...location.position).project(camera);
      expect(Math.abs(projected.x), location.id).toBeLessThan(1);
      expect(Math.abs(projected.y), location.id).toBeLessThan(1);
      expect(Math.abs(projected.z), location.id).toBeLessThan(1);
    }
  }
});
