import { api } from './api';

export interface ScheduledTaskItem {
  id: string;
  name: string;
  description: string;
  agent_id: string;
  cron_expr: string;
  input_text: string;
  is_enabled: boolean;
  last_run_at: string | null;
  next_run_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface ScheduledTaskListResponse {
  data: ScheduledTaskItem[];
  total: number;
}

export interface ScheduledTaskCreateParams {
  name: string;
  description?: string;
  agent_id: string;
  cron_expr: string;
  input_text?: string;
}

export interface ScheduledTaskUpdateParams {
  name?: string;
  description?: string;
  cron_expr?: string;
  input_text?: string;
  is_enabled?: boolean;
}

export const scheduledTaskService = {
  async list(params?: Record<string, string | number | boolean | undefined>): Promise<ScheduledTaskListResponse> {
    const cleanParams: Record<string, string | number | undefined> = {};
    if (params) {
      Object.entries(params).forEach(([k, v]) => {
        if (v !== undefined && v !== '') cleanParams[k] = typeof v === 'boolean' ? String(v) : v as string | number;
      });
    }
    return api.get<ScheduledTaskListResponse>('/scheduled-tasks', cleanParams);
  },

  async get(id: string): Promise<ScheduledTaskItem> {
    return api.get<ScheduledTaskItem>(`/scheduled-tasks/${id}`);
  },

  async create(data: ScheduledTaskCreateParams): Promise<ScheduledTaskItem> {
    return api.post<ScheduledTaskItem>('/scheduled-tasks', data);
  },

  async update(id: string, data: ScheduledTaskUpdateParams): Promise<ScheduledTaskItem> {
    return api.put<ScheduledTaskItem>(`/scheduled-tasks/${id}`, data);
  },

  async delete(id: string): Promise<void> {
    await api.delete(`/scheduled-tasks/${id}`);
  },
};
