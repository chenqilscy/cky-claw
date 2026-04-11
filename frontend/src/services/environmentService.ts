import { api } from './api';

export interface Environment {
  id: string;
  name: string;
  display_name: string;
  description: string;
  color: string;
  sort_order: number;
  is_protected: boolean;
  settings_override: Record<string, unknown>;
  org_id: string | null;
  created_at: string;
  updated_at: string;
}

export interface EnvironmentListResponse {
  data: Environment[];
  total: number;
}

export interface EnvironmentCreateInput {
  name: string;
  display_name: string;
  description?: string;
  color?: string;
  sort_order?: number;
  is_protected?: boolean;
  settings_override?: Record<string, unknown>;
}

export interface EnvironmentUpdateInput {
  display_name?: string;
  description?: string;
  color?: string;
  sort_order?: number;
  is_protected?: boolean;
  settings_override?: Record<string, unknown>;
}

export interface PublishRequest {
  version_id?: string;
  notes?: string;
}

export interface RollbackRequest {
  target_version_id?: string;
  notes?: string;
}

export interface BindingResponse {
  id: string;
  agent_config_id: string;
  environment_id: string;
  version_id: string;
  is_active: boolean;
  published_at: string;
  published_by: string | null;
  rollback_from_id: string | null;
  notes: string;
  org_id: string | null;
}

export interface EnvironmentAgentsResponse {
  environment: string;
  data: BindingResponse[];
}

export interface EnvironmentDiffResponse {
  agent_name: string;
  env1: string;
  env2: string;
  snapshot_env1: Record<string, unknown>;
  snapshot_env2: Record<string, unknown>;
}

export const environmentService = {
  /** 获取环境列表 */
  list: () =>
    api.get<EnvironmentListResponse>('/environments'),

  /** 获取环境详情 */
  get: (envName: string) =>
    api.get<Environment>(`/environments/${encodeURIComponent(envName)}`),

  /** 创建环境 */
  create: (data: EnvironmentCreateInput) =>
    api.post<Environment>('/environments', data),

  /** 更新环境 */
  update: (envName: string, data: EnvironmentUpdateInput) =>
    api.put<Environment>(`/environments/${encodeURIComponent(envName)}`, data),

  /** 删除环境 */
  delete: (envName: string) =>
    api.delete<{ message: string }>(`/environments/${encodeURIComponent(envName)}`),

  /** 发布 Agent 到环境 */
  publishAgent: (envName: string, agentName: string, data: PublishRequest) =>
    api.post<BindingResponse>(
      `/environments/${encodeURIComponent(envName)}/agents/${encodeURIComponent(agentName)}/publish`,
      data,
    ),

  /** 回滚环境中的 Agent */
  rollbackAgent: (envName: string, agentName: string, data: RollbackRequest) =>
    api.post<BindingResponse>(
      `/environments/${encodeURIComponent(envName)}/agents/${encodeURIComponent(agentName)}/rollback`,
      data,
    ),

  /** 获取环境内已发布 Agent 列表 */
  listAgents: (envName: string) =>
    api.get<EnvironmentAgentsResponse>(`/environments/${encodeURIComponent(envName)}/agents`),

  /** 环境间差异对比 */
  diff: (agentName: string, env1: string, env2: string) =>
    api.get<EnvironmentDiffResponse>('/environments/diff', { agent: agentName, env1, env2 }),
};
