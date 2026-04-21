/**
 * API 工具函数测试。
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { buildUrl, API_BASE, ApiError } from '../services/api';

describe('buildUrl', () => {
  it('构建基础路径', () => {
    const url = buildUrl('/agents');
    expect(url).toContain(`${API_BASE}/agents`);
  });

  it('附加查询参数', () => {
    const url = buildUrl('/agents', { limit: 10, offset: 0 });
    expect(url).toContain('limit=10');
    expect(url).toContain('offset=0');
  });

  it('忽略 undefined 参数', () => {
    const url = buildUrl('/agents', { limit: 10, name: undefined });
    expect(url).toContain('limit=10');
    expect(url).not.toContain('name');
  });

  it('不附加参数时无查询字符串', () => {
    const url = buildUrl('/agents');
    expect(url).not.toContain('?');
  });
});

describe('ApiError', () => {
  it('包含 status 和 code', () => {
    const err = new ApiError(404, 'NOT_FOUND', '资源不存在');
    expect(err.status).toBe(404);
    expect(err.code).toBe('NOT_FOUND');
    expect(err.message).toBe('资源不存在');
    expect(err.name).toBe('ApiError');
  });

  it('是 Error 实例', () => {
    const err = new ApiError(500, 'INTERNAL', '服务器错误');
    expect(err).toBeInstanceOf(Error);
  });
});

describe('api.get / api.post / api.put / api.delete', () => {
  const originalFetch = globalThis.fetch;

  beforeEach(() => {
    // Mock localStorage
    const storage: Record<string, string> = { kasaya_token: 'test-jwt' };
    vi.stubGlobal('localStorage', {
      getItem: (key: string) => storage[key] ?? null,
      setItem: (key: string, val: string) => { storage[key] = val; },
      removeItem: (key: string) => { Reflect.deleteProperty(storage, key); },
    });
  });

  afterEach(() => {
    globalThis.fetch = originalFetch;
    vi.restoreAllMocks();
  });

  it('GET 请求附带 Authorization header', async () => {
    let capturedHeaders: Record<string, string> = {};
    globalThis.fetch = vi.fn(async (_url: string | URL | Request, init?: RequestInit) => {
      capturedHeaders = Object.fromEntries(
        Object.entries(init?.headers ?? {})
      );
      return new Response(JSON.stringify({ data: [] }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      });
    });

    // 动态导入以重新获取带 mock 的模块
    const { api } = await import('../services/api');
    await api.get('/agents');

    expect(capturedHeaders['Authorization']).toBe('Bearer test-jwt');
  });

  it('POST 请求序列化 body', async () => {
    let capturedBody: string | undefined;
    globalThis.fetch = vi.fn(async (_url: string | URL | Request, init?: RequestInit) => {
      capturedBody = init?.body as string;
      return new Response(JSON.stringify({ id: '1' }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      });
    });

    const { api } = await import('../services/api');
    await api.post('/agents', { name: 'test-agent' });

    expect(capturedBody).toBe(JSON.stringify({ name: 'test-agent' }));
  });

  it('非 2xx 响应抛出 ApiError', async () => {
    globalThis.fetch = vi.fn(async () => {
      return new Response(JSON.stringify({ error: { code: 'NOT_FOUND', message: '找不到' } }), {
        status: 404,
        headers: { 'Content-Type': 'application/json' },
      });
    });

    const { api, ApiError: AE } = await import('../services/api');
    await expect(api.get('/agents/missing')).rejects.toThrow(AE);
  });

  it('204 响应返回 undefined', async () => {
    globalThis.fetch = vi.fn(async () => {
      return new Response(null, { status: 204 });
    });

    const { api } = await import('../services/api');
    const result = await api.delete('/agents/1');
    expect(result).toBeUndefined();
  });
});
