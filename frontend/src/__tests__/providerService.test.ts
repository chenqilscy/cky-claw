/**
 * providerService 测试。
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

import { providerService } from '../services/providerService';
import { api } from '../services/api';

const mockApi = api as unknown as {
  get: ReturnType<typeof vi.fn>;
  post: ReturnType<typeof vi.fn>;
  put: ReturnType<typeof vi.fn>;
  delete: ReturnType<typeof vi.fn>;
};

describe('providerService', () => {
  beforeEach(() => { vi.clearAllMocks(); });
  afterEach(() => { vi.restoreAllMocks(); });

  it('list 调用 GET /providers', async () => {
    const data = { data: [], total: 0 };
    mockApi.get.mockResolvedValue(data);
    const result = await providerService.list();
    expect(mockApi.get).toHaveBeenCalledWith('/providers', undefined);
    expect(result).toEqual(data);
  });

  it('list 传递查询参数', async () => {
    mockApi.get.mockResolvedValue({ data: [], total: 0 });
    await providerService.list({ provider_type: 'openai', is_enabled: true });
    expect(mockApi.get).toHaveBeenCalledWith('/providers', { provider_type: 'openai', is_enabled: true });
  });

  it('get 调用 GET /providers/:id', async () => {
    const provider = { id: 'p1', name: 'test' };
    mockApi.get.mockResolvedValue(provider);
    const result = await providerService.get('p1');
    expect(mockApi.get).toHaveBeenCalledWith('/providers/p1');
    expect(result).toEqual(provider);
  });

  it('create 调用 POST /providers', async () => {
    const input = { name: 'new', provider_type: 'openai', config: {}, base_url: 'https://api.openai.com', api_key: 'sk-xxx' };
    const created = { id: '1', ...input };
    mockApi.post.mockResolvedValue(created);
    const result = await providerService.create(input);
    expect(mockApi.post).toHaveBeenCalledWith('/providers', input);
    expect(result).toEqual(created);
  });

  it('update 调用 PUT /providers/:id', async () => {
    const update = { name: 'updated' };
    mockApi.put.mockResolvedValue({ id: '1', ...update });
    await providerService.update('1', update);
    expect(mockApi.put).toHaveBeenCalledWith('/providers/1', update);
  });

  it('delete 调用 DELETE /providers/:id', async () => {
    mockApi.delete.mockResolvedValue(undefined);
    await providerService.delete('1');
    expect(mockApi.delete).toHaveBeenCalledWith('/providers/1');
  });

  it('toggle 调用 PUT /providers/:id/toggle', async () => {
    mockApi.put.mockResolvedValue({ id: '1', is_enabled: false });
    await providerService.toggle('1', false);
    expect(mockApi.put).toHaveBeenCalledWith('/providers/1/toggle', { is_enabled: false });
  });

  it('testConnection 调用 POST /providers/:id/test', async () => {
    const result = { success: true };
    mockApi.post.mockResolvedValue(result);
    const resp = await providerService.testConnection('1');
    expect(mockApi.post).toHaveBeenCalledWith('/providers/1/test');
    expect(resp).toEqual(result);
  });
});
