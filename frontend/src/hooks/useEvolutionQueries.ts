/**
 * TanStack Query hooks — Evolution 相关查询。
 */
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { evolutionService } from '../services/evolutionService';
import type { EvolutionProposalCreate, EvolutionProposalUpdate, EvolutionProposalListParams, RollbackCheckRequest } from '../services/evolutionService';

const KEY = ['evolutions'] as const;

export function useEvolutionList(params?: EvolutionProposalListParams) {
  return useQuery({
    queryKey: [...KEY, params],
    queryFn: () => evolutionService.list(params),
  });
}

export function useEvolution(id: string | undefined) {
  return useQuery({
    queryKey: [...KEY, id],
    queryFn: () => evolutionService.get(id as string),
    enabled: !!id,
  });
}

export function useCreateEvolution() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: EvolutionProposalCreate) => evolutionService.create(data),
    onSuccess: () => { void qc.invalidateQueries({ queryKey: KEY }); },
  });
}

export function useUpdateEvolution() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: EvolutionProposalUpdate }) =>
      evolutionService.update(id, data),
    onSuccess: () => { void qc.invalidateQueries({ queryKey: KEY }); },
  });
}

export function useDeleteEvolution() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => evolutionService.delete(id),
    onSuccess: () => { void qc.invalidateQueries({ queryKey: KEY }); },
  });
}

export function useRollbackCheck() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: RollbackCheckRequest }) =>
      evolutionService.rollbackCheck(id, data),
    onSuccess: () => { void qc.invalidateQueries({ queryKey: KEY }); },
  });
}

export function useScanRollback() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (threshold?: number) => evolutionService.scanRollback(threshold),
    onSuccess: () => { void qc.invalidateQueries({ queryKey: KEY }); },
  });
}
