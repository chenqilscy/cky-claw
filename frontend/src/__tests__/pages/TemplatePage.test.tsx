import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

// Mock agentTemplateService — use inline vi.fn() to avoid hoisting
vi.mock('../../services/agentTemplateService', () => ({
  agentTemplateService: {
    list: vi.fn(),
    seedBuiltin: vi.fn(),
    createFromTemplate: vi.fn(),
  },
}));

// Mock navigate
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom');
  return { ...actual, useNavigate: () => vi.fn() };
});

// Mock message
vi.mock('antd', async () => {
  const actual = await vi.importActual<typeof import('antd')>('antd');
  return { ...actual, message: { success: vi.fn(), error: vi.fn() } };
});

import TemplatePage from '../../pages/templates/TemplatePage';
import { agentTemplateService } from '../../services/agentTemplateService';

describe('TemplatePage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(agentTemplateService.list).mockResolvedValue({
      data: [
        {
          id: 'tpl-1',
          name: 'code-reviewer',
          display_name: '代码审查助手',
          description: '自动审查代码并给出建议',
          category: 'development',
          icon: 'CodeOutlined',
          is_builtin: true,
          template_config: {},
          created_at: '2026-01-01T00:00:00Z',
        },
      ],
      total: 1,
    } as never);
  });

  it('renders page title', async () => {
    render(
      <MemoryRouter>
        <TemplatePage />
      </MemoryRouter>,
    );
    await waitFor(() => {
      expect(document.body.textContent).toContain('模板');
    });
  });

  it('loads and displays template card', async () => {
    render(
      <MemoryRouter>
        <TemplatePage />
      </MemoryRouter>,
    );
    await waitFor(() => {
      expect(document.body.textContent).toContain('代码审查助手');
    });
  });

  it('shows template description', async () => {
    render(
      <MemoryRouter>
        <TemplatePage />
      </MemoryRouter>,
    );
    await waitFor(() => {
      expect(document.body.textContent).toContain('自动审查代码');
    });
  });

  it('shows category tag', async () => {
    render(
      <MemoryRouter>
        <TemplatePage />
      </MemoryRouter>,
    );
    await waitFor(() => {
      expect(document.body.textContent).toContain('开发辅助');
    });
  });

  it('calls list API on mount', async () => {
    render(
      <MemoryRouter>
        <TemplatePage />
      </MemoryRouter>,
    );
    await waitFor(() => {
      expect(vi.mocked(agentTemplateService.list)).toHaveBeenCalled();
    });
  });

  it('shows empty state when no templates', async () => {
    vi.mocked(agentTemplateService.list).mockResolvedValue({ data: [], total: 0 } as never);
    render(
      <MemoryRouter>
        <TemplatePage />
      </MemoryRouter>,
    );
    await waitFor(() => {
      // Ant Design Empty component or custom empty text
      expect(document.body.textContent).toContain('暂无');
    });
  });
});
