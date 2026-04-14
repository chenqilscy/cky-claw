import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, waitFor, screen } from '@testing-library/react';
import { TestQueryWrapper } from '../test-utils';
import { MemoryRouter, Route, Routes } from 'react-router-dom';

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom');
  return { ...actual, useNavigate: () => vi.fn() };
});

vi.mock('../../services/environmentService', () => ({
  environmentService: {
    list: vi.fn(),
    get: vi.fn(),
    create: vi.fn(),
    update: vi.fn(),
    delete: vi.fn(),
    publishAgent: vi.fn(),
    rollbackAgent: vi.fn(),
    listAgents: vi.fn(),
    diff: vi.fn(),
  },
}));

vi.mock('antd', async () => {
  const actual = await vi.importActual<typeof import('antd')>('antd');
  return { ...actual, message: { success: vi.fn(), error: vi.fn() } };
});

import EnvironmentDetailPage from '../../pages/environments/EnvironmentDetailPage';
import { environmentService } from '../../services/environmentService';

const mockEnv = {
  id: 'env-1',
  name: 'dev',
  display_name: '开发',
  description: '开发环境',
  color: '#52c41a',
  sort_order: 0,
  is_protected: false,
  settings_override: {},
  org_id: null,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
};

describe('EnvironmentDetailPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(environmentService.get).mockResolvedValue(mockEnv);
    vi.mocked(environmentService.listAgents).mockResolvedValue({
      environment: 'dev',
      data: [],
    });
    vi.mocked(environmentService.list).mockResolvedValue({
      data: [mockEnv],
      total: 1,
    });
  });

  const renderPage = () =>
    render(
      <TestQueryWrapper withRouter={false}>
        <MemoryRouter initialEntries={['/environments/dev']}>
          <Routes>
            <Route path="/environments/:envName" element={<EnvironmentDetailPage />} />
          </Routes>
        </MemoryRouter>
      </TestQueryWrapper>,
    );

  it('renders environment detail page', async () => {
    renderPage();
    await waitFor(() => {
      expect(vi.mocked(environmentService.get)).toHaveBeenCalledWith('dev');
    });
  });

  it('displays environment info', async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText('已发布 Agent')).toBeTruthy();
    });
  });

  it('shows publish and diff buttons', async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText('发布 Agent')).toBeTruthy();
      expect(screen.getByText('环境对比')).toBeTruthy();
    });
  });

  it('shows back button', async () => {
    renderPage();
    await waitFor(() => {
      expect(screen.getByText('返回列表')).toBeTruthy();
    });
  });
});
