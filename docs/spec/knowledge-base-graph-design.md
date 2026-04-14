# CkyClaw 知识库方案：基于 LLM Wiki 图谱的知识管理

> 版本：v1.0  
> 日期：2026-04-14  
> 状态：方案设计

## 1. 背景与动机

### 1.1 现状分析

当前知识库采用经典 RAG（Retrieval-Augmented Generation）管道：

```
文档上传 → 分块(Chunking) → 向量嵌入(Embedding) → 向量存储 → 余弦相似度检索
```

**存在的问题**：
- Embedding 仅有 `InMemoryEmbeddingProvider`（hash 伪实现），无生产级 Embedding
- 向量存储仅 `InMemoryVectorStore`，不支持持久化
- 纯向量检索缺乏语义理解，无法捕捉文档间的关系和层次结构
- 对复杂知识体系（概念联系、因果关系、层次结构）表达能力弱

### 1.2 目标方案

**放弃纯向量检索，转向 LLM Wiki 图谱方案**——利用 LLM 从文档中抽取实体、关系和概念，构建知识图谱，基于图谱提供结构化检索。

核心理念：
- **LLM 即抽取器**：用 LLM 从文档中抽取实体和关系，而非简单向量化
- **图谱即索引**：知识以图结构（实体-关系-属性）存储，而非扁平向量
- **社区即摘要**：通过图社区检测自动发现知识主题，生成 Wiki 式摘要
- **混合检索**：图遍历 + 关键词 + 可选向量，多路径融合

---

## 2. 架构设计

### 2.1 整体流程

```
                    ┌──────────────┐
                    │  文档上传     │
                    └──────┬───────┘
                           │
                    ┌──────▼───────┐
                    │  LLM 抽取    │  ← 实体识别 + 关系抽取 + 摘要生成
                    └──────┬───────┘
                           │
              ┌────────────┼────────────┐
              │            │            │
        ┌─────▼───┐  ┌────▼────┐  ┌───▼──────┐
        │  实体表  │  │ 关系表  │  │ 社区表    │
        │ entities │  │relations│  │communities│
        └────┬────┘  └────┬────┘  └────┬──────┘
             │            │            │
             └────────────┼────────────┘
                          │
                   ┌──────▼───────┐
                   │  图谱检索引擎  │
                   └──────┬───────┘
                          │
              ┌───────────┼───────────┐
              │           │           │
        ┌─────▼───┐ ┌────▼────┐ ┌───▼──────┐
        │实体查询  │ │关系遍历  │ │社区摘要   │
        │         │ │         │ │          │
        └─────────┘ └─────────┘ └──────────┘
                          │
                   ┌──────▼───────┐
                   │  上下文注入   │  → Agent system message
                   └──────────────┘
```

### 2.2 核心数据模型

#### 实体（Entity）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID | 主键 |
| knowledge_base_id | UUID(FK) | 所属知识库 |
| document_id | UUID(FK) | 来源文档 |
| name | VARCHAR(256) | 实体名称 |
| entity_type | VARCHAR(64) | 实体类型（Person/Concept/Tool/API/...） |
| description | TEXT | LLM 生成的描述 |
| attributes | JSONB | 附加属性 |
| source_chunk | TEXT | 抽取自哪段文本 |
| confidence | FLOAT | LLM 抽取置信度 |

#### 关系（Relation）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID | 主键 |
| knowledge_base_id | UUID(FK) | 所属知识库 |
| source_entity_id | UUID(FK) | 源实体 |
| target_entity_id | UUID(FK) | 目标实体 |
| relation_type | VARCHAR(64) | 关系类型（uses/depends_on/part_of/...） |
| description | TEXT | 关系描述 |
| weight | FLOAT | 关系强度 |
| source_chunk | TEXT | 抽取自哪段文本 |

