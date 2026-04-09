/**
 * TanStack Query hooks — Trace 相关查询。
 */
import { useQuery } from '@tanstack/react-query';
import { traceService } from '../services/traceService';
import type { TraceListParams, SpanListParams } from '../services/traceService';

const KEY = ['traces'] as const;

export function useTraceList(params?: TraceListParams) {
  return useQuery({
    queryKey: [...KEY, params],
    queryFn: () => traceService.list(params),
  });
}

export function useTraceDetail(traceId: string | undefined) {
  return useQuery({
    queryKey: [...KEY, 'detail', traceId],
    queryFn: () => traceService.detail(traceId as string),
    enabled: !!traceId,
  });
}

export function useTraceSpans(params?: SpanListParams) {
  return useQuery({
    queryKey: [...KEY, 'spans', params],
    queryFn: () => traceService.listSpans(params),
    enabled: !!params?.trace_id,
  });
}

export function useTraceStats(params?: TraceListParams) {
  return useQuery({
    queryKey: [...KEY, 'stats', params],
    queryFn: () => traceService.stats(params),
  });
}

export function useTraceFlame(traceId: string | undefined, maxDepth?: number) {
  return useQuery({
    queryKey: [...KEY, 'flame', traceId, maxDepth],
    queryFn: () => traceService.flame(traceId as string, maxDepth),
    enabled: !!traceId,
  });
}

export function useTraceReplay(traceId: string | undefined) {
  return useQuery({
    queryKey: [...KEY, 'replay', traceId],
    queryFn: () => traceService.replay(traceId as string),
    enabled: !!traceId,
  });
}
