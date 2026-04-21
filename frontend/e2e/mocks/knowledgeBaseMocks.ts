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

export interface MockGraphEntity {
  id: string;
  knowledge_base_id: string;
  document_id: string;
  name: string;
  entity_type: string;
  description: string;
  attributes: Record<string, unknown>;
  confidence: number;
  confidence_label: string;
  content_hash: string;
  created_at: string;
}

export interface MockGraphCommunity {
  id: string;
  knowledge_base_id: string;
  name: string;
  summary: string;
  entity_count: number;
  level: number;
  parent_community_id: string | null;
  created_at: string;
  updated_at: string;
}

export interface MockGraphBuildTask {
  task_id: string;
  kb_id: string;
  status: string;
  progress: number;
  entity_count: number;
  relation_count: number;
  community_count: number;
  error: string | null;
  poll_count: number;
}

/* ---- 预设 mock 数据 ---- */

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
  {
    name: 'e2e-vector-kb',
    description: 'E2E 向量搜索测试知识库',
    embedding_model: 'text-embedding-3-small',
    chunk_strategy: { chunk_size: 512, overlap: 64 },
    mode: 'vector',
    metadata: {},
    created_at: '2025-01-01T00:00:00Z',
    updated_at: '2025-01-01T00:00:00Z',
  },
];

const presetDocuments: Omit<MockKnowledgeDocument, 'id'>[] = [
  {
    knowledge_base_id: '', // will be set after KB id is known
    filename: 'test-doc.txt',
    media_type: 'text/plain',
    size_bytes: 2048,
    status: 'indexed',
    chunk_count: 5,
    metadata: {},
    created_at: '2025-01-01T00:00:00Z',
    updated_at: '2025-01-01T00:00:00Z',
  },
];

const presetEntities: Omit<MockGraphEntity, 'id'>[] = [
  {
    knowledge_base_id: '',
    document_id: 'doc-1',
    name: 'Kasaya Agent',
    entity_type: 'Concept',
    description: 'Kasaya 框架中的核心 Agent 数据类',
    attributes: {},
    confidence: 0.95,
    confidence_label: 'extracted',
    content_hash: 'abc123',
    created_at: '2025-01-01T00:00:00Z',
  },
  {
    knowledge_base_id: '',
    document_id: 'doc-1',
    name: 'Runner',
    entity_type: 'Tool',
    description: '执行引擎，支持 run/run_sync/run_streamed',
    attributes: {},
    confidence: 0.88,
    confidence_label: 'extracted',
    content_hash: 'def456',
    created_at: '2025-01-01T00:00:00Z',
  },
];

const presetCommunities: Omit<MockGraphCommunity, 'id'>[] = [
  {
    knowledge_base_id: '',
    name: 'Agent 执行流程',
    summary: 'Agent 生命周期管理和执行引擎相关实体',
    entity_count: 3,
    level: 0,
    parent_community_id: null,
    created_at: '2025-01-01T00:00:00Z',
    updated_at: '2025-01-01T00:00:00Z',
  },
];

/* ---- 内存存储 ---- */

export const kbStore = new MockStore<MockKnowledgeBase>();
export const kbDocStore = new MockStore<MockKnowledgeDocument>();
export const entityStore = new MockStore<MockGraphEntity>();
export const communityStore = new MockStore<MockGraphCommunity>();

/** 图谱构建任务存储（key = task_id） */
const buildTasks = new Map<string, MockGraphBuildTask>();

/** 初始化预设数据 */
function seedData() {
  for (const item of presetKnowledgeBases) {
    kbStore.create({ ...item });
  }

  // 为 graph 模式 KB 添加预设文档和实体
  const graphKB = kbStore.findBy('name', 'e2e-mock-kb');
  if (graphKB) {
    for (const doc of presetDocuments) {
      kbDocStore.create({ ...doc, knowledge_base_id: graphKB.id });
    }
    for (const entity of presetEntities) {
      entityStore.create({ ...entity, knowledge_base_id: graphKB.id });
    }
    for (const community of presetCommunities) {
      communityStore.create({ ...community, knowledge_base_id: graphKB.id });
    }
  }

  // 为 vector 模式 KB 添加预设文档
  const vectorKB = kbStore.findBy('name', 'e2e-vector-kb');
  if (vectorKB) {
    kbDocStore.create({
      knowledge_base_id: vectorKB.id,
      filename: 'vector-test.txt',
      media_type: 'text/plain',
      size_bytes: 1024,
      status: 'indexed',
      chunk_count: 3,
      metadata: {},
      created_at: '2025-01-01T00:00:00Z',
      updated_at: '2025-01-01T00:00:00Z',
    });
  }
}

