/**
 * TanStack Query hooks — Evaluation / Feedback / Quality 相关查询。
 */
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  listEvaluations, createEvaluation, getAgentQuality,
  listFeedbacks, createFeedback,
} from '../services/evaluationService';
import type { RunEvaluationCreate, RunFeedbackCreate } from '../services/evaluationService';

const EVAL_KEY = ['evaluations'] as const;
const FEEDBACK_KEY = ['feedbacks'] as const;
const QUALITY_KEY = ['agent-quality'] as const;

/* ---------- Evaluations ---------- */

export function useEvaluationList(params?: { agent_id?: string; run_id?: string; limit?: number; offset?: number }) {
  return useQuery({
    queryKey: [...EVAL_KEY, params],
    queryFn: () => listEvaluations(params),
  });
}

export function useCreateEvaluation() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: RunEvaluationCreate) => createEvaluation(data),
    onSuccess: () => { void qc.invalidateQueries({ queryKey: EVAL_KEY }); },
  });
}

/* ---------- Feedbacks ---------- */

export function useFeedbackList(params?: { agent_id?: string; run_id?: string; limit?: number; offset?: number }) {
  return useQuery({
    queryKey: [...FEEDBACK_KEY, params],
    queryFn: () => listFeedbacks(params),
  });
}

export function useCreateFeedback() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: RunFeedbackCreate) => createFeedback(data),
    onSuccess: () => { void qc.invalidateQueries({ queryKey: FEEDBACK_KEY }); },
  });
}

/* ---------- Quality ---------- */

export function useAgentQuality(agentId: string | undefined) {
  return useQuery({
    queryKey: [...QUALITY_KEY, agentId],
    queryFn: () => getAgentQuality(agentId as string),
    enabled: !!agentId,
  });
}
