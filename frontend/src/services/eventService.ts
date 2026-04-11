/**
 * Event Sourcing 事件服务 — 对接后端 /api/v1/events 接口。
 */
import { api } from './api';

// ── 类型定义 ──

export interface EventItem {
  event_id: string;
  sequence: number;
  event_type: string;
  run_id: string;
  session_id: string | null;
  agent_name: string | null;
  span_id: string | null;
  timestamp: string;
  payload: Record<string, unknown> | null;
}

export interface EventListResponse {
  items: EventItem[];
  total: number;
}

export interface EventStatsResponse {
  total_events: number;
  event_type_counts: Record<string, number>;
  run_count: number;
}

export interface ReplayParams {
  event_type?: string;
  after_sequence?: number;
  limit?: number;
}

export interface SessionEventParams {
  event_type?: string;
  limit?: number;
}

// ── 服务 ──

export const eventService = {
  /** 按 run_id 查询事件流（用于回放）。 */
  replay: (runId: string, params?: ReplayParams) =>
    api.get<EventListResponse>(
      `/events/replay/${runId}`,
      params as Record<string, string | number | undefined>,
    ),

  /** 按 session_id 查询事件。 */
  sessionEvents: (sessionId: string, params?: SessionEventParams) =>
    api.get<EventListResponse>(
      `/events/sessions/${sessionId}`,
      params as Record<string, string | number | undefined>,
    ),

  /** 获取事件统计。 */
  stats: (params?: { run_id?: string; session_id?: string }) =>
    api.get<EventStatsResponse>(
      '/events/stats',
      params as Record<string, string | number | undefined>,
    ),
};
