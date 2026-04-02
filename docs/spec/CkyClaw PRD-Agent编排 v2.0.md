# CkyClaw PRD-Agent 编排 v2.0

## 文档信息

| 字段 | 内容 |
|------|------|
| 版本 | v2.0.8 |
| 日期 | 2026-04-02 |
| 状态 | 进行中 |
| 维护人 | CkyClaw Team |
| 依赖 | CkyClaw PRD v2.0（总纲）、CkyClaw Framework Design v2.0 |

> 本文档是 CkyClaw PRD v2.0 的分册，包含第四章（Agent 执行模式）、第五章（工具系统与 MCP）、第六章（任务执行可视化）。

---

## 四、Agent 执行模式

### 4.1 概述

CkyClaw Framework 支持两种 Agent 编排模式：**Handoff（控制转移）

** 和 **Agent-as-Tool（嵌套调用）**。两种模式可独立使用或组合使用，由 LLM 或应用代码驱动编排决策。CkyClaw 不干预编排逻辑，负责配置管理、执行可视化和人工监督。

### 4.2 LLM 驱动编排 vs 代码驱动编排

| 编排方式 | 说明 | 适用场景 |
|---------|------|---------|
| **LLM 驱动** | Agent 自主决策：调用工具、Handoff、Agent-as-Tool，由 LLM 推理驱动 | 开放式任务，需要灵活决策 |
| **代码驱动** | 应用代码控制 Agent 执行顺序：链式调用、条件分支、并行执行 | 确定性流程，需要可预测性 |

### 4.3 Handoff 编排示例

```
用户消息: "我要退款"       │
▼┌──────────────────┐│   Triage Agent   │  分析用户意图│   (入口 Agent)    │└──────┬───────────┘
│ Handoff: transfer_to_refund_agent
▼┌──────────────────┐│   Refund Agent   │  接管对话，直接回复用户│   (专家 Agent)    │
│   - 查询订单      │
│   - 发起退款      │
│   - 回复结果      │└──────────────────┘

```

### 4.4 Agent-as-Tool 编排示例

```
用户消息: "帮我写一份 Q1 数据分析报告"       │
▼┌──────────────────────────────────────────────┐│            Research Manager Agent             │
│            (保持对话控制权)                     │
│
│
│
┌────────────────┐
┌────────────────────┐
│
│
│ call: Search   │
│ call: Data         │
│
│
│ Agent (as tool)│
│ Analysis Agent     │
│
│
│ → 搜索 Q1 数据 │
│ (as tool)          │
│
│
│ → 返回结果     │
│ → 分析数据趋势     │
│
│
└────────────────┘
│ → 返回分析结论     │
│
│
└────────────────────┘
│
│
│
│  汇总各 Agent 结果 → 生成完整报告 → 回复用户   │└──────────────────────────────────────────────┘

```

### 4.5 混合编排示例

```
用户消息  │
▼┌────────────────┐│  Triage Agent  │ ── Handoff ──► ┌───────────────────┐└────────────────┘
│ Support Specialist │
│     (Handoff 接管)  │
│                     │
│  ┌───────────────┐ │
│  │ Search Agent  │ │ ← Agent-as-Tool                                  │
│ (作为工具调用)  │ │
│  └───────────────┘ │
│                     │
│  汇总结果回复用户    │
└───────────────────┘

```

### 4.6 代码驱动编排模式当任务流程确定时，可通过代码驱动 Agent 执行顺序，支持以下模式：

| 模式 | 说明 | 适用场景 |
|------|------|---------|
| **链式调用** | Agent A → Agent B → Agent C 顺序执行 | ETL 流水线、文档处理 |
| **条件分支** | 根据分类 Agent 结果路由到不同专家 Agent | 客服分诊、意图路由 |
| **并行执行** | 多 Agent 并行 + 汇总 Agent 合并 | 多维度数据采集 |

> 代码驱动编排的完整示例（链式/条件/并行）见《CkyClaw Framework Design v2.0》第四章和第六章。

### 4.7 编排错误处理

