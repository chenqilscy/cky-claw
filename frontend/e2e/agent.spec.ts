import { test, expect } from '@playwright/test';
import { registerMocks } from './mocks/index';
import { agentMocks, seedAgents } from './mocks/agentMocks';
import { AgentListPage } from './pom/AgentListPage';
import { AgentEditPage } from './pom/AgentEditPage';

/**
 * CkyClaw Agent（智能体）模块 E2E 测试。
 *
 * 覆盖：列表渲染、五步向导创建、编辑、删除、搜索、校验、分页。
 * 所有 API 通过 agentMocks 拦截，无需后端服务。
 */

/* ---- 公共 beforeEach：认证 + Mock 注册 ---- */

test.beforeEach(async ({ page }) => {
  // 注入 JWT token 模拟已认证状态
  await page.addInitScript(() => {
    localStorage.setItem(
      'ckyclaw_token',
      'eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJ0ZXN0QGV4YW1wbGUuY29tIiwiZXhwIjozMjUxODA0ODAwfQ.fake',
    );
  });
  // 注册 Agent Mock（含 Provider 级联 Mock）
  await registerMocks(page, [agentMocks]);
});

/* ================================================
 * 1. 列表页渲染 — 表格显示 mock 数据
 * ================================================ */
test('列表页渲染 — 表格显示 mock 数据', async ({ page }) => {
  const listPage = new AgentListPage(page);
  await listPage.goto();

  // 表格可见
  await expect(listPage.table).toBeVisible({ timeout: 10_000 });

  // 预设的 2 条 mock Agent 应显示在表格中
  await listPage.expectAgentInTable('e2e-mock-agent-1');
  await listPage.expectAgentInTable('e2e-mock-agent-2');

  // 列头可见
  await expect(page.locator('.ant-table-thead th').getByText('名称')).toBeVisible();
  await expect(page.locator('.ant-table-thead th').getByText('描述')).toBeVisible();
  await expect(page.locator('.ant-table-thead th').getByText('模型')).toBeVisible();
});

/* ================================================
 * 2. 创建 Agent — 步骤 1 必填校验
 * ================================================ */
test('创建 Agent — 步骤 1 必填校验（不填名称 → 校验错误）', async ({ page }) => {
  const editPage = new AgentEditPage(page);
  await editPage.gotoCreate();

  // 当前步骤为 "基本信息"
  await editPage.expectStepActive('基本信息');

  // 不填任何字段，直接点下一步
  await editPage.clickNext();

  // 应出现校验错误提示
  await editPage.expectValidationError();
});

/* ================================================
 * 3. 创建 Agent — 步骤 1 填写后可前进
 * ================================================ */
test('创建 Agent — 步骤 1 填写后可前进（填名称 → 下一步 → 断言步骤 2 激活）', async ({ page }) => {
  const editPage = new AgentEditPage(page);
  await editPage.gotoCreate();

  // 填写名称
  await editPage.fillStep1({ name: 'test-forward-agent' });

  // 点击下一步
  await editPage.clickNext();

  // 断言步骤 2 "模型配置" 激活
  await editPage.expectStepActive('模型配置');
});

/* ================================================
 * 4. 创建 Agent — 前进/后退导航
 * ================================================ */
test('创建 Agent — 前进/后退导航（步骤 1→2→1，断言数据保留）', async ({ page }) => {
  const editPage = new AgentEditPage(page);
  await editPage.gotoCreate();

  const agentName = 'nav-test-agent';

  // 步骤 1：填写名称
  await editPage.fillStep1({
    name: agentName,
    description: '导航测试描述',
    instructions: '导航测试指令',
  });
  await editPage.clickNext();

  // 步骤 2 激活
  await editPage.expectStepActive('模型配置');

  // 点击上一步
  await editPage.clickPrev();

  // 应回到步骤 1
  await editPage.expectStepActive('基本信息');

  // 数据应保留
  const savedName = await editPage.getFieldValue('name');
  expect(savedName).toBe(agentName);
});

/* ================================================
 * 5. 创建 Agent — Provider/Model 级联选择
 * ================================================ */
