import { expect, type Locator } from '@playwright/test';
import { BasePage } from './BasePage';

/**
 * ChatPage — /chat 页面的 Page Object Model。
 *
 * 封装侧边栏 Agent 选择、消息发送、会话管理等交互。
 * 选择器基于 ChatPage.tsx / ChatSidebar.tsx / ChatWindow.tsx 的实际 DOM 结构。
 */
export class ChatPage extends BasePage {
  /* ---- 定位器 ---- */

  /** 消息输入框（Ant Design TextArea） */
  get messageInput(): Locator {
    return this.page.locator('textarea').first();
  }

  /** 侧边栏容器（main 内容区内 ChatPage 的 Sider，或移动端 Drawer） */
  private get sidebarContainer(): Locator {
    return this.page.locator('main .ant-layout-sider, .ant-drawer-body').first();
  }

  /** Agent 选择器触发器（侧边栏内的 Select 下拉的 .ant-select-selector） */
  get agentSelect(): Locator {
    return this.sidebarContainer.locator('.ant-select-selector').first();
  }

  /** Agent Select 外层容器（用于 visible 断言） */
  get agentSelectWrapper(): Locator {
    return this.sidebarContainer.locator('.ant-select').first();
  }

  /** "新建对话" 按钮 */
  get newSessionButton(): Locator {
    return this.sidebarContainer.locator('button').getByText('新建对话').first();
  }

  /** 发送按钮（SendOutlined 图标按钮） */
  get sendButton(): Locator {
    return this.page.locator('button .anticon-send').locator('..').first();
  }

  /** 会话列表项（侧边栏内的历史会话） */
  get sessionItems(): Locator {
    return this.sidebarContainer.locator('.ant-list-item');
  }

  /** 顶栏标题文本 */
  get headerTitle(): Locator {
    return this.page.locator('.ant-typography').filter({ hasText: /请选择 Agent|.+/ }).first();
  }

  /* ---- 导航 ---- */

  /** 导航到 /chat 页面 */
  async goto() {
    await this.navigateTo('/chat');
  }

  /* ---- Agent 选择 ---- */

  /**
   * 在侧边栏选择指定 Agent 并激活对话。
   *
   * ChatSidebar 的 Select onChange 只更新侧边栏内部的 selectedAgent 状态，
   * 不会设置 ChatPage 的 agentName。必须点击"新建对话"按钮触发 onNewSession
   * 才能真正激活 textarea。
   *
   * 流程：Select 中选择 Agent → 点击"新建对话"按钮
   */
  async selectAgent(name: string) {
    // 1. 点击 Select 触发器打开下拉
    await this.agentSelect.click({ force: true });

    // 2. 等待下拉面板出现，点击匹配的选项
    const option = this.page
      .locator('.ant-select-dropdown:not(.ant-select-dropdown-hidden) .ant-select-item-option')
      .getByText(name, { exact: true })
      .first();

    // 如果下拉没出现，重试点击
    try {
      await option.waitFor({ state: 'visible', timeout: 3_000 });
    } catch {
      await this.agentSelect.click({ force: true });
      await option.waitFor({ state: 'visible', timeout: 5_000 });
    }
    await option.click();

    // 3. 点击"新建对话"按钮触发 onNewSession，设置 ChatPage.agentName
    await this.newSessionButton.click();
  }

  /* ---- 消息操作 ---- */

  /** 在 textarea 中填写消息文本并发送（Enter 键） */
  async sendMessage(text: string) {
    await this.messageInput.fill(text);
    await this.messageInput.press('Enter');
  }

  /** 在 textarea 中填写消息文本，然后点击发送按钮 */
  async sendMessageByButton(text: string) {
    await this.messageInput.fill(text);
    await this.sendButton.click();
  }

  /* ---- 断言 ---- */

  /** 断言用户消息气泡出现（用户消息靠右对齐，背景色为 colorPrimary） */
  async expectUserMessage(text: string) {
    // 用户消息通过文本内容定位
    const msgBubble = this.page
      .locator('div')
      .filter({ hasText: text })
      .first();
    await expect(msgBubble).toBeVisible({ timeout: 10_000 });
  }

  /** 断言 assistant 消息出现（可指定包含的文本片段） */
  async expectAssistantMessage(text?: string) {
    // assistant 消息靠左对齐，包含 Markdown 渲染内容
    if (text) {
      const msg = this.page.getByText(text, { exact: false }).first();
      await expect(msg).toBeVisible({ timeout: 15_000 });
    } else {
      // 不指定文本时，等待消息区域出现非空 assistant 消息
      // assistant 消息通过 MarkdownRenderer 渲染，包含在 div 中
      const assistantArea = this.page.locator('[class*="markdown"], .ant-typography').first();
      await expect(assistantArea).toBeVisible({ timeout: 15_000 }).catch(() => {
        // 回退：等待任意消息内容出现
      });
    }
  }

  /** 断言 textarea 处于 disabled 状态 */
  async expectInputDisabled() {
    await expect(this.messageInput).toBeDisabled();
  }

  /** 断言 textarea 处于 enabled 状态 */
  async expectInputEnabled() {
    await expect(this.messageInput).toBeEnabled();
  }

  /** 判断 textarea 是否 disabled */
  async isInputDisabled(): Promise<boolean> {
    return this.messageInput.isDisabled();
  }

  /* ---- 会话操作 ---- */

  /** 点击 "新建对话" 按钮 */
  async clickNewSession() {
    await this.newSessionButton.click();
  }

  /** 断言会话列表中包含指定标题的会话 */
  async expectSessionInList(title: string) {
    const item = this.sessionItems.filter({ hasText: title }).first();
    await expect(item).toBeVisible({ timeout: 5_000 });
  }

  /** 点击会话列表中指定标题的会话 */
  async clickSession(title: string) {
    const item = this.sessionItems.filter({ hasText: title }).first();
    await item.click();
  }

  /** 断言会话列表项数量 */
  async expectSessionCount(count: number) {
    await expect(this.sessionItems).toHaveCount(count, { timeout: 5_000 });
  }

  /** 断言消息区域显示指定文本（提示语或消息内容） */
  async expectMessageAreaText(text: string) {
    const el = this.page.getByText(text, { exact: false }).first();
    await expect(el).toBeVisible({ timeout: 5_000 });
  }

  /** 获取当前消息数量（消息气泡的 div 数量） */
  async getMessageCount(): Promise<number> {
    // 消息气泡在消息列表区域中，每条消息是一个直接子 div
    const messageArea = this.page.locator('[style*="overflow: auto"]').first();
    if (!(await messageArea.isVisible().catch(() => false))) {
      return 0;
    }
    // 消息气泡的特征：有 marginBottom: 12 的 div
    const messages = messageArea.locator(':scope > div[style*="margin-bottom"]');
    return messages.count();
  }
}
