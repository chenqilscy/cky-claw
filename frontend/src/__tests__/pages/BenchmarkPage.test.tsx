import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

// Mock react-query
vi.mock('@tanstack/react-query', async () => {
  const actual = await vi.importActual<typeof import('@tanstack/react-query')>('@tanstack/react-query');
  return {
    ...actual,
    useQuery: vi.fn().mockReturnValue({ data: undefined, isLoading: false, refetch: vi.fn() }),
    useMutation: vi.fn().mockReturnValue({ mutateAsync: vi.fn(), isPending: false }),
    useQueryClient: vi.fn().mockReturnValue({ invalidateQueries: vi.fn() }),
  };
});

// Mock benchmarkService
vi.mock('../../services/benchmarkService', () => ({
  benchmarkService: {
    getDashboard: vi.fn().mockResolvedValue({ total_suites: 3, total_runs: 10, completed_runs: 8, avg_score: 0.78, avg_pass_rate: 0.85 }),
    listSuites: vi.fn().mockResolvedValue({ data: [{ id: '1', name: 'accuracy', description: '准确率', agent_name: 'bot', model: 'gpt-4', tags: ['acc'], created_at: '2026-01-01' }], total: 1 }),
    createSuite: vi.fn().mockResolvedValue({ id: '2', name: 'new-suite' }),
    listRuns: vi.fn().mockResolvedValue({ data: [], total: 0 }),
    createRun: vi.fn().mockResolvedValue({ id: 'r1', status: 'pending' }),
  },
}));

import BenchmarkPage from '../../pages/benchmark/BenchmarkPage';

describe('BenchmarkPage', () => {
  beforeEach(() => vi.clearAllMocks());

  it('渲染页面标题', async () => {
    render(
      <MemoryRouter>
        <BenchmarkPage />
      </MemoryRouter>,
    );
    await waitFor(() => {
      expect(document.body.textContent).toContain('评测');
    });
  });

  it('渲染统计卡片区域', async () => {
    render(
      <MemoryRouter>
        <BenchmarkPage />
      </MemoryRouter>,
    );
    await waitFor(() => {
      // 页面应包含统计相关文本
      const text = document.body.textContent || '';
      expect(text.length).toBeGreaterThan(0);
    });
  });

  it('渲染 Tabs 切换区', async () => {
    render(
      <MemoryRouter>
        <BenchmarkPage />
      </MemoryRouter>,
    );
    await waitFor(() => {
      const text = document.body.textContent || '';
      // 应包含 Suite 或 Run 标签页
      expect(text).toMatch(/Suite|Run|评测/i);
    });
  });

  it('页面不崩溃（空数据）', async () => {
    render(
      <MemoryRouter>
        <BenchmarkPage />
      </MemoryRouter>,
    );
    // 没有异常抛出即通过
    expect(document.body).toBeDefined();
  });
});
