# Graphify 图谱驱动知识库方案研究报告

> 版本：v1.0  
> 日期：2026-04-16  
> 作者：cky  
> 状态：调研报告

---

## 1. 背景

### 1.1 问题来源

原知识库方案（`knowledge-base-graph-design.md` v1.0）已提出用 LLM Wiki 图谱替代向量检索。本报告进一步聚焦：**如何将 CkyClaw 内部已在运行的 graphify 知识图谱工具应用到 Agent 知识库功能中**。

### 1.2 graphify 是什么

`graphify`（本项目使用的版本）是一个从代码/文档语料中自动构建知识图谱的工具：

- **输入**：代码库、Markdown 文档、任意文本文件
- **输出**：
  - `graph.json` — 全量节点/边数据（CosmosGraph 兼容格式）
  - `GRAPH_REPORT.md` — 结构分析报告（God Node、社区、意外连接）
  - `manifest.json` — 元数据（节点数、边数、社区数、Token 成本）
  - `graphify-out/wiki/` — 社区摘要 Wiki（可选）

本项目 graphify 运行结果（`graphify-out/GRAPH_REPORT.md`）显示：

| 指标 | 数值 |
|------|------|
| 节点数 | 67,359 |
| 边数 | 182,706 |
| 社区数 | 3,539 |
| 图谱构建模式 | INFERRED（无 LLM 调用，基于静态分析） |

---

## 2. graphify 核心机制分析

### 2.1 图谱构建流程

```
语料文件 (*.py / *.ts / *.md)
       │
       ▼
  静态+语义解析
  ├── 标识符提取（函数、类、变量名）
  ├── 导入/依赖边推断（INFERRED）
  └── 注释/文档字符串读取
       │
       ▼
  图谱构建
  ├── 节点：代码实体 / 概念 / 文档段落
  ├── 边：uses / imports / calls / implements / references
  └── 置信度：EXTRACTED(1.0) > INFERRED(0.5) > AMBIGUOUS
       │
       ▼
  社区检测（Louvain / Label Propagation）
       │
       ▼
  输出：graph.json + GRAPH_REPORT.md
```

### 2.2 两种构建模式对比

| 模式 | 说明 | Token 消耗 | 适合场景 |
|------|------|-----------|---------|
| **INFERRED**（纯静态） | AST 解析 + 符号引用分析，无 LLM 调用 | 0 | 代码库大规模构建 |
| **EXTRACTED**（LLM 驱动） | LLM 语义抽取实体、关系、摘要 | 高 | 文档/非结构化文本 |

CkyClaw 知识库场景中，用户上传的文档（PDF、Markdown、Word）以非结构化文本为主，**需要 EXTRACTED 模式**。

---

## 3. 集成方案设计

### 3.1 整体架构

```
用户上传文档
     │
     ▼
[Ingest Pipeline]
  ├── 文件解析（PDF/DOCX/MD → 纯文本）
  ├── 分段（按章节/段落）
  └── 送入 graphify EXTRACTED 模式
         │
         ├── LLM 抽取实体 + 关系 + 摘要
         └── 写入 KnowledgeGraph (PostgreSQL JSON)
              │
              ▼
    [检索接口]
    ├── 关键词检索（实体名称匹配）
    ├── 图遍历（实体→关系→相邻实体）
    └── 社区摘要（按主题聚合）
              │
              ▼
    Agent RAG 注入（Context Engineering）
```

### 3.2 PostgreSQL 图谱存储方案

利用现有 PostgreSQL，无需引入 Neo4j 等图数据库：

```sql
-- 节点表：概念/实体
CREATE TABLE kb_graph_nodes (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    kb_id       UUID REFERENCES knowledge_bases(id) ON DELETE CASCADE,
    name        TEXT NOT NULL,          -- 实体/概念名
    node_type   TEXT NOT NULL,          -- 'entity' | 'concept' | 'chunk'
    summary     TEXT,                   -- LLM 生成的摘要
    properties  JSONB DEFAULT '{}',     -- 额外元数据
    embedding   vector(1536),           -- 可选向量（pgvector）
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

-- 边表：关系
CREATE TABLE kb_graph_edges (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    kb_id       UUID REFERENCES knowledge_bases(id) ON DELETE CASCADE,
    source_id   UUID REFERENCES kb_graph_nodes(id) ON DELETE CASCADE,
    target_id   UUID REFERENCES kb_graph_nodes(id) ON DELETE CASCADE,
    relation    TEXT NOT NULL,          -- 'uses' | 'references' | 'is_a' | 'part_of' 等
    confidence  FLOAT DEFAULT 1.0,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

-- 社区表：聚类主题
CREATE TABLE kb_graph_communities (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    kb_id       UUID REFERENCES knowledge_bases(id) ON DELETE CASCADE,
    community_id INTEGER NOT NULL,
    title       TEXT,                   -- 社区主题标题
    summary     TEXT,                   -- 社区摘要（用于 RAG 注入）
    node_count  INTEGER DEFAULT 0,
    cohesion    FLOAT DEFAULT 0.0,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);
```

