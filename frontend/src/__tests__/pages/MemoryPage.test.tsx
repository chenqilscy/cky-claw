import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, waitFor } from '@testing-library/react';
import { TestQueryWrapper } from '../test-utils';

// Mock echarts
vi.mock('echarts-for-react', () => ({
  default: () => <div data-testid="mock-echart" />,
}));

// Mock ProTable to avoid heavy @ant-design/pro-components rendering
vi.mock('@ant-design/pro-components', () => ({
  ProTable: ({ headerTitle, dataSource }: { headerTitle: string; dataSource: unknown[] }) => (
    <div data-testid="pro-table">
      <div>{headerTitle}</div>
      <div data-testid="row-count">{Array.isArray(dataSource) ? dataSource.length : 0}</div>
      {Array.isArray(dataSource) && (dataSource as Record<string, unknown>[]).map((item, i: number) => (
        <div key={i} data-testid="row">{(item as { content?: string }).content}</div>
      ))}
    </div>
  ),
}));

// Mock memoryService
vi.mock('../../services/memoryService', () => ({
  memoryService: {
    list: vi.fn(),
    create: vi.fn(),
    update: vi.fn(),
    delete: vi.fn(),
    search: vi.fn(),
  },
}));

import MemoryPage from '../../pages/memories/MemoryPage';
import { memoryService } from '../../services/memoryService';

describe('MemoryPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(memoryService.list).mockResolvedValue({
      data: [
        {
          id: 'mem-1',
          user_id: 'user-1',
          agent_name: 'test-agent',
          type: 'structured_fact',
          content: '用户偏好设置',
          metadata: {},
          confidence: 0.95,
          created_at: '2026-01-01T00:00:00Z',
          updated_at: '2026-01-01T00:00:00Z',
        },
      ],
      total: 1,
    } as never);
  });

  it('renders page title', async () => {
    render(
      <TestQueryWrapper>
          <MemoryPage />
      </TestQueryWrapper>,
    );
    await waitFor(() => {
      expect(document.body.textContent).toContain('记忆');
    });
  });

  it('calls memoryService.list on mount', async () => {
    render(
      <TestQueryWrapper>
          <MemoryPage />
      </TestQueryWrapper>,
    );
    await waitFor(() => {
      expect(vi.mocked(memoryService.list)).toHaveBeenCalled();
    });
  });

  it('renders memory data', async () => {
    render(
      <TestQueryWrapper>
          <MemoryPage />
      </TestQueryWrapper>,
    );
    await waitFor(() => {
      expect(document.body.textContent).toContain('用户偏好设置');
    });
  });

  it('renders view toggle and search buttons', async () => {
    render(
      <TestQueryWrapper>
          <MemoryPage />
      </TestQueryWrapper>,
    );
    await waitFor(() => {
      const text = document.body.textContent ?? '';
      expect(text).toContain('表格');
      expect(text).toContain('时间线');
    });
  });

  it('renders statistics overview', async () => {
    render(
      <TestQueryWrapper>
          <MemoryPage />
      </TestQueryWrapper>,
    );
    await waitFor(() => {
      const text = document.body.textContent ?? '';
      expect(text).toContain('记忆总数');
      expect(text).toContain('平均置信度');
    });
  });
});