/* ---- URL 前缀 ---- */

const API_PREFIX = '/api/v1/knowledge-bases';

/* ---- 辅助：提取 query 参数 ---- */

function getQueryParam(url: string, key: string): string | null {
  const u = new URL(url);
  return u.searchParams.get(key);
}

/* ---- 模拟向量搜索结果 ---- */

const mockSearchResults = [
  {
    chunk_id: 'chunk-1',
    document_id: 'doc-1',
    content: 'Kasaya Agent 是基于声明式定义的 AI Agent 数据类，支持指令、模型、工具、Handoff 等配置。',
    score: 0.92,
    metadata: {},
  },
  {
    chunk_id: 'chunk-2',
    document_id: 'doc-1',
    content: 'Runner 执行引擎负责构建消息、调用 LLM、并行执行工具、处理 Handoff。',
    score: 0.85,
    metadata: {},
  },
];

/* ---- 模拟图谱搜索结果 ---- */

const mockGraphSearchResults = [
  {
    entity: { id: 'e-1', name: 'Kasaya Agent', entity_type: 'Concept', description: '核心 Agent 数据类', confidence: 0.95, confidence_label: 'extracted' },
    relation: null,
    community: null,
    score: 0.93,
    source: 'entity_match',
  },
  {
    entity: null,
    relation: { id: 'r-1', source_entity_id: 'e-1', target_entity_id: 'e-2', relation_type: 'executed_by', description: 'Agent 由 Runner 执行', weight: 0.9 },
    community: null,
    score: 0.87,
    source: 'relation_traverse',
  },
  {
    entity: null,
    relation: null,
    community: { id: 'c-1', name: 'Agent 执行流程', summary: 'Agent 生命周期管理相关实体', level: 0 },
    score: 0.82,
    source: 'community_match',
  },
];

/* ---- Mock 模块 ---- */

