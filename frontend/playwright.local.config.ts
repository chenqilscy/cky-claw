import { defineConfig, devices } from '@playwright/test';

/**
 * CkyClaw 本地 E2E 测试配置。
 * 依赖：前端 localhost:3000 + 后端 localhost:8000 已启动。
 */

const STORAGE_STATE = 'test-results/.auth/user.json';

export default defineConfig({
  testDir: './e2e',
  timeout: 30_000,
  expect: { timeout: 8_000 },
  fullyParallel: false,
  retries: 0,
  workers: 1,
  reporter: [
    ['list'],
    ['html', { open: 'never' }],
  ],
  projects: [
    {
      name: 'setup',
      testMatch: /auth\.setup\.ts$/,
    },
    {
      name: 'ui-tests',
      testMatch: /ui-automation\.spec\.ts$/,
      dependencies: ['setup'],
      use: {
        storageState: STORAGE_STATE,
      },
    },
  ],
  use: {
    baseURL: 'http://localhost:3000',
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
    actionTimeout: 10_000,
    navigationTimeout: 15_000,
  },
});
