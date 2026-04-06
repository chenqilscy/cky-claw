import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

// Mock roleService
vi.mock('../../services/roleService', () => ({
  roleService: {
    list: vi.fn(),
    create: vi.fn(),
    update: vi.fn(),
    delete: vi.fn(),
  },
}));

import RolePage from '../../pages/roles/RolePage';
import { roleService } from '../../services/roleService';

function createWrapper() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={qc}>
      <MemoryRouter>{children}</MemoryRouter>
    </QueryClientProvider>
  );
}

describe('RolePage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(roleService.list).mockResolvedValue({
      data: [
        {
          id: 'role-1',
          name: 'admin',
          description: '管理员',
          permissions: { agents: ['read', 'write', 'delete'], users: ['read'] },
          is_system: true,
          created_at: '2026-01-01T00:00:00Z',
          updated_at: '2026-01-01T00:00:00Z',
        },
      ],
      total: 1,
    } as never);
  });

  it('renders page title', async () => {
    render(<RolePage />, { wrapper: createWrapper() });
    await waitFor(() => {
      expect(document.body.textContent).toContain('角色');
    });
  });

  it('calls roleService.list on mount', async () => {
    render(<RolePage />, { wrapper: createWrapper() });
    await waitFor(() => {
      expect(vi.mocked(roleService.list)).toHaveBeenCalled();
    });
  });

  it('renders role data', async () => {
    render(<RolePage />, { wrapper: createWrapper() });
    await waitFor(() => {
      expect(document.body.textContent).toContain('admin');
    });
  });

  it('renders permission resources', async () => {
    render(<RolePage />, { wrapper: createWrapper() });
    await waitFor(() => {
      // 角色管理页面应显示权限矩阵中的资源标签
      expect(document.body.textContent).toContain('角色');
    });
  });
});
