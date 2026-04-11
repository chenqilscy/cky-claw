/**
 * eventService 测试。
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

import { eventService } from '../services/eventService';
import { api } from '../services/api';

const mockApi = api as unknown as {
  get: ReturnType<typeof vi.fn>;
};

describe('eventService', () => {
  beforeEach(() => { vi.clearAllMocks(); });
  afterEach(() => { vi.restoreAllMocks(); });

  it('replay 调用 GET /events/replay/{runId}', async () => {
    const data = { items: [], total: 0 };
    mockApi.get.mockResolvedValue(data);
    const result = await eventService.replay('run-001');
    expect(mockApi.get).toHaveBeenCalledWith('/events/replay/run-001', undefined);
    expect(result).toEqual(data);
  });

  it('replay 带过滤参数', async () => {
    const data = { items: [], total: 0 };
    mockApi.get.mockResolvedValue(data);
    await eventService.replay('run-002', { event_type: 'llm_call_end', limit: 50 });
    expect(mockApi.get).toHaveBeenCalledWith('/events/replay/run-002', {
      event_type: 'llm_call_end',
      limit: 50,
    });
  });

  it('sessionEvents 调用 GET /events/sessions/{sessionId}', async () => {
    const data = { items: [{ event_id: 'e1', sequence: 1 }], total: 1 };
    mockApi.get.mockResolvedValue(data);
    const result = await eventService.sessionEvents('sess-001');
    expect(mockApi.get).toHaveBeenCalledWith('/events/sessions/sess-001', undefined);
    expect(result).toEqual(data);
  });

  it('stats 调用 GET /events/stats', async () => {
    const stats = { total_events: 10, event_type_counts: {}, run_count: 2 };
    mockApi.get.mockResolvedValue(stats);
    const result = await eventService.stats({ run_id: 'r1' });
    expect(mockApi.get).toHaveBeenCalledWith('/events/stats', { run_id: 'r1' });
    expect(result).toEqual(stats);
  });

  it('stats 无参调用', async () => {
    const stats = { total_events: 0, event_type_counts: {}, run_count: 0 };
    mockApi.get.mockResolvedValue(stats);
    await eventService.stats();
    expect(mockApi.get).toHaveBeenCalledWith('/events/stats', undefined);
  });
});
