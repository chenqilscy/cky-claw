import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

// Mock all service dependencies
vi.mock('../../services/agentService', () => ({
  agentService: {
    list: vi.fn().mockResolvedValue({ data: [], total: 5, limit: 1, offset: 0 }),
    realtimeStatus: vi.fn().mockResolvedValue({
      data: [
        { agent_name: 'bot-1', run_count: 3, last_active_at: '2026-07-02T10:00:00Z', error_count: 0, status: 'active' },
      ],
      minutes: 5,
      total: 1,
    }),
    activityTrend: vi.fn().mockResolvedValue({
      data: [
        { time: '2026-07-02T09:55:00Z', run_count: 5, error_count: 0 },
        { time: '2026-07-02T10:00:00Z', run_count: 3, error_count: 1 },
      ],
      hours: 1,
      interval: 5,
    }),
  },
}));

vi.mock('../../services/chatService', () => ({
  chatService: {
    listSessions: vi.fn().mockResolvedValue({ data: [], total: 12, limit: 1, offset: 0 }),
  },
}));

vi.mock('../../services/traceService', () => ({
  traceService: {
    stats: vi.fn().mockResolvedValue({
      total_traces: 100,
      total_tokens: { total_tokens: 50000 },
      span_type_counts: { agent: 30, llm: 40, tool: 20, handoff: 5, guardrail: 5 },
      guardrail_stats: { total_triggered: 10, blocked_count: 3 },
    }),
  },
}));

vi.mock('../../services/tokenUsageService', () => ({
  tokenUsageService: {
    summary: vi.fn().mockResolvedValue({ data: [] }),
    trend: vi.fn().mockResolvedValue({
      data: [
        { date: '2026-07-01', total_tokens: 1200, total_cost: 0.05, call_count: 10, model: null },
        { date: '2026-07-02', total_tokens: 1800, total_cost: 0.08, call_count: 15, model: null },
      ],
      days: 7,
    }),
  },
}));

// Mock ECharts — avoid DOM measurement issues in jsdom
vi.mock('echarts-for-react', () => ({
  default: () => <div data-testid="mock-echarts" />,
}));

import DashboardPage from '../../pages/dashboard/DashboardPage';

describe('DashboardPage', () => {
  beforeEach(() => vi.clearAllMocks());

  it('renders dashboard title', async () => {
    render(
      <MemoryRouter>
        <DashboardPage />
      </MemoryRouter>,
    );
    await waitFor(() => {
      expect(screen.getByText('平台概览')).toBeDefined();
    });
  });

  it('shows agent count after loading', async () => {
    render(
      <MemoryRouter>
        <DashboardPage />
      </MemoryRouter>,
    );
    await waitFor(() => {
      expect(screen.getByText('Agent 总数')).toBeDefined();
    });
  });

  it('shows session count after loading', async () => {
    render(
      <MemoryRouter>
        <DashboardPage />
      </MemoryRouter>,
    );
    await waitFor(() => {
      expect(screen.getByText('Session 总数')).toBeDefined();
    });
  });

  it('renders ECharts component', async () => {
    render(
      <MemoryRouter>
        <DashboardPage />
      </MemoryRouter>,
    );
    await waitFor(() => {
      expect(screen.getAllByTestId('mock-echarts').length).toBeGreaterThan(0);
    });
  });

  it('renders token trend card title', async () => {
    const { container } = render(
      <MemoryRouter>
        <DashboardPage />
      </MemoryRouter>,
    );
    await waitFor(() => {
      expect(container.textContent).toContain('Token 消耗趋势');
    });
  });

  it('renders agent realtime status card', async () => {
    const { container } = render(
      <MemoryRouter>
        <DashboardPage />
      </MemoryRouter>,
    );
    await waitFor(() => {
      expect(container.textContent).toContain('Agent 实时状态');
    });
  });

  it('renders agent activity trend card', async () => {
    const { container } = render(
      <MemoryRouter>
        <DashboardPage />
      </MemoryRouter>,
    );
    await waitFor(() => {
      expect(container.textContent).toContain('Agent 活动趋势');
    });
  });

  it('shows auto-refresh switch', async () => {
    const { container } = render(
      <MemoryRouter>
        <DashboardPage />
      </MemoryRouter>,
    );
    await waitFor(() => {
      expect(container.textContent).toContain('手动');
    });
  });
});
