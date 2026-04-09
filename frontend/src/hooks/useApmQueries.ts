/**
 * TanStack Query hooks — APM 仪表盘查询。
 */
import { useQuery } from '@tanstack/react-query';
import { apmService } from '../services/apmService';

const KEY = ['apm'] as const;

export function useApmDashboard(days?: number) {
  return useQuery({
    queryKey: [...KEY, 'dashboard', days],
    queryFn: () => apmService.dashboard(days),
  });
}
