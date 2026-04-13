import { test as setup, expect } from '@playwright/test';

/**
 * 全局认证设置 — 执行真实登录并保存浏览器状态。
 * 后续测试复用此认证状态，无需重复登录。
 */

const STORAGE_STATE = 'test-results/.auth/user.json';

setup('authenticate', async ({ page }) => {
  await page.goto('/login');

  // 填写登录表单
  const username = page.locator('input[aria-label="用户名"]');
  const password = page.locator('input[aria-label="密码"]');
  await expect(username).toBeVisible({ timeout: 10_000 });

  await username.fill('admin');
  await password.fill('Admin888!');
  await page.locator('button[type="submit"]').click();

  // 等待登录成功 — 跳转到 /chat
  await expect(page).toHaveURL(/\/(chat|dashboard)/, { timeout: 15_000 });

  // 确保 token 已存入 localStorage
  const token = await page.evaluate(() => localStorage.getItem('ckyclaw_token'));
  expect(token).toBeTruthy();

  // 持久化认证状态
  await page.context().storageState({ path: STORAGE_STATE });
});

export { STORAGE_STATE };
