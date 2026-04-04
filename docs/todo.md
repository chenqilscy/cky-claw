# CkyClaw 待办事项与演进规划

> 本文件基于 PRD v2.0 与 mvp-progress.md 的差距分析生成，记录所有未完成功能、待优化项和未来演进方向。
>
> 最后更新：2026-04-04

---

## 一、MVP 内延期项（已标记"后续迭代"）

以下功能在 M0–M7 实现过程中被显式标记为"后续迭代"：

| # | 功能 | 来源 | 优先级 | 说明 |
|---|------|------|:------:|------|
| 1 | ~~WebSocket 审批通道~~ | Phase 4.2.8 / 4.3.6 | P1 | ✅ 已完成（WebSocket + Redis pub/sub + 前端实时推送 + 10 测试） |
| 2 | 可观测性基础设施 | Phase 0.5.3 | P2 | OTel Collector + Jaeger + Prometheus + Grafana；当前仅有 PostgresTraceProcessor |
| 3 | auto-edit 审批模式真实语义 | Phase 4.2.5 | P2 | 当前 auto-edit 等同 FULL_AUTO；需实现"安全操作自动、高风险需审批"分级逻辑 |

---

## 二、PRD 功能差距分析

以下功能在 PRD v2.0 中有完整设计但当前未实现：

### 2.1 核心框架层（CkyClaw Framework）

| # | 功能 | PRD 章节 | 优先级 | 复杂度 | 说明 |
|---|------|----------|:------:|:------:|------|
| 4 | ~~**Memory 记忆系统**~~ | §2.12 | P1 | 高 | ✅ 已完成（Framework 4 文件 + Backend 6 文件 + Frontend 4 文件 + 44 测试） |
| 5 | ~~**Agent Team 协作协议**~~ | §2.5.5 | P1 | 高 | ✅ Framework 全栈完成（Sequential/Parallel/Coordinator + Backend CRUD + Frontend UI + Migration 0021 + 43 测试） |
| 6 | ~~**Skill 技能系统**~~ | §2.7 | P2 | 中 | ✅ 已完成（Framework 4 文件 + Backend 6 文件 + Frontend 4 文件 + 40 测试） |
| 7 | **Sandbox 沙箱隔离** | §3.2 | P2 | 高 | Docker/K8s 隔离代码执行环境、CPU/内存/网络资源限制 |
| 8 | ~~**output_type 结构化输出**~~ | §2.1 | P1 | 中 | ✅ 已完成（Agent.output_type + Runner JSON 解析 + 前端 JSON Schema 编辑器） |
| 9 | ~~**Dynamic Instructions**~~ | §2.1 | P2 | 低 | ✅ 已完成（InstructionsType 支持 str/sync/async callable + 6 测试） |
| 10 | ~~**Handoff input_type**~~ | §2.3 | P2 | 低 | ✅ 已完成（Handoff.input_type Pydantic Schema + 5 测试） |
| 11 | **ToolSearchTool 延迟加载** | §2.6 | P2 | 中 | 工具数 >20 时自动启用 `search_tools(query)` 元工具，减少 Prompt Token |
| 12 | **条件启用** | §2.6 | P3 | 低 | Agent-as-Tool / Function Tool 基于 RunContext 动态启用/禁用 |
| 13 | **Hosted Tool 内置工具** | §2.6 | P2 | 中 | Web Search、Code Interpreter 等平台内置工具 |
| 14 | ~~**Session 历史裁剪**~~ | §2.9 | P1 | 中 | ✅ 已完成（HistoryTrimmer 滑动窗口 + Token 预算集成） |
| 15 | **Guardrail 并行模式** | §2.10 | P2 | 中 | 当前仅阻塞模式；需支持 Guardrail 与 Agent 并行执行以降低延迟 |

### 2.2 应用层（CkyClaw Backend + Frontend）