export const knowledgeBaseMocks: MockModule = {
  name: 'knowledge-bases',

  reset() {
    kbStore.reset();
    kbDocStore.reset();
    entityStore.reset();
    communityStore.reset();
    buildTasks.clear();
    seedData();
  },

  async register(page: Page) {
    this.reset();

    await page.route('**/api/v1/knowledge-bases**', async (route: Route) => {
      const url = route.request().url();
      const path = getPath(url);
      const method = route.request().method();

      // ---- 顶层路由 ----

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

      // GET /api/v1/knowledge-bases — 列表
      if (method === 'GET' && path === API_PREFIX) {
        const all = kbStore.list();
        await jsonResponse(route, { data: all, total: all.length, limit: 20, offset: 0 });
        return;
      }

      // ---- 子路径路由（长路径优先） ----

      // GET /api/v1/knowledge-bases/:id/documents — 文档列表
      const docMatch = extractPathParams(`${API_PREFIX}/:id/documents`, path);
      if (method === 'GET' && docMatch) {
        const docs = kbDocStore.list().filter((d) => d.knowledge_base_id === docMatch.id);
        await jsonResponse(route, docs);
        return;
      }

      // POST /api/v1/knowledge-bases/:id/documents — 上传文档
      if (method === 'POST' && docMatch) {
        const now = new Date().toISOString();
        const doc = kbDocStore.create({
          knowledge_base_id: docMatch.id,
          filename: 'uploaded-file.txt',
          media_type: 'text/plain',
          size_bytes: 512,
          status: 'indexed',
          chunk_count: 2,
          metadata: {},
          created_at: now,
          updated_at: now,
        });
        await jsonResponse(route, doc, 201);
        return;
      }

      // POST /api/v1/knowledge-bases/:id/search — 向量搜索
      const searchMatch = extractPathParams(`${API_PREFIX}/:id/search`, path);
      if (method === 'POST' && searchMatch) {
        const body = (await parseBody(route)) as { query: string };
        await jsonResponse(route, {
          knowledge_base_id: searchMatch.id,
          query: body.query,
          results: mockSearchResults,
        });
        return;
      }

      // POST /api/v1/knowledge-bases/:id/build-graph — 构建图谱
      const buildGraphMatch = extractPathParams(`${API_PREFIX}/:id/build-graph`, path);
      if (method === 'POST' && buildGraphMatch) {
        const taskId = `build-task-${Date.now()}`;
        buildTasks.set(taskId, {
          task_id: taskId,
          kb_id: buildGraphMatch.id,
          status: 'processing',
          progress: 0.1,
          entity_count: 0,
          relation_count: 0,
          community_count: 0,
          error: null,
          poll_count: 0,
        });
        await jsonResponse(route, { task_id: taskId, status: 'processing' }, 201);
        return;
      }

      // GET /api/v1/knowledge-bases/:id/graph-status — 图谱构建状态轮询
      const graphStatusMatch = extractPathParams(`${API_PREFIX}/:id/graph-status`, path);
      if (method === 'GET' && graphStatusMatch) {
        const taskId = getQueryParam(url, 'task_id');
        const task = taskId ? buildTasks.get(taskId) : null;
        if (!task) {
          await jsonResponse(route, { detail: '任务不存在' }, 404);
          return;
        }
        task.poll_count++;
        if (task.poll_count >= 3) {
          task.status = 'completed';
          task.progress = 1.0;
          task.entity_count = 5;
          task.relation_count = 3;
          task.community_count = 1;
        } else {
          task.progress = Math.min(0.1 + task.poll_count * 0.3, 0.9);
          task.entity_count = task.poll_count * 2;
          task.relation_count = task.poll_count;
        }
        await jsonResponse(route, {
          task_id: task.task_id,
          status: task.status,
          progress: task.progress,
          entity_count: task.entity_count,
          relation_count: task.relation_count,
          community_count: task.community_count,
          error: task.error,
        });
        return;
      }

      // GET /api/v1/knowledge-bases/:id/graph — 图谱可视化数据
      const graphDataMatch = extractPathParams(`${API_PREFIX}/:id/graph`, path);
      if (method === 'GET' && graphDataMatch) {
        await jsonResponse(route, {
          nodes: [
            { id: 'n1', label: 'Kasaya Agent', type: 'Concept', confidence: 0.95 },
            { id: 'n2', label: 'Runner', type: 'Tool', confidence: 0.88 },
          ],
          edges: [
            { source: 'n1', target: 'n2', type: 'executed_by', weight: 0.9 },
          ],
        });
        return;
      }

      // GET /api/v1/knowledge-bases/:id/entities — 实体列表
      const entitiesMatch = extractPathParams(`${API_PREFIX}/:id/entities`, path);
      if (method === 'GET' && entitiesMatch) {
        const entities = entityStore.list().filter((e) => e.knowledge_base_id === entitiesMatch.id);
        await jsonResponse(route, { data: entities, total: entities.length, limit: 50, offset: 0 });
        return;
      }

      // GET /api/v1/knowledge-bases/:id/relations — 关系列表
      const relationsMatch = extractPathParams(`${API_PREFIX}/:id/relations`, path);
      if (method === 'GET' && relationsMatch) {
        await jsonResponse(route, { data: [], total: 0, limit: 50, offset: 0 });
        return;
      }

      // GET /api/v1/knowledge-bases/:id/communities — 社区列表
      const communitiesMatch = extractPathParams(`${API_PREFIX}/:id/communities`, path);
      if (method === 'GET' && communitiesMatch) {
        const communities = communityStore.list().filter((c) => c.knowledge_base_id === communitiesMatch.id);
        await jsonResponse(route, { data: communities, total: communities.length, limit: 50, offset: 0 });
        return;
      }

      // POST /api/v1/knowledge-bases/:id/graph-search — 图谱搜索
      const graphSearchMatch = extractPathParams(`${API_PREFIX}/:id/graph-search`, path);
      if (method === 'POST' && graphSearchMatch) {
        const body = (await parseBody(route)) as { query: string };
        await jsonResponse(route, {
          knowledge_base_id: graphSearchMatch.id,
          query: body.query,
          results: mockGraphSearchResults,
        });
        return;
      }

      // DELETE /api/v1/knowledge-bases/:id/graph — 删除图谱
      const graphDeleteMatch = extractPathParams(`${API_PREFIX}/:id/graph`, path);
      if (method === 'DELETE' && graphDeleteMatch) {
        // 清空该 KB 的实体和社区
        const kbId = graphDeleteMatch.id;
        for (const e of entityStore.list()) {
          if (e.knowledge_base_id === kbId) entityStore.delete(e.id);
        }
        for (const c of communityStore.list()) {
          if (c.knowledge_base_id === kbId) communityStore.delete(c.id);
        }
        await jsonResponse(route, { deleted_count: 1 });
        return;
      }

      // ---- 单条 :id 路由 ----

      const singleMatch = extractPathParams(`${API_PREFIX}/:id`, path);
      if (singleMatch) {
        const { id } = singleMatch;

        // PUT — 更新知识库
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

        // DELETE — 删除知识库
        if (method === 'DELETE') {
          const deleted = kbStore.delete(id);
          if (deleted) {
            await noContentResponse(route);
          } else {
            await jsonResponse(route, { detail: '未找到知识库' }, 404);
          }
          return;
        }

        // GET — 获取详情
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

      // 未匹配的路由继续
      await route.continue();
    });
  },
};
