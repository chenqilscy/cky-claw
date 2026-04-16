import { expect, type Locator } from '@playwright/test';
import { BasePage } from './BasePage';

/**
 * AgentListPage — Agent 列表页 Page Object。
 * 路由: /agents
 *
 * 封装 ProTable 表格交互：搜索、创建、编辑、删除。
 */
export class AgentListPage extends BasePage {
  /* ---- 路由 ---- */

  /** 列表页路径 */
  static readonly PATH = '/agents';

  /* ---- 导航 ---- */

  /** 导航到 Agent 列表页并等待就绪 */
  async goto() {
    await this.navigateTo(AgentListPage.PATH);
  }

  /* ---- 页面元素定位 ---- */

  /** "创建 Agent" 按钮 */
  get createButton(): Locator {
    return this.page.locator('button').getByText('创建 Agent', { exact: true });
  }

  /** 搜索框 */
  get searchInput(): Locator {
    return this.page.locator('.ant-pro-table .ant-input-search input, input[placeholder*="搜索"]').first();
  }

  /** ProTable 表格 */
  get table(): Locator {
    return this.page.locator('.ant-table');
  }

  /** 所有表格行 */
  get tableRows(): Locator {
    return this.page.getByRole('row');
  }

  /* ---- 操作 ---- */

  /** 点击 "创建 Agent" 按钮 */
  async clickCreate() {
    await this.createButton.click();
    await this.page.waitForURL(/\/agents\/new/, { timeout: 5_000 });
  }

  /**
   * 点击指定 Agent 名称链接，进入编辑页。
   * @param name Agent 名称
   */
  async clickEdit(name: string) {
    const row = this.findRowByName(name);
    await row.locator('a').getByText(name, { exact: true }).click();
    await this.page.waitForURL(new RegExp(`/agents/${escapeRegex(name)}/edit`), { timeout: 5_000 });
  }

  /**
   * 点击指定 Agent 行的 Dropdown (MoreOutlined) → "删除" → 确认 Modal。
   * @param name Agent 名称
   */
  async clickDelete(name: string) {
    const row = this.findRowByName(name);

    // 点击 Dropdown 触发按钮（MoreOutlined 图标按钮）
    const moreBtn = row.locator('button .anticon-more, button').filter({ has: this.page.locator('.anticon-more') }).first();
    // 备选：通过 Dropdown 的触发按钮定位
    const dropdownTrigger = row.locator('.ant-dropdown-trigger, button[type="button"]').last();
    if (await moreBtn.isVisible().catch(() => false)) {
      await moreBtn.click();
    } else {
      await dropdownTrigger.click();
    }

    // 等待 Dropdown 菜单出现并点击 "删除"
    const deleteMenuItem = this.page.locator('.ant-dropdown-menu-item').getByText('删除', { exact: true }).first();
    await deleteMenuItem.waitFor({ state: 'visible', timeout: 5_000 });
    await deleteMenuItem.click();

    // 等待确认 Modal 出现并点击确认
    await this.waitForModalOpen();
    // Modal.confirm 的确认按钮
    const confirmBtn = this.page.locator('.ant-modal-wrap:visible .ant-btn-primary').getByText(/确认删除|确认/).first();
    if (await confirmBtn.isVisible().catch(() => false)) {
      await confirmBtn.click();
    } else {
      await this.confirmModal();
    }
  }

  /**
   * 在搜索框输入关键词并触发搜索。
   * @param keyword 搜索关键词
   */
  async searchAgent(keyword: string) {
    const input = this.searchInput;
    await input.click();
    await input.fill(keyword);
    // 按 Enter 触发搜索
    await this.page.keyboard.press('Enter');
    // 等待搜索请求完成
    await this.page.waitForTimeout(500);
  }

  /* ---- 断言 ---- */

  /**
   * 断言表格中存在指定名称的 Agent 行。
   * @param name Agent 名称
   */
  async expectAgentInTable(name: string) {
    const cell = this.page.locator('.ant-table-cell').getByText(name, { exact: true }).first();
    await expect(cell).toBeVisible({ timeout: 5_000 });
  }

  /**
   * 断言表格中不存在指定名称的 Agent 行。
   * @param name Agent 名称
   */
  async expectAgentNotInTable(name: string) {
    const cell = this.page.locator('.ant-table-cell').getByText(name, { exact: true });
    await expect(cell).toHaveCount(0, { timeout: 5_000 });
  }

  /**
   * 断言表格数据为空（显示空状态或无行）。
   */
  async expectEmptyTable() {
    const empty = this.page.locator('.ant-table-placeholder, .ant-empty');
    await expect(empty.first()).toBeVisible({ timeout: 5_000 });
  }

  /**
   * 断言分页控件的文本包含指定内容。
   * @param text 分页文本（如 "共 50 条"）
   */
  async expectPaginationText(text: string) {
    const paginationInfo = this.page.locator('.ant-pagination').getByText(text);
    await expect(paginationInfo).toBeVisible({ timeout: 5_000 });
  }

  /* ---- 辅助 ---- */

  /** 按名称查找表格行 */
  private findRowByName(name: string): Locator {
    return this.page.getByRole('row', { name }).first();
  }
}

/** 转义正则特殊字符 */
function escapeRegex(str: string): string {
  return str.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}
