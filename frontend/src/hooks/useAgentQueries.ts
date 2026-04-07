/**
 * TanStack Query hooks — Agent 相关查询。
 */
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { agentService } from '../services/agentService';
import type { AgentCreateInput, AgentUpdateInput } from '../services/agentService';

const AGENTS_KEY = ['agents'] as const;

export function useAgentList(params?: { search?: string; limit?: number; offset?: number }) {
  return useQuery({
    queryKey: [...AGENTS_KEY, params],
    queryFn: () => agentService.list(params),
  });
}

export function useAgent(name: string | undefined) {
  return useQuery({
    queryKey: [...AGENTS_KEY, name],
    queryFn: () => agentService.get(name as string),
    enabled: !!name,
  });
}

export function useCreateAgent() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: AgentCreateInput) => agentService.create(data),
    onSuccess: () => { void qc.invalidateQueries({ queryKey: AGENTS_KEY }); },
  });
}

export function useUpdateAgent() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ name, data }: { name: string; data: AgentUpdateInput }) =>
      agentService.update(name, data),
    onSuccess: () => { void qc.invalidateQueries({ queryKey: AGENTS_KEY }); },
  });
}

export function useDeleteAgent() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (name: string) => agentService.delete(name),
    onSuccess: () => { void qc.invalidateQueries({ queryKey: AGENTS_KEY }); },
  });
}
