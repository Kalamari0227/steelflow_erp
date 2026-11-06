import { defineConfig, mergeConfig } from 'vite';
import { resolve } from 'node:path';
import base from '../../../vite.config';
if (process.env.STEELFLOW_QA_OBSERVER_FIXTURE !== '1' || !process.env.STEELFLOW_E2E_RUN_DIR) throw new Error('Use the owned observer QA runner.');
export default mergeConfig(base, defineConfig({
  cacheDir: resolve(process.env.STEELFLOW_E2E_RUN_DIR, 'observer-vite-cache'),
  build: { rollupOptions: { input: [resolve('index.html'), resolve('tests/fixtures/factory-observer/index.html')] } },
}));
