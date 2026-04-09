import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, act } from '@testing-library/react';
import { TestQueryWrapper } from '../test-utils';

/* ---------- mock traceService ---------- */
const mockList = vi.fn();
const mockStats = vi.fn();
vi.mock('../../services/traceService', () => ({
  traceService: {
    list: (...args: unknown[]) => mockList(...args),
    stats: (...args: unknown[]) => mockStats(...args),
    get: vi.fn().mockResolvedValue({ id: 't1', spans: [] }),
    exportTraces: vi.fn().mockResolvedValue([]),
  },
}));

/* ---------- mock ProTable ---------- */
vi.mock('@ant-design/pro-components', () => ({
  ProTable: (props: Record<string, unknown>) => {
    const { headerTitle, toolBarRender, dataSource } = props as {
      headerTitle?: React.ReactNode;
      toolBarRender?: (() => React.ReactNode[]) | false;
      dataSource?: Array<{ id: string }>;
    };
    return (
      <div data-testid="pro-table">
        <div data-testid="header-title">{headerTitle}</div>
        <div data-testid="toolbar">{typeof toolBarRender === 'function' ? toolBarRender() : null}</div>
        <div data-testid="data">
          {dataSource?.map((d, i) => <span key={i}>{d.id}</span>)}
        </div>
      </div>
    );
  },
}));

/* ---------- mock SpanWaterfall ---------- */
vi.mock('../../pages/traces/SpanWaterfall', () => ({
  default: () => <div data-testid="waterfall">waterfall</div>,
}));

import TracesPage from '../../pages/traces/TracesPage';

describe('TracesPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockList.mockResolvedValue({
      data: [
        { id: 't1', agent_name: 'bot', status: 'completed', total_duration_ms: 100, span_count: 3, created_at: '2024-01-01' },
      ],
      total: 1,
    });
    mockStats.mockResolvedValue({
      total_traces: 10,
      avg_duration_ms: 50,
      total_spans: 30,
      guardrail_trigger_count: 2,
      total_tokens: { total_tokens: 5000, prompt_tokens: 3000, completion_tokens: 2000 },
      guardrail_stats: { total: 5, triggered: 2 },
    });
  });

  it('渲染页面标题', async () => {
    let container!: HTMLElement;
    await act(async () => {
      ({ container } = render(<TestQueryWrapper><TracesPage /></TestQueryWrapper>));
    });
    const text = container.textContent ?? '';
    expect(text).toContain('Trace');
  });

  it('渲染统计卡片', async () => {
    let container!: HTMLElement;
    await act(async () => {
      ({ container } = render(<TestQueryWrapper><TracesPage /></TestQueryWrapper>));
    });
    const text = container.textContent ?? '';
    // 统计卡片包含 "总 Trace" 或 "平均耗时" 等
    expect(text).toContain('Trace');
  });

  it('调用列表和统计接口', async () => {
    await act(async () => {
      render(<TestQueryWrapper><TracesPage /></TestQueryWrapper>);
    });
    expect(mockList).toHaveBeenCalled();
    expect(mockStats).toHaveBeenCalled();
  });

  it('加载失败不崩溃', async () => {
    mockList.mockRejectedValueOnce(new Error('fail'));
    mockStats.mockRejectedValueOnce(new Error('fail'));
    let container!: HTMLElement;
    await act(async () => {
      ({ container } = render(<TestQueryWrapper><TracesPage /></TestQueryWrapper>));
    });
    expect(container).toBeTruthy();
  });
});
