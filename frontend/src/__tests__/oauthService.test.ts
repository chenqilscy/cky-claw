/**
 * oauthService 测试。
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

import { oauthService } from '../services/oauthService';
import { api } from '../services/api';

const mockApi = api as unknown as {
  get: ReturnType<typeof vi.fn>;
  post: ReturnType<typeof vi.fn>;
  delete: ReturnType<typeof vi.fn>;
};

describe('oauthService', () => {
  beforeEach(() => { vi.clearAllMocks(); });
  afterEach(() => { vi.restoreAllMocks(); });

  it('getProviders 调用 GET /auth/oauth/providers', async () => {
    const data = { providers: ['github', 'google'] };
    mockApi.get.mockResolvedValue(data);
    const result = await oauthService.getProviders();
    expect(mockApi.get).toHaveBeenCalledWith('/auth/oauth/providers');
    expect(result).toEqual(data);
  });

  it('authorize 调用 GET /auth/oauth/:provider/authorize', async () => {
    const data = { authorize_url: 'https://example.com', state: 'abc' };
    mockApi.get.mockResolvedValue(data);
    const result = await oauthService.authorize('github');
    expect(mockApi.get).toHaveBeenCalledWith('/auth/oauth/github/authorize');
    expect(result).toEqual(data);
  });

  it('callback 调用 GET /auth/oauth/:provider/callback', async () => {
    const token = { access_token: 'jwt', token_type: 'bearer', expires_in: 3600 };
    mockApi.get.mockResolvedValue(token);
    const result = await oauthService.callback('github', 'code123', 'state456');
    expect(mockApi.get).toHaveBeenCalledWith('/auth/oauth/github/callback', { code: 'code123', state: 'state456' });
    expect(result).toEqual(token);
  });

  it('bind 调用 POST /auth/oauth/:provider/bind', async () => {
    const conn = { id: '1', provider: 'github' };
    mockApi.post.mockResolvedValue(conn);
    const result = await oauthService.bind('github', 'code123', 'state456');
    expect(mockApi.post).toHaveBeenCalledWith('/auth/oauth/github/bind', { code: 'code123', state: 'state456' });
    expect(result).toEqual(conn);
  });

  it('getConnections 调用 GET /auth/oauth/connections', async () => {
    const conns = [{ id: '1', provider: 'github' }];
    mockApi.get.mockResolvedValue(conns);
    const result = await oauthService.getConnections();
    expect(mockApi.get).toHaveBeenCalledWith('/auth/oauth/connections');
    expect(result).toEqual(conns);
  });

  it('unbind 调用 DELETE /auth/oauth/:provider/unbind', async () => {
    mockApi.delete.mockResolvedValue(undefined);
    await oauthService.unbind('github');
    expect(mockApi.delete).toHaveBeenCalledWith('/auth/oauth/github/unbind');
  });
});
