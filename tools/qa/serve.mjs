import { mkdirSync, rmSync } from 'node:fs';
import { join } from 'node:path';
import { processOwner, startServices, json } from './runtime.mjs';

const env = process.env;
const evidence = env.STEELFLOW_EVIDENCE_DIR;
if (!evidence || !env.STEELFLOW_E2E_RUN_DIR) throw new Error('Standalone QA requires an isolated run directory');
mkdirSync(evidence, { recursive: true });
const owner = processOwner(evidence, env);
const controller = new AbortController();
let stopping = false;
async function stop(code) {
  if (stopping) return;
  stopping = true;
  controller.abort();
  const stopped = await owner.cleanup();
  for (const path of ['dist', 'steelflow.sqlite', 'steelflow.sqlite-wal', 'steelflow.sqlite-shm', 'node-cache', 'bun-cache']) {
    rmSync(join(env.STEELFLOW_E2E_RUN_DIR, path), { recursive: true, force: true });
  }
  json(join(evidence, 'cleanup.json'), { stopped, complete: true });
  process.exit(code);
}
process.on('SIGINT', () => void stop(130));
process.on('SIGTERM', () => void stop(0));
try { await startServices(owner, env, controller.signal); }
catch (error) { console.error(error); await stop(1); }
