import { create } from 'zustand';

interface EnvironmentState {
  /** 当前选中的环境名称，null 表示全部环境 */
  current: string | null;
  /** 设置当前环境 */
  setCurrent: (env: string | null) => void;
}

const STORAGE_KEY = 'ckyclaw_environment';

const getInitialEnv = (): string | null => {
  return localStorage.getItem(STORAGE_KEY);
};

const useEnvironmentStore = create<EnvironmentState>((set) => ({
  current: getInitialEnv(),
  setCurrent: (env) => {
    if (env) {
      localStorage.setItem(STORAGE_KEY, env);
    } else {
      localStorage.removeItem(STORAGE_KEY);
    }
    set({ current: env });
  },
}));

export default useEnvironmentStore;
