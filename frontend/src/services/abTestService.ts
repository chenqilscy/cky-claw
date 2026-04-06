import { api } from './api';

export interface ABTestModelResult {
  model: string;
  output: string;
  latency_ms: number;
  token_usage: Record<string, number>;
  error: string | null;
}

export interface ABTestResponse {
  prompt: string;
  results: ABTestModelResult[];
}

export interface ABTestRequest {
  prompt: string;
  models: string[];
  provider_name?: string;
  max_tokens?: number;
}

export const abTestService = {
  run: (data: ABTestRequest) =>
    api.post<ABTestResponse>('/ab-test', data),
};
