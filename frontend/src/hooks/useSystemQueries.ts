import { useQuery } from '@tanstack/react-query';
import { systemService } from '../services/systemService';

export function useSystemInfo() {
  return useQuery({
    queryKey: ['system', 'info'],
    queryFn: () => systemService.info(),
    staleTime: 60_000,
  });
}
