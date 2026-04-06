import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

vi.mock('../../services/evolutionService', () => ({
  evolutionService: {
    list: vi.fn().mockResolvedValue({
      data: [
        {
          id: '1',
          agent_name: 'test-bot',
          proposal_type: 'instructions',
          status: 'pending',
          trigger_reason: '评分 0.5 低于阈值',
          current_value: null,
          proposed_value: null,
          confidence_score: 0.8,
          eval_before: null,
          eval_after: null,
          applied_at: null,
          rolled_back_at: null,
          metadata: {},
          created_at: '2026-07-03T00:00:00Z',
          updated_at: '2026-07-03T00:00:00Z',
        },
      ],
      total: 1,
      limit: 20,
      offset: 0,
    }),
    create: vi.fn(),
    update: vi.fn(),
    delete: vi.fn(),
    get: vi.fn(),
  },
}));

import EvolutionPage from '../../pages/evolution/EvolutionPage';

describe('EvolutionPage', () => {
  beforeEach(() => vi.clearAllMocks());

  it('renders page title', () => {
    render(
      <MemoryRouter>
        <EvolutionPage />
      </MemoryRouter>,
    );
    // Card title 通过 Ant Design 内部渲染，用 container 查找
    expect(document.body.textContent).toContain('进化建议');
  });

  it('shows proposal in table after loading', async () => {
    render(
      <MemoryRouter>
        <EvolutionPage />
      </MemoryRouter>,
    );
    await waitFor(() => {
      expect(screen.getByText('test-bot')).toBeDefined();
    });
  });

  it('shows proposal type tag', async () => {
    render(
      <MemoryRouter>
        <EvolutionPage />
      </MemoryRouter>,
    );
    await waitFor(() => {
      expect(screen.getByText('指令优化')).toBeDefined();
    });
  });

  it('shows status tag', async () => {
    render(
      <MemoryRouter>
        <EvolutionPage />
      </MemoryRouter>,
    );
    await waitFor(() => {
      expect(screen.getByText('待审批')).toBeDefined();
    });
  });

  it('renders filter inputs', () => {
    render(
      <MemoryRouter>
        <EvolutionPage />
      </MemoryRouter>,
    );
    expect(screen.getByPlaceholderText('Agent 名称')).toBeDefined();
  });

  it('renders create button', () => {
    render(
      <MemoryRouter>
        <EvolutionPage />
      </MemoryRouter>,
    );
    expect(screen.getByRole('button', { name: /新建建议/ })).toBeDefined();
  });

  it('renders refresh button', () => {
    render(
      <MemoryRouter>
        <EvolutionPage />
      </MemoryRouter>,
    );
    expect(screen.getByRole('button', { name: /刷新/ })).toBeDefined();
  });
});
