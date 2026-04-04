import { api } from './api';

export interface ToolDefinition {
  name: string;
  description: string;
  parameters_schema: Record<string, unknown>;
}

export interface ToolGroupResponse {
  id: string;
  name: string;
  description: string;
  tools: ToolDefinition[];
  conditions: Record<string, unknown>;
  source: string;
  is_enabled: boolean;
  created_at: string;
  updated_at: string;
}

export interface ToolGroupListResponse {
  data: ToolGroupResponse[];
  total: number;
}

export interface ToolGroupCreateRequest {
  name: string;
  description?: string;
  tools?: ToolDefinition[];
  conditions?: Record<string, unknown>;
}

export interface ToolGroupUpdateRequest {
  description?: string;
  tools?: ToolDefinition[];
  conditions?: Record<string, unknown>;
  is_enabled?: boolean;
}

export const toolGroupService = {
  async list(): Promise<ToolGroupListResponse> {
    return api.get<ToolGroupListResponse>('/tool-groups');
  },

  async get(name: string): Promise<ToolGroupResponse> {
    return api.get<ToolGroupResponse>(`/tool-groups/${name}`);
  },

  async create(data: ToolGroupCreateRequest): Promise<ToolGroupResponse> {
    return api.post<ToolGroupResponse>('/tool-groups', data);
  },

  async update(name: string, data: ToolGroupUpdateRequest): Promise<ToolGroupResponse> {
    return api.put<ToolGroupResponse>(`/tool-groups/${name}`, data);
  },

  async delete(name: string): Promise<void> {
    await api.delete(`/tool-groups/${name}`);
  },
};
