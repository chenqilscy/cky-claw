import { create } from 'zustand';

import type { PaletteType } from '../theme/themeConfig';

type ThemeMode = 'light' | 'dark';

interface ThemeState {
  mode: ThemeMode;
  palette: PaletteType;
  toggle: () => void;
  setMode: (mode: ThemeMode) => void;
  setPalette: (palette: PaletteType) => void;
}

const MODE_KEY = 'kasaya_theme';
const PALETTE_KEY = 'kasaya_palette';

const getInitialMode = (): ThemeMode => {
  const stored = localStorage.getItem(MODE_KEY);
  if (stored === 'dark' || stored === 'light') return stored;
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
};

const getInitialPalette = (): PaletteType => {
  const stored = localStorage.getItem(PALETTE_KEY);
  if (stored === 'aurora' || stored === 'dawn') return stored;
  return 'aurora';
};

const useThemeStore = create<ThemeState>((set) => ({
  mode: getInitialMode(),
  palette: getInitialPalette(),
  toggle: () =>
    set((state) => {
      const next = state.mode === 'light' ? 'dark' : 'light';
      localStorage.setItem(MODE_KEY, next);
      return { mode: next };
    }),
  setMode: (mode) => {
    localStorage.setItem(MODE_KEY, mode);
    set({ mode });
  },
  setPalette: (palette) => {
    localStorage.setItem(PALETTE_KEY, palette);
    set({ palette });
  },
}));

export default useThemeStore;
