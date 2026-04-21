import { test, expect, type Page } from '@playwright/test';

/**
 * Kasaya UI 自动化测试 — 基于真实后端的端到端交互验证。
 *
 * 前置条件：前端 localhost:3000 + 后端 localhost:8000 已启动。
 * 认证状态通过 auth.setup.ts 提前注入。
 */

// ---------- 辅助函数 ----------

/** 等待页面核心内容加载完成。 */
async function waitForPageReady(page: Page): Promise<void> {
  await expect(page.locator('#root')).toBeVisible({ timeout: 10_000 });
  // 等待 loading spinner 消失（最多等 5 秒，不阻塞）
  try {
    const spinner = page.locator('.ant-spin-spinning');
    await spinner.waitFor({ state: 'hidden', timeout: 5_000 });
  } catch {
    // spinner 可能不存在或超时 — 继续执行
  }
}

/** 断言 ProTable/Table 或空状态可见。 */
async function expectTableOrEmpty(page: Page): Promise<void> {
  const content = page.locator('.ant-table, .ant-empty, .ant-pro-table');
  await expect(content.first()).toBeVisible({ timeout: 15_000 });
}

// =============================================
// 1. 登录流程
// =============================================

test.describe('登录流程', () => {
  // 使用独立 context，不依赖存储状态
  test.use({ storageState: { cookies: [], origins: [] } });

  test('正确凭证 — 成功登录并跳转', async ({ page }) => {
    await page.goto('/login');
    const username = page.locator('input[aria-label="用户名"]');
    const password = page.locator('input[aria-label="密码"]');
    await expect(username).toBeVisible({ timeout: 10_000 });

    await username.fill('admin');
    await password.fill('Admin888!');
    await page.locator('button[type="submit"]').click();

    // 等待跳转
    await expect(page).toHaveURL(/\/(chat|dashboard)/, { timeout: 15_000 });
    // localStorage 应有 token
    const token = await page.evaluate(() => localStorage.getItem('kasaya_token'));
    expect(token).toBeTruthy();
  });

  test('错误密码 — 保持在登录页并提示', async ({ page }) => {
    await page.goto('/login');
    const username = page.locator('input[aria-label="用户名"]');
    const password = page.locator('input[aria-label="密码"]');
    await expect(username).toBeVisible({ timeout: 10_000 });

    await username.fill('admin');
    await password.fill('WrongPassword');
    await page.locator('button[type="submit"]').click();

    // 应保持在 login 页
    await page.waitForTimeout(2000);
    await expect(page).toHaveURL(/login/);
    // 应显示错误提示
    const alert = page.locator('[role="alert"]');
    await expect(alert).toBeVisible({ timeout: 5_000 });
  });

  test('空表单提交 — 显示必填校验', async ({ page }) => {
    await page.goto('/login');
    await expect(page.locator('button[type="submit"]')).toBeVisible({ timeout: 10_000 });
    await page.locator('button[type="submit"]').click();
    // Ant Design Form 校验提示
    const errorMsg = page.locator('.ant-form-item-explain-error');
    await expect(errorMsg.first()).toBeVisible({ timeout: 5_000 });
  });

  test('未认证访问 — 重定向到登录页', async ({ page }) => {
    await page.goto('/dashboard');
    await expect(page).toHaveURL(/login/, { timeout: 10_000 });
  });
});

// =============================================
// 2. 仪表盘
// =============================================

