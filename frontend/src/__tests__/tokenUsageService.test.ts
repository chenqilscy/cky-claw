/**
 * tokenUsageService 测试。
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

import { tokenUsageService } from '../services/tokenUsageService';
import { api } from '../services/api';

const mockApi = api as unknown as {
  get: ReturnType<typeof vi.fn>;
};

describe('tokenUsageService', () => {
  beforeEach(() => { vi.clearAllMocks(); });
  afterEach(() => { vi.restoreAllMocks(); });

  it('list 调用 GET /token-usage', async () => {
    const data = { data: [], total: 0, limit: 20, offset: 0 };
    mockApi.get.mockResolvedValue(data);
    const result = await tokenUsageService.list({ agent_name: 'bot', limit: 10 });
    expect(mockApi.get).toHaveBeenCalledWith('/token-usage', { agent_name: 'bot', limit: 10 });
    expect(result).toEqual(data);
  });

  it('list 无参数时传 undefined', async () => {
    mockApi.get.mockResolvedValue({ data: [], total: 0 });
    await tokenUsageService.list();
    expect(mockApi.get).toHaveBeenCalledWith('/token-usage', undefined);
  });

  it('summary 调用 GET /token-usage/summary', async () => {
    const data = { data: [] };
    mockApi.get.mockResolvedValue(data);
    const result = await tokenUsageService.summary({ group_by: 'model' });
    expect(mockApi.get).toHaveBeenCalledWith('/token-usage/summary', { group_by: 'model' });
    expect(result).toEqual(data);
  });

  it('summary 无参数时传 undefined', async () => {
    mockApi.get.mockResolvedValue({ data: [] });
    await tokenUsageService.summary();
    expect(mockApi.get).toHaveBeenCalledWith('/token-usage/summary', undefined);
  });
});
