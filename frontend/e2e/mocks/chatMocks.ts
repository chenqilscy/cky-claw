import type { Page, Route } from '@playwright/test';
import {
  type MockModule,
  MockStore,
  getPath,
  jsonResponse,
  parseBody,
} from './index';

/* ================================================================
 * Chat API Mock — 拦截 /api/v1/agents/** 和 /api/v1/sessions/**
 *
 * Mock 的 API：
 *   GET    /api/v1/agents                    → Agent 列表
 *   POST   /api/v1/sessions                  → 创建会话
 *   GET    /api/v1/sessions                  → 会话列表
 *   GET    /api/v1/sessions/:id/messages     → 消息历史
 *   POST   /api/v1/sessions/:id/run          → SSE 流式响应
 *   DELETE /api/v1/sessions/:id              → 删除会话
 * ================================================================ */

/* ---- 类型定义 ---- */

/** Agent 配置（与前端 AgentConfig 接口对齐） */
export interface MockAgent {
  name: string;
  description: string;
  [key: string]: unknown;
}

/** Chat 会话（与前端 ChatSession 接口对齐） */
export interface MockSession {
  agent_name: string;
  status: string;
  title: string;
  metadata: Record<string, unknown>;
  created_at: string;
  updated_at: string;
  [key: string]: unknown;
}

/** 消息条目（与前端 SessionMessageItem 接口对齐） */
export interface MockMessage {
  role: 'user' | 'assistant' | 'system';
  content: string;
  agent_name?: string | null;
  created_at: string;
  [key: string]: unknown;
}

/* ---- 内存存储 ---- */

const agentStore = new MockStore<MockAgent>();
const sessionStore = new MockStore<MockSession>();
const messageStore = new MockStore<MockMessage>();

/* ---- 预设 Mock 数据 ---- */

/** 默认 Agent 列表 */
const DEFAULT_AGENTS: MockAgent[] = [
  { name: 'e2e-mock-chat-agent', description: 'E2E 对话测试' },
];

/** SSE 流式响应 body 生成器 */
export function buildSSEBody(): string {
  return [
    'event: run_start\ndata: {"run_id":"mock-run-1"}\n\n',
    'event: text_delta\ndata: {"delta":"你好"}\n\n',
    'event: text_delta\ndata: {"delta":"，这是"}\n\n',
    'event: text_delta\ndata: {"delta":"模拟回复"}\n\n',
    'event: run_end\ndata: {"duration_ms":1500,"total_tokens":30}\n\n',
  ].join('');
}

/** 自定义 SSE 事件列表生成器 */
export function buildSSEBodyFromEvents(events: Array<{ event: string; data: Record<string, unknown> }>): string {
  return events
    .map((e) => `event: ${e.event}\ndata: ${JSON.stringify(e.data)}\n\n`)
    .join('');
}

/* ---- API URL 前缀 ---- */

const API_PREFIX = '/api/v1';

/* ---- 路由处理函数 ---- */

/** GET /api/v1/agents — 返回 Agent 列表 */
async function handleListAgents(route: Route) {
  const agents = agentStore.list();
  await jsonResponse(route, {
    data: agents,
    total: agents.length,
    limit: 100,
    offset: 0,
  });
}

/** POST /api/v1/sessions — 创建会话 */
async function handleCreateSession(route: Route) {
  const body = (await parseBody(route)) as { agent_name?: string; metadata?: Record<string, unknown> };
  const agentName = body.agent_name || 'e2e-mock-chat-agent';
  const now = new Date().toISOString();
  const session = sessionStore.create({
    agent_name: agentName,
    status: 'active',
    title: '',
    metadata: body.metadata || {},
    created_at: now,
    updated_at: now,
  });

  await jsonResponse(route, session);
}

/** GET /api/v1/sessions — 会话列表 */
async function handleListSessions(route: Route) {
  const url = new URL(route.request().url());
  const agentName = url.searchParams.get('agent_name');
  let sessions = sessionStore.list();
  if (agentName) {
    sessions = sessions.filter((s) => s.agent_name === agentName);
  }
  await jsonResponse(route, {
    data: sessions,
    total: sessions.length,
    limit: 50,
    offset: 0,
  });
}

/** GET /api/v1/sessions/:id/messages — 消息历史 */
async function handleGetMessages(route: Route, sessionId: string) {
  // 简化实现：返回所有消息（不按 sessionId 过滤）
  const messages = messageStore.list();
  await jsonResponse(route, {
    session_id: sessionId,
    messages,
    total: messages.length,
  });
}