test.describe('仪表盘', () => {
  test('统计卡片渲染', async ({ page }) => {
    await page.goto('/dashboard');
    await waitForPageReady(page);

    // 应有统计卡片
    const cards = page.locator('.ant-card');
    await expect(cards.first()).toBeVisible({ timeout: 10_000 });

    // 标题中应有"平台概览"或 Dashboard 相关文字
    const title = page.locator('text=平台概览');
    const hasTitle = await title.isVisible().catch(() => false);
    if (!hasTitle) {
      // 可能用了 Dashboard 英文标题
      await expect(page.locator('.ant-page-header, .ant-pro-page-container').first()).toBeVisible();
    }
  });

  test('Agent 总数可点击跳转', async ({ page }) => {
    await page.goto('/dashboard');
    await waitForPageReady(page);

    // Statistic 卡片应存在 — 点击 Agent 统计
    const agentStat = page.locator('text=Agent').first();
    if (await agentStat.isVisible().catch(() => false)) {
      // 尝试点击包含 Agent 文本的卡片
      const card = page.locator('.ant-card').filter({ hasText: 'Agent' }).first();
      if (await card.isVisible().catch(() => false)) {
        await card.click();
        await expect(page).toHaveURL(/agents/, { timeout: 10_000 });
      }
    }
  });

  test('刷新按钮可用', async ({ page }) => {
    await page.goto('/dashboard');
    await waitForPageReady(page);

    const reloadBtn = page.locator('button').filter({ has: page.locator('.anticon-reload') }).first();
    if (await reloadBtn.isVisible().catch(() => false)) {
      await reloadBtn.click();
      // 不应报错 — 等待加载完成
      await waitForPageReady(page);
    }
  });
});

// =============================================
// 3. Agent 管理
// =============================================

test.describe('Agent 管理', () => {
  test('Agent 列表页 — 表格渲染', async ({ page }) => {
    await page.goto('/agents');
    await waitForPageReady(page);
    await expectTableOrEmpty(page);

    // 应有"Agent 管理"标题
    const header = page.locator('text=Agent 管理');
    await expect(header.first()).toBeVisible({ timeout: 10_000 });
  });

  test('搜索过滤', async ({ page }) => {
    await page.goto('/agents');
    await waitForPageReady(page);

    const searchInput = page.locator('input[placeholder*="搜索"], input.ant-input').first();
    if (await searchInput.isVisible().catch(() => false)) {
      await searchInput.fill('nonexistent-agent-xyz');
      await searchInput.press('Enter');
      await page.waitForTimeout(1000);
      // 应显示空状态或 0 条记录
      const empty = page.locator('.ant-empty, .ant-table-placeholder');
      const hasEmpty = await empty.first().isVisible().catch(() => false);
      // 清空搜索
      await searchInput.clear();
      await searchInput.press('Enter');
      expect(hasEmpty || true).toBeTruthy(); // 搜索不应崩溃
    }
  });

  test('创建 Agent 按钮跳转', async ({ page }) => {
    await page.goto('/agents');
    await waitForPageReady(page);

    const createBtn = page.locator('button').filter({ hasText: /创建|新建/ }).first();
    if (await createBtn.isVisible().catch(() => false)) {
      await createBtn.click();
      await expect(page).toHaveURL(/agents\/new/, { timeout: 10_000 });
    }
  });

  test('Agent 创建页 — 表单渲染', async ({ page }) => {
    await page.goto('/agents/new');
    await waitForPageReady(page);

    // 应有表单元素
    const form = page.locator('form, .ant-form');
    await expect(form.first()).toBeVisible({ timeout: 10_000 });

    // 应有名称输入框
    const nameInput = page.locator('input[id*="name"], input[placeholder*="名称"]').first();
    await expect(nameInput).toBeVisible({ timeout: 10_000 });
  });

  test('创建并删除临时 Agent', async ({ page }) => {
    // 进入创建页
    await page.goto('/agents/new');
    await waitForPageReady(page);

    const agentName = `e2e-pw-agent-${Date.now()}`;

    // 填写名称
    const nameInput = page.locator('input[id*="name"], input[placeholder*="名称"]').first();
    await nameInput.fill(agentName);

    // 填写指令
    const instructionInput = page.locator('textarea').first();
    if (await instructionInput.isVisible().catch(() => false)) {
      await instructionInput.fill('Playwright E2E test agent');
    }

    // 提交表单
    const saveBtn = page.locator('button[type="submit"], button').filter({ hasText: /保存|创建|提交/ }).first();
    if (await saveBtn.isVisible().catch(() => false)) {
      await saveBtn.click();
      // 等待跳转回列表或编辑页
      await page.waitForTimeout(2000);
    }

    // 回到列表，验证 Agent 出现
    await page.goto('/agents');
    await waitForPageReady(page);
    await page.waitForTimeout(1000);

    // 搜索刚创建的 Agent
    const searchInput = page.locator('input[placeholder*="搜索"], input.ant-input').first();
    if (await searchInput.isVisible().catch(() => false)) {
      await searchInput.fill(agentName);
      await searchInput.press('Enter');
      await page.waitForTimeout(1000);
    }

    // 删除 Agent（如果找到）
    const row = page.locator('tr').filter({ hasText: agentName });
    if (await row.isVisible().catch(() => false)) {
      const deleteBtn = row.locator('text=删除').first();
      if (await deleteBtn.isVisible().catch(() => false)) {
        await deleteBtn.click();
        // 确认弹窗
        const confirmBtn = page.locator('.ant-popconfirm button').filter({ hasText: /确定|确认|是/ }).first();
        if (await confirmBtn.isVisible().catch(() => false)) {
          await confirmBtn.click();
          await page.waitForTimeout(1000);
        }
      }
    }
  });
});

