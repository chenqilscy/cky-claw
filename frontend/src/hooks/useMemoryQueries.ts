/**
 * TanStack Query hooks — Memory 相关查询。
 */
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { memoryService } from '../services/memoryService';
import type { MemoryCreateParams, MemoryUpdateParams, MemorySearchParams, MemoryDecayParams } from '../services/memoryService';

const KEY = ['memories'] as const;

export function useMemoryList(params?: Record<string, string | number | undefined>) {
  return useQuery({
    queryKey: [...KEY, params],
    queryFn: () => memoryService.list(params),
  });
}

export function useMemory(id: string | undefined) {
  return useQuery({
    queryKey: [...KEY, id],
    queryFn: () => memoryService.get(id as string),
    enabled: !!id,
  });
}

export function useCreateMemory() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: MemoryCreateParams) => memoryService.create(data),
    onSuccess: () => { void qc.invalidateQueries({ queryKey: KEY }); },
  });
}

export function useUpdateMemory() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: MemoryUpdateParams }) =>
      memoryService.update(id, data),
    onSuccess: () => { void qc.invalidateQueries({ queryKey: KEY }); },
  });
}

export function useDeleteMemory() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => memoryService.delete(id),
    onSuccess: () => { void qc.invalidateQueries({ queryKey: KEY }); },
  });
}

export function useSearchMemory() {
  return useMutation({
    mutationFn: (data: MemorySearchParams) => memoryService.search(data),
  });
}

export function useDecayMemory() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: MemoryDecayParams) => memoryService.decay(data),
    onSuccess: () => { void qc.invalidateQueries({ queryKey: KEY }); },
  });
}
