import type { Page, Locator } from '@playwright/test';

/**
 * BasePage — 所有 Page Object 的基类。
 * 封装 Ant Design 通用交互：等待、表单填写、Select、Modal、Popconfirm、Tabs。
 */
export class BasePage {
  constructor(protected page: Page) {}

  /* ---- 导航 ---- */

  /** 导航到指定路径并等待页面就绪 */
  async navigateTo(path: string) {
    await this.page.goto(path);
    await this.waitForPageReady();
  }

  /* ---- 等待 ---- */

  /** 等待页面渲染完成：Spin 消失 + 主内容区域可见 */
  async waitForPageReady() {
    // 等待 ant-spin 不再存在（或超时不阻塞）
    await this.page.locator('.ant-spin').waitFor({ state: 'hidden', timeout: 15_000 }).catch(() => {});
  }

  /** 等待成功消息提示 */
  async waitForSuccessMessage(timeout = 5_000): Promise<Locator> {
    const msg = this.page.locator('.ant-message-success').first();
    await msg.waitFor({ state: 'visible', timeout });
    return msg;
  }

  /** 等待错误消息提示 */
  async waitForErrorMessage(timeout = 5_000): Promise<Locator> {
    const msg = this.page.locator('.ant-message-error').first();
    await msg.waitFor({ state: 'visible', timeout });
    return msg;
  }

  /* ---- 表单交互 ---- */

  /** 填写 Ant Design Form.Item（通过 CSS id 选择器） */
  async fillField(name: string, value: string) {
    const input = this.page.locator(`#${name}`);
    await input.click();
    await input.fill(value);
  }

  /** 填写 Input.Password（antd 的密码框） */
  async fillPassword(name: string, value: string) {
    const input = this.page.locator(`#${name} input`).first();
    if (await input.isVisible().catch(() => false)) {
      await input.click();
      await input.fill(value);
    } else {
      // fallback：直接填 #name
      await this.fillField(name, value);
    }
  }

  /** 填写 Input.TextArea */
  async fillTextArea(name: string, value: string) {
    const textarea = this.page.locator(`#${name} textarea`).first();
    if (await textarea.isVisible().catch(() => false)) {
      await textarea.click();
      await textarea.fill(value);
    } else {
      await this.fillField(name, value);
    }
  }

  /** 选择 Ant Design Select 下拉值 */
  async selectOption(name: string, value: string) {
    // 点击 Select 的 .ant-select-selector 触发器（避免被 selection-item 遮挡）
    const selector = this.page.locator(`#${name} + .ant-select-selector, #${name}`).first();
    // 使用 force: true 绕过遮挡元素
    await selector.click({ force: true });
    // 等待下拉出现并点击选项
    const option = this.page.locator(`.ant-select-dropdown:not(.ant-select-dropdown-hidden) .ant-select-item-option`).getByText(value, { exact: true }).first();
    await option.waitFor({ state: 'visible', timeout: 5_000 });
    await option.click();
  }

  /** 多选 Ant Design Select */
  async multiSelect(name: string, values: string[]) {
    const selector = this.page.locator(`#${name} + .ant-select-selector, #${name}`).first();
    for (const val of values) {
      await selector.click({ force: true });
      const option = this.page.locator(`.ant-select-dropdown:not(.ant-select-dropdown-hidden) .ant-select-item-option`).getByText(val, { exact: true }).first();
      await option.waitFor({ state: 'visible', timeout: 5_000 });
      await option.click();
    }
    // 按 Escape 关闭下拉
    await this.page.keyboard.press('Escape');
  }

  /* ---- Modal / Popconfirm ---- */

  /** 点击 Modal 的确认按钮 */
  async confirmModal() {
    await this.page.locator('.ant-modal-wrap:visible .ant-modal-footer .ant-btn-primary').click();
  }

  /** 点击 Popconfirm 的确认按钮 */
  async confirmPopconfirm() {
    await this.page.locator('.ant-popconfirm-buttons .ant-btn-primary').click();
  }

  /** 等待 Modal 打开 */
  async waitForModalOpen() {
    await this.page.locator('.ant-modal-wrap:visible').waitFor({ state: 'visible', timeout: 5_000 });
  }

  /** 等待 Modal 关闭 */
  async waitForModalClose() {
    await this.page.locator('.ant-modal-wrap:visible').waitFor({ state: 'hidden', timeout: 5_000 }).catch(() => {});
  }

  /* ---- Tabs ---- */

  /** 切换 Ant Design Tabs */
  async switchTab(tabText: string) {
    await this.page.locator(`.ant-tabs-tab`).getByText(tabText).click();
  }

  /* ---- Switch ---- */

  /** 切换 Switch */
  async toggleSwitch(checked: boolean) {
    const sw = this.page.locator('.ant-switch').first();
    const isChecked = await sw.getAttribute('aria-checked');
    if ((checked && isChecked !== 'true') || (!checked && isChecked === 'true')) {
      await sw.click();
    }
  }

  /* ---- 表格辅助 ---- */

  /** 断言表格中有指定文本的行 */
  async expectRowWithText(text: string) {
    await this.page.getByRole('row', { name: new RegExp(text) }).first().waitFor({ state: 'visible', timeout: 5_000 });
  }

  /** 断言表格中没有指定文本的行 */
  async expectNoRowWithText(text: string) {
    const count = await this.page.getByRole('row', { name: new RegExp(text) }).count();
    return count === 0;
  }

  /* ---- 按钮 ---- */

  /** 根据文本点击按钮 */
  async clickButton(text: string) {
    await this.page.locator('button').getByText(text, { exact: true }).first().click();
  }
}