#### 社区（Community）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID | 主键 |
| knowledge_base_id | UUID(FK) | 所属知识库 |
| name | VARCHAR(256) | 社区名称（LLM 生成） |
| summary | TEXT | Wiki 式摘要（LLM 生成） |
| entity_ids | UUID[] | 包含的实体列表 |
| level | INT | 社区层级（0=最细粒度） |
| parent_community_id | UUID | 层级父社区 |

---

## 3. Framework 层设计

### 3.1 模块结构

```
ckyclaw_framework/rag/
├── document.py       # 保留：文档加载
├── chunker.py        # 保留：分块（用于 LLM 抽取前的预分块）
├── graph/
│   ├── __init__.py
│   ├── extractor.py  # 新增：LLM 实体/关系抽取器
│   ├── entity.py     # 新增：Entity / Relation 数据类
│   ├── community.py  # 新增：社区检测 + 摘要生成
│   ├── store.py      # 新增：GraphStore ABC + PostgresGraphStore
│   └── retriever.py  # 新增：GraphRetriever 多路检索
├── pipeline.py       # 改造：支持图谱模式
└── tool.py           # 改造：图谱检索工具
```

### 3.2 抽取器（Extractor）

```python
@dataclass
class Entity:
    """图谱实体。"""
    name: str
    entity_type: str
    description: str
    attributes: dict[str, Any] = field(default_factory=dict)
    confidence: float = 1.0

@dataclass 
class Relation:
    """实体间关系。"""
    source: str          # 源实体 name
    target: str          # 目标实体 name
    relation_type: str
    description: str
    weight: float = 1.0

class GraphExtractor:
    """使用 LLM 从文本中抽取实体和关系。"""

    async def extract(
        self, 
        text: str, 
        model_provider: ModelProvider,
        entity_types: list[str] | None = None,
    ) -> tuple[list[Entity], list[Relation]]:
        """从文本中抽取实体和关系。"""
        ...
```

### 3.3 社区检测

基于 Leiden 算法（或简化的连通分量算法）对实体-关系图进行社区检测：

```python
class CommunityDetector:
    """图社区检测 + LLM 摘要生成。"""

    async def detect_communities(
        self,
        entities: list[Entity],
        relations: list[Relation],
        model_provider: ModelProvider,
        resolution: float = 1.0,
    ) -> list[Community]:
        """检测社区并生成 Wiki 摘要。"""
        ...
```

### 3.4 图谱检索器

```python
class GraphRetriever:
    """多路图谱检索。"""

    async def retrieve(
        self,
        query: str,
        store: GraphStore,
        model_provider: ModelProvider,
        top_k: int = 10,
    ) -> list[RetrievalResult]:
        """
        三路检索融合：
        1. 实体匹配：LLM 提取查询中的关键实体 → 精确/模糊匹配
        2. 关系遍历：从匹配实体出发，N 跳邻居遍历
        3. 社区摘要：查找相关社区的 Wiki 摘要
        """
        ...
```

---

## 4. Backend 层设计

### 4.1 新增 ORM 模型

在 `backend/app/models/` 新增：

- `KnowledgeEntity` — 映射 `knowledge_entities` 表
- `KnowledgeRelation` — 映射 `knowledge_relations` 表
- `KnowledgeCommunity` — 映射 `knowledge_communities` 表

### 4.2 新增 API 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/knowledge-bases/{kb_id}/build-graph` | 触发图谱构建（异步任务） |
| GET | `/knowledge-bases/{kb_id}/entities` | 实体列表（分页 + 搜索） |
| GET | `/knowledge-bases/{kb_id}/relations` | 关系列表 |
| GET | `/knowledge-bases/{kb_id}/communities` | 社区列表 |
| GET | `/knowledge-bases/{kb_id}/graph` | 图谱数据（用于可视化） |
| POST | `/knowledge-bases/{kb_id}/graph-search` | 图谱检索（替代向量检索） |

### 4.3 图谱构建流程

