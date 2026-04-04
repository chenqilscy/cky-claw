import { api } from './api';

export interface TeamConfig {
  id: string;
  name: string;
  description: string;
  protocol: string;
  member_agent_ids: string[];
  coordinator_agent_id: string | null;
  config: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface TeamConfigListResponse {
  data: TeamConfig[];
  total: number;
}

export interface TeamConfigCreate {
  name: string;
  description?: string;
  protocol?: string;
  member_agent_ids?: string[];
  coordinator_agent_id?: string | null;
  config?: Record<string, unknown>;
}

export interface TeamConfigUpdate {
  name?: string;
  description?: string;
  protocol?: string;
  member_agent_ids?: string[];
  coordinator_agent_id?: string | null;
  config?: Record<string, unknown>;
}

export async function listTeams(params?: {
  limit?: number;
  offset?: number;
  search?: string;
}): Promise<TeamConfigListResponse> {
  return api.get<TeamConfigListResponse>('/api/v1/teams', params as Record<string, string | number | undefined>);
}

export async function getTeam(id: string): Promise<TeamConfig> {
  return api.get<TeamConfig>(`/api/v1/teams/${id}`);
}

export async function createTeam(data: TeamConfigCreate): Promise<TeamConfig> {
  return api.post<TeamConfig>('/api/v1/teams', data);
}

export async function updateTeam(id: string, data: TeamConfigUpdate): Promise<TeamConfig> {
  return api.put<TeamConfig>(`/api/v1/teams/${id}`, data);
}

export async function deleteTeam(id: string): Promise<void> {
  await api.delete(`/api/v1/teams/${id}`);
}
