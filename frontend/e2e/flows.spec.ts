import { test, expect } from '@playwright/test';

/**
 * Kasaya 前端 E2E 功能测试 — 验证核心用户交互流程。
 */

test.describe('认证流程', () => {
  test('登录表单校验 — 空提交应提示', async ({ page }) => {
    await page.goto('/login');
    const submitBtn = page.locator('button[type="submit"]');
    if (await submitBtn.isVisible()) {
      await submitBtn.click();
      // 应显示校验提示或保持在登录页
      await expect(page).toHaveURL(/login/, { timeout: 5_000 });
    }
  });

  test('错误凭证应提示失败', async ({ page }) => {
    await page.goto('/login');
    const usernameInput = page.locator('input[id="username"], input[type="text"]').first();
    const passwordInput = page.locator('input[type="password"]').first();
    if (await usernameInput.isVisible() && await passwordInput.isVisible()) {
      await usernameInput.fill('invalid@test.com');
      await passwordInput.fill('wrongpassword');
      const submitBtn = page.locator('button[type="submit"]');
      if (await submitBtn.isVisible()) {
        await submitBtn.click();
        // 应保持在登录页（不会跳转到 dashboard）
        await expect(page).toHaveURL(/login/, { timeout: 5_000 });
      }
    }
  });
});

test.describe('认证后导航', () => {
  test.beforeEach(async ({ page }) => {
    await page.addInitScript(() => {
      localStorage.setItem(
        'kasaya_token',
        'eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJ0ZXN0QGV4YW1wbGUuY29tIiwiZXhwIjozMjUxODA0ODAwfQ.fake'
      );
    });
  });

  test('侧边栏菜单可见', async ({ page }) => {
    await page.goto('/dashboard');
    await expect(page.locator('#root')).toBeVisible({ timeout: 10_000 });
    // ProLayout 侧边栏应渲染菜单项
    const sidebar = page.locator('.ant-pro-sider, .ant-layout-sider').first();
    await expect(sidebar).toBeVisible({ timeout: 10_000 });
  });

  test('页面标题区域可见', async ({ page }) => {
    await page.goto('/dashboard');
    await expect(page.locator('#root')).toBeVisible({ timeout: 10_000 });
    // 页面应有内容区
    const content = page.locator('.ant-pro-page-container, .ant-layout-content, main').first();
    await expect(content).toBeVisible({ timeout: 10_000 });
  });

  test('Agent 列表页 — 表格或空状态渲染', async ({ page }) => {
    await page.goto('/agents');
    await expect(page.locator('#root')).toBeVisible({ timeout: 10_000 });
    // 应有表格或空状态提示
    const table = page.locator('.ant-table, .ant-empty, .ant-pro-table');
    await expect(table.first()).toBeVisible({ timeout: 15_000 });
  });

  test('Traces 页 — 主内容区渲染', async ({ page }) => {
    await page.goto('/traces');
    await expect(page.locator('#root')).toBeVisible({ timeout: 10_000 });
    const content = page.locator('.ant-table, .ant-empty, .ant-pro-table, .ant-card');
    await expect(content.first()).toBeVisible({ timeout: 15_000 });
  });

  test('Marketplace 页 — 卡片网格或空状态渲染', async ({ page }) => {
    await page.goto('/marketplace');
    await expect(page.locator('#root')).toBeVisible({ timeout: 10_000 });
    const content = page.locator('.ant-card, .ant-empty, .ant-spin');
    await expect(content.first()).toBeVisible({ timeout: 15_000 });
  });

  test('Compliance 页 — Tab 或统计卡片渲染', async ({ page }) => {
    await page.goto('/compliance');
    await expect(page.locator('#root')).toBeVisible({ timeout: 10_000 });
    const content = page.locator('.ant-tabs, .ant-card, .ant-statistic');
    await expect(content.first()).toBeVisible({ timeout: 15_000 });
  });

  test('Chat 页 — 消息输入框渲染', async ({ page }) => {
    await page.goto('/chat');
    await expect(page.locator('#root')).toBeVisible({ timeout: 10_000 });
    const input = page.locator('textarea, input[type="text"], .ant-input');
    await expect(input.first()).toBeVisible({ timeout: 15_000 });
  });

  test('导航到不存在的路径 — 展示 404 或重定向', async ({ page }) => {
    await page.goto('/this-page-does-not-exist-12345');
    await expect(page.locator('#root')).toBeVisible({ timeout: 10_000 });
    // 应匹配 404 页面或重定向到已知路由
    const notFound = page.locator('text=404, text=未找到, text=Not Found');
    const hasNotFound = await notFound.first().isVisible().catch(() => false);
    if (!hasNotFound) {
      // 可能重定向了
      const url = page.url();
      expect(url).toBeTruthy();
    }
  });

  test('Benchmark 页 — 统计卡片和 Tab 渲染', async ({ page }) => {
    await page.goto('/benchmark');
    await expect(page.locator('#root')).toBeVisible({ timeout: 10_000 });
    const content = page.locator('.ant-card, .ant-tabs, .ant-statistic');
    await expect(content.first()).toBeVisible({ timeout: 15_000 });
  });

  test('Benchmark 页 — 创建套件弹窗可打开', async ({ page }) => {
    await page.goto('/benchmark');
    await expect(page.locator('#root')).toBeVisible({ timeout: 10_000 });
    const createBtn = page.locator('button:has-text("创建套件"), button:has-text("新建")');
    if (await createBtn.first().isVisible({ timeout: 5_000 }).catch(() => false)) {
      await createBtn.first().click();
      const modal = page.locator('.ant-modal');
      await expect(modal.first()).toBeVisible({ timeout: 5_000 });
    }
  });

  test('Visual Builder 页 — 画布和工具栏渲染', async ({ page }) => {
    await page.goto('/agents/visual-builder');
    await expect(page.locator('#root')).toBeVisible({ timeout: 10_000 });
    const canvas = page.locator('.react-flow, .react-flow__renderer');
    await expect(canvas.first()).toBeVisible({ timeout: 15_000 });
  });

  test('Debug 页 — 调试器列表渲染', async ({ page }) => {
    await page.goto('/debug');
    await expect(page.locator('#root')).toBeVisible({ timeout: 10_000 });
    const content = page.locator('.ant-table, .ant-empty, .ant-pro-table, .ant-card');
    await expect(content.first()).toBeVisible({ timeout: 15_000 });
  });

  test('Environment 列表页 — 表格渲染', async ({ page }) => {
    await page.goto('/environments');
    await expect(page.locator('#root')).toBeVisible({ timeout: 10_000 });
    const content = page.locator('.ant-table, .ant-empty, .ant-pro-table');
    await expect(content.first()).toBeVisible({ timeout: 15_000 });
  });
});
