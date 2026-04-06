/**
 * toolGroupService 测试。
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

import { toolGroupService } from '../services/toolGroupService';
import { api } from '../services/api';

const mockApi = api as unknown as {
  get: ReturnType<typeof vi.fn>;
  post: ReturnType<typeof vi.fn>;
  put: ReturnType<typeof vi.fn>;
  delete: ReturnType<typeof vi.fn>;
};

describe('toolGroupService', () => {
  beforeEach(() => { vi.clearAllMocks(); });
  afterEach(() => { vi.restoreAllMocks(); });

  it('list 调用 GET /tool-groups', async () => {
    const data = { data: [], total: 0 };
    mockApi.get.mockResolvedValue(data);
    const result = await toolGroupService.list();
    expect(mockApi.get).toHaveBeenCalledWith('/tool-groups');
    expect(result).toEqual(data);
  });

  it('get 按 name 调用 GET /tool-groups/:name', async () => {
    const group = { id: '1', name: 'web-tools' };
    mockApi.get.mockResolvedValue(group);
    const result = await toolGroupService.get('web-tools');
    expect(mockApi.get).toHaveBeenCalledWith('/tool-groups/web-tools');
    expect(result).toEqual(group);
  });

  it('create 调用 POST /tool-groups', async () => {
    const input = { name: 'new-group', tools: [] };
    mockApi.post.mockResolvedValue({ id: '1', ...input });
    const result = await toolGroupService.create(input);
    expect(mockApi.post).toHaveBeenCalledWith('/tool-groups', input);
    expect(result).toEqual({ id: '1', ...input });
  });

  it('update 按 name 调用 PUT /tool-groups/:name', async () => {
    const update = { description: 'updated' };
    mockApi.put.mockResolvedValue({ name: 'grp', ...update });
    await toolGroupService.update('grp', update);
    expect(mockApi.put).toHaveBeenCalledWith('/tool-groups/grp', update);
  });

  it('delete 按 name 调用 DELETE /tool-groups/:name', async () => {
    mockApi.delete.mockResolvedValue(undefined);
    await toolGroupService.delete('old-group');
    expect(mockApi.delete).toHaveBeenCalledWith('/tool-groups/old-group');
  });
});
