import { readFileSync } from 'node:fs';
import { factorySnapshotSchema, factoryWorldSchema } from './contractsV3';

const raw: unknown = JSON.parse(readFileSync('shared/fixtures/factory-contract-test-v3/domain.json', 'utf8'));
const state = factorySnapshotSchema.parse(raw);
export const factoryTestWorld = factoryWorldSchema.parse({ ...state, kpis: { schema_version: 3, run_id: state.run.id, revision: state.run.revision, active_material_count: 3, active_kg: 2400, available_kg: 2400, allocated_kg: 0, shipped_kg: 0, opening_kg: 2500, received_kg: 0, additions_kg: 0, byproduct_kg: 0, loss_kg: 100 } });
