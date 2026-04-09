/**
 * TanStack Query hooks — Agent Version 相关查询。
 */
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { agentVersionService } from '../services/agentVersionService';

const KEY = ['agent-versions'] as const;

export function useAgentVersionList(
  agentId: string | undefined,
  params?: { limit?: number; offset?: number },
) {
  return useQuery({
    queryKey: [...KEY, agentId, params],
    queryFn: () => agentVersionService.list(agentId as string, params),
    enabled: !!agentId,
  });
}

export function useAgentVersionDiff(
  agentId: string | undefined,
  v1: number | undefined,
  v2: number | undefined,
) {
  return useQuery({
    queryKey: [...KEY, agentId, 'diff', v1, v2],
    queryFn: () => agentVersionService.diff(agentId as string, v1 as number, v2 as number),
    enabled: !!agentId && v1 !== undefined && v2 !== undefined,
  });
}

export function useRollbackAgentVersion() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      agentId,
      version,
      changeSummary,
    }: {
      agentId: string;
      version: number;
      changeSummary?: string;
    }) => agentVersionService.rollback(agentId, version, changeSummary),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: KEY });
    },
  });
}
