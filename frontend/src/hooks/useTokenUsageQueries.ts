/**
 * TanStack Query hooks — Token Usage 相关查询。
 */
import { useQuery } from '@tanstack/react-query';
import { tokenUsageService } from '../services/tokenUsageService';
import type { TokenUsageListParams, TokenUsageSummaryParams, TokenUsageTrendParams } from '../services/tokenUsageService';

const KEY = ['token-usage'] as const;

export function useTokenUsageList(params?: TokenUsageListParams) {
  return useQuery({
    queryKey: [...KEY, params],
    queryFn: () => tokenUsageService.list(params),
  });
}

export function useTokenUsageSummary(params?: TokenUsageSummaryParams) {
  return useQuery({
    queryKey: [...KEY, 'summary', params],
    queryFn: () => tokenUsageService.summary(params),
  });
}

export function useTokenUsageTrend(params?: TokenUsageTrendParams) {
  return useQuery({
    queryKey: [...KEY, 'trend', params],
    queryFn: () => tokenUsageService.trend(params),
  });
}
