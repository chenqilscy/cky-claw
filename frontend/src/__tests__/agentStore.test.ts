/**
 * agentStore 测试。
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

vi.mock('../services/agentService', () => ({
  agentService: {
    list: vi.fn(),
  },
}));

import { agentService } from '../services/agentService';
import { useAgentStore } from '../stores/agentStore';

const mockAgentService = agentService as unknown as {
  list: ReturnType<typeof vi.fn>;
};

describe('agentStore', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // 重置 store 状态
    useAgentStore.setState({
      agents: [],
      total: 0,
      loading: false,
      lastFetchedAt: null,
      page: 1,
      pageSize: 20,
      search: '',
    });
  });

  afterEach(() => { vi.restoreAllMocks(); });

  it('初始状态正确', () => {
    const state = useAgentStore.getState();
    expect(state.agents).toEqual([]);
    expect(state.total).toBe(0);
    expect(state.loading).toBe(false);
    expect(state.page).toBe(1);
    expect(state.pageSize).toBe(20);
    expect(state.search).toBe('');
  });

  it('fetchAgents 成功更新列表', async () => {
    const agents = [{ name: 'bot', description: 'test' }];
    mockAgentService.list.mockResolvedValue({ data: agents, total: 1 });

    await useAgentStore.getState().fetchAgents();

    const state = useAgentStore.getState();
    expect(state.agents).toEqual(agents);
    expect(state.total).toBe(1);
    expect(state.loading).toBe(false);
    expect(state.lastFetchedAt).not.toBeNull();
  });

  it('fetchAgents 缓存未过期时跳过请求', async () => {
    mockAgentService.list.mockResolvedValue({ data: [], total: 0 });

    await useAgentStore.getState().fetchAgents();
    expect(mockAgentService.list).toHaveBeenCalledTimes(1);

    // 第二次调用在缓存期内应跳过
    await useAgentStore.getState().fetchAgents();
    expect(mockAgentService.list).toHaveBeenCalledTimes(1);
  });

  it('fetchAgents 异常时恢复 loading 状态', async () => {
    mockAgentService.list.mockRejectedValue(new Error('network error'));

    await useAgentStore.getState().fetchAgents();

    const state = useAgentStore.getState();
    expect(state.loading).toBe(false);
  });

  it('setPage 更新分页并触发拉取', async () => {
    mockAgentService.list.mockResolvedValue({ data: [], total: 0 });

    useAgentStore.getState().setPage(3);

    // setPage 内部调用 fetchAgents，需要等待异步
    await vi.waitFor(() => {
      expect(mockAgentService.list).toHaveBeenCalled();
    });
    expect(useAgentStore.getState().page).toBe(3);
  });

  it('setSearch 重置为第一页并触发拉取', async () => {
    mockAgentService.list.mockResolvedValue({ data: [], total: 0 });

    useAgentStore.getState().setSearch('test');

    await vi.waitFor(() => {
      expect(mockAgentService.list).toHaveBeenCalled();
    });
    expect(useAgentStore.getState().search).toBe('test');
    expect(useAgentStore.getState().page).toBe(1);
  });

  it('invalidate 清除缓存并重新拉取', async () => {
    mockAgentService.list.mockResolvedValue({ data: [], total: 0 });

    // 首次拉取
    await useAgentStore.getState().fetchAgents();
    expect(mockAgentService.list).toHaveBeenCalledTimes(1);

    // invalidate 应强制重新拉取
    await useAgentStore.getState().invalidate();
    expect(mockAgentService.list).toHaveBeenCalledTimes(2);
  });
});
