import type { Page, Route } from '@playwright/test';
import {
  MockStore,
  getPath,
  extractPathParams,
  jsonResponse,
  parseBody,
  type MockModule,
} from './index';

/* ---- 类型定义 ---- */

interface ProviderMock {
  id: string;
  name: string;
  provider_type: string;
  base_url: string;
  auth_type: string;
  api_key_set: boolean;
  is_enabled: boolean;
  model_tier: string;
  capabilities: string[];
  auth_config: Record<string, unknown>;
  rate_limit_rpm: number | null;
  rate_limit_tpm: number | null;
  org_id: string | null;
  last_health_check: string | null;
  health_status: string;
  key_expires_at: string | null;
  key_last_rotated_at: string | null;
  key_expired: boolean;
  created_at: string;
  updated_at: string;
}

interface ProviderModelMock {
  id: string;
  provider_id: string;
  model_name: string;
  display_name: string;
  context_window: number;
  max_output_tokens: number | null;
  prompt_price_per_1k: number;
  completion_price_per_1k: number;
  is_enabled: boolean;
  created_at: string;
  updated_at: string;
}

/* ---- 预设数据 ---- */

const PRESET_PROVIDERS: Omit<ProviderMock, 'id'>[] = [
  {
    name: 'e2e-mock-openai',
    provider_type: 'openai',
    base_url: 'https://api.openai.com/v1',
    auth_type: 'api_key',
    api_key_set: true,
    is_enabled: true,
    model_tier: 'general',
    capabilities: ['chat', 'function_calling'],
    auth_config: {},
    rate_limit_rpm: null,
    rate_limit_tpm: null,
    org_id: null,
    last_health_check: null,
    health_status: 'unknown',
    key_expires_at: null,
    key_last_rotated_at: null,
    key_expired: false,
    created_at: '2025-01-01T00:00:00Z',
    updated_at: '2025-01-01T00:00:00Z',
  },
  {
    name: 'e2e-mock-anthropic',
    provider_type: 'anthropic',
    base_url: 'https://api.anthropic.com/v1',
    auth_type: 'api_key',
    api_key_set: true,
    is_enabled: true,
    model_tier: 'complex',
    capabilities: ['chat', 'vision'],
    auth_config: {},
    rate_limit_rpm: null,
    rate_limit_tpm: null,
    org_id: null,
    last_health_check: null,
    health_status: 'unknown',
    key_expires_at: null,
    key_last_rotated_at: null,
    key_expired: false,
    created_at: '2025-01-02T00:00:00Z',
    updated_at: '2025-01-02T00:00:00Z',
  },
];

