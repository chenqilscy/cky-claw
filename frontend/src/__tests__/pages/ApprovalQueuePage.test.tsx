import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, waitFor } from '@testing-library/react';

// Mock useApprovalWs hook
vi.mock('../../hooks/useApprovalWs', () => ({
  useApprovalWs: vi.fn(),
}));

// Mock ProTable
vi.mock('@ant-design/pro-components', () => ({
  ProTable: (props: {
    headerTitle?: string;
    request?: (params: Record<string, unknown>) => Promise<unknown>;
    toolBarRender?: () => React.ReactNode[];
  }) => {
    if (props.request) {
      props.request({ current: 1, pageSize: 20 });
    }
    return (
      <div data-testid="pro-table">
        {props.headerTitle && <h3>{props.headerTitle}</h3>}
        {props.toolBarRender && <div data-testid="toolbar">{props.toolBarRender()}</div>}
      </div>
    );
  },
}));

// Mock 审批服务
const mockList = vi.fn();
vi.mock('../../services/approvalService', () => ({
  approvalService: {
    list: (...args: unknown[]) => mockList(...args),
    resolve: vi.fn(),
  },
}));

import ApprovalQueuePage from '../../pages/approvals/ApprovalQueuePage';

describe('ApprovalQueuePage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockList.mockResolvedValue({
      data: [
        {
          id: 'a1',
          agent_name: 'test-agent',
          trigger: 'tool_call',
          content: { tool_name: 'search' },
          status: 'pending',
          comment: null,
          created_at: '2026-01-01T00:00:00Z',
        },
      ],
      total: 1,
    });
  });

  it('渲染审批队列标题', () => {
    const { container } = render(<ApprovalQueuePage />);
    expect(container.textContent).toContain('审批队列');
  });

  it('渲染刷新按钮', () => {
    const { container } = render(<ApprovalQueuePage />);
    expect(container.textContent).toContain('刷新');
  });

  it('调用审批列表接口', async () => {
    render(<ApprovalQueuePage />);
    await waitFor(() => {
      expect(mockList).toHaveBeenCalled();
    });
  });

  it('渲染 WebSocket 连接状态', () => {
    const { container } = render(<ApprovalQueuePage />);
    expect(container.textContent).toContain('未连接');
  });
});
