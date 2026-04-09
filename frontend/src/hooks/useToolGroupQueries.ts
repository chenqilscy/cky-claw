/**
 * TanStack Query hooks — ToolGroup 相关查询。
 */
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { toolGroupService } from '../services/toolGroupService';
import type { ToolGroupCreateRequest, ToolGroupUpdateRequest } from '../services/toolGroupService';

const KEY = ['tool-groups'] as const;

export function useToolGroupList() {
  return useQuery({
    queryKey: [...KEY],
    queryFn: () => toolGroupService.list(),
  });
}

export function useToolGroup(name: string | undefined) {
  return useQuery({
    queryKey: [...KEY, name],
    queryFn: () => toolGroupService.get(name as string),
    enabled: !!name,
  });
}

export function useCreateToolGroup() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: ToolGroupCreateRequest) => toolGroupService.create(data),
    onSuccess: () => { void qc.invalidateQueries({ queryKey: KEY }); },
  });
}

export function useUpdateToolGroup() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ name, data }: { name: string; data: ToolGroupUpdateRequest }) =>
      toolGroupService.update(name, data),
    onSuccess: () => { void qc.invalidateQueries({ queryKey: KEY }); },
  });
}

export function useDeleteToolGroup() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (name: string) => toolGroupService.delete(name),
    onSuccess: () => { void qc.invalidateQueries({ queryKey: KEY }); },
  });
}
