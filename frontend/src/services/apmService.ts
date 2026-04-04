import { api } from './api';

export interface ApmOverview {
  total_traces: number;
  total_spans: number;
  total_tokens: number;
  total_cost: number;
  avg_duration_ms: number;
  error_rate: number;
}

export interface AgentRankItem {
  agent_name: string;
  call_count: number;
  total_tokens: number;
  total_cost: number;
  avg_duration_ms: number;
  error_count: number;
}

export interface ModelUsageItem {
  model: string;
  call_count: number;
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
  total_cost: number;
}

export interface DailyTrendItem {
  date: string;
  traces: number;
  tokens: number;
  cost: number;
}

export interface ToolUsageItem {
  tool_name: string;
  call_count: number;
  avg_duration_ms: number;
}

export interface ApmDashboardResponse {
  overview: ApmOverview;
  agent_ranking: AgentRankItem[];
  model_usage: ModelUsageItem[];
  daily_trend: DailyTrendItem[];
  tool_usage: ToolUsageItem[];
}

export const apmService = {
  dashboard: (days = 30) =>
    api.get<ApmDashboardResponse>(`/apm/dashboard?days=${days}`),
};
