import { api, API_BASE, getToken } from './api';

export interface ChatSession {
  id: string;
  agent_name: string;
  status: string;
  title: string;
  metadata: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface SessionListResponse {
  data: ChatSession[];
  total: number;
  limit: number;
  offset: number;
}

export interface RunResponse {
  run_id: string;
  status: string;
  output: string;
  token_usage: {
    prompt_tokens: number;
    completion_tokens: number;
    total_tokens: number;
  };
  duration_ms: number;
  turn_count: number;
  last_agent_name: string;
}

export interface SSEEvent {
  type: string;
  data: Record<string, unknown>;
}

export const chatService = {
  createSession: (agentName: string, metadata?: Record<string, unknown>) =>
    api.post<ChatSession>('/sessions', { agent_name: agentName, metadata }),

  listSessions: (params?: { agent_name?: string; limit?: number; offset?: number }) =>
    api.get<SessionListResponse>('/sessions', params),

  getSession: (sessionId: string) =>
    api.get<ChatSession>(`/sessions/${sessionId}`),

  deleteSession: (sessionId: string) =>
    api.delete<undefined>(`/sessions/${sessionId}`),

  runNonStream: (sessionId: string, input: string) =>
    api.post<RunResponse>(`/sessions/${sessionId}/run`, {
      input,
      config: { stream: false },
    }),

  /**
   * 发起 SSE 流式请求。返回 EventSource 对象。
   * 调用方负责监听事件和关闭连接。
   */
  runStream: (
    sessionId: string,
    input: string,
    onEvent: (event: SSEEvent) => void,
    onError?: (err: Event) => void,
    onDone?: () => void,
  ): AbortController => {
    const controller = new AbortController();
    const url = `${API_BASE}/sessions/${sessionId}/run`;
    const token = getToken();

    fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { 'Authorization': `Bearer ${token}` } : {}),
      },
      body: JSON.stringify({ input, config: { stream: true } }),
      signal: controller.signal,
    })
      .then(async (response) => {
        if (!response.ok || !response.body) {
          onError?.(new Event('error'));
          return;
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split('\n');
          buffer = lines.pop() || '';

          let currentEventType = '';
          for (const line of lines) {
            if (line.startsWith('event: ')) {
              currentEventType = line.slice(7).trim();
            } else if (line.startsWith('data: ')) {
              const dataStr = line.slice(6);
              try {
                const data = JSON.parse(dataStr);
                onEvent({ type: currentEventType || 'message', data });
              } catch {
                // skip malformed data
              }
            }
          }
        }

        onDone?.();
      })
      .catch((err) => {
        if (err.name !== 'AbortError') {
          onError?.(err);
        }
      });

    return controller;
  },
};
