/**
 * auditLogService 测试。
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

vi.mock('../services/api', () => ({
  api: {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    delete: vi.fn(),
  },
}));

import { listAuditLogs, getAuditLog } from '../services/auditLogService';
import { api } from '../services/api';

const mockApi = api as unknown as {
  get: ReturnType<typeof vi.fn>;
};

describe('auditLogService', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('listAuditLogs 调用 GET /api/v1/audit-logs', async () => {
    const mockData = { items: [], total: 0 };
    mockApi.get.mockResolvedValue(mockData);

    const result = await listAuditLogs({ limit: 10, offset: 0 });

    expect(mockApi.get).toHaveBeenCalledWith('/api/v1/audit-logs', { limit: 10, offset: 0 });
    expect(result).toEqual(mockData);
  });

  it('listAuditLogs 无参数可调用', async () => {
    mockApi.get.mockResolvedValue({ items: [], total: 0 });

    await listAuditLogs();

    expect(mockApi.get).toHaveBeenCalledWith('/api/v1/audit-logs', undefined);
  });

  it('listAuditLogs 支持过滤参数', async () => {
    mockApi.get.mockResolvedValue({ items: [], total: 0 });

    await listAuditLogs({ action: 'CREATE', resource_type: 'agents' });

    expect(mockApi.get).toHaveBeenCalledWith('/api/v1/audit-logs', { action: 'CREATE', resource_type: 'agents' });
  });

  it('getAuditLog 调用 GET /api/v1/audit-logs/{id}', async () => {
    const mock = { id: 'log-1', action: 'CREATE', resource_type: 'agents' };
    mockApi.get.mockResolvedValue(mock);

    const result = await getAuditLog('log-1');

    expect(mockApi.get).toHaveBeenCalledWith('/api/v1/audit-logs/log-1');
    expect(result).toEqual(mock);
  });
});
