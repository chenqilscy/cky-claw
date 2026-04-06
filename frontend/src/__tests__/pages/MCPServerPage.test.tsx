import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, waitFor } from '@testing-library/react';

// Mock ProTable
vi.mock('@ant-design/pro-components', () => ({
  ProTable: (props: {
    headerTitle?: string;
    dataSource?: unknown[];
    toolBarRender?: () => React.ReactNode[];
  }) => (
    <div data-testid="pro-table">
      {props.headerTitle && <h3>{props.headerTitle}</h3>}
      {props.toolBarRender && <div data-testid="toolbar">{props.toolBarRender()}</div>}
      {props.dataSource?.map((_, i) => <div key={i} data-testid="table-row" />)}
    </div>
  ),
}));

// Mock 服务
const mockList = vi.fn();
vi.mock('../../services/mcpServerService', () => ({
  mcpServerService: {
    list: (...args: unknown[]) => mockList(...args),
    create: vi.fn(),
    update: vi.fn(),
    delete: vi.fn(),
    test: vi.fn(),
    listTools: vi.fn(),
  },
  TRANSPORT_TYPES: ['stdio', 'sse', 'http'],
}));

import MCPServerPage from '../../pages/mcp/MCPServerPage';

describe('MCPServerPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockList.mockResolvedValue({
      data: [
        {
          id: 'mcp-1',
          name: 'test-mcp',
          transport_type: 'stdio',
          command: 'python server.py',
          is_enabled: true,
          created_at: '2026-01-01T00:00:00Z',
        },
      ],
      total: 1,
    });
  });

  it('渲染 MCP Server 管理标题', async () => {
    render(<MCPServerPage />);
    await waitFor(() => {
      expect(document.body.textContent).toContain('MCP Server 管理');
    });
  });

  it('渲染新建按钮', async () => {
    render(<MCPServerPage />);
    await waitFor(() => {
      expect(document.body.textContent).toContain('新建 MCP Server');
    });
  });

  it('调用列表接口', async () => {
    render(<MCPServerPage />);
    await waitFor(() => {
      expect(mockList).toHaveBeenCalled();
    });
  });

  it('加载失败不崩溃', async () => {
    mockList.mockRejectedValueOnce(new Error('fail'));
    render(<MCPServerPage />);
    await waitFor(() => {
      expect(document.body.textContent).toContain('MCP Server 管理');
    });
  });
});
