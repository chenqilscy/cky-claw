/**
 * TanStack Query hooks — Team 相关查询。
 */
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { listTeams, getTeam, createTeam, updateTeam, deleteTeam } from '../services/teamService';
import type { TeamConfigCreate, TeamConfigUpdate } from '../services/teamService';

const KEY = ['teams'] as const;

export function useTeamList(params?: { limit?: number; offset?: number; search?: string }) {
  return useQuery({
    queryKey: [...KEY, params],
    queryFn: () => listTeams(params),
  });
}

export function useTeam(id: string | undefined) {
  return useQuery({
    queryKey: [...KEY, id],
    queryFn: () => getTeam(id as string),
    enabled: !!id,
  });
}

export function useCreateTeam() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: TeamConfigCreate) => createTeam(data),
    onSuccess: () => { void qc.invalidateQueries({ queryKey: KEY }); },
  });
}

export function useUpdateTeam() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: TeamConfigUpdate }) =>
      updateTeam(id, data),
    onSuccess: () => { void qc.invalidateQueries({ queryKey: KEY }); },
  });
}

export function useDeleteTeam() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => deleteTeam(id),
    onSuccess: () => { void qc.invalidateQueries({ queryKey: KEY }); },
  });
}
