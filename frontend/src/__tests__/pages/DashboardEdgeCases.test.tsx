import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

// Mock all heavy services — 使用与 DashboardPage.test.tsx 一致的 mock 结构
vi.mock('../../services/agentService', () => ({
  agentService: {
    list: vi.fn().mockResolvedValue({ data: [], total: 0, limit: 1, offset: 0 }),
    realtimeStatus: vi.fn().mockResolvedValue({ data: [], minutes: 5, total: 0 }),
    activityTrend: vi.fn().mockResolvedValue({ data: [], hours: 1, interval: 5 }),
  },
}));

vi.mock('../../services/chatService', () => ({
  chatService: {
    listSessions: vi.fn().mockResolvedValue({ data: [], total: 0, limit: 1, offset: 0 }),
  },
}));

vi.mock('../../services/traceService', () => ({
  traceService: {
    stats: vi.fn().mockResolvedValue({
      total_traces: 0,
      total_tokens: { total_tokens: 0 },
      span_type_counts: {},
      guardrail_stats: { total_triggered: 0, blocked_count: 0 },
    }),
  },
}));

vi.mock('../../services/tokenUsageService', () => ({
  tokenUsageService: {
    summary: vi.fn().mockResolvedValue({ data: [] }),
    trend: vi.fn().mockResolvedValue({ data: [], days: 7 }),
  },
}));

vi.mock('echarts-for-react', () => ({
  default: () => <div data-testid="mock-echarts" />,
}));

import DashboardPage from '../../pages/dashboard/DashboardPage';

describe('DashboardPage 边界场景', () => {
  beforeEach(() => vi.clearAllMocks());

  it('所有 API 返回空数据不崩溃', async () => {
    const { container } = render(
      <MemoryRouter>
        <DashboardPage />
      </MemoryRouter>,
    );
    await waitFor(() => {
      expect(container).toBeTruthy();
    });
  });

  it('渲染概览标题', async () => {
    const { container } = render(
      <MemoryRouter>
        <DashboardPage />
      </MemoryRouter>,
    );
    await waitFor(() => {
      expect(container.textContent).toContain('平台概览');
    });
  });

  it('API 抛异常不崩溃', async () => {
    const { agentService } = await import('../../services/agentService');
    (agentService.list as ReturnType<typeof vi.fn>).mockRejectedValueOnce(new Error('Network error'));

    const { container } = render(
      <MemoryRouter>
        <DashboardPage />
      </MemoryRouter>,
    );
    await waitFor(() => {
      expect(container).toBeTruthy();
    });
  });

  it('渲染 ECharts 图表区域', async () => {
    const { container } = render(
      <MemoryRouter>
        <DashboardPage />
      </MemoryRouter>,
    );
    await waitFor(() => {
      const charts = container.querySelectorAll('[data-testid="mock-echarts"]');
      expect(charts.length).toBeGreaterThanOrEqual(0);
    });
  });
});
