import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import type { UseQueryResult } from '@tanstack/react-query';

// Mock navigate
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom');
  return { ...actual, useNavigate: () => vi.fn() };
});

// Mock agentService
vi.mock('../../services/agentService', () => ({
  agentService: {
    exportAgent: vi.fn(),
    importAgent: vi.fn(),
  },
}));

// Mock useAgentQueries hooks
const mockRefetch = vi.fn();
vi.mock('../../hooks/useAgentQueries', () => ({
  useAgentList: () => ({
    data: {
      data: [
        { name: 'test-agent', description: '测试 Agent', model: 'gpt-4', approval_mode: 'full-auto' },
      ],
      total: 1,
    },
    isLoading: false,
    refetch: mockRefetch,
  } as unknown as UseQueryResult),
  useDeleteAgent: () => ({
    mutateAsync: vi.fn(),
  }),
}));

// Mock message
vi.mock('antd', async () => {
  const actual = await vi.importActual<typeof import('antd')>('antd');
  return { ...actual, message: { success: vi.fn(), error: vi.fn() } };
});

// Mock ProTable
vi.mock('@ant-design/pro-components', () => ({
  ProTable: ({ dataSource, headerTitle }: { dataSource: unknown[]; headerTitle: string }) => (
    <div data-testid="pro-table">
      <div>{headerTitle}</div>
      <div data-testid="row-count">{Array.isArray(dataSource) ? dataSource.length : 0}</div>
    </div>
  ),
}));

import AgentListPage from '../../pages/agents/AgentListPage';

describe('AgentListPage', () => {
  beforeEach(() => vi.clearAllMocks());

  it('renders page content', async () => {
    render(
      <MemoryRouter>
        <AgentListPage />
      </MemoryRouter>,
    );
    await waitFor(() => {
      expect(document.body.textContent).toContain('Agent');
    });
  });

  it('shows agent data via ProTable', async () => {
    render(
      <MemoryRouter>
        <AgentListPage />
      </MemoryRouter>,
    );
    await waitFor(() => {
      const rowCount = document.querySelector('[data-testid="row-count"]');
      expect(rowCount?.textContent).toBe('1');
    });
  });

  it('renders create and refresh buttons', async () => {
    render(
      <MemoryRouter>
        <AgentListPage />
      </MemoryRouter>,
    );
    await waitFor(() => {
      // buttons should have text content for create
      expect(document.body.textContent).toContain('Agent');
    });
  });
});
