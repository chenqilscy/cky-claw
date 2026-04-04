import { api } from './api';

export interface StepIOSchema {
  input_map?: Record<string, string>;
  output_key?: string;
}

export interface RetryConfigSchema {
  max_retries?: number;
  retry_delay?: number;
}

export interface StepSchema {
  id: string;
  name: string;
  type: 'agent' | 'parallel' | 'conditional' | 'loop';
  agent_name?: string;
  prompt_template?: string;
  max_turns?: number;
  io?: StepIOSchema;
  retry_config?: RetryConfigSchema;
  timeout?: number;
  parallel_step_ids?: string[];
  branches?: Array<{ condition: string; target_step_id: string }>;
  default_target_step_id?: string;
  condition?: string;
  body_step_ids?: string[];
  max_iterations?: number;
}

export interface EdgeSchema {
  id: string;
  source_step_id: string;
  target_step_id: string;
  condition?: string;
}

export interface WorkflowItem {
  id: string;
  name: string;
  description: string;
  steps: StepSchema[];
  edges: EdgeSchema[];
  input_schema: Record<string, string> | null;
  output_keys: string[] | null;
  timeout: number | null;
  guardrail_names: string[] | null;
  metadata: Record<string, unknown> | null;
  created_at: string;
  updated_at: string;
}

export interface WorkflowListResponse {
  items: WorkflowItem[];
  total: number;
}

export interface WorkflowCreateParams {
  name: string;
  description?: string;
  steps: StepSchema[];
  edges: EdgeSchema[];
  input_schema?: Record<string, string>;
  output_keys?: string[];
  timeout?: number;
  guardrail_names?: string[];
  metadata?: Record<string, unknown>;
}

export interface WorkflowUpdateParams {
  name?: string;
  description?: string;
  steps?: StepSchema[];
  edges?: EdgeSchema[];
  input_schema?: Record<string, string>;
  output_keys?: string[];
  timeout?: number;
  guardrail_names?: string[];
  metadata?: Record<string, unknown>;
}

export interface WorkflowValidateResponse {
  valid: boolean;
  errors: string[];
}

export const workflowService = {
  list: (params?: { limit?: number; offset?: number }) => {
    const cleanParams: Record<string, string | number | undefined> = {};
    if (params) {
      if (params.limit !== undefined) cleanParams.limit = params.limit;
      if (params.offset !== undefined) cleanParams.offset = params.offset;
    }
    return api.get<WorkflowListResponse>('/workflows', cleanParams);
  },

  get: (id: string) =>
    api.get<WorkflowItem>(`/workflows/${id}`),

  create: (data: WorkflowCreateParams) =>
    api.post<WorkflowItem>('/workflows', data),

  update: (id: string, data: WorkflowUpdateParams) =>
    api.put<WorkflowItem>(`/workflows/${id}`, data),

  delete: (id: string) =>
    api.delete(`/workflows/${id}`),

  validate: (data: WorkflowCreateParams) =>
    api.post<WorkflowValidateResponse>('/workflows/validate', data),
};
