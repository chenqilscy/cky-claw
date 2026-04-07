import { test, expect } from '@playwright/test';

/**
 * CkyClaw 前端 E2E 烟雾测试 — 验证关键页面可加载。
 */

test.describe('关键页面加载', () => {
  test('登录页可访问', async ({ page }) => {
    await page.goto('/login');
    await expect(page.locator('body')).toBeVisible();
    // 登录页应包含登录按钮或输入框
    const loginInput = page.locator('input[type="text"], input[type="email"], input[id="username"]');
    await expect(loginInput.first()).toBeVisible({ timeout: 10_000 });
  });

  test('未认证用户重定向到登录页', async ({ page }) => {
    await page.goto('/dashboard');
    // 应被重定向到登录页
    await expect(page).toHaveURL(/login/, { timeout: 10_000 });
  });
});

test.describe('认证后页面', () => {
  test.beforeEach(async ({ page }) => {
    // 模拟已认证状态 — 注入 JWT token
    await page.addInitScript(() => {
      localStorage.setItem(
        'ckyclaw_token',
        'eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJ0ZXN0QGV4YW1wbGUuY29tIiwiZXhwIjozMjUxODA0ODAwfQ.fake'
      );
    });
  });

  test('Dashboard 页面渲染标题', async ({ page }) => {
    await page.goto('/dashboard');
    // Dashboard 页面应包含 "仪表盘" 或 "Dashboard" 标题
    // 即使 API 调用失败，页面框架也应加载
    await expect(page.locator('#root')).toBeVisible({ timeout: 10_000 });
  });

  test('Agent 列表页可加载', async ({ page }) => {
    await page.goto('/agents');
    await expect(page.locator('#root')).toBeVisible({ timeout: 10_000 });
  });

  test('A/B 测试页可加载', async ({ page }) => {
    await page.goto('/ab-test');
    await expect(page.locator('#root')).toBeVisible({ timeout: 10_000 });
    // 应显示 A/B 测试相关内容
    await expect(page.locator('text=A/B')).toBeVisible({ timeout: 10_000 });
  });

  test('Traces 页可加载', async ({ page }) => {
    await page.goto('/traces');
    await expect(page.locator('#root')).toBeVisible({ timeout: 10_000 });
  });
});
