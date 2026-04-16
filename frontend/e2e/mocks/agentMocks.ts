import type { Page, Route } from '@playwright/test';
import {
  MockStore,
  getPath,
  extractPathParams,
  jsonResponse,
  noContentResponse,
  parseBody,
  type MockModule,
} from './index';

/* ---- Agent 数据类型 ---- */

/** Mock Agent 记录结构 */
export interface MockAgent {
  id: string;
  name: string;
  description: string;
  instructions: string;
  model: string;
  provider_name: string | null;
  model_settings: Record<string, unknown>;
  tool_groups: string[];
  handoffs: string[];
  guardrails: {
    input: string[];
    output: string[];
    tool: string[];
  };
  approval_mode: string;
  mcp_servers: string[];
  agent_tools: string[];
  skills: string[];
  knowledge_bases: string[];
  output_type: Record<string, unknown> | null;
  metadata: Record<string, unknown>;
  prompt_variables: Array<Record<string, unknown>>;
  response_style: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

/* ---- Provider / Model Mock 数据 ---- */

/** Mock Provider 记录 */
const MOCK_PROVIDER = {
  id: 'mock-provider-id-1',
  name: 'e2e-mock-openai',
  provider_type: 'openai',
  base_url: 'https://api.openai.com/v1',
  api_key_set: true,
  auth_type: 'api_key',
  auth_config: {},
  rate_limit_rpm: null,
  rate_limit_tpm: null,
  model_tier: 'complex',
  capabilities: ['text', 'code', 'function_calling'],
  is_enabled: true,
  org_id: null,
  last_health_check: null,
  health_status: 'healthy',
  key_expires_at: null,
  key_last_rotated_at: null,
  key_expired: false,
  created_at: '2025-01-01T00:00:00Z',
  updated_at: '2025-01-01T00:00:00Z',
};

/** Mock Model 列表 */
const MOCK_MODELS = [
  {
    id: 'mock-model-id-1',
    provider_id: 'mock-provider-id-1',
    model_name: 'gpt-4o',
    display_name: 'GPT-4o',
    context_window: 128000,
    max_output_tokens: 4096,
    prompt_price_per_1k: 0.005,
    completion_price_per_1k: 0.015,
    is_enabled: true,
    created_at: '2025-01-01T00:00:00Z',
    updated_at: '2025-01-01T00:00:00Z',
  },
  {
    id: 'mock-model-id-2',
    provider_id: 'mock-provider-id-1',
    model_name: 'gpt-4o-mini',
    display_name: 'GPT-4o Mini',
    context_window: 128000,
    max_output_tokens: 4096,
    prompt_price_per_1k: 0.00015,
    completion_price_per_1k: 0.0006,
    is_enabled: true,
    created_at: '2025-01-01T00:00:00Z',
    updated_at: '2025-01-01T00:00:00Z',
  },
];

/* ---- 预设 Agent 数据 ---- */

/** 默认预设的 2 条 Mock Agent */
const DEFAULT_AGENTS: Omit<MockAgent, 'id'>[] = [
  {
    name: 'e2e-mock-agent-1',
    description: 'E2E 测试 Agent',
    instructions: '你是一个测试助手',
    model: 'gpt-4o',
    provider_name: 'e2e-mock-openai',
    model_settings: {},
    tool_groups: [],
    handoffs: [],
    guardrails: { input: [], output: [], tool: [] },
    approval_mode: 'full_auto',
    mcp_servers: [],
    agent_tools: [],
    skills: [],
    knowledge_bases: [],
    output_type: null,
    metadata: {},
    prompt_variables: [],
    response_style: null,
    is_active: true,
    created_at: '2025-01-01T00:00:00Z',
    updated_at: '2025-01-01T00:00:00Z',
  },
  {
    name: 'e2e-mock-agent-2',
    description: 'E2E 测试 Agent 二号',
    instructions: '你是另一个测试助手',
    model: 'gpt-4o-mini',
    provider_name: 'e2e-mock-openai',
    model_settings: {},
    tool_groups: [],
    handoffs: [],
    guardrails: { input: [], output: [], tool: [] },
    approval_mode: 'suggest',
    mcp_servers: [],
    agent_tools: [],
    skills: [],
    knowledge_bases: [],
    output_type: null,
    metadata: {},
    prompt_variables: [],
    response_style: null,
    is_active: true,
    created_at: '2025-01-02T00:00:00Z',
    updated_at: '2025-01-02T00:00:00Z',
  },
];

/* ---- Agent 内存存储 ---- */

// eslint-disable-next-line @typescript-eslint/no-explicit-any
const agentStore = new MockStore<any>();

/* ---- Provider / Model 路由拦截 ---- */

/** 拦截 Provider 列表请求 */
async function handleProviderList(route: Route) {
  await jsonResponse(route, {
    data: [MOCK_PROVIDER],
    total: 1,
    limit: 100,
    offset: 0,
  });
}

/** 拦截 Provider 模型列表请求 */
async function handleProviderModels(route: Route, path: string) {
  // 路径格式: /api/v1/providers/:id/models
  const params = extractPathParams('/api/v1/providers/:id/models', path);
  if (!params) {
    await jsonResponse(route, { data: [], total: 0 }, 404);
    return;
  }
  // 无论 id 是什么，都返回 mock 模型列表
  await jsonResponse(route, {
    data: MOCK_MODELS,
    total: MOCK_MODELS.length,
  });
}

/* ---- Agent CRUD 路由拦截 ---- */

/** 拦截 Agent 列表请求 */
async function handleAgentList(route: Route, path: string) {
  const url = new URL(path, 'http://localhost');
  const search = url.searchParams.get('search') || '';
  const limit = parseInt(url.searchParams.get('limit') || '20', 10);
  const offset = parseInt(url.searchParams.get('offset') || '0', 10);

  let agents = agentStore.list();
  if (search) {
    agents = agents.filter(
      (a) => a.name.includes(search) || a.description.includes(search),
    );
  }
  const total = agents.length;
  const sliced = agents.slice(offset, offset + limit);

  await jsonResponse(route, {
    data: sliced,
    total,
    limit,
    offset,
  });
}

/** 拦截 Agent 详情请求 */
async function handleAgentGet(route: Route, path: string) {
  const params = extractPathParams('/api/v1/agents/:name', path);
  if (!params) {
    await jsonResponse(route, { error: '未找到' }, 404);
    return;
  }
  const agent = agentStore.findBy('name', params.name);
  if (!agent) {
    await jsonResponse(route, { error: { code: 'NOT_FOUND', message: 'Agent 不存在' } }, 404);
    return;
  }
  await jsonResponse(route, agent);
}

/** 拦截 Agent 创建请求 */
async function handleAgentCreate(route: Route) {
  const body = (await parseBody(route)) as Record<string, unknown>;
  const now = new Date().toISOString();
  const agent = agentStore.create({
    name: (body.name as string) || '',
    description: (body.description as string) || '',
    instructions: (body.instructions as string) || '',
    model: (body.model as string) || '',
    provider_name: (body.provider_name as string | null) ?? null,
    model_settings: (body.model_settings as Record<string, unknown>) || {},
    tool_groups: (body.tool_groups as string[]) || [],
    handoffs: (body.handoffs as string[]) || [],
    guardrails: (body.guardrails as MockAgent['guardrails']) || { input: [], output: [], tool: [] },
    approval_mode: (body.approval_mode as string) || 'suggest',
    mcp_servers: (body.mcp_servers as string[]) || [],
    agent_tools: (body.agent_tools as string[]) || [],
    skills: (body.skills as string[]) || [],
    knowledge_bases: (body.knowledge_bases as string[]) || [],
    output_type: (body.output_type as Record<string, unknown>) || null,
    metadata: (body.metadata as Record<string, unknown>) || {},
    prompt_variables: (body.prompt_variables as Array<Record<string, unknown>>) || [],
    response_style: (body.response_style as string) || null,
    is_active: true,
    created_at: now,
    updated_at: now,
  });
  await jsonResponse(route, agent, 201);
}

/** 拦截 Agent 更新请求 */
async function handleAgentUpdate(route: Route, path: string) {
  const params = extractPathParams('/api/v1/agents/:name', path);
  if (!params) {
    await jsonResponse(route, { error: '无效路径' }, 400);
    return;
  }
  const existing = agentStore.findBy('name', params.name);
  if (!existing) {
    await jsonResponse(route, { error: { code: 'NOT_FOUND', message: 'Agent 不存在' } }, 404);
    return;
  }
  const body = (await parseBody(route)) as Partial<MockAgent>;
  const updated = agentStore.update(existing.id, body);
  await jsonResponse(route, { ...updated, updated_at: new Date().toISOString() });
}

/** 拦截 Agent 删除请求 */
async function handleAgentDelete(route: Route, path: string) {
  const params = extractPathParams('/api/v1/agents/:name', path);
  if (!params) {
    await jsonResponse(route, { error: '无效路径' }, 400);
    return;
  }
  const existing = agentStore.findBy('name', params.name);
  if (!existing) {
    await jsonResponse(route, { error: { code: 'NOT_FOUND', message: 'Agent 不存在' } }, 404);
    return;
  }
  agentStore.delete(existing.id);
  await noContentResponse(route);
}

/* ---- Mock 模块导出 ---- */

/** Agent Mock 模块 — 注册所有 Agent 和 Provider 相关的 API 拦截 */
export const agentMocks: MockModule = {
  name: 'agent',

  reset() {
    agentStore.reset();
    // 重新填充预设数据
    for (const agent of DEFAULT_AGENTS) {
      agentStore.create({ ...agent });
    }
  },

  async register(page: Page) {
    // Agent CRUD 路由
    await page.route('**/api/v1/agents**', async (route) => {
      const method = route.request().method();
      const url = route.request().url();
      const path = getPath(url);

      // 特殊路径先处理（导出、导入等）
      if (path.includes('/export') || path.includes('/import') ||
          path.includes('/prompt/') || path.includes('/realtime-status') ||
          path.includes('/activity-trend')) {
        // 对特殊路径返回空数据，避免 404
        await jsonResponse(route, { data: [] });
        return;
      }

      if (method === 'GET' && path === '/api/v1/agents') {
        await handleAgentList(route, url);
      } else if (method === 'GET' && path.match(/^\/api\/v1\/agents\/[^/]+$/)) {
        await handleAgentGet(route, path);
      } else if (method === 'POST' && path === '/api/v1/agents') {
        await handleAgentCreate(route);
      } else if (method === 'PUT' && path.match(/^\/api\/v1\/agents\/[^/]+$/)) {
        await handleAgentUpdate(route, path);
      } else if (method === 'DELETE' && path.match(/^\/api\/v1\/agents\/[^/]+$/)) {
        await handleAgentDelete(route, path);
      } else {
        await route.continue();
      }
    });

    // Provider 列表（Agent 编辑页级联选择需要）
    await page.route('**/api/v1/providers**', async (route) => {
      const method = route.request().method();
      const url = route.request().url();
      const path = getPath(url);

      if (method === 'GET' && path === '/api/v1/providers') {
        await handleProviderList(route);
      } else if (method === 'GET' && path.match(/^\/api\/v1\/providers\/[^/]+\/models$/)) {
        await handleProviderModels(route, path);
      } else if (method === 'GET' && path.match(/^\/api\/v1\/providers\/[^/]+$/)) {
        // Provider 详情
        await jsonResponse(route, MOCK_PROVIDER);
      } else {
        await route.continue();
      }
    });

    // 其他 Agent 编辑页依赖的 API（guardrails、tool-groups、mcp-servers、skills、knowledge-bases）
    await page.route('**/api/v1/guardrails**', async (route) => {
      await jsonResponse(route, { data: [], total: 0 });
    });
    await page.route('**/api/v1/tool-groups**', async (route) => {
      await jsonResponse(route, { data: [], total: 0 });
    });
    await page.route('**/api/v1/mcp-servers**', async (route) => {
      await jsonResponse(route, { data: [], total: 0 });
    });
    await page.route('**/api/v1/skills**', async (route) => {
      await jsonResponse(route, { data: [], total: 0 });
    });
    await page.route('**/api/v1/knowledge-bases**', async (route) => {
      await jsonResponse(route, { data: [], total: 0 });
    });
  },
};

/* ---- 辅助：批量生成 Mock Agent（用于分页测试） ---- */

/** 向内存存储追加 N 条 mock Agent */
export function seedAgents(count: number): void {
  for (let i = 0; i < count; i++) {
    const idx = agentStore.list().length + 1;
    agentStore.create({
      name: `e2e-batch-agent-${String(idx).padStart(3, '0')}`,
      description: `批量测试 Agent #${idx}`,
      instructions: `你是批量测试 Agent #${idx}`,
      model: 'gpt-4o',
      provider_name: 'e2e-mock-openai',
      model_settings: {},
      tool_groups: [],
      handoffs: [],
      guardrails: { input: [], output: [], tool: [] },
      approval_mode: 'full_auto',
      mcp_servers: [],
      agent_tools: [],
      skills: [],
      knowledge_bases: [],
      output_type: null,
      metadata: {},
      prompt_variables: [],
      response_style: null,
      is_active: true,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    });
  }
}