test('创建 Agent — Provider/Model 级联选择（选 Provider → Model 出现选项 → 选择）', async ({ page }) => {
  const editPage = new AgentEditPage(page);
  await editPage.gotoCreate();

  // 通过步骤 1
  await editPage.passStep1('cascade-test-agent');

  // 步骤 2 激活
  await editPage.expectStepActive('模型配置');

  // 选择 Provider（Mock 中预设了 e2e-mock-openai）
  await editPage.selectProvider('e2e-mock-openai (openai)');

  // 选择 Model（Mock 中预设了 gpt-4o）
  await editPage.selectModel('GPT-4o');

  // 验证选中状态：Model 下拉应显示已选文本
  const modelFormItem = page.getByLabel('选择模型').locator('..').locator('..');
  await expect(modelFormItem).toContainText('GPT-4o', { timeout: 5_000 });
});

/* ================================================
 * 6. 创建 Agent — 完整五步创建
 * ================================================ */
test('创建 Agent — 完整五步创建（基本信息→模型配置→工具→编排→安全→创建→断言成功）', async ({ page }) => {
  const editPage = new AgentEditPage(page);
  await editPage.gotoCreate();

  const agentName = 'e2e-full-create-agent';

  // 步骤 1：基本信息
  await editPage.fillStep1({
    name: agentName,
    description: 'E2E 完整创建测试',
    instructions: '你是一个用于完整流程测试的 Agent',
  });
  await editPage.clickNext();

  // 步骤 2：模型配置
  await editPage.selectProvider('e2e-mock-openai (openai)');
  await editPage.selectModel('GPT-4o');
  await editPage.clickNext();

  // 步骤 3：工具配置（跳过，不选任何工具）
  await editPage.expectStepActive('工具配置');
  await editPage.clickNext();

  // 步骤 4：编排配置（跳过）
  await editPage.expectStepActive('编排配置');
  await editPage.clickNext();

  // 步骤 5：安全与高级
  await editPage.expectStepActive('安全与高级');

  // 点击创建
  await editPage.clickSubmit();

  // 等待成功提示或页面跳转
  const successMsg = page.locator('.ant-message-success');
  const navigated = page.waitForURL(/\/agents$/, { timeout: 5_000 });
  await Promise.race([successMsg.waitFor({ state: 'visible', timeout: 5_000 }).catch(() => {}), navigated.catch(() => {})]);

  // 验证跳转到列表页或成功提示
  const url = page.url();
  const isOnList = url.includes('/agents') && !url.includes('/new') && !url.includes('/edit');
  const hasMsg = await successMsg.isVisible().catch(() => false);
  expect(isOnList || hasMsg).toBeTruthy();
});

/* ================================================
 * 7. 编辑 Agent — 加载已有数据
 * ================================================ */
test('编辑 Agent — 加载已有数据（导航到编辑页 → 断言名称已填充）', async ({ page }) => {
  const editPage = new AgentEditPage(page);
  // 导航到预设 Agent 的编辑页
  await editPage.gotoEdit('e2e-mock-agent-1');

  // 等待页面加载
  await editPage.expectStepActive('基本信息');

  // 名称字段应已填充（编辑模式 disabled）
  const nameInput = page.locator('#name input, #name');
  const nameValue = await nameInput.first().inputValue();
  expect(nameValue).toBe('e2e-mock-agent-1');
});

/* ================================================
 * 8. 编辑 Agent — 修改描述和指令
 * ================================================ */
test('编辑 Agent — 修改描述和指令（修改 → 保存 → 成功）', async ({ page }) => {
  const editPage = new AgentEditPage(page);
  await editPage.gotoEdit('e2e-mock-agent-1');
  await editPage.expectStepActive('基本信息');

  // 修改描述
  await editPage.fillTextArea('description', '更新后的描述 — E2E 编辑测试');

  // 修改指令
  await editPage.fillTextArea('instructions', '更新后的指令 — 你是一个已修改的测试助手');

  // 跳到步骤 5（最终步骤）点击保存
  await editPage.clickNext(); // → 步骤 2
  await editPage.clickNext(); // → 步骤 3
  await editPage.clickNext(); // → 步骤 4
  await editPage.clickNext(); // → 步骤 5
  await editPage.expectStepActive('安全与高级');

  // 点击保存
  await editPage.clickSubmit();

  // 等待成功提示
  const successMsg = page.locator('.ant-message-success');
  await expect(successMsg).toBeVisible({ timeout: 5_000 });
});

/* ================================================
 * 9. 删除 Agent
 * ================================================ */
