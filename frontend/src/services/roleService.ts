import { api } from './api';

export interface RoleItem {
  id: string;
  name: string;
  description: string;
  permissions: Record<string, string[]>;
  is_system: boolean;
  created_at: string;
  updated_at: string;
}

export interface RoleListResponse {
  items: RoleItem[];
  total: number;
}

export interface RoleCreateParams {
  name: string;
  description?: string;
  permissions: Record<string, string[]>;
}

export interface RoleUpdateParams {
  description?: string;
  permissions?: Record<string, string[]>;
}

export const roleService = {
  list: (params?: { limit?: number; offset?: number }) =>
    api.get<RoleListResponse>('/roles', params),

  get: (id: string) =>
    api.get<RoleItem>(`/roles/${id}`),

  create: (data: RoleCreateParams) =>
    api.post<RoleItem>('/roles', data),

  update: (id: string, data: RoleUpdateParams) =>
    api.put<RoleItem>(`/roles/${id}`, data),

  delete: (id: string) =>
    api.delete(`/roles/${id}`),

  assignRole: (roleId: string, userId: string) =>
    api.post<{ message: string }>(`/roles/${roleId}/assign/${userId}`, {}),
};
