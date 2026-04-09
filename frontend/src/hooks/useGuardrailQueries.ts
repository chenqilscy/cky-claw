/**
 * TanStack Query hooks — Guardrail 相关查询。
 */
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { guardrailService } from '../services/guardrailService';
import type { GuardrailRuleCreateParams, GuardrailRuleUpdateParams } from '../services/guardrailService';

const KEY = ['guardrails'] as const;

export function useGuardrailList(params?: Record<string, string | number | boolean | undefined>) {
  return useQuery({
    queryKey: [...KEY, params],
    queryFn: () => guardrailService.list(params),
  });
}

export function useGuardrail(id: string | undefined) {
  return useQuery({
    queryKey: [...KEY, id],
    queryFn: () => guardrailService.get(id as string),
    enabled: !!id,
  });
}

export function useCreateGuardrail() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: GuardrailRuleCreateParams) => guardrailService.create(data),
    onSuccess: () => { void qc.invalidateQueries({ queryKey: KEY }); },
  });
}

export function useUpdateGuardrail() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: GuardrailRuleUpdateParams }) =>
      guardrailService.update(id, data),
    onSuccess: () => { void qc.invalidateQueries({ queryKey: KEY }); },
  });
}

export function useDeleteGuardrail() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => guardrailService.delete(id),
    onSuccess: () => { void qc.invalidateQueries({ queryKey: KEY }); },
  });
}
