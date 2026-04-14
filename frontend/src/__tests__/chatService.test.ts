/**
 * chatService 测试。
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

vi.mock('../services/api', () => ({
  api: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    delete: vi.fn(),
  },
  API_BASE: '/api/v1',
  getToken: vi.fn(() => 'test-token'),
}));

import { chatService } from '../services/chatService';
import { api } from '../services/api';

const mockApi = api as unknown as {
  get: ReturnType<typeof vi.fn>;
  post: ReturnType<typeof vi.fn>;
  delete: ReturnType<typeof vi.fn>;
};

describe('chatService', () => {
  beforeEach(() => { vi.clearAllMocks(); });
  afterEach(() => { vi.restoreAllMocks(); });

  it('createSession 调用 POST /sessions', async () => {
    const session = { id: 's1', agent_name: 'bot' };
    mockApi.post.mockResolvedValue(session);
    const result = await chatService.createSession('bot', { key: 'val' });
    expect(mockApi.post).toHaveBeenCalledWith('/sessions', { agent_name: 'bot', metadata: { key: 'val' } });
    expect(result).toEqual(session);
  });

  it('listSessions 调用 GET /sessions', async () => {
    const data = { data: [], total: 0 };
    mockApi.get.mockResolvedValue(data);
    const result = await chatService.listSessions({ limit: 10, offset: 0 });
    expect(mockApi.get).toHaveBeenCalledWith('/sessions', { limit: 10, offset: 0 });
    expect(result).toEqual(data);
  });

  it('getSession 调用 GET /sessions/:id', async () => {
    mockApi.get.mockResolvedValue({ id: 's1' });
    const result = await chatService.getSession('s1');
    expect(mockApi.get).toHaveBeenCalledWith('/sessions/s1');
    expect(result).toEqual({ id: 's1' });
  });

  it('deleteSession 调用 DELETE /sessions/:id', async () => {
    mockApi.delete.mockResolvedValue(undefined);
    await chatService.deleteSession('s1');
    expect(mockApi.delete).toHaveBeenCalledWith('/sessions/s1');
  });

  it('runNonStream 调用 POST /sessions/:id/run', async () => {
    const runResp = { run_id: 'r1', status: 'completed', output: 'hello' };
    mockApi.post.mockResolvedValue(runResp);
    const result = await chatService.runNonStream('s1', 'hello');
    expect(mockApi.post).toHaveBeenCalledWith('/sessions/s1/run', {
      input: 'hello',
      config: { stream: false },
    });
    expect(result).toEqual(runResp);
  });

  it('getMessages 调用 GET /sessions/:id/messages', async () => {
    const resp = { session_id: 's1', messages: [], total: 0 };
    mockApi.get.mockResolvedValue(resp);
    const result = await chatService.getMessages('s1');
    expect(mockApi.get).toHaveBeenCalledWith('/sessions/s1/messages', undefined);
    expect(result).toEqual(resp);
  });

  it('getMessages 带搜索参数', async () => {
    const resp = { session_id: 's1', messages: [], total: 0 };
    mockApi.get.mockResolvedValue(resp);
    await chatService.getMessages('s1', '关键词');
    expect(mockApi.get).toHaveBeenCalledWith('/sessions/s1/messages', { search: '关键词' });
  });

  it('runStream 返回 AbortController', () => {
    // runStream 使用原生 fetch + SSE，mock fetch 测试基本流程
    const mockReader = {
      read: vi.fn()
        .mockResolvedValueOnce({ done: false, value: new TextEncoder().encode('event: message\ndata: {"text":"hi"}\n\n') })
        .mockResolvedValueOnce({ done: true, value: undefined }),
    };
    const mockResponse = {
      ok: true,
      body: { getReader: () => mockReader },
    };
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(mockResponse));

    const onEvent = vi.fn();
    const controller = chatService.runStream('s1', 'test', onEvent);

    expect(controller).toBeInstanceOf(AbortController);
    vi.unstubAllGlobals();
  });
});
