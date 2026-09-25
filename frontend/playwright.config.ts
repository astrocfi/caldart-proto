/**
 * End-to-end tests for the five low-friction flows in `docs/demo-walkthrough.rst`.
 *
 * The specs talk to a real Django server with a real seeded database; `make
 * e2e` builds the front end, resets the `caldart_e2e` database, starts the
 * server and tears it down again.  Run them against a server you started
 * yourself with `E2E_BASE_URL=http://localhost:8020 npm run e2e`.
 *
 * One worker, no parallelism: every spec shares one database, and flows A, D
 * and E write to it.
 */
import { defineConfig, devices } from '@playwright/test';

const baseURL = process.env.E2E_BASE_URL ?? 'http://localhost:8021';

export default defineConfig({
  testDir: './e2e',
  workers: 1,
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  // A spec that failed and then passed on the retry is a flaky spec, and a
  // flaky end-to-end spec hides a real race. Retrying still makes the failure
  // easy to read; it just does not turn the run green.
  failOnFlakyTests: true,
  reporter: process.env.CI ? [['list'], ['html', { open: 'never' }]] : 'list',
  timeout: 60_000,
  expect: { timeout: 10_000 },
  use: {
    baseURL,
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
  },
  projects: [
    {
      name: 'desktop',
      use: { ...devices['Desktop Chrome'] },
    },
    {
      // Joining and the ramp-side member check have to work on a phone, so
      // those two flows run again at iPhone size.  Chromium, not the
      // descriptor's WebKit: one engine to install, in CI as well as here.
      name: 'phone',
      use: { ...devices['iPhone 13'], browserName: 'chromium' },
      testMatch: /(join-and-pay|leader-check)\.spec\.ts/,
    },
  ],
});
