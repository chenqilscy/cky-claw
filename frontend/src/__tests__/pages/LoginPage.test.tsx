import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { App as AntApp } from 'antd';

// Mock authStore
vi.mock('../../stores/authStore', () => ({
  default: vi.fn(() => ({
    login: vi.fn(),
    loading: false,
    error: null,
    clearError: vi.fn(),
  })),
}));

// Mock oauthService
const mockGetProviders = vi.fn();
const mockAuthorize = vi.fn();
vi.mock('../../services/oauthService', () => ({
  oauthService: {
    getProviders: (...args: unknown[]) => mockGetProviders(...args),
    authorize: (...args: unknown[]) => mockAuthorize(...args),
    callback: vi.fn(),
  },
}));

// Mock message
// antd App.useApp() 通过 AntApp 包裹即可工作

import LoginPage from '../../pages/Login';

describe('LoginPage', () => {
  const originalLocation = window.location;

  beforeEach(() => {
    vi.clearAllMocks();
    mockGetProviders.mockResolvedValue({ providers: [] });
    // 防止 jsdom 在 window.location.href 赋值时挂起
    Object.defineProperty(window, 'location', {
      value: { ...originalLocation, href: '' },
      writable: true,
      configurable: true,
    });
  });

  afterEach(() => {
    Object.defineProperty(window, 'location', {
      value: originalLocation,
      writable: true,
      configurable: true,
    });
  });

  it('renders login form', () => {
    render(
      <AntApp><MemoryRouter><LoginPage />
      </MemoryRouter></AntApp>,
    );
    expect(screen.getByText('Kasaya')).toBeDefined();
    expect(screen.getByPlaceholderText('用户名')).toBeDefined();
    expect(screen.getByPlaceholderText('密码')).toBeDefined();
  });

  it('renders login button', () => {
    render(
      <AntApp><MemoryRouter><LoginPage />
      </MemoryRouter></AntApp>,
    );
    expect(screen.getByRole('button', { name: /登\s*录/ })).toBeDefined();
  });

  it('shows error message when store has error', async () => {
    const useAuthStore = (await import('../../stores/authStore')).default;
    vi.mocked(useAuthStore).mockReturnValue({
      login: vi.fn(),
      loading: false,
      error: '密码错误',
      clearError: vi.fn(),
      token: null,
      user: null,
      logout: vi.fn(),
    });

    render(
      <AntApp><MemoryRouter><LoginPage />
      </MemoryRouter></AntApp>,
    );
    expect(screen.getByText('密码错误')).toBeDefined();
  });

  it('renders GitHub login button when provider is available', async () => {
    mockGetProviders.mockResolvedValue({ providers: ['github'] });
    render(
      <AntApp><MemoryRouter><LoginPage />
      </MemoryRouter></AntApp>,
    );
    await waitFor(() => {
      expect(screen.getByRole('button', { name: /GitHub 登录/ })).toBeDefined();
    }, { timeout: 15000 });
  });

  it('renders wecom login button when provider is available', async () => {
    mockGetProviders.mockResolvedValue({ providers: ['wecom'] });
    render(
      <AntApp><MemoryRouter><LoginPage />
      </MemoryRouter></AntApp>,
    );
    await waitFor(() => {
      expect(screen.getByRole('button', { name: /企业微信 登录/ })).toBeDefined();
    }, { timeout: 15000 });
  });

  it('renders dingtalk login button when provider is available', async () => {
    mockGetProviders.mockResolvedValue({ providers: ['dingtalk'] });
    render(
      <AntApp><MemoryRouter><LoginPage />
      </MemoryRouter></AntApp>,
    );
    await waitFor(() => {
      expect(screen.getByRole('button', { name: /钉钉 登录/ })).toBeDefined();
    }, { timeout: 15000 });
  });

  it('renders feishu login button when provider is available', async () => {
    mockGetProviders.mockResolvedValue({ providers: ['feishu'] });
    render(
      <AntApp><MemoryRouter><LoginPage />
      </MemoryRouter></AntApp>,
    );
    await waitFor(() => {
      expect(screen.getByRole('button', { name: /飞书 登录/ })).toBeDefined();
    }, { timeout: 15000 });
  });

  it('renders multiple OAuth providers together', async () => {
    mockGetProviders.mockResolvedValue({ providers: ['github', 'wecom', 'dingtalk', 'feishu'] });
    render(
      <AntApp><MemoryRouter><LoginPage />
      </MemoryRouter></AntApp>,
    );
    await waitFor(() => {
      expect(screen.getByRole('button', { name: /GitHub 登录/ })).toBeDefined();
      expect(screen.getByRole('button', { name: /企业微信 登录/ })).toBeDefined();
      expect(screen.getByRole('button', { name: /钉钉 登录/ })).toBeDefined();
      expect(screen.getByRole('button', { name: /飞书 登录/ })).toBeDefined();
    }, { timeout: 15000 });
  });

  it('does not show divider when no providers available', () => {
    mockGetProviders.mockResolvedValue({ providers: [] });
    render(
      <AntApp><MemoryRouter><LoginPage />
      </MemoryRouter></AntApp>,
    );
    // 密码登录按钮应该存在
    expect(screen.getByRole('button', { name: /登\s*录/ })).toBeDefined();
    // 不应出现 OAuth 按钮
    expect(screen.queryByRole('button', { name: /GitHub 登录/ })).toBeNull();
  });

  it('clicks OAuth button and calls authorize', async () => {
    mockGetProviders.mockResolvedValue({ providers: ['dingtalk'] });
    mockAuthorize.mockResolvedValue({ authorize_url: 'https://login.dingtalk.com/test', state: 'abc' });

    render(
      <AntApp><MemoryRouter><LoginPage />
      </MemoryRouter></AntApp>,
    );

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /钉钉 登录/ })).toBeDefined();
    }, { timeout: 15000 });

    const user = userEvent.setup();
    await user.click(screen.getByRole('button', { name: /钉钉 登录/ }));

    await waitFor(() => {
      expect(mockAuthorize).toHaveBeenCalledWith('dingtalk');
    }, { timeout: 15000 });
  });

  it('shows error message when OAuth authorize fails', async () => {
    // 确保 authStore 使用默认值（无 error 泄漏）
    const useAuthStore = (await import('../../stores/authStore')).default;
    vi.mocked(useAuthStore).mockReturnValue({
      login: vi.fn(),
      loading: false,
      error: null,
      clearError: vi.fn(),
      token: null,
      user: null,
      logout: vi.fn(),
    });

    mockGetProviders.mockResolvedValue({ providers: ['wecom'] });
    mockAuthorize.mockRejectedValue(new Error('网络错误'));

    // 获取全局 mock 的 message 对象
    const { App: MockApp } = await import('antd');
    const { message: mockMsg } = (MockApp as unknown as { useApp: () => { message: { error: ReturnType<typeof vi.fn> } } }).useApp();

    render(
      <AntApp><MemoryRouter><LoginPage />
      </MemoryRouter></AntApp>,
    );

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /企业微信 登录/ })).toBeDefined();
    }, { timeout: 15000 });

    const user = userEvent.setup();
    await user.click(screen.getByRole('button', { name: /企业微信 登录/ }));

    // message.error 是全局 mock，检查调用而非 DOM 文本
    await waitFor(() => {
      expect(mockMsg.error).toHaveBeenCalledWith('企业微信 登录暂不可用');
    }, { timeout: 15000 });
  });

  it('handles getProviders failure gracefully', async () => {
    mockGetProviders.mockRejectedValue(new Error('网络异常'));
    render(
      <AntApp><MemoryRouter><LoginPage />
      </MemoryRouter></AntApp>,
    );
    // 应该依然能渲染密码登录表单
    expect(screen.getByPlaceholderText('用户名')).toBeDefined();
    expect(screen.getByPlaceholderText('密码')).toBeDefined();
    // OAuth 按钮不应出现
    await waitFor(() => {
      expect(screen.queryByRole('button', { name: /GitHub 登录/ })).toBeNull();
    });
  });
});

