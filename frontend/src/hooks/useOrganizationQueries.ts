/**
 * TanStack Query hooks — Organization 相关查询。
 */
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { organizationService } from '../services/organizationService';
import type { OrganizationCreateParams, OrganizationUpdateParams } from '../services/organizationService';

const KEY = ['organizations'] as const;

export function useOrganizationList(params?: { search?: string; limit?: number; offset?: number }) {
  return useQuery({
    queryKey: [...KEY, params],
    queryFn: () => organizationService.list(params),
  });
}

export function useOrganization(id: string | undefined) {
  return useQuery({
    queryKey: [...KEY, id],
    queryFn: () => organizationService.get(id as string),
    enabled: !!id,
  });
}

export function useCreateOrganization() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: OrganizationCreateParams) => organizationService.create(data),
    onSuccess: () => { void qc.invalidateQueries({ queryKey: KEY }); },
  });
}

export function useUpdateOrganization() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: OrganizationUpdateParams }) =>
      organizationService.update(id, data),
    onSuccess: () => { void qc.invalidateQueries({ queryKey: KEY }); },
  });
}

export function useDeleteOrganization() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => organizationService.delete(id),
    onSuccess: () => { void qc.invalidateQueries({ queryKey: KEY }); },
  });
}