| 场景 | 行为 |
|------|------|
| Agent 执行超过 max_turns | 触发 `on_max_turns_exceeded` 回调；默认抛出异常 |
| Handoff 目标 Agent 不存在 | Runner 抛出 `AgentError` |
| Agent-as-Tool 子 Agent 失败 | 将错误信息作为 tool_result 返回给 Manager Agent，由 LLM 决策 |
| Guardrail Tripwire 触发 | 立即中断执行，抛出对应异常 |
| LLM 调用失败 | 自动重试 2 次（指数退避）；仍失败则抛出 `ModelProviderError` |

### 4.8 CkyClaw Agent 配置管理

CkyClaw 提供声明式 Agent 管理界面：

| 能力 | 说明 |
|------|------|
| Agent CRUD | 创建/编辑/删除/查看 Agent 定义 |
| Instructions 编辑 | SOUL.md 编辑器，支持富文本和变量占位符 |
| 版本管理 | 每次保存自动创建版本快照，支持对比和回滚（详见 4.8.1） |
| Handoff 配置 | 可视化配置 Agent 间的 Handoff 关系 |
| Tool Group 选择 | 为 Agent 选择可用工具组 |
| 模板库 | 预置常用 Agent 模板（分诊、客服、数据分析等） |
| 审批模式 | 为 Agent 配置默认审批模式（suggest / auto-edit / full-auto） |

#### 4.8.1 Agent 版本管理与回滚

**版本模型：** 采用 **全量快照** 策略——每次 Agent 配置变更时自动创建包含完整 Agent 定义的版本快照。| 概念 | 说明 |
|------|------|
| AgentVersion | Agent 某一时刻的完整配置快照（JSON） |
| version_number | 自增版本号（1, 2, 3, ...） |
| published_version | 当前生效的版本（所有新 Run 使用此版本） |
| draft | 编辑中的草稿（尚未发布） |

**版本生命周期：**

```
创建 Agent → v1 (published)编辑保存   → v2 (draft)发布 v2    → v2 (published), v1 (archived)回滚到 v1  → v3 (published, 内容=v1 快照)

```
**快照内容（AgentVersion JSON）：**

| 字段 | 说明 |
|------|------|
| agent_name | Agent 名称 |
| version_number | 版本号 |
| instructions | SOUL.md 全文 |
| model | 模型标识 |
| model_settings | temperature、max_tokens 等 |
| tools | 工具组 ID 列表 |
| handoffs | Handoff 目标列表 |
| guardrails | 护栏配置 |
| approval_mode | 审批模式 |
| metadata | 自定义元数据（标签、描述等） |
| created_by | 版本创建者 |
| created_at | 创建时间 |
| change_description | 变更说明（可选） |**版本操作：**

| 操作 | 说明 |
|------|------|
| 对比（diff） | 任意两个版本间的字段级差异对比，Instructions 按行 diff |
| 回滚（rollback） | 将指定历史版本的完整内容作为新版本发布（不删除中间版本） |
| 标签（tag） | 为特定版本添加标签（如 `stable`、`production`、`experiment`） |
| 清理（prune） | 保留最近 N 个版本 + 所有有标签的版本，归档其余（默认 N=50） |

**与执行的关系：**- 所有 Run 记录关联 `agent_version_number`，用于回溯"这次执行用的是哪个版本的 Agent"。- 回滚不影响已完成的历史 Run，仅改变后续新 Run 的 Agent 配置。

### 4.9 Agent 配置示例（YAML 格式）

```
yamlname: data-analystdescription: "数据分析专家，擅长数据清洗、统计分析和可视化报告"model: gpt-4otool_groups:  - code-executor  - file-ops  - web-searchhandoffs:  - report-writerguardrails:  input: [content-safety]  output: [pii-filter]approval_mode: auto-editinstructions: |  你是一名专业的数据分析师...  （SOUL.md 内容）

```

### 4.10 定时与批量任务执行

CkyClaw 支持 Agent 的非交互式执行——定时触发和批量输入两种模式。

#### 4.10.1 定时任务（Scheduled Run）

| 需求 | 说明 |
|------|------|
| Cron 调度 | 支持 Cron 表达式配置执行周期（如 `0 9 * * *` = 每天 9:00） |
| 输入模板 | 支持固定输入或带日期变量的动态输入 |
| 完成通知 | 执行完成后通过邮件/Webhook/站内信通知 |
| 失败重试 | 可配置最大重试次数和间隔 |
| 审计追踪 | 所有定时执行纳入 Tracing 和 Token 审计（标记 `trigger_type=scheduled`） |
| 启停管理 | 支持启用/禁用/删除定时任务，受 RBAC 权限控制 |

