import { expect, type Locator } from '@playwright/test';
import { BasePage } from './BasePage';

/**
 * ProviderEditPage — 模型厂商编辑/注册页的 Page Object。
 * 支持注册（/providers/new）和编辑（/providers/:id/edit）两种模式。
 */
export class ProviderEditPage extends BasePage {
  /* ---- 导航 ---- */

  /** 导航到注册新厂商页 */
  async gotoCreate() {
    await this.navigateTo('/providers/new');
  }

  /** 导航到编辑厂商页 */
  async gotoEdit(id: string) {
    await this.navigateTo(`/providers/${id}/edit`);
  }

  /* ---- 表单填写 ---- */

  /** 填写厂商名称 */
  async fillName(value: string) {
    await this.fillField('name', value);
  }

  /** 选择厂商类型 */
  async selectProviderType(type: string) {
    await this.selectOption('provider_type', type);
  }

  /** 填写 Base URL */
  async fillBaseUrl(value: string) {
    await this.fillField('base_url', value);
  }

  /** 填写 API Key */
  async fillApiKey(value: string) {
    await this.fillPassword('api_key', value);
  }

  /** 选择认证方式 */
  async selectAuthType(type: string) {
    await this.selectOption('auth_type', type);
  }

  /** 选择模型层级 */
  async selectModelTier(tier: string) {
    await this.selectOption('model_tier', tier);
  }

  /** 选择模型能力（多选） */
  async selectCapabilities(capabilities: string[]) {
    await this.multiSelect('capabilities', capabilities);
  }

  /* ---- 操作按钮 ---- */

  /** 点击 "注册" 或 "保存" 按钮 */
  async clickSave() {
    // 注册模式显示 "注册"，编辑模式显示 "保存"
    const registerBtn = this.page.locator('button[type="submit"]').first();
    await registerBtn.click();
  }

  /** 点击 "测试连接" 按钮（仅编辑模式） */
  async clickTestConnection() {
    await this.page.locator('button').filter({ hasText: '测试连接' }).first().click();
  }

  /** 点击 "返回列表" 按钮 */
  async clickBackToList() {
    await this.page.locator('button').filter({ hasText: '返回列表' }).first().click();
  }

  /** 点击 "取消" 按钮 */
  async clickCancel() {
    await this.page.locator('button').getByText('取消').first().click();
  }

  /* ---- Tabs ---- */

  /** 切换到 "关联模型" Tab */
  async switchToModelsTab() {
    await this.switchTab('关联模型');
  }

  /** 切换到 "基本配置" Tab */
  async switchToBasicTab() {
    await this.switchTab('基本配置');
  }

  /* ---- 模型操作 ---- */

  /** 点击 "添加模型" 按钮 */
  async clickAddModel() {
    await this.page.locator('button').getByText('添加模型').first().click();
  }

  /** 点击 "从厂商同步" 按钮 */
  async clickSyncModels() {
    await this.page.locator('button').filter({ hasText: '从厂商同步' }).first().click();
  }

  /** 在模型弹窗中填写模型名称 */
  async fillModelName(value: string) {
    await this.page.locator('.ant-modal-wrap:visible #model_name').fill(value);
  }

  /** 在模型弹窗中填写显示名称 */
  async fillModelDisplayName(value: string) {
    await this.page.locator('.ant-modal-wrap:visible #display_name').fill(value);
  }

  /** 点击模型弹窗的确认按钮 */
  async confirmModelModal() {
    await this.page.locator('.ant-modal-wrap:visible .ant-modal-footer .ant-btn-primary').click();
  }

  /* ---- 断言 ---- */

  /** 断言 Base URL 输入框的值 */
  async expectBaseUrlValue(expected: string) {
    const input = this.page.locator('#base_url');
    await expect(input).toHaveValue(expected);
  }

  /** 断言表单验证错误出现 */
  async expectValidationError() {
    const error = this.page.locator('.ant-form-item-explain-error').first();
    await expect(error).toBeVisible({ timeout: 5_000 });
  }

  /** 断言模型表格中有指定模型名称 */
  async expectModelInTable(modelName: string) {
    const row = this.page.getByRole('row', { name: modelName }).first();
    await expect(row).toBeVisible({ timeout: 5_000 });
  }

  /** 获取 Base URL 输入框的值 */
  async getBaseUrlValue(): Promise<string> {
    return this.page.locator('#base_url').inputValue();
  }
}
