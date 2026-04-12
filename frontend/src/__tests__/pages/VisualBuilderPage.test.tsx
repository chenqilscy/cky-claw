import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

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
  useNodesState: (initial: unknown[]) => [initial, vi.fn(), vi.fn()],
  useEdgesState: (initial: unknown[]) => [initial, vi.fn(), vi.fn()],
  addEdge: vi.fn(),
}));

import VisualBuilderPage from '../../pages/agents/VisualBuilderPage';

describe('VisualBuilderPage', () => {
  beforeEach(() => vi.clearAllMocks());

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

  it('渲染保存按钮', () => {
    render(
      <MemoryRouter>
        <VisualBuilderPage />
      </MemoryRouter>,
    );
    expect(document.body.textContent).toContain('保存');
  });

  it('渲染 JSON 输出区域', () => {
    render(
      <MemoryRouter>
        <VisualBuilderPage />
      </MemoryRouter>,
    );
    const text = document.body.textContent ?? '';
    expect(text).toContain('Agent JSON');
    expect(text).toContain('instructions');
  });

  it('初始节点包含 Agent Core', () => {
    render(
      <MemoryRouter>
        <VisualBuilderPage />
      </MemoryRouter>,
    );
    expect(screen.getByTestId('node-count').textContent).toBe('1');
  });
});
