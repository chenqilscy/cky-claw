import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

// Mock organizationService
vi.mock('../../services/organizationService', () => ({
  organizationService: {
    list: vi.fn(),
    create: vi.fn(),
    update: vi.fn(),
    delete: vi.fn(),
  },
}));

import OrganizationPage from '../../pages/organizations/OrganizationPage';
import { organizationService } from '../../services/organizationService';

function createWrapper() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={qc}>
      <MemoryRouter>{children}</MemoryRouter>
    </QueryClientProvider>
  );
}

describe('OrganizationPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(organizationService.list).mockResolvedValue({
      data: [
        {
          id: 'org-1',
          name: '测试组织',
          slug: 'test-org',
          description: '测试描述',
          settings: {},
          quota: {},
          is_active: true,
          created_at: '2026-01-01T00:00:00Z',
          updated_at: '2026-01-01T00:00:00Z',
        },
      ],
      total: 1,
      limit: 200,
      offset: 0,
    } as never);
  });

  it('renders page title', async () => {
    render(<OrganizationPage />, { wrapper: createWrapper() });
    await waitFor(() => {
      expect(document.body.textContent).toContain('组织');
    });
  });

  it('calls organizationService.list on mount', async () => {
    render(<OrganizationPage />, { wrapper: createWrapper() });
    await waitFor(() => {
      expect(vi.mocked(organizationService.list)).toHaveBeenCalled();
    });
  });

  it('renders organization data', async () => {
    render(<OrganizationPage />, { wrapper: createWrapper() });
    await waitFor(() => {
      expect(document.body.textContent).toContain('测试组织');
    });
  });

  it('renders create button', async () => {
    render(<OrganizationPage />, { wrapper: createWrapper() });
    await waitFor(() => {
      expect(document.body.textContent).toContain('新建');
    });
  });
});
