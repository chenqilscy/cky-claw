/**
 * authStore 测试。
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

// Mock localStorage
const storage: Record<string, string> = {};
vi.stubGlobal('localStorage', {
  getItem: (key: string) => storage[key] ?? null,
  setItem: (key: string, val: string) => { storage[key] = val; },
  removeItem: (key: string) => { delete storage[key]; },
});

// Mock api
vi.mock('../services/api', () => ({
  api: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    delete: vi.fn(),
  },
  ApiError: class extends Error {
    status: number;
    code: string;
    constructor(status: number, code: string, message: string) {
      super(message);
      this.status = status;
      this.code = code;
      this.name = 'ApiError';
    }
  },
  getToken: vi.fn(() => null),
  buildUrl: vi.fn(),
  API_BASE: '/api/v1',
}));

import { api } from '../services/api';

const mockApi = api as unknown as {
  get: ReturnType<typeof vi.fn>;
  post: ReturnType<typeof vi.fn>;
};

describe('authStore', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // 清理 storage
    Object.keys(storage).forEach(k => delete storage[k]);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('初始状态 token 为 null', async () => {
    const { default: useAuthStore } = await import('../stores/authStore');
    const state = useAuthStore.getState();
    expect(state.user).toBeNull();
    expect(state.loading).toBe(false);
  });

  it('login 成功设置 token 和 user', async () => {
    mockApi.post.mockResolvedValue({
      access_token: 'jwt-token-123',
      token_type: 'bearer',
      expires_in: 3600,
    });
    mockApi.get.mockResolvedValue({
      id: '1',
      username: 'admin',
      email: 'admin@test.com',
      role: 'admin',
      is_active: true,
    });

    const { default: useAuthStore } = await import('../stores/authStore');
    await useAuthStore.getState().login('admin', 'password');

    const state = useAuthStore.getState();
    expect(state.token).toBe('jwt-token-123');
    expect(state.user?.username).toBe('admin');
    expect(storage['ckyclaw_token']).toBe('jwt-token-123');
  });

  it('login 失败设置 error', async () => {
    const { ApiError: AE } = await import('../services/api');
    mockApi.post.mockRejectedValue(new AE(401, 'UNAUTHORIZED', '密码错误'));

    const { default: useAuthStore } = await import('../stores/authStore');
    await expect(useAuthStore.getState().login('admin', 'wrong')).rejects.toThrow();

    const state = useAuthStore.getState();
    expect(state.error).toBe('密码错误');
    expect(state.loading).toBe(false);
  });

  it('logout 清除 token 和 user', async () => {
    storage['ckyclaw_token'] = 'old-token';

    const { default: useAuthStore } = await import('../stores/authStore');
    useAuthStore.setState({ token: 'old-token', user: { id: '1', username: 'u', email: '', role: 'user', is_active: true } });

    useAuthStore.getState().logout();

    const state = useAuthStore.getState();
    expect(state.token).toBeNull();
    expect(state.user).toBeNull();
    expect(storage['ckyclaw_token']).toBeUndefined();
  });

  it('fetchMe 获取当前用户', async () => {
    mockApi.get.mockResolvedValue({
      id: '2',
      username: 'viewer',
      email: 'v@test.com',
      role: 'user',
      is_active: true,
    });

    const { default: useAuthStore } = await import('../stores/authStore');
    await useAuthStore.getState().fetchMe();

    expect(useAuthStore.getState().user?.username).toBe('viewer');
  });
});
