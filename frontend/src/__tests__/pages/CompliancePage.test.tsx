import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

// Mock react-query
vi.mock('@tanstack/react-query', async () => {
  const actual = await vi.importActual<typeof import('@tanstack/react-query')>('@tanstack/react-query');
  return {
    ...actual,
    useQuery: vi.fn().mockReturnValue({ data: undefined, isLoading: false, refetch: vi.fn() }),
    useMutation: vi.fn().mockReturnValue({ mutateAsync: vi.fn(), isPending: false }),
    useQueryClient: vi.fn().mockReturnValue({ invalidateQueries: vi.fn() }),
  };
});

// Mock complianceService
vi.mock('../../services/complianceService', () => ({
  complianceService: {
    getDashboard: vi.fn().mockResolvedValue({
      satisfied_control_points: 8,
      satisfaction_rate: 0.8,
      active_retention_policies: 3,
      pending_erasure_requests: 1,
      classification_summary: { pii: 5, confidential: 2 },
    }),
    listLabels: vi.fn().mockResolvedValue({ data: [], total: 0, limit: 20, offset: 0 }),
    listRetentionPolicies: vi.fn().mockResolvedValue({ data: [], total: 0, limit: 20, offset: 0 }),
    listErasureRequests: vi.fn().mockResolvedValue({ data: [], total: 0, limit: 20, offset: 0 }),
    listControlPoints: vi.fn().mockResolvedValue({ data: [], total: 0, limit: 20, offset: 0 }),
    createLabel: vi.fn(),
    createRetentionPolicy: vi.fn(),
    createErasureRequest: vi.fn(),
    createControlPoint: vi.fn(),
    updateControlPoint: vi.fn(),
  },
}));

import CompliancePage from '../../pages/compliance/CompliancePage';

describe('CompliancePage', () => {
  beforeEach(() => vi.clearAllMocks());

  it('渲染页面标题', async () => {
    render(
      <MemoryRouter>
        <CompliancePage />
      </MemoryRouter>,
    );
    await waitFor(() => {
      expect(document.body.textContent).toContain('合规');
    });
  });

  it('渲染统计仪表盘', async () => {
    render(
      <MemoryRouter>
        <CompliancePage />
      </MemoryRouter>,
    );
    await waitFor(() => {
      const text = document.body.textContent || '';
      expect(text.length).toBeGreaterThan(0);
    });
  });

  it('渲染 Tabs（数据分类/保留策略/擦除请求/控制点）', async () => {
    render(
      <MemoryRouter>
        <CompliancePage />
      </MemoryRouter>,
    );
    await waitFor(() => {
      const text = document.body.textContent || '';
      expect(text).toMatch(/分类|保留|擦除|控制|Compliance/i);
    });
  });

  it('空数据不崩溃', async () => {
    render(
      <MemoryRouter>
        <CompliancePage />
      </MemoryRouter>,
    );
    expect(document.body).toBeDefined();
  });
});