test('删除 Agent（Dropdown 删除 → 确认 → 不再出现）', async ({ page }) => {
  const listPage = new AgentListPage(page);
  await listPage.goto();

  // 确认预设 Agent 可见
  await listPage.expectAgentInTable('e2e-mock-agent-2');

  // 执行删除
  await listPage.clickDelete('e2e-mock-agent-2');

  // 等待成功提示
  await listPage.waitForSuccessMessage();

  // Agent 不再出现在表格中
  await listPage.expectAgentNotInTable('e2e-mock-agent-2');
});

/* ================================================
 * 10. 搜索 Agent
 * ================================================ */
test('搜索 Agent（输入不存在名称 → 空结果）', async ({ page }) => {
  const listPage = new AgentListPage(page);
  await listPage.goto();

  // 搜索不存在的 Agent
  await listPage.searchAgent('nonexistent-agent-xyz');

  // 表格应为空
  await listPage.expectEmptyTable();
});

/* ================================================
 * 11. 创建 Agent — 名称格式校验
 * ================================================ */
test('创建 Agent — 名称格式校验（输入大写 → 校验错误）', async ({ page }) => {
  const editPage = new AgentEditPage(page);
  await editPage.gotoCreate();

  // 输入包含大写字母的名称
  await editPage.fillField('name', 'InvalidAgentName');

  // 触发校验
  await editPage.clickNext();

  // 应出现格式校验错误（提示包含 "小写字母" 相关文本）
  await editPage.expectValidationError();
  const errorText = page.locator('.ant-form-item-explain-error').first();
  await expect(errorText).toContainText(/小写/);
});

/* ================================================
 * 12. 创建 Agent — 选择审批模式
 * ================================================ */
test('创建 Agent — 选择审批模式（步骤 2 切换审批模式）', async ({ page }) => {
  const editPage = new AgentEditPage(page);
  await editPage.gotoCreate();

  // 通过步骤 1
  await editPage.passStep1('approval-mode-test');
  await editPage.expectStepActive('模型配置');

  // 切换审批模式为 full-auto
  await editPage.selectApprovalMode('Full Auto');

  // 验证选中状态
  const approvalFormItem = page.getByLabel('审批模式').locator('..').locator('..');
  await expect(approvalFormItem).toContainText('Full Auto', { timeout: 5_000 });
});

/* ================================================
 * 13. 列表页分页
 * ================================================ */
test('列表页分页（mock 大量数据 → 验证分页控件）', async ({ page }) => {
  // 额外填充 25 条 mock Agent（加上预设 2 条 = 27 条）
  seedAgents(25);

  const listPage = new AgentListPage(page);
  await listPage.goto();

  // 分页控件可见
  const pagination = page.locator('.ant-pagination');
  await expect(pagination).toBeVisible({ timeout: 10_000 });

  // "共 27 条" 文本可见
  await listPage.expectPaginationText('共 27 条');

  // 分页大小切换器可见
  const sizeChanger = pagination.locator('.ant-pagination-options-size-changer');
  await expect(sizeChanger).toBeVisible();
});

/* ================================================
 * 14. 创建后列表刷新
 * ================================================ */
test('创建后列表刷新（创建 Agent → 返回列表 → 断言新 Agent 出现）', async ({ page }) => {
  const newAgentName = 'e2e-new-refreshed-agent';

  // 步骤 1: 创建 Agent
  const editPage = new AgentEditPage(page);
  await editPage.gotoCreate();

  await editPage.fillStep1({
    name: newAgentName,
    description: '创建后列表刷新测试',
  });
  await editPage.clickNext();

  // 步骤 2: 模型配置（选择 Provider 和 Model）
  await editPage.selectProvider('e2e-mock-openai (openai)');
  await editPage.selectModel('GPT-4o');
  await editPage.clickNext();

  // 步骤 3-4: 跳过
  await editPage.clickNext(); // 工具配置
  await editPage.clickNext(); // 编排配置

  // 步骤 5: 安全与高级 → 创建
  await editPage.expectStepActive('安全与高级');
  await editPage.clickSubmit();

  // 等待跳转到列表页
  await page.waitForURL(/\/agents$/, { timeout: 5_000 }).catch(() => {});
  await page.waitForTimeout(500);

  // 步骤 2: 验证列表页出现新 Agent
  const listPage = new AgentListPage(page);
  await listPage.expectAgentInTable(newAgentName);
});
