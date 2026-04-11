import { api } from './api';

export interface MemoryItem {
  id: string;
  user_id: string;
  type: string;
  content: string;
  confidence: number;
  agent_name: string | null;
  source_session_id: string | null;
  metadata: Record<string, unknown>;
  tags: string[];
  access_count: number;
  embedding: number[] | null;
  created_at: string;
  updated_at: string;
}

export interface MemoryListResponse {
  data: MemoryItem[];
  total: number;
}

export interface MemoryCreateParams {
  type: string;
  content: string;
  confidence?: number;
  user_id: string;
  agent_name?: string;
  source_session_id?: string;
  metadata?: Record<string, unknown>;
  tags?: string[];
}

export interface MemoryUpdateParams {
  content?: string;
  confidence?: number;
  type?: string;
  metadata?: Record<string, unknown>;
  tags?: string[];
}

export interface MemoryTagSearchParams {
  user_id: string;
  tags: string[];
  limit?: number;
}

export interface MemoryCountResponse {
  user_id: string;
  count: number;
}

export interface MemorySearchParams {
  user_id: string;
  query: string;
  limit?: number;
}

export interface MemoryDecayParams {
  before: string;
  rate: number;
}

export const memoryService = {
  async list(params?: Record<string, string | number | undefined>): Promise<MemoryListResponse> {
    const cleanParams: Record<string, string | number | undefined> = {};
    if (params) {
      Object.entries(params).forEach(([k, v]) => {
        if (v !== undefined && v !== '') cleanParams[k] = v as string | number;
      });
    }
    return api.get<MemoryListResponse>('/memories', cleanParams);
  },

  async get(id: string): Promise<MemoryItem> {
    return api.get<MemoryItem>(`/memories/${id}`);
  },

  async create(data: MemoryCreateParams): Promise<MemoryItem> {
    return api.post<MemoryItem>('/memories', data);
  },

  async update(id: string, data: MemoryUpdateParams): Promise<MemoryItem> {
    return api.put<MemoryItem>(`/memories/${id}`, data);
  },

  async delete(id: string): Promise<void> {
    await api.delete(`/memories/${id}`);
  },

  async deleteByUser(userId: string): Promise<{ deleted: number }> {
    return api.delete<{ deleted: number }>(`/memories/user/${userId}`);
  },

  async search(data: MemorySearchParams): Promise<MemoryItem[]> {
    return api.post<MemoryItem[]>('/memories/search', data);
  },

  async decay(data: MemoryDecayParams): Promise<{ affected: number }> {
    return api.post<{ affected: number }>('/memories/decay', data);
  },

  async searchByTags(data: MemoryTagSearchParams): Promise<MemoryItem[]> {
    return api.post<MemoryItem[]>('/memories/search-by-tags', data);
  },

  async count(userId: string): Promise<MemoryCountResponse> {
    return api.get<MemoryCountResponse>(`/memories/count/${userId}`);
  },
};
