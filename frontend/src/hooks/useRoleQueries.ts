/**
 * TanStack Query hooks — Role 相关查询。
 */
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { roleService } from '../services/roleService';
import type { RoleCreateParams, RoleUpdateParams } from '../services/roleService';

const KEY = ['roles'] as const;

export function useRoleList(params?: { limit?: number; offset?: number }) {
  return useQuery({
    queryKey: [...KEY, params],
    queryFn: () => roleService.list(params),
  });
}

export function useRole(id: string | undefined) {
  return useQuery({
    queryKey: [...KEY, id],
    queryFn: () => roleService.get(id as string),
    enabled: !!id,
  });
}

export function useCreateRole() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: RoleCreateParams) => roleService.create(data),
    onSuccess: () => { void qc.invalidateQueries({ queryKey: KEY }); },
  });
}

export function useUpdateRole() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: RoleUpdateParams }) =>
      roleService.update(id, data),
    onSuccess: () => { void qc.invalidateQueries({ queryKey: KEY }); },
  });
}

export function useDeleteRole() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => roleService.delete(id),
    onSuccess: () => { void qc.invalidateQueries({ queryKey: KEY }); },
  });
}
