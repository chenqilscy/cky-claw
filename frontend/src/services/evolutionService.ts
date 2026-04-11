import { api } from './api';

export interface EvolutionProposal {
  id: string;
  agent_name: string;
  proposal_type: string;
  status: string;
  trigger_reason: string;
  current_value: Record<string, unknown> | null;
  proposed_value: Record<string, unknown> | null;
  confidence_score: number;
  eval_before: number | null;
  eval_after: number | null;
  applied_at: string | null;
  rolled_back_at: string | null;
  metadata: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface EvolutionProposalListResponse {
  data: EvolutionProposal[];
  total: number;
  limit: number;
  offset: number;
}

export interface EvolutionProposalListParams {
  agent_name?: string;
  proposal_type?: string;
  status?: string;
  limit?: number;
  offset?: number;
}

export interface EvolutionProposalCreate {
  agent_name: string;
  proposal_type: string;
  trigger_reason?: string;
  current_value?: Record<string, unknown>;
  proposed_value?: Record<string, unknown>;
  confidence_score?: number;
  metadata?: Record<string, unknown>;
}

export interface EvolutionProposalUpdate {
  status?: string;
  eval_before?: number;
  eval_after?: number;
  metadata?: Record<string, unknown>;
}

export interface RollbackCheckRequest {
  eval_after: number;
  rollback_threshold?: number;
}

export interface RollbackCheckResponse {
  rolled_back: boolean;
  proposal: EvolutionProposal;
}

export interface ScanRollbackResponse {
  rolled_back_count: number;
  proposals: EvolutionProposal[];
}

export const evolutionService = {
  async list(params?: EvolutionProposalListParams): Promise<EvolutionProposalListResponse> {
    const cleanParams: Record<string, string | number> = {};
    if (params) {
      if (params.agent_name) cleanParams.agent_name = params.agent_name;
      if (params.proposal_type) cleanParams.proposal_type = params.proposal_type;
      if (params.status) cleanParams.status = params.status;
      if (params.limit) cleanParams.limit = params.limit;
      if (params.offset !== undefined) cleanParams.offset = params.offset;
    }
    return api.get<EvolutionProposalListResponse>('/evolution/proposals', cleanParams);
  },

  async get(id: string): Promise<EvolutionProposal> {
    return api.get<EvolutionProposal>(`/evolution/proposals/${id}`);
  },

  async create(data: EvolutionProposalCreate): Promise<EvolutionProposal> {
    return api.post<EvolutionProposal>('/evolution/proposals', data);
  },

  async update(id: string, data: EvolutionProposalUpdate): Promise<EvolutionProposal> {
    return api.put<EvolutionProposal>(`/evolution/proposals/${id}`, data);
  },

  async delete(id: string): Promise<void> {
    await api.delete<undefined>(`/evolution/proposals/${id}`);
  },

  async rollbackCheck(id: string, data: RollbackCheckRequest): Promise<RollbackCheckResponse> {
    return api.post<RollbackCheckResponse>(`/evolution/proposals/${id}/rollback-check`, data);
  },

  async scanRollback(rollbackThreshold = 0.1): Promise<ScanRollbackResponse> {
    return api.post<ScanRollbackResponse>(`/evolution/scan-rollback?rollback_threshold=${rollbackThreshold}`);
  },
};
