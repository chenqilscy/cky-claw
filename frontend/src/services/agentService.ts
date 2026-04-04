import { api, getToken, API_BASE } from './api';

export interface AgentConfig {
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
  output_type: Record<string, unknown> | null;
  metadata: Record<string, unknown>;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface AgentListResponse {
  data: AgentConfig[];
  total: number;
  limit: number;
  offset: number;
}

export interface AgentCreateInput {
  name: string;
  description?: string;
  instructions?: string;
  model?: string;
  provider_name?: string | null;
  model_settings?: Record<string, unknown>;
  tool_groups?: string[];
  handoffs?: string[];
  guardrails?: {
    input?: string[];
    output?: string[];
    tool?: string[];
  };
  approval_mode?: string;
  mcp_servers?: string[];
  agent_tools?: string[];
  skills?: string[];
  output_type?: Record<string, unknown> | null;
  metadata?: Record<string, unknown>;
}

export type AgentUpdateInput = Partial<AgentCreateInput>;

export const agentService = {
  list: (params?: { search?: string; limit?: number; offset?: number }) =>
    api.get<AgentListResponse>('/agents', params),

  get: (name: string) =>
    api.get<AgentConfig>(`/agents/${encodeURIComponent(name)}`),

  create: (data: AgentCreateInput) =>
    api.post<AgentConfig>('/agents', data),

  update: (name: string, data: AgentUpdateInput) =>
    api.put<AgentConfig>(`/agents/${encodeURIComponent(name)}`, data),

  delete: (name: string) =>
    api.delete<undefined>(`/agents/${encodeURIComponent(name)}`),

  exportAgent: async (name: string, format: 'yaml' | 'json' = 'yaml'): Promise<void> => {
    const token = getToken();
    const resp = await fetch(
      `${API_BASE}/agents/${encodeURIComponent(name)}/export?format=${format}`,
      { headers: token ? { Authorization: `Bearer ${token}` } : {} },
    );
    if (!resp.ok) throw new Error(`导出失败: ${resp.status}`);
    const blob = await resp.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${name}.${format}`;
    a.click();
    URL.revokeObjectURL(url);
  },

  importAgent: async (file: File): Promise<AgentConfig> => {
    const token = getToken();
    const form = new FormData();
    form.append('file', file);
    const resp = await fetch(`${API_BASE}/agents/import`, {
      method: 'POST',
      headers: token ? { Authorization: `Bearer ${token}` } : {},
      body: form,
    });
    if (!resp.ok) {
      const err = await resp.json().catch(() => ({}));
      throw new Error(err.detail || `导入失败: ${resp.status}`);
    }
    return resp.json();
  },
};
