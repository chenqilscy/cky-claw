import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';

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
vi.mock('../../services/agentVersionService', () => ({
  agentVersionService: {
    list: (...args: unknown[]) => mockList(...args),
    diff: vi.fn(),
    rollback: vi.fn(),
  },
}));

import AgentVersionPage from '../../pages/agents/AgentVersionPage';

function renderWithRouter(agentId = 'agent-1') {
  return render(
    <MemoryRouter initialEntries={[`/agents/${agentId}/versions`]}>
      <Routes>
        <Route path="/agents/:agentId/versions" element={<AgentVersionPage />} />
      </Routes>
    </MemoryRouter>
  );
}

describe('AgentVersionPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockList.mockResolvedValue({
      data: [
        {
          id: 'v1',
          version: 1,
          agent_id: 'agent-1',
          change_summary: '初始版本',
          snapshot: {},
          created_at: '2026-01-01T00:00:00Z',
        },
      ],
      total: 1,
    });
  });

  it('渲染返回按钮', async () => {
    renderWithRouter();
    await waitFor(() => {
      expect(document.body.textContent).toContain('返回 Agent 列表');
    });
  });

  it('渲染版本历史表格标题', async () => {
    renderWithRouter();
    await waitFor(() => {
      expect(document.body.textContent).toContain('版本历史');
    });
  });

  it('调用版本列表接口', async () => {
    renderWithRouter('agent-1');
    await waitFor(() => {
      expect(mockList).toHaveBeenCalledWith('agent-1', expect.objectContaining({
        limit: 20,
        offset: 0,
      }));
    });
  });

  it('加载失败不崩溃', async () => {
    mockList.mockRejectedValueOnce(new Error('fail'));
    renderWithRouter();
    await waitFor(() => {
      expect(document.body.textContent).toContain('版本历史');
    });
  });
});
