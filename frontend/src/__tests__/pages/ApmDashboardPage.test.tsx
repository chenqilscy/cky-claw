import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, act } from '@testing-library/react';

/* ---------- mock apmService ---------- */
const mockDashboard = vi.fn();
vi.mock('../../services/apmService', () => ({
  apmService: {
    dashboard: (...args: unknown[]) => mockDashboard(...args),
  },
}));

/* ---------- mock ECharts ---------- */
vi.mock('echarts-for-react', () => ({
  default: (props: Record<string, unknown>) => (
    <div data-testid="echarts">{JSON.stringify(props.option ?? {}).slice(0, 50)}</div>
  ),
}));

import ApmDashboardPage from '../../pages/apm/ApmDashboardPage';

const MOCK_DASHBOARD = {
  overview: {
    total_traces: 100,
    total_tokens: 50000,
    total_cost: 12.5,
    avg_latency_ms: 320,
    active_agents: 5,
    error_count: 2,
  },
  agent_ranking: [
    { agent_name: 'bot-1', call_count: 50, total_tokens: 20000, avg_latency_ms: 300, error_rate: 0.02, total_cost: 5.5, avg_duration_ms: 300, error_count: 1 },
  ],
  model_usage: [
    { model: 'gpt-4', total_tokens: 30000, call_count: 40, avg_tokens_per_call: 750, total_cost: 7.0, avg_duration_ms: 250, prompt_tokens: 20000, completion_tokens: 10000 },
  ],
  daily_trend: [
    { date: '2024-01-01', traces: 10, tokens: 5000, cost: 1.2 },
  ],
  tool_usage: [
    { tool_name: 'web_search', call_count: 20, avg_duration_ms: 150 },
  ],
};

describe('ApmDashboardPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockDashboard.mockResolvedValue(MOCK_DASHBOARD);
  });

  it('渲染页面标题', async () => {
    let container!: HTMLElement;
    await act(async () => {
      ({ container } = render(<ApmDashboardPage />));
    });
    const text = container.textContent ?? '';
    expect(text).toContain('APM');
  });

  it('渲染统计卡片', async () => {
    let container!: HTMLElement;
    await act(async () => {
      ({ container } = render(<ApmDashboardPage />));
    });
    const text = container.textContent ?? '';
    expect(text).toContain('100');
  });

  it('调用 dashboard 接口', async () => {
    await act(async () => {
      render(<ApmDashboardPage />);
    });
    expect(mockDashboard).toHaveBeenCalledWith(30);
  });

  it('加载失败显示错误提示', async () => {
    mockDashboard.mockRejectedValueOnce(new Error('fail'));
    let container!: HTMLElement;
    await act(async () => {
      ({ container } = render(<ApmDashboardPage />));
    });
    const text = container.textContent ?? '';
    expect(text).toContain('失败');
  });

  it('渲染 ECharts 图表', async () => {
    let container!: HTMLElement;
    await act(async () => {
      ({ container } = render(<ApmDashboardPage />));
    });
    const charts = container.querySelectorAll('[data-testid="echarts"]');
    expect(charts.length).toBeGreaterThan(0);
  });
});
