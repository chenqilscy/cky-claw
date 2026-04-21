# Kasaya 知识库方案：基于 LLM Wiki 图谱的知识管理

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
kasaya/rag/
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
| **LLM 抽取** | Kasaya Framework ModelProvider | 复用现有 LLM 集成 |
| **图可视化** | ReactFlow（已集成） | 复用现有依赖 |
| **缓存** | Redis（图谱检索结果缓存） | 复用现有 Redis |

### 8.1 为什么不用图数据库？

- **简化部署**：不引入 Neo4j/ArangoDB 等额外中间件
- **PostgreSQL 足够**：实体/关系规模（单知识库 < 100K 实体）下，PG + 索引 + CTE 性能足够
- **后续可扩展**：`GraphStore` 设计为 ABC，未来可添加 Neo4j 实现

---

## 9. Graphify 方案与实现研究报告

> 补充日期：2026-04-15

### 9.1 项目概况

[graphify](https://github.com/safishamsi/graphify)（PyPI 包名 `graphifyy`）是一个 AI 编程助手技能插件，可将任意文件夹（代码、文档、论文、图片、视频）转化为可查询的知识图谱。

| 指标 | 数值 |
|------|------|
| GitHub Stars | 26.5k+ |
| 版本 | v0.4.14 |
| 许可证 | MIT |
| Python 版本 | 3.10+ |
| 支持平台 | Claude Code、Codex、OpenCode、Cursor、Gemini CLI、GitHub Copilot CLI、Aider、OpenClaw、Trae、Kiro、Hermes 等 14+ 个平台 |

### 9.2 核心架构

graphify 的工作流分为三个阶段：

```
Pass 1: AST 静态分析（代码文件）
├── tree-sitter 解析 25 种语言
├── 提取：classes / functions / imports / call graphs / docstrings / rationale comments
├── 跨文件调用图
└── 无需 LLM，纯本地执行

Pass 2: 音视频转录（可选）
├── faster-whisper 本地转录
├── 基于语料 god nodes 的领域感知提示词
├── 转录缓存（重复运行即时跳过）
└── 音频不出本机

Pass 3: LLM 语义抽取（文档/论文/图片/转录稿）
├── Claude 子代理并行抽取
├── 提取概念、关系、设计原理
├── 合并为 NetworkX 图
├── Leiden 社区检测（基于图拓扑，非 Embedding）
└── 输出：HTML + JSON + Report
```

### 9.3 输出产物

```
graphify-out/
├── graph.html          # 交互式图谱可视化（vis.js）
├── GRAPH_REPORT.md     # God nodes、意外连接、建议问题
├── graph.json          # 持久化图谱 JSON（可周后查询）
├── cache/              # SHA256 缓存（增量更新仅处理变更文件）
├── wiki/               # (--wiki) Wikipedia 式社区文章
│   ├── index.md        # 入口索引
│   └── community-*.md  # 各社区文章
└── transcripts/        # (视频) 转录稿缓存
```

### 9.4 关键特性分析

#### 9.4.1 关系置信度标注

每条关系都标记来源类型：

| 标签 | 含义 | 置信度 |
|------|------|--------|
| `EXTRACTED` | 从源码/文档中直接发现 | 1.0（确定） |
| `INFERRED` | LLM 推理得出（合理推断） | 0.0-1.0（含分数） |
| `AMBIGUOUS` | 不确定，标记待审查 | 需人工确认 |

#### 9.4.2 检索效率

官方基准测试：

| 语料规模 | 文件数 | Token 压缩比 |
|---------|:------:|:-------:|
| Karpathy repos + 5 论文 + 4 图片 | 52 | **71.5x** |
| graphify 源码 + Transformer 论文 | 4 | 5.4x |
| httpx（小型库） | 6 | ~1x |

> 压缩比随语料规模增长。小项目（6 文件）图谱价值在于结构化清晰度，而非压缩。

#### 9.4.3 增量更新

- `--update`：仅重新抽取变更文件，合并到现有图谱
- `--watch`：后台监听文件变更（代码文件立即重建 AST；文档变更通知用户执行 `--update`）
- `graphify hook install`：Git post-commit / post-checkout 钩子自动重建
- SHA256 缓存保证未变更文件零开销

#### 9.4.4 MCP 服务器

```bash
python -m graphify.serve graphify-out/graph.json
```

暴露结构化图访问 API：`query_graph`、`get_node`、`get_neighbors`、`shortest_path`。Agent 可通过 MCP 协议直接查询图谱。

#### 9.4.5 多种导出格式

| 格式 | 命令 | 用途 |
|------|------|------|
| HTML | 默认 | 交互式可视化浏览 |
| JSON | 默认 | 程序化查询 |
| Wiki | `--wiki` | Agent 可导航的 Markdown 知识库 |
| SVG | `--svg` | 静态图导出 |
| GraphML | `--graphml` | Gephi / yEd 导入 |
| Cypher | `--neo4j` | Neo4j 导入脚本 |
| Neo4j Push | `--neo4j-push bolt://...` | 直接推送到 Neo4j |

### 9.5 与 Kasaya 知识库的整合方案

#### 9.5.1 方案对比

| 维度 | Kasaya 当前方案（第 2-8 章） | graphify 方案 |
|------|----------------------------|---------------|
| 抽取引擎 | 自研 GraphExtractor | graphify（tree-sitter + Claude 子代理） |
| 代码分析 | 仅 LLM 抽取 | AST 静态分析（精确）+ LLM 补充 |
| 社区检测 | igraph + Leiden | graspologic + Leiden |
| 图存储 | PostgreSQL（自研 ORM） | NetworkX + JSON 文件 |
| 可视化 | ReactFlow | vis.js（graph.html） |
| 增量更新 | 需自研 | 内置（SHA256 缓存 + --update） |
| 多模态 | 仅文档 | 代码 + 文档 + 图片 + 视频 + 论文 |
| 置信度 | 仅 0.0-1.0 | EXTRACTED / INFERRED / AMBIGUOUS 三级 |
| 部署 | 嵌入后端服务 | 独立 CLI（pip install） |

#### 9.5.2 推荐整合策略

**方案 A：graphify 作为抽取引擎（推荐）**

```
用户上传文档/代码
    ↓
Kasaya 后端调用 graphify Python API
    ↓
graphify 执行三阶段抽取 → 生成 graph.json
    ↓
Kasaya 解析 graph.json → 导入到 PostgreSQL 图谱表
    ↓
Kasaya GraphRetriever 基于 PG 数据检索
```

**优势**：
- 利用 graphify 成熟的 AST 分析和 LLM 抽取能力
- 保持 Kasaya 自身的图存储和检索系统
- graphify 的 MCP 服务器可直接暴露给 Agent 使用

**实施步骤**：
1. `pip install graphifyy` 添加为 backend 依赖
2. 在 `knowledge_base_service.py` 中集成 graphify 的 Python API
3. 图谱构建任务调用 graphify，输出 `graph.json`
4. 解析 `graph.json` 中的 nodes/edges，写入 `knowledge_entities` / `knowledge_relations` 表
5. 社区信息写入 `knowledge_communities` 表

**方案 B：graphify MCP Server 直接对接**

```
Agent 运行时
    ↓
MCP Client 连接 graphify MCP Server（stdio）
    ↓
Agent 通过 query_graph / get_neighbors 查询
    ↓
直接返回结构化结果
```

**优势**：零开发量。**劣势**：不经过 Kasaya 管控，无法审计和权限控制。

#### 9.5.3 建议路径

1. **短期**（Phase 1）：方案 B — 将 graphify MCP Server 作为预置 MCP 工具，Agent 直接使用
2. **中期**（Phase 2）：方案 A — 集成 graphify Python API 作为抽取引擎，数据导入 PG
3. **长期**（Phase 3）：基于 graphify 的 Wiki 输出构建 Agent 可导航知识库

### 9.6 技术风险

| 风险 | 等级 | 缓解 |
|------|:----:|------|
| graphify 依赖 Claude API（LLM 抽取） | 中 | Kasaya 可替换为自有 Provider |
| PyPI 包名 `graphifyy`（双 y）易混淆 | 低 | 锁定版本 + 内部文档标注 |
| tree-sitter 安装可能需要编译 | 低 | Docker 镜像预装 |
| graphify API 不稳定（快速迭代中） | 中 | 锁定版本 + 封装适配层 |
| graph.json 大文件性能（>10万节点） | 中 | 按知识库分片 + PG 持久化后释放 JSON |
