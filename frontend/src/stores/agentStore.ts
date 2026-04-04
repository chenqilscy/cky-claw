/**
 * Agent 列表全局状态（Zustand）。
 *
 * 管理 Agent 的列表缓存、分页、加载状态和 CRUD 后的失效刷新，
 * 避免各页面重复发起相同请求。
 */
import { create } from 'zustand';
import { agentService } from '../services/agentService';
import type { AgentConfig } from '../services/agentService';

interface AgentListState {
  /** 当前页 Agent 列表 */
  agents: AgentConfig[];
  /** 总数 */
  total: number;
  /** 是否正在加载 */
  loading: boolean;
  /** 最后一次加载时间（ms），用于 stale-while-revalidate */
  lastFetchedAt: number | null;
  /** 当前分页参数 */
  page: number;
  pageSize: number;
  /** 搜索关键字 */
  search: string;

  /** 拉取 Agent 列表 */
  fetchAgents: (params?: { page?: number; pageSize?: number; search?: string }) => Promise<void>;
  /** 设置分页 */
  setPage: (page: number) => void;
  /** 设置搜索关键字并重新拉取 */
  setSearch: (search: string) => void;
  /** 使缓存失效并重新拉取（CRUD 操作后调用） */
  invalidate: () => Promise<void>;
}

const STALE_MS = 30_000; // 30s 内不重复请求

const useAgentStore = create<AgentListState>((set, get) => ({
  agents: [],
  total: 0,
  loading: false,
  lastFetchedAt: null,
  page: 1,
  pageSize: 20,
  search: '',

  fetchAgents: async (params) => {
    const state = get();
    const page = params?.page ?? state.page;
    const pageSize = params?.pageSize ?? state.pageSize;
    const search = params?.search ?? state.search;

    // stale-while-revalidate：参数不变且缓存未过期则跳过
    const isFresh =
      state.lastFetchedAt !== null &&
      Date.now() - state.lastFetchedAt < STALE_MS &&
      page === state.page &&
      pageSize === state.pageSize &&
      search === state.search;
    if (isFresh) return;

    set({ loading: true });
    try {
      const offset = (page - 1) * pageSize;
      const resp = await agentService.list({ limit: pageSize, offset, search: search || undefined });
      set({
        agents: resp.data,
        total: resp.total,
        page,
        pageSize,
        search,
        loading: false,
        lastFetchedAt: Date.now(),
      });
    } catch {
      set({ loading: false });
    }
  },

  setPage: (page) => {
    set({ page, lastFetchedAt: null });
    void get().fetchAgents({ page });
  },

  setSearch: (search) => {
    set({ search, page: 1, lastFetchedAt: null });
    void get().fetchAgents({ search, page: 1 });
  },

  invalidate: async () => {
    set({ lastFetchedAt: null });
    await get().fetchAgents();
  },
}));

export { useAgentStore };
export type { AgentListState };
