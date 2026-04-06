import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
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
vi.mock('../../services/oauthService', () => ({
  oauthService: {
    authorize: vi.fn(),
    callback: vi.fn(),
  },
}));

import LoginPage from '../../pages/Login';

describe('LoginPage', () => {
  beforeEach(() => vi.clearAllMocks());

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
    expect(screen.getByRole('button', { name: /登录/ })).toBeDefined();
  });

  it('renders GitHub login button', () => {
    render(
      <MemoryRouter>
        <LoginPage />
      </MemoryRouter>,
    );
    expect(screen.getByRole('button', { name: /GitHub 登录/ })).toBeDefined();
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
});
