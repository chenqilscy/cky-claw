/**
 * guardrailService 测试。
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

import { guardrailService } from '../services/guardrailService';
import { api } from '../services/api';

const mockApi = api as unknown as {
  get: ReturnType<typeof vi.fn>;
  post: ReturnType<typeof vi.fn>;
  put: ReturnType<typeof vi.fn>;
  delete: ReturnType<typeof vi.fn>;
};

describe('guardrailService', () => {
  beforeEach(() => { vi.clearAllMocks(); });
  afterEach(() => { vi.restoreAllMocks(); });

  it('list 调用 GET /guardrails', async () => {
    const data = { data: [], total: 0 };
    mockApi.get.mockResolvedValue(data);
    const result = await guardrailService.list();
    expect(mockApi.get).toHaveBeenCalledWith('/guardrails', {});
    expect(result).toEqual(data);
  });

  it('list 过滤空值和空字符串参数', async () => {
    mockApi.get.mockResolvedValue({ data: [], total: 0 });
    await guardrailService.list({ guardrail_type: 'input', stage: undefined, is_enabled: true });
    // is_enabled (boolean) 应转为字符串
    expect(mockApi.get).toHaveBeenCalledWith('/guardrails', { guardrail_type: 'input', is_enabled: 'true' });
  });

  it('get 调用 GET /guardrails/:id', async () => {
    const guardrail = { id: 'g1', name: 'test' };
    mockApi.get.mockResolvedValue(guardrail);
    const result = await guardrailService.get('g1');
    expect(mockApi.get).toHaveBeenCalledWith('/guardrails/g1');
    expect(result).toEqual(guardrail);
  });

  it('create 调用 POST /guardrails', async () => {
    const input = { name: 'new', guardrail_type: 'input', config: {} };
    mockApi.post.mockResolvedValue({ id: '1', ...input });
    const result = await guardrailService.create(input);
    expect(mockApi.post).toHaveBeenCalledWith('/guardrails', input);
    expect(result).toEqual({ id: '1', ...input });
  });

  it('update 调用 PUT /guardrails/:id', async () => {
    const update = { name: 'updated' };
    mockApi.put.mockResolvedValue({ id: '1', ...update });
    await guardrailService.update('1', update);
    expect(mockApi.put).toHaveBeenCalledWith('/guardrails/1', update);
  });

  it('delete 调用 DELETE /guardrails/:id', async () => {
    mockApi.delete.mockResolvedValue(undefined);
    await guardrailService.delete('g1');
    expect(mockApi.delete).toHaveBeenCalledWith('/guardrails/g1');
  });
});
