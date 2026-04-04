import { create } from 'zustand';

type ThemeMode = 'light' | 'dark';

interface ThemeState {
  mode: ThemeMode;
  toggle: () => void;
  setMode: (mode: ThemeMode) => void;
}

const STORAGE_KEY = 'ckyclaw_theme';

const getInitialMode = (): ThemeMode => {
  const stored = localStorage.getItem(STORAGE_KEY);
  if (stored === 'dark' || stored === 'light') return stored;
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
};

const useThemeStore = create<ThemeState>((set) => ({
  mode: getInitialMode(),
  toggle: () =>
    set((state) => {
      const next = state.mode === 'light' ? 'dark' : 'light';
      localStorage.setItem(STORAGE_KEY, next);
      return { mode: next };
    }),
  setMode: (mode) => {
    localStorage.setItem(STORAGE_KEY, mode);
    set({ mode });
  },
}));

export default useThemeStore;
