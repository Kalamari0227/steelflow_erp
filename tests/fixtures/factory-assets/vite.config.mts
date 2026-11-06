import { defineConfig, mergeConfig } from 'vite';
import { resolve } from 'node:path';
import { appendFileSync, statSync } from 'node:fs';
import base from '../../../vite.config';

if (process.env.STEELFLOW_QA_ASSET_FIXTURE !== '1' || !process.env.STEELFLOW_E2E_RUN_DIR || !process.env.STEELFLOW_EVIDENCE_DIR) throw new Error('Use the owned asset QA runner.');
const probeEvidence = resolve(process.env.STEELFLOW_EVIDENCE_DIR, 'asset-http-probes.jsonl');
const record = (mode: string, event: string, url: string, probeRequestId: string | null, statusCode?: number) => appendFileSync(probeEvidence, `${JSON.stringify({ mode, event, url, probe_request_id: probeRequestId, status_code: statusCode, pid: process.pid, at_ms: Date.now() })}\n`);
export default mergeConfig(base, defineConfig({
  cacheDir: resolve(process.env.STEELFLOW_E2E_RUN_DIR, 'asset-vite-cache'),
  plugins: [{
    name: 't13-owned-preview-failure-probes',
    configurePreviewServer(server) {
      server.middlewares.use((request, response, next) => {
        const url = request.url ?? '';
        const probeRequestId = typeof request.headers['x-steelflow-asset-probe-id'] === 'string' ? request.headers['x-steelflow-asset-probe-id'] : null;
        if (url === '/__t13_redirect_target__') { record('redirect', 'target-hit', url, probeRequestId); response.writeHead(500); response.end(); return; }
        const mode = request.headers['x-steelflow-asset-probe'];
        if (url !== '/assets/steelworks/shear-lod2.glb' || request.method !== 'GET' || typeof mode !== 'string' || !['headers-only', 'stalled-404', 'redirect', 'caller-abort'].includes(mode)) { next(); return; }
        record(mode, 'request', url, probeRequestId); response.once('close', () => record(mode, 'close', url, probeRequestId, response.statusCode));
        if (mode === 'redirect') { response.writeHead(302, { location: '/__t13_redirect_target__' }); response.end(); return; }
        response.writeHead(mode === 'stalled-404' ? 404 : 200, { 'content-type': 'model/gltf-binary', 'content-length': String(statSync(resolve('public/assets/steelworks/shear-lod2.glb')).size) });
        response.flushHeaders(); record(mode, 'headers-flushed', url, probeRequestId, response.statusCode);
      });
    },
  }],
  build: { rollupOptions: { input: resolve('tests/fixtures/factory-assets/index.html') } },
}));
