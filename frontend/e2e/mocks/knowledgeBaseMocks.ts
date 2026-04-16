import type { Page, Route } from '@playwright/test';
import {
  MockStore,
  getPath,
  extractPathParams,
  jsonResponse,
  noContentResponse,
  parseBody,
  type MockModule,
} from './index';

/* ---- 类型定义 ---- */

export interface MockKnowledgeBase {
  id: string;
  name: string;
  description: string;
  embedding_model: string;
  chunk_strategy: Record<string, unknown>;
  mode: string;
  metadata: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface MockKnowledgeDocument {
  id: string;
  knowledge_base_id: string;
  filename: string;
  media_type: string;
  size_bytes: number;
  status: string;
  chunk_count: number;
  metadata: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

/* ---- 预设 mock 知识库 ---- */

const presetKnowledgeBases: Omit<MockKnowledgeBase, 'id'>[] = [
  {
    name: 'e2e-mock-kb',
    description: 'E2E 测试知识库',
    embedding_model: 'text-embedding-3-small',
    chunk_strategy: { chunk_size: 512, overlap: 64 },
    mode: 'graph',
    metadata: {},
    created_at: '2025-01-01T00:00:00Z',
    updated_at: '2025-01-01T00:00:00Z',
  },
];

/* ---- 内存存储 ---- */

export const kbStore = new MockStore<MockKnowledgeBase>();
export const kbDocStore = new MockStore<MockKnowledgeDocument>();

/** 初始化预设数据 */
function seedData() {
  for (const item of presetKnowledgeBases) {
    kbStore.create({ ...item });
  }
}

/* ---- URL 前缀 ---- */

const API_PREFIX = '/api/v1/knowledge-bases';

/* ---- Mock 模块 ---- */

export const knowledgeBaseMocks: MockModule = {
  name: 'knowledge-bases',

  reset() {
    kbStore.reset();
    kbDocStore.reset();
    seedData();
  },

  async register(page: Page) {
    this.reset();

    await page.route('**/api/v1/knowledge-bases**', async (route: Route) => {
      const url = route.request().url();
      const path = getPath(url);
      const method = route.request().method();

      // POST /api/v1/knowledge-bases — 创建知识库
      if (method === 'POST' && path === API_PREFIX) {
        const body = (await parseBody(route)) as Omit<MockKnowledgeBase, 'id'>;
        const now = new Date().toISOString();
        const created = kbStore.create({
          ...body,
          chunk_strategy: body.chunk_strategy ?? { chunk_size: 512, overlap: 64 },
          mode: body.mode ?? 'vector',
          metadata: body.metadata ?? {},
          created_at: now,
          updated_at: now,
        });
        await jsonResponse(route, created, 201);
        return;
      }

      // 带 ID 的路由
      const singleMatch = extractPathParams(`${API_PREFIX}/:id`, path);
      if (singleMatch) {
        const { id } = singleMatch;

        // GET /api/v1/knowledge-bases/:id/documents — 文档列表
        const docMatch = extractPathParams(`${API_PREFIX}/:id/documents`, path);
        if (method === 'GET' && docMatch) {
          const docs = kbDocStore.list().filter((d) => d.knowledge_base_id === id);
          await jsonResponse(route, docs);
          return;
        }

        // PUT /api/v1/knowledge-bases/:id — 更新知识库
        if (method === 'PUT') {
          const body = (await parseBody(route)) as Partial<MockKnowledgeBase>;
          const updated = kbStore.update(id, {
            ...body,
            updated_at: new Date().toISOString(),
          });
          if (updated) {
            await jsonResponse(route, updated);
          } else {
            await jsonResponse(route, { detail: '未找到知识库' }, 404);
          }
          return;
        }

        // DELETE /api/v1/knowledge-bases/:id — 删除知识库
        if (method === 'DELETE') {
          const deleted = kbStore.delete(id);
          if (deleted) {
            await noContentResponse(route);
          } else {
            await jsonResponse(route, { detail: '未找到知识库' }, 404);
          }
          return;
        }

        // GET /api/v1/knowledge-bases/:id — 获取详情
        if (method === 'GET') {
          const item = kbStore.get(id);
          if (item) {
            await jsonResponse(route, item);
          } else {
            await jsonResponse(route, { detail: '未找到知识库' }, 404);
          }
          return;
        }
      }

      // GET /api/v1/knowledge-bases — 列表
      if (method === 'GET' && path === API_PREFIX) {
        const all = kbStore.list();
        await jsonResponse(route, { data: all, total: all.length, limit: 20, offset: 0 });
        return;
      }

      // 未匹配的路由继续
      await route.continue();
    });
  },
};
