/**
 * TanStack Query hooks — Skill 相关查询。
 */
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { skillService } from '../services/skillService';
import type { SkillCreateParams, SkillUpdateParams, SkillSearchParams } from '../services/skillService';

const KEY = ['skills'] as const;

export function useSkillList(params?: Record<string, string | number | undefined>) {
  return useQuery({
    queryKey: [...KEY, params],
    queryFn: () => skillService.list(params),
  });
}

export function useSkill(id: string | undefined) {
  return useQuery({
    queryKey: [...KEY, id],
    queryFn: () => skillService.get(id as string),
    enabled: !!id,
  });
}

export function useCreateSkill() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (data: SkillCreateParams) => skillService.create(data),
    onSuccess: () => { void qc.invalidateQueries({ queryKey: KEY }); },
  });
}

export function useUpdateSkill() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: string; data: SkillUpdateParams }) =>
      skillService.update(id, data),
    onSuccess: () => { void qc.invalidateQueries({ queryKey: KEY }); },
  });
}

export function useDeleteSkill() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => skillService.delete(id),
    onSuccess: () => { void qc.invalidateQueries({ queryKey: KEY }); },
  });
}

export function useSearchSkill() {
  return useMutation({
    mutationFn: (data: SkillSearchParams) => skillService.search(data),
  });
}