#### 4.10.2 批量执行（Batch Run）对同一 Agent 批量提交多个输入，并行执行后汇总结果。

| 需求 | 说明 |
|------|------|
| 批量输入 | 支持上传 JSON/CSV 格式的输入列表 |
| 并行控制 | 可配置最大并行度（默认 5），防止 LLM API 限流 |
| 进度查询 | 提供实时进度（总数 / 完成 / 失败 / 进行中） |
| 单项回调 | 可选的 Webhook 通知单项完成 |
| 取消支持 | 支持取消整批或单项 |
| 结果汇总 | 所有执行关联同一 batch_id，便于整体查询和导出 |

> 数据模型（scheduled_runs / batch_runs 表）详见《CkyClaw 数据模型详细设计 v1.3》，API 接口详见《CkyClaw API Design v1.2》。**适用场景：**- "每天 9 点运行日报 Agent，生成各部门运营日报"（定时）。- "对 200 份简历逐一运行筛选 Agent"（批量）。- "每周一生成上周 Token 成本报告并邮件发送"（定时 + 通知）。

### 4.11 Agent Team 与 Coordinator 设计

#### 4.11.1 TeamConfig 配置模型Team 通过声明式 YAML 或 API 配置，主要参数：

| 参数 | 说明 |
|------|------|
| name / display_name | Team 唯一标识符 / 显示名称 |
| description | 描述（同时作为 Team-as-Tool 的 tool_description） |
| protocol | 协作协议：sequential / parallel / hierarchical / supervisor / debate / negotiated / round_robin / broadcast |
| members | 成员列表（Agent 引用 + 角色说明，debate 模式需指定 Judge） |
| termination | 终止条件：最大轮次、超时时间、共识阈值 |
| result_strategy | 结果聚合：last / concat / vote / judge / custom |
| context_sharing | 上下文共享：sequential（流水线传递） / shared / isolated |

> TeamConfig 完整数据类定义、YAML 示例和 TeamRunner 执行策略详见《CkyClaw Framework Design v2.0》4.5 节。

#### 4.11.2 内置 Team 模板

CkyClaw 应用层预置以下 Team 模板，用户可基于模板快速创建团队或直接使用：

| 内置 Team | 协议 | 成员组成 | 典型用途 |
|-----------|------|---------|---------|
| **research_report_team** | Sequential | Researcher → Analyst → Writer | 调研报告生成 |
| **code_review_team** | Parallel | Reviewer + Security Auditor + Test Reviewer | 代码审查（并行评审后汇总） |
| **decision_debate_team** | Debate | Advocate + Critic + Judge | 方案论证、采购决策 |
| **content_pipeline_team** | Sequential | Drafter → Editor → Fact-Checker | 内容创作流水线 |
| **translation_team** | Broadcast | EN Translator + JA Translator + KO Translator | 多语言翻译 |
| **brainstorm_team** | RoundRobin | Creative + Analyst + Strategist | 头脑风暴、创意迭代 |
| **project_decomposition_team** | Hierarchical | ProjectManager → [Backend Dev, Frontend Dev, QA] | 复杂项目任务分解与执行 |
| **dynamic_workflow_team** | Supervisor | Supervisor → [Researcher, Coder, Reviewer, Writer] | 不确定路径的复合任务 |
| **budget_planning_team** | Negotiated | Finance + Engineering + Marketing | 预算分配、资源协商 |

> 内置 Team 的成员 Agent 由平台预先注册，其 instructions 和 tools 均针对对应角色优化。用户可在 Web UI 中克隆并自定义。

#### 4.11.3 Coordinator Agent 模式

Coordinator 是一个顶层 Agent，其 `tools` 中包含多个 `team.as_tool()`。Coordinator 的 **instructions** 定义了"什么任务交给什么 Team"的路由策略。

```
用户请求 ──► Coordinator Agent                │
├── 需要调研? → tool_call(research_report_team, ...)
├── 需要评审? → tool_call(code_review_team, ...)
├── 需要决策? → tool_call(decision_debate_team, ...)
├── 简单问题? → 直接回复（不调用 Team）                │
▼
Coordinator 汇总 Team 结果后回复用户

```
**Coordinator 配置要点：** 使用小模型（降低路由 Token 开销），tools 中通过 `team::` 前缀引用 Team，instructions 中明确路由规则。

