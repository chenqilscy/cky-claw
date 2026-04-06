import { api } from './api';

export interface AlertRule {
  id: string;
  name: string;
  description: string;
  metric: string;
  operator: string;
  threshold: number;
  window_minutes: number;
  agent_name: string | null;
  severity: string;
  is_enabled: boolean;
  cooldown_minutes: number;
  notification_config: Record<string, unknown>;
  last_triggered_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface AlertEvent {
  id: string;
  rule_id: string;
  metric_value: number;
  threshold: number;
  severity: string;
  agent_name: string | null;
  message: string;
  resolved_at: string | null;
  created_at: string;
}

export interface AlertRuleCreate {
  name: string;
  description?: string;
  metric: string;
  operator: string;
  threshold: number;
  window_minutes?: number;
  agent_name?: string | null;
  severity?: string;
  cooldown_minutes?: number;
  notification_config?: Record<string, unknown>;
}

export interface AlertListResponse {
  data: AlertRule[];
  total: number;
}

export interface AlertEventListResponse {
  data: AlertEvent[];
  total: number;
}

/** 慢查询告警预设 */
export const SLOW_QUERY_PRESETS: AlertRuleCreate[] = [
  {
    name: '慢查询告警 (>5s)',
    description: '当平均 Trace 耗时超过 5000ms 时触发告警',
    metric: 'avg_duration_ms',
    operator: '>',
    threshold: 5000,
    window_minutes: 15,
    severity: 'warning',
    cooldown_minutes: 30,
  },
  {
    name: '慢查询告警 (>10s)',
    description: '当平均 Trace 耗时超过 10000ms 时触发严重告警',
    metric: 'avg_duration_ms',
    operator: '>',
    threshold: 10000,
    window_minutes: 15,
    severity: 'critical',
    cooldown_minutes: 60,
  },
  {
    name: '高错误率告警 (>10%)',
    description: '当 Trace 错误率超过 10% 时触发严重告警',
    metric: 'error_rate',
    operator: '>',
    threshold: 10,
    window_minutes: 30,
    severity: 'critical',
    cooldown_minutes: 30,
  },
];

export const alertService = {
  listRules: (params?: { limit?: number; offset?: number; is_enabled?: boolean; severity?: string }) =>
    api.get<AlertListResponse>('/alerts/rules', params as Record<string, string | number | undefined>),

  createRule: (data: AlertRuleCreate) =>
    api.post<AlertRule>('/alerts/rules', data),

  updateRule: (ruleId: string, data: Partial<AlertRuleCreate>) =>
    api.put<AlertRule>(`/alerts/rules/${ruleId}`, data),

  deleteRule: (ruleId: string) =>
    api.delete(`/alerts/rules/${ruleId}`),

  listEvents: (params?: { rule_id?: string; severity?: string; limit?: number; offset?: number }) =>
    api.get<AlertEventListResponse>('/alerts/events', params as Record<string, string | number | undefined>),
};
