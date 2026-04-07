import { api } from './api';

export const PROVIDER_TYPES = [
  'openai', 'anthropic', 'azure', 'deepseek', 'qwen',
  'doubao', 'zhipu', 'moonshot', 'minimax', 'custom',
] as const;

export const AUTH_TYPES = ['api_key', 'azure_ad', 'custom_header'] as const;

export type ProviderType = typeof PROVIDER_TYPES[number];
export type AuthType = typeof AUTH_TYPES[number];

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
};
