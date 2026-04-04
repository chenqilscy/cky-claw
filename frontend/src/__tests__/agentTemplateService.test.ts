/**
 * agentTemplateService 测试。
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

import { agentTemplateService } from '../services/agentTemplateService';
import { api } from '../services/api';

const mockApi = api as unknown as {
  get: ReturnType<typeof vi.fn>;
  post: ReturnType<typeof vi.fn>;
  put: ReturnType<typeof vi.fn>;
  delete: ReturnType<typeof vi.fn>;
};

describe('agentTemplateService', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('list 调用 GET /agent-templates', async () => {
    const mockData = { items: [], total: 0 };
    mockApi.get.mockResolvedValue(mockData);

    const result = await agentTemplateService.list({ limit: 10, offset: 0 });

    expect(mockApi.get).toHaveBeenCalledWith('/agent-templates', { limit: 10, offset: 0 });
    expect(result).toEqual(mockData);
  });

  it('list 过滤空值和空字符串参数', async () => {
    mockApi.get.mockResolvedValue({ items: [], total: 0 });

    await agentTemplateService.list({ limit: 20, category: '' });

    expect(mockApi.get).toHaveBeenCalledWith('/agent-templates', { limit: 20 });
  });

  it('get 调用 GET /agent-templates/{id}', async () => {
    const mock = { id: 'abc', name: 'tpl-1' };
    mockApi.get.mockResolvedValue(mock);

    const result = await agentTemplateService.get('abc');

    expect(mockApi.get).toHaveBeenCalledWith('/agent-templates/abc');
    expect(result).toEqual(mock);
  });

  it('create 调用 POST /agent-templates', async () => {
    const input = { name: 'new-tpl', display_name: 'New' };
    mockApi.post.mockResolvedValue({ id: '1', ...input });

    const result = await agentTemplateService.create(input);

    expect(mockApi.post).toHaveBeenCalledWith('/agent-templates', input);
    expect(result.name).toBe('new-tpl');
  });

  it('update 调用 PUT /agent-templates/{id}', async () => {
    const update = { description: 'updated' };
    mockApi.put.mockResolvedValue({ id: '1', ...update });

    await agentTemplateService.update('1', update);

    expect(mockApi.put).toHaveBeenCalledWith('/agent-templates/1', update);
  });

  it('delete 调用 DELETE /agent-templates/{id}', async () => {
    mockApi.delete.mockResolvedValue(undefined);

    await agentTemplateService.delete('old-tpl');

    expect(mockApi.delete).toHaveBeenCalledWith('/agent-templates/old-tpl');
  });

  it('seedBuiltin 调用 POST /agent-templates/seed', async () => {
    mockApi.post.mockResolvedValue({ created: 10 });

    const result = await agentTemplateService.seedBuiltin();

    expect(mockApi.post).toHaveBeenCalledWith('/agent-templates/seed', {});
    expect(result).toEqual({ created: 10 });
  });
});
