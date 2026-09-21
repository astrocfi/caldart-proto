import { resolve } from 'node:path';

import react from '@vitejs/plugin-react';
// `vitest/config` re-exports vite's `defineConfig` and adds the `test` key.
import { defineConfig } from 'vitest/config';

/**
 * Two entries: the public site's progressive enhancement and the
 * portal SPA.  Django reads `dist/.vite/manifest.json` through django-vite,
 * and `frontend/dist` is on STATICFILES_DIRS so `collectstatic` picks the
 * built assets up unchanged.
 */
export default defineConfig({
  base: '/static/',
  plugins: [react()],
  // Mirrors the `@/*` path mapping in tsconfig.json so the bundler and the
  // type-checker agree; code imports across the portal as `@/portal/...`
  // rather than counting `../`s.
  resolve: {
    alias: { '@': resolve(__dirname, 'src') },
  },
  build: {
    manifest: true,
    outDir: 'dist',
    emptyOutDir: true,
    rollupOptions: {
      input: {
        site: resolve(__dirname, 'src/site/main.ts'),
        portal: resolve(__dirname, 'src/portal/main.tsx'),
      },
    },
  },
  server: {
    port: 5173,
    strictPort: true,
    origin: 'http://localhost:5173',
    cors: true,
  },
  test: {
    environment: 'jsdom',
    globals: false,
    setupFiles: ['./src/test/setup.ts'],
    css: false,
    include: ['src/**/*.{test,spec}.{ts,tsx}'],
  },
});