| # | 功能 | PRD 章节 | 优先级 | 复杂度 | 说明 |
|---|------|----------|:------:|:------:|------|
| 16 | **IM 渠道接入** | §7 | P1 | 高 | 企业微信、钉钉、Slack、Telegram 等消息渠道；统一消息总线 |
| 17 | **定时/批量任务** | 附录 A | P2 | 中 | ScheduledRun（Cron 表达式）+ BatchRun（多输入并行）|
| 18 | **完整 RBAC** | §13.3 | P1 | 高 | Organization / Team / Role 层级 + 资源级细粒度授权 |
| 19 | **多租户** | §3.3 | P1 | 高 | 数据隔离、配额管理、组织级配置 |
| 20 | **APM 仪表盘** | §9 | P2 | 高 | 指标聚合、告警规则、成本分析、Grafana 集成 |
| 21 | **Agent 评估与质量度量** | 附录 B v2.0.4 | P2 | 中 | 7 维评估（准确性/响应/安全/工具使用/成本/用户满意度/任务完成率）+ 用户反馈 |
| 22 | **配置热更新** | 附录 B v2.0.5 | P3 | 中 | ConfigChangeLog + 审计 + 回滚（6 类可热更新项）|
| 23 | **Agent 国际化** | 附录 B v2.0.5 | P3 | 低 | 多语言 Instructions / UI / 描述 |
| 24 | **模型列表管理** | §2.13 | P2 | 低 | Provider 下可用模型列表 CRUD（名称、上下文窗口、价格信息）|
| 25 | **成本计算** | §2.13 | P2 | 低 | prompt/completion token 单价配置 → 自动成本核算 |
| 26 | **限流配置** | §2.13 | P2 | 低 | Provider 级 RPM/TPM 限制，防超配额 |
| 27 | **灾备策略** | 附录 B v2.0.4 | P3 | 中 | RTO<4h / RPO<1h、PostgreSQL/Redis/对象存储备份方案 |
| 28 | ~~**内置 Agent 模板**~~ | 附录 B v2.0.5 | P2 | 低 | ✅ 已完成（10 个预设模板 + 模板市场 UI + CRUD API + Seed + 18 测试） |
| 29 | **垂直 Agent** | 定位守卫 P2 | P2 | 高 | 代码审查、DevOps、客服、数据分析等垂直领域 Agent |
| 30 | **声明式配置（YAML/TOML）** | §3.4 | P3 | 低 | Agent 配置除 API/DB 外，支持 YAML/TOML 文件导入导出 |

---

## 三、现有功能待优化项

### 3.1 前端优化

| # | 优化项 | 优先级 | 说明 |
|---|--------|:------:|------|
| O1 | TanStack Query 数据层 | P2 | 当前使用原生 fetch + useEffect；引入 TanStack Query 获得缓存/去重/重试/乐观更新 |
| O2 | Zustand 全局状态扩充 | P3 | 仅 authStore 使用 Zustand；Agent 列表、Session 等可受益于全局状态 |
| O3 | ECharts 图表 | P3 | Dashboard 当前用 Ant Design Progress 条；ECharts 饼图/折线图可提升数据表达 |
| O4 | 响应式布局 | P3 | 当前无移动端适配 |
| O5 | 暗色模式 | P3 | Ant Design 5 支持 ConfigProvider theme 切换 |
| O6 | ~~前端测试覆盖~~ | P1 | ✅ 已完成（58 个 Vitest 测试：API/AgentService/AuthStore/SkillService/TemplateService/WorkflowService/TeamService/AuditLogService） |
| O7 | ~~对话页体验优化~~ | P1 | ✅ 已完成（MarkdownRenderer + Prism 代码高亮 + 复制按钮 + React.memo 优化） |

### 3.2 后端优化

| # | 优化项 | 优先级 | 说明 |
|---|--------|:------:|------|
| O8 | ~~Redis 实际使用~~ | P2 | ✅ 已完成（WebSocket 审批通道 Redis pub/sub + 连接池管理） |
| O9 | API 分页标准化 | P2 | 部分列表端点分页参数不完全一致 |
| O10 | 软删除统一 | P3 | 仅 Agent 有软删除；其他实体（Session/Provider/MCP 等）为硬删除 |
| O11 | ~~操作审计日志~~ | P1 | ✅ 已完成（AuditLog Model + Middleware + API + Frontend UI + Migration 0022 + 21 测试） |
| O12 | 错误信息国际化 | P3 | 当前错误消息只有英文 |

### 3.3 Framework 优化

| # | 优化项 | 优先级 | 说明 |
|---|--------|:------:|------|
| O13 | Guardrail 并行 + 阻塞双模式 | P2 | 当前仅阻塞模式；PRD 设计支持并行模式（Guardrail 与 Agent Loop 同时执行）|
| O14 | ~~Runner 重试机制~~ | P2 | ✅ 已完成（RunConfig.max_retries + retry_delay + 指数退避 + run/run_streamed 双路径 + 6 测试） |
| O15 | 多 TraceProcessor | P3 | 当前每次 run 只注入 1 个 PostgresTraceProcessor；支持链式多 Processor |
| O16 | Tool 并发限流 | P3 | 多工具并行时无全局并发限制；可配置最大并发工具数 |

---

## 四、演进路线图

基于 PRD 附录 C.3 的迭代优先级和项目现状，规划以下演进方向：

### v2.1 — 核心增强 ✅ 全部完成

**目标**：补齐核心框架缺失能力，提升对话体验。

| 功能 | 对应编号 | 状态 | 关键交付物 |
|------|:--------:|:----:|----------|
| output_type 结构化输出 | #8 | ✅ | Agent.output_type + Runner JSON 解析 + 前端 JSON Schema 编辑器 |
| Session 历史裁剪 | #14 | ✅ | HistoryTrimmer 集成（滑动窗口 + Token 预算） |
| WebSocket 审批 | #1 | ✅ | WebSocket + Redis pub/sub + 前端 WS 客户端 + 10 测试 |
| 前端测试覆盖 | O6 | ✅ | 47 个 Vitest 测试 |
| 对话页体验优化 | O7 | ✅ | MarkdownRenderer + Prism 代码高亮 + 复制按钮 |

