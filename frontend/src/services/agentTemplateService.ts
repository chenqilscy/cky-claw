import { api } from './api';

export interface AgentTemplateItem {
  id: string;
  name: string;
  display_name: string;
  description: string;
  category: string;
  icon: string;
  config: Record<string, unknown>;
  is_builtin: boolean;
  metadata: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface AgentTemplateListResponse {
  data: AgentTemplateItem[];
  total: number;
}

export interface AgentTemplateCreateParams {
  name: string;
  display_name: string;
  description?: string;
  category?: string;
  icon?: string;
  config?: Record<string, unknown>;
  metadata?: Record<string, unknown>;
}

export interface AgentTemplateUpdateParams {
  display_name?: string;
  description?: string;
  category?: string;
  icon?: string;
  config?: Record<string, unknown>;
  metadata?: Record<string, unknown>;
}

export interface TemplateInstantiateResult {
  template_name: string;
  display_name: string;
  description: string;
  category: string;
  config: Record<string, unknown>;
}

export const agentTemplateService = {
  async list(params?: Record<string, string | number | boolean | undefined>): Promise<AgentTemplateListResponse> {
    const cleanParams: Record<string, string | number | undefined> = {};
    if (params) {
      Object.entries(params).forEach(([k, v]) => {
        if (v !== undefined && v !== '') cleanParams[k] = v as string | number;
      });
    }
    return api.get<AgentTemplateListResponse>('/agent-templates', cleanParams);
  },

  async get(id: string): Promise<AgentTemplateItem> {
    return api.get<AgentTemplateItem>(`/agent-templates/${id}`);
  },

  async create(data: AgentTemplateCreateParams): Promise<AgentTemplateItem> {
    return api.post<AgentTemplateItem>('/agent-templates', data);
  },

  async update(id: string, data: AgentTemplateUpdateParams): Promise<AgentTemplateItem> {
    return api.put<AgentTemplateItem>(`/agent-templates/${id}`, data);
  },

  async delete(id: string): Promise<void> {
    await api.delete(`/agent-templates/${id}`);
  },

  async seedBuiltin(): Promise<{ created: number }> {
    return api.post<{ created: number }>('/agent-templates/seed', {});
  },

  async instantiate(
    id: string,
    overrides?: Record<string, unknown> | null,
  ): Promise<TemplateInstantiateResult> {
    return api.post<TemplateInstantiateResult>(
      `/agent-templates/${id}/instantiate`,
      overrides ?? null,
    );
  },
};
