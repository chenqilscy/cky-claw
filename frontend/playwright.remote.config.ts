import { defineConfig, devices } from '@playwright/test';

/**
 * Kasaya 远程站点 E2E 测试配置。
 * 目标：http://fn.cky:3000（远程部署站点）。
 */
export default defineConfig({
  testDir: './e2e',
  timeout: 30_000,
  expect: { timeout: 10_000 },
  fullyParallel: true,
  retries: 1,
  workers: 1,
  reporter: [['list'], ['json', { outputFile: '../e2e-results.json' }]],
  use: {
    baseURL: 'http://fn.cky:3000',
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'], channel: 'chrome' },
    },
  ],
  // 无 webServer — 使用远程已部署的站点
});
