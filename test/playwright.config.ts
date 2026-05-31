import { defineConfig, devices } from '@playwright/test';

/**
 * FinAlly E2E configuration.
 *
 * baseURL is driven by BASE_URL so the same specs run inside the compose network
 * (http://app:8000) and, if needed, against a locally running container
 * (http://localhost:8000). Timeouts are deliberately generous: SSE handshakes,
 * the simulator's first ticks, and the 10s portfolio poll all need slack before
 * the rendered DOM settles.
 */
export default defineConfig({
  testDir: './e2e',
  // All specs share ONE app container and ONE SQLite DB (user_id="default"). Run strictly
  // serial: multiple parallel workers open concurrent long-lived SSE streams that saturate
  // the app (the connection dot never reaches "connected") AND let mutating specs (chat/trade)
  // race the pristine-state assertions in fresh-start. workers:1 + fullyParallel:false makes
  // execution deterministic against the shared backend.
  fullyParallel: false,
  workers: 1,
  // Per-test ceiling — covers page load + SSE handshake + a price-change poll window.
  timeout: 30_000,
  // Web-first assertions auto-retry up to this; prices/snapshots take time to appear.
  expect: { timeout: 10_000 },
  retries: process.env.CI ? 1 : 0,
  reporter: [['list'], ['html', { open: 'never' }]],
  use: {
    baseURL: process.env.BASE_URL ?? 'http://localhost:8000',
    trace: 'on-first-retry',
    video: 'retain-on-failure',
  },
  // Single chromium project only — the app is desktop-first; multi-browser is out of scope.
  // The plain-HTTP app is reached via a dotted host alias (BASE_URL=http://app.local:8000
  // in docker-compose.test.yml) to dodge Chromium's bare-hostname HTTPS auto-upgrade.
  //
  // Two ordered projects against the ONE shared app+DB: the `smoke` (fresh-start) project
  // asserts the pristine $10k / default-watchlist seed and so MUST run before any spec that
  // mutates cash or positions. `scenarios` declares a dependency on `smoke`, so Playwright
  // runs fresh-start to completion first; the remaining scenario specs (chat/trade buy shares,
  // watchlist add/removes, sse-resilience is read-only) then run serially afterward.
  projects: [
    {
      name: 'smoke',
      testMatch: /fresh-start\.spec\.ts/,
      use: { ...devices['Desktop Chrome'] },
    },
    {
      name: 'scenarios',
      testMatch: /(chat|trade|watchlist|sse-resilience)\.spec\.ts/,
      dependencies: ['smoke'],
      use: { ...devices['Desktop Chrome'] },
    },
  ],
});
