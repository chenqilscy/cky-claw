/**
 * imChannelService 测试。
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

import {
  listIMChannels,
  getIMChannel,
  createIMChannel,
  updateIMChannel,
  deleteIMChannel,
} from '../services/imChannelService';
import { api } from '../services/api';

const mockApi = api as unknown as {
  get: ReturnType<typeof vi.fn>;
  post: ReturnType<typeof vi.fn>;
  put: ReturnType<typeof vi.fn>;
  delete: ReturnType<typeof vi.fn>;
};

describe('imChannelService', () => {
  beforeEach(() => { vi.clearAllMocks(); });
  afterEach(() => { vi.restoreAllMocks(); });

  it('listIMChannels 调用 GET /api/v1/im-channels', async () => {
    const data = { data: [], total: 0 };
    mockApi.get.mockResolvedValue(data);
    const result = await listIMChannels({ channel_type: 'wecom' });
    expect(mockApi.get).toHaveBeenCalledWith('/api/v1/im-channels', { channel_type: 'wecom' });
    expect(result).toEqual(data);
  });

  it('getIMChannel 调用 GET /api/v1/im-channels/:id', async () => {
    mockApi.get.mockResolvedValue({ id: 'c1', name: 'test' });
    const result = await getIMChannel('c1');
    expect(mockApi.get).toHaveBeenCalledWith('/api/v1/im-channels/c1');
    expect(result).toEqual({ id: 'c1', name: 'test' });
  });

  it('createIMChannel 调用 POST /api/v1/im-channels', async () => {
    const input = { name: 'wecom-bot', channel_type: 'wecom' };
    mockApi.post.mockResolvedValue({ id: '1', ...input });
    const result = await createIMChannel(input);
    expect(mockApi.post).toHaveBeenCalledWith('/api/v1/im-channels', input);
    expect(result).toEqual({ id: '1', ...input });
  });

  it('updateIMChannel 调用 PUT /api/v1/im-channels/:id', async () => {
    const update = { description: 'updated' };
    mockApi.put.mockResolvedValue({ id: '1', ...update });
    await updateIMChannel('1', update);
    expect(mockApi.put).toHaveBeenCalledWith('/api/v1/im-channels/1', update);
  });

  it('deleteIMChannel 调用 DELETE /api/v1/im-channels/:id', async () => {
    mockApi.delete.mockResolvedValue(undefined);
    await deleteIMChannel('c1');
    expect(mockApi.delete).toHaveBeenCalledWith('/api/v1/im-channels/c1');
  });
});
