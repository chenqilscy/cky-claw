/**
 * scheduledTaskService 测试。
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

import { scheduledTaskService } from '../services/scheduledTaskService';
import { api } from '../services/api';

const mockApi = api as unknown as {
  get: ReturnType<typeof vi.fn>;
  post: ReturnType<typeof vi.fn>;
  put: ReturnType<typeof vi.fn>;
  delete: ReturnType<typeof vi.fn>;
};

describe('scheduledTaskService', () => {
  beforeEach(() => { vi.clearAllMocks(); });
  afterEach(() => { vi.restoreAllMocks(); });

  it('list 调用 GET /scheduled-tasks', async () => {
    const data = { data: [], total: 0 };
    mockApi.get.mockResolvedValue(data);
    const result = await scheduledTaskService.list();
    expect(mockApi.get).toHaveBeenCalledWith('/scheduled-tasks', {});
    expect(result).toEqual(data);
  });

  it('list 过滤 undefined 和空字符串，布尔转字符串', async () => {
    mockApi.get.mockResolvedValue({ data: [], total: 0 });
    await scheduledTaskService.list({ agent_id: 'a1', name: '', is_enabled: true });
    expect(mockApi.get).toHaveBeenCalledWith('/scheduled-tasks', { agent_id: 'a1', is_enabled: 'true' });
  });

  it('get 调用 GET /scheduled-tasks/:id', async () => {
    mockApi.get.mockResolvedValue({ id: 's1', name: 'task' });
    const result = await scheduledTaskService.get('s1');
    expect(mockApi.get).toHaveBeenCalledWith('/scheduled-tasks/s1');
    expect(result).toEqual({ id: 's1', name: 'task' });
  });

  it('create 调用 POST /scheduled-tasks', async () => {
    const input = { name: 'daily', agent_id: 'a1', cron_expr: '0 0 * * *' };
    mockApi.post.mockResolvedValue({ id: '1', ...input });
    const result = await scheduledTaskService.create(input);
    expect(mockApi.post).toHaveBeenCalledWith('/scheduled-tasks', input);
    expect(result).toEqual({ id: '1', ...input });
  });

  it('update 调用 PUT /scheduled-tasks/:id', async () => {
    const update = { is_enabled: false };
    mockApi.put.mockResolvedValue({ id: '1', ...update });
    await scheduledTaskService.update('1', update);
    expect(mockApi.put).toHaveBeenCalledWith('/scheduled-tasks/1', update);
  });

  it('delete 调用 DELETE /scheduled-tasks/:id', async () => {
    mockApi.delete.mockResolvedValue(undefined);
    await scheduledTaskService.delete('s1');
    expect(mockApi.delete).toHaveBeenCalledWith('/scheduled-tasks/s1');
  });
});
