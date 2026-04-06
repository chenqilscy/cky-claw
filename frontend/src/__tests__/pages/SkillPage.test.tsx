import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

// Mock ProTable to avoid heavy @ant-design/pro-components rendering
vi.mock('@ant-design/pro-components', () => ({
  ProTable: (props: Record<string, unknown>) => {
    const { headerTitle, toolBarRender, request, dataSource } = props as {
      headerTitle?: string;
      toolBarRender?: (() => React.ReactNode[]) | false;
      request?: (params: Record<string, unknown>) => Promise<{ data: unknown[] }>;
      dataSource?: unknown[];
    };
    // Call request on render to trigger data fetch
    if (request) {
      void request({ current: 1, pageSize: 20 }).then(() => {});
    }
    const items = Array.isArray(dataSource) ? dataSource : [];
    return (
      <div data-testid="pro-table">
        <div>{headerTitle}</div>
        {typeof toolBarRender === 'function' && <div data-testid="toolbar">{toolBarRender()}</div>}
        <div data-testid="row-count">{items.length}</div>
        {items.map((item: Record<string, unknown>, i: number) => (
          <div key={i} data-testid="row">{(item as { name?: string }).name}</div>
        ))}
      </div>
    );
  },
}));

// Mock skillService
vi.mock('../../services/skillService', () => ({
  skillService: {
    list: vi.fn(),
    create: vi.fn(),
    update: vi.fn(),
    delete: vi.fn(),
    search: vi.fn(),
  },
}));

import SkillPage from '../../pages/skills/SkillPage';
import { skillService } from '../../services/skillService';

describe('SkillPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(skillService.list).mockResolvedValue({
      data: [
        {
          id: 'skill-1',
          name: '代码审查',
          version: '1.0',
          description: '自动代码审查技能',
          content: 'review code',
          category: 'public',
          tags: ['code', 'review'],
          applicable_agents: [],
          author: 'cky',
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
        <SkillPage />
      </MemoryRouter>,
    );
    await waitFor(() => {
      expect(document.body.textContent).toContain('技能');
    });
  });

  it('calls skillService.list via ProTable request', async () => {
    render(
      <MemoryRouter>
        <SkillPage />
      </MemoryRouter>,
    );
    await waitFor(() => {
      expect(vi.mocked(skillService.list)).toHaveBeenCalled();
    });
  });

  it('renders create button', async () => {
    render(
      <MemoryRouter>
        <SkillPage />
      </MemoryRouter>,
    );
    await waitFor(() => {
      expect(document.body.textContent).toContain('新建技能');
    });
  });

  it('renders search button', async () => {
    render(
      <MemoryRouter>
        <SkillPage />
      </MemoryRouter>,
    );
    await waitFor(() => {
      expect(document.body.textContent).toContain('搜索技能');
    });
  });
});
