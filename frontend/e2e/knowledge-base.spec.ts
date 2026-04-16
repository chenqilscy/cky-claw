import { test, expect } from '@playwright/test';
import { KnowledgeBasePage } from './pom/KnowledgeBasePage';
import { registerMocks } from './mocks/index';
import { knowledgeBaseMocks, kbStore } from './mocks/knowledgeBaseMocks';

/**
 * CkyClaw 知识库管理 E2E 测试。
 *
 * 使用 API Mock 拦截所有 /api/v1/knowledge-bases/** 请求，不依赖真实后端。
 */
test.describe('知识库管理', () => {
  let kbPage: KnowledgeBasePage;

  test.beforeEach(async ({ page }) => {
    // 注册 mock 拦截
    await registerMocks(page, [knowledgeBaseMocks]);
    kbPage = new KnowledgeBasePage(page);

    // 模拟已登录状态
    await page.goto('/');
    await page.evaluate(() => {
      localStorage.setItem('ckyclaw_token', 'mock-e2e-token');
    });
  });

  // 1. 列表页渲染
  test('列表页渲染 — 表格显示 mock 数据', async ({ page }) => {
    await kbPage.goto();

    // 表格应可见
    await expect(page.locator('.ant-table')).toBeVisible({ timeout: 10_000 });

    // 应显示预设的 mock 知识库
    await kbPage.expectInTable('e2e-mock-kb');
  });

  // 2. 新建知识库完整流程
  test('新建知识库完整流程', async ({ page }) => {
    await kbPage.goto();

    const kbName = `e2e-test-kb-${Date.now()}`;
    await kbPage.clickCreate();
    await kbPage.fillCreateForm({
      name: kbName,
      description: 'E2E 自动创建的知识库',
    });
    await kbPage.confirmCreate();

    // 等待成功提示
    await kbPage.waitForSuccessMessage();

    // 新知识库应出现在列表中
    await kbPage.expectInTable(kbName);
  });

  // 3. 新建知识库必填校验
  test('新建知识库必填校验 — 空名称', async ({ page }) => {
    await kbPage.goto();

    await kbPage.clickCreate();
    // 不填写名称，直接点确认
    await kbPage.confirmCreate();

    // 应出现校验错误
    const errorMsg = page.locator('.ant-form-item-explain-error');
    await expect(errorMsg.first()).toBeVisible({ timeout: 5_000 });
    await expect(errorMsg.first()).toContainText('请输入名称');
  });

  // 4. 编辑知识库
  test('编辑知识库 — 修改名称和描述', async ({ page }) => {
    await kbPage.goto();

    // 点击预设知识库的编辑按钮
    await kbPage.clickEdit('e2e-mock-kb');

    // 修改描述
    const newDesc = `更新后的描述 ${Date.now()}`;
    await kbPage.fillEditForm({ description: newDesc });
    await kbPage.confirmCreate();

    // 等待成功提示
    await kbPage.waitForSuccessMessage();
  });

  // 5. 删除知识库
  test('删除知识库 — 确认后不再出现', async ({ page }) => {
    await kbPage.goto();

    // 删除预设知识库
    await kbPage.clickDelete('e2e-mock-kb');

    // 等待成功提示
    await kbPage.waitForSuccessMessage();

    // 该知识库不应再出现在列表中
    await kbPage.expectNotInTable('e2e-mock-kb');
  });

  // 6. 查看知识库详情
  test('查看知识库详情 — Modal 打开', async ({ page }) => {
    await kbPage.goto();

    // 点击详情按钮
    await kbPage.clickDetail('e2e-mock-kb');

    // 详情 Modal 应打开，包含知识库名称
    await kbPage.expectDetailContains('e2e-mock-kb');

    // 详情中应有文档 Tab
    const modal = page.locator('.ant-modal-wrap:visible');
    await expect(modal.locator('.ant-tabs-tab').getByText('文档')).toBeVisible({ timeout: 5_000 });
  });

  // 7. 知识库模式选择
  test('知识库模式选择 — 创建时选择不同模式', async ({ page }) => {
    await kbPage.goto();

    const kbName = `e2e-mode-kb-${Date.now()}`;
    await kbPage.clickCreate();
    await kbPage.fillCreateForm({
      name: kbName,
      mode: '图谱检索 (graph)',
    });
    await kbPage.confirmCreate();

    // 等待成功提示
    await kbPage.waitForSuccessMessage();

    // 新知识库应出现在列表中
    await kbPage.expectInTable(kbName);
  });

  // 8. 知识库列表显示模式 Tag
  test('知识库列表显示模式 Tag — 断言 graph Tag', async ({ page }) => {
    await kbPage.goto();

    // 预设知识库 mode='graph'，表格中应显示 graph Tag
    await kbPage.expectModeTag('graph');
  });

  // 9. 详情弹窗关闭
  test('详情弹窗关闭 — 打开后关闭 Modal 消失', async ({ page }) => {
    await kbPage.goto();

    // 打开详情
    await kbPage.clickDetail('e2e-mock-kb');
    await kbPage.expectDetailContains('e2e-mock-kb');

    // 点击 Modal 的关闭按钮（X 或取消）
    const modal = page.locator('.ant-modal-wrap:visible');
    const closeBtn = modal.locator('.ant-modal-close').first();
    await closeBtn.click();

    // Modal 应关闭
    await kbPage.expectDetailClosed();
  });

  // 10. 新建知识库选择 Embedding 模型
  test('新建知识库选择 Embedding 模型', async ({ page }) => {
    await kbPage.goto();

    const kbName = `e2e-embedding-kb-${Date.now()}`;
    await kbPage.clickCreate();
    await kbPage.fillCreateForm({
      name: kbName,
      embedding_model: 'text-embedding-3-large',
      description: '测试 Embedding 模型选择',
    });
    await kbPage.confirmCreate();

    // 等待成功提示
    await kbPage.waitForSuccessMessage();

    // 新知识库应出现在列表中
    await kbPage.expectInTable(kbName);
  });
});
