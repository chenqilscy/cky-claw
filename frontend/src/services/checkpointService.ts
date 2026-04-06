import { api } from './api';

export interface CheckpointResponse {
  checkpoint_id: string;
  run_id: string;
  turn_count: number;
  current_agent_name: string;
  messages: Record<string, unknown>[];
  token_usage: Record<string, number>;
  context: Record<string, unknown>;
  created_at: string;
}

export interface CheckpointListResponse {
  data: CheckpointResponse[];
  total: number;
}

export const checkpointService = {
  /** 获取指定 run 的全部检查点 */
  list: (runId: string) =>
    api.get<CheckpointListResponse>('/checkpoints', { run_id: runId }),

  /** 获取指定 run 的最新检查点 */
  getLatest: (runId: string) =>
    api.get<CheckpointResponse>('/checkpoints/latest', { run_id: runId }),

  /** 删除指定 run 的所有检查点 */
  delete: (runId: string) =>
    api.delete<undefined>(`/checkpoints/${runId}`),
};
