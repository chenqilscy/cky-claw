import { api } from './api';

export interface DebugSession {
  id: string;
  agent_id: string;
  agent_name: string;
  user_id: string;
  state: string;
  mode: string;
  input_message: string;
  current_turn: number;
  current_agent_name: string;
  pause_context: Record<string, unknown>;
  token_usage: Record<string, number>;
  result: string | null;
  error: string | null;
  created_at: string;
  updated_at: string;
  finished_at: string | null;
}

export interface DebugSessionListResponse {
  items: DebugSession[];
  total: number;
}

export interface DebugSessionCreateInput {
  agent_id: string;
  input_message: string;
  mode?: string;
}

export interface DebugContext {
  turn: number;
  agent_name: string;
  reason: string;
  recent_messages: Record<string, unknown>[];
  last_llm_response: Record<string, unknown> | null;
  last_tool_calls: Record<string, unknown>[] | null;
  token_usage: Record<string, number>;
  paused_at: string | null;
}

export const debugService = {
  /** 获取调试会话列表 */
  list(params?: { state?: string; limit?: number; offset?: number }): Promise<DebugSessionListResponse> {
    return api.get<DebugSessionListResponse>('/debug/sessions', params);
  },

  /** 获取调试会话详情 */
  get(id: string): Promise<DebugSession> {
    return api.get<DebugSession>(`/debug/sessions/${id}`);
  },

  /** 创建调试会话 */
  create(input: DebugSessionCreateInput): Promise<DebugSession> {
    return api.post<DebugSession>('/debug/sessions', input);
  },

  /** 单步执行 */
  step(id: string): Promise<DebugSession> {
    return api.post<DebugSession>(`/debug/sessions/${id}/step`);
  },

  /** 继续执行 */
  continue(id: string): Promise<DebugSession> {
    return api.post<DebugSession>(`/debug/sessions/${id}/continue`);
  },

  /** 终止会话 */
  stop(id: string): Promise<DebugSession> {
    return api.post<DebugSession>(`/debug/sessions/${id}/stop`);
  },

  /** 获取暂停上下文 */
  getContext(id: string): Promise<DebugContext> {
    return api.get<DebugContext>(`/debug/sessions/${id}/context`);
  },
};
