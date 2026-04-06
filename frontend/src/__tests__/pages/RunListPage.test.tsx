import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, act } from '@testing-library/react';

/* ---------- mock tokenUsageService ---------- */
const mockList = vi.fn();
const mockSummary = vi.fn();
vi.mock('../../services/tokenUsageService', () => ({
  tokenUsageService: {
    list: (...args: unknown[]) => mockList(...args),
    summary: (...args: unknown[]) => mockSummary(...args),
  },
}));

/* ---------- mock ProTable ---------- */
vi.mock('@ant-design/pro-components', () => ({
  ProTable: (props: Record<string, unknown>) => {
    const { headerTitle, dataSource } = props as {
      headerTitle?: React.ReactNode;
      dataSource?: Array<{ id?: string; agent_name?: string }>;
    };
    return (
      <div data-testid="pro-table">
        <div data-testid="header-title">{headerTitle}</div>
        <div data-testid="data">
          {dataSource?.map((d, i) => <span key={i}>{d.agent_name ?? d.id}</span>)}
        </div>
      </div>
    );
  },
}));

import RunListPage from '../../pages/runs/RunListPage';

describe('RunListPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockList.mockResolvedValue({
      data: [
        {
          id: 'u1', agent_name: 'bot', model: 'gpt-4',
          prompt_tokens: 100, completion_tokens: 50, total_tokens: 150,
          trace_id: 't1', timestamp: '2024-01-01T00:00:00Z',
        },
      ],
      total: 1,
    });
    mockSummary.mockResolvedValue({
      data: [
        { agent_name: 'bot', model: 'gpt-4', total_prompt_tokens: 100, total_completion_tokens: 50, total_tokens: 150, call_count: 1 },
      ],
    });
  });

  it('渲染页面标题', async () => {
    let container!: HTMLElement;
    await act(async () => {
      ({ container } = render(<RunListPage />));
    });
    const text = container.textContent ?? '';
    expect(text).toContain('Token');
  });

  it('渲染统计卡片', async () => {
    let container!: HTMLElement;
    await act(async () => {
      ({ container } = render(<RunListPage />));
    });
    const text = container.textContent ?? '';
    // 页面渲染总 Token / 调用次数 等统计
    expect(text).toContain('总 Token');
  });

  it('调用列表和汇总接口', async () => {
    await act(async () => {
      render(<RunListPage />);
    });
    expect(mockList).toHaveBeenCalled();
    expect(mockSummary).toHaveBeenCalled();
  });

  it('切换分组模式', async () => {
    let container!: HTMLElement;
    await act(async () => {
      ({ container } = render(<RunListPage />));
    });
    const text = container.textContent ?? '';
    // 页面有 Segmented 控件含 "Agent + 模型" / "按用户" / "按模型"
    expect(text).toContain('Agent + 模型');
  });

  it('加载失败不崩溃', async () => {
    mockList.mockRejectedValueOnce(new Error('fail'));
    mockSummary.mockRejectedValueOnce(new Error('fail'));
    let container!: HTMLElement;
    await act(async () => {
      ({ container } = render(<RunListPage />));
    });
    expect(container).toBeTruthy();
  });
});
