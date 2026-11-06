import { build } from 'esbuild';
import { fileURLToPath } from 'node:url';

// Bundle the existing admission contract in memory; no generated files or global hooks.
export async function productionParser() {
  const result = await build({
    entryPoints: [fileURLToPath(new URL('../../src/operations/scene/assets/manifest.ts', import.meta.url))],
    bundle: true, write: false, platform: 'node', format: 'esm', target: 'node24', logLevel: 'silent',
  });
  const module = await import(`data:text/javascript;base64,${Buffer.from(result.outputFiles[0].contents).toString('base64')}`);
  return module.parseProductionAssetManifest;
}
