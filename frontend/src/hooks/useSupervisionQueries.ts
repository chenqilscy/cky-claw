/**
 * TanStack Query hooks — Supervision 相关查询。
 */
import { useQuery, useMutation } from '@tanstack/react-query';
import { supervisionService } from '../services/supervisionService';
import type { SupervisionListParams } from '../services/supervisionService';

const KEY = ['supervision'] as const;

export function useSupervisionSessionList(params?: SupervisionListParams) {
  return useQuery({
    queryKey: [...KEY, params],
    queryFn: () => supervisionService.listSessions(params),
  });
}

export function useSupervisionSessionDetail(sessionId: string | undefined) {
  return useQuery({
    queryKey: [...KEY, 'detail', sessionId],
    queryFn: () => supervisionService.getSessionDetail(sessionId as string),
    enabled: !!sessionId,
  });
}

export function usePauseSession() {
  return useMutation({
    mutationFn: ({ sessionId, reason }: { sessionId: string; reason?: string }) =>
      supervisionService.pauseSession(sessionId, reason),
  });
}

export function useResumeSession() {
  return useMutation({
    mutationFn: ({ sessionId, instructions }: { sessionId: string; instructions?: string }) =>
      supervisionService.resumeSession(sessionId, instructions),
  });
}
