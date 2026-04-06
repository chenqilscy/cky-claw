/**
 * traceService 测试。
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

import { traceService } from '../services/traceService';
import { api } from '../services/api';

const mockApi = api as unknown as {
  get: ReturnType<typeof vi.fn>;
  post: ReturnType<typeof vi.fn>;
  put: ReturnType<typeof vi.fn>;
  delete: ReturnType<typeof vi.fn>;
};

describe('traceService', () => {
  beforeEach(() => { vi.clearAllMocks(); });
  afterEach(() => { vi.restoreAllMocks(); });

  it('list 调用 GET /traces', async () => {
    const data = { data: [], total: 0 };
    mockApi.get.mockResolvedValue(data);
    const result = await traceService.list({ limit: 20 });
    expect(mockApi.get).toHaveBeenCalledWith('/traces', { limit: 20 });
    expect(result).toEqual(data);
  });

  it('detail 调用 GET /traces/:id', async () => {
    const trace = { id: 't1', agent_name: 'test' };
    mockApi.get.mockResolvedValue(trace);
    const result = await traceService.detail('t1');
    expect(mockApi.get).toHaveBeenCalledWith('/traces/t1');
    expect(result).toEqual(trace);
  });

  it('stats 调用 GET /traces/stats', async () => {
    const stats = { total_traces: 100 };
    mockApi.get.mockResolvedValue(stats);
    const result = await traceService.stats({ days: 7 } as Record<string, unknown>);
    expect(mockApi.get).toHaveBeenCalledWith('/traces/stats', { days: 7 });
    expect(result).toEqual(stats);
  });

  it('listSpans 调用 GET /traces/spans', async () => {
    const spans = { data: [], total: 0 };
    mockApi.get.mockResolvedValue(spans);
    const result = await traceService.listSpans({ trace_id: 't1', limit: 50 });
    expect(mockApi.get).toHaveBeenCalledWith('/traces/spans', { trace_id: 't1', limit: 50 });
    expect(result).toEqual(spans);
  });
});