/** POST /api/v1/sessions/:id/run — SSE 流式响应 */
async function handleRunStream(route: Route) {
  const sseBody = buildSSEBody();
  await route.fulfill({
    status: 200,
    headers: {
      'Content-Type': 'text/event-stream',
      'Cache-Control': 'no-cache',
      'Connection': 'keep-alive',
    },
    body: sseBody,
  });
}

/** DELETE /api/v1/sessions/:id — 删除会话 */
async function handleDeleteSession(route: Route, sessionId: string) {
  sessionStore.delete(sessionId);
  await jsonResponse(route, null);
}

/* ---- 路由分发 ---- */

async function handleRoute(route: Route) {
  const path = getPath(route.request().url());
  const method = route.request().method();

  // GET /api/v1/agents
  if (path === `${API_PREFIX}/agents` && method === 'GET') {
    return handleListAgents(route);
  }

  // POST /api/v1/sessions
  if (path === `${API_PREFIX}/sessions` && method === 'POST') {
    return handleCreateSession(route);
  }

  // GET /api/v1/sessions
  if (path === `${API_PREFIX}/sessions` && method === 'GET') {
    return handleListSessions(route);
  }

  // GET /api/v1/sessions/:id/messages
  const messagesMatch = path.match(new RegExp(`^${API_PREFIX}/sessions/([^/]+)/messages$`));
  if (messagesMatch && method === 'GET') {
    return handleGetMessages(route, messagesMatch[1]);
  }

  // POST /api/v1/sessions/:id/run
  const runMatch = path.match(new RegExp(`^${API_PREFIX}/sessions/([^/]+)/run$`));
  if (runMatch && method === 'POST') {
    return handleRunStream(route);
  }

  // DELETE /api/v1/sessions/:id
  const deleteMatch = path.match(new RegExp(`^${API_PREFIX}/sessions/([^/]+)$`));
  if (deleteMatch && method === 'DELETE') {
    return handleDeleteSession(route, deleteMatch[1]);
  }

  // 未匹配的路由放行
  await route.continue();
}

/* ---- MockModule 导出 ---- */

/** 重置所有内存数据并填充默认 Agent、会话和消息 */
function resetData() {
  agentStore.reset();
  sessionStore.reset();
  messageStore.reset();

  // 填充默认 Agent
  for (const agent of DEFAULT_AGENTS) {
    agentStore.create({ ...agent });
  }

  // 填充默认会话
  sessionStore.create({
    agent_name: 'e2e-mock-chat-agent',
    status: 'active',
    title: 'E2E 测试对话',
    metadata: {},
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
  });

  // 填充 2 条预设消息（1 user + 1 assistant）
  messageStore.create({
    role: 'user',
    content: '你好，这是一条测试消息',
    agent_name: null,
    created_at: new Date().toISOString(),
  });
  messageStore.create({
    role: 'assistant',
    content: '你好，我是 E2E 测试 Agent 的模拟回复',
    agent_name: 'e2e-mock-chat-agent',
    created_at: new Date().toISOString(),
  });
}

/** Chat Mock 模块（实现 MockModule 接口） */
export const chatMocks: MockModule = {
  name: 'chatMocks',

  reset() {
    resetData();
  },

  async register(page: Page) {
    await page.route(
      (url) => {
        const path = getPath(url.toString());
        return (
          path.startsWith(`${API_PREFIX}/agents`) ||
          path.startsWith(`${API_PREFIX}/sessions`)
        );
      },
      handleRoute,
    );
  },
};

/* ---- 辅助方法（供测试直接操作内存数据） ---- */

/** 添加自定义 Agent */
export function addMockAgent(agent: MockAgent) {
  return agentStore.create({ ...agent });
}

/** 添加自定义会话 */
export function addMockSession(session: MockSession) {
  return sessionStore.create({ ...session });
}

/** 添加消息 */
export function addMockMessage(message: MockMessage) {
  return messageStore.create({ ...message });
}

/** 获取所有会话 */
export function getMockSessions() {
  return sessionStore.list();
}

/** 获取所有消息 */
export function getMockMessages() {
  return messageStore.list();
}

/** 清空所有会话（保留 Agent） */
export function clearSessions() {
  sessionStore.reset();
  messageStore.reset();
}
