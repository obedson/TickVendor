import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: './e2e',
  timeout: 30_000,
  fullyParallel: false,
  reporter: 'list',
  globalTeardown: './e2e/global-teardown.mjs',
  use: { baseURL: 'http://127.0.0.1:4173', trace: 'retain-on-failure' },
  webServer: [
    {
      command: 'node e2e/python-runner.mjs e2e/run_backend.py',
      url: 'http://127.0.0.1:8000/docs',
      reuseExistingServer: false,
      timeout: 60_000,
    },
    {
      command: 'npm run preview -- --host 127.0.0.1',
      url: 'http://127.0.0.1:4173',
      reuseExistingServer: false,
      timeout: 60_000,
    },
  ],
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
});
