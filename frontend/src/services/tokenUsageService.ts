import { api } from './api';

export interface TokenUsageLog {
  id: string;
  trace_id: string;
  span_id: string;
  session_id: string | null;
  user_id: string | null;
  agent_name: string;
  model: string;
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
  timestamp: string;
}

export interface TokenUsageListResponse {
  data: TokenUsageLog[];
  total: number;
  limit: number;
  offset: number;
}

export interface TokenUsageSummaryItem {
  agent_name: string;
  model: string;
  total_prompt_tokens: number;
  total_completion_tokens: number;
  total_tokens: number;
  call_count: number;
}

export interface TokenUsageByUserItem {
  user_id: string | null;
  total_prompt_tokens: number;
  total_completion_tokens: number;
  total_tokens: number;
  call_count: number;
}

export interface TokenUsageByModelItem {
  model: string;
  total_prompt_tokens: number;
  total_completion_tokens: number;
  total_tokens: number;
  call_count: number;
}

export type SummaryGroupBy = 'agent_model' | 'user' | 'model';

export interface TokenUsageSummaryResponse {
  data: (TokenUsageSummaryItem | TokenUsageByUserItem | TokenUsageByModelItem)[];
}

export interface TokenUsageListParams {
  agent_name?: string;
  session_id?: string;
  user_id?: string;
  model?: string;
  start_time?: string;
  end_time?: string;
  limit?: number;
  offset?: number;
}

export interface TokenUsageSummaryParams {
  agent_name?: string;
  user_id?: string;
  model?: string;
  start_time?: string;
  end_time?: string;
  group_by?: SummaryGroupBy;
}

export const tokenUsageService = {
  list: (params?: TokenUsageListParams) =>
    api.get<TokenUsageListResponse>('/token-usage', params ? { ...params } : undefined),

  summary: (params?: TokenUsageSummaryParams) =>
    api.get<TokenUsageSummaryResponse>('/token-usage/summary', params ? { ...params } : undefined),
};
