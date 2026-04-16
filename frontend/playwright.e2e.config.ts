import { defineConfig } from '@playwright/test';

/**
 * CkyClaw E2E 功能测试配置。
 * 使用 API Mock 模式，仅依赖前端 dev server（localhost:3000），不需要后端。
 * 认证状态复用 auth.setup.ts 保存的 storageState。
 */

const STORAGE_STATE = 'test-results/.auth/user.json';

export default defineConfig({
  testDir: './e2e',
  timeout: 45_000,
  expect: { timeout: 10_000 },
  fullyParallel: false,
  retries: 0,
  workers: 1,
  reporter: [
    ['list'],
    ['html', { open: 'never', outputDir: 'test-results/e2e-report' }],
  ],
  projects: [
    {
      name: 'setup',
      testMatch: /auth\.setup\.ts$/,
    },
    {
      name: 'provider-tests',
      testMatch: /provider\.spec\.ts$/,
      dependencies: ['setup'],
      use: { storageState: STORAGE_STATE },
    },
    {
      name: 'agent-tests',
      testMatch: /agent\.spec\.ts$/,
      dependencies: ['setup'],
      use: { storageState: STORAGE_STATE },
    },
    {
      name: 'chat-tests',
      testMatch: /chat\.spec\.ts$/,
      dependencies: ['setup'],
      use: { storageState: STORAGE_STATE },
    },
    {
      name: 'skill-tests',
      testMatch: /skill\.spec\.ts$/,
      dependencies: ['setup'],
      use: { storageState: STORAGE_STATE },
    },
    {
      name: 'kb-tests',
      testMatch: /knowledge-base\.spec\.ts$/,
      dependencies: ['setup'],
      use: { storageState: STORAGE_STATE },
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
