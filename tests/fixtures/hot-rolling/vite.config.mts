import { defineConfig, mergeConfig } from 'vite';
import { resolve } from 'node:path';
import { realpathSync } from 'node:fs';
import base from '../../../vite.config';

if (process.env.STEELFLOW_QA_ASSET_FAMILY !== 'hot-rolling' || !process.env.STEELFLOW_E2E_RUN_DIR) throw new Error('Use the owned hot-rolling QA runner.');
const sourceRoot=realpathSync(process.env.STEELFLOW_QA_HOT_ROLLING_ROOT ?? resolve('.'));
if (sourceRoot !== realpathSync(resolve('.')) && !sourceRoot.startsWith(realpathSync(resolve('.omo/evidence'))+'/')) throw new Error('Family snapshot must be owned local evidence.');
export default mergeConfig(base, defineConfig({
  publicDir: resolve(sourceRoot,'public'),
  cacheDir: resolve(process.env.STEELFLOW_E2E_RUN_DIR, 'hot-rolling-vite-cache'),
  build: { rollupOptions: { input: resolve('tests/fixtures/hot-rolling/index.html') } },
}));
