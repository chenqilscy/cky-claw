/**
 * sessionStore 测试。
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

vi.mock('../services/chatService', () => ({
  chatService: {
    listSessions: vi.fn(),
  },
}));

import { chatService } from '../services/chatService';
import { useSessionStore } from '../stores/sessionStore';

const mockChatService = chatService as unknown as {
  listSessions: ReturnType<typeof vi.fn>;
};

describe('sessionStore', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useSessionStore.setState({
      sessions: [],
      total: 0,
      loading: false,
      lastFetchedAt: null,
      page: 1,
      pageSize: 20,
    });
  });

  afterEach(() => { vi.restoreAllMocks(); });

  it('初始状态正确', () => {
    const state = useSessionStore.getState();
    expect(state.sessions).toEqual([]);
    expect(state.total).toBe(0);
    expect(state.loading).toBe(false);
    expect(state.page).toBe(1);
  });

  it('fetchSessions 成功更新列表', async () => {
    const sessions = [{ id: 's1', agent_name: 'bot' }];
    mockChatService.listSessions.mockResolvedValue({ data: sessions, total: 1 });

    await useSessionStore.getState().fetchSessions();

    const state = useSessionStore.getState();
    expect(state.sessions).toEqual(sessions);
    expect(state.total).toBe(1);
    expect(state.loading).toBe(false);
    expect(state.lastFetchedAt).not.toBeNull();
  });

  it('fetchSessions 缓存未过期时跳过请求', async () => {
    mockChatService.listSessions.mockResolvedValue({ data: [], total: 0 });

    await useSessionStore.getState().fetchSessions();
    expect(mockChatService.listSessions).toHaveBeenCalledTimes(1);

    await useSessionStore.getState().fetchSessions();
    expect(mockChatService.listSessions).toHaveBeenCalledTimes(1);
  });

  it('fetchSessions 异常时恢复 loading', async () => {
    mockChatService.listSessions.mockRejectedValue(new Error('fail'));

    await useSessionStore.getState().fetchSessions();

    expect(useSessionStore.getState().loading).toBe(false);
  });

  it('setPage 更新分页并触发拉取', async () => {
    mockChatService.listSessions.mockResolvedValue({ data: [], total: 0 });

    useSessionStore.getState().setPage(2);

    await vi.waitFor(() => {
      expect(mockChatService.listSessions).toHaveBeenCalled();
    });
    expect(useSessionStore.getState().page).toBe(2);
  });

  it('invalidate 清除缓存并重新拉取', async () => {
    mockChatService.listSessions.mockResolvedValue({ data: [], total: 0 });

    await useSessionStore.getState().fetchSessions();
    expect(mockChatService.listSessions).toHaveBeenCalledTimes(1);

    await useSessionStore.getState().invalidate();
    expect(mockChatService.listSessions).toHaveBeenCalledTimes(2);
  });
});
