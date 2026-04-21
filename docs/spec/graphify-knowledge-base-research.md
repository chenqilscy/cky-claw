# Graphify 图谱驱动知识库 — 集成可行性补充报告

> 版本：v1.1（修正版）
> 日期：2026-04-16
> 作者：cky
> 状态：调研报告
> 上游文档：[knowledge-base-graph-design.md](knowledge-base-graph-design.md)（完整方案设计）

---

## 0. 文档定位

本文档是 [knowledge-base-graph-design.md](knowledge-base-graph-design.md) 的**补充调研报告**，聚焦于一个具体问题：

> **能否将外部工具 graphify 的图谱构建能力，应用到 Kasaya 知识库的 Ingest Pipeline 中？**

本文档的结论将影响 `knowledge-base-graph-design.md` 第 9 章中 graphify 整合策略的选型。两份文档的术语和表名以 `knowledge-base-graph-design.md` 为准。

---

## 1. graphify 是什么

### 1.1 准确定义

`graphify`（[GitHub](https://github.com/safishamsi/graphify)，PyPI 包名 `graphifyy`）是一个 **AI 编程助手技能插件**，可将任意文件夹（代码、文档、论文、图片、视频）转化为可查询的知识图谱。

**关键事实**：

| 属性 | 数值 |
|------|------|
| 类型 | Claude Code / Codex / Gemini CLI 技能插件 |
| PyPI 包名 | `graphifyy`（双 y） |
| 版本 | v0.4.14+ |
| 许可证 | MIT |
| 定位 | AI 编程助手的工作流工具，**不是 Python SDK** |

graphify 在本项目的运行结果（`graphify-out/GRAPH_REPORT.md`）：

| 指标 | 数值 |
|------|------|
| 节点数 | 67,359 |
| 边数 | 182,706 |
| 社区数 | 3,539 |
| 关系标签分布 | 37% EXTRACTED / 63% INFERRED / 0% AMBIGUOUS |
| Token 消耗 | 0（本次构建未启用 LLM 抽取） |
| 社区内聚度 | 全部 0.0（检测质量差） |

### 1.2 工作原理 — 三阶段流水线

```
Pass 1: AST 静态分析（代码文件）
├── tree-sitter 解析 25 种语言
├── 提取：classes / functions / imports / call graphs / docstrings
├── 跨文件调用图推断
└── 无需 LLM，纯本地执行

Pass 2: 音视频转录（可选）
├── faster-whisper 本地转录
└── 转录缓存（重复运行即时跳过）

Pass 3: LLM 语义抽取（文档/论文/图片/转录稿）
├── Claude 子代理并行抽取（依赖 Claude API）
├── 提取概念、关系、设计原理
├── 合并为 NetworkX 图
├── Leiden 社区检测
└── 输出：HTML + JSON + Report
```

### 1.3 关系置信度标签

**EXTRACTED / INFERRED / AMBIGUOUS 是关系的置信度标签，不是"构建模式"**：

| 标签 | 含义 | 置信度 |
|------|------|--------|
| `EXTRACTED` | 从源码/文档中直接发现 | 1.0 |
| `INFERRED` | 推理得出（AST 引用分析或 LLM 推断） | 0.0–1.0 |
| `AMBIGUOUS` | 不确定，标记待审查 | 需人工确认 |

文档 `v1.0` 将其误称为"INFERRED（纯静态）"和"EXTRACTED（LLM 驱动）"两种构建模式，这是不准确的。graphify 的实际工作方式是三阶段流水线，EXTRACTED/INFERRED 是**每条边的属性**，不是全局模式选择。

---

## 2. 集成可行性分析

### 2.1 graphify 能否作为后端抽取引擎？

| 评估维度 | 结论 | 说明 |
|----------|------|------|
| **Python API 可调用性** | **不可行** | graphify 是 CLI 技能插件，非 Python SDK。其 LLM 抽取依赖 Claude 子代理，无法从 FastAPI 后端直接调用 |
| **pip install 可用性** | 部分 | `pip install graphifyy` 可安装，但其核心功能依赖 Claude Code 运行时环境 |
| **AST 分析能力** | 有价值 | Pass 1 的 tree-sitter 静态分析是独立可用的，但仅适用于代码文件，不适用于知识库的文档场景 |
| **LLM 抽取能力** | 不可复用 | Pass 3 的 LLM 抽取硬编码使用 Claude 子代理，无法替换为 Kasaya 的 `LiteLLMProvider` |
| **MCP Server** | 可用 | `python -m graphify.serve` 可作为独立 MCP 服务运行，Agent 可通过 MCP 协议查询 |

### 2.2 三种集成路径

#### 路径 A：graphify MCP Server 直接对接（零开发量）

```
Agent 运行时
    ↓
MCP Client 连接 graphify MCP Server（stdio）
    ↓
Agent 通过 query_graph / get_neighbors / shortest_path 查询
    ↓
返回结构化结果
```

- **优势**：零开发量，立即可用
- **劣势**：不经过 Kasaya 管控（无审计、无权限控制、无持久化）；仅能查询 graphify 构建的固定图谱，无法按知识库隔离
- **适合**：开发者自测、POC 验证

#### 路径 B：graphify 输出导入（中等开发量）

```
离线：graphify CLI 构建图谱 → graph.json
    ↓
Kasaya 管理接口：上传 graph.json → 解析 nodes/edges
    ↓
写入 knowledge_entities / knowledge_relations 表
    ↓
Kasaya GraphRetriever 基于 PG 数据检索
```

- **优势**：利用 graphify 成熟的 AST 分析和 LLM 抽取；数据在 PG 中可控
- **劣势**：图谱构建仍在 Kasaya 外部；需要手动或半自动触发 graphify；`graph.json` 格式需适配
- **适合**：知识库内容为代码仓库或大型文档集的场景

#### 路径 C：自研 LLM 抽取引擎（完整开发量）

```
用户上传文档
    ↓
Kasaya Ingest Pipeline
├── 文件解析（PDF/DOCX/MD → 纯文本）
├── 分段（按章节/段落）
├── GraphExtractor（自研，基于 ModelProvider）
│   ├── 逐段调用 LLM 抽取实体 + 关系
│   └── 实体消歧 + 跨文档对齐
├── CommunityDetector（自研，igraph Leiden）
└── 写入 PostgreSQL 图谱表
```

- **优势**：完全可控；支持多 LLM 厂商；可按知识库隔离；支持增量构建
- **劣势**：开发量大（需自研抽取器、社区检测器、检索器）
- **适合**：生产级知识库场景

### 2.3 推荐策略

> **结论：以路径 C（自研）为主，路径 B（graphify 导入）为辅。**

理由：
1. graphify 的核心价值（AST 静态分析）不适用于知识库文档场景
2. graphify 的 LLM 抽取硬编码 Claude 子代理，无法复用 Kasaya 的多 LLM 厂商能力
3. 知识库需要按用户/组织隔离，graphify 无法满足
4. `knowledge-base-graph-design.md` 已设计完整的自研方案，路径 C 与之完全对齐

graphify 的价值在于**设计参考**：
- 置信度标签体系（EXTRACTED / INFERRED / AMBIGUOUS）
- 增量更新机制（SHA256 缓存 + diff 检测）
- 社区检测 + Wiki 摘要的输出格式
- MCP Server 的查询接口设计

---

## 3. 与已有方案的对齐

### 3.1 表名对齐

本文档 v1.0 中提出的 `kb_graph_nodes` / `kb_graph_edges` / `kb_graph_communities` **作废**，统一使用 `knowledge-base-graph-design.md` 第 2.2 节定义的：

- `knowledge_entities`（实体表）
- `knowledge_relations`（关系表）
- `knowledge_communities`（社区表）

### 3.2 技术选型对齐

| 组件 | 选型 | 来源 |
|------|------|------|
| 图存储 | PostgreSQL + 递归 CTE | `knowledge-base-graph-design.md` §8 |
| 社区检测 | python-igraph + Leiden | `knowledge-base-graph-design.md` §3.3 / §8 |
| LLM 抽取 | Kasaya ModelProvider（LiteLLM） | `knowledge-base-graph-design.md` §3.2 |
| Embedding（可选） | LiteLLMEmbeddingProvider | [embedding.py](../../kasaya-framework/kasaya/rag/embedding.py) |
| 图可视化 | ReactFlow | `knowledge-base-graph-design.md` §8 |

### 3.3 当前 Embedding 现状

当前 `knowledge_base.py` 服务使用 `InMemoryEmbeddingProvider`（SHA-256 hash 伪实现，`dimension=128`），这是**测试级代码**，不是生产实现。

Framework 已有 `LiteLLMEmbeddingProvider`（支持 OpenAI / 通义等多厂商），但后端知识库服务尚未接入。知识库 v2.0 图谱方案中，Embedding 是可选的 M2 阶段能力，不阻塞核心功能。

---

## 4. 社区检测质量分析

### 4.1 问题

本项目 graphify 输出的社区检测结果显示**全部 3,539 个社区的 Cohesion 均为 0.0**，表明社区检测质量极差。原因：

1. **graphify 对本项目构建使用的是纯 INFERRED 模式**（无 LLM 调用，Token 消耗为 0），仅基于 AST 引用分析
2. 大量 INFERRED 边的置信度仅为 0.5，引入大量噪声
3. 前端 node_modules 等第三方库被包含，产生了大量无关节点

### 4.2 对知识库方案的启示

知识库场景的社区检测需要注意：

- **输入质量**：LLM 抽取的实体/关系质量远高于 AST 引用分析，社区检测效果应更好
- **领域聚焦**：知识库内容是用户上传的领域文档，不包含第三方库代码，噪声更少
- **粒度控制**：需要 Leiden 算法的 resolution 参数可调，支持粗/细粒度社区
- **Fallback**：当社区 Cohesion 过低时，退化为按实体类型分组或按文档来源分组

---

## 5. LLM 抽取成本估算

### 5.1 模型选择

| 模型 | 输入价格/1M Token | 输出价格/1M Token | 推荐场景 |
|------|:-----------------:|:-----------------:|---------|
| Claude Sonnet 4 | $3 | $15 | 高质量抽取 |
| GPT-4o | $2.50 | $10 | 性价比平衡 |
| GPT-4o-mini | $0.15 | $0.60 | 大规模低成本 |
| DeepSeek V3 | ~$0.27 | ~$1.10 | 最低成本 |

### 5.2 成本估算（100 页技术文档）

假设：
- 100 页 ≈ 50,000 字 ≈ 25,000 Token（中文）
- 分 50 段抽取，每段 ~500 Token 输入 + ~300 Token 输出
- 总输入：~25,000 + 50 × 200（prompt）= 35,000 Token
- 总输出：50 × 300 = 15,000 Token

| 模型 | 单次构建成本 |
|------|------------|
| Claude Sonnet 4 | ~$0.33 |
| GPT-4o | ~$0.24 |
| GPT-4o-mini | ~$0.015 |
| DeepSeek V3 | ~$0.02 |

**结论**：100 页文档的单次图谱构建成本在 $0.02–$0.33 之间，可接受。成本随文档规模线性增长，可通过缓存已抽取段落控制增量成本。

---

## 6. 结论

### 6.1 核心结论

1. **graphify 不可直接作为后端抽取引擎集成**——它是 AI 编程助手技能插件，不是 Python SDK
2. **自研 LLM 抽取引擎是正确路径**——`knowledge-base-graph-design.md` 的方案设计完整可行
3. **graphify 的 MCP Server 可作为短期补充**——Agent 可直接查询 graphify 构建的全局代码图谱
4. **LLM 抽取成本可控**——100 页文档 $0.02–$0.33，增量构建更省
5. **社区检测需要 Fallback 策略**——当 Cohesion 过低时按实体类型/文档来源分组

### 6.2 对 knowledge-base-graph-design.md 的修订建议

1. **Phase 1（短期）**：增加 graphify MCP Server 作为预置 MCP 工具的选项
2. **Phase 2（中期）**：GraphExtractor 的抽取 prompt 应包含 Few-shot 示例 + JSON Schema 约束 + 实体消歧规则
3. **社区检测**：增加 Cohesion 阈值配置和 Fallback 策略
4. **成本控制**：增加已抽取段落缓存机制（SHA256 hash → 抽取结果）
