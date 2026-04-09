/**
 * TanStack Query hooks — AgentTemplate 相关查询。
 */
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { agentTemplateService } from '../services/agentTemplateService';
import type { AgentTemplateCreateParams, AgentTemplateUpdateParams } from '../services/agentTemplateService';

const KEY = ['templates'] as const;

export function useTemplateList(params?: Record<string, string | number | boolean | undefined>) {
  return useQuery({
    queryKey: [...KEY, params],
    queryFn: () => agentTemplateService.list(params),
  });
}

export function useTemplate(id: string | undefined) {
  return useQuery({
    queryKey: [...KEY, id],
    queryFn: () => agentTemplateService.get(id as string),
    enabled: !!id,
  });
}

export function useCreateTemplate() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: AgentTemplateCreateParams) => agentTemplateService.create(data),
    onSuccess: () => { void qc.invalidateQueries({ queryKey: KEY }); },
  });
}

export function useUpdateTemplate() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: AgentTemplateUpdateParams }) =>
      agentTemplateService.update(id, data),
    onSuccess: () => { void qc.invalidateQueries({ queryKey: KEY }); },
  });
}

export function useDeleteTemplate() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => agentTemplateService.delete(id),
    onSuccess: () => { void qc.invalidateQueries({ queryKey: KEY }); },
  });
}

export function useSeedBuiltinTemplates() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => agentTemplateService.seedBuiltin(),
    onSuccess: () => { void qc.invalidateQueries({ queryKey: KEY }); },
  });
}

export function useInstantiateTemplate() {
  return useMutation({
    mutationFn: ({ id, overrides }: { id: string; overrides?: Record<string, unknown> }) =>
      agentTemplateService.instantiate(id, overrides),
  });
}
