import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, waitFor } from '@testing-library/react';
import { TestQueryWrapper } from '../test-utils';
import { MemoryRouter } from 'react-router-dom';

// Mock teamService — named exports
const mockListTeams = vi.fn();
vi.mock('../../services/teamService', () => ({
  listTeams: (...args: unknown[]) => mockListTeams(...args),
  createTeam: vi.fn(),
  updateTeam: vi.fn(),
  deleteTeam: vi.fn(),
}));

import TeamPage from '../../pages/teams/TeamPage';

describe('TeamPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockListTeams.mockResolvedValue({
      data: [
        {
          id: 'team-1',
          name: '客服团队',
          description: '客服场景团队',
          protocol: 'SEQUENTIAL',
          member_agent_ids: ['agent-1', 'agent-2'],
          coordinator_agent_id: null,
          config: {},
          created_at: '2026-01-01T00:00:00Z',
          updated_at: '2026-01-01T00:00:00Z',
        },
      ],
      total: 1,
    });
  });

  it('renders page title', async () => {
    render(
      <TestQueryWrapper>
        <MemoryRouter>
          <TeamPage />
        </MemoryRouter>
      </TestQueryWrapper>,
    );
    await waitFor(() => {
      expect(document.body.textContent).toContain('团队');
    });
  });

  it('calls listTeams on mount', async () => {
    render(
      <TestQueryWrapper>
        <MemoryRouter>
          <TeamPage />
        </MemoryRouter>
      </TestQueryWrapper>,
    );
    await waitFor(() => {
      expect(mockListTeams).toHaveBeenCalled();
    });
  });

  it('renders team data', async () => {
    render(
      <TestQueryWrapper>
        <MemoryRouter>
          <TeamPage />
        </MemoryRouter>
      </TestQueryWrapper>,
    );
    await waitFor(() => {
      expect(document.body.textContent).toContain('客服团队');
    });
  });

  it('renders protocol tag', async () => {
    render(
      <TestQueryWrapper>
        <MemoryRouter>
          <TeamPage />
        </MemoryRouter>
      </TestQueryWrapper>,
    );
    await waitFor(() => {
      expect(document.body.textContent).toContain('顺序执行');
    });
  });
});
