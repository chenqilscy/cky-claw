/**
 * agentVersionService 测试。
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

import { agentVersionService } from '../services/agentVersionService';
import { api } from '../services/api';

const mockApi = api as unknown as {
  get: ReturnType<typeof vi.fn>;
  post: ReturnType<typeof vi.fn>;
};

describe('agentVersionService', () => {
  beforeEach(() => { vi.clearAllMocks(); });
  afterEach(() => { vi.restoreAllMocks(); });

  it('list 调用 GET /agents/:id/versions', async () => {
    const data = { data: [], total: 0 };
    mockApi.get.mockResolvedValue(data);
    const result = await agentVersionService.list('agent-1', { limit: 10, offset: 0 });
    expect(mockApi.get).toHaveBeenCalledWith('/agents/agent-1/versions', { limit: 10, offset: 0 });
    expect(result).toEqual(data);
  });

  it('get 调用 GET /agents/:id/versions/:version', async () => {
    const version = { id: 'v1', version: 3 };
    mockApi.get.mockResolvedValue(version);
    const result = await agentVersionService.get('agent-1', 3);
    expect(mockApi.get).toHaveBeenCalledWith('/agents/agent-1/versions/3');
    expect(result).toEqual(version);
  });

  it('rollback 无 changeSummary 时不传 body', async () => {
    mockApi.post.mockResolvedValue({ id: 'v1', version: 2 });
    await agentVersionService.rollback('agent-1', 2);
    expect(mockApi.post).toHaveBeenCalledWith('/agents/agent-1/versions/2/rollback', undefined);
  });

  it('rollback 有 changeSummary 时传 body', async () => {
    mockApi.post.mockResolvedValue({ id: 'v1', version: 2 });
    await agentVersionService.rollback('agent-1', 2, '紧急回滚');
    expect(mockApi.post).toHaveBeenCalledWith('/agents/agent-1/versions/2/rollback', { change_summary: '紧急回滚' });
  });

  it('diff 调用 GET /agents/:id/versions/diff', async () => {
    const diff = { version_a: 1, version_b: 3 };
    mockApi.get.mockResolvedValue(diff);
    const result = await agentVersionService.diff('agent-1', 1, 3);
    expect(mockApi.get).toHaveBeenCalledWith('/agents/agent-1/versions/diff', { v1: 1, v2: 3 });
    expect(result).toEqual(diff);
  });
});
