import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, waitFor } from '@testing-library/react';
import { App } from 'antd';

/* ---------- mock services ---------- */
const mockAgentList = vi.fn();
vi.mock('../../services/agentService', () => ({
  agentService: {
    list: (...args: unknown[]) => mockAgentList(...args),
    get: vi.fn().mockResolvedValue({ name: 'bot', handoffs: [], model: 'gpt-4' }),
    update: vi.fn().mockResolvedValue({}),
  },
}));

/* ---------- mock ReactFlow ---------- */
const stableSetNodes = vi.fn();
const stableOnNodesChange = vi.fn();
const stableSetEdges = vi.fn();
const stableOnEdgesChange = vi.fn();
vi.mock('@xyflow/react', () => ({
  ReactFlow: ({ children }: { children?: React.ReactNode }) => <div data-testid="reactflow">{children}</div>,
  Background: () => <div data-testid="background" />,
  Controls: () => <div data-testid="controls" />,
  MiniMap: () => <div data-testid="minimap" />,
  useNodesState: (init: unknown[]) => [init ?? [], stableSetNodes, stableOnNodesChange],
  useEdgesState: (init: unknown[]) => [init ?? [], stableSetEdges, stableOnEdgesChange],
  addEdge: vi.fn(),
  MarkerType: { ArrowClosed: 'arrowclosed' },
  Position: { Top: 'top', Bottom: 'bottom', Left: 'left', Right: 'right' },
  Handle: () => <div />,
  Panel: ({ children }: { children?: React.ReactNode }) => <div>{children}</div>,
}));

vi.mock('@dagrejs/dagre', () => ({
  default: { graphlib: { Graph: vi.fn().mockImplementation(() => ({ setDefaultEdgeLabel: vi.fn(), setNode: vi.fn(), setEdge: vi.fn(), node: vi.fn().mockReturnValue({ x: 0, y: 0 }), setGraph: vi.fn() })) }, layout: vi.fn() },
}));

import HandoffEditorPage from '../../pages/agents/HandoffEditorPage';

describe('HandoffEditorPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockAgentList.mockResolvedValue({
      data: [
        { name: 'bot-1', description: 'test', model: 'gpt-4', is_active: true, handoffs: ['bot-2'] },
        { name: 'bot-2', description: 'helper', model: 'gpt-4', is_active: true, handoffs: [] },
      ],
    });
  });

  it('渲染页面标题', async () => {
    const { container } = render(<App><HandoffEditorPage /></App>);
    await waitFor(() => {
      const text = container.textContent ?? '';
      expect(text).toContain('Handoff');
    }, { timeout: 5000 });
  });

  it('渲染 ReactFlow 画布', async () => {
    const { container } = render(<App><HandoffEditorPage /></App>);
    await waitFor(() => {
      const flow = container.querySelector('[data-testid="reactflow"]');
      expect(flow).toBeTruthy();
    }, { timeout: 5000 });
  });

  it('调用 Agent 列表接口', async () => {
    render(<App><HandoffEditorPage /></App>);
    await waitFor(() => {
      expect(mockAgentList).toHaveBeenCalled();
    }, { timeout: 5000 });
  });

  it('加载失败不崩溃', async () => {
    mockAgentList.mockRejectedValueOnce(new Error('fail'));
    const { container } = render(<App><HandoffEditorPage /></App>);
    await waitFor(() => {
      expect(container).toBeTruthy();
    }, { timeout: 5000 });
  });
});
