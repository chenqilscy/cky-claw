import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, act } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

/* ---------- mock hooks ---------- */
const mockWorkflows = {
  data: [
    {
      id: 'w1', name: 'test-flow', description: 'desc',
      steps: [], edges: [], is_active: true, created_at: '2024-01-01',
    },
  ],
  total: 1,
};

vi.mock('../../hooks/useWorkflowQueries', () => ({
  useWorkflowList: () => ({ data: mockWorkflows, isLoading: false, refetch: vi.fn() }),
  useCreateWorkflow: () => ({ mutateAsync: vi.fn().mockResolvedValue({}) }),
  useUpdateWorkflow: () => ({ mutateAsync: vi.fn().mockResolvedValue({}) }),
  useDeleteWorkflow: () => ({ mutateAsync: vi.fn().mockResolvedValue({}) }),
  useValidateWorkflow: () => ({ mutateAsync: vi.fn().mockResolvedValue({ valid: true }) }),
}));

/* ---------- mock WorkflowGraphView ---------- */
vi.mock('../../pages/workflows/WorkflowGraphView', () => ({
  default: () => <div data-testid="graph-view">graph</div>,
}));

import WorkflowPage from '../../pages/workflows/WorkflowPage';

function renderPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>
        <WorkflowPage />
      </MemoryRouter>
    </QueryClientProvider>
  );
}

describe('WorkflowPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('渲染页面标题', async () => {
    let container!: HTMLElement;
    await act(async () => {
      ({ container } = renderPage());
    });
    const text = container.textContent ?? '';
    expect(text).toContain('工作流');
  });

  it('渲染新建按钮', async () => {
    let container!: HTMLElement;
    await act(async () => {
      ({ container } = renderPage());
    });
    const text = container.textContent ?? '';
    expect(text).toContain('新建');
  });

  it('渲染工作流列表记录', async () => {
    let container!: HTMLElement;
    await act(async () => {
      ({ container } = renderPage());
    });
    const text = container.textContent ?? '';
    expect(text).toContain('test-flow');
  });

  it('渲染操作按钮', async () => {
    let container!: HTMLElement;
    await act(async () => {
      ({ container } = renderPage());
    });
    const text = container.textContent ?? '';
    // 有 "编辑" / "预览" / "编排" / "删除" 等操作
    expect(text).toContain('可视化编排');
  });
});