> Coordinator YAML 配置示例详见《CkyClaw Framework Design v2.0》4.5 节。

#### 4.11.4 Team 管理功能

| 功能 | 说明 | MVP 阶段 |
|------|------|---------|
| 模板浏览 | 在 Web UI 中浏览内置 Team 模板，查看成员组成和协议 | v1.0 |
| 从模板创建 | 基于内置模板克隆，调整成员 Agent 和参数 | v1.0 |
| 自定义 Team | 从零创建 Team（选择成员 Agent、协议、终止条件） | v1.0 |
| Team 测试 | Playground 中测试 Team 执行效果 | v1.0 |
| Coordinator 配置 | 为 Coordinator Agent 绑定 Team-as-Tool | v1.0 |
| Team 版本管理 | Team 配置纳入 Agent 版本管理体系（参见 4.8.1） | v1.1 |
| Team 共享 | 在组织内发布和共享 Team 模板 | v1.2 |
| 执行监控 | APM 中查看 Team 执行的 Trace（含成员 Agent 子 Span） | v1.0 |

#### 4.11.5 Team TracingTeam 执行在 Tracing 中产生层级化的 Span 结构：

```
Team Span [research_report_team]├── Agent Span [researcher]│
├── LLM Span│
└── Tool Span [web_search]├── Agent Span [data_analyst]│
├── LLM Span│
└── Tool Span [sql_query]└── Agent Span [report_writer]
└── LLM Span

```
- Debate 协议会按 Round 嵌套：`Team Span → Round 1 Span → [Agent A Span, Agent B Span, Judge Span] → Round 2 Span → ...`- Token 消耗按 Team 级别聚合，同时保留各成员 Agent 的明细。- Team Span 的 `attributes` 中记录协议类型、成员列表、轮次数、最终结果策略。

#### 4.11.6 协作协议详解

CkyClaw 支持 8 种协作协议，覆盖主流多 Agent 协作范式：

| 协议 | 执行模型 | 数据流 | 典型场景 | 关键参数 |
|------|---------|--------|---------|---------|
| **sequential** | 成员按声明顺序依次执行，前一个 Agent 的输出作为后一个的输入 | 线性管道（A → B → C） | 流水线式任务（调研→分析→撰写） | — |
| **parallel** | 所有成员同时并发执行同一输入，执行完毕后通过 result_strategy 聚合 | 扇出 → 聚合 | 代码审查（多角度并行评审）、多语言翻译 | max_concurrency |
| **hierarchical** | 根 Agent 将任务分解为子任务并分配给成员 Agent；成员可进一步递归分配给子成员 Agent | 树形分解与汇聚 | 复杂项目管理（多层级分工）、大规模数据处理 | max_depth, delegation_strategy |
| **supervisor** | Supervisor Agent 动态决定每一步由哪个 Worker Agent 执行，根据上一步结果选择下一步 Worker | Supervisor 环路（Supervisor → Worker_i → Supervisor → Worker_j → ...） | 需要动态路由的复杂任务、不确定执行路径的工作流 | max_iterations, routing_instructions |
| **debate** | 正方与反方 Agent 交替论证，Judge Agent 在每轮后评估是否达成结论 | 对抗式循环（A ↔ B，Judge 裁决） | 方案论证、风险评估、采购决策 | max_rounds, judge_criteria |
| **negotiated** | 所有成员 Agent 各自提出方案，通过投票或迭代修正达成共识 | 广播 → 投票/修正循环 | 需要多方共识的决策（预算分配、优先级排序） | consensus_threshold, max_negotiation_rounds |
| **round_robin** | 成员按顺序循环发言，每轮所有成员可看到之前所有发言，直到终止条件满足 | 循环传递 | 头脑风暴、创意迭代 | max_rounds |
| **broadcast** | 同一输入广播给所有成员，各自独立执行，结果不汇聚（各自输出） | 扇出（不聚合） | 多语言翻译（各语言独立输出）、多渠道通知 | — |

