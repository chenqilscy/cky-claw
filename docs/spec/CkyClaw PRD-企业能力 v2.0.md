# CkyClaw PRD-企业能力 v2.0

## 文档信息

| 字段 | 内容 |
|------|------|
| 版本 | v2.0.8 |
| 日期 | 2026-04-02 |
| 状态 | 进行中 |
| 维护人 | CkyClaw Team |
| 依赖 | CkyClaw PRD v2.0（总纲）、CkyClaw Framework Design v2.0、CkyClaw 应用层技术设计方案 v1.2 |

> 本文档是 CkyClaw PRD v2.0 的分册，包含第七章（IM 渠道接入）、第八章（人工监督机制）、第九章（APM 与可观测性）、第十章（前端与用户界面）。

---

## 七、IM 渠道接入

### 7.1 概述

CkyClaw 支持多渠道接入，用户可通过 IM 应用、Web 端等多种方式与 Agent 交互。渠道层通过统一消息总线（MessageBus）连接 CkyClaw Framework 的 Runner 执行引擎。

### 7.2 渠道架构

```
┌─────────────────────────────────────────────────────────────────────┐│                       IM Channel Architecture                        │
│
│
│
┌──────────┐
┌──────────┐
┌──────────┐
┌──────────┐
│
│
│ Telegram │
│  Slack   │
│ 飞书/Lark │
│  自定义   │
│
│
└────┬─────┘
└────┬─────┘
└────┬─────┘
└────┬─────┘
│
│
└──────────────┴──────────────┴──────────────┘
│
│
│                                       │
│
┌───────▼──────┐
│
│
│  MessageBus  │
│
│
└───────┬──────┘
│
│
│                                       │
│
┌───────▼──────────┐
│
│
│ ChannelManager   │
│
│
└───────┬──────────┘
│
│
│                                       │
│
┌──────────┴──────────┐
│
│
▼
▼
│
│           CkyClaw Framework Session       CkyClaw Framework Runner                    │└─────────────────────────────────────────────────────────────────────┘

```

### 7.3 首期实现渠道（P0）

| 渠道 | 传输方式 | 流式输出 | 说明 |
|------|---------|---------|------|
| **Web 端** | REST + SSE | 是 | CkyClaw 前端对话界面，支持流式输出和文件上传 |
| **Telegram** | Bot API（长轮询） | 否 | 个人/群组对话 |

### 7.4 后续扩展渠道

| 渠道 | 优先级 | 说明 |
|------|--------|------|
| Slack | P1 | Socket Mode |
| 飞书/Lark | P1 | WebSocket |
| 企业微信 | P1 | 回调接口 |
| 钉钉 | P1 | 回调接口 |
| API 直接接入 | P0 | 第三方系统通过 REST + SSE 调用 |

### 7.5 消息生命周期

用户发送消息 → Channel 接收封装 → MessageBus 路由 → 加载 Session 历史 → Runner 创建 Run → Agent 处理（可能涉及 Handoff/Tool 调用）→ 回复消息 → Session 持久化 → Channel 发送给用户

### 7.6 会话映射

| IM 端概念 | CkyClaw Framework 映射 |
|----------|-------------|
| chat_id（群/私聊） | Session |
| user_id | Run Context metadata |
| InboundMessage | 用户输入 → Runner.run() |

> Channel Adapter 接口定义、MessageBus（Redis Streams）架构、Session 映射规则、渠道格式转换、分段推送策略、用户绑定流程等技术细节详见《CkyClaw 应用层技术设计方案 v1.2》第一章。

---

## 八、人工监督机制

### 8.1 概述

CkyClaw 提供全程人工监督能力，与 CkyClaw Framework 的 Approval Mode 和 Guardrails 机制配合，确保 AI Agent 的行为安全可控。人类操作员可以随时观察任何 Agent 对话，实时干预或修正 Agent 行为。

### 8.2 监督模式

| 模式 | 说明 | 适用场景 |
|------|------|---------|
| **观察模式** | 只读查看 Agent 实时对话，不影响执行 | 日常监控、质量审查 |
| **干预模式** | 暂停 Agent 执行，人工修改/补充指令后恢复 | 关键决策、异常处理 |
| **接管模式** | 完全替代 Agent，由人工直接回复用户 | 紧急情况、Agent 无法处理 |
| **审批模式** | Agent 输出/工具调用需人工审批后才执行 | 高风险操作、敏感内容 |

