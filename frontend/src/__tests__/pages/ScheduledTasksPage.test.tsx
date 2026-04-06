import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

// Mock ProTable to avoid heavy @ant-design/pro-components rendering
vi.mock('@ant-design/pro-components', () => ({
  ProTable: ({ headerTitle, dataSource }: { headerTitle: string; dataSource: unknown[] }) => (
    <div data-testid="pro-table">
      <div>{headerTitle}</div>
      <div data-testid="row-count">{Array.isArray(dataSource) ? dataSource.length : 0}</div>
      {Array.isArray(dataSource) && (dataSource as Record<string, unknown>[]).map((item, i: number) => (
        <div key={i} data-testid="row">{(item as { name?: string }).name}</div>
      ))}
    </div>
  ),
}));

// Mock scheduledTaskService
vi.mock('../../services/scheduledTaskService', () => ({
  scheduledTaskService: {
    list: vi.fn(),
    create: vi.fn(),
    update: vi.fn(),
    delete: vi.fn(),
    toggle: vi.fn(),
  },
}));

import ScheduledTasksPage from '../../pages/scheduled-tasks/ScheduledTasksPage';
import { scheduledTaskService } from '../../services/scheduledTaskService';

describe('ScheduledTasksPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(scheduledTaskService.list).mockResolvedValue({
      data: [
        {
          id: 'task-1',
          name: '每日报告',
          description: '每天生成总结报告',
          agent_id: 'agent-1',
          cron_expr: '0 9 * * *',
          input_text: '生成日报',
          is_enabled: true,
          last_run_at: null,
          next_run_at: '2026-01-02T09:00:00Z',
          created_at: '2026-01-01T00:00:00Z',
          updated_at: '2026-01-01T00:00:00Z',
        },
      ],
      total: 1,
    } as never);
  });

  it('renders page title', async () => {
    render(
      <MemoryRouter>
        <ScheduledTasksPage />
      </MemoryRouter>,
    );
    await waitFor(() => {
      expect(document.body.textContent).toContain('定时任务');
    });
  });

  it('calls scheduledTaskService.list on mount', async () => {
    render(
      <MemoryRouter>
        <ScheduledTasksPage />
      </MemoryRouter>,
    );
    await waitFor(() => {
      expect(vi.mocked(scheduledTaskService.list)).toHaveBeenCalled();
    });
  });

  it('renders task data', async () => {
    render(
      <MemoryRouter>
        <ScheduledTasksPage />
      </MemoryRouter>,
    );
    await waitFor(() => {
      expect(document.body.textContent).toContain('每日报告');
    });
  });

  it('renders create button', async () => {
    render(
      <MemoryRouter>
        <ScheduledTasksPage />
      </MemoryRouter>,
    );
    await waitFor(() => {
      expect(document.body.textContent).toContain('新建任务');
    });
  });
});
