/**
 * organizationService 测试。
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

import { organizationService } from '../services/organizationService';
import { api } from '../services/api';

const mockApi = api as unknown as {
  get: ReturnType<typeof vi.fn>;
  post: ReturnType<typeof vi.fn>;
  put: ReturnType<typeof vi.fn>;
  delete: ReturnType<typeof vi.fn>;
};

describe('organizationService', () => {
  beforeEach(() => { vi.clearAllMocks(); });
  afterEach(() => { vi.restoreAllMocks(); });

  it('list 调用 GET /organizations', async () => {
    const data = { data: [], total: 0 };
    mockApi.get.mockResolvedValue(data);
    const result = await organizationService.list({ search: 'test' });
    expect(mockApi.get).toHaveBeenCalledWith('/organizations', { search: 'test' });
    expect(result).toEqual(data);
  });

  it('get 调用 GET /organizations/:id', async () => {
    mockApi.get.mockResolvedValue({ id: 'o1', name: 'org' });
    const result = await organizationService.get('o1');
    expect(mockApi.get).toHaveBeenCalledWith('/organizations/o1');
    expect(result).toEqual({ id: 'o1', name: 'org' });
  });

  it('create 调用 POST /organizations', async () => {
    const input = { name: 'new-org', slug: 'new-org' };
    mockApi.post.mockResolvedValue({ id: '1', ...input });
    const result = await organizationService.create(input);
    expect(mockApi.post).toHaveBeenCalledWith('/organizations', input);
    expect(result).toEqual({ id: '1', ...input });
  });

  it('update 调用 PUT /organizations/:id', async () => {
    const update = { name: 'updated' };
    mockApi.put.mockResolvedValue({ id: '1', ...update });
    await organizationService.update('1', update);
    expect(mockApi.put).toHaveBeenCalledWith('/organizations/1', update);
  });

  it('delete 调用 DELETE /organizations/:id', async () => {
    mockApi.delete.mockResolvedValue(undefined);
    await organizationService.delete('o1');
    expect(mockApi.delete).toHaveBeenCalledWith('/organizations/o1');
  });
});
