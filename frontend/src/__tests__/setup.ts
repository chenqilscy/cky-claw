/**
 * Vitest 全局 setup — 为 jsdom 环境补全 Ant Design 需要的浏览器 API。
 */

/* ---------- 全局 mock antd App.useApp()（jsdom 中无法使用 context） ---------- */
vi.mock('antd', async () => {
  const actual = await vi.importActual<Record<string, unknown>>('antd');
  const mockMessage = { error: vi.fn(), info: vi.fn(), success: vi.fn(), warning: vi.fn() };
  const mockNotification = { error: vi.fn(), info: vi.fn(), success: vi.fn(), warning: vi.fn(), open: vi.fn() };
  const mockModal = { confirm: vi.fn(), info: vi.fn(), success: vi.fn(), error: vi.fn(), warning: vi.fn() };
  const ActualApp = actual.App as Record<string, unknown>;
  const MockApp = Object.assign(
    ({ children }: { children?: React.ReactNode }) => children,
    { ...ActualApp, useApp: () => ({ message: mockMessage, notification: mockNotification, modal: mockModal }) },
  );
  return { ...actual, App: MockApp, message: mockMessage };
});

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
