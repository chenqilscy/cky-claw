import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';

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
vi.mock('antd', async () => {
  const actual = await vi.importActual<typeof import('antd')>('antd');
  return { ...actual, message: { success: vi.fn(), error: vi.fn() } };
});

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
      <MemoryRouter>
        <LoginPage />
      </MemoryRouter>,
    );
    expect(screen.getByText('CkyClaw')).toBeDefined();
    expect(screen.getByPlaceholderText('用户名')).toBeDefined();
    expect(screen.getByPlaceholderText('密码')).toBeDefined();
  });

  it('renders login button', () => {
    render(
      <MemoryRouter>
        <LoginPage />
      </MemoryRouter>,
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
      <MemoryRouter>
        <LoginPage />
      </MemoryRouter>,
    );
    expect(screen.getByText('密码错误')).toBeDefined();
  });

  it('renders GitHub login button when provider is available', async () => {
    mockGetProviders.mockResolvedValue({ providers: ['github'] });
    render(
      <MemoryRouter>
        <LoginPage />
      </MemoryRouter>,
    );
    await waitFor(() => {
      expect(screen.getByRole('button', { name: /GitHub 登录/ })).toBeDefined();
    });
  });

  it('renders wecom login button when provider is available', async () => {
    mockGetProviders.mockResolvedValue({ providers: ['wecom'] });
    render(
      <MemoryRouter>
        <LoginPage />
      </MemoryRouter>,
    );
    await waitFor(() => {
      expect(screen.getByRole('button', { name: /企业微信 登录/ })).toBeDefined();
    });
  });

  it('renders dingtalk login button when provider is available', async () => {
    mockGetProviders.mockResolvedValue({ providers: ['dingtalk'] });
    render(
      <MemoryRouter>
        <LoginPage />
      </MemoryRouter>,
    );
    await waitFor(() => {
      expect(screen.getByRole('button', { name: /钉钉 登录/ })).toBeDefined();
    });
  });

  it('renders feishu login button when provider is available', async () => {
    mockGetProviders.mockResolvedValue({ providers: ['feishu'] });
    render(
      <MemoryRouter>
        <LoginPage />
      </MemoryRouter>,
    );
    await waitFor(() => {
      expect(screen.getByRole('button', { name: /飞书 登录/ })).toBeDefined();
    });
  });

  it('renders multiple OAuth providers together', async () => {
    mockGetProviders.mockResolvedValue({ providers: ['github', 'wecom', 'dingtalk', 'feishu'] });
    render(
      <MemoryRouter>
        <LoginPage />
      </MemoryRouter>,
    );
    await waitFor(() => {
      expect(screen.getByRole('button', { name: /GitHub 登录/ })).toBeDefined();
      expect(screen.getByRole('button', { name: /企业微信 登录/ })).toBeDefined();
      expect(screen.getByRole('button', { name: /钉钉 登录/ })).toBeDefined();
      expect(screen.getByRole('button', { name: /飞书 登录/ })).toBeDefined();
    });
  });

  it('does not show divider when no providers available', () => {
    mockGetProviders.mockResolvedValue({ providers: [] });
    render(
      <MemoryRouter>
        <LoginPage />
      </MemoryRouter>,
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
      <MemoryRouter>
        <LoginPage />
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /钉钉 登录/ })).toBeDefined();
    });

    const user = userEvent.setup();
    await user.click(screen.getByRole('button', { name: /钉钉 登录/ }));

    await waitFor(() => {
      expect(mockAuthorize).toHaveBeenCalledWith('dingtalk');
    });
  });

  it('shows error message when OAuth authorize fails', async () => {
    mockGetProviders.mockResolvedValue({ providers: ['wecom'] });
    mockAuthorize.mockRejectedValue(new Error('网络错误'));

    render(
      <MemoryRouter>
        <LoginPage />
      </MemoryRouter>,
    );

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /企业微信 登录/ })).toBeDefined();
    });

    const user = userEvent.setup();
    await user.click(screen.getByRole('button', { name: /企业微信 登录/ }));

    const { message: antdMessage } = await import('antd');
    await waitFor(() => {
      expect(antdMessage.error).toHaveBeenCalledWith('企业微信 登录暂不可用');
    });
  });

  it('handles getProviders failure gracefully', async () => {
    mockGetProviders.mockRejectedValue(new Error('网络异常'));
    render(
      <MemoryRouter>
        <LoginPage />
      </MemoryRouter>,
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

