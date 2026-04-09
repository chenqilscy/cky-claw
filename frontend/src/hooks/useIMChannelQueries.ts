/**
 * TanStack Query hooks — IMChannel 相关查询。
 */
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  listIMChannels, getIMChannel, createIMChannel,
  updateIMChannel, deleteIMChannel,
} from '../services/imChannelService';
import type { IMChannelCreate, IMChannelUpdate } from '../services/imChannelService';

const KEY = ['im-channels'] as const;

export function useIMChannelList(params?: { channel_type?: string; is_enabled?: boolean; limit?: number; offset?: number }) {
  return useQuery({
    queryKey: [...KEY, params],
    queryFn: () => listIMChannels(params),
  });
}

export function useIMChannel(id: string | undefined) {
  return useQuery({
    queryKey: [...KEY, id],
    queryFn: () => getIMChannel(id as string),
    enabled: !!id,
  });
}

export function useCreateIMChannel() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: IMChannelCreate) => createIMChannel(data),
    onSuccess: () => { void qc.invalidateQueries({ queryKey: KEY }); },
  });
}

export function useUpdateIMChannel() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: IMChannelUpdate }) =>
      updateIMChannel(id, data),
    onSuccess: () => { void qc.invalidateQueries({ queryKey: KEY }); },
  });
}

export function useDeleteIMChannel() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => deleteIMChannel(id),
    onSuccess: () => { void qc.invalidateQueries({ queryKey: KEY }); },
  });
}
