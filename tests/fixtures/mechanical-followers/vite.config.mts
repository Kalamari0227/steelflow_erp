import { defineConfig, mergeConfig } from 'vite';
import { resolve } from 'node:path';
import base from '../../../vite.config';

if (process.env.STEELFLOW_QA_ASSET_FAMILY !== 'mechanical-followers' || !process.env.STEELFLOW_E2E_RUN_DIR) throw new Error('Use the owned mechanical-followers QA runner.');
export default mergeConfig(base, defineConfig({
  publicDir: resolve('tests/fixtures/mechanical-followers/generated/public'),
  cacheDir: resolve(process.env.STEELFLOW_E2E_RUN_DIR, 'mechanical-followers-vite-cache'),
  build: { rollupOptions: { input: resolve('tests/fixtures/mechanical-followers/index.html') } },
}));
