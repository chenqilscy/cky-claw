import { test, expect } from '@playwright/test';
import { KnowledgeBasePage } from './pom/KnowledgeBasePage';
import { registerMocks } from './mocks/index';
import { knowledgeBaseMocks } from './mocks/knowledgeBaseMocks';

/**
 * Kasaya 知识库 — 图谱功能 E2E 测试。
 *
 * 覆盖：图谱构建、实体管理、社区管理、图谱搜索、图谱删除、模式差异。
 * 使用 API Mock，不依赖真实后端。
 */
test.describe('知识库图谱功能', () => {
  let kbPage: KnowledgeBasePage;

  test.beforeEach(async ({ page }) => {
    // Catch-all：拦截未 mock 的 API 调用（防止 401 重定向）
    await page.route('**/api/v1/**', async (route) => {
      await route.fulfill({ status: 200, contentType: 'application/json', body: '{"data":[]}' });
    });

    // 注册知识库特定 mock（优先级高于 catch-all）
    await registerMocks(page, [knowledgeBaseMocks]);

    kbPage = new KnowledgeBasePage(page);
  });

  // ---- 图谱 Tab 可见性 ----

  // 1. graph 模式 KB 显示图谱相关 Tab
  test('graph 模式 KB 显示图谱相关 Tab', async ({ page }) => {
    await kbPage.goto();
    await kbPage.clickDetail('e2e-mock-kb');

    await kbPage.expectDetailTab('文档');
    await kbPage.expectDetailTab('图谱');
    await kbPage.expectDetailTab('实体');
    await kbPage.expectDetailTab('社区');
    await kbPage.expectDetailTab('图谱搜索');

    // 不应有向量"搜索"Tab
    await kbPage.expectNoDetailTab('搜索');
  });

  // 2. vector 模式 KB 不显示图谱 Tab
  test('vector 模式 KB 不显示图谱 Tab', async ({ page }) => {
    await kbPage.goto();
    await kbPage.clickDetail('e2e-vector-kb');

    await kbPage.expectDetailTab('文档');
    await kbPage.expectDetailTab('搜索');

    await kbPage.expectNoDetailTab('图谱');
    await kbPage.expectNoDetailTab('实体');
    await kbPage.expectNoDetailTab('社区');
    await kbPage.expectNoDetailTab('图谱搜索');
  });

  // 3. hybrid 模式 KB 显示图谱 Tab
  test('hybrid 模式 KB 显示图谱 Tab', async ({ page }) => {
    await kbPage.goto();

    // 创建 hybrid 模式知识库
    const kbName = `e2e-hybrid-kb-${Date.now()}`;
    await kbPage.clickCreate();
    await kbPage.fillCreateForm({
      name: kbName,
      mode: '混合模式 (hybrid)',
    });
    await kbPage.confirmCreate();
    await kbPage.waitForSuccessMessage();

    // 打开详情
    await kbPage.clickDetail(kbName);

    // hybrid 模式应显示图谱 Tab（与 graph 相同）
    await kbPage.expectDetailTab('图谱');
    await kbPage.expectDetailTab('实体');
    await kbPage.expectDetailTab('社区');
    await kbPage.expectDetailTab('图谱搜索');
  });

  // ---- 图谱构建 ----

  // 4. 构建图谱按钮触发构建
  test('构建图谱按钮 — 触发构建并显示进度', async ({ page }) => {
    await kbPage.goto();
    await kbPage.clickDetail('e2e-mock-kb');

    // 切换到图谱 Tab
    await kbPage.clickDetailTab('图谱');

    // 点击构建按钮
    await kbPage.clickBuildGraph();

    // 应出现信息提示（task_id）
    const infoMsg = page.locator('.ant-message-info').first();
    await expect(infoMsg).toBeVisible({ timeout: 5_000 });

    // 进度条应出现
    await kbPage.expectBuildProgress();
  });

  // 5. 构建完成提示实体/关系数
  test('构建完成 — 提示实体和关系数', async ({ page }) => {
    await kbPage.goto();
    await kbPage.clickDetail('e2e-mock-kb');
    await kbPage.clickDetailTab('图谱');

    await kbPage.clickBuildGraph();

    // Mock 在第3次轮询后返回 completed
    // 等待成功提示
    const successMsg = page.locator('.ant-message-success').first();
    await expect(successMsg).toBeVisible({ timeout: 15_000 });
    await expect(successMsg).toContainText('图谱构建完成');
  });

  // ---- 实体管理 ----

  // 6. 实体 Tab 显示实体表格
  test('实体 Tab — 显示预设实体', async ({ page }) => {
    await kbPage.goto();
    await kbPage.clickDetail('e2e-mock-kb');

    // 切换到实体 Tab
    await kbPage.clickDetailTab('实体');

    // 预设实体应显示
    await kbPage.expectEntityInTable('Kasaya Agent');
    await kbPage.expectEntityInTable('Runner');
  });

  // 7. 实体表格列
  test('实体表格列 — 名称/类型/描述/置信度/标签', async ({ page }) => {
    await kbPage.goto();
    await kbPage.clickDetail('e2e-mock-kb');
    await kbPage.clickDetailTab('实体');

    const modal = page.locator('.ant-modal-wrap:visible');
    const entityTabPane = modal.locator('.ant-tabs-tabpane-active');

    // 验证表头
    await expect(entityTabPane.locator('th').getByText('名称')).toBeVisible();
    await expect(entityTabPane.locator('th').getByText('类型')).toBeVisible();
    await expect(entityTabPane.locator('th').getByText('描述')).toBeVisible();
    await expect(entityTabPane.locator('th').getByText('置信度')).toBeVisible();
    await expect(entityTabPane.locator('th').getByText('标签')).toBeVisible();

    // 验证实体数据
    await expect(entityTabPane.locator('.ant-table-tbody')).toContainText('Concept');
    await expect(entityTabPane.locator('.ant-table-tbody')).toContainText('Tool');
    await expect(entityTabPane.locator('.ant-table-tbody')).toContainText('95%');
    await expect(entityTabPane.locator('.ant-table-tbody')).toContainText('extracted');
  });

  // 8. 实体总数显示
  test('实体总数显示', async ({ page }) => {
    await kbPage.goto();
    await kbPage.clickDetail('e2e-mock-kb');
    await kbPage.clickDetailTab('实体');

    // 应显示实体总数
    const modal = page.locator('.ant-modal-wrap:visible');
    await expect(modal.locator('.ant-typography').getByText(/共 \d+ 个实体/)).toBeVisible({ timeout: 5_000 });
  });

  // ---- 社区管理 ----

  // 9. 社区 Tab 显示社区卡片
  test('社区 Tab — 显示预设社区卡片', async ({ page }) => {
    await kbPage.goto();
    await kbPage.clickDetail('e2e-mock-kb');

    // 切换到社区 Tab
    await kbPage.clickDetailTab('社区');

    // 预设社区应显示
    await kbPage.expectCommunityCard('Agent 执行流程');
  });

  // 10. 社区卡片内容
  test('社区卡片内容 — 名称/摘要/实体数/层级', async ({ page }) => {
    await kbPage.goto();
    await kbPage.clickDetail('e2e-mock-kb');
    await kbPage.clickDetailTab('社区');

    const modal = page.locator('.ant-modal-wrap:visible');
    const card = modal.locator('.ant-card').filter({ hasText: 'Agent 执行流程' }).first();

    // 卡片应包含摘要
    await expect(card).toContainText('Agent 生命周期管理和执行引擎相关实体');

    // 应显示实体数
    await expect(card).toContainText('包含 3 个实体');

    // 应显示层级 Tag
    await expect(card.locator('.ant-tag').getByText('Level 0')).toBeVisible();
  });

  // 11. 空社区列表提示
  test('空社区列表提示 — vector 模式 KB', async ({ page }) => {
    await kbPage.goto();

    // 创建 graph 模式知识库（无预设社区）
    const kbName = `e2e-no-community-${Date.now()}`;
    await kbPage.clickCreate();
    await kbPage.fillCreateForm({ name: kbName, mode: '图谱检索 (graph)' });
    await kbPage.confirmCreate();
    await kbPage.waitForSuccessMessage();

    await kbPage.clickDetail(kbName);
    await kbPage.clickDetailTab('社区');

    // 无社区数据时应有提示
    await kbPage.expectNoCommunities();
  });

  // ---- 图谱搜索 ----

  // 12. 图谱搜索 Tab 显示搜索表单
  test('图谱搜索 Tab — 显示查询输入和模式选择', async ({ page }) => {
    await kbPage.goto();
    await kbPage.clickDetail('e2e-mock-kb');
    await kbPage.clickDetailTab('图谱搜索');

    const modal = page.locator('.ant-modal-wrap:visible');

    // 应有查询输入框
    const searchInput = modal.locator('input[placeholder*="输入查询"]').first();
    await expect(searchInput).toBeVisible({ timeout: 5_000 });

    // 应有搜索按钮
    await expect(modal.locator('button').getByText('搜索').first()).toBeVisible();
  });

  // 13. 执行图谱搜索
  test('执行图谱搜索 — 显示搜索结果', async ({ page }) => {
    await kbPage.goto();
    await kbPage.clickDetail('e2e-mock-kb');
    await kbPage.clickDetailTab('图谱搜索');

    // 填写搜索查询
    await kbPage.fillGraphSearchQuery('Agent 如何调用工具？');

    // 点击搜索
    await kbPage.clickGraphSearchButton();

    // 应显示搜索结果
    await kbPage.expectGraphSearchResult('Kasaya Agent');
  });

  // 14. 图谱搜索结果展示来源标签
  test('图谱搜索结果展示来源标签 — entity_match/relation_traverse/community_match', async ({ page }) => {
    await kbPage.goto();
    await kbPage.clickDetail('e2e-mock-kb');
    await kbPage.clickDetailTab('图谱搜索');

    await kbPage.fillGraphSearchQuery('Agent');
    await kbPage.clickGraphSearchButton();

    // 应显示不同来源标签
    await kbPage.expectGraphSearchResult('entity_match');
    await kbPage.expectGraphSearchResult('relation_traverse');
    await kbPage.expectGraphSearchResult('community_match');
  });

  // 15. 图谱搜索验证 — 空查询
  test('图谱搜索验证 — 空查询报错', async ({ page }) => {
    await kbPage.goto();
    await kbPage.clickDetail('e2e-mock-kb');
    await kbPage.clickDetailTab('图谱搜索');

    // 不填写查询直接搜索
    await kbPage.clickGraphSearchButton();

    const modal = page.locator('.ant-modal-wrap:visible');
    const errorMsg = modal.locator('.ant-form-item-explain-error');
    await expect(errorMsg.first()).toBeVisible({ timeout: 5_000 });
  });

  // 16. 图谱搜索未搜索时无结果提示
  test('图谱搜索未搜索时 — 显示暂无搜索结果', async ({ page }) => {
    await kbPage.goto();
    await kbPage.clickDetail('e2e-mock-kb');
    await kbPage.clickDetailTab('图谱搜索');

    await kbPage.expectNoGraphSearchResults();
  });

  // ---- 图谱删除 ----

  // 17. 清空图谱成功
  test('清空图谱 — 成功提示', async ({ page }) => {
    await kbPage.goto();
    await kbPage.clickDetail('e2e-mock-kb');
    await kbPage.clickDetailTab('图谱');

    // 点击清空图谱按钮
    await kbPage.clickDeleteGraph();

    // 等待成功提示
    await kbPage.waitForSuccessMessage();
  });

  // 18. 清空图谱后实体数据重置
  test('清空图谱后 — 实体和社区数据重置', async ({ page }) => {
    await kbPage.goto();
    await kbPage.clickDetail('e2e-mock-kb');
    await kbPage.clickDetailTab('图谱');

    // 先确认实体存在
    await kbPage.clickDetailTab('实体');
    await kbPage.expectEntityInTable('Kasaya Agent');

    // 回到图谱 Tab 清空
    await kbPage.clickDetailTab('图谱');
    await kbPage.clickDeleteGraph();
    await kbPage.waitForSuccessMessage();

    // 再看实体，应为空
    await kbPage.clickDetailTab('实体');
    await kbPage.expectEntityTableEmpty();
  });
});
