import { create } from 'zustand';
import { api, ApiError } from '../services/api';

interface User {
  id: string;
  username: string;
  email: string;
  role: string;
  is_active: boolean;
}

interface AuthState {
  token: string | null;
  user: User | null;
  loading: boolean;
  error: string | null;

  login: (username: string, password: string) => Promise<void>;
  logout: () => void;
  fetchMe: () => Promise<void>;
  clearError: () => void;
}

interface LoginResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
}

const useAuthStore = create<AuthState>((set) => ({
  token: localStorage.getItem('ckyclaw_token'),
  user: null,
  loading: false,
  error: null,

  login: async (username: string, password: string) => {
    set({ loading: true, error: null });
    try {
      const data = await api.post<LoginResponse>('/auth/login', { username, password });
      localStorage.setItem('ckyclaw_token', data.access_token);
      set({ token: data.access_token, loading: false });

      // 获取用户信息
      const user = await api.get<User>('/auth/me');
      set({ user });
    } catch (err) {
      const message = err instanceof ApiError ? err.message : '登录失败';
      set({ loading: false, error: message });
      throw err;
    }
  },

  logout: () => {
    localStorage.removeItem('ckyclaw_token');
    set({ token: null, user: null, error: null });
  },

  fetchMe: async () => {
    try {
      const user = await api.get<User>('/auth/me');
      set({ user });
    } catch {
      // token 无效时静默清除
      localStorage.removeItem('ckyclaw_token');
      set({ token: null, user: null });
    }
  },

  clearError: () => set({ error: null }),
}));

export default useAuthStore;
export type { User, AuthState };
