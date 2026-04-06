import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, act } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

/* ---------- mock hooks ---------- */
vi.mock('../../hooks/useWorkflowQueries', () => ({
  useWorkflow: () => ({
    data: { id: 'w1', name: 'flow', steps: [], edges: [], description: '' },
    isLoading: false,
  }),
  useCreateWorkflow: () => ({ mutateAsync: vi.fn().mockResolvedValue({ id: 'w2' }) }),
  useUpdateWorkflow: () => ({ mutateAsync: vi.fn().mockResolvedValue({}) }),
  useValidateWorkflow: () => ({ mutateAsync: vi.fn().mockResolvedValue({ valid: true }) }),
}));

/* ---------- mock ReactFlow ---------- */
vi.mock('@xyflow/react', () => ({
  ReactFlow: ({ children }: { children?: React.ReactNode }) => <div data-testid="reactflow">{children}</div>,
  Background: () => <div data-testid="background" />,
  Controls: () => <div data-testid="controls" />,
  MiniMap: () => <div data-testid="minimap" />,
  useNodesState: (init: unknown[]) => [init ?? [], vi.fn(), vi.fn()],
  useEdgesState: (init: unknown[]) => [init ?? [], vi.fn(), vi.fn()],
  addEdge: vi.fn((_conn: unknown, edges: unknown[]) => edges),
  MarkerType: { ArrowClosed: 'arrowclosed' },
  Position: { Top: 'top', Bottom: 'bottom', Left: 'left', Right: 'right' },
  Panel: ({ children }: { children?: React.ReactNode }) => <div>{children}</div>,
}));

import WorkflowEditorPage from '../../pages/workflows/WorkflowEditorPage';

function renderPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={['/workflow-editor']}>
        <WorkflowEditorPage />
      </MemoryRouter>
    </QueryClientProvider>
  );
}

describe('WorkflowEditorPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('渲染页面标题', async () => {
    let container!: HTMLElement;
    await act(async () => {
      ({ container } = renderPage());
    });
    const text = container.textContent ?? '';
    expect(text).toContain('创建');
  });

  it('渲染 ReactFlow 画布', async () => {
    let container!: HTMLElement;
    await act(async () => {
      ({ container } = renderPage());
    });
    const flow = container.querySelector('[data-testid="reactflow"]');
    expect(flow).toBeTruthy();
  });

  it('渲染创建按钮', async () => {
    let container!: HTMLElement;
    await act(async () => {
      ({ container } = renderPage());
    });
    const text = container.textContent ?? '';
    expect(text).toContain('创建');
  });

  it('渲染步骤类型选项', async () => {
    let container!: HTMLElement;
    await act(async () => {
      ({ container } = renderPage());
    });
    const text = container.textContent ?? '';
    // 侧边栏有 "Agent 步骤" / "并行步骤" 等可拖拽项
    expect(text).toContain('Agent');
  });
});
