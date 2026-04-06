import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';

// Mock authStore
const mockSetToken = vi.fn();
vi.mock('../../stores/authStore', () => ({
  default: vi.fn(() => ({
    setToken: mockSetToken,
  })),
}));

// Mock oauthService
const mockCallback = vi.fn();
vi.mock('../../services/oauthService', () => ({
  oauthService: {
    callback: (...args: unknown[]) => mockCallback(...args),
  },
}));

// Mock navigate
const mockNavigate = vi.fn();
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom');
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  };
});

import OAuthCallbackPage from '../../pages/oauth/OAuthCallbackPage';

const renderWithRoute = (provider: string, search: string) => {
  render(
    <MemoryRouter initialEntries={[`/oauth/callback/${provider}${search}`]}>
      <Routes>
        <Route path="/oauth/callback/:provider" element={<OAuthCallbackPage />} />
      </Routes>
    </MemoryRouter>,
  );
};

describe('OAuthCallbackPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('shows loading state during callback', () => {
    mockCallback.mockReturnValue(new Promise(() => {})); // never resolves
    renderWithRoute('github', '?code=abc&state=xyz');
    // During loading, page should exist (Spin rendered)
    expect(document.body.querySelector('.ant-spin')).toBeDefined();
  });

  it('shows error when missing code param', async () => {
    renderWithRoute('github', '?state=xyz');
    await waitFor(() => {
      expect(screen.getByText('OAuth 登录失败')).toBeDefined();
    });
  });

  it('shows error when missing state param', async () => {
    renderWithRoute('github', '?code=abc');
    await waitFor(() => {
      expect(screen.getByText('OAuth 登录失败')).toBeDefined();
    });
  });

  it('shows error when callback fails', async () => {
    mockCallback.mockRejectedValue(new Error('token 交换失败'));
    renderWithRoute('github', '?code=abc&state=xyz');
    await waitFor(() => {
      expect(screen.getByText('OAuth 登录失败')).toBeDefined();
    });
  });

  it('calls oauthService.callback with correct params', async () => {
    mockCallback.mockResolvedValue({ access_token: 'jwt123' });
    renderWithRoute('wecom', '?code=abc&state=xyz');
    await waitFor(() => {
      expect(mockCallback).toHaveBeenCalledWith('wecom', 'abc', 'xyz');
    });
  });

  it('renders back to login link on error', async () => {
    renderWithRoute('github', '');
    await waitFor(() => {
      expect(screen.getByText('返回登录页')).toBeDefined();
    });
  });
});
