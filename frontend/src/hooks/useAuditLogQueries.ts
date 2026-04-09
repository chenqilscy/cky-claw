/**
 * TanStack Query hooks — AuditLog 相关查询。
 */
import { useQuery } from '@tanstack/react-query';
import { listAuditLogs, getAuditLog } from '../services/auditLogService';

const KEY = ['audit-logs'] as const;

export function useAuditLogList(params?: { limit?: number; offset?: number; action?: string; resource_type?: string; user_id?: string; resource_id?: string }) {
  return useQuery({
    queryKey: [...KEY, params],
    queryFn: () => listAuditLogs(params),
  });
}

export function useAuditLog(id: string | undefined) {
  return useQuery({
    queryKey: [...KEY, id],
    queryFn: () => getAuditLog(id as string),
    enabled: !!id,
  });
}
