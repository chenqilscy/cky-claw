import { api } from './api';

export const TRANSPORT_TYPES = ['stdio', 'sse', 'http'] as const;
export type TransportType = typeof TRANSPORT_TYPES[number];

export interface MCPServerResponse {
  id: string;
  name: string;
  description: string;
  transport_type: TransportType;
  command: string | null;
  url: string | null;
  env: Record<string, string>;
  auth_config: Record<string, unknown> | null;
  is_enabled: boolean;
  org_id: string | null;
  created_at: string;
  updated_at: string;
}

export interface MCPServerListResponse {
  items: MCPServerResponse[];
  total: number;
}

export interface MCPServerCreateRequest {
  name: string;
  description?: string;
  transport_type: TransportType;
  command?: string;
  url?: string;
  env?: Record<string, string>;
  auth_config?: Record<string, unknown>;
  is_enabled?: boolean;
}

export interface MCPServerUpdateRequest {
  description?: string;
  transport_type?: TransportType;
  command?: string | null;
  url?: string | null;
  env?: Record<string, string>;
  auth_config?: Record<string, unknown>;
  is_enabled?: boolean;
}

export interface MCPServerListParams {
  transport_type?: string;
  is_enabled?: boolean;
  limit?: number;
  offset?: number;
}

export const mcpServerService = {
  async list(params?: MCPServerListParams): Promise<MCPServerListResponse> {
    const cleanParams: Record<string, string | number | undefined> = {};
    if (params) {
      Object.entries(params).forEach(([k, v]) => {
        if (v !== undefined && v !== '') cleanParams[k] = typeof v === 'boolean' ? String(v) : v as string | number;
      });
    }
    return api.get<MCPServerListResponse>('/mcp/servers', cleanParams);
  },

  async get(id: string): Promise<MCPServerResponse> {
    return api.get<MCPServerResponse>(`/mcp/servers/${id}`);
  },

  async create(data: MCPServerCreateRequest): Promise<MCPServerResponse> {
    return api.post<MCPServerResponse>('/mcp/servers', data);
  },

  async update(id: string, data: MCPServerUpdateRequest): Promise<MCPServerResponse> {
    return api.put<MCPServerResponse>(`/mcp/servers/${id}`, data);
  },

  async delete(id: string): Promise<void> {
    await api.delete(`/mcp/servers/${id}`);
  },
};
