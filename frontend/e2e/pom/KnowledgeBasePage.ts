import { expect } from '@playwright/test';
import { BasePage } from './BasePage';

/**
 * KnowledgeBasePage — 知识库管理页（/knowledge-bases）的 Page Object。
 *
 * 封装知识库页面的交互：新建/编辑 Modal、删除确认、详情弹窗、文档上传、搜索、图谱操作。
 */
export class KnowledgeBasePage extends BasePage {
  /* ---- 导航 ---- */

  /** 导航到知识库管理页 */
  async goto() {
    await this.navigateTo('/knowledge-bases');
  }

  /* ---- 新建知识库 ---- */

  /** 点击"新建知识库"按钮 */
  async clickCreate() {
    await this.page.locator('button').getByText('新建知识库', { exact: true }).first().click();
    await this.waitForModalOpen();
    // 等待表单字段渲染（destroyOnHidden + initialValues 确保立即可用）
    await this.page.locator('#name').waitFor({ state: 'visible', timeout: 5_000 });
  }

  /** 在新建/编辑 Modal 中填写表单 */
  async fillCreateForm(data: {
    name: string;
    description?: string;
    mode?: string;
    embedding_model?: string;
    chunk_size?: number;
    overlap?: number;
  }) {
    await this.fillField('name', data.name);

    if (data.description !== undefined) {
      await this.fillTextArea('description', data.description);
    }

    if (data.mode !== undefined) {
      await this.selectOption('mode', data.mode);
    }

    if (data.embedding_model !== undefined) {
      await this.fillField('embedding_model', data.embedding_model);
    }

    if (data.chunk_size !== undefined) {
      const chunkSizeInput = this.page.locator('#chunk_size input').first();
      if (await chunkSizeInput.isVisible().catch(() => false)) {
        await chunkSizeInput.clear();
        await chunkSizeInput.fill(String(data.chunk_size));
      }
    }

    if (data.overlap !== undefined) {
      const overlapInput = this.page.locator('#overlap input').first();
      if (await overlapInput.isVisible().catch(() => false)) {
        await overlapInput.clear();
        await overlapInput.fill(String(data.overlap));
      }
    }
  }

  /** 点击 Modal 确认按钮 */
  async confirmCreate() {
    await this.confirmModal();
  }

  /* ---- 编辑知识库 ---- */

  /** 点击指定知识库名称所在行的"编辑"按钮 */
  async clickEdit(name: string) {
    const row = this.findRowByName(name);
    await row.getByRole('button', { name: /编\s*辑/ }).first().click();
    await this.waitForModalOpen();
    // 等待 afterOpenChange 填充编辑值
    await this.page.locator('#name').waitFor({ state: 'visible', timeout: 5_000 });
    await this.page.waitForTimeout(300);
  }

  /** 在编辑 Modal 中修改字段 */
  async fillEditForm(data: { name?: string; description?: string }) {
    if (data.name !== undefined) {
      const nameInput = this.page.locator('#name');
      await nameInput.clear();
      await nameInput.fill(data.name);
    }
    if (data.description !== undefined) {
      await this.fillTextArea('description', data.description);
    }
  }

  /* ---- 删除知识库 ---- */

  /** 点击指定知识库的"删除"按钮（直接删除，无确认弹窗） */
  async clickDelete(name: string) {
    const row = this.findRowByName(name);
    await row.getByRole('button', { name: /删\s*除/ }).first().click();
  }

  /* ---- 查看详情 ---- */

  /** 点击指定知识库的"详情"按钮 */
  async clickDetail(name: string) {
    const row = this.findRowByName(name);
    await row.getByRole('button', { name: /详\s*情/ }).first().click();
    await this.waitForModalOpen();
  }

  /** 在详情弹窗中切换 Tab */
  async clickDetailTab(tabText: string) {
    const modal = this.page.locator('.ant-modal-wrap:visible');
    await modal.locator('.ant-tabs-tab').getByText(tabText, { exact: true }).click();
  }

  /* ---- 文档管理 ---- */

  /** 点击"上传文档并索引"按钮 */
  async clickUploadButton() {
    const modal = this.page.locator('.ant-modal-wrap:visible');
    await modal.locator('button').getByText('上传文档并索引').first().click();
  }

