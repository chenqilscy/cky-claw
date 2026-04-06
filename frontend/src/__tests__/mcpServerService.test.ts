/**
 * mcpServerService 测试。
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

import { mcpServerService } from '../services/mcpServerService';
import type { MCPServerListParams } from '../services/mcpServerService';
import { api } from '../services/api';

const mockApi = api as unknown as {
  get: ReturnType<typeof vi.fn>;
  post: ReturnType<typeof vi.fn>;
  put: ReturnType<typeof vi.fn>;
  delete: ReturnType<typeof vi.fn>;
};

describe('mcpServerService', () => {
  beforeEach(() => { vi.clearAllMocks(); });
  afterEach(() => { vi.restoreAllMocks(); });

  it('list 调用 GET /mcp/servers', async () => {
    const data = { data: [], total: 0 };
    mockApi.get.mockResolvedValue(data);
    const result = await mcpServerService.list();
    expect(mockApi.get).toHaveBeenCalledWith('/mcp/servers', {});
    expect(result).toEqual(data);
  });

  it('list 过滤空值和空字符串，布尔转字符串', async () => {
    mockApi.get.mockResolvedValue({ data: [], total: 0 });
    await mcpServerService.list({ transport_type: 'stdio', is_enabled: true } as MCPServerListParams & { is_enabled: boolean });
    expect(mockApi.get).toHaveBeenCalledWith('/mcp/servers', { transport_type: 'stdio', is_enabled: 'true' });
  });

  it('get 调用 GET /mcp/servers/:id', async () => {
    mockApi.get.mockResolvedValue({ id: 'm1' });
    const result = await mcpServerService.get('m1');
    expect(mockApi.get).toHaveBeenCalledWith('/mcp/servers/m1');
    expect(result).toEqual({ id: 'm1' });
  });

  it('create 调用 POST /mcp/servers', async () => {
    const input = { name: 'new-mcp', transport_type: 'stdio' as const, config: {} };
    mockApi.post.mockResolvedValue({ id: '1', ...input });
    const result = await mcpServerService.create(input);
    expect(mockApi.post).toHaveBeenCalledWith('/mcp/servers', input);
    expect(result).toEqual({ id: '1', ...input });
  });

  it('update 调用 PUT /mcp/servers/:id', async () => {
    const update = { description: 'updated-mcp' };
    mockApi.put.mockResolvedValue({ id: '1', ...update });
    await mcpServerService.update('1', update);
    expect(mockApi.put).toHaveBeenCalledWith('/mcp/servers/1', update);
  });

  it('delete 调用 DELETE /mcp/servers/:id', async () => {
    mockApi.delete.mockResolvedValue(undefined);
    await mcpServerService.delete('m1');
    expect(mockApi.delete).toHaveBeenCalledWith('/mcp/servers/m1');
  });

  it('testConnection 调用 POST /mcp/servers/:id/test', async () => {
    const result = { success: true, tools: [] };
    mockApi.post.mockResolvedValue(result);
    const resp = await mcpServerService.testConnection('m1');
    expect(mockApi.post).toHaveBeenCalledWith('/mcp/servers/m1/test');
    expect(resp).toEqual(result);
  });
});
