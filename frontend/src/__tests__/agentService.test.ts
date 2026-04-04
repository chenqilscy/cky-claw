/**
 * agentService 测试。
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

// Mock api module
vi.mock('../services/api', () => ({
  api: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    delete: vi.fn(),
  },
  ApiError: class extends Error {
    status: number;
    code: string;
    constructor(status: number, code: string, message: string) {
      super(message);
      this.status = status;
      this.code = code;
    }
  },
  getToken: vi.fn(() => 'token'),
  buildUrl: vi.fn((p: string) => p),
  API_BASE: '/api/v1',
}));

import { agentService } from '../services/agentService';
import { api } from '../services/api';

const mockApi = api as unknown as {
  get: ReturnType<typeof vi.fn>;
  post: ReturnType<typeof vi.fn>;
  put: ReturnType<typeof vi.fn>;
  delete: ReturnType<typeof vi.fn>;
};

describe('agentService', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('list 调用 GET /agents', async () => {
    const mockData = { data: [], total: 0, limit: 20, offset: 0 };
    mockApi.get.mockResolvedValue(mockData);

    const result = await agentService.list({ limit: 10, offset: 0 });

    expect(mockApi.get).toHaveBeenCalledWith('/agents', { limit: 10, offset: 0 });
    expect(result).toEqual(mockData);
  });

  it('list 无参数也可调用', async () => {
    mockApi.get.mockResolvedValue({ data: [], total: 0, limit: 20, offset: 0 });

    await agentService.list();

    expect(mockApi.get).toHaveBeenCalledWith('/agents', undefined);
  });

  it('get 调用 GET /agents/{name}', async () => {
    const mockAgent = { id: '1', name: 'test-agent' };
    mockApi.get.mockResolvedValue(mockAgent);

    const result = await agentService.get('test-agent');

    expect(mockApi.get).toHaveBeenCalledWith('/agents/test-agent');
    expect(result).toEqual(mockAgent);
  });

  it('get 对 Agent 名称进行 URI 编码', async () => {
    mockApi.get.mockResolvedValue({});

    await agentService.get('my agent');

    expect(mockApi.get).toHaveBeenCalledWith('/agents/my%20agent');
  });

  it('create 调用 POST /agents', async () => {
    const input = { name: 'new-agent', description: 'desc' };
    const mockCreated = { id: '2', ...input };
    mockApi.post.mockResolvedValue(mockCreated);

    const result = await agentService.create(input);

    expect(mockApi.post).toHaveBeenCalledWith('/agents', input);
    expect(result).toEqual(mockCreated);
  });

  it('update 调用 PUT /agents/{name}', async () => {
    const update = { description: 'updated' };
    mockApi.put.mockResolvedValue({ name: 'a', ...update });

    await agentService.update('a', update);

    expect(mockApi.put).toHaveBeenCalledWith('/agents/a', update);
  });

  it('delete 调用 DELETE /agents/{name}', async () => {
    mockApi.delete.mockResolvedValue(undefined);

    await agentService.delete('old-agent');

    expect(mockApi.delete).toHaveBeenCalledWith('/agents/old-agent');
  });
});
