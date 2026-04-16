import { expect, type Locator } from '@playwright/test';
import { BasePage } from './BasePage';

/**
 * AgentEditPage — Agent 创建/编辑页 Page Object。
 * 路由: /agents/new 和 /agents/:name/edit
 *
 * 五步向导结构：
 *   0: 基本信息
 *   1: 模型配置
 *   2: 工具配置
 *   3: 编排配置
 *   4: 安全与高级
 */
export class AgentEditPage extends BasePage {
  /* ---- 路由 ---- */

  static readonly CREATE_PATH = '/agents/new';

  /* ---- Steps 步骤条 ---- */

  /** 步骤条容器 */
  get steps(): Locator {
    return this.page.locator('.ant-steps');
  }

  /** 当前激活步骤的标题 */
  get activeStepTitle(): Locator {
    return this.page.locator('.ant-steps-item-active .ant-steps-item-title');
  }

  /* ---- 导航 ---- */

  /** 导航到 Agent 创建页并等待就绪 */
  async gotoCreate() {
    await this.navigateTo(AgentEditPage.CREATE_PATH);
    // 等待表单渲染完成
    await this.page.locator('#name').waitFor({ state: 'visible', timeout: 10_000 }).catch(() => {});
  }

  /**
   * 导航到指定 Agent 的编辑页。
   * @param name Agent 名称
   */
  async gotoEdit(name: string) {
    await this.navigateTo(`/agents/${encodeURIComponent(name)}/edit`);
  }

  /* ---- 步骤断言 ---- */

  /**
   * 断言当前激活步骤的标题匹配。
   * @param title 步骤标题（如 "基本信息"）
   */
  async expectStepActive(title: string) {
    await expect(this.activeStepTitle).toHaveText(title, { timeout: 5_000 });
  }

  /* ---- 步骤 1：基本信息 ---- */

  /**
   * 填写基本信息步骤。
   * @param data 基本信息数据
   */
  async fillStep1(data: { name: string; description?: string; instructions?: string }) {
    // 名称（Input）
    await this.fillField('name', data.name);

    // 描述（TextArea）
    if (data.description) {
      await this.fillTextArea('description', data.description);
    }

    // 系统指令（TextArea）
    if (data.instructions) {
      await this.fillTextArea('instructions', data.instructions);
    }
  }

  /* ---- 步骤导航按钮 ---- */

  /** 点击 "下一步" 按钮 */
  async clickNext() {
    const btn = this.page.locator('button').filter({ hasText: /^下一步$/ });
    await btn.first().click();
    // 等待步骤切换动画
    await this.page.waitForTimeout(300);
  }

  /** 点击 "上一步" 按钮 */
  async clickPrev() {
    const btn = this.page.locator('button').filter({ hasText: /^上一步$/ });
    await btn.first().click();
    await this.page.waitForTimeout(300);
  }

  /* ---- 步骤 2：模型配置 ---- */

  /**
   * 选择模型厂商（Provider）— 级联第一级。
   * @param name Provider 名称（label 中包含的文本）
   */
  async selectProvider(name: string) {
    const select = this.page.locator('#provider_name');
    await select.click();
    // 等待下拉选项出现
    const option = this.page
      .locator('.ant-select-dropdown:not(.ant-select-dropdown-hidden) .ant-select-item-option')
      .getByText(name, { exact: false })
      .first();
    await option.waitFor({ state: 'visible', timeout: 5_000 });
    await option.click();
    // 等待模型列表加载
    await this.page.waitForTimeout(300);
  }

  /**
   * 选择模型 — 级联第二级。
   * @param name 模型名称（display_name 或 model_name）
   */
  async selectModel(name: string) {
    const modelSelect = this.page.locator('#model');
    await modelSelect.click();
    // 等待下拉选项出现
    const option = this.page
      .locator('.ant-select-dropdown:not(.ant-select-dropdown-hidden) .ant-select-item-option')
      .getByText(name, { exact: false })
      .first();
    await option.waitFor({ state: 'visible', timeout: 5_000 });
    await option.click();
    await this.page.waitForTimeout(200);
  }

  /**
   * 选择审批模式。
   * @param mode 审批模式显示标签（Suggest / Auto Edit / Full Auto）
   */
  async selectApprovalMode(mode: string) {
    await this.selectOption('approval_mode', mode);
  }

  /**
   * 填写模型配置步骤的全部字段。
   * @param data 模型配置数据
   */
  async fillStep2(data: {
    providerName?: string;
    model?: string;
    approvalMode?: string;
  }) {
    if (data.providerName) {
      await this.selectProvider(data.providerName);
    }
    if (data.model) {
      await this.selectModel(data.model);
    }
    if (data.approvalMode) {
      await this.selectApprovalMode(data.approvalMode);
    }
  }

  /* ---- 提交 ---- */

  /** 点击 "创建" 或 "保存" 按钮 */
  async clickSubmit() {
    const btn = this.page.locator('button[type="submit"], button').filter({ hasText: /创\s?建|保\s?存/ }).first();
    await btn.click();
  }

  /* ---- 校验错误断言 ---- */

  /** 断言表单存在校验错误 */
  async expectValidationError() {
    const error = this.page.locator('.ant-form-item-explain-error');
    await expect(error.first()).toBeVisible({ timeout: 5_000 });
  }

  /**
   * 断言指定字段存在校验错误。
   * @param fieldName 字段的 CSS id（不含 # 前缀）
   */
  async expectFieldError(fieldName: string) {
    const field = this.page.locator(`#${fieldName}`);
    const formItem = field.locator('xpath=ancestor::div[contains(@class,"ant-form-item")]');
    const error = formItem.locator('.ant-form-item-explain-error');
    await expect(error).toBeVisible({ timeout: 5_000 });
  }

  /* ---- 返回列表 ---- */

  /** 点击 "返回列表" 按钮 */
  async clickBackToList() {
    const btn = this.page.locator('button').filter({ hasText: /返回列表/ });
    await btn.first().click();
  }

  /* ---- 辅助 ---- */

  /**
   * 获取指定输入框的值（用于断言数据保留）。
   * @param fieldId 字段 id
   */
  async getFieldValue(fieldId: string): Promise<string> {
    const input = this.page.locator(`#${fieldId} input, #${fieldId} textarea, #${fieldId}`).first();
    return input.inputValue();
  }

  /**
   * 快速跳到指定步骤（从步骤 1 开始逐个前进）。
   * 用于跳过中间步骤直达目标步骤。
   * @param targetStep 目标步骤索引（0-4）
   */
  async skipToStep(targetStep: number) {
    // 从当前步骤前进到目标步骤（不填写任何字段）
    for (let i = 0; i < targetStep; i++) {
      await this.clickNext();
    }
  }

  /**
   * 快速通过步骤 1（填写最小必填信息）。
   * @param name Agent 名称
   */
  async passStep1(name: string) {
    await this.fillStep1({ name });
    await this.clickNext();
  }

  /**
   * 快速通过步骤 2（选择 Provider 和 Model）。
   * @param providerName Provider 名称
   * @param modelName 模型名称
   */
  async passStep2(providerName: string, modelName: string) {
    await this.selectProvider(providerName);
    await this.selectModel(modelName);
    await this.clickNext();
  }
}
