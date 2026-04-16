import { expect, type Locator } from '@playwright/test';
import { BasePage } from './BasePage';

/**
 * SkillPage — 技能管理页（/skills）的 Page Object。
 *
 * 封装 CrudTable 组件的交互：新建/编辑 Modal、Dropdown 删除、搜索弹窗、预览弹窗。
 */
export class SkillPage extends BasePage {
  /* ---- 导航 ---- */

  /** 导航到技能管理页 */
  async goto() {
    await this.navigateTo('/skills');
  }

  /* ---- 新建技能 ---- */

  /** 点击 CrudTable 的"新建技能"按钮 */
  async clickCreate() {
    await this.page.locator('button').getByText('新建技能', { exact: true }).first().click();
    await this.waitForModalOpen();
  }

  /** 在新建/编辑 Modal 中填写表单 */
  async fillCreateForm(data: {
    name?: string;
    version?: string;
    description?: string;
    content: string;
    category?: string;
    tags?: string[];
  }) {
    if (data.name !== undefined) {
      await this.fillField('name', data.name);
    }
    if (data.version !== undefined) {
      await this.fillField('version', data.version);
    }
    if (data.description !== undefined) {
      await this.fillTextArea('description', data.description);
    }
    // content 使用 TextArea
    await this.fillTextArea('content', data.content);
    if (data.category !== undefined) {
      await this.selectOption('category', data.category);
    }
    if (data.tags && data.tags.length > 0) {
      await this.fillTags('tags', data.tags);
    }
  }

  /** 点击 Modal 确认按钮 */
  async confirmCreate() {
    await this.confirmModal();
  }

  /* ---- 编辑技能 ---- */

  /** 点击指定技能名称所在行的"编辑"按钮 */
  async clickEdit(name: string) {
    const row = this.findRowByName(name);
    await row.locator('button').getByText('编辑', { exact: true }).first().click();
    await this.waitForModalOpen();
  }

  /** 在编辑 Modal 中填写描述字段 */
  async fillEditForm(data: { description?: string; version?: string }) {
    if (data.description !== undefined) {
      await this.fillTextArea('description', data.description);
    }
    if (data.version !== undefined) {
      await this.fillField('version', data.version);
    }
  }

  /* ---- 删除技能 ---- */

  /** 点击指定技能的 Dropdown → 删除 → 确认 Modal.confirm */
  async clickDelete(name: string) {
    const row = this.findRowByName(name);
    const moreBtn = row.locator('button').filter({ has: this.page.locator('.anticon-more') }).first();
    if (await moreBtn.isVisible().catch(() => false)) {
      await moreBtn.click();
      const deleteMenu = this.page.locator('.ant-dropdown-menu-item').filter({ hasText: '删除' }).first();
      await deleteMenu.waitFor({ state: 'visible', timeout: 5_000 });
      await deleteMenu.click();
      const confirmBtn = this.page.getByRole('button', { name: '确认删除', exact: true }).first();
      await confirmBtn.waitFor({ state: 'visible', timeout: 5_000 });
      await confirmBtn.click();
      return;
    }
    const deleteBtn = row.locator('button').getByText('删除', { exact: true }).first();
    if (await deleteBtn.isVisible().catch(() => false)) {
      await deleteBtn.click();
      const confirmBtn = this.page.getByRole('button', { name: '确认删除', exact: true }).first();
      await confirmBtn.waitFor({ state: 'visible', timeout: 5_000 });
      await confirmBtn.click();
    }
  }

  /* ---- 查看预览 ---- */

  /** 点击指定技能的查看按钮（在 Dropdown 中） */
  async clickPreview(name: string) {
    const row = this.findRowByName(name);
    const moreBtn = row.locator('button').filter({ has: this.page.locator('.anticon-more') }).first();
    if (await moreBtn.isVisible().catch(() => false)) {
      await moreBtn.click();
      const viewMenu = this.page.locator('.ant-dropdown-menu-item').filter({ hasText: '查看' }).first();
      await viewMenu.waitFor({ state: 'visible', timeout: 5_000 });
      await viewMenu.click();
    }
  }

  /* ---- 搜索技能 ---- */

  /** 点击"搜索技能"按钮 */
  async clickSearch() {
    await this.page.locator('button').getByText('搜索技能', { exact: true }).first().click();
    await this.waitForModalOpen();
  }

  /** 在搜索弹窗中填写关键词和可选分类 */
  async fillSearchForm(query: string, category?: string) {
    // 搜索弹窗中的 query 输入框
    const searchModal = this.page.locator('.ant-modal-wrap:visible');
    const queryInput = searchModal.locator('input').first();
    await queryInput.fill(query);

    if (category) {
      // 搜索弹窗中有 category Select
      const categorySelect = searchModal.locator('.ant-select').nth(0);
      if (await categorySelect.isVisible().catch(() => false)) {
        await categorySelect.click();
        const option = this.page.locator('.ant-select-dropdown:not(.ant-select-dropdown-hidden) .ant-select-item-option')
          .getByText(category, { exact: true }).first();
        if (await option.isVisible().catch(() => false)) {
          await option.click();
        }
      }
    }
  }

  /** 点击搜索弹窗中的"搜索"按钮 */
  async confirmSearch() {
    const searchModal = this.page.locator('.ant-modal-wrap:visible');
    await searchModal.locator('button').getByText('搜索', { exact: true }).first().click();
  }

  /* ---- 断言 ---- */

  /** 断言表格中包含指定名称的技能 */
  async expectInTable(name: string) {
    await this.expectRowWithText(name);
  }

  /** 断言表格中不包含指定名称的技能 */
  async expectNotInTable(name: string) {
    const result = await this.expectNoRowWithText(name);
    expect(result, `表格中不应包含"${name}"`).toBeTruthy();
  }

  /** 断言预览 Modal 中包含指定文本 */
  async expectPreviewContent(text: string) {
    const previewModal = this.page.locator('.ant-modal-wrap:visible');
    await expect(previewModal).toContainText(text);
  }

  /** 断言搜索结果的数量 */
  async expectSearchResults(count: number) {
    const searchModal = this.page.locator('.ant-modal-wrap:visible');
    const rows = searchModal.locator('table tbody tr');
    await expect(rows).toHaveCount(count, { timeout: 5_000 });
  }

  /* ---- 辅助 ---- */

  /** 根据名称查找表格行 */
  private findRowByName(name: string): Locator {
    return this.page.getByRole('row', { name }).first();
  }

  /** 在 Tags Select 中输入标签（mode="tags" 需要逐个输入并回车） */
  private async fillTags(fieldId: string, tags: string[]) {
    const combobox = this.page.getByRole('combobox', { name: fieldId === 'tags' ? '标签' : fieldId });
    for (const tag of tags) {
      await combobox.click();
      await this.page.keyboard.type(tag);
      await this.page.keyboard.press('Enter');
      await this.page.waitForTimeout(200);
    }
    await this.page.keyboard.press('Escape');
  }
}
