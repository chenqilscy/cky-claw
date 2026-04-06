/**
 * supervisionService 测试。
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

import { supervisionService } from '../services/supervisionService';
import { api } from '../services/api';

const mockApi = api as unknown as {
  get: ReturnType<typeof vi.fn>;
  post: ReturnType<typeof vi.fn>;
};

describe('supervisionService', () => {
  beforeEach(() => { vi.clearAllMocks(); });
  afterEach(() => { vi.restoreAllMocks(); });

  it('listSessions 调用 GET /supervision/sessions', async () => {
    const data = { data: [], total: 0 };
    mockApi.get.mockResolvedValue(data);
    const result = await supervisionService.listSessions();
    expect(mockApi.get).toHaveBeenCalledWith('/supervision/sessions', undefined);
    expect(result).toEqual(data);
  });

  it('listSessions 传递过滤参数', async () => {
    mockApi.get.mockResolvedValue({ data: [], total: 0 });
    await supervisionService.listSessions({ agent_name: 'bot', status: 'running' });
    expect(mockApi.get).toHaveBeenCalledWith('/supervision/sessions', { agent_name: 'bot', status: 'running' });
  });

  it('getSessionDetail 调用 GET /supervision/sessions/:id', async () => {
    const detail = { session_id: 's1', messages: [] };
    mockApi.get.mockResolvedValue(detail);
    const result = await supervisionService.getSessionDetail('s1');
    expect(mockApi.get).toHaveBeenCalledWith('/supervision/sessions/s1');
    expect(result).toEqual(detail);
  });

  it('pauseSession 无 reason 时不传 body', async () => {
    mockApi.post.mockResolvedValue({ session_id: 's1', status: 'paused' });
    await supervisionService.pauseSession('s1');
    expect(mockApi.post).toHaveBeenCalledWith('/supervision/sessions/s1/pause', undefined);
  });

  it('pauseSession 有 reason 时传 body', async () => {
    mockApi.post.mockResolvedValue({ session_id: 's1', status: 'paused' });
    await supervisionService.pauseSession('s1', 'safety check');
    expect(mockApi.post).toHaveBeenCalledWith('/supervision/sessions/s1/pause', { reason: 'safety check' });
  });

  it('resumeSession 无 instructions 时不传 body', async () => {
    mockApi.post.mockResolvedValue({ session_id: 's1', status: 'running' });
    await supervisionService.resumeSession('s1');
    expect(mockApi.post).toHaveBeenCalledWith('/supervision/sessions/s1/resume', undefined);
  });

  it('resumeSession 有 instructions 时传 body', async () => {
    mockApi.post.mockResolvedValue({ session_id: 's1', status: 'running' });
    await supervisionService.resumeSession('s1', 'continue carefully');
    expect(mockApi.post).toHaveBeenCalledWith('/supervision/sessions/s1/resume', { injected_instructions: 'continue carefully' });
  });
});
