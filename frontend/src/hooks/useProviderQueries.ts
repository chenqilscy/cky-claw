/**
 * TanStack Query hooks — Provider 相关查询。
 */
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { providerService } from '../services/providerService';
import type {
  ProviderCreateRequest,
  ProviderUpdateRequest,
  ProviderListParams,
  RotateKeyRequest,
} from '../services/providerService';

const KEY = ['providers'] as const;

export function useProviderList(params?: ProviderListParams) {
  return useQuery({
    queryKey: [...KEY, params],
    queryFn: () => providerService.list(params),
  });
}

export function useProvider(id: string | undefined) {
  return useQuery({
    queryKey: [...KEY, id],
    queryFn: () => providerService.get(id as string),
    enabled: !!id,
  });
}

export function useCreateProvider() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: ProviderCreateRequest) => providerService.create(data),
    onSuccess: () => { void qc.invalidateQueries({ queryKey: KEY }); },
  });
}

export function useUpdateProvider() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: ProviderUpdateRequest }) =>
      providerService.update(id, data),
    onSuccess: () => { void qc.invalidateQueries({ queryKey: KEY }); },
  });
}

export function useDeleteProvider() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => providerService.delete(id),
    onSuccess: () => { void qc.invalidateQueries({ queryKey: KEY }); },
  });
}

export function useToggleProvider() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, isEnabled }: { id: string; isEnabled: boolean }) =>
      providerService.toggle(id, isEnabled),
    onSuccess: () => { void qc.invalidateQueries({ queryKey: KEY }); },
  });
}

export function useTestProviderConnection() {
  return useMutation({
    mutationFn: (id: string) => providerService.testConnection(id),
  });
}

export function useRotateProviderKey() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: RotateKeyRequest }) =>
      providerService.rotateKey(id, data),
    onSuccess: () => { void qc.invalidateQueries({ queryKey: KEY }); },
  });
}
