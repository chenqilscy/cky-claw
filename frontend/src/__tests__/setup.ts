/**
 * Vitest 全局 setup — 为 jsdom 环境补全 Ant Design 需要的浏览器 API。
 */

// Ant Design 中 Grid/Responsive 组件依赖 window.matchMedia
Object.defineProperty(window, 'matchMedia', {
  writable: true,
  value: vi.fn().mockImplementation((query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: vi.fn(),
    removeListener: vi.fn(),
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn(),
  })),
});

// Ant Design 某些组件依赖 getComputedStyle
if (!window.getComputedStyle) {
  (window as unknown as Record<string, unknown>).getComputedStyle = vi.fn().mockReturnValue({});
}
