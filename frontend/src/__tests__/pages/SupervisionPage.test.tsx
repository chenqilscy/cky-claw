import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, act } from '@testing-library/react';

/* ---------- mock supervisionService ---------- */
const mockListSessions = vi.fn();
vi.mock('../../services/supervisionService', () => ({
  supervisionService: {
    listSessions: (...args: unknown[]) => mockListSessions(...args),
    getSessionDetail: vi.fn().mockResolvedValue({ id: 's1', agent_name: 'a', status: 'active', messages: [] }),
    pauseSession: vi.fn().mockResolvedValue({ message: 'ok' }),
    resumeSession: vi.fn().mockResolvedValue({ message: 'ok' }),
  },
}));

/* ---------- mock ProTable ---------- */
vi.mock('@ant-design/pro-components', () => ({
  ProTable: (props: Record<string, unknown>) => {
    const { headerTitle, toolBarRender, dataSource } = props as {
      headerTitle?: React.ReactNode;
      toolBarRender?: () => React.ReactNode[];
      dataSource?: Array<{ id: string }>;
    };
    return (
      <div data-testid="pro-table">
        <div data-testid="header-title">{headerTitle}</div>
        <div data-testid="toolbar">{toolBarRender?.()}</div>
        <div data-testid="data">
          {dataSource?.map((d, i) => <span key={i}>{d.id}</span>)}
        </div>
      </div>
    );
  },
}));

import SupervisionPage from '../../pages/supervision/SupervisionPage';

describe('SupervisionPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockListSessions.mockResolvedValue({
      data: [
        { id: 's1', agent_name: 'bot-1', status: 'active', current_turn: 3, created_at: '2024-01-01' },
      ],
    });
  });

  it('渲染页面标题', async () => {
    let container!: HTMLElement;
    await act(async () => {
      ({ container } = render(<SupervisionPage />));
    });
    const text = container.textContent ?? '';
    expect(text).toContain('监督面板');
  });

  it('渲染统计卡片', async () => {
    let container!: HTMLElement;
    await act(async () => {
      ({ container } = render(<SupervisionPage />));
    });
    const text = container.textContent ?? '';
    // 期望有 "总会话" / "运行中" / "已暂停" 之类的统计
    expect(text).toContain('活跃会话');
  });

  it('调用列表接口', async () => {
    await act(async () => {
      render(<SupervisionPage />);
    });
    expect(mockListSessions).toHaveBeenCalled();
  });

  it('加载失败不崩溃', async () => {
    mockListSessions.mockRejectedValueOnce(new Error('fail'));
    let container!: HTMLElement;
    await act(async () => {
      ({ container } = render(<SupervisionPage />));
    });
    expect(container).toBeTruthy();
  });
});
