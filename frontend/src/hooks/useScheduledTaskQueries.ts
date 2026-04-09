/**
 * TanStack Query hooks — ScheduledTask 相关查询。
 */
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { scheduledTaskService } from '../services/scheduledTaskService';
import type { ScheduledTaskCreateParams, ScheduledTaskUpdateParams } from '../services/scheduledTaskService';

const KEY = ['scheduled-tasks'] as const;

export function useScheduledTaskList(params?: Record<string, string | number | boolean | undefined>) {
  return useQuery({
    queryKey: [...KEY, params],
    queryFn: () => scheduledTaskService.list(params),
  });
}

export function useCreateScheduledTask() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: ScheduledTaskCreateParams) => scheduledTaskService.create(data),
    onSuccess: () => { void qc.invalidateQueries({ queryKey: KEY }); },
  });
}

export function useUpdateScheduledTask() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: ScheduledTaskUpdateParams }) =>
      scheduledTaskService.update(id, data),
    onSuccess: () => { void qc.invalidateQueries({ queryKey: KEY }); },
  });
}

export function useDeleteScheduledTask() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => scheduledTaskService.delete(id),
    onSuccess: () => { void qc.invalidateQueries({ queryKey: KEY }); },
  });
}
