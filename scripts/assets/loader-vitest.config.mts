import { defineConfig } from 'vitest/config';
import { resolve } from 'node:path';

const evidence = process.env.ASSET_LOADER_EVIDENCE_ROOT;
if (!evidence) throw new Error('Set ASSET_LOADER_EVIDENCE_ROOT to an owned evidence directory.');
export default defineConfig({
  cacheDir: resolve(evidence, 'runtime/vite'),
  test: {
    environment: 'node', fileParallelism: false,
    include: ['src/operations/scene/assets/{loader,registry,lod,manifest}.test.ts', 'src/operations/scene/motion/assetAdapter.test.ts'],
    fsModuleCachePath: resolve(evidence, 'runtime/modules'),
  },
});
