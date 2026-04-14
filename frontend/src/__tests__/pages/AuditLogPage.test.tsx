import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, waitFor } from '@testing-library/react';
import { TestQueryWrapper } from '../test-utils';

// Mock auditLogService
const mockListAuditLogs = vi.fn();
vi.mock('../../services/auditLogService', () => ({
  listAuditLogs: (...args: unknown[]) => mockListAuditLogs(...args),
}));

import AuditLogPage from '../../pages/audit-logs/AuditLogPage';

describe('AuditLogPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockListAuditLogs.mockResolvedValue({
      data: [
        {
          id: 'log-1',
          user_id: 'user-1',
          username: 'admin',
          action: 'CREATE',
          resource_type: 'agent',
          resource_id: 'agent-1',
          details: { name: 'test-agent' },
          created_at: '2026-01-01T00:00:00Z',
        },
      ],
      total: 1,
    });
  });

  it('renders page title', async () => {
    render(
      <TestQueryWrapper>
          <AuditLogPage />
      </TestQueryWrapper>,
    );
    await waitFor(() => {
      expect(document.body.textContent).toContain('审计日志');
    });
  });

  it('renders audit log data in table', async () => {
    render(
      <TestQueryWrapper>
          <AuditLogPage />
      </TestQueryWrapper>,
    );
    await waitFor(() => {
      expect(mockListAuditLogs).toHaveBeenCalled();
    });
    // Data should eventually render
    await waitFor(() => {
      const text = document.body.textContent ?? '';
      expect(text).toContain('CREATE');
    });
  });

  it('renders table columns', async () => {
    render(
      <TestQueryWrapper>
          <AuditLogPage />
      </TestQueryWrapper>,
    );
    await waitFor(() => {
      expect(document.body.textContent).toContain('审计日志');
    });
    // Table headers should be present
    expect(document.body.textContent).toContain('操作');
    expect(document.body.textContent).toContain('资源类型');
  });

  it('calls listAuditLogs on mount', async () => {
    render(
      <TestQueryWrapper>
          <AuditLogPage />
      </TestQueryWrapper>,
    );
    await waitFor(() => {
      expect(mockListAuditLogs).toHaveBeenCalled();
    });
  });
});
