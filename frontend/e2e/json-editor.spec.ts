import { test, expect } from '@playwright/test';

/**
 * JSON 编辑器相关 E2E 烟雾测试。
 * 目标：验证使用 JsonEditor 的关键页面可以正常加载对应表单区域。
 */

test.describe('JsonEditor 页面烟雾测试', () => {
  test.beforeEach(async ({ page }) => {
    await page.addInitScript(() => {
      localStorage.setItem(
        'ckyclaw_token',
        'eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJ0ZXN0QGV4YW1wbGUuY29tIiwiZXhwIjozMjUxODA0ODAwfQ.fake',
      );
    });
  });

  test('Provider 新建页可加载基础表单', async ({ page }) => {
    await page.goto('/providers/new');
    await expect(page.locator('#root')).toBeVisible({ timeout: 10_000 });
    await expect(page.getByText('注册新 Provider')).toBeVisible({ timeout: 10_000 });
    await expect(page.getByText('厂商类型')).toBeVisible({ timeout: 10_000 });
    await expect(page.getByText('Base URL')).toBeVisible({ timeout: 10_000 });
  });

  test('Agent 新建页显示 JSON Schema 字段', async ({ page }) => {
    await page.goto('/agents/new');
    await expect(page.locator('#root')).toBeVisible({ timeout: 10_000 });
    await expect(page.getByText('结构化输出（JSON Schema）')).toBeVisible({ timeout: 10_000 });
  });

  test('Workflow 页面可打开新建表单并显示 JSON 字段', async ({ page }) => {
    await page.goto('/workflows');
    await expect(page.locator('#root')).toBeVisible({ timeout: 10_000 });
    await page.getByRole('button', { name: '新建工作流' }).click();
    await expect(page.getByText('步骤 (JSON)')).toBeVisible({ timeout: 10_000 });
    await expect(page.getByText('边 (JSON)')).toBeVisible({ timeout: 10_000 });
  });
});