  /** 上传文档（通过 file input chooser） */
  async uploadDocument(filePath: string) {
    const modal = this.page.locator('.ant-modal-wrap:visible');
    // Ant Design Upload 组件内部有隐藏的 file input
    const fileInput = modal.locator('input[type="file"]').first();
    await fileInput.setInputFiles(filePath);
  }

  /** 断言文档表格中包含指定文件名 */
  async expectDocumentInTable(filename: string) {
    const modal = this.page.locator('.ant-modal-wrap:visible');
    const docTable = modal.locator('.ant-table').first();
    await expect(docTable.locator('tbody')).toContainText(filename, { timeout: 5_000 });
  }

  /** 断言文档表格中不包含指定文件名 */
  async expectDocumentNotInTable(filename: string) {
    const modal = this.page.locator('.ant-modal-wrap:visible');
    const docTable = modal.locator('.ant-table').first();
    await expect(docTable.locator('tbody')).not.toContainText(filename);
  }

  /** 断言文档表格可见 */
  async expectDocumentTableVisible() {
    const modal = this.page.locator('.ant-modal-wrap:visible');
    const docTable = modal.locator('.ant-table').first();
    await expect(docTable).toBeVisible({ timeout: 5_000 });
  }

  /* ---- 向量搜索 ---- */

  /** 填写搜索查询 */
  async fillSearchQuery(query: string) {
    const modal = this.page.locator('.ant-modal-wrap:visible');
    // 搜索 Tab 中的 query input
    const searchInput = modal.locator('input[placeholder*="输入问题"]').first();
    await searchInput.click();
    await searchInput.fill(query);
  }

  /** 点击搜索按钮 */
  async clickSearchButton() {
    const modal = this.page.locator('.ant-modal-wrap:visible');
    await modal.locator('button').getByText('搜索').first().click();
  }

  /** 断言搜索结果包含指定文本 */
  async expectSearchResult(text: string) {
    const modal = this.page.locator('.ant-modal-wrap:visible');
    await expect(modal.locator('.ant-card').first()).toContainText(text, { timeout: 5_000 });
  }

  /** 断言无搜索结果提示 */
  async expectNoSearchResults() {
    const modal = this.page.locator('.ant-modal-wrap:visible');
    await expect(modal.locator('.ant-typography').getByText('暂无搜索结果')).toBeVisible({ timeout: 5_000 });
  }

  /* ---- 图谱操作 ---- */

  /** 点击"构建图谱"按钮 */
  async clickBuildGraph() {
    const modal = this.page.locator('.ant-modal-wrap:visible');
    await modal.locator('button').getByText('构建图谱').first().click();
  }

  /** 点击"清空图谱"按钮 */
  async clickDeleteGraph() {
    const modal = this.page.locator('.ant-modal-wrap:visible');
    await modal.locator('button').getByText('清空图谱').first().click();
  }

  /** 断言构建进度条可见 */
  async expectBuildProgress() {
    const modal = this.page.locator('.ant-modal-wrap:visible');
    await expect(modal.locator('.ant-progress')).toBeVisible({ timeout: 5_000 });
  }

  /** 断言实体表格中包含指定名称 */
  async expectEntityInTable(name: string) {
    const modal = this.page.locator('.ant-modal-wrap:visible');
    // 实体 Tab 的活跃面板中的表格
    const entityTabPane = modal.locator('.ant-tabs-tabpane-active');
    await expect(entityTabPane.locator('.ant-table-tbody')).toContainText(name, { timeout: 5_000 });
  }

  /** 断言实体表格为空 */
  async expectEntityTableEmpty() {
    const modal = this.page.locator('.ant-modal-wrap:visible');
    const entityTabPane = modal.locator('.ant-tabs-tabpane-active');
    // Ant Design 空表格有一行 "暂无数据" 的 placeholder 行
    const placeholder = entityTabPane.locator('.ant-table-placeholder');
    await expect(placeholder).toBeVisible({ timeout: 5_000 });
  }

  /** 断言社区卡片中包含指定名称 */
  async expectCommunityCard(name: string) {
    const modal = this.page.locator('.ant-modal-wrap:visible');
    await expect(modal.locator('.ant-card').filter({ hasText: name }).first()).toBeVisible({ timeout: 5_000 });
  }

