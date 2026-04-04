import { describe, it, expect, vi, beforeEach } from 'vitest';
import { roleService } from '../services/roleService';
import * as apiModule from '../services/api';

vi.mock('../services/api', () => ({
  api: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    delete: vi.fn(),
  },
}));

const mockApi = apiModule.api as unknown as {
  get: ReturnType<typeof vi.fn>;
  post: ReturnType<typeof vi.fn>;
  put: ReturnType<typeof vi.fn>;
  delete: ReturnType<typeof vi.fn>;
};

beforeEach(() => {
  vi.clearAllMocks();
});

describe('roleService', () => {
  it('list fetches /roles', async () => {
    const data = { items: [], total: 0 };
    mockApi.get.mockResolvedValue(data);
    const result = await roleService.list({ limit: 50 });
    expect(mockApi.get).toHaveBeenCalledWith('/roles', { limit: 50 });
    expect(result).toEqual(data);
  });

  it('get fetches /roles/:id', async () => {
    const role = { id: '1', name: 'admin' };
    mockApi.get.mockResolvedValue(role);
    const result = await roleService.get('1');
    expect(mockApi.get).toHaveBeenCalledWith('/roles/1');
    expect(result).toEqual(role);
  });

  it('create posts to /roles', async () => {
    const params = { name: 'dev', permissions: { agents: ['read'] } };
    mockApi.post.mockResolvedValue({ id: '2', ...params });
    await roleService.create(params);
    expect(mockApi.post).toHaveBeenCalledWith('/roles', params);
  });

  it('update puts to /roles/:id', async () => {
    mockApi.put.mockResolvedValue({});
    await roleService.update('1', { description: 'updated' });
    expect(mockApi.put).toHaveBeenCalledWith('/roles/1', { description: 'updated' });
  });

  it('delete calls delete /roles/:id', async () => {
    mockApi.delete.mockResolvedValue(undefined);
    await roleService.delete('1');
    expect(mockApi.delete).toHaveBeenCalledWith('/roles/1');
  });

  it('assignRole posts to /roles/:roleId/assign/:userId', async () => {
    mockApi.post.mockResolvedValue({ message: 'ok' });
    await roleService.assignRole('r1', 'u1');
    expect(mockApi.post).toHaveBeenCalledWith('/roles/r1/assign/u1', {});
  });
});
