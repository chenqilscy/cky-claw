import { api } from './api';

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
    return api.get<A2AAgentCardListResponse>('/a2a/agent-cards', params as Record<string, string | number | undefined>);
  },

  async createAgentCard(data: { agent_id: string; name: string; url?: string; description?: string }): Promise<A2AAgentCard> {
    return api.post<A2AAgentCard>('/a2a/agent-cards', data);
  },

  async updateAgentCard(id: string, data: Partial<{ name: string; url: string; description: string }>): Promise<A2AAgentCard> {
    return api.put<A2AAgentCard>(`/a2a/agent-cards/${id}`, data);
  },

  async deleteAgentCard(id: string): Promise<void> {
    await api.delete(`/a2a/agent-cards/${id}`);
  },

  async discoverAgent(agentId: string): Promise<Record<string, unknown>> {
    return api.get<Record<string, unknown>>(`/a2a/discover/${agentId}`);
  },

  async listTasks(params?: { agent_card_id?: string; limit?: number; offset?: number }): Promise<A2ATaskListResponse> {
    return api.get<A2ATaskListResponse>('/a2a/tasks', params as Record<string, string | number | undefined>);
  },

  async createTask(data: { agent_card_id: string; input_messages?: Record<string, unknown>[] }): Promise<A2ATask> {
    return api.post<A2ATask>('/a2a/tasks', data);
  },

  async getTask(taskId: string): Promise<A2ATask> {
    return api.get<A2ATask>(`/a2a/tasks/${taskId}`);
  },

  async cancelTask(taskId: string): Promise<A2ATask> {
    return api.post<A2ATask>(`/a2a/tasks/${taskId}/cancel`);
  },
};
