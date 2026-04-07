/**
 * TanStack Query hooks — Workflow 相关查询。
 */
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { workflowService } from '../services/workflowService';
import type { WorkflowCreateParams, WorkflowUpdateParams } from '../services/workflowService';

const WORKFLOWS_KEY = ['workflows'] as const;

export function useWorkflowList(params?: { limit?: number; offset?: number }) {
  return useQuery({
    queryKey: [...WORKFLOWS_KEY, params],
    queryFn: () => workflowService.list(params),
  });
}

export function useWorkflow(id: string | undefined) {
  return useQuery({
    queryKey: [...WORKFLOWS_KEY, id],
    queryFn: () => workflowService.get(id as string),
    enabled: !!id,
  });
}

export function useCreateWorkflow() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: WorkflowCreateParams) => workflowService.create(data),
    onSuccess: () => { void qc.invalidateQueries({ queryKey: WORKFLOWS_KEY }); },
  });
}

export function useUpdateWorkflow() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: WorkflowUpdateParams }) =>
      workflowService.update(id, data),
    onSuccess: () => { void qc.invalidateQueries({ queryKey: WORKFLOWS_KEY }); },
  });
}

export function useDeleteWorkflow() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => workflowService.delete(id),
    onSuccess: () => { void qc.invalidateQueries({ queryKey: WORKFLOWS_KEY }); },
  });
}

export function useValidateWorkflow() {
  return useMutation({
    mutationFn: (data: WorkflowCreateParams) => workflowService.validate(data),
  });
}
