/**
 * agentLocaleService 测试。
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

import { agentLocaleService } from '../services/agentLocaleService';
import { api } from '../services/api';

const mockApi = api as unknown as {
  get: ReturnType<typeof vi.fn>;
  post: ReturnType<typeof vi.fn>;
  put: ReturnType<typeof vi.fn>;
  delete: ReturnType<typeof vi.fn>;
};

describe('agentLocaleService', () => {
  beforeEach(() => { vi.clearAllMocks(); });
  afterEach(() => { vi.restoreAllMocks(); });

  it('list 调用 GET /agents/:name/locales', async () => {
    const data = { data: [] };
    mockApi.get.mockResolvedValue(data);
    const result = await agentLocaleService.list('my-agent');
    expect(mockApi.get).toHaveBeenCalledWith('/agents/my-agent/locales');
    expect(result).toEqual(data);
  });

  it('list 对 agent 名称进行 URI 编码', async () => {
    mockApi.get.mockResolvedValue({ data: [] });
    await agentLocaleService.list('agent with space');
    expect(mockApi.get).toHaveBeenCalledWith('/agents/agent%20with%20space/locales');
  });

  it('create 调用 POST /agents/:name/locales', async () => {
    const input = { locale: 'zh-CN', instructions: '你好' };
    mockApi.post.mockResolvedValue({ id: '1', ...input });
    const result = await agentLocaleService.create('bot', input);
    expect(mockApi.post).toHaveBeenCalledWith('/agents/bot/locales', input);
    expect(result).toEqual({ id: '1', ...input });
  });

  it('update 调用 PUT /agents/:name/locales/:locale', async () => {
    const update = { instructions: 'updated' };
    mockApi.put.mockResolvedValue({ id: '1', ...update });
    await agentLocaleService.update('bot', 'zh-CN', update);
    expect(mockApi.put).toHaveBeenCalledWith('/agents/bot/locales/zh-CN', update);
  });

  it('delete 调用 DELETE /agents/:name/locales/:locale', async () => {
    mockApi.delete.mockResolvedValue(undefined);
    await agentLocaleService.delete('bot', 'en-US');
    expect(mockApi.delete).toHaveBeenCalledWith('/agents/bot/locales/en-US');
  });
});