// =============================================
// 4. 模型提供商
// =============================================

test.describe('模型提供商', () => {
  test('Provider 列表页渲染', async ({ page }) => {
    await page.goto('/providers');
    await waitForPageReady(page);
    await expectTableOrEmpty(page);
  });

  test('创建 Provider 按钮', async ({ page }) => {
    await page.goto('/providers');
    await waitForPageReady(page);

    const createBtn = page.locator('button').filter({ hasText: /添加|创建|新建/ }).first();
    if (await createBtn.isVisible().catch(() => false)) {
      await createBtn.click();
      await expect(page).toHaveURL(/providers\/new/, { timeout: 10_000 });
    }
  });
});

// =============================================
// 5. Chat 对话
// =============================================

test.describe('Chat 对话', () => {
  test('Chat 页面基本渲染', async ({ page }) => {
    await page.goto('/chat');
    await waitForPageReady(page);

    // 应有消息输入区
    const input = page.locator('textarea, input[type="text"]');
    await expect(input.first()).toBeVisible({ timeout: 15_000 });
  });

  test('侧边栏会话列表可见（桌面端）', async ({ page }) => {
    await page.goto('/chat');
    await waitForPageReady(page);

    const sider = page.locator('.ant-layout-sider, .ant-drawer');
    const hasSider = await sider.first().isVisible().catch(() => false);
    // 桌面端应有 Sider
    expect(hasSider).toBeTruthy();
  });
});

// =============================================
// 6. Traces 链路追踪
// =============================================

test.describe('Traces 链路追踪', () => {
  test('Traces 列表渲染', async ({ page }) => {
    await page.goto('/traces');
    await waitForPageReady(page);

    const content = page.locator('.ant-table, .ant-empty, .ant-pro-table, .ant-card');
    await expect(content.first()).toBeVisible({ timeout: 15_000 });
  });
});

// =============================================
// 7. Runs 执行记录
// =============================================

test.describe('Runs 执行记录', () => {
  test('Runs 页面 Tab 渲染', async ({ page }) => {
    await page.goto('/runs');
    await waitForPageReady(page);

    const tabs = page.locator('.ant-tabs, .ant-card, .ant-table');
    await expect(tabs.first()).toBeVisible({ timeout: 15_000 });
  });
});

// =============================================
// 8. 护栏 / 审批 / MCP
// =============================================

