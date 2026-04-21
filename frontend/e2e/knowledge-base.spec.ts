import { test, expect } from '@playwright/test';
import { KnowledgeBasePage } from './pom/KnowledgeBasePage';
import { registerMocks } from './mocks/index';
import { knowledgeBaseMocks, kbStore } from './mocks/knowledgeBaseMocks';

/**
 * Kasaya 知识库管理 E2E 测试。
 *
 * 使用 API Mock 拦截所有 /api/v1/knowledge-bases/** 请求，不依赖真实后端。
 */
test.describe('知识库管理', () => {
  let kbPage: KnowledgeBasePage;

  test.beforeEach(async ({ page }) => {
    // Catch-all：拦截未 mock 的 API 调用（防止 401 重定向），返回空数据
    // 注意：必须先注册 catch-all，后注册特定 mock（Playwright 后注册的路由优先级高）
    await page.route('**/api/v1/**', async (route) => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: '{"data":[]}' });
    });

    // 注册知识库特定 mock（优先级高于 catch-all）
    await registerMocks(page, [knowledgeBaseMocks]);

    kbPage = new KnowledgeBasePage(page);
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

    // 应出现校验错误（antd 动画可能导致 visibility:hidden，用 toContainText 替代 toBeVisible）
    const errorMsg = page.locator('.ant-form-item-explain-error');
    await expect(errorMsg.first()).toContainText('请输入名称', { timeout: 5_000 });
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
    await kbPage.expectDetailTab('文档');
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

  // ---- 文档管理 ----

  // 11. 文档列表显示
  test('文档列表显示 — 详情弹窗中可见文档表格', async ({ page }) => {
    await kbPage.goto();

    // 打开 graph 模式知识库详情（有预设文档）
    await kbPage.clickDetail('e2e-mock-kb');

    // 文档表格应可见
    await kbPage.expectDocumentTableVisible();

    // 预设文档应显示
    await kbPage.expectDocumentInTable('test-doc.txt');
  });

  // 12. 文档表格列
  test('文档表格列 — 显示文件名/类型/大小/状态/分块数', async ({ page }) => {
    await kbPage.goto();
    await kbPage.clickDetail('e2e-mock-kb');

    // 确认表头
    const modal = page.locator('.ant-modal-wrap:visible');
    const docTable = modal.locator('.ant-table').first();
    await expect(docTable.locator('th').getByText('文件名')).toBeVisible();
    await expect(docTable.locator('th').getByText('类型')).toBeVisible();
    await expect(docTable.locator('th').getByText('大小')).toBeVisible();
    await expect(docTable.locator('th').getByText('状态')).toBeVisible();
    await expect(docTable.locator('th').getByText('分块数')).toBeVisible();

    // 预设文档数据验证
    await expect(docTable.locator('tbody')).toContainText('test-doc.txt');
    await expect(docTable.locator('tbody')).toContainText('text/plain');
    await expect(docTable.locator('tbody')).toContainText('2 KB');
    await expect(docTable.locator('tbody')).toContainText('indexed');
    await expect(docTable.locator('tbody')).toContainText('5');
  });

  // 13. 文档状态 Tag 颜色
  test('文档状态 Tag 颜色 — indexed=green', async ({ page }) => {
    await kbPage.goto();
    await kbPage.clickDetail('e2e-mock-kb');

    // indexed 状态应为绿色 Tag
    const modal = page.locator('.ant-modal-wrap:visible');
    const indexedTag = modal.locator('.ant-tag-green').getByText('indexed').first();
    await expect(indexedTag).toBeVisible({ timeout: 5_000 });
  });

  // 14. 上传文档
  test('上传文档 — 上传后文档列表更新', async ({ page }) => {
    await kbPage.goto();
    await kbPage.clickDetail('e2e-mock-kb');

    // 上传文件
    await kbPage.uploadDocument({
      name: 'new-upload.txt',
      mimeType: 'text/plain',
      buffer: Buffer.from('测试上传内容'),
    });

    // 等待成功提示
    await kbPage.waitForSuccessMessage();

    // 上传的文档应出现在列表中
    await kbPage.expectDocumentInTable('uploaded-file.txt');
  });

  // 15. 空文档列表不崩溃
  test('空文档列表不崩溃 — 新建KB详情无文档', async ({ page }) => {
    await kbPage.goto();

    // 新建一个知识库
    const kbName = `e2e-empty-docs-${Date.now()}`;
    await kbPage.clickCreate();
    await kbPage.fillCreateForm({ name: kbName });
    await kbPage.confirmCreate();
    await kbPage.waitForSuccessMessage();

    // 打开详情
    await kbPage.clickDetail(kbName);

    // 文档表格应可见（空表格）
    await kbPage.expectDocumentTableVisible();

    // 不应崩溃
    await kbPage.expectDetailContains(kbName);
  });

  // ---- 向量搜索 ----

  // 16. 向量模式 KB 显示搜索 Tab
  test('向量模式 KB 显示搜索 Tab — 非 graph 标签', async ({ page }) => {
    await kbPage.goto();

    // 打开 vector 模式知识库详情
    await kbPage.clickDetail('e2e-vector-kb');

    // 应有"搜索"Tab
    await kbPage.expectDetailTab('搜索');

    // 不应有"图谱"Tab
    await kbPage.expectNoDetailTab('图谱');
    await kbPage.expectNoDetailTab('实体');
    await kbPage.expectNoDetailTab('社区');
    await kbPage.expectNoDetailTab('图谱搜索');
  });

  // 17. 执行向量搜索
  test('执行向量搜索 — 输入查询后显示结果', async ({ page }) => {
    await kbPage.goto();
    await kbPage.clickDetail('e2e-vector-kb');

    // 切换到搜索 Tab
    await kbPage.clickDetailTab('搜索');

    // 填写搜索查询
    await kbPage.fillSearchQuery('如何配置 Agent？');

    // 点击搜索
    await kbPage.clickSearchButton();

    // 应显示搜索结果
    await kbPage.expectSearchResult('Kasaya Agent');
  });

  // 18. 搜索结果展示分数和内容
  test('搜索结果展示分数和内容', async ({ page }) => {
    await kbPage.goto();
    await kbPage.clickDetail('e2e-vector-kb');
    await kbPage.clickDetailTab('搜索');
    await kbPage.fillSearchQuery('Runner');
    await kbPage.clickSearchButton();

    // 结果应包含分数
    await kbPage.expectSearchResult('score');
    // 结果应包含内容文本
    await kbPage.expectSearchResult('Runner');
  });

  // 19. 向量搜索验证 — 空查询
  test('向量搜索验证 — 空查询报错', async ({ page }) => {
    await kbPage.goto();
    await kbPage.clickDetail('e2e-vector-kb');
    await kbPage.clickDetailTab('搜索');

    // 不填写查询直接点搜索
    await kbPage.clickSearchButton();

    // 应出现校验错误
    const modal = page.locator('.ant-modal-wrap:visible');
    const errorMsg = modal.locator('.ant-form-item-explain-error');
    await expect(errorMsg.first()).toBeVisible({ timeout: 5_000 });
  });

  // 20. 空搜索结果提示（打开搜索 Tab 后未搜索时）
  test('空搜索结果提示 — 未搜索时显示暂无结果', async ({ page }) => {
    await kbPage.goto();
    await kbPage.clickDetail('e2e-vector-kb');
    await kbPage.clickDetailTab('搜索');

    // 未搜索时应有提示
    await kbPage.expectNoSearchResults();
  });
});
