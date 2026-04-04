/**
 * teamService 测试。
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

import { listTeams, getTeam, createTeam, updateTeam, deleteTeam } from '../services/teamService';
import { api } from '../services/api';

const mockApi = api as unknown as {
  get: ReturnType<typeof vi.fn>;
  post: ReturnType<typeof vi.fn>;
  put: ReturnType<typeof vi.fn>;
  delete: ReturnType<typeof vi.fn>;
};

describe('teamService', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('listTeams 调用 GET /api/v1/teams', async () => {
    const mockData = { items: [], total: 0 };
    mockApi.get.mockResolvedValue(mockData);

    const result = await listTeams({ limit: 10, offset: 0 });

    expect(mockApi.get).toHaveBeenCalledWith('/api/v1/teams', { limit: 10, offset: 0 });
    expect(result).toEqual(mockData);
  });

  it('listTeams 无参数可调用', async () => {
    mockApi.get.mockResolvedValue({ items: [], total: 0 });

    await listTeams();

    expect(mockApi.get).toHaveBeenCalledWith('/api/v1/teams', undefined);
  });

  it('listTeams 支持 search 参数', async () => {
    mockApi.get.mockResolvedValue({ items: [], total: 0 });

    await listTeams({ search: 'test' });

    expect(mockApi.get).toHaveBeenCalledWith('/api/v1/teams', { search: 'test' });
  });

  it('getTeam 调用 GET /api/v1/teams/{id}', async () => {
    const mock = { id: 'team-1', name: 'test-team', protocol: 'SEQUENTIAL' };
    mockApi.get.mockResolvedValue(mock);

    const result = await getTeam('team-1');

    expect(mockApi.get).toHaveBeenCalledWith('/api/v1/teams/team-1');
    expect(result).toEqual(mock);
  });

  it('createTeam 调用 POST /api/v1/teams', async () => {
    const input = { name: 'new-team', protocol: 'PARALLEL', member_agent_ids: ['a1', 'a2'] };
    mockApi.post.mockResolvedValue({ id: '1', ...input });

    const result = await createTeam(input);

    expect(mockApi.post).toHaveBeenCalledWith('/api/v1/teams', input);
    expect(result.name).toBe('new-team');
  });

  it('updateTeam 调用 PUT /api/v1/teams/{id}', async () => {
    const update = { description: 'updated', protocol: 'COORDINATOR' };
    mockApi.put.mockResolvedValue({ id: '1', ...update });

    const result = await updateTeam('1', update);

    expect(mockApi.put).toHaveBeenCalledWith('/api/v1/teams/1', update);
    expect(result.description).toBe('updated');
  });

  it('deleteTeam 调用 DELETE /api/v1/teams/{id}', async () => {
    mockApi.delete.mockResolvedValue(undefined);

    await deleteTeam('old-team');

    expect(mockApi.delete).toHaveBeenCalledWith('/api/v1/teams/old-team');
  });
});
