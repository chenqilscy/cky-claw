import { api } from './api';

export const CHANNEL_TYPES = ['wecom', 'dingtalk', 'slack', 'telegram', 'feishu', 'webhook'] as const;
export type ChannelType = typeof CHANNEL_TYPES[number];

export interface IMChannel {
  id: string;
  name: string;
  description: string;
  channel_type: ChannelType;
  webhook_url: string | null;
  webhook_secret: string | null;
  app_config: Record<string, unknown>;
  agent_id: string | null;
  is_enabled: boolean;
  created_at: string;
  updated_at: string;
}

export interface IMChannelListResponse {
  data: IMChannel[];
  total: number;
  limit: number;
  offset: number;
}

export interface IMChannelCreate {
  name: string;
  description?: string;
  channel_type: string;
  webhook_url?: string | null;
  webhook_secret?: string | null;
  app_config?: Record<string, unknown>;
  agent_id?: string | null;
  is_enabled?: boolean;
}

export interface IMChannelUpdate {
  description?: string;
  channel_type?: string;
  webhook_url?: string | null;
  webhook_secret?: string | null;
  app_config?: Record<string, unknown>;
  agent_id?: string | null;
  is_enabled?: boolean;
}

export async function listIMChannels(params?: {
  channel_type?: string;
  is_enabled?: boolean;
  limit?: number;
  offset?: number;
}): Promise<IMChannelListResponse> {
  return api.get<IMChannelListResponse>('/api/v1/im-channels', params as Record<string, string | number | undefined>);
}

export async function getIMChannel(id: string): Promise<IMChannel> {
  return api.get<IMChannel>(`/api/v1/im-channels/${id}`);
}

export async function createIMChannel(data: IMChannelCreate): Promise<IMChannel> {
  return api.post<IMChannel>('/api/v1/im-channels', data);
}

export async function updateIMChannel(id: string, data: IMChannelUpdate): Promise<IMChannel> {
  return api.put<IMChannel>(`/api/v1/im-channels/${id}`, data);
}

export async function deleteIMChannel(id: string): Promise<void> {
  await api.delete(`/api/v1/im-channels/${id}`);
}
