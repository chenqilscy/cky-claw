import { api } from './api';

export interface OrganizationItem {
  id: string;
  name: string;
  slug: string;
  description: string;
  settings: Record<string, unknown>;
  quota: Record<string, unknown>;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface OrganizationListResponse {
  data: OrganizationItem[];
  total: number;
  limit: number;
  offset: number;
}

export interface OrganizationCreateParams {
  name: string;
  slug: string;
  description?: string;
  settings?: Record<string, unknown>;
  quota?: Record<string, unknown>;
}

export interface OrganizationUpdateParams {
  name?: string;
  description?: string;
  settings?: Record<string, unknown>;
  quota?: Record<string, unknown>;
  is_active?: boolean;
}

export const organizationService = {
  list: (params?: { search?: string; limit?: number; offset?: number }) =>
    api.get<OrganizationListResponse>('/organizations', params),

  get: (id: string) =>
    api.get<OrganizationItem>(`/organizations/${id}`),

  create: (data: OrganizationCreateParams) =>
    api.post<OrganizationItem>('/organizations', data),

  update: (id: string, data: OrganizationUpdateParams) =>
    api.put<OrganizationItem>(`/organizations/${id}`, data),

  delete: (id: string) =>
    api.delete(`/organizations/${id}`),
};