### 8.3 与 CkyClaw Framework 机制集成

| CkyClaw 监督能力 | CkyClaw Framework 底层机制 |
|-----------------|-----------------|
| 审批工作流 | Approval Mode（suggest / auto-edit / full-auto） |
| 工具调用拦截 | Tool Guardrails + Approval 拦截 |
| 输出审核 | Output Guardrails + Tripwire |
| 暂停/恢复 | RunState 序列化 + 恢复执行 |
| 实时监控 | Tracing Streaming Events |

### 8.4 实时对话监控监督面板可实时展示以下内容：

| 内容 | 说明 |
|------|------|
| 用户输入 | 用户发送的原始消息 |
| Agent 思考过程 | LLM 推理链 |
| 工具调用 | 调用的工具、参数、返回结果 |
| Handoff 事件 | Agent 间的控制转移 |
| Agent 输出 | 最终回复内容 |
| Token 消耗 | 实时 Token 使用量 |
| 执行耗时 | 各步骤耗时 |

### 8.5 人工干预能力

#### 8.5.1 暂停与

恢复监督员可随时暂停正在执行的 Agent。CkyClaw Framework 将当前 RunState 序列化保存（含消息历史、待执行节点）。监督员修改或补充指令后恢复执行，Agent 从保存的状态继续。**RunState 序列化内容：**

| 状态数据 | 说明 |
|---------|------|
| 消息历史 | 截至暂停时刻的完整消息列表 |
| 当前 Agent | 当前执行的 Agent 名称（可能已经 Handoff） |
| 执行轮次 | 当前 turn_count（用于 max_turns 计算） |
| 待执行操作 | 暂停时正在等待的操作（工具调用/LLM 响应） |
| Trace 快照 | 已产生的 Span 列表 |
| Context 数据 | RunContext 中的自定义数据 |

暂停后状态持久化到 PostgreSQL，恢复时 Runner 从序列化状态重建执行上下文继续运行。

#### 8.5.2 消息注入

| 注入类型 | 说明 |
|---------|------|
| 系统指令 | 给 Agent 追加系统级约束 |
| 补充信息 | 提供 Agent 缺少的上下文 |
| 结果覆盖 | 替换 Agent 的最后输出 |
| 工具结果修正 | 修改工具调用的返回值 |

#### 8.5.3 接管

监督员可完全接管会话，取消当前 Agent 执行，直接回复用户。操作完成后可交还控制权，恢复 Agent 自动处理。

### 8.6 审批工作流审批工作流基于 CkyClaw Framework Approval Mode 扩展，可配置审批规则：

| 触发条件 | 说明 |
|---------|------|
| 特定工具调用 | 高风险工具（如数据库写入、外部 API）需审批 |
| 输出包含敏感关键词 | Agent 回复命中关键词时需审批 |
| 成本超过阈值 | 单次执行成本超标时需审批 |
| Guardrail Tripwire | 护栏检测到异常时触发审批 |

**审批流程详细时序：**

```
1. Runner 执行中遇到需审批的操作
├── suggest 模式：所有工具调用/输出均触发
├── auto-edit 模式：仅高风险操作触发（由 SupervisionRule 定义）
└── full-auto 模式：不触发（除非 Guardrail Tripwire）2. CkyClaw Framework 调用 ApprovalHandler.request_approval()3. CkyClaw ApprovalHandler 实现：     a. 创建 ApprovalRequest 记录（状态 = pending）     b. WebSocket 推送到监督面板审批队列     c. 同时发送通知（站内 + 邮件/Webhook）给匹配角色的审批人     d. Runner 执行挂起，等待审批结果4. 审批人操作：
├── 批准 → ApprovalRequest 状态 = approved → Runner 继续执行
├── 拒绝 → ApprovalRequest 状态 = rejected → Runner 终止或修改后重试
└── 超时 → 触发 timeout_policy（可配置：拒绝 / 通过 / 升级到上级审批人）5. 审批结果记录到 AuditLog

```
**审批规则配置：**

| 配置项 | 说明 |
|--------|------|
| 匹配条件 | Agent 名称 / 工具名称 / 关键词正则 / Guardrail 类型 |
| 审批人角色 | 指定可审批的角色列表 |
| 超时时间 | 默认 300 秒 |
| 超时策略 | reject（拒绝）/ approve（自动通过）/ escalate（升级） |
| 作用域 | 全局 / 组织级 / Agent 级 |

