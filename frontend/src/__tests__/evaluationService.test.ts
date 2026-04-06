/**
 * evaluationService 测试。
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

vi.mock('../services/api', () => ({
  api: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    delete: vi.fn(),
  },
}));

import {
  listEvaluations,
  getEvaluation,
  createEvaluation,
  getAgentQuality,
  listFeedbacks,
  createFeedback,
} from '../services/evaluationService';
import { api } from '../services/api';

const mockApi = api as unknown as {
  get: ReturnType<typeof vi.fn>;
  post: ReturnType<typeof vi.fn>;
};

describe('evaluationService', () => {
  beforeEach(() => { vi.clearAllMocks(); });
  afterEach(() => { vi.restoreAllMocks(); });

  it('listEvaluations 调用 GET /api/v1/evaluations', async () => {
    const data = { data: [], total: 0, limit: 20, offset: 0 };
    mockApi.get.mockResolvedValue(data);
    const result = await listEvaluations({ agent_id: 'a1', limit: 10 });
    expect(mockApi.get).toHaveBeenCalledWith('/api/v1/evaluations', { agent_id: 'a1', limit: 10 });
    expect(result).toEqual(data);
  });

  it('getEvaluation 调用 GET /api/v1/evaluations/:id', async () => {
    const evaluation = { id: 'e1', overall_score: 0.9 };
    mockApi.get.mockResolvedValue(evaluation);
    const result = await getEvaluation('e1');
    expect(mockApi.get).toHaveBeenCalledWith('/api/v1/evaluations/e1');
    expect(result).toEqual(evaluation);
  });

  it('createEvaluation 调用 POST /api/v1/evaluations', async () => {
    const input = { run_id: 'r1', accuracy: 0.95 };
    mockApi.post.mockResolvedValue({ id: 'e1', ...input });
    const result = await createEvaluation(input);
    expect(mockApi.post).toHaveBeenCalledWith('/api/v1/evaluations', input);
    expect(result).toEqual({ id: 'e1', ...input });
  });

  it('getAgentQuality 调用 GET /api/v1/evaluations/agents/:id/quality', async () => {
    const quality = { agent_id: 'a1', avg_overall: 0.85 };
    mockApi.get.mockResolvedValue(quality);
    const result = await getAgentQuality('a1');
    expect(mockApi.get).toHaveBeenCalledWith('/api/v1/evaluations/agents/a1/quality');
    expect(result).toEqual(quality);
  });

  it('listFeedbacks 调用 GET /api/v1/evaluations/feedbacks', async () => {
    const data = { data: [], total: 0 };
    mockApi.get.mockResolvedValue(data);
    const result = await listFeedbacks({ run_id: 'r1' });
    expect(mockApi.get).toHaveBeenCalledWith('/api/v1/evaluations/feedbacks', { run_id: 'r1' });
    expect(result).toEqual(data);
  });

  it('createFeedback 调用 POST /api/v1/evaluations/feedbacks', async () => {
    const input = { run_id: 'r1', rating: 5, comment: 'great' };
    mockApi.post.mockResolvedValue({ id: 'f1', ...input });
    const result = await createFeedback(input);
    expect(mockApi.post).toHaveBeenCalledWith('/api/v1/evaluations/feedbacks', input);
    expect(result).toEqual({ id: 'f1', ...input });
  });
});
