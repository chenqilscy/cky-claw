import { api } from './api';

export interface SupervisionSessionItem {
  session_id: string;
  agent_name: string;
  status: string;
  title: string;
  token_used: number;
  call_count: number;
  created_at: string;
  updated_at: string;
}

export interface SupervisionSessionListResponse {
  data: SupervisionSessionItem[];
  total: number;
}

export interface MessageItem {
  role: string;
  content: string;
  timestamp: string | null;
}

export interface SupervisionSessionDetail extends SupervisionSessionItem {
  messages: MessageItem[];
  metadata: Record<string, unknown>;
}

export interface SupervisionActionResponse {
  session_id: string;
  status: string;
  message: string;
}

export interface SupervisionListParams {
  agent_name?: string;
  status?: string;
}

export const supervisionService = {
  listSessions: (params?: SupervisionListParams) =>
    api.get<SupervisionSessionListResponse>('/supervision/sessions', params ? { ...params } : undefined),

  getSessionDetail: (sessionId: string) =>
    api.get<SupervisionSessionDetail>(`/supervision/sessions/${sessionId}`),

  pauseSession: (sessionId: string, reason?: string) =>
    api.post<SupervisionActionResponse>(`/supervision/sessions/${sessionId}/pause`, reason ? { reason } : undefined),

  resumeSession: (sessionId: string, injectedInstructions?: string) =>
    api.post<SupervisionActionResponse>(
      `/supervision/sessions/${sessionId}/resume`,
      injectedInstructions ? { injected_instructions: injectedInstructions } : undefined,
    ),
};
