import { fetchApi } from './api';

export interface A2AAgentCard {
  id: string;
  agent_id: string;
  name: string;
  description: string;
  url: string;
  version: string;
  capabilities: Record<string, unknown>;
  skills: Record<string, unknown>[];
  authentication: Record<string, unknown>;
  metadata_: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface A2ATask {
  id: string;
  agent_card_id: string;
  status: string;
  input_messages: Record<string, unknown>[];
  artifacts: Record<string, unknown>[];
  history: Record<string, unknown>[];
  metadata_: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface A2AAgentCardListResponse {
  data: A2AAgentCard[];
  total: number;
  limit: number;
  offset: number;
}

export interface A2ATaskListResponse {
  data: A2ATask[];
  total: number;
  limit: number;
  offset: number;
}

export const a2aService = {
  async listAgentCards(params?: { limit?: number; offset?: number }): Promise<A2AAgentCardListResponse> {
    const query = new URLSearchParams();
    if (params?.limit) query.set('limit', String(params.limit));
    if (params?.offset) query.set('offset', String(params.offset));
    const qs = query.toString();
    return fetchApi(`/api/v1/a2a/agent-cards${qs ? `?${qs}` : ''}`);
  },

  async createAgentCard(data: { agent_id: string; name: string; url?: string; description?: string }): Promise<A2AAgentCard> {
    return fetchApi('/api/v1/a2a/agent-cards', { method: 'POST', body: JSON.stringify(data) });
  },

  async updateAgentCard(id: string, data: Partial<{ name: string; url: string; description: string }>): Promise<A2AAgentCard> {
    return fetchApi(`/api/v1/a2a/agent-cards/${id}`, { method: 'PUT', body: JSON.stringify(data) });
  },

  async deleteAgentCard(id: string): Promise<void> {
    await fetchApi(`/api/v1/a2a/agent-cards/${id}`, { method: 'DELETE' });
  },

  async discoverAgent(agentId: string): Promise<Record<string, unknown>> {
    return fetchApi(`/api/v1/a2a/discover/${agentId}`);
  },

  async listTasks(params?: { agent_card_id?: string; limit?: number; offset?: number }): Promise<A2ATaskListResponse> {
    const query = new URLSearchParams();
    if (params?.agent_card_id) query.set('agent_card_id', params.agent_card_id);
    if (params?.limit) query.set('limit', String(params.limit));
    if (params?.offset) query.set('offset', String(params.offset));
    const qs = query.toString();
    return fetchApi(`/api/v1/a2a/tasks${qs ? `?${qs}` : ''}`);
  },

  async createTask(data: { agent_card_id: string; input_messages?: Record<string, unknown>[] }): Promise<A2ATask> {
    return fetchApi('/api/v1/a2a/tasks', { method: 'POST', body: JSON.stringify(data) });
  },

  async getTask(taskId: string): Promise<A2ATask> {
    return fetchApi(`/api/v1/a2a/tasks/${taskId}`);
  },

  async cancelTask(taskId: string): Promise<A2ATask> {
    return fetchApi(`/api/v1/a2a/tasks/${taskId}/cancel`, { method: 'POST' });
  },
};
