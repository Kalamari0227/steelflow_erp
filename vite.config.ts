import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';

const apiTarget = process.env.VITE_API_TARGET || 'http://127.0.0.1:8000';
const apiProxy = { '/api': apiTarget, '/health': apiTarget };

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: { port: 5173, strictPort: true, proxy: apiProxy },
  preview: { port: 4173, strictPort: true, proxy: apiProxy },
  test: { environment: 'jsdom', globals: true, setupFiles: ['./src/test-setup.ts'], include: ['src/**/*.test.{ts,tsx}'] },
});
