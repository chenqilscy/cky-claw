import { api } from './api';

export interface AgentLocaleItem {
  id: string;
  locale: string;
  instructions: string;
  is_default: boolean;
  updated_at: string;
}

export interface AgentLocaleListResponse {
  data: AgentLocaleItem[];
}

export interface AgentLocaleCreateParams {
  locale: string;
  instructions: string;
  is_default?: boolean;
}

export interface AgentLocaleUpdateParams {
  instructions: string;
  is_default?: boolean;
}

export const agentLocaleService = {
  async list(agentName: string): Promise<AgentLocaleListResponse> {
    return api.get<AgentLocaleListResponse>(`/agents/${encodeURIComponent(agentName)}/locales`);
  },

  async create(agentName: string, data: AgentLocaleCreateParams): Promise<AgentLocaleItem> {
    return api.post<AgentLocaleItem>(`/agents/${encodeURIComponent(agentName)}/locales`, data);
  },

  async update(agentName: string, locale: string, data: AgentLocaleUpdateParams): Promise<AgentLocaleItem> {
    return api.put<AgentLocaleItem>(
      `/agents/${encodeURIComponent(agentName)}/locales/${encodeURIComponent(locale)}`,
      data,
    );
  },

  async delete(agentName: string, locale: string): Promise<void> {
    await api.delete(`/agents/${encodeURIComponent(agentName)}/locales/${encodeURIComponent(locale)}`);
  },
};