审批支持配置审批人角色、超时时间和超时策略（拒绝/通过/升级）。

### 8.7 监督面板功能

| 功能 | 说明 |
|------|------|
| 活跃会话列表 | 实时显示所有正在执行的会话 |
| 对话实时流 | Agent 对话实时内容推送 |
| Agent 状态总览 | 运行状态、错误率、Token 消耗 |
| 干预操作台 | 暂停/恢复/接管/注入消息操作 |
| 审批队列 | 待审批的 Agent 输出和工具调用 |
| 历史回放 | 回放任意会话的完整交互历史 |
| 告警通知 | 异常行为、成本超标等实时告警 |

### 8.8 监督权限

| 角色 | 观察 | 干预 | 接管 | 审批 | 配置规则 |
|------|------|------|------|------|---------|
| Admin | ✅ | ✅ | ✅ | ✅ | ✅ |
| Operator | ✅ | ✅ | ✅ | ✅ | ❌ |
| Developer | ✅ | ✅ | ❌ | ❌ | ❌ |
| Viewer | ✅ | ❌ | ❌ | ❌ | ❌ |---

## 九、APM 与可观测性

### 9.1 Tracing 驱动的可观测性

CkyClaw 的 APM 体系基于 CkyClaw Framework 内建的 Tracing 系统。每次 Agent 执行自动产生 Trace，包含完整的 Span 层级结构：

```
Trace (workflow_name, trace_id, group_id)├── Agent Span (triage-agent)│
├── LLM Span (gpt-4o, tokens: 1200)│
└── Handoff Span → data-analyst├── Agent Span (data-analyst)│
├── LLM Span (gpt-4o, tokens: 800)│
├── Tool Span (query_database, 2.1s)│
├── Agent-as-Tool Span (chart-agent)│
│
├── LLM Span (gpt-4o-mini, tokens: 400)│
│
└── Tool Span (generate_chart, 1.5s)│
└── LLM Span (gpt-4o, tokens: 600)└── Total: 3000 tokens, 8.2s

```

#### 9.1.1 Tracing 数据导出方案

CkyClaw Framework 的 `TraceProcessor` 接口支持多种导出目标。CkyClaw 应用层采用 **OTel 主路径 + 可选增强** 架构：| 导出目标 | 定位 | 用途 | 方式 |
|---------|------|------|------|
| **PostgreSQL** | **默认（MVP）** | Token 审计写入 `token_usage_log` 表，Span 写入 `spans` 表 | `PostgresTraceProcessor` 直写 |
| **OTel Collector** | **推荐（生产）** | 分布式追踪、指标采集、对接企业可观测性平台 | `OTelTraceProcessor` 通过 OTLP 导出 |
| **ClickHouse** | **可选（大规模）** | 海量 Trace 分析、高并发多维聚合（日均 > 100 万 Span 场景） | `ClickHouseTraceProcessor` 直写 |**推荐生产部署组合：** PostgresTraceProcessor（Token 审计）+ OTelTraceProcessor（Trace/Metrics）→ OTel Collector → Jaeger/Tempo + Prometheus + Grafana。**OpenTelemetry 集成策略（兼容而非依赖）：**CkyClaw Framework 内部 Tracing 使用自研轻量 API（`Trace` / `Span` / `TraceProcessor`），**不依赖** OTel Python SDK。原因：| 因素 | 决策理由 |
|------|---------|
| Agent 语义 | Agent/Handoff/Guardrail 等 Span 类型无 OTel 标准语义约定 |
| 性能 | 自研 Span 创建开销 < 0.1ms，OTel SDK 约 5-10ms/Span |
| Token 审计 | 需要从 LLM Span 实时提取 token_usage 进行聚合，自研流水线可精准控制 |
| 灵活性 | 自研接口可自由扩展字段（如 approval_status、handoff_target） |

但通过 `OTelTraceProcessor` 提供**协议兼容**：- CkyClaw Span → 转换为 OTel Span（W3C trace_id / span_id 格式）- 通过 OTLP gRPC/HTTP 推送到 OTel Collector- Collector 再分发到 Jaeger、Grafana Tempo 等后端存储- Collector 通过 Prometheus Remote Write 导出指标- Grafana 统一仪表盘查询 Jaeger/Tempo + Prometheus 数据源

