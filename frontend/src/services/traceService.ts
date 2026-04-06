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
  duration_ms: number | null;
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
  duration_ms: number | null;
  input: Record<string, unknown> | null;
  output: Record<string, unknown> | null;
  metadata: Record<string, unknown>;
  model: string | null;
  token_usage: { prompt_tokens: number; completion_tokens: number; total_tokens: number } | null;
  created_at: string;
}

export interface TraceListResponse {
  data: TraceItem[];
  total: number;
}

export interface TraceDetailResponse {
  trace: TraceItem;
  spans: SpanItem[];
}

export interface SpanListResponse {
  data: SpanItem[];
  total: number;
}

export interface TokenUsageStats {
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
}

export interface SpanTypeCount {
  agent: number;
  llm: number;
  tool: number;
  handoff: number;
  guardrail: number;
}

export interface GuardrailStats {
  total: number;
  triggered: number;
  trigger_rate: number;
}

export interface TraceStatsResponse {
  total_traces: number;
  total_spans: number;
  avg_duration_ms: number | null;
  total_tokens: TokenUsageStats;
  span_type_counts: SpanTypeCount;
  guardrail_stats: GuardrailStats;
  error_rate: number;
}

export interface TraceListParams {
  session_id?: string;
  agent_name?: string;
  workflow_name?: string;
  status?: string;
  start_time?: string;
  end_time?: string;
  min_duration_ms?: number;
  max_duration_ms?: number;
  has_guardrail_triggered?: boolean;
  limit?: number;
  offset?: number;
}

export interface SpanListParams {
  trace_id?: string;
  type?: string;
  status?: string;
  name?: string;
  min_duration_ms?: number;
  limit?: number;
  offset?: number;
}

export interface FlameNode {
  span_id: string;
  parent_span_id: string | null;
  type: string;
  name: string;
  status: string;
  start_time: string | null;
  end_time: string | null;
  duration_ms: number | null;
  model: string | null;
  children: FlameNode[];
}

export interface FlameTreeResponse {
  trace_id: string;
  root: FlameNode | FlameNode[] | null;
  total_spans: number;
}

export interface ReplayEvent {
  span_id: string;
  parent_span_id: string | null;
  type: string;
  name: string;
  status: string;
  offset_ms: number;
  duration_ms: number | null;
  start_time: string | null;
  end_time: string | null;
  model: string | null;
  input_summary: string | null;
  output_summary: string | null;
}

export interface ReplayTimelineResponse {
  trace_id: string;
  timeline: ReplayEvent[];
  total_duration_ms: number;
}

export const traceService = {
  list: (params?: TraceListParams) =>
    api.get<TraceListResponse>('/traces', params as Record<string, string | number | undefined>),

  detail: (traceId: string) =>
    api.get<TraceDetailResponse>(`/traces/${traceId}`),

  stats: (params?: Partial<TraceListParams>) =>
    api.get<TraceStatsResponse>('/traces/stats', params as Record<string, string | number | undefined>),

  listSpans: (params?: SpanListParams) =>
    api.get<SpanListResponse>('/traces/spans', params as Record<string, string | number | undefined>),

  flame: (traceId: string, maxDepth = 50) =>
    api.get<FlameTreeResponse>(`/traces/${traceId}/flame`, { max_depth: maxDepth }),

  replay: (traceId: string) =>
    api.get<ReplayTimelineResponse>(`/traces/${traceId}/replay`),
};