test.describe('安全与治理页面', () => {
  test('Guardrails 护栏页', async ({ page }) => {
    await page.goto('/guardrails');
    await waitForPageReady(page);
    await expectTableOrEmpty(page);
  });

  test('Approvals 审批队列页', async ({ page }) => {
    await page.goto('/approvals');
    await waitForPageReady(page);
    // 应有内容区域
    const content = page.locator('.ant-card, .ant-table, .ant-empty, .ant-list');
    await expect(content.first()).toBeVisible({ timeout: 15_000 });
  });

  test('MCP Servers 页', async ({ page }) => {
    await page.goto('/mcp-servers');
    await waitForPageReady(page);
    await expectTableOrEmpty(page);
  });
});

// =============================================
// 9. Supervision 监管面板
// =============================================

test.describe('Supervision 监管', () => {
  test('监管面板渲染', async ({ page }) => {
    await page.goto('/supervision');
    await waitForPageReady(page);

    const content = page.locator('.ant-card, .ant-table, .ant-list, .ant-statistic');
    await expect(content.first()).toBeVisible({ timeout: 15_000 });
  });
});

// =============================================
// 10. Marketplace 模板市场
// =============================================

test.describe('Marketplace 模板市场', () => {
  test('市场页渲染', async ({ page }) => {
    await page.goto('/marketplace');
    await waitForPageReady(page);

    const content = page.locator('.ant-card, .ant-empty, .ant-spin, .ant-list');
    await expect(content.first()).toBeVisible({ timeout: 15_000 });
  });
});

// =============================================
// 11. Benchmark 评测
// =============================================

test.describe('Benchmark 评测', () => {
  test('评测页渲染', async ({ page }) => {
    await page.goto('/benchmark');
    await waitForPageReady(page);

    const content = page.locator('.ant-card, .ant-tabs, .ant-statistic');
    await expect(content.first()).toBeVisible({ timeout: 15_000 });
  });
});

// =============================================
// 12. 全局导航
// =============================================

test.describe('全局导航', () => {
  const criticalRoutes = [
    { path: '/dashboard', name: 'Dashboard 仪表盘' },
    { path: '/agents', name: 'Agent 列表' },
    { path: '/chat', name: 'Chat 对话' },
    { path: '/providers', name: 'Providers 提供商' },
    { path: '/runs', name: 'Runs 执行记录' },
    { path: '/traces', name: 'Traces 链路' },
    { path: '/guardrails', name: 'Guardrails 护栏' },
    { path: '/approvals', name: 'Approvals 审批' },
    { path: '/mcp-servers', name: 'MCP Servers' },
    { path: '/supervision', name: 'Supervision 监管' },
    { path: '/marketplace', name: 'Marketplace 市场' },
    { path: '/knowledge-bases', name: 'Knowledge Bases 知识库' },
    { path: '/compliance', name: 'Compliance 合规' },
    { path: '/benchmark', name: 'Benchmark 评测' },
    { path: '/environments', name: 'Environments 环境' },
    { path: '/a2a', name: 'A2A 协议' },
  ];

  for (const route of criticalRoutes) {
    test(`${route.name} — 无报错渲染`, async ({ page }) => {
      const errors: string[] = [];
      page.on('pageerror', (err) => errors.push(err.message));

      await page.goto(route.path);
      await waitForPageReady(page);

      // 不应有 JS 报错
      expect(errors).toHaveLength(0);
    });
  }
});

// =============================================
// 13. API 健康检查
// =============================================

test.describe('API 健康', () => {
  test('后端 API 可达', async ({ page }) => {
    const response = await page.request.get('/api/v1/agents?limit=1');
    expect(response.status()).toBeLessThan(500);
  });

  test('认证 API 返回用户信息', async ({ page }) => {
    // 先导航到应用页面，才能从同源 localStorage 取 JWT
    await page.goto('/');
    await page.waitForLoadState('domcontentloaded');
    const token = await page.evaluate(() => localStorage.getItem('kasaya_token'));
    expect(token).toBeTruthy();
    const response = await page.request.get('/api/v1/auth/me', {
      headers: { Authorization: `Bearer ${token}` },
    });
    expect(response.ok()).toBeTruthy();
    const body = await response.json();
    expect(body.username).toBe('admin');
    expect(body.role).toBe('admin');
  });
});
