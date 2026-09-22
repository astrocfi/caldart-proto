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
  // Mirrors the path mappings in tsconfig.json so the bundler and the
  // type-checker agree; code imports across the portal as `@/portal/...`
  // rather than counting `../`s, and tests reach the shared helpers and
  // fixtures as `@test/render` and `@test/fixtures/...`.
  resolve: {
    alias: {
      '@test': resolve(__dirname, 'src/test'),
      '@': resolve(__dirname, 'src'),
    },
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
  // The dev server keeps Vite's own CORS default, which answers the loopback
  // origins the Django dev server runs on and refuses every other site. Django
  // in dev-mode points its module tags at `origin`, so that is all it needs.
  server: {
    port: 5173,
    strictPort: true,
    origin: 'http://localhost:5173',
  },
  test: {
    environment: 'jsdom',
    globals: false,
    setupFiles: ['./src/test/setup.ts'],
    css: false,
    include: ['src/**/*.{test,spec}.{ts,tsx}'],
    // A committed `.only` narrows the run to one test and passes; refusing it
    // keeps a debugging aid from reaching main.
    allowOnly: false,
    // Every spy is restored before the next test, so a file that patches a
    // module member cannot leak it into the file that runs after it.
    restoreMocks: true,
    // Files and the tests inside them run in a random order, which is what
    // surfaces a test that only passes after another has run.
    sequence: { shuffle: true },
    coverage: {
      provider: 'v8',
      // Production code only: the test helpers, the tests themselves and the
      // generated OpenAPI types are not the subject of the measurement.
      include: ['src/**/*.{ts,tsx}'],
      exclude: [
        'src/test/**',
        'src/**/*.{test,spec}.{ts,tsx}',
        'src/portal/api/schema.d.ts',
        'src/**/*.d.ts',
      ],
      reporter: ['text', 'html'],
      reportsDirectory: 'coverage',
    },
  },
});
