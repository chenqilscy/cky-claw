import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, waitFor } from '@testing-library/react';
import { TestQueryWrapper } from '../test-utils';
import { MemoryRouter } from 'react-router-dom';

// Mock navigate
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom');
  return { ...actual, useNavigate: () => vi.fn() };
});

// Mock providerService — use inline functions to avoid hoisting issues
vi.mock('../../services/providerService', () => ({
  providerService: {
    list: vi.fn(),
    delete: vi.fn(),
    toggle: vi.fn(),
    testConnection: vi.fn(),
  },
}));

// Mock message
vi.mock('antd', async () => {
  const actual = await vi.importActual<typeof import('antd')>('antd');
  return { ...actual, message: { success: vi.fn(), error: vi.fn() } };
});

// Mock ProTable to avoid heavy @ant-design/pro-components rendering
vi.mock('@ant-design/pro-components', () => ({
  ProTable: ({ dataSource, headerTitle }: { dataSource: unknown[]; headerTitle: string }) => (
    <div data-testid="pro-table">
      <div>{headerTitle}</div>
      <div data-testid="row-count">{Array.isArray(dataSource) ? dataSource.length : 0}</div>
    </div>
  ),
}));

import ProviderListPage from '../../pages/providers/ProviderListPage';
import { providerService } from '../../services/providerService';

describe('ProviderListPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(providerService.list).mockResolvedValue({
      data: [
        {
          id: 'p-1',
          name: 'openai-prod',
          provider_type: 'openai',
          is_enabled: true,
          health_status: 'healthy',
          created_at: '2026-01-01T00:00:00Z',
        },
      ],
      total: 1,
    } as never);
  });

  it('renders and fetches providers on mount', async () => {
    render(
      <TestQueryWrapper>
        <MemoryRouter>
          <ProviderListPage />
        </MemoryRouter>
      </TestQueryWrapper>,
    );
    await waitFor(() => {
      expect(vi.mocked(providerService.list)).toHaveBeenCalled();
    });
  });

  it('renders page content', async () => {
    render(
      <TestQueryWrapper>
        <MemoryRouter>
          <ProviderListPage />
        </MemoryRouter>
      </TestQueryWrapper>,
    );
    await waitFor(() => {
      expect(document.body.textContent).toContain('模型厂商');
    });
  });

  it('shows provider data in table', async () => {
    render(
      <TestQueryWrapper>
        <MemoryRouter>
          <ProviderListPage />
        </MemoryRouter>
      </TestQueryWrapper>,
    );
    await waitFor(() => {
      // PRO table mock shows row count
      const rowCount = document.querySelector('[data-testid="row-count"]');
      expect(rowCount?.textContent).toBe('1');
    });
  });
});
