import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, waitFor, screen } from '@testing-library/react';
import { TestQueryWrapper } from '../test-utils';

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

vi.mock('@ant-design/pro-components', () => ({
  ProTable: ({ dataSource, headerTitle }: { dataSource: unknown[]; headerTitle: string }) => (
    <div data-testid="pro-table">
      <div>{headerTitle}</div>
      <div data-testid="row-count">{Array.isArray(dataSource) ? dataSource.length : 0}</div>
    </div>
  ),
}));

import EnvironmentListPage from '../../pages/environments/EnvironmentListPage';
import { environmentService } from '../../services/environmentService';

const mockEnvs = [
  {
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
  },
  {
    id: 'env-2',
    name: 'prod',
    display_name: '生产',
    description: '生产环境',
    color: '#f5222d',
    sort_order: 2,
    is_protected: true,
    settings_override: {},
    org_id: null,
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
  },
];

describe('EnvironmentListPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(environmentService.list).mockResolvedValue({
      data: mockEnvs,
      total: 2,
    });
  });

  it('renders and fetches environments on mount', async () => {
    render(
      <TestQueryWrapper>
          <EnvironmentListPage />
      </TestQueryWrapper>,
    );
    await waitFor(() => {
      expect(vi.mocked(environmentService.list)).toHaveBeenCalled();
    });
  });

  it('displays environment data in the table', async () => {
    render(
      <TestQueryWrapper>
          <EnvironmentListPage />
      </TestQueryWrapper>,
    );
    await waitFor(() => {
      expect(document.body.textContent).toContain('环境管理');
    });
    expect(screen.getByTestId('row-count').textContent).toBe('2');
  });

  it('calls list API', async () => {
    render(
      <TestQueryWrapper>
          <EnvironmentListPage />
      </TestQueryWrapper>,
    );
    await waitFor(() => {
      expect(vi.mocked(environmentService.list)).toHaveBeenCalledTimes(1);
    });
  });
});
