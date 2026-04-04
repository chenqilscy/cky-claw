/**
 * workflowService 测试。
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

import { workflowService } from '../services/workflowService';
import { api } from '../services/api';

const mockApi = api as unknown as {
  get: ReturnType<typeof vi.fn>;
  post: ReturnType<typeof vi.fn>;
  put: ReturnType<typeof vi.fn>;
  delete: ReturnType<typeof vi.fn>;
};

describe('workflowService', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('list 调用 GET /workflows', async () => {
    const mockData = { items: [], total: 0 };
    mockApi.get.mockResolvedValue(mockData);

    const result = await workflowService.list({ limit: 10, offset: 0 });

    expect(mockApi.get).toHaveBeenCalledWith('/workflows', { limit: 10, offset: 0 });
    expect(result).toEqual(mockData);
  });

  it('list 无参数可调用', async () => {
    mockApi.get.mockResolvedValue({ items: [], total: 0 });

    await workflowService.list();

    expect(mockApi.get).toHaveBeenCalledWith('/workflows', {});
  });

  it('get 调用 GET /workflows/{id}', async () => {
    const mock = { id: 'wf-1', name: 'test-wf' };
    mockApi.get.mockResolvedValue(mock);

    const result = await workflowService.get('wf-1');

    expect(mockApi.get).toHaveBeenCalledWith('/workflows/wf-1');
    expect(result).toEqual(mock);
  });

  it('create 调用 POST /workflows', async () => {
    const input = { name: 'new-wf', steps: [], edges: [] };
    mockApi.post.mockResolvedValue({ id: '1', ...input });

    const result = await workflowService.create(input);

    expect(mockApi.post).toHaveBeenCalledWith('/workflows', input);
    expect(result.name).toBe('new-wf');
  });

  it('update 调用 PUT /workflows/{id}', async () => {
    const update = { description: 'updated' };
    mockApi.put.mockResolvedValue({ id: '1', ...update });

    await workflowService.update('1', update);

    expect(mockApi.put).toHaveBeenCalledWith('/workflows/1', update);
  });

  it('delete 调用 DELETE /workflows/{id}', async () => {
    mockApi.delete.mockResolvedValue(undefined);

    await workflowService.delete('old-wf');

    expect(mockApi.delete).toHaveBeenCalledWith('/workflows/old-wf');
  });

  it('validate 调用 POST /workflows/validate', async () => {
    const input = { name: 'test', steps: [], edges: [] };
    mockApi.post.mockResolvedValue({ valid: true, errors: [] });

    const result = await workflowService.validate(input);

    expect(mockApi.post).toHaveBeenCalledWith('/workflows/validate', input);
    expect(result.valid).toBe(true);
  });

  it('validate 返回错误信息', async () => {
    const input = { name: 'test', steps: [], edges: [] };
    mockApi.post.mockResolvedValue({ valid: false, errors: ['循环依赖'] });

    const result = await workflowService.validate(input);

    expect(result.valid).toBe(false);
    expect(result.errors).toContain('循环依赖');
  });
});