```
CkyClaw Framework Tracing (自研 API)        │
├──► PostgresTraceProcessor → PostgreSQL（Token 审计 + MVP Span 存储）        │
├──► OTelTraceProcessor → OTLP → OTel Collector（推荐生产路径）        │
├──► Jaeger / Tempo（分布式追踪）        │
├──► Prometheus（Metrics）        │
└──► Grafana（统一仪表盘）        │
└──► ClickHouseTraceProcessor → ClickHouse（可选：大规模分析场景）

```

### 9.2 核心监控指标

#### 9.2.1 任务指标

| 指标 | 说明 | 告警阈值 |
|------|------|---------|
| 任务总数/活跃数 | 运行中的 Run 数量 | 活跃 > 100 |
| 任务执行耗时 | 端到端执行时间（Trace Duration） | p95 > 5min |
| 任务成功率 | 成功/总数 | < 95% |
| 超时/失败数 | 异常任务计数 | > 10/min |

#### 9.2.2 Agent 指标

| 指标 | 说明 | 告警阈值 |
|------|------|---------|
| 调用次数/活跃数 | Agent 使用频率 | - |
| 响应时间 | Agent Span Duration | p95 > 3s |
| 错误率 | 失败 Span / 总 Span | > 5% |
| Token 消耗 | LLM Span 累计 Token | - |
| Handoff 次数 | 编排跳转频率 | - |

#### 9.2.3 工具指标

| 指标 | 说明 | 告警阈值 |
|------|------|---------|
| 调用次数 | Tool Span 计数 | - |
| 成功率 | 工具调用成功比例 | < 99% |
| 延迟 | Tool Span Duration | p99 > 2s |
| Guardrail 拦截率 | 被 Tool Guardrail 拦截的比例 | - |

#### 9.2.4 成本指标

| 指标 | 说明 |
|------|------|
| 总成本 | 平台总 LLM 调用成本 |
| 按 Agent/模型分摊 | 细分维度的成本（基于 LLM Span Token 计算） |
| 单任务平均成本 | 每次 Run 的平均花费 |
| 预算使用比例 | 当前成本 / 预算上限 |

### 9.3 告警规则支持配置告警规则：

| 配置项 | 说明 |
|--------|------|
| 指标类型 | task / agent / tool / mcp / cost |
| 触发条件 | 阈值比较（>、<、>=、<=） |
| 持续时间 | 持续满足条件的秒数 |
| 作用域 | 全局 / 团队 / Agent / 工具 |
| 严重级别 | critical / warning / info |
| 通知渠道 | 邮件 / Webhook / Slack / 站内消息 |

#### 预置告警规则

| 规则 | 条件 | 严重度 |
|------|------|--------|
| 任务失败率过高 | > 5% | Critical |
| Agent 响应过慢 | P95 > 3s | Warning |
| 工具失败率过高 | > 1% | Warning |
| MCP Server 断连 | 连接状态 = 0 | Critical |
| 日成本超预算 | 

> 预算 80% | Warning |
| Guardrail 拦截率异常 | > 20% | Warning |

### 9.4 成本控制策略

#### 9.4.1 预算管理

| 维度 | 说明 |
|------|------|
| 组织级预算 | 每月 Token 消耗总额上限，达到 80% 告警、100% 阻断 |
| 团队级预算 | 团队内预算分配 |
| 用户级配额 | 个人每日 Token 上限和请求次数上限 |
| Agent 级限额 | 单次 Run 最大 Token 消耗（通过 max_turns + 模型设置控制） |

#### 9.4.2 模型降级策略

| 触发条件 | 降级行为 |
|---------|----------|
| 预算使用 > 80% | 推荐使用低成本模型 |
| 预算使用 > 95% | 强制使用低成本模型（通过 RunConfig 覆盖 Agent 模型） |
| 预算使用 = 100% | 阻断新请求 |

> 告警引擎评估周期与状态机、成本控制引擎（Pre-Run / Per-LLM 检查点）、模型降级执行器、指标查询层（PostgreSQL / Prometheus + Redis 缓存策略）等技术细节详见《CkyClaw 应用层技术设计方案 v1.2》第三章。

#### 9.4.3 Token 开销优化设计

CkyClaw 在系统架构的 **6 个层面** 内嵌 Token 节省机制：

