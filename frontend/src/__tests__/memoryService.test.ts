/**
 * memoryService 测试。
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

import { memoryService } from '../services/memoryService';
import { api } from '../services/api';

const mockApi = api as unknown as {
  get: ReturnType<typeof vi.fn>;
  post: ReturnType<typeof vi.fn>;
  put: ReturnType<typeof vi.fn>;
  delete: ReturnType<typeof vi.fn>;
};

describe('memoryService', () => {
  beforeEach(() => { vi.clearAllMocks(); });
  afterEach(() => { vi.restoreAllMocks(); });

  it('list 调用 GET /memories', async () => {
    const data = { data: [], total: 0 };
    mockApi.get.mockResolvedValue(data);
    const result = await memoryService.list({ user_id: 'u1' });
    expect(mockApi.get).toHaveBeenCalledWith('/memories', { user_id: 'u1' });
    expect(result).toEqual(data);
  });

  it('list 过滤 undefined 和空字符串参数', async () => {
    mockApi.get.mockResolvedValue({ data: [], total: 0 });
    await memoryService.list({ user_id: 'u1', agent_name: '', type: undefined });
    expect(mockApi.get).toHaveBeenCalledWith('/memories', { user_id: 'u1' });
  });

  it('get 调用 GET /memories/:id', async () => {
    mockApi.get.mockResolvedValue({ id: 'm1' });
    const result = await memoryService.get('m1');
    expect(mockApi.get).toHaveBeenCalledWith('/memories/m1');
    expect(result).toEqual({ id: 'm1' });
  });

  it('create 调用 POST /memories', async () => {
    const input = { type: 'fact', content: 'test', user_id: 'u1' };
    mockApi.post.mockResolvedValue({ id: '1', ...input });
    const result = await memoryService.create(input);
    expect(mockApi.post).toHaveBeenCalledWith('/memories', input);
    expect(result).toEqual({ id: '1', ...input });
  });

  it('update 调用 PUT /memories/:id', async () => {
    const update = { content: 'updated' };
    mockApi.put.mockResolvedValue({ id: '1', ...update });
    await memoryService.update('1', update);
    expect(mockApi.put).toHaveBeenCalledWith('/memories/1', update);
  });

  it('delete 调用 DELETE /memories/:id', async () => {
    mockApi.delete.mockResolvedValue(undefined);
    await memoryService.delete('m1');
    expect(mockApi.delete).toHaveBeenCalledWith('/memories/m1');
  });

  it('deleteByUser 调用 DELETE /memories/user/:userId', async () => {
    mockApi.delete.mockResolvedValue({ deleted: 5 });
    const result = await memoryService.deleteByUser('u1');
    expect(mockApi.delete).toHaveBeenCalledWith('/memories/user/u1');
    expect(result).toEqual({ deleted: 5 });
  });

  it('search 调用 POST /memories/search', async () => {
    const params = { user_id: 'u1', query: 'test' };
    mockApi.post.mockResolvedValue([]);
    const result = await memoryService.search(params);
    expect(mockApi.post).toHaveBeenCalledWith('/memories/search', params);
    expect(result).toEqual([]);
  });

  it('decay 调用 POST /memories/decay', async () => {
    const params = { before: '2024-01-01', rate: 0.1 };
    mockApi.post.mockResolvedValue({ affected: 10 });
    const result = await memoryService.decay(params);
    expect(mockApi.post).toHaveBeenCalledWith('/memories/decay', params);
    expect(result).toEqual({ affected: 10 });
  });
});
