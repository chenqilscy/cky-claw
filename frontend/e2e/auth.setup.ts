import { test as setup, expect } from '@playwright/test';

/**
 * 全局认证设置 — 注入 Mock JWT Token 并保存浏览器状态。
 * E2E Mock 模式下不依赖真实后端登录，只需 localStorage 中存在 token 即可通过 RequireAuth 守卫。
 */

const STORAGE_STATE = 'test-results/.auth/user.json';

/** Mock JWT — 格式合法但非真实签名，仅用于通过前端 RequireAuth 检查 */
const MOCK_JWT =
  'eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJhZG1pbiIsInJvbGUiOiJhZG1pbiIsImV4cCI6OTk5OTk5OTk5OX0.mock-signature';

setup('authenticate', async ({ page }) => {
  // 先访问任意页面，确保 localStorage 可用
  await page.goto('/login');

  // 直接注入 Mock JWT Token
  await page.evaluate((token) => {
    localStorage.setItem('ckyclaw_token', token);
  }, MOCK_JWT);

  // 验证 token 已写入
  const stored = await page.evaluate(() => localStorage.getItem('ckyclaw_token'));
  expect(stored).toBe(MOCK_JWT);

  // 导航到受保护页面，确保 RequireAuth 放行
  await page.goto('/providers');
  await expect(page).toHaveURL(/\/providers/, { timeout: 10_000 });

  // 持久化认证状态（含 localStorage）
  await page.context().storageState({ path: STORAGE_STATE });
});

export { STORAGE_STATE };
