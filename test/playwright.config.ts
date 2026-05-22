import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: './e2e',
  timeout: 30000,
  expect: {
    timeout: 10000,
  },
  fullyParallel: false,
  workers: 1,
  retries: 1,
  reporter: [['list'], ['html', { open: 'never' }]],
  use: {
    baseURL: process.env.BASE_URL || 'http://localhost:8000',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
    trace: 'retain-on-failure',
    actionTimeout: 10000,
    navigationTimeout: 15000,
    // Chromium force-upgrades http:// to https:// for the bare `app` hostname,
    // which the plain-HTTP container can't serve. A `.localhost` host is exempt
    // from that upgrade; route it to the `app` service via a resolver rule.
    launchOptions: {
      args: ['--host-resolver-rules=MAP app.localhost app'],
    },
  },
});
