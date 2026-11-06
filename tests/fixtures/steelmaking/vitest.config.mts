import { defineConfig } from 'vitest/config';
import { resolve } from 'node:path';
const evidence=process.env.ASSET_LOADER_EVIDENCE_ROOT;
if(!evidence)throw new Error('Set current ASSET_LOADER_EVIDENCE_ROOT.');
export default defineConfig({cacheDir:resolve(evidence,'runtime/fixed-vite'),test:{environment:'node',fileParallelism:false,include:['src/operations/scene/assets/fixedPartFrames.test.ts'],fsModuleCachePath:resolve(evidence,'runtime/fixed-modules')}});
