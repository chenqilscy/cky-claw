import { api } from './api';

export interface GuardrailRuleItem {
  id: string;
  name: string;
  description: string;
  type: string;
  mode: string;
  config: Record<string, unknown>;
  is_enabled: boolean;
  created_at: string;
  updated_at: string;
}

export interface GuardrailRuleListResponse {
  data: GuardrailRuleItem[];
  total: number;
}

export interface GuardrailRuleCreateParams {
  name: string;
  description?: string;
  type: string;
  mode: string;
  config: Record<string, unknown>;
}

export interface GuardrailRuleUpdateParams {
  description?: string;
  type?: string;
  mode?: string;
  config?: Record<string, unknown>;
  is_enabled?: boolean;
}

export const guardrailService = {
  async list(params?: Record<string, string | number | boolean | undefined>): Promise<GuardrailRuleListResponse> {
    const cleanParams: Record<string, string | number | undefined> = {};
    if (params) {
      Object.entries(params).forEach(([k, v]) => {
        if (v !== undefined && v !== '') cleanParams[k] = typeof v === 'boolean' ? String(v) : v as string | number;
      });
    }
    return api.get<GuardrailRuleListResponse>('/guardrails', cleanParams);
  },

  async get(id: string): Promise<GuardrailRuleItem> {
    return api.get<GuardrailRuleItem>(`/guardrails/${id}`);
  },

  async create(data: GuardrailRuleCreateParams): Promise<GuardrailRuleItem> {
    return api.post<GuardrailRuleItem>('/guardrails', data);
  },

  async update(id: string, data: GuardrailRuleUpdateParams): Promise<GuardrailRuleItem> {
    return api.put<GuardrailRuleItem>(`/guardrails/${id}`, data);
  },

  async delete(id: string): Promise<void> {
    await api.delete(`/guardrails/${id}`);
  },
};