**hierarchical 与 supervisor 的区别：**
- **hierarchical**：任务分解在开始时静态规划，形成完整的子任务树后并行/串行执行，适合结构化、可预知路径的任务。
- **supervisor**：每一步动态决策，Supervisor 根据当前状态实时选择下一个 Worker，适合探索性、不确定路径的任务。

**debate 与 negotiated 的区别：**
- **debate**：对抗式结构，正反双方辩论 + 独立 Judge 裁决，适合有明确对立观点的场景。
- **negotiated**：协商式结构，所有参与方平等提案并迭代修正，通过共识阈值（如 >75% 赞同）终止，适合需要多方妥协的场景。

### 4.12 内置 Agent、工具与 Skill 清单

CkyClaw 平台出厂即包含一组经过调优的 **内置 Agent 模板**、**Hosted Tool（内置工具组）** 和 **内置 Skill 包**，让用户开箱可用。

#### 4.12.1 内置 Agent 模板用户可在 Web UI 中基于模板一键创建 Agent，也可从零开始自定义。

| 模板名称 | 用途 | Instructions 要点 | 默认工具组 | 默认 Handoff |
|---------|------|-------------------|-----------|-------------|
| **Triage（分诊）** | 意图识别 + 路由 | 识别用户意图分类，选择最合适的专家 Agent 转交 | — | ✅ 可配 |
| **FAQ Bot** | 常见问题解答 | 基于知识库/Skill 文档回答常见问题 | — | — |
| **Researcher** | 网络调研 | 使用搜索工具收集信息，按结构化模板输出 | web-search | — |
| **Data Analyst** | 数据分析 | 编写并执行 SQL/Python 代码处理数据 | code-executor | — |
| **Report Writer** | 报告撰写 | 将分析结果整理为结构化报告（Markdown/PDF） | file-ops | — |
| **Code Assistant** | 代码辅助 | 编写、审阅、解释代码，支持多种编程语言 | code-executor | — |
| **Translator** | 多语言翻译 | 准确翻译并保持语境和专业术语 | — | — |
| **Customer Service** | 客服助手 | 回答产品问题、处理退款/订单查询 | http | ✅ 可配 |
| **Summarizer** | 文本摘要 | 对长文本提取关键信息，输出精炼摘要 | — | — |
| **Coordinator** | 总协调员 | 根据任务类型选择合适的 Team 或 Agent 调用 | team::* | — |

> 模板提供默认 instructions 和工具配置，用户创建时可任意修改。模板不影响已创建的 Agent。

#### 4.12.2 内置工具组（Hosted Tool Groups）

| 工具组 ID | 包含能力 | 说明 |
|-----------|---------|------|
| **web-search** | 搜索 + 页面抓取 | 网络搜索返回结果摘要、抓取指定 URL 内容 |
| **code-executor** | Python + Shell 执行 | 在 Sandbox 中执行代码（详见 5.5） |
| **file-ops** | 读 / 写 / 目录列表 | 文件读写和目录浏览 |
| **http** | HTTP 请求 | 发送 GET/POST/PUT/DELETE 请求 |
| **database** | SQL 查询 | 只读 SQL 查询（带超时和行数限制） |

> 各工具组的函数签名和 JSON Schema 详见《CkyClaw Framework Design v2.0》第八章。开发者可通过 `@function_tool` 注册自定义工具或通过 MCP Server 接入外部工具。

#### 4.12.3 内置 Skill 包

| Skill 名称 | 适用 Agent | 内容概要 |
|------------|-----------|---------|
| **customer-service-handbook** | Customer Service, FAQ Bot | 客服标准话术、退款政策流程、常见问题库 |
| **data-analysis** | Data Analyst, Report Writer | SQL 查询优化提示、图表类型选择建议、统计方法指南 |
| **code-review** | Code Assistant | 代码审查检查清单、常见安全漏洞模式、性能反模式 |
| **research-methodology** | Researcher | 信息源可信度评估、调研报告模板、引用格式规范 |
| **writing-style-guide** | Report Writer, Translator | 技术写作风格指南、术语表、格式模板 |
| **compliance-rules** | 所有 Agent | 组织合规规则（敏感词、信息分级、外发审查标准） |

> Skill 包以 `.skill` 归档包分发（结构详见 2.7）。内置 Skill 随平台安装，也可通过 Skill Registry 获取社区贡献的 Skill。

