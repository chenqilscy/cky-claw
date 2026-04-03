import { api } from './api';

export interface AgentConfig {
  id: string;
  name: string;
  description: string;
  instructions: string;
  model: string;
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
};
