import { api } from './api';

export interface AgentVersion {
  id: string;
  agent_config_id: string;
  version: number;
  snapshot: Record<string, unknown>;
  change_summary: string | null;
  created_by: string | null;
  created_at: string;
}

export interface AgentVersionListResponse {
  data: AgentVersion[];
  total: number;
}

export interface AgentVersionDiffResponse {
  version_a: number;
  version_b: number;
  snapshot_a: Record<string, unknown>;
  snapshot_b: Record<string, unknown>;
}

export const agentVersionService = {
  list: (agentId: string, params?: { limit?: number; offset?: number }) =>
    api.get<AgentVersionListResponse>(`/agents/${agentId}/versions`, params),

  get: (agentId: string, version: number) =>
    api.get<AgentVersion>(`/agents/${agentId}/versions/${version}`),

  rollback: (agentId: string, version: number, changeSummary?: string) =>
    api.post<AgentVersion>(`/agents/${agentId}/versions/${version}/rollback`,
      changeSummary ? { change_summary: changeSummary } : undefined,
    ),

  diff: (agentId: string, v1: number, v2: number) =>
    api.get<AgentVersionDiffResponse>(`/agents/${agentId}/versions/diff`, { v1, v2 }),
};
