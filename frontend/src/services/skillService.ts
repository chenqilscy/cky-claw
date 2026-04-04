import { api } from './api';

export interface SkillItem {
  id: string;
  name: string;
  version: string;
  description: string;
  content: string;
  category: string;
  tags: string[];
  applicable_agents: string[];
  author: string;
  metadata: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface SkillListResponse {
  items: SkillItem[];
  total: number;
}

export interface SkillCreateParams {
  name: string;
  version?: string;
  description?: string;
  content: string;
  category?: string;
  tags?: string[];
  applicable_agents?: string[];
  author?: string;
  metadata?: Record<string, unknown>;
}

export interface SkillUpdateParams {
  version?: string;
  description?: string;
  content?: string;
  category?: string;
  tags?: string[];
  applicable_agents?: string[];
  author?: string;
  metadata?: Record<string, unknown>;
}

export interface SkillSearchParams {
  query: string;
  category?: string;
  limit?: number;
}

export const skillService = {
  async list(params?: Record<string, string | number | undefined>): Promise<SkillListResponse> {
    const cleanParams: Record<string, string | number | undefined> = {};
    if (params) {
      Object.entries(params).forEach(([k, v]) => {
        if (v !== undefined && v !== '') cleanParams[k] = v as string | number;
      });
    }
    return api.get<SkillListResponse>('/skills', cleanParams);
  },

  async get(id: string): Promise<SkillItem> {
    return api.get<SkillItem>(`/skills/${id}`);
  },

  async create(data: SkillCreateParams): Promise<SkillItem> {
    return api.post<SkillItem>('/skills', data);
  },

  async update(id: string, data: SkillUpdateParams): Promise<SkillItem> {
    return api.put<SkillItem>(`/skills/${id}`, data);
  },

  async delete(id: string): Promise<void> {
    await api.delete(`/skills/${id}`);
  },

  async search(data: SkillSearchParams): Promise<SkillItem[]> {
    return api.post<SkillItem[]>('/skills/search', data);
  },

  async findForAgent(agentName: string): Promise<SkillItem[]> {
    return api.get<SkillItem[]>(`/skills/for-agent/${encodeURIComponent(agentName)}`);
  },
};
