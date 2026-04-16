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

export interface MockSkill {
  id: string;
  name: string;
  version: string;
  description: string;
  content: string;
  category: string;
  tags: string[];
  applicable_agents: string[];
  author: string;
  metadata: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

/* ---- 预设 mock 技能 ---- */

const presetSkills: Omit<MockSkill, 'id'>[] = [
  {
    name: 'e2e-mock-skill-hello',
    version: '1.0.0',
    description: 'E2E 测试技能',
    category: 'general',
    content: '# 你好技能\n\n这是一个测试技能。',
    tags: ['test', 'e2e'],
    applicable_agents: [],
    author: 'e2e-tester',
    metadata: {},
    created_at: '2025-01-01T00:00:00Z',
    updated_at: '2025-01-01T00:00:00Z',
  },
  {
    name: 'e2e-mock-skill-world',
    version: '2.0.0',
    description: '另一个 E2E 测试技能',
    category: 'custom',
    content: '# 世界技能\n\n另一个测试技能的内容。',
    tags: ['demo'],
    applicable_agents: [],
    author: 'e2e-tester',
    metadata: {},
    created_at: '2025-01-02T00:00:00Z',
    updated_at: '2025-01-02T00:00:00Z',
  },
];

/* ---- 内存存储 ---- */

export const skillStore = new MockStore<MockSkill>();

/** 初始化预设数据 */
function seedData() {
  for (const item of presetSkills) {
    skillStore.create({ ...item });
  }
}

/* ---- URL 前缀 ---- */

const API_PREFIX = '/api/v1/skills';

/* ---- Mock 模块 ---- */

export const skillMocks: MockModule = {
  name: 'skills',

  reset() {
    skillStore.reset();
    seedData();
  },

  async register(page: Page) {
    this.reset();

    await page.route('**/api/v1/skills**', async (route: Route) => {
      const url = route.request().url();
      const path = getPath(url);
      const method = route.request().method();

      // POST /api/v1/skills/search — 搜索技能
      if (method === 'POST' && path === `${API_PREFIX}/search`) {
        const body = (await parseBody(route)) as { query?: string; category?: string };
        const query = (body.query ?? '').toLowerCase();
        const all = skillStore.list();
        const results = all.filter((s) => {
          const nameMatch = s.name.toLowerCase().includes(query);
          const descMatch = s.description.toLowerCase().includes(query);
          const contentMatch = s.content.toLowerCase().includes(query);
          const categoryMatch = body.category ? s.category === body.category : true;
          return (nameMatch || descMatch || contentMatch) && categoryMatch;
        });
        await jsonResponse(route, results);
        return;
      }

      // POST /api/v1/skills — 创建技能
      if (method === 'POST' && path === API_PREFIX) {
        const body = (await parseBody(route)) as Omit<MockSkill, 'id'>;
        const now = new Date().toISOString();
        const created = skillStore.create({
          ...body,
          tags: body.tags ?? [],
          applicable_agents: body.applicable_agents ?? [],
          author: body.author ?? '',
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

        // GET /api/v1/skills/:id — 获取详情
        if (method === 'GET') {
          const item = skillStore.get(id);
          if (item) {
            await jsonResponse(route, item);
          } else {
            await jsonResponse(route, { detail: '未找到技能' }, 404);
          }
          return;
        }

        // PUT /api/v1/skills/:id — 更新技能
        if (method === 'PUT') {
          const body = (await parseBody(route)) as Partial<MockSkill>;
          const updated = skillStore.update(id, {
            ...body,
            updated_at: new Date().toISOString(),
          });
          if (updated) {
            await jsonResponse(route, updated);
          } else {
            await jsonResponse(route, { detail: '未找到技能' }, 404);
          }
          return;
        }

        // DELETE /api/v1/skills/:id — 删除技能
        if (method === 'DELETE') {
          const deleted = skillStore.delete(id);
          if (deleted) {
            await noContentResponse(route);
          } else {
            await jsonResponse(route, { detail: '未找到技能' }, 404);
          }
          return;
        }
      }

      // GET /api/v1/skills — 列表
      if (method === 'GET' && path === API_PREFIX) {
        const all = skillStore.list();
        await jsonResponse(route, { data: all, total: all.length });
        return;
      }

      // 未匹配的路由继续
      await route.continue();
    });
  },
};
