import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

/* ---------- mock antd message (prevents jsdom hang) ---------- */
vi.mock('antd', async () => {
  const actual = await vi.importActual<Record<string, unknown>>('antd');
  return {
    ...actual,
    message: { error: vi.fn(), info: vi.fn(), success: vi.fn(), warning: vi.fn() },
  };
});

/* ---------- mock CSS ---------- */
vi.mock('@xyflow/react/dist/style.css', () => ({}));

/* ---------- mock services ---------- */
const mockGetTeam = vi.fn();
const mockAgentList = vi.fn();
vi.mock('../../services/teamService', () => ({
  getTeam: (...args: unknown[]) => mockGetTeam(...args),
  updateTeam: vi.fn().mockResolvedValue({}),
}));
vi.mock('../../services/agentService', () => ({
  agentService: {
    list: (...args: unknown[]) => mockAgentList(...args),
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
  MarkerType: { ArrowClosed: 'arrowclosed' },
  Position: { Top: 'top', Bottom: 'bottom', Left: 'left', Right: 'right' },
  Handle: () => <div />,
  Panel: ({ children }: { children?: React.ReactNode }) => <div>{children}</div>,
}));

vi.mock('@dagrejs/dagre', () => ({
  default: { graphlib: { Graph: vi.fn().mockImplementation(() => ({ setDefaultEdgeLabel: vi.fn(), setNode: vi.fn(), setEdge: vi.fn(), node: vi.fn().mockReturnValue({ x: 0, y: 0 }), setGraph: vi.fn() })) }, layout: vi.fn() },
}));

import TeamFlowPage from '../../pages/teams/TeamFlowPage';

function renderPage(teamId = 'team-1') {
  return render(
    <MemoryRouter initialEntries={[`/teams/flow?id=${teamId}`]}>
      <TeamFlowPage />
    </MemoryRouter>
  );
}

describe('TeamFlowPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockGetTeam.mockResolvedValue({
      id: 'team-1', name: 'test-team', protocol: 'SEQUENTIAL',
      member_agent_ids: ['bot-1'],
      members: [{ agent_name: 'bot-1', role: 'member' }],
    });
    mockAgentList.mockResolvedValue({
      data: [{ id: 'a1', name: 'bot-1', description: 'test', model: 'gpt-4' }],
    });
  });

  it('渲染页面标题', async () => {
    const { container } = renderPage();
    await waitFor(() => {
      const text = container.textContent ?? '';
      expect(text).toContain('团队拓扑');
    }, { timeout: 5000 });
  });

  it('渲染 ReactFlow 画布', async () => {
    const { container } = renderPage();
    await waitFor(() => {
      const flow = container.querySelector('[data-testid="reactflow"]');
      expect(flow).toBeTruthy();
    }, { timeout: 5000 });
  });

  it('加载失败不崩溃', async () => {
    mockGetTeam.mockRejectedValueOnce(new Error('fail'));
    const { container } = renderPage();
    await waitFor(() => {
      expect(container).toBeTruthy();
    }, { timeout: 5000 });
  });
});
