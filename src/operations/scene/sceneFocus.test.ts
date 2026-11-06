import { expect, it } from 'vitest';
import { testWorld } from '../testWorld';
import { MaterialSchema, ProcessExecutionSchema } from '../contracts';
import { sceneFocus } from './sceneFocus';

it('follows the actual running stage while preserving manual context when follow is off', () => {
  const base = testWorld(), material = base.materials[0], process = base.processes[0];
  if (!material || !process) throw new Error('Missing fixture');
  const world = { ...base, processes: [ProcessExecutionSchema.parse({ ...process, material_id: material.id, equipment_id: 'CS-GA-05', status: 'RUNNING', start_ms: 0, end_ms: 1000 })] };
  expect(sceneFocus(world, { materialId: material.id, stageId: 'hr', follow: true })).toBe('ga');
  expect(sceneFocus(world, { materialId: material.id, stageId: 'hr', follow: false })).toBe('hr');
  const waiting = { ...base, processes: [], transfers: [], materials: [MaterialSchema.parse({ ...material, location_id: 'OPS-ORE-SOURCE-BUFFER' })] };
  expect(sceneFocus(waiting, { materialId: material.id, stageId: 'hr', follow: true })).toBe('sources');
});