### 3.3 LLM 抽取 Prompt

```
你是一个知识图谱构建专家。请从以下文本中抽取：
1. **实体**：文档中提到的主要概念、对象、人物、组织
2. **关系**：实体之间的关系（uses/is_a/part_of/references/implements）
3. **摘要**：用一句话概括文本核心内容

输出格式（JSON）：
{
  "entities": [{"name": "...", "type": "concept|entity|person|org", "description": "..."}],
  "relations": [{"source": "...", "target": "...", "relation": "..."}],
  "summary": "..."
}

文本：
{chunk_text}
```

### 3.4 检索策略

| 检索模式 | 实现方式 | 适合查询 |
|---------|---------|---------|
| **关键词匹配** | `WHERE name ILIKE '%keyword%'` | 精确实体查找 |
| **图遍历** | 递归 CTE + depth 限制 | "X 和什么相关" |
| **社区摘要** | SELECT * FROM communities ORDER BY relevance | 主题概览 |
| **混合** | 上述三路结果合并去重 | 通用 RAG |

---

## 4. 与现有 CkyClaw 知识库的集成

### 4.1 当前知识库状态

现有 `knowledge_bases` 表和相关 API（`/api/v1/knowledge-bases`）已实现：
- 知识库 CRUD + 文档上传
- 文件存储（`uploads/`）
- RAG 检索 API（`/api/v1/knowledge-bases/{id}/search`）

### 4.2 增量改造路径

**阶段 1（M0 — 最小可用）**：
- 在文档上传时异步触发 graphify EXTRACTED 流程
- 将抽取的实体/关系写入 `kb_graph_nodes` / `kb_graph_edges`
- 检索 API 增加 `?mode=graph` 参数，返回图谱检索结果

**阶段 2（M1 — 社区摘要）**：
- 抽取完成后运行 Louvain 社区检测
- 生成社区摘要写入 `kb_graph_communities`
- 支持"按主题问答"场景（RAG 注入社区摘要）

**阶段 3（M2 — 图 + 向量混合）**：
- 为节点生成 embedding（可选 pgvector）
- 检索时先语义相似召回候选节点，再图遍历扩展
- 最终合并用于 Context Engineering 注入

---

## 5. 可行性评估

### 5.1 优点

| 优势 | 说明 |
|------|------|
| **语义理解强** | LLM 可识别文档中隐式的概念关系，而非仅关键词匹配 |
| **结构化知识** | 图谱比向量更能表达知识层次和关系 |
| **社区摘要** | 主题聚合适合"给我讲讲 X 是什么"类问答 |
| **无额外基础设施** | PostgreSQL 即可，无需 Neo4j/向量数据库 |
| **可增量构建** | 每次上传新文档只需处理增量节点 |

### 5.2 局限性

| 局限 | 缓解措施 |
|------|---------|
| LLM 抽取 Token 成本高 | 缓存抽取结果 + 去重检测 |
| 图谱质量依赖 LLM 能力 | 选用推理级模型（GPT-4o/Claude）进行抽取 |
| 关系抽取有误差 | 置信度评分 + 人工审核接口 |
| 冷启动慢（大文档） | 异步任务队列（Celery/ARQ）+ 进度通知 |

### 5.3 推荐优先级

- **阶段 1（M0）**：P1 — 核心知识库价值，应尽快落地
- **阶段 2（M1）**：P2 — 差异化功能，竞品少见
- **阶段 3（M2）**：P3 — 锦上添花，可延后

---

## 6. 结论

graphify 的 EXTRACTED 模式（LLM 驱动实体关系抽取 + 社区检测）完全适合 CkyClaw 知识库场景：

1. **技术可行**：现有 PostgreSQL + FastAPI 可承载图谱存储和检索，无需额外基础设施
2. **业务价值高**：图谱检索 >> 纯向量相似度，特别适合知识密集型文档
3. **演进路径清晰**：三阶段渐进，最小可用版（阶段1）工作量约 3–5 人天

**建议**：将 graphify 图谱方案作为知识库 v2.0 的核心架构，替代当前 InMemory 伪实现，纳入 N1 阶段演进规划。
