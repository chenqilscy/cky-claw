import { api } from './api';

export interface RunEvaluation {
  id: string;
  run_id: string;
  agent_id: string | null;
  accuracy: number;
  relevance: number;
  coherence: number;
  helpfulness: number;
  safety: number;
  efficiency: number;
  tool_usage: number;
  overall_score: number;
  eval_method: string;
  evaluator: string;
  comment: string;
  created_at: string;
}

export interface RunEvaluationListResponse {
  data: RunEvaluation[];
  total: number;
  limit: number;
  offset: number;
}

export interface RunEvaluationCreate {
  run_id: string;
  agent_id?: string | null;
  accuracy?: number;
  relevance?: number;
  coherence?: number;
  helpfulness?: number;
  safety?: number;
  efficiency?: number;
  tool_usage?: number;
  eval_method?: string;
  evaluator?: string;
  comment?: string;
  metadata?: Record<string, unknown>;
}

export interface RunFeedback {
  id: string;
  run_id: string;
  user_id: string | null;
  rating: number;
  comment: string;
  tags: string[];
  created_at: string;
}

export interface RunFeedbackListResponse {
  data: RunFeedback[];
  total: number;
  limit: number;
  offset: number;
}

export interface RunFeedbackCreate {
  run_id: string;
  rating: number;
  comment?: string;
  tags?: string[];
}

export interface AgentQualitySummary {
  agent_id: string;
  eval_count: number;
  avg_accuracy: number;
  avg_relevance: number;
  avg_coherence: number;
  avg_helpfulness: number;
  avg_safety: number;
  avg_efficiency: number;
  avg_tool_usage: number;
  avg_overall: number;
  feedback_count: number;
  positive_rate: number;
}

export async function listEvaluations(params?: {
  agent_id?: string;
  run_id?: string;
  limit?: number;
  offset?: number;
}): Promise<RunEvaluationListResponse> {
  return api.get<RunEvaluationListResponse>('/api/v1/evaluations', params as Record<string, string | number | undefined>);
}

export async function getEvaluation(id: string): Promise<RunEvaluation> {
  return api.get<RunEvaluation>(`/api/v1/evaluations/${id}`);
}

export async function createEvaluation(data: RunEvaluationCreate): Promise<RunEvaluation> {
  return api.post<RunEvaluation>('/api/v1/evaluations', data);
}

export async function getAgentQuality(agentId: string): Promise<AgentQualitySummary> {
  return api.get<AgentQualitySummary>(`/api/v1/evaluations/agents/${agentId}/quality`);
}

export async function listFeedbacks(params?: {
  run_id?: string;
  limit?: number;
  offset?: number;
}): Promise<RunFeedbackListResponse> {
  return api.get<RunFeedbackListResponse>('/api/v1/evaluations/feedbacks', params as Record<string, string | number | undefined>);
}

export async function createFeedback(data: RunFeedbackCreate): Promise<RunFeedback> {
  return api.post<RunFeedback>('/api/v1/evaluations/feedbacks', data);
}