### v2.2 — Memory & Skill ✅ 全部完成

**目标**：引入跨会话记忆和知识注入能力。

| 功能 | 对应编号 | 状态 | 关键交付物 |
|------|:--------:|:----:|----------|
| Memory 记忆系统 | #4 | ✅ | Framework + Backend + Frontend 全栈实现 + 44 测试 |
| Skill 技能系统 | #6 | ✅ | Framework + Backend + Frontend 全栈实现 + 40 测试 |
| Dynamic Instructions | #9 | ✅ | InstructionsType 支持 str/sync/async callable + 6 测试 |
| 内置 Agent 模板 | #28 | ✅ | 10 个预设模板 + 模板市场 + 18 测试 |

### v2.3 — Agent Team ✅ 全部完成

**目标**：团队级 Agent 协作。

| 功能 | 对应编号 | 状态 | 关键交付物 |
|------|:--------:|:----:|----------|
| Agent Team 协作协议 | #5 | ✅ | Framework: Team + TeamProtocol + TeamRunner + 18 测试 |
| Team Backend 持久化 | #5 | ✅ | ORM + Schema + Service + 5 API + Migration 0021 + 18 测试 |
| Team 管理 UI | #5 | ✅ | TeamPage CRUD + teamService + 7 测试 |
| Team 可视化 | #5 | ❌ | ReactFlow Team 编排画布 |

### v2.4 — 企业能力

**目标**：多租户和权限体系。

| 功能 | 对应编号 | 关键交付物 |
|------|:--------:|-----------|
| 完整 RBAC | #18 | Role / Permission 模型 + 资源级授权中间件 |
| 多租户 | #19 | Organization / Team 隔离 + 配额管理 |
| ~~操作审计~~ | O11 | ✅ AuditLog + AuditMiddleware + API + UI（已在 v2.3 提前完成） |
| IM 渠道接入 | #16 | 企业微信/钉钉 Webhook + 消息路由 |

### v2.5 — 可观测性 & APM

**目标**：生产级监控体系。

| 功能 | 对应编号 | 关键交付物 |
|------|:--------:|-----------|
| OTel + Jaeger | #2 | OpenTelemetry Collector + Jaeger Trace 导出 |
| Prometheus + Grafana | #2 | 指标采集 + 预置 Dashboard |
| APM 仪表盘 | #20 | 告警规则 + 成本分析 + 异常检测 |
| Agent 评估 | #21 | 7 维评估 + RunFeedback 用户反馈 |

### v2.6 — 高级特性

**目标**：补齐长尾功能。

| 功能 | 对应编号 | 关键交付物 |
|------|:--------:|-----------|
| Sandbox 沙箱 | #7 | Docker-in-Docker 代码执行隔离 |
| 定时/批量任务 | #17 | ScheduledRun + BatchRun + Celery/APScheduler |
| ToolSearchTool | #11 | 延迟加载元工具 |
| 配置热更新 | #22 | ConfigChangeLog + 回滚 |
| 灾备 | #27 | 自动备份 + 恢复脚本 |

---

## 五、技术债务

| 项目 | 说明 | 风险 |
|------|------|------|
| ~~Redis 未使用~~ | ✅ 已解决：WebSocket 审批通道使用 Redis pub/sub | ~~资源浪费~~ |
| ~~前端测试极少~~ | ✅ 已解决：47 个 Vitest 测试 | ~~无法保证 UI 回归~~ |
| mypy 未集成 CI | ruff lint 已有但 mypy strict 检查未在 CI 中运行 | 类型安全漏网 |
| 部分 test 排除 | CI 排除 smoke/performance/e2e/mcp 测试 | 需定期手动运行验证 |
| Alembic 自动生成 | 迁移均手写；未配置 autogenerate 对比 | 模型/迁移不一致风险 |

## 六、工作流引擎

⏳ Phase 1（Framework DAG 引擎）+ Phase 2（Backend 持久化 + CRUD API）已完成。

| Phase | 状态 | 说明 |
|-------|:----:|------|
| Phase 1 — Framework DAG 引擎 | ✅ | 5 步骤类型 + 安全表达式求值 + DAG 验证 + 并行执行 + 64 测试 |
| Phase 2 — Backend 持久化 | ✅ | ORM + Alembic 0020 + CRUD Service + 6 端点 + 验证 API + 管理 UI + 24 测试 |
| Phase 3 — Frontend 可视化管理 | ✅ | ReactFlow DAG 可视化 + Tabs 预览 + WorkflowGraphView 组件 |
| Phase 4 — ReactFlow DAG 编辑器 | ❌ | 拖拽式可视化 DAG 编排画布 |

---

*文档版本：v1.2.0*
*生成日期：2026-04-04*
*基于：PRD v2.0.9 / mvp-progress.md M0–M7 + v2.1~v2.3 增量实现*
