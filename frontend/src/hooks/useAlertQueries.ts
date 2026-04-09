/**
 * TanStack Query hooks — Alert 相关查询。
 */
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { alertService } from '../services/alertService';
import type { AlertRuleCreate } from '../services/alertService';

const RULES_KEY = ['alert-rules'] as const;
const EVENTS_KEY = ['alert-events'] as const;

export function useAlertRuleList(params?: { limit?: number; offset?: number; is_enabled?: boolean; severity?: string }) {
  return useQuery({
    queryKey: [...RULES_KEY, params],
    queryFn: () => alertService.listRules(params),
  });
}

export function useCreateAlertRule() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: AlertRuleCreate) => alertService.createRule(data),
    onSuccess: () => { void qc.invalidateQueries({ queryKey: RULES_KEY }); },
  });
}

export function useUpdateAlertRule() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: Partial<AlertRuleCreate> }) =>
      alertService.updateRule(id, data),
    onSuccess: () => { void qc.invalidateQueries({ queryKey: RULES_KEY }); },
  });
}

export function useDeleteAlertRule() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => alertService.deleteRule(id),
    onSuccess: () => { void qc.invalidateQueries({ queryKey: RULES_KEY }); },
  });
}

export function useAlertEventList(params?: { rule_id?: string; severity?: string; limit?: number; offset?: number }) {
  return useQuery({
    queryKey: [...EVENTS_KEY, params],
    queryFn: () => alertService.listEvents(params),
  });
}
