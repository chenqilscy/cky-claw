import { api } from './api';

export interface BenchmarkSuiteItem {
  id: string;
  name: string;
  description: string;
  agent_name: string;
  model: string;
  config: Record<string, unknown> | null;
  tags: string[] | null;
  created_by: string | null;
  created_at: string;
  updated_at: string;
}

export interface BenchmarkRunItem {
  id: string;
  suite_id: string;
  status: string;
  total_cases: number;
  passed_cases: number;
  failed_cases: number;
  error_cases: number;
  overall_score: number;
  pass_rate: number;
  total_latency_ms: number;
  total_tokens: number;
  dimension_summaries: Record<string, unknown> | null;
  report: Record<string, unknown> | null;
  started_at: string | null;
  finished_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface BenchmarkDashboard {
  total_suites: number;
  total_runs: number;
  completed_runs: number;
  avg_score: number;
  avg_pass_rate: number;
}

export const benchmarkService = {
  async getDashboard(): Promise<BenchmarkDashboard> {
    return api.get('/api/v1/benchmark/dashboard');
  },

  async listSuites(params?: Record<string, string | number | undefined>): Promise<{ data: BenchmarkSuiteItem[]; total: number }> {
    return api.get('/api/v1/benchmark/suites', params);
  },

  async createSuite(body: { name: string; description?: string; agent_name?: string; model?: string; tags?: string[] }): Promise<BenchmarkSuiteItem> {
    return api.post('/api/v1/benchmark/suites', body);
  },

  async getSuite(id: string): Promise<BenchmarkSuiteItem> {
    return api.get(`/api/v1/benchmark/suites/${id}`);
  },

  async updateSuite(id: string, body: Partial<BenchmarkSuiteItem>): Promise<BenchmarkSuiteItem> {
    return api.put(`/api/v1/benchmark/suites/${id}`, body);
  },

  async deleteSuite(id: string): Promise<void> {
    return api.delete(`/api/v1/benchmark/suites/${id}`);
  },

  async listRuns(params?: Record<string, string | number | undefined>): Promise<{ data: BenchmarkRunItem[]; total: number }> {
    return api.get('/api/v1/benchmark/runs', params);
  },

  async createRun(suiteId: string): Promise<BenchmarkRunItem> {
    return api.post('/api/v1/benchmark/runs', { suite_id: suiteId });
  },

  async getRun(id: string): Promise<BenchmarkRunItem> {
    return api.get(`/api/v1/benchmark/runs/${id}`);
  },

  async completeRun(id: string, body: Record<string, unknown>): Promise<BenchmarkRunItem> {
    return api.post(`/api/v1/benchmark/runs/${id}/complete`, body);
  },
};