| 优化层 | 产品能力 | 预期效果 |
|--------|---------|---------|
| **上下文管理** | Session 历史裁剪——滑动窗口 / Token 预算 / 摘要压缩三种策略 | 高：长对话场景下可节省 50-80% 上下文 Token |
| **工具描述优化** | 精确工具组加载 + 延迟工具发现（ToolSearchTool）| 中-高：初始提示可减少 200-500 Token/工具 |
| **Prompt 工程** | Instructions 模板变量、Handoff 历史过滤、结构化输出、Agent-as-Tool 上下文隔离 | 中：减少冗余上下文传递 |
| **模型选择与路由** | 任务分级自动匹配模型（简单用小模型）、预算触发降级、Coordinator 路由用小模型 | 高：小模型单价约大模型的 1/10-1/20 |
| **缓存与复用** | 语义缓存（相似查询复用）、工具结果缓存（TTL 内复用）| 高：完全免除重复 LLM 调用 |
| **运行时控制** | max_turns 限制、工具超时、Guardrail 早期拦截 | 中：防止无限循环和无效消耗 |

**效果度量指标：**

| 指标 | 来源 | 说明 |
|------|------|------|
| 平均每 Run Token 消耗 | Token 审计 | 越低越好（质量不变前提下） |
| Token / 质量比 | 审计 + 评估 | Token 消耗 / 用户好评率——综合衡量成本效率 |
| 缓存命中率 | 应用层指标 | 语义缓存 + 工具结果缓存的命中比例 |

> 各优化策略的实现细节（裁剪算法、缓存引擎、降级执行器）详见《CkyClaw Framework Design v2.0》第六/九章和《CkyClaw 应用层技术设计方案 v1.2》第三章。

### 9.5 Token 审计日志与统计

Token 审计是 CkyClaw 对大模型使用的全链路追踪与分析体系。基于 CkyClaw Framework Tracing 中的 LLM Span 数据，构建多维度的 Token 消耗审计、统计和预警能力。

#### 9.5.1 审计

数据采集每次 LLM 调用自动采集以下审计字段（由 Trace Processor 从 LLM Span 提取并写入 `token_usage_log` 表；MVP 使用 PostgreSQL，大规模场景可选 ClickHouse）：| 字段 | 说明 |
|------|------|
| trace_id | 执行链路 ID |
| span_id | LLM Span ID |
| user_id | 发起请求的用户 |
| org_id | 所属组织 |
| team_id | 所属团队 |
| agent_name | 执行的 Agent |
| model | 使用的模型（如 gpt-4o） |
| provider | 模型厂商（如 openai） |
| prompt_tokens | 输入 Token 数 |
| completion_tokens | 输出 Token 数 |
| total_tokens | 总 Token 数 |
| cost_usd | 费用（基于 ModelConfig 中的单价自动计算） |
| session_id | 会话 ID |
| run_id | Run ID |
| timestamp | 调用时间 |

#### 9.5.2 统计聚合维度系统提供预计算的物化视图，支持以下统计维度：

| 维度 | 聚合粒度 | 典型查询 |
|------|---------|---------|
| 按用户 | 每日/每周/每月 | "张三本月共消耗多少 Token？花费多少？" |
| 按 Agent | 每日/每周/每月 | "data-analyst Agent 上周 Token 趋势？" |
| 按模型 | 每日/每周/每月 | "GPT-4o vs Claude 3.5 本月用量对比？" |
| 按厂商 | 每日/每周/每月 | "OpenAI 与 DeepSeek 成本占比？" |
| 按组织 | 每日/每周/每月 | "各组织本月总开销排名？" |
| 按团队 | 每日/每周/每月 | "研发团队 vs 运营团队 Token 用量？" |

**聚合更新策略：**- **PostgreSQL（默认）：** 定时任务（pg_cron）每 5 分钟增量聚合写入 `token_usage_summary` 表，查询延迟 < 1s。- **ClickHouse（可选）：** AggregatingMergeTree 引擎物化视图，实时增量聚合，查询延迟 < 500ms。适用于日均 > 100 万条审计记录的大规模场景。

#### 9.5.3 审计日志查询审计日志支持按以下条件组合查询：

| 筛选条件 | 说明 |
|---------|------|
| 时间范围 | 起止时间 |
| 用户 | 指定用户 |
| Agent | 指定 Agent |
| 模型 | 指定模型 |
| 厂商 | 指定厂商 |
| 组织/团队 | 按组织层级筛选 |
| 最低消耗 | Token 数或费用下限（筛选高消耗请求） |