#### 4.12.4 Agent × Tool × Skill 推荐矩阵

| Agent 模板 | 推荐工具组 | 推荐 Skill | 典型场景 |
|-----------|-----------|-----------|---------|
| Triage | — | compliance-rules | 意图路由、多 Agent 分诊 |
| Researcher | web-search | research-methodology | 市场调研、竞品分析 |
| Data Analyst | code-executor, database | data-analysis | 数据清洗、统计分析 |
| Report Writer | file-ops | writing-style-guide, data-analysis | 周报/研究报告生成 |
| Code Assistant | code-executor | code-review | 代码生成/审查/解释 |
| Customer Service | http | customer-service-handbook | 客服工单处理 |
| Coordinator | team::* | — | 复杂任务分解与 Team 调度 |

### 4.13 配置热更新与 Agent 国际化

#### 4.13.1 配置热更新系统应支持在不重启服务的情况下动态变更以下配置，变更即时生效：

| 可热更新配置项 | 说明 | 生效范围 |
|---------------|------|---------|
| Agent Instructions | 修改 Instructions 后新 Run 立即使用新版本 | 新创建的 Run |
| Model 绑定 | 切换 Agent 使用的模型（如 gpt-4o → claude-sonnet） | 新创建的 Run |
| Tool Group 成员 | 增删工具组中的工具 | 新创建的 Run |
| Guardrail 规则 | 新增/修改/禁用安全护栏规则 | 下一次护栏检查 |
| 系统限流参数 | 调整 Token 限额、并发数限制 | 即时 |
| 功能开关 | 开关特定功能（如 Sandbox、Approval Mode） | 即时 |

**产品要求：**- 已运行中的 Run 不受配置变更影响，保证执行一致性- 所有配置变更记录审计日志（操作人、变更前后值、时间）- 管理后台提供配置变更历史查看页面- 支持配置变更回滚（基于审计日志恢复至指定时间点的配置）

#### 4.13.2 Agent 国际化（i18n）系统应支持多语言环境下的 Agent 运行与管理：

| 能力 | 说明 |
|------|------|
| **多语言 Instructions** | 每个 Agent 可维护多个语言版本的 Instructions，按用户语言偏好/请求中的 `locale` 字段自动选择 |
| **响应语言检测** | Agent 响应时可根据用户输入语言自动匹配回复语言（通过 Instructions 指令完成，非硬编码） |
| **平台 UI 多语言** | 管理后台 UI 支持中文/英文切换（前端 i18n 方案） |
| **Agent 描述多语言** | Agent 的 display_name、description 支持多语言版本，按当前 locale 展示 |
| **日期/数字格式** | 前端展示层按用户 locale 格式化日期、数字、货币等 |

**MVP 范围：** 平台 UI 中英文双语 + Instructions 按用户语言手动切换版本。自动语言检测和 locale 路由为 Post-MVP。

---

## 五、工具系统与 MCP

### 5.1 Function Calling 概述

Function Calling 是 LLM 与外部工具交互的标准机制。CkyClaw Framework 通过 Function Tool 装饰器注册工具函数，自动生成 JSON Schema 供 LLM 调用。**工具注册流程：** 开发者用 `@function_tool` 装饰器标注 Python 函数 → 框架自动从签名和 docstring 生成 JSON Schema → 工具注册到 ToolRegistry → Runner 将 Agent 可用工具的 Schema 附带给 LLM → LLM 返回 tool_calls 后 Runner 执行对应函数。

> 工具注册示例代码、ToolRegistry API 和 JSON Schema 生成细节详见《CkyClaw Framework Design v2.0》第八章。

### 5.2 工具组（Tool Groups）工具按功能分组管理，Agent 可按组批量加载：

| 工具组 | 说明 |
|--------|------|
| web-search | 网络搜索 |
| code-executor | 代码执行（在 Sandbox 中） |
| file-ops | 文件操作 |
| http | HTTP 请求 |

自定义工具接入：将 Python 函数注册为 Function Tool 并归入指定 Tool Group，或通过 MCP Server 暴露工具。

### 5.3 MCP 协议MCP（Model Context Protocol）

