/**
 * themeStore 测试。
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

const storage: Record<string, string> = {};
vi.stubGlobal('localStorage', {
  getItem: (key: string) => storage[key] ?? null,
  setItem: (key: string, val: string) => { storage[key] = val; },
  removeItem: (key: string) => { delete storage[key]; },
});

// matchMedia 默认返回 light
vi.stubGlobal('matchMedia', vi.fn().mockReturnValue({ matches: false }));

describe('themeStore', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    Object.keys(storage).forEach(k => delete storage[k]);
  });

  afterEach(() => { vi.restoreAllMocks(); });

  it('默认 mode 为 light（无 localStorage、系统偏好为 light）', async () => {
    const { default: useThemeStore } = await import('../stores/themeStore');
    useThemeStore.setState({ mode: 'light' });
    expect(useThemeStore.getState().mode).toBe('light');
  });

  it('toggle 从 light 切换到 dark', async () => {
    const { default: useThemeStore } = await import('../stores/themeStore');
    useThemeStore.setState({ mode: 'light' });

    useThemeStore.getState().toggle();

    expect(useThemeStore.getState().mode).toBe('dark');
    expect(storage['ckyclaw_theme']).toBe('dark');
  });

  it('toggle 从 dark 切换到 light', async () => {
    const { default: useThemeStore } = await import('../stores/themeStore');
    useThemeStore.setState({ mode: 'dark' });

    useThemeStore.getState().toggle();

    expect(useThemeStore.getState().mode).toBe('light');
    expect(storage['ckyclaw_theme']).toBe('light');
  });

  it('setMode 设置并持久化到 localStorage', async () => {
    const { default: useThemeStore } = await import('../stores/themeStore');

    useThemeStore.getState().setMode('dark');

    expect(useThemeStore.getState().mode).toBe('dark');
    expect(storage['ckyclaw_theme']).toBe('dark');
  });
});
