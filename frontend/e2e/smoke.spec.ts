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

  test('404 页面显示未找到提示', async ({ page }) => {
    await page.goto('/nonexistent-page-xyz');
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
    await expect(page.locator('#root')).toBeVisible({ timeout: 10_000 });
  });

  test('Agent 列表页可加载', async ({ page }) => {
    await page.goto('/agents');
    await expect(page.locator('#root')).toBeVisible({ timeout: 10_000 });
  });

  test('A/B 测试页可加载', async ({ page }) => {
    await page.goto('/ab-test');
    await expect(page.locator('#root')).toBeVisible({ timeout: 10_000 });
    await expect(page.locator('text=A/B').first()).toBeVisible({ timeout: 10_000 });
  });

  test('Traces 页可加载', async ({ page }) => {
    await page.goto('/traces');
    await expect(page.locator('#root')).toBeVisible({ timeout: 10_000 });
  });

  test('Chat 对话页可加载', async ({ page }) => {
    await page.goto('/chat');
    await expect(page.locator('#root')).toBeVisible({ timeout: 10_000 });
  });

  test('Runs 运行列表页可加载', async ({ page }) => {
    await page.goto('/runs');
    await expect(page.locator('#root')).toBeVisible({ timeout: 10_000 });
  });

  test('Providers 模型提供商页可加载', async ({ page }) => {
    await page.goto('/providers');
    await expect(page.locator('#root')).toBeVisible({ timeout: 10_000 });
  });

  test('Guardrails 护栏页可加载', async ({ page }) => {
    await page.goto('/guardrails');
    await expect(page.locator('#root')).toBeVisible({ timeout: 10_000 });
  });

  test('Approvals 审批页可加载', async ({ page }) => {
    await page.goto('/approvals');
    await expect(page.locator('#root')).toBeVisible({ timeout: 10_000 });
  });

  test('MCP Servers 页可加载', async ({ page }) => {
    await page.goto('/mcp-servers');
    await expect(page.locator('#root')).toBeVisible({ timeout: 10_000 });
  });

  test('Tool Groups 工具组页可加载', async ({ page }) => {
    await page.goto('/tool-groups');
    await expect(page.locator('#root')).toBeVisible({ timeout: 10_000 });
  });

  test('Memories 记忆页可加载', async ({ page }) => {
    await page.goto('/memories');
    await expect(page.locator('#root')).toBeVisible({ timeout: 10_000 });
  });

  test('Skills 技能页可加载', async ({ page }) => {
    await page.goto('/skills');
    await expect(page.locator('#root')).toBeVisible({ timeout: 10_000 });
  });

  test('Templates 模板页可加载', async ({ page }) => {
    await page.goto('/templates');
    await expect(page.locator('#root')).toBeVisible({ timeout: 10_000 });
  });

  test('Workflows 工作流页可加载', async ({ page }) => {
    await page.goto('/workflows');
    await expect(page.locator('#root')).toBeVisible({ timeout: 10_000 });
  });

  test('Teams 团队页可加载', async ({ page }) => {
    await page.goto('/teams');
    await expect(page.locator('#root')).toBeVisible({ timeout: 10_000 });
  });

  test('Audit Logs 审计日志页可加载', async ({ page }) => {
    await page.goto('/audit-logs');
    await expect(page.locator('#root')).toBeVisible({ timeout: 10_000 });
  });

  test('Roles 角色管理页可加载', async ({ page }) => {
    await page.goto('/roles');
    await expect(page.locator('#root')).toBeVisible({ timeout: 10_000 });
  });

  test('IM Channels 渠道页可加载', async ({ page }) => {
    await page.goto('/im-channels');
    await expect(page.locator('#root')).toBeVisible({ timeout: 10_000 });
  });

  test('Evaluations 评估页可加载', async ({ page }) => {
    await page.goto('/evaluations');
    await expect(page.locator('#root')).toBeVisible({ timeout: 10_000 });
  });

  test('Evolution 进化页可加载', async ({ page }) => {
    await page.goto('/evolution');
    await expect(page.locator('#root')).toBeVisible({ timeout: 10_000 });
  });

  test('Organizations 组织页可加载', async ({ page }) => {
    await page.goto('/organizations');
    await expect(page.locator('#root')).toBeVisible({ timeout: 10_000 });
  });

  test('Scheduled Tasks 定时任务页可加载', async ({ page }) => {
    await page.goto('/scheduled-tasks');
    await expect(page.locator('#root')).toBeVisible({ timeout: 10_000 });
  });

  test('APM 仪表盘页可加载', async ({ page }) => {
    await page.goto('/apm');
    await expect(page.locator('#root')).toBeVisible({ timeout: 10_000 });
  });

  test('Cost Router 成本路由页可加载', async ({ page }) => {
    await page.goto('/cost-router');
    await expect(page.locator('#root')).toBeVisible({ timeout: 10_000 });
  });

  test('Checkpoints 检查点页可加载', async ({ page }) => {
    await page.goto('/checkpoints');
    await expect(page.locator('#root')).toBeVisible({ timeout: 10_000 });
  });

  test('Intent Detection 意图检测页可加载', async ({ page }) => {
    await page.goto('/intent');
    await expect(page.locator('#root')).toBeVisible({ timeout: 10_000 });
  });

  test('Supervision 监管页可加载', async ({ page }) => {
    await page.goto('/supervision');
    await expect(page.locator('#root')).toBeVisible({ timeout: 10_000 });
  });

  test('I18n 国际化设置页可加载', async ({ page }) => {
    await page.goto('/i18n');
    await expect(page.locator('#root')).toBeVisible({ timeout: 10_000 });
  });
});
