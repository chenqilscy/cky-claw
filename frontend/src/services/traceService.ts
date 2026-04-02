import { api } from './api';

export interface TraceItem {
  id: string;
  workflow_name: string;
  group_id: string | null;
  session_id: string | null;
  agent_name: string | null;
  status: string;
  span_count: number;
  start_time: string;
  end_time: string | null;
  metadata: Record<string, unknown>;
  created_at: string;
}

export interface SpanItem {
  id: string;
  trace_id: string;
  parent_span_id: string | null;
  type: string;
  name: string;
  status: string;
  start_time: string;
  end_time: string | null;
  input: Record<string, unknown> | null;
  output: Record<string, unknown> | null;
  metadata: Record<string, unknown>;
  model: string | null;
  token_usage: { prompt_tokens: number; completion_tokens: number; total_tokens: number } | null;
  created_at: string;
}

export interface TraceListResponse {
  items: TraceItem[];
  total: number;
}

export interface TraceDetailResponse {
  trace: TraceItem;
  spans: SpanItem[];
}

export interface TraceListParams {
  session_id?: string;
  agent_name?: string;
  workflow_name?: string;
  start_time?: string;
  end_time?: string;
  limit?: number;
  offset?: number;
}

export const traceService = {
  list: (params?: TraceListParams) =>
    api.get<TraceListResponse>('/traces', params as Record<string, string | number | undefined>),

  detail: (traceId: string) =>
    api.get<TraceDetailResponse>(`/traces/${traceId}`),
};
