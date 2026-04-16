import type { Page, Route } from '@playwright/test';

/**
 * Mock 基础设施 — 统一的 API 拦截注册和内存数据存储。
 */

/* ---- 内存数据存储 ---- */

/** 带自增 ID 的内存 CRUD 存储 */
export class MockStore<T extends Record<string, unknown>> {
  private data: Map<string, T> = new Map();
  private nextId = 1;

  /** 重置存储 */
  reset() {
    this.data.clear();
    this.nextId = 1;
  }

  /** 生成新 ID */
  genId(): string {
    return `mock-${this.nextId++}`;
  }

  /** 新增 */
  create(item: T): T & { id: string } {
    const id = this.genId();
    const record = { ...item, id } as T & { id: string };
    this.data.set(id, record);
    return record;
  }

  /** 按 ID 获取 */
  get(id: string): (T & { id: string }) | undefined {
    return this.data.get(id) as (T & { id: string }) | undefined;
  }

  /** 列表 */
  list(): (T & { id: string })[] {
    return Array.from(this.data.values()) as (T & { id: string })[];
  }

  /** 更新 */
  update(id: string, partial: Partial<T>): (T & { id: string }) | undefined {
    const existing = this.data.get(id);
    if (!existing) return undefined;
    const updated = { ...existing, ...partial, id } as T & { id: string };
    this.data.set(id, updated);
    return updated;
  }

  /** 删除 */
  delete(id: string): boolean {
    return this.data.delete(id);
  }

  /** 按字段查找 */
  findBy(field: string, value: unknown): (T & { id: string }) | undefined {
    return this.list().find((item) => item[field] === value);
  }
}

/* ---- URL 匹配工具 ---- */

/** 从请求 URL 提取路径（去除 origin） */
export function getPath(url: string): string {
  const u = new URL(url);
  return u.pathname;
}

/** 从 URL 提取路径参数 */
export function extractPathParams(pattern: string, path: string): Record<string, string> | null {
  const patternParts = pattern.split('/');
  const pathParts = path.split('/');
  if (patternParts.length !== pathParts.length) return null;
  const params: Record<string, string> = {};
  for (let i = 0; i < patternParts.length; i++) {
    if (patternParts[i].startsWith(':')) {
      params[patternParts[i].slice(1)] = pathParts[i];
    } else if (patternParts[i] !== pathParts[i]) {
      return null;
    }
  }
  return params;
}

/* ---- Mock 注册器 ---- */

export type MockHandler = (route: Route, path: string, method: string, body: unknown) => Promise<void>;

export interface MockModule {
  /** 模块名 */
  name: string;
  /** 重置内存数据 */
  reset(): void;
  /** 注册 API 拦截规则 */
  register(page: Page): Promise<void>;
}

/** 注册所有指定模块的 mock */
export async function registerMocks(page: Page, modules: MockModule[]) {
  for (const mod of modules) {
    mod.reset();
    await mod.register(page);
  }
}

/* ---- 通用 JSON 响应辅助 ---- */

export async function jsonResponse(route: Route, data: unknown, status = 200) {
  await route.fulfill({
    status,
    contentType: 'application/json',
    body: JSON.stringify(data),
  });
}

export async function noContentResponse(route: Route) {
  await route.fulfill({ status: 204, body: '' });
}

/** 解析请求 body */
export async function parseBody(route: Route): Promise<unknown> {
  const body = route.request().postData();
  if (!body) return {};
  try {
    return JSON.parse(body);
  } catch {
    return {};
  }
}