是标准化工具服务协议。CkyClaw Framework 原生支持 MCP 集成：| 传输类型 | 说明 | 适用场景 |
|---------|------|---------|
| stdio | 通过子进程标准输入/输出通信 | 本地 MCP Server |
| SSE | Server-Sent Events 长连接 | 远程 MCP Server |
| HTTP | 标准 HTTP 请求/响应 | RESTful 远程服务 |

MCP 安全：对 HTTP/SSE 类型支持 OAuth 令牌流（client_credentials / refresh_token）；stdio 类型支持环境变量注入凭证。**MCP 工具发现流程：**

```
1. CkyClaw 后台配置 MCP Server 连接信息（URL/命令 + 认证方式）2. CkyClaw Framework MCPServer 建立连接（stdio 启动子进程 / HTTP 握手）3. 调用 MCP list_tools 获取可用工具列表和 JSON Schema4. 工具注册到 ToolRegistry，归入 Agent 的 mcp_servers5. Agent 运行时，MCP 工具与 Function Tool 统一作为 tools 传递给 LLM6. LLM 调用 MCP 工具 → CkyClaw Framework 通过 MCP 协议转发请求 → 返回结果

```

### 5.4 Tool Guardrails工具级护栏在每次工具调用时执行：

| 类型 | 说明 |
|------|------|
| Input Tool Guardrail | 调用前验证参数（如检测敏感数据、阻止危险操作） |
| Output Tool Guardrail | 调用后验证返回值（如过滤敏感信息） |

### 5.5 Sandbox 执行环境代码执行工具在隔离的 Sandbox 中运行：

| 模式 | 说明 | 适用场景 |
|------|------|---------|
| Local | 直接在宿主机执行 | 开发测试 |
| Docker | 在 Docker 容器中执行 | 生产环境 |
| Kubernetes | 在 K8s Pod 中执行 | 大规模生产 |

### 5.6 工具命名空间（Tool Namespace）

当 Agent 同时使用来自多个 MCP Server、多个 Skill、本地 Function Tool 的工具时，工具名称可能冲突。CkyClaw Framework 通过命名空间自动隔离：**命名空间自动分配规则：**

| 来源 | 前缀规则 | 示例 |
|------|---------|------|
| MCP Server | `{server_name}::` | `github::create_issue` |
| Skill 注入 | `{skill_name}::` | `data_analysis::run_query` |
| 内置 Function Tool | 无前缀 | `search_web` |
| 自定义 Function Tool | 可选指定 `namespace` 参数 | `ops::restart_service` |

**LLM 交互：** 工具名称含命名空间前缀一起传入 LLM，使 LLM 能够识别同名但不同来源的工具。

### 5.7 延迟工具加载（Deferred Tool Loading）

当 Agent 配置的可用工具数量较多时，将所有工具的 JSON Schema 注入 Prompt 会消耗大量 Token 并降低 LLM 的工具选择精度。CkyClaw Framework 实现 **ToolSearchTool** 模式来解决此问题：**工作流程：**

```
1. Agent 配置了 50 个工具，超过 deferred_threshold（默认 20）2. Runner 不将全部 50 个工具 Schema 注入 Prompt3. 改为注入一个 search_tools(query: str) 元工具4. LLM 根据用户请求，调用 search_tools("数据库查询") 5. ToolSearchTool 在全局 ToolRegistry 中语义搜索，返回 Top-K 匹配工具的名称+描述6. Runner 将匹配的工具 Schema 动态注入到下一轮 Prompt7. LLM 使用具体工具完成任务

```
**配置项：**

| 配置 | 说明 | 默认值 |
|------|------|--------|
| `deferred_threshold` | 触发延迟加载的工具数量阈值 | 20 |
| `search_top_k` | 每次搜索返回的最大工具数 | 5 |
| `search_strategy` | 搜索策略（keyword / semantic / hybrid） | hybrid |

### 5.8 工具错误处理与超时

工具调用是 Agent 系统中最常见的异常来源。CkyClaw Framework 采用"容错而非终止"策略：**默认行为：** 工具执行异常不会终止 Run，而是将错误信息作为工具结果返回给 LLM，由 LLM 决定重试、换用其他工具或通知用户。| 错误场景 | 处理方式 |
|---------|---------|
| 函数异常 | 捕获异常，返回错误消息给 LLM |
| 超时 | 终止工具执行，返回超时提示给 LLM |
| MCP Server 断连 | 返回连接失败提示，LLM 可选择其他工具 |
| Tool Guardrail 拦截 | 返回拦截原因给 LLM（非 Tripwire 场景） |