  /** 断言无社区数据提示 */
  async expectNoCommunities() {
    const modal = this.page.locator('.ant-modal-wrap:visible');
    await expect(modal.locator('.ant-typography').getByText('暂无社区数据')).toBeVisible({ timeout: 5_000 });
  }

  /** 填写图谱搜索查询 */
  async fillGraphSearchQuery(query: string) {
    const modal = this.page.locator('.ant-modal-wrap:visible');
    const searchInput = modal.locator('input[placeholder*="输入查询"]').first();
    await searchInput.click();
    await searchInput.fill(query);
  }

  /** 选择图谱搜索模式 */
  async selectGraphSearchMode(mode: string) {
    const modal = this.page.locator('.ant-modal-wrap:visible');
    // 找到 search_mode 的 Select
    const select = modal.locator('.ant-select').filter({ hasText: '混合' }).first();
    if (await select.isVisible().catch(() => false)) {
      await select.click({ force: true });
      const option = this.page.locator('.ant-select-dropdown:not(.ant-select-dropdown-hidden) .ant-select-item-option').getByText(mode, { exact: true }).first();
      await option.waitFor({ state: 'visible', timeout: 5_000 });
      await option.click();
    }
  }

  /** 点击图谱搜索按钮 */
  async clickGraphSearchButton() {
    const modal = this.page.locator('.ant-modal-wrap:visible');
    await modal.locator('button').getByText('搜索').first().click();
  }

  /** 断言图谱搜索结果包含指定文本 */
  async expectGraphSearchResult(text: string) {
    const modal = this.page.locator('.ant-modal-wrap:visible');
    // 图谱搜索结果可能有多个 Card，检查整体区域包含文本
    const searchTab = modal.locator('.ant-tabs-tabpane-active').last();
    await expect(searchTab).toContainText(text, { timeout: 5_000 });
  }

  /** 断言图谱搜索无结果 */
  async expectNoGraphSearchResults() {
    const modal = this.page.locator('.ant-modal-wrap:visible');
    await expect(modal.locator('.ant-typography').getByText('暂无搜索结果')).toBeVisible({ timeout: 5_000 });
  }

  /* ---- 断言 ---- */

  /** 断言表格中包含指定名称的知识库 */
  async expectInTable(name: string) {
    await this.expectRowWithText(name);
  }

  /** 断言表格中不包含指定名称的知识库 */
  async expectNotInTable(name: string) {
    const result = await this.expectNoRowWithText(name);
    expect(result, `表格中不应包含"${name}"`).toBeTruthy();
  }

  /** 断言详情 Modal 已打开且包含指定文本 */
  async expectDetailContains(text: string) {
    const detailModal = this.page.locator('.ant-modal-wrap:visible');
    await expect(detailModal).toContainText(text);
  }

  /** 断言详情 Modal 已关闭 */
  async expectDetailClosed() {
    await expect(this.page.locator('.ant-modal-wrap:visible')).toHaveCount(0, { timeout: 5_000 });
  }

  /** 断言表格中显示指定模式的 Tag */
  async expectModeTag(mode: string) {
    const table = this.page.locator('.ant-table');
    await expect(table.locator('.ant-tag').getByText(mode, { exact: true }).first()).toBeVisible({ timeout: 5_000 });
  }

  /** 断言详情弹窗中包含指定 Tab */
  async expectDetailTab(tabText: string) {
    const modal = this.page.locator('.ant-modal-wrap:visible');
    await expect(modal.locator('.ant-tabs-tab').getByText(tabText, { exact: true })).toBeVisible({ timeout: 5_000 });
  }

  /** 断言详情弹窗中不包含指定 Tab */
  async expectNoDetailTab(tabText: string) {
    const modal = this.page.locator('.ant-modal-wrap:visible');
    await expect(modal.locator('.ant-tabs-tab').getByText(tabText, { exact: true })).toHaveCount(0);
  }

  /* ---- 辅助 ---- */

  /** 根据名称查找表格行（仅匹配 tbody 中的行） */
  private findRowByName(name: string) {
    return this.page.locator('.ant-table-tbody tr').filter({ hasText: name }).first();
  }
}
