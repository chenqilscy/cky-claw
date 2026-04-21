import { api } from './api';

export const PROVIDER_TYPES = [
  'openai', 'anthropic', 'azure', 'deepseek', 'qwen',
  'doubao', 'zhipu', 'moonshot', 'minimax', 'openai_compatible', 'custom',
] as const;

/** 各厂商官方 API Base URL，azure/openai_compatible/custom 需用户自行填写 */
export const PROVIDER_BASE_URLS: Record<string, string> = {
  openai: 'https://api.openai.com/v1',
  anthropic: 'https://api.anthropic.com/v1',
  azure: '',
  deepseek: 'https://api.deepseek.com/v1',
  qwen: 'https://dashscope.aliyuncs.com/compatible-mode/v1',
  doubao: 'https://ark.cn-beijing.volces.com/api/v3',
  zhipu: 'https://open.bigmodel.cn/api/paas/v4',
  moonshot: 'https://api.moonshot.cn/v1',
  minimax: 'https://api.minimax.chat/v1',
  openai_compatible: '',
  custom: '',
};

export const AUTH_TYPES = ['api_key', 'azure_ad', 'custom_header'] as const;

/** 厂商类型的中文显示标签 */
export const PROVIDER_TYPE_LABELS: Record<string, string> = {
  openai: 'OpenAI',
  anthropic: 'Anthropic',
  azure: 'Azure OpenAI',
  deepseek: 'DeepSeek',
  qwen: '通义千问',
  doubao: '豆包',
  zhipu: '智谱 AI',
  moonshot: 'Moonshot',
  minimax: 'MiniMax',
  openai_compatible: 'OpenAI Compatible',
  custom: '自定义',
};

export type ProviderType = typeof PROVIDER_TYPES[number];
export type AuthType = typeof AUTH_TYPES[number];

export type ModelTier = 'simple' | 'moderate' | 'complex' | 'reasoning' | 'multimodal';
export type ProviderCapability = 'text' | 'code' | 'vision' | 'reasoning' | 'function_calling';

export const MODEL_TIER_OPTIONS: { label: string; value: ModelTier }[] = [
  { label: '简单', value: 'simple' },
  { label: '中等', value: 'moderate' },
  { label: '复杂', value: 'complex' },
  { label: '推理', value: 'reasoning' },
  { label: '多模态', value: 'multimodal' },
];

export const CAPABILITY_OPTIONS: { label: string; value: ProviderCapability }[] = [
  { label: '文本处理', value: 'text' },
  { label: '代码处理', value: 'code' },
  { label: '视觉识别', value: 'vision' },
  { label: '推理能力', value: 'reasoning' },
  { label: '函数调用', value: 'function_calling' },
];

export const MODEL_TIER_LABELS: Record<ModelTier, string> = {
  simple: '简单',
  moderate: '中等',
  complex: '复杂',
  reasoning: '推理',
  multimodal: '多模态',
};

export const CAPABILITY_LABELS: Record<ProviderCapability, string> = {
  text: '文本',
  code: '代码',
  vision: '视觉',
  reasoning: '推理',
  function_calling: '函数调用',
};

export interface ProviderResponse {
  id: string;
  name: string;
  provider_type: ProviderType;
  base_url: string;
  api_key_set: boolean;
  auth_type: AuthType;
  auth_config: Record<string, unknown>;
  rate_limit_rpm: number | null;
  rate_limit_tpm: number | null;
  model_tier: ModelTier;
  capabilities: ProviderCapability[];
  is_enabled: boolean;
  org_id: string | null;
  last_health_check: string | null;
  health_status: string;
  key_expires_at: string | null;
  key_last_rotated_at: string | null;
  key_expired: boolean;
  created_at: string;
  updated_at: string;
}

export interface RotateKeyRequest {
  new_api_key: string;
  key_expires_at?: string | null;
}

export interface ProviderListResponse {
  data: ProviderResponse[];
  total: number;
  limit: number;
  offset: number;
}

export interface ProviderCreateRequest {
  name: string;
  provider_type: string;
  base_url: string;
  api_key: string;
  auth_type?: string;
  auth_config?: Record<string, unknown>;
  rate_limit_rpm?: number | null;
  rate_limit_tpm?: number | null;
  model_tier?: ModelTier;
  capabilities?: ProviderCapability[];
}

export interface ProviderUpdateRequest {
  name?: string;
  provider_type?: string;
  base_url?: string;
  api_key?: string;
  auth_type?: string;
  auth_config?: Record<string, unknown>;
  rate_limit_rpm?: number | null;
  rate_limit_tpm?: number | null;
  model_tier?: ModelTier;
  capabilities?: ProviderCapability[];
}

export interface ProviderListParams {
  is_enabled?: boolean;
  provider_type?: string;
  limit?: number;
  offset?: number;
}

export interface ProviderTestResult {
  success: boolean;
  latency_ms: number;
  error: string | null;
  model_used: string | null;
}

export interface ProviderModelResponse {
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

export interface ProviderModelListResponse {
  data: ProviderModelResponse[];
  total: number;
}

export interface ProviderModelCreateRequest {
  model_name: string;
  display_name?: string;
  context_window?: number;
  max_output_tokens?: number | null;
  prompt_price_per_1k?: number;
  completion_price_per_1k?: number;
  is_enabled?: boolean;
}

export interface ProviderModelUpdateRequest {
  model_name?: string;
  display_name?: string;
  context_window?: number;
  max_output_tokens?: number | null;
  prompt_price_per_1k?: number;
  completion_price_per_1k?: number;
  is_enabled?: boolean;
}

export const providerService = {
  list: (params?: ProviderListParams) =>
    api.get<ProviderListResponse>('/providers', params ? { ...params } as Record<string, string | number | undefined> : undefined),

  get: (id: string) =>
    api.get<ProviderResponse>(`/providers/${id}`),

  create: (data: ProviderCreateRequest) =>
    api.post<ProviderResponse>('/providers', data),

  update: (id: string, data: ProviderUpdateRequest) =>
    api.put<ProviderResponse>(`/providers/${id}`, data),

  delete: (id: string) =>
    api.delete<undefined>(`/providers/${id}`),

  toggle: (id: string, isEnabled: boolean) =>
    api.put<ProviderResponse>(`/providers/${id}/toggle`, { is_enabled: isEnabled }),

  testConnection: (id: string) =>
    api.post<ProviderTestResult>(`/providers/${id}/test`),

  rotateKey: (id: string, data: RotateKeyRequest) =>
    api.post<ProviderResponse>(`/providers/${id}/rotate-key`, data),

  listModels: (providerId: string, isEnabled?: boolean) =>
    api.get<ProviderModelListResponse>(`/providers/${providerId}/models`, isEnabled != null ? { is_enabled: isEnabled } as unknown as Record<string, string | number | undefined> : undefined),

  createModel: (providerId: string, data: ProviderModelCreateRequest) =>
    api.post<ProviderModelResponse>(`/providers/${providerId}/models`, data),

  updateModel: (providerId: string, modelId: string, data: ProviderModelUpdateRequest) =>
    api.put<ProviderModelResponse>(`/providers/${providerId}/models/${modelId}`, data),

  deleteModel: (providerId: string, modelId: string) =>
    api.delete<undefined>(`/providers/${providerId}/models/${modelId}`),

  syncModels: (providerId: string) =>
    api.post<{ synced: number; created: number; updated: number; errors: string[] }>(`/providers/${providerId}/models/sync`),
};