const PRESET_MODELS: Record<string, Omit<ProviderModelMock, 'id' | 'provider_id'>[]> = {
  'mock-1': [
    {
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
  ],
};

/* ---- 存储实例 ---- */

const providerStore = new MockStore<ProviderMock>();
const modelStore = new MockStore<ProviderModelMock>();

/** 重置所有存储并填充预设数据 */
function resetStores() {
  providerStore.reset();
  modelStore.reset();

  // 填充预设 Provider — MockStore.genId() 生成 mock-1, mock-2
  for (const preset of PRESET_PROVIDERS) {
    providerStore.create({ ...preset });
  }
  // mock-1 是第一个 provider，模型引用它

  // 填充预设模型（provider_id 对应 mock-1）
  for (const m of PRESET_MODELS['mock-1'] ?? []) {
    modelStore.create({
      ...m,
      provider_id: 'mock-1',
    });
  }
}

/* ---- 路由处理 ---- */

/** 匹配 Provider API 路径前缀 */
const API_PREFIX = '/api/v1/providers';

async function handleRoute(route: Route) {
  const path = getPath(route.request().url());
  const method = route.request().method();

  // 只拦截 /api/v1/providers/** 的请求
  if (!path.startsWith(API_PREFIX)) {
    await route.continue();
    return;
  }

  const subPath = path.slice(API_PREFIX.length);

  /* ---- 列表: GET /api/v1/providers ---- */
  if (subPath === '' && method === 'GET') {
    await jsonResponse(route, {
      data: providerStore.list(),
      total: providerStore.list().length,
      limit: 20,
      offset: 0,
    });
    return;
  }

  /* ---- 创建: POST /api/v1/providers ---- */
  if (subPath === '' && method === 'POST') {
    const body = (await parseBody(route)) as Record<string, unknown>;
    const now = new Date().toISOString();
    const provider = providerStore.create({
      name: (body.name as string) || '',
      provider_type: (body.provider_type as string) || 'openai',
      base_url: (body.base_url as string) || '',
      auth_type: (body.auth_type as string) || 'api_key',
      api_key_set: !!(body.api_key as string),
      is_enabled: true,
      model_tier: (body.model_tier as string) || 'moderate',
      capabilities: (body.capabilities as string[]) || [],
      auth_config: (body.auth_config as Record<string, unknown>) || {},
      rate_limit_rpm: (body.rate_limit_rpm as number | null) ?? null,
      rate_limit_tpm: (body.rate_limit_tpm as number | null) ?? null,
      org_id: null,
      last_health_check: null,
      health_status: 'unknown',
      key_expires_at: null,
      key_last_rotated_at: null,
      key_expired: false,
      created_at: now,
      updated_at: now,
    });
    await jsonResponse(route, provider, 201);
    return;
  }

  /* ---- 测试连接: POST /api/v1/providers/:id/test ---- */
  let params = extractPathParams('/:id/test', subPath);
  if (params && method === 'POST') {
    await jsonResponse(route, {
      success: true,
      latency_ms: 150,
      model_used: 'gpt-4o',
    });
    return;
  }

  /* ---- 同步模型: POST /api/v1/providers/:id/models/sync ---- */
  params = extractPathParams('/:id/models/sync', subPath);
  if (params && method === 'POST') {
    await jsonResponse(route, {
      synced: 3,
      created: 2,
      updated: 1,
      errors: [],
    });
    return;
  }

  /* ---- 模型列表: GET /api/v1/providers/:id/models ---- */
  params = extractPathParams('/:id/models', subPath);
  if (params && method === 'GET') {
    const providerId = params.id;
    const models = modelStore.list().filter((m) => m.provider_id === providerId);
    await jsonResponse(route, {
      data: models,
      total: models.length,
    });
    return;
  }

  /* ---- 添加模型: POST /api/v1/providers/:id/models ---- */
  params = extractPathParams('/:id/models', subPath);
  if (params && method === 'POST') {
    const providerId = params.id;
    const body = (await parseBody(route)) as Record<string, unknown>;
    const now = new Date().toISOString();
    const model = modelStore.create({
      provider_id: providerId,
      model_name: (body.model_name as string) || '',
      display_name: (body.display_name as string) || '',
      context_window: (body.context_window as number) ?? 4096,
      max_output_tokens: (body.max_output_tokens as number | null) ?? null,
      prompt_price_per_1k: (body.prompt_price_per_1k as number) ?? 0,
      completion_price_per_1k: (body.completion_price_per_1k as number) ?? 0,
      is_enabled: (body.is_enabled as boolean) ?? true,
      created_at: now,
      updated_at: now,
    });
    await jsonResponse(route, model, 201);
    return;
  }

  /* ---- 更新模型: PUT /api/v1/providers/:id/models/:mid ---- */
  params = extractPathParams('/:id/models/:mid', subPath);
  if (params && method === 'PUT') {
    const modelId = params.mid;
    const body = (await parseBody(route)) as Record<string, unknown>;
    const updated = modelStore.update(modelId, {
      ...(body as Partial<ProviderModelMock>),
      updated_at: new Date().toISOString(),
    });
    if (updated) {
      await jsonResponse(route, updated);
    } else {
      await jsonResponse(route, { detail: '模型不存在' }, 404);
    }
    return;
  }

  /* ---- 删除模型: DELETE /api/v1/providers/:id/models/:mid ---- */
  params = extractPathParams('/:id/models/:mid', subPath);
  if (params && method === 'DELETE') {
    modelStore.delete(params.mid);
    await jsonResponse(route, null, 204);
    return;
  }

  /* ---- 切换启用/禁用: PUT /api/v1/providers/:id/toggle ---- */
  params = extractPathParams('/:id/toggle', subPath);
  if (params && method === 'PUT') {
    const body = (await parseBody(route)) as Record<string, unknown>;
    const updated = providerStore.update(params.id, {
      is_enabled: body.is_enabled as boolean,
      updated_at: new Date().toISOString(),
    });
    if (updated) {
      await jsonResponse(route, updated);
    } else {
      await jsonResponse(route, { detail: '厂商不存在' }, 404);
    }
    return;
  }

  /* ---- 轮换密钥: POST /api/v1/providers/:id/rotate-key ---- */
  params = extractPathParams('/:id/rotate-key', subPath);
  if (params && method === 'POST') {
    const updated = providerStore.update(params.id, {
      api_key_set: true,
      key_last_rotated_at: new Date().toISOString(),
      key_expired: false,
      updated_at: new Date().toISOString(),
    });
    if (updated) {
      await jsonResponse(route, updated);
    } else {
      await jsonResponse(route, { detail: '厂商不存在' }, 404);
    }
    return;
  }

  /* ---- 获取单个: GET /api/v1/providers/:id ---- */
  params = extractPathParams('/:id', subPath);
  if (params && method === 'GET') {
    const provider = providerStore.get(params.id);
    if (provider) {
      await jsonResponse(route, provider);
    } else {
      await jsonResponse(route, { detail: '厂商不存在' }, 404);
    }
    return;
  }

  /* ---- 更新: PUT /api/v1/providers/:id ---- */
  params = extractPathParams('/:id', subPath);
  if (params && method === 'PUT') {
    const body = (await parseBody(route)) as Record<string, unknown>;
    const updated = providerStore.update(params.id, {
      ...(body as Partial<ProviderMock>),
      updated_at: new Date().toISOString(),
    });
    if (updated) {
      await jsonResponse(route, updated);
    } else {
      await jsonResponse(route, { detail: '厂商不存在' }, 404);
    }
    return;
  }

  /* ---- 删除: DELETE /api/v1/providers/:id ---- */
  params = extractPathParams('/:id', subPath);
  if (params && method === 'DELETE') {
    providerStore.delete(params.id);
    await jsonResponse(route, null, 204);
    return;
  }

  /* ---- 未匹配的路由 ---- */
  await route.continue();
}

/* ---- 导出 ---- */

/** 创建并注册 Provider API Mock */
export async function createProviderMocks(page: Page) {
  resetStores();
  await page.route('**/api/v1/providers**', handleRoute);
}

/** 获取 Provider 存储（用于在测试中直接操作数据） */
export function getProviderStore() {
  return providerStore;
}

/** 获取模型存储 */
export function getModelStore() {
  return modelStore;
}
