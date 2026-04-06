/**
 * apmService 测试。
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

import { apmService } from '../services/apmService';
import { api } from '../services/api';

const mockApi = api as unknown as {
  get: ReturnType<typeof vi.fn>;
};

describe('apmService', () => {
  beforeEach(() => { vi.clearAllMocks(); });
  afterEach(() => { vi.restoreAllMocks(); });

  it('dashboard 默认查询 30 天', async () => {
    const data = { overview: {}, agent_ranking: [], model_usage: [], daily_trend: [], tool_usage: [] };
    mockApi.get.mockResolvedValue(data);
    const result = await apmService.dashboard();
    expect(mockApi.get).toHaveBeenCalledWith('/apm/dashboard?days=30');
    expect(result).toEqual(data);
  });

  it('dashboard 自定义天数', async () => {
    mockApi.get.mockResolvedValue({});
    await apmService.dashboard(7);
    expect(mockApi.get).toHaveBeenCalledWith('/apm/dashboard?days=7');
  });
});
