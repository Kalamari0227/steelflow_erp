import { defineConfig } from 'vitest/config';
import { resolve } from 'node:path';

const evidence = process.env.ASSET_PIPELINE_EVIDENCE_ROOT;
if (!evidence) throw new Error('Set ASSET_PIPELINE_EVIDENCE_ROOT to a registered owned directory.');
export default defineConfig({
  cacheDir: resolve(evidence, 'runtime/vite'),
  test: { environment: 'node', include: ['src/operations/scene/assets/pipeline.test.ts'], fileParallelism: false },
});
