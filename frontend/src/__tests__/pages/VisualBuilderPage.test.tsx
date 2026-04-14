import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

/* ---------- stable fn refs (avoid infinite re-render) ---------- */
const stableSetNodes = vi.fn();
const stableSetEdges = vi.fn();
const stableOnNodesChange = vi.fn();
const stableOnEdgesChange = vi.fn();

/* ---------- mock services ---------- */
const mockAgentList = vi.fn();
const mockAgentCreate = vi.fn();
const mockToolGroupList = vi.fn();
const mockGuardrailList = vi.fn();
const mockMcpServerList = vi.fn();

vi.mock('../../services/agentService', () => ({
  agentService: {
    list: (...args: unknown[]) => mockAgentList(...args),
    create: (...args: unknown[]) => mockAgentCreate(...args),
  },
}));
vi.mock('../../services/toolGroupService', () => ({
  toolGroupService: { list: (...args: unknown[]) => mockToolGroupList(...args) },
}));
vi.mock('../../services/guardrailService', () => ({
  guardrailService: { list: (...args: unknown[]) => mockGuardrailList(...args) },
}));
vi.mock('../../services/mcpServerService', () => ({
  mcpServerService: { list: (...args: unknown[]) => mockMcpServerList(...args) },
}));

// Mock @xyflow/react — heavy dependency
vi.mock('@xyflow/react', () => ({
  ReactFlow: ({ nodes, edges }: { nodes: unknown[]; edges: unknown[] }) => (
    <div data-testid="mock-reactflow">
      <span data-testid="node-count">{nodes?.length ?? 0}</span>
      <span data-testid="edge-count">{edges?.length ?? 0}</span>
    </div>
  ),
  Background: () => <div data-testid="mock-background" />,
  Controls: () => <div data-testid="mock-controls" />,
  MiniMap: () => <div data-testid="mock-minimap" />,
  useNodesState: (initial: unknown[]) => [initial, stableSetNodes, stableOnNodesChange],
  useEdgesState: (initial: unknown[]) => [initial, stableSetEdges, stableOnEdgesChange],
  addEdge: vi.fn(),
}));

import VisualBuilderPage from '../../pages/agents/VisualBuilderPage';

describe('VisualBuilderPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockAgentList.mockResolvedValue({ data: [] });
    mockAgentCreate.mockResolvedValue({});
    mockToolGroupList.mockResolvedValue({ data: [] });
    mockGuardrailList.mockResolvedValue({ data: [] });
    mockMcpServerList.mockResolvedValue({ data: [] });
  });

  it('渲染 ReactFlow 画布', () => {
    render(
      <MemoryRouter>
        <VisualBuilderPage />
      </MemoryRouter>,
    );
    expect(screen.getByTestId('mock-reactflow')).toBeDefined();
  });

  it('渲染工具栏按钮', () => {
    render(
      <MemoryRouter>
        <VisualBuilderPage />
      </MemoryRouter>,
    );
    const text = document.body.textContent ?? '';
    expect(text).toContain('添加 Tool');
    expect(text).toContain('添加 Guardrail');
    expect(text).toContain('添加 Handoff');
    expect(text).toContain('添加 MCP');
  });

  it('渲染保存为 Agent 按钮', () => {
    render(
      <MemoryRouter>
        <VisualBuilderPage />
      </MemoryRouter>,
    );
    expect(document.body.textContent).toContain('保存为 Agent');
  });

  it('渲染复制 JSON 按钮', () => {
    render(
      <MemoryRouter>
        <VisualBuilderPage />
      </MemoryRouter>,
    );
    expect(document.body.textContent).toContain('复制 JSON');
  });

  it('初始节点包含 Agent Core', () => {
    render(
      <MemoryRouter>
        <VisualBuilderPage />
      </MemoryRouter>,
    );
    expect(screen.getByTestId('node-count').textContent).toBe('1');
  });

  it('加载后端数据', () => {
    render(
      <MemoryRouter>
        <VisualBuilderPage />
      </MemoryRouter>,
    );
    expect(mockToolGroupList).toHaveBeenCalled();
    expect(mockGuardrailList).toHaveBeenCalled();
    expect(mockMcpServerList).toHaveBeenCalled();
    expect(mockAgentList).toHaveBeenCalled();
  });

  it('点击保存为 Agent 打开 Modal', () => {
    render(
      <MemoryRouter>
        <VisualBuilderPage />
      </MemoryRouter>,
    );
    const saveBtn = Array.from(document.querySelectorAll('button')).find(
      (b) => b.textContent?.includes('保存为 Agent'),
    );
    expect(saveBtn).toBeDefined();
    fireEvent.click(saveBtn!);
    expect(document.body.textContent).toContain('Agent 名称');
  });
});