查询结果支持**导出为 CSV/Excel**，用于财务对账和审计存档。

#### 9.5.4 Token 使用告警与 9.3 告警规则体系集成，新增以下 Token 专属告警：

| 告警规则 | 条件 | 说明 |
|---------|------|------|
| 单次 Run 异常消耗 |

单次 Run 的 total_tokens

> 阈值 | 检测可能的无限循环或 Prompt 膨胀 |
| 用户日消耗超限 | 用户当日累计 

> 个人配额 80% | 提前预警配额耗尽 |
| 团队月预算超限 | 团队当月累计 

> 预算 80% | 提前预警预算耗尽 |
| 成本异常波动 | 当日成本 

> 最近 7 天均值×2 | 检测异常使用模式 |

#### 9.5.5 Token 审计仪表盘在 APM 仪表盘中嵌入 Token 审计专属视图（详见 10.2 页面清单）：

| 视图组件 | 说明 |
|---------|------|
| 总览卡片 | 本月总消耗 Token / 总费用 / 日均消耗 / 活跃用户数 |
| 趋势折线图 | Token 消耗随时间变化（按日/周/月切换） |
| 维度分布图 | 按 Agent / 模型 / 厂商 / 团队 的消耗占比饼图/柱状图 |
| Top-N 排名 | 消耗最高的用户 / Agent / 模型 排名表 |
| 预算进度 | 各层级（组织/团队/用户）预算使用进度条 |
| 审计日志表 | 可筛选、可排序的详细 Token 消耗明细 |

### 9.6 Agent 评估与质量度量

Agent 评估帮助团队持续优化 Agent 的回答质量和任务完成效果，超越简单的成功/失败统计。

#### 9.6.1 评估维度

| 维度 | 指标 | 采集方式 |
|------|------|---------|
| **任务完成率** | Run 成功结束比例（final_output 非空 / 总 Run） | 自动（Tracing 数据） |
| **质量评分** | 用户对 Agent 回复的 👍/👎 评分 | 用户反馈（前端评分组件） |
| **Token 效率** | 平均每次成功 Run 消耗的 Token 数 | 自动（Token 审计） |
| **延迟分布** | P50 / P95 / P99 端到端响应时间 | 自动（Tracing 数据） |
| **Guardrail 触发率** | Input/Output Guardrail Tripwire 触发频率 | 自动（Guardrail Span） |
| **Handoff 成功率** | Handoff 后目标 Agent 成功完成比例 | 自动（Tracing 数据） |
| **工具调用成功率** | Tool 执行成功 / 总调用 | 自动（Tool Span） |

#### 9.6.2 用户反馈采集

| 场景 | 采集方式 |
|------|---------|
| Web 对话 | 每条 Agent 回复下方 👍/👎 按钮 + 可选文字反馈 |
| IM 渠道 | 回复末尾添加评分引导（如 Slack 的 reaction 表情） |
| API 调用 | `POST /api/v1/runs/{run_id}/feedback` 接口 |

反馈数据关联到 `run_id`，存储在 `run_feedback` 表（user_id, run_id, rating, comment, created_at）。

#### 9.6.3 评估报表APM 仪表盘中新增 **Agent 质量** 视图：

| 组件 | 说明 |
|------|------|
| Agent 质量排名 | 按综合评分排序的 Agent 列表（任务完成率 × 用户好评率） |
| 质量趋势 | 按周/月展示各 Agent 的质量分变化趋势 |
| 负面反馈明细 | 用户给出 👎 的 Run 列表，可查看原始对话和 Trace |
| 版本对比 | 同一 Agent 不同版本的质量指标对比（与 4.8.1 版本管理联动） |---

## 十、前端与用户界面

### 10.1 技术选型

| 维度 | 方案 | 说明 |
|------|------|------|
| 框架 | React 18+ | SPA 单页应用 |
| 构建工具 | Vite 5 | 开发热更新快，生产构建高效 |
| 状态管理 | Zustand | 轻量、无 boilerplate、支持中间件 |
| UI 组件库 | Ant Design 5 | 企业级组件丰富、中文生态成熟 |
| 高级业务组件 | ProComponents（ProTable / ProForm / ProLayout） | 基于 Ant Design 的高级封装，大幅减少管理后台样板代码 |
| 数据请求 | TanStack Query（React Query） | 自动缓存、重复请求去重、乐观更新、后台重新获取 |
| 流程图渲染 | ReactFlow | Agent 编排与执行可视化 |
| 图表 | ECharts | APM 仪表盘、Token 审计趋势图 |
| 实时通信 | WebSocket（监督面板）+ SSE（Agent 流式输出） | 双通道满足不同场景 |
| 构建部署 | Vite 构建，Nginx 静态托管，独立于后端部署 | 前后端分离 |

