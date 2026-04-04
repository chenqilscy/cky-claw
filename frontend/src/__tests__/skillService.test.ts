/**
 * skillService 测试。
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

import { skillService } from '../services/skillService';
import { api } from '../services/api';

const mockApi = api as unknown as {
  get: ReturnType<typeof vi.fn>;
  post: ReturnType<typeof vi.fn>;
  put: ReturnType<typeof vi.fn>;
  delete: ReturnType<typeof vi.fn>;
};

describe('skillService', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('list 调用 GET /skills', async () => {
    const mockData = { items: [], total: 0 };
    mockApi.get.mockResolvedValue(mockData);

    const result = await skillService.list({ limit: 10, offset: 0 });

    expect(mockApi.get).toHaveBeenCalledWith('/skills', { limit: 10, offset: 0 });
    expect(result).toEqual(mockData);
  });

  it('list 过滤空值参数', async () => {
    mockApi.get.mockResolvedValue({ items: [], total: 0 });

    await skillService.list({ limit: 20, offset: undefined });

    expect(mockApi.get).toHaveBeenCalledWith('/skills', { limit: 20 });
  });

  it('get 调用 GET /skills/{id}', async () => {
    const mockSkill = { id: 'abc', name: 'test-skill' };
    mockApi.get.mockResolvedValue(mockSkill);

    const result = await skillService.get('abc');

    expect(mockApi.get).toHaveBeenCalledWith('/skills/abc');
    expect(result).toEqual(mockSkill);
  });

  it('create 调用 POST /skills', async () => {
    const input = { name: 'new-skill', content: 'content here' };
    const mockCreated = { id: '1', ...input };
    mockApi.post.mockResolvedValue(mockCreated);

    const result = await skillService.create(input);

    expect(mockApi.post).toHaveBeenCalledWith('/skills', input);
    expect(result).toEqual(mockCreated);
  });

  it('update 调用 PUT /skills/{id}', async () => {
    const update = { description: 'updated desc' };
    mockApi.put.mockResolvedValue({ id: '1', ...update });

    await skillService.update('1', update);

    expect(mockApi.put).toHaveBeenCalledWith('/skills/1', update);
  });

  it('delete 调用 DELETE /skills/{id}', async () => {
    mockApi.delete.mockResolvedValue(undefined);

    await skillService.delete('old-skill');

    expect(mockApi.delete).toHaveBeenCalledWith('/skills/old-skill');
  });

  it('search 调用 POST /skills/search', async () => {
    const params = { query: 'test', category: 'public' };
    mockApi.post.mockResolvedValue([]);

    const result = await skillService.search(params);

    expect(mockApi.post).toHaveBeenCalledWith('/skills/search', params);
    expect(result).toEqual([]);
  });

  it('findForAgent 调用 GET /skills/for-agent/{name}', async () => {
    mockApi.get.mockResolvedValue([]);

    const result = await skillService.findForAgent('my-agent');

    expect(mockApi.get).toHaveBeenCalledWith('/skills/for-agent/my-agent');
    expect(result).toEqual([]);
  });

  it('findForAgent 对 agent 名称进行 URI 编码', async () => {
    mockApi.get.mockResolvedValue([]);

    await skillService.findForAgent('agent with space');

    expect(mockApi.get).toHaveBeenCalledWith('/skills/for-agent/agent%20with%20space');
  });
});
