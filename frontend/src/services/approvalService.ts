import { api } from './api';

export interface ApprovalItem {
  id: string;
  session_id: string;
  run_id: string;
  agent_name: string;
  trigger: string;
  content: Record<string, unknown>;
  status: string;
  comment: string;
  resolved_at: string | null;
  created_at: string;
}

export interface ApprovalListResponse {
  items: ApprovalItem[];
  total: number;
}

export interface ApprovalListParams {
  status?: string;
  agent_name?: string;
  session_id?: string;
  limit?: number;
  offset?: number;
}

export interface ApprovalResolveParams {
  action: 'approve' | 'reject';
  comment?: string;
}

export const approvalService = {
  async list(params?: ApprovalListParams): Promise<ApprovalListResponse> {
    const cleanParams: Record<string, string | number> = {};
    if (params) {
      if (params.status) cleanParams.status = params.status;
      if (params.agent_name) cleanParams.agent_name = params.agent_name;
      if (params.session_id) cleanParams.session_id = params.session_id;
      if (params.limit) cleanParams.limit = params.limit;
      if (params.offset !== undefined) cleanParams.offset = params.offset;
    }
    return api.get<ApprovalListResponse>('/approvals', cleanParams);
  },

  async get(id: string): Promise<ApprovalItem> {
    return api.get<ApprovalItem>(`/approvals/${id}`);
  },

  async resolve(id: string, data: ApprovalResolveParams): Promise<ApprovalItem> {
    return api.post<ApprovalItem>(`/approvals/${id}/resolve`, data);
  },
};
