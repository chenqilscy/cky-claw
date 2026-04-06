/**
 * approvalService 测试。
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

import { approvalService } from '../services/approvalService';
import { api } from '../services/api';

const mockApi = api as unknown as {
  get: ReturnType<typeof vi.fn>;
  post: ReturnType<typeof vi.fn>;
  put: ReturnType<typeof vi.fn>;
  delete: ReturnType<typeof vi.fn>;
};

describe('approvalService', () => {
  beforeEach(() => { vi.clearAllMocks(); });
  afterEach(() => { vi.restoreAllMocks(); });

  it('list 调用 GET /approvals', async () => {
    const data = { data: [], total: 0 };
    mockApi.get.mockResolvedValue(data);
    const result = await approvalService.list();
    expect(mockApi.get).toHaveBeenCalledWith('/approvals', {});
    expect(result).toEqual(data);
  });

  it('list 过滤空值参数', async () => {
    mockApi.get.mockResolvedValue({ data: [], total: 0 });
    await approvalService.list({ status: 'pending', agent_name: undefined });
    expect(mockApi.get).toHaveBeenCalledWith('/approvals', { status: 'pending' });
  });

  it('get 调用 GET /approvals/:id', async () => {
    const approval = { id: 'a1', status: 'pending' };
    mockApi.get.mockResolvedValue(approval);
    const result = await approvalService.get('a1');
    expect(mockApi.get).toHaveBeenCalledWith('/approvals/a1');
    expect(result).toEqual(approval);
  });

  it('resolve 调用 POST /approvals/:id/resolve', async () => {
    const resolved = { id: 'a1', status: 'approved' };
    mockApi.post.mockResolvedValue(resolved);
    const result = await approvalService.resolve('a1', { action: 'approve' });
    expect(mockApi.post).toHaveBeenCalledWith('/approvals/a1/resolve', { action: 'approve' });
    expect(result).toEqual(resolved);
  });
});
