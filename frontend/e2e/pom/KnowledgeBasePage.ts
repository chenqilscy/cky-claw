import { expect } from '@playwright/test';
import { BasePage } from './BasePage';

/**
 * KnowledgeBasePage — 知识库管理页（/knowledge-bases）的 Page Object。
 *
 * 封装知识库页面的交互：新建/编辑 Modal、删除确认、详情弹窗。
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
  }

  /** 在编辑 Modal 中修改字段 */
  async fillEditForm(data: { name?: string; description?: string }) {
    if (data.name !== undefined) {
      // 编辑模式时清空再填入
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

  /* ---- 辅助 ---- */

  /** 根据名称查找表格行（仅匹配 tbody 中的行） */
  private findRowByName(name: string) {
    return this.page.locator('.ant-table-tbody tr').filter({ hasText: name }).first();
  }
}
