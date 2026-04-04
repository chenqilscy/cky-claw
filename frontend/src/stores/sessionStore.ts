/**
 * Session 列表全局状态（Zustand）。
 *
 * 管理 Chat Session 的列表缓存、分页、加载状态，
 * 避免 ChatPage 重复发起相同请求。
 */
import { create } from 'zustand';
import { chatService } from '../services/chatService';
import type { ChatSession } from '../services/chatService';

interface SessionListState {
  /** 当前页 Session 列表 */
  sessions: ChatSession[];
  /** 总数 */
  total: number;
  /** 是否正在加载 */
  loading: boolean;
  /** 最后一次加载时间（ms） */
  lastFetchedAt: number | null;
  /** 当前分页参数 */
  page: number;
  pageSize: number;

  /** 拉取 Session 列表 */
  fetchSessions: (params?: { page?: number; pageSize?: number }) => Promise<void>;
  /** 设置分页 */
  setPage: (page: number) => void;
  /** 使缓存失效并重新拉取 */
  invalidate: () => Promise<void>;
}

const STALE_MS = 15_000; // 15s 内不重复请求

const useSessionStore = create<SessionListState>((set, get) => ({
  sessions: [],
  total: 0,
  loading: false,
  lastFetchedAt: null,
  page: 1,
  pageSize: 20,

  fetchSessions: async (params) => {
    const state = get();
    const page = params?.page ?? state.page;
    const pageSize = params?.pageSize ?? state.pageSize;

    const isFresh =
      state.lastFetchedAt !== null &&
      Date.now() - state.lastFetchedAt < STALE_MS &&
      page === state.page &&
      pageSize === state.pageSize;
    if (isFresh) return;

    set({ loading: true });
    try {
      const offset = (page - 1) * pageSize;
      const resp = await chatService.listSessions({ limit: pageSize, offset });
      set({
        sessions: resp.data,
        total: resp.total,
        page,
        pageSize,
        loading: false,
        lastFetchedAt: Date.now(),
      });
    } catch {
      set({ loading: false });
    }
  },

  setPage: (page) => {
    set({ page, lastFetchedAt: null });
    void get().fetchSessions({ page });
  },

  invalidate: async () => {
    set({ lastFetchedAt: null });
    await get().fetchSessions();
  },
}));

export { useSessionStore };
export type { SessionListState };
