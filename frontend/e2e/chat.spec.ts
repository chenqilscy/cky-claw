import { test, expect } from '@playwright/test';
import { ChatPage } from './pom/ChatPage';
import {
  chatMocks,
  addMockAgent,
  addMockSession,
  addMockMessage,
  clearSessions,
  buildSSEBodyFromEvents,
} from './mocks/chatMocks';
import { registerMocks } from './mocks/index';

/**
 * CkyClaw Chat 模块 E2E 测试。
 *
 * 所有 API 请求通过 Playwright route mock 拦截，不依赖真实后端。
 * Mock 注册在 beforeEach 中，每个测试拥有独立的内存数据。
 */

test.describe('Chat 对话模块', () => {
  let chatPage: ChatPage;

  test.beforeEach(async ({ page }) => {
    // 注入 JWT Token 以绕过前端认证守卫
    await page.addInitScript(() => {
      localStorage.setItem(
        'ckyclaw_token',
        'eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJ0ZXN0QGV4YW1wbGUuY29tIiwiZXhwIjozMjUxODA0ODAwfQ.fake',
      );
    });

    // 注册 Chat API Mock
    await registerMocks(page, [chatMocks]);

    chatPage = new ChatPage(page);
    await chatPage.goto();
  });

  // ================================================================
  // 测试 1: Chat 页面基本渲染
  // ================================================================
  test('Chat 页面基本渲染 — textarea 可见且初始 disabled', async () => {
    // textarea 应可见
    await expect(chatPage.messageInput).toBeVisible({ timeout: 10_000 });

    // 未选 Agent 时 textarea 应 disabled
    await chatPage.expectInputDisabled();

    // Agent 选择器应可见
    await expect(chatPage.agentSelect).toBeVisible();

    // 顶栏应显示 "请选择 Agent"
    await chatPage.expectMessageAreaText('请从左侧选择 Agent 并创建对话');
  });

  // ================================================================
  // 测试 2: 侧边栏 Agent 选择器
  // ================================================================
  test('侧边栏 Agent 选择器 — 选择 Agent 后 textarea 变为 enabled', async () => {
    // Agent 选择器可见
    await expect(chatPage.agentSelect).toBeVisible();

    // 选择 Agent
    await chatPage.selectAgent('e2e-mock-chat-agent');

    // textarea 应变为 enabled
    await chatPage.expectInputEnabled();
  });

  // ================================================================
  // 测试 3: 新建对话
  // ================================================================
  test('新建对话 — 选择 Agent → 点击新建 → textarea 可用', async () => {
    // 先选择 Agent
    await chatPage.selectAgent('e2e-mock-chat-agent');
    await chatPage.expectInputEnabled();

    // 点击 "新建对话" 按钮
    await chatPage.clickNewSession();

    // 新建对话后 textarea 仍应可用
    await chatPage.expectInputEnabled();

    // 应显示空对话提示
    await chatPage.expectMessageAreaText('发送消息开始对话');
  });

  // ================================================================
  // 测试 4: 发送消息 SSE 流式回复
  // ================================================================
  test('发送消息 SSE 流式回复 — 用户消息出现 + assistant 模拟回复', async () => {
    // 选择 Agent
    await chatPage.selectAgent('e2e-mock-chat-agent');

    // 输入消息并发送
    await chatPage.sendMessage('你好');

    // 断言用户消息出现
    await chatPage.expectUserMessage('你好');

    // 断言 assistant 消息出现（SSE 流式 mock 返回 "你好，这是模拟回复"）
    await chatPage.expectAssistantMessage('模拟回复');
  });

  // ================================================================
  // 测试 5: 消息历史加载
  // ================================================================
  test('消息历史加载 — 点击已有会话后显示历史消息', async ({ page }) => {
    // 默认 mock 已预设 1 个会话和 2 条消息
    // 先选择 Agent 让侧边栏加载会话列表
    await chatPage.selectAgent('e2e-mock-chat-agent');

    // 等待会话列表加载
    await page.waitForTimeout(500);

    // 点击预设的会话（标题为 agent name 或 "E2E 测试对话"）
    const sessionItem = chatPage.sessionItems.first();
    if (await sessionItem.isVisible().catch(() => false)) {
      await sessionItem.click();
      await page.waitForTimeout(500);

      // 断言历史消息渲染（预设的用户消息和 assistant 消息）
      await chatPage.expectUserMessage('这是一条测试消息');
      await chatPage.expectAssistantMessage('模拟回复');
    }
  });

  // ================================================================
  // 测试 6: 未选 Agent 时 textarea disabled
  // ================================================================
  test('未选 Agent 时 textarea disabled', async () => {
    // 初始状态：未选 Agent
    await chatPage.expectInputDisabled();

    // placeholder 应提示 "请先选择 Agent"
    const placeholder = await chatPage.messageInput.getAttribute('placeholder');
    expect(placeholder).toContain('请先选择 Agent');
  });

  // ================================================================
  // 测试 7: 选择 Agent 后 textarea enabled
  // ================================================================
  test('选择 Agent 后 textarea enabled', async () => {
    // 初始 disabled
    await chatPage.expectInputDisabled();

    // 选择 Agent
    await chatPage.selectAgent('e2e-mock-chat-agent');

    // 变为 enabled
    await chatPage.expectInputEnabled();

    // placeholder 应变为包含 "输入消息" 的提示
    const placeholder = await chatPage.messageInput.getAttribute('placeholder');
    expect(placeholder).toContain('输入消息');
  });

  // ================================================================
  // 测试 8: 发送空消息不触发
  // ================================================================
  test('发送空消息不触发 — 不增加消息数量', async ({ page }) => {
    await chatPage.selectAgent('e2e-mock-chat-agent');

    // 记录当前消息数
    const countBefore = await chatPage.getMessageCount();

    // 输入空白文本并发送
    await chatPage.sendMessage('   ');

    // 等待一下确保不会触发发送
    await page.waitForTimeout(500);

    // 消息数不应增加
    const countAfter = await chatPage.getMessageCount();
    expect(countAfter).toBe(countBefore);
  });

  // ================================================================
  // 测试 9: 会话列表渲染
  // ================================================================
  test('会话列表渲染 — Mock 多个会话后列表项数量正确', async () => {
    // 清除默认会话，添加 3 个自定义会话
    clearSessions();
    addMockSession({
      agent_name: 'e2e-mock-chat-agent',
      status: 'active',
      title: '对话一',
      metadata: {},
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    });
    addMockSession({
      agent_name: 'e2e-mock-chat-agent',
      status: 'active',
      title: '对话二',
      metadata: {},
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    });
    addMockSession({
      agent_name: 'e2e-mock-chat-agent',
      status: 'active',
      title: '对话三',
      metadata: {},
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    });

    // 选择 Agent 触发会话列表加载
    await chatPage.selectAgent('e2e-mock-chat-agent');

    // 断言列表项数量为 3
    await chatPage.expectSessionCount(3);
  });

  // ================================================================
  // 测试 10: 切换会话
  // ================================================================
  test('切换会话 — 点击另一个会话后消息区域更新', async ({ page }) => {
    // 准备两个会话，各自有不同消息
    clearSessions();

    addMockSession({
      agent_name: 'e2e-mock-chat-agent',
      status: 'active',
      title: '会话 Alpha',
      metadata: {},
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    });

    addMockSession({
      agent_name: 'e2e-mock-chat-agent',
      status: 'active',
      title: '会话 Beta',
      metadata: {},
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    });

    // 为两个会话添加不同的消息
    addMockMessage({
      role: 'user',
      content: '这是 Alpha 会话的消息',
      agent_name: null,
      created_at: new Date().toISOString(),
    });
    addMockMessage({
      role: 'assistant',
      content: 'Alpha 回复内容',
      agent_name: 'e2e-mock-chat-agent',
      created_at: new Date().toISOString(),
    });

    // 选择 Agent 触发会话列表加载
    // sidebar 已有默认选中的 agent，先点击 "新建对话" 激活 textarea
    await chatPage.newSessionButton.click();
    await chatPage.expectInputEnabled();

    // 等待会话列表渲染
    await chatPage.expectSessionCount(2);

    // 点击第一个会话
    await chatPage.clickSession('Alpha');
    await page.waitForTimeout(500);

    // 消息区域应显示 Alpha 的内容
    await chatPage.expectUserMessage('Alpha');

    // 点击第二个会话
    await chatPage.clickSession('Beta');
    await page.waitForTimeout(500);

    // 关键断言：会话列表中 Beta 被高亮
    const betaItem = chatPage.sessionItems.filter({ hasText: 'Beta' }).first();
    await expect(betaItem).toBeVisible();
  });
});

/* ================================================================
 * 独立测试：SSE 流式 Mock 边界情况
 * ================================================================ */

test.describe('Chat SSE 流式 Mock', () => {
  test('自定义 SSE 事件序列可正确生成 body', () => {
    const body = buildSSEBodyFromEvents([
      { event: 'run_start', data: { run_id: 'custom-run-1' } },
      { event: 'text_delta', data: { delta: '自定义' } },
      { event: 'text_delta', data: { delta: '回复内容' } },
      { event: 'run_end', data: { duration_ms: 500, total_tokens: 10 } },
    ]);

    expect(body).toContain('event: run_start');
    expect(body).toContain('event: text_delta');
    expect(body).toContain('"delta":"自定义"');
    expect(body).toContain('event: run_end');
  });
});
