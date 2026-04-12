import { api } from './api';

export interface ClassificationLabel {
  id: string;
  resource_type: string;
  resource_id: string;
  classification: string;
  auto_detected: boolean;
  reason: string;
  created_at: string;
}

export interface RetentionPolicyItem {
  id: string;
  resource_type: string;
  classification: string;
  retention_days: number;
  status: string;
  last_executed_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface ErasureRequestItem {
  id: string;
  requester_user_id: string;
  target_user_id: string;
  status: string;
  scanned_resources: number;
  deleted_resources: number;
  report: Record<string, unknown> | null;
  completed_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface ControlPointItem {
  id: string;
  control_id: string;
  category: string;
  description: string;
  implementation: string;
  evidence_links: Record<string, unknown> | null;
  is_satisfied: boolean;
  created_at: string;
  updated_at: string;
}

export interface ComplianceDashboard {
  total_control_points: number;
  satisfied_control_points: number;
  satisfaction_rate: number;
  active_retention_policies: number;
  pending_erasure_requests: number;
  classification_summary: Record<string, number>;
}

export const complianceService = {
  async getDashboard(): Promise<ComplianceDashboard> {
    return api.get('/api/v1/compliance/dashboard');
  },

  async listLabels(params?: Record<string, string | number | undefined>): Promise<{ data: ClassificationLabel[]; total: number }> {
    return api.get('/api/v1/compliance/labels', params);
  },

  async createLabel(body: { resource_type: string; resource_id: string; classification: string; reason?: string }): Promise<ClassificationLabel> {
    return api.post('/api/v1/compliance/labels', body);
  },

  async listRetentionPolicies(): Promise<{ data: RetentionPolicyItem[]; total: number }> {
    return api.get('/api/v1/compliance/retention-policies');
  },

  async createRetentionPolicy(body: { resource_type: string; classification: string; retention_days: number }): Promise<RetentionPolicyItem> {
    return api.post('/api/v1/compliance/retention-policies', body);
  },

  async listErasureRequests(params?: Record<string, string | number | undefined>): Promise<{ data: ErasureRequestItem[]; total: number }> {
    return api.get('/api/v1/compliance/erasure-requests', params);
  },

  async createErasureRequest(targetUserId: string): Promise<ErasureRequestItem> {
    return api.post('/api/v1/compliance/erasure-requests', { target_user_id: targetUserId });
  },

  async listControlPoints(params?: Record<string, string | number | undefined>): Promise<{ data: ControlPointItem[]; total: number }> {
    return api.get('/api/v1/compliance/control-points', params);
  },

  async createControlPoint(body: { control_id: string; category: string; description: string }): Promise<ControlPointItem> {
    return api.post('/api/v1/compliance/control-points', body);
  },

  async updateControlPoint(id: string, body: { implementation?: string; is_satisfied?: boolean }): Promise<ControlPointItem> {
    return api.put(`/api/v1/compliance/control-points/${id}`, body);
  },
};