开发者可通过 `failure_error_function` 参数自定义错误消息格式，控制 LLM 收到的错误提示内容。

> 工具错误处理的完整配置项和示例代码详见《CkyClaw Framework Design v2.0》第八章。

---

## 六、任务执行可视化

### 6.1 概述任务执行可视化是 CkyClaw 的核心功能，基

于 CkyClaw Framework Tracing 数据，以流程图形式实时展示 Agent 编排与执行过程。用户可以直观查看 Agent 间的 Handoff/调用关系、各节点的执行状态和日志，并对执行进行管理。

### 6.2 执行图结构每次 Run 的 Trace 数据被解析为一个有向图，包含以下节点类型：

| 节点类型 | 说明 | 展示信息 |
|---------|------|---------|
| **Agent** | Agent 执行节点 | Agent 名称、思考过程、决策内容、耗时 |
| **Handoff** | 控制转移节点 | 源 Agent → 目标 Agent、携带的元数据 |
| **Tool Call** | 工具调用节点 | 工具名称、参数、返回值、耗时 |
| **LLM Call** | 模型推理节点 | 模型名称、Token 消耗、耗时 |
| **User Message** | 用户输入节点 | 原始消息内容 |
| **Agent Response** | Agent 回复节点 | 最终回复内容 |

**执行图示例（Handoff + Agent-as-Tool 混合）：**

```
┌──────────────┐│ User Message │
│ "分析Q1数据"  │└──────┬───────┘
▼┌──────────────┐         Handoff│ Triage Agent │ ──────────────────► ┌──────────────────┐│  ✅ 完成     │
│ Data Analyst Agent│
│  0.8s        │
│  🔄 执行中        │└──────────────┘
│                   │
│  ┌─────────────┐ │
│  │ Tool: query  │ │
│  │ ✅ OK  2.1s  │ │
│  └─────────────┘ │
│                   │
│  ┌─────────────┐ │
│  │ Chart Agent  │ │ ← as_tool                                     │
│ ✅ OK  3.2s  │ │
│  └─────────────┘ │
│                   │
│  汇总 → 回复      │
└──────────────────┘

```

### 6.3 实时状态展示执行图中每个节点实时显示以下信息：

| 信息项 | 说明 |
|--------|------|
| 执行状态 | pending / running / completed / failed / cancelled |
| 耗时 | 已用时间，执行中节点实时更新 |
| Token 消耗 | LLM 调用的 Token 数量 |
| 输入/输出 | 点击节点展开查看详细输入参数和输出结果 |
| 日志 | 节点执行的详细日志（推理链、工具返回值、错误信息） |

### 6.4 执行状态管理

| 操作 | 说明 | 适用状态 |
|------|------|---------|
| **取消** | 终止当前 Run 执行 | running |
| **暂停** | 暂停执行（通过监督机制实现） | running |
| **恢复** | 恢复暂停的执行 | interrupted |
| **重试** | 对失败的 Run 重新执行 | failed |

### 6.5 执行历史

| 功能 | 说明 |
|------|------|
| 执行列表 | 按时间倒序展示所有 Run 记录，支持按 Agent、状态、时间范围筛选 |
| 详情回放 | 点击任意历史 Run，以执行图形式回放完整执行过程 |
| 日志查看 | 展开任意节点查看详细日志和输入/输出数据 |
| 导出 | 导出执行记录和日志用于审计 |

### 6.6 数据来源执行可视化的数据来源于 CkyClaw Framework Tracing 系统：

| 数据源 | 可视化用途 |
|--------|-----------|
| Agent Span | 渲染 Agent 节点及其思考过程 |
| Handoff Span | 渲染 Agent 间控制转移边 |
| Tool Span | 渲染工具调用节点 |
| LLM Span | 渲染模型推理节点，提取 Token 消耗 |
| Streaming Events | 实时更新执行图节点状态 |

CkyClaw 后端注册自定义 Trace Processor，将 Tracing 事件实时推送到前端渲染执行图。

---


---

*文档版本：v2.0.8*
*最后更新：2026-04-02*
*作者：CkyClaw Team*
