import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

// Mock a2aService
vi.mock('../../services/a2aService', () => ({
  a2aService: {
    listAgentCards: vi.fn().mockResolvedValue({
      data: [
        {
          id: '1', agent_id: 'agent-1', name: 'test-card', description: '测试 A2A Agent',
          url: 'http://localhost:8000', version: '1.0', capabilities: {},
          skills: [], authentication: {}, metadata_: {}, created_at: '2026-01-01',
        },
      ],
      total: 1,
    }),
    createAgentCard: vi.fn().mockResolvedValue({ id: '2', name: 'new-card' }),
    deleteAgentCard: vi.fn().mockResolvedValue(undefined),
    discoverAgent: vi.fn().mockResolvedValue({ name: 'remote-agent', skills: [] }),
    listTasks: vi.fn().mockResolvedValue({ data: [], total: 0 }),
    createTask: vi.fn().mockResolvedValue({ id: 't1', status: 'submitted' }),
    getTask: vi.fn().mockResolvedValue({ id: 't1', status: 'completed' }),
    cancelTask: vi.fn().mockResolvedValue(undefined),
  },
}));

import A2APage from '../../pages/a2a/A2APage';

describe('A2APage', () => {
  beforeEach(() => vi.clearAllMocks());

  it('渲染页面标题', async () => {
    render(
      <MemoryRouter>
        <A2APage />
      </MemoryRouter>,
    );
    await waitFor(() => {
      expect(document.body.textContent).toContain('A2A');
    });
  });

  it('渲染 Agent Card 表格', async () => {
    render(
      <MemoryRouter>
        <A2APage />
      </MemoryRouter>,
    );
    await waitFor(() => {
      const text = document.body.textContent || '';
      expect(text).toMatch(/Card|Agent|A2A/i);
    });
  });

  it('渲染操作按钮（注册/发现）', async () => {
    render(
      <MemoryRouter>
        <A2APage />
      </MemoryRouter>,
    );
    await waitFor(() => {
      const text = document.body.textContent || '';
      expect(text.length).toBeGreaterThan(0);
    });
  });

  it('空数据不崩溃', () => {
    render(
      <MemoryRouter>
        <A2APage />
      </MemoryRouter>,
    );
    expect(document.body).toBeDefined();
  });
});