```
1. 用户上传文档 → 存储到 knowledge_documents
2. 用户点击"构建图谱"
3. 后端异步任务：
   a. 加载文档内容
   b. 分块（用于 LLM 抽取，控制上下文长度）
   c. 逐块调用 GraphExtractor 抽取实体+关系
   d. 合并去重：相同名称的实体合并，属性合并
   e. 社区检测 + Wiki 摘要生成
   f. 持久化到 PG 表
4. 前端轮询/WebSocket 获取进度
```

---

## 5. Frontend 层设计

### 5.1 页面改造

**知识库详情页**新增：

1. **图谱可视化 Tab**：使用 ReactFlow 或 D3.js 展示实体-关系图
2. **实体列表 Tab**：表格浏览所有实体（搜索、过滤、编辑）
3. **社区摘要 Tab**：Wiki 式浏览社区摘要（层级结构）
4. **图谱检索 Tab**：替代原来的向量检索，支持自然语言查询

### 5.2 创建/编辑表单改造

- 移除 `embedding_model` 字段
- 移除 `chunk_strategy` 相关配置
- 新增 `extract_model` 字段：选择用于抽取的 LLM 模型
- 新增 `entity_types` 字段：配置需要抽取的实体类型
- 新增 "构建图谱" 按钮

---

## 6. Agent 集成

### 6.1 知识检索工具

改造 `create_knowledge_base_tool()` 为图谱检索：

```python
def create_knowledge_graph_tool(
    store: GraphStore,
    model_provider: ModelProvider,
) -> FunctionTool:
    """创建图谱检索工具，供 Agent 调用。"""
    
    async def search_knowledge(query: str) -> str:
        """在知识图谱中搜索相关知识。"""
        retriever = GraphRetriever()
        results = await retriever.retrieve(query, store, model_provider)
        return format_results(results)
    
    return FunctionTool.from_function(search_knowledge)
```

### 6.2 Runner 集成

Runner 在构建 system message 时：
1. 检查 Agent 绑定的 `knowledge_bases`
2. 调用 GraphRetriever 检索相关知识
3. 将检索到的实体描述 + 关系 + 社区摘要注入 system message

---

## 7. 迁移策略

### 7.1 兼容性

- **保留现有 API**：`/knowledge-bases` CRUD 不变
- **新增图谱 API**：在现有基础上扩展
- **渐进迁移**：现有 `knowledge_chunks` 表保留，新增图谱表并行存在
- **双模式**：知识库支持 `mode: "vector" | "graph"` 字段，默认新建为 `graph`

### 7.2 实施节奏

| 阶段 | 内容 | 预期 |
|------|------|------|
| Phase 1 | Framework 层：Entity/Relation 数据类 + GraphExtractor + GraphStore ABC | 基础数据结构 |
| Phase 2 | Backend 层：ORM 模型 + Alembic 迁移 + 异步图谱构建 API | 后端能力 |
| Phase 3 | Framework 层：CommunityDetector + GraphRetriever | 检索能力 |
| Phase 4 | Frontend 层：图谱可视化 + 实体浏览 + 图谱检索 UI | 前端交互 |
| Phase 5 | Runner 集成：知识注入 + Agent 绑定 | 端到端打通 |

---

## 8. 技术选型

| 组件 | 选型 | 理由 |
|------|------|------|
| **图存储** | PostgreSQL（实体/关系表 + 递归 CTE 遍历） | 不引入图数据库，复用现有 PG |
| **社区检测** | Python igraph + Leiden 算法 | 轻量级，无需额外服务 |
| **LLM 抽取** | CkyClaw Framework ModelProvider | 复用现有 LLM 集成 |
| **图可视化** | ReactFlow（已集成） | 复用现有依赖 |
| **缓存** | Redis（图谱检索结果缓存） | 复用现有 Redis |

### 8.1 为什么不用图数据库？

- **简化部署**：不引入 Neo4j/ArangoDB 等额外中间件
- **PostgreSQL 足够**：实体/关系规模（单知识库 < 100K 实体）下，PG + 索引 + CTE 性能足够
- **后续可扩展**：`GraphStore` 设计为 ABC，未来可添加 Neo4j 实现
