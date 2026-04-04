import { api } from './api';

export interface AuditLog {
  id: string;
  user_id: string | null;
  action: string;
  resource_type: string;
  resource_id: string | null;
  detail: Record<string, unknown>;
  ip_address: string | null;
  user_agent: string | null;
  request_id: string | null;
  status_code: number | null;
  created_at: string;
}

export interface AuditLogListResponse {
  data: AuditLog[];
  total: number;
}

export async function listAuditLogs(params?: {
  limit?: number;
  offset?: number;
  action?: string;
  resource_type?: string;
  user_id?: string;
  resource_id?: string;
}): Promise<AuditLogListResponse> {
  return api.get<AuditLogListResponse>('/api/v1/audit-logs', params as Record<string, string | number | undefined>);
}

export async function getAuditLog(id: string): Promise<AuditLog> {
  return api.get<AuditLog>(`/api/v1/audit-logs/${id}`);
}
