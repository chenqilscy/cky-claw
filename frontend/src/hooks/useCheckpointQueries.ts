/**
 * TanStack Query hooks — Checkpoint 相关查询。
 */
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { checkpointService } from '../services/checkpointService';

const KEY = ['checkpoints'] as const;

export function useCheckpointList(runId: string | undefined) {
  return useQuery({
    queryKey: [...KEY, runId],
    queryFn: () => checkpointService.list(runId as string),
    enabled: !!runId,
  });
}

export function useCheckpointLatest(runId: string | undefined) {
  return useQuery({
    queryKey: [...KEY, 'latest', runId],
    queryFn: () => checkpointService.getLatest(runId as string),
    enabled: !!runId,
  });
}

export function useDeleteCheckpoint() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (runId: string) => checkpointService.delete(runId),
    onSuccess: () => { void qc.invalidateQueries({ queryKey: KEY }); },
  });
}