### 10.2 页面清单

| 页面 | 优先级 | 说明 |
|------|--------|------|
| **对话界面** | P0 | 与 Agent 实时对话，支持流式输出、文件上传、历史记录 |
| **Agent 管理** | P0 | 声明式创建/编辑 Agent，编辑 Instructions，配置 Handoff/工具组 |
| **执行监控面板** | P0 | 以流程图展示 Run 执行过程（基于 Tracing 数据） |
| **监督面板** | P0 | 活跃会话列表、实时对话流、干预/接管/审批操作 |
| **APM 仪表盘** | P1 | 指标图表、链路追踪详情、告警列表、成本概览 |
| **Token 审计** | P0 | Token 消耗统计、多维度分析、审计日志查询、预算进度、数据导出 |
| **SOUL.md 编辑器** | P1 | Prompt 模板编辑，版本历史对比，模板库 |
| **模型厂商管理** | P0 | 配置 LLM 厂商连接信息、模型列表、价格、默认模型、连通性测试 |
| **系统管理** | P1 | 用户管理、角色权限、渠道配置、审计日志 |
| **登录/注册** | P0 | 用户认证 |

### 10.3 信息架构

```
CkyClaw├── 对话                           

# 与 Agent 对话交互│
├── 新建

对话（选择 Agent）│
├── 历史对话列表│
└── 对话详情（流式输出 + 执行图）├── Agent 管理│
├── Agent 列表│
├── 创建/编辑 Agent│
│
├── 基本信息（名称、描述、模型）│
│
├── Instructions 编辑器（SOUL.md）│
│
├── 工具组配置│
│
├── Handoff 关系配置│
│
├── Guardrails 配置│
│
└── 审批模式设置│
└── 版本历史├── 执行监控│
├── 执行记录列表│
├── 执行详情（流程图 + Trace 详情）│
└── 执行状态管理├── 监督中心│
├── 活跃会话│
├── 审批队列│
└── 监督规则配置├── APM│
├── 仪表盘│
├── 链路追踪（Trace/Span 详情）│
├── 告警管理│
├── 成本分析│
└── Token 审计│
├── 统计概览（总览卡片 + 趋势图 + 维度分布）│
├── 审计日志查询（多条件筛选 + 导出）│
├── Top-N 排名│
└── 预算进度└── 系统设置
├── 模型厂商管理    │
├── 厂商列表（名称、状态、模型数、最近健康检查）    │
├── 添加/编辑厂商（Base URL、API Key、认证方式、限流）    │
├── 模型配置（名称、上下文窗口、价格、启用状态）    │
└── 连通性测试 / 设置默认模型
├── 用户管理
├── 角色权限
├── 渠道配置
├── MCP Server 管理
└── 审计日志

```
> 项目结构、路由表、SSE 流式渲染机制、执行流程图（ReactFlow）映射规则、监督面板 WebSocket 事件协议等技术细节详见《CkyClaw 应用层技术设计方案 v1.2》第二章。

### 10.4 核心用户旅程

#### 10.4.1 发起对话

选择 Agent → 创建对话 → 输入消息 → 实时查看流式回复 → 查看工具调用 / Handoff 过程 → 继续对话或结束

#### 10.4.2 创建 Agent

Agent 管理 → 新建 → 填写基本信息 → 编辑 Instructions（可从模板库选择）→ 配置工具组 → 配置 Handoff 目标 → 设置审批模式 → 保存 → 发起对话测试

#### 10.4.3 查看执行过程

在对话界面或执行监控中点击 Run → 以流程图查看执行 Trace → 点击节点查看 Span 详情 → 对异常执行取消/重试

#### 10.4.4 监督干预

监督面板查看活跃会话 → 进入实时对话流 → 发现异常 → 暂停 Agent → 注入修正指令 → 恢复执行（或接管/拒绝）

---


---

*文档版本：v2.0.8*
*最后更新：2026-04-02*
*作者：CkyClaw Team*
