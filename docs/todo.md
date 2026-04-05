# CkyClaw 待办事项与演进规划

> 本文件基于 PRD v2.0 与 mvp-progress.md 的差距分析生成，记录所有未完成功能、待优化项和未来演进方向。
>
> 最后更新：2026-04-05

---

## 一、MVP 内延期项（已标记"后续迭代"）

以下功能在 M0–M7 实现过程中被显式标记为"后续迭代"：

| # | 功能 | 来源 | 优先级 | 说明 |
|---|------|------|:------:|------|
| 1 | ~~WebSocket 审批通道~~ | Phase 4.2.8 / 4.3.6 | P1 | ✅ 已完成（WebSocket + Redis pub/sub + 前端实时推送 + 10 测试） |
| 2 | ~~可观测性基础设施~~ | Phase 0.5.3 | P2 | ✅ 已完成（OTelTraceProcessor + FastAPI 中间件 + Jaeger docker-compose profile + Prometheus 配置） |
| 3 | ~~auto-edit 审批模式真实语义~~ | Phase 4.2.5 | P2 | ✅ 已完成（classify_tool_risk 风险分级 + SAFE/RISKY 前缀集 + _check_approval 重写） |

---

## 二、PRD 功能差距分析

以下功能在 PRD v2.0 中有完整设计但当前未实现：

### 2.1 核心框架层（CkyClaw Framework）

| # | 功能 | PRD 章节 | 优先级 | 复杂度 | 说明 |
|---|------|----------|:------:|:------:|------|
| 4 | ~~**Memory 记忆系统**~~ | §2.12 | P1 | 高 | ✅ 已完成（Framework 4 文件 + Backend 6 文件 + Frontend 4 文件 + 44 测试） |
| 5 | ~~**Agent Team 协作协议**~~ | §2.5.5 | P1 | 高 | ✅ Framework 全栈完成（Sequential/Parallel/Coordinator + Backend CRUD + Frontend UI + Migration 0021 + 43 测试） |
| 6 | ~~**Skill 技能系统**~~ | §2.7 | P2 | 中 | ✅ 已完成（Framework 4 文件 + Backend 6 文件 + Frontend 4 文件 + 40 测试） |
| 7 | ~~**Sandbox 沙箱隔离**~~ | §3.2 | P2 | 高 | ✅ 已完成（Framework: SandboxConfig + SandboxExecutor + LocalSandbox + Backend API + 25 测试） |
| 8 | ~~**output_type 结构化输出**~~ | §2.1 | P1 | 中 | ✅ 已完成（Agent.output_type + Runner JSON 解析 + 前端 JSON Schema 编辑器） |
| 9 | ~~**Dynamic Instructions**~~ | §2.1 | P2 | 低 | ✅ 已完成（InstructionsType 支持 str/sync/async callable + 6 测试） |
| 10 | ~~**Handoff input_type**~~ | §2.3 | P2 | 低 | ✅ 已完成（Handoff.input_type Pydantic Schema + 5 测试） |
| 11 | ~~**ToolSearchTool 延迟加载**~~ | §2.6 | P2 | 中 | ✅ 已完成（ToolSearchTool 元工具 + keyword 匹配 + threshold 阈值机制） |
| 12 | ~~**条件启用**~~ | §2.6 | P3 | 低 | ✅ 已完成（Guardrail + FunctionTool + Agent-as-Tool 三级条件启用，condition: Callable[[RunContext], bool]，20 测试） |
| 13 | ~~**Hosted Tool 内置工具**~~ | §2.6 | P2 | 中 | ✅ 已完成（10 个工具函数 + 5 组 ToolGroup + 种子数据 + Framework 57 测试 + Backend 7 测试） |
| 14 | ~~**Session 历史裁剪**~~ | §2.9 | P1 | 中 | ✅ 已完成（HistoryTrimmer 滑动窗口 + Token 预算集成） |
| 15 | ~~**Guardrail 并行模式**~~ | §2.10 | P2 | 中 | ✅ 已完成（RunConfig.guardrail_parallel + asyncio.TaskGroup 并行执行 Input/Output 护栏） |

### 2.2 应用层（CkyClaw Backend + Frontend）

| # | 功能 | PRD 章节 | 优先级 | 复杂度 | 说明 |
|---|------|----------|:------:|:------:|------|
| 16 | ~~**IM 渠道接入**~~ | §7 | P1 | 高 | ✅ 已完成（IMChannel ORM + CRUD API + Webhook 端点 + HMAC 签名验证 + 消息路由 + Migration 0025） |
| 17 | ~~**定时/批量任务**~~| 附录 A | P2 | 中 | ✅ 已完成（CRUD + SchedulerEngine 执行引擎 + ScheduledRun 历史 + Migration 0031 + 27 测试） |
| 18 | ~~**完整 RBAC**~~ | §13.3 | P1 | 高 | ✅ 已完成（Role ORM + RBAC Service + require_permission 全端点注入 + 前端 RolePage + Migration 0023 + 29 测试 + mypy re-export 修复） |
| 19 | ~~**多租户**~~ | §3.3 | P1 | 高 | ✅ 已完成（get_org_id 租户依赖 + 11 路由 org_id 注入 + conftest 全局 fixture + 28 测试） |
| 20 | ~~**APM 仪表盘**~~ | §9 | P2 | 高 | ✅ 已完成（聚合服务 + ECharts 可视化 + AlertRule/AlertEvent 告警引擎 + 7 API + Migration 0032 + 32 测试） |
| 21 | ~~**Agent 评估与质量度量**~~ | 附录 B v2.0.4 | P2 | 中 | ✅ 已完成（RunEvaluation 7 维评分 + RunFeedback 用户反馈 + AgentQualitySummary 汇总 + API 8 端点 + Migration 0026） |
| 22 | ~~**配置热更新**~~ | 附录 B v2.0.5 | P3 | 中 | ✅ 已完成（ConfigChangeLog 审计 + 回滚预览 + require_admin 权限 + Migration 0033-0034 + 28 测试） |
| 23 | ~~**Agent 国际化**~~ | 附录 B v2.0.5 | P3 | 低 | ✅ 已完成（Framework LocalizedInstructions + RunConfig.locale + Backend CRUD API 4 端点 + Migration 0035 + Frontend I18nSettingsPage + 24 测试） |
| 24 | ~~**模型列表管理**~~ | §2.13 | P2 | 低 | ✅ 已完成（ProviderModel ORM + CRUD API 5 端点 + Migration 0024） |
| 25 | ~~**成本计算**~~ | §2.13 | P2 | 低 | ✅ 已完成（TokenUsage 3 列成本字段 + 汇总聚合 + Migration 0024） |
| 26 | ~~**限流配置**~~ | §2.13 | P2 | 低 | ✅ 已完成（Redis 滑动窗口 RPM/TPM 限流器 + RateLimitExceeded 429） |
| 27 | ~~**灾备策略**~~ | 附录 B v2.0.4 | P3 | 中 | ✅ 已完成（scripts/backup.sh + restore.sh + backup-verify.sh + docker-compose backup profile 每日 2:00 AM cron + PG 30 天 / Redis 7 天保留策略） |
| 28 | ~~**内置 Agent 模板**~~ | 附录 B v2.0.5 | P2 | 低 | ✅ 已完成（10 个预设模板 + 模板市场 UI + CRUD API + Seed + 18 测试） |
| 29 | ~~**垂直 Agent**~~ | 定位守卫 P2 | P2 | 高 | ✅ 已完成（新增 4 个垂直模板：code-reviewer / devops-assistant / bi-analyst / complaint-handler，种子在 BUILTIN_TEMPLATES） |
| 30 | ~~**声明式配置（YAML/TOML）**~~ | §3.4 | P3 | 低 | ✅ 已完成（Agent 导出/导入 API + YAML/JSON 双格式 + 前端服务 + 16 测试） |

---

## 三、现有功能待优化项

### 3.1 前端优化

| # | 优化项 | 优先级 | 说明 |
|---|--------|:------:|------|
| O1 | ~~TanStack Query 数据层~~ | P2 | ✅ 已完成（useAgentQueries + useWorkflowQueries hooks + AgentListPage/WorkflowPage 重构） |
| ~~O2~~ | ~~Zustand 全局状态扩充~~ | P3 | ✅ 已完成（agentStore + sessionStore：列表缓存、分页、stale-while-revalidate、invalidate 接口） |
| ~~O3~~ | ~~ECharts 图表~~ | P3 | ✅ 已完成（Dashboard Guardrail 拦截率改为 ECharts Gauge + Span 类型分布改为 ECharts 饼图） |
| ~~O4~~ | ~~响应式布局~~ | P3 | ✅ 已完成（BasicLayout 添加 Grid.useBreakpoint + ProLayout breakpoint="md" 移动端折叠侧边栏） |
| O5 | ~~暗色模式~~ | P3 | ✅ 已完成（themeStore + ConfigProvider 主题切换） |
| O6 | ~~前端测试覆盖~~ | P1 | ✅ 已完成（64 个 Vitest 测试：API/AgentService/AuthStore/SkillService/TemplateService/WorkflowService/TeamService/AuditLogService/RoleService） |
| O7 | ~~对话页体验优化~~ | P1 | ✅ 已完成（MarkdownRenderer + Prism 代码高亮 + 复制按钮 + React.memo 优化） |

### 3.2 后端优化

| # | 优化项 | 优先级 | 说明 |
|---|--------|:------:|------|
| O8 | ~~Redis 实际使用~~ | P2 | ✅ 已完成（WebSocket 审批通道 Redis pub/sub + 连接池管理） |
| O9 | ~~API 分页标准化~~ | P2 | ✅ 已完成（36 文件统一 data/total/limit/offset 格式 + PaginatedResponse 泛型基类） |
| O10 | ~~软删除统一~~ | P3 | ✅ 已完成（SoftDeleteMixin + 15 模型/服务 + Migration 0030 + 30 测试） |
| O11 | ~~操作审计日志~~ | P1 | ✅ 已完成（AuditLog Model + Middleware + API + Frontend UI + Migration 0022 + 21 测试） |
| ~~O12~~ | ~~错误信息国际化~~ | P3 | ✅ 已完成（im_channels/organizations/agents/providers/evaluations 等全部英文错误消息改为中文） |

### 3.3 Framework 优化

| # | 优化项 | 优先级 | 说明 |
|---|--------|:------:|------|
| O13 | ~~Guardrail 并行 + 阻塞双模式~~ | P2 | ✅ 已完成（guardrail_parallel 配置 + asyncio.TaskGroup 并行执行） |
| O14 | ~~Runner 重试机制~~ | P2 | ✅ 已完成（RunConfig.max_retries + retry_delay + 指数退避 + run/run_streamed 双路径 + 6 测试） |
| O15 | ~~多 TraceProcessor~~ | P3 | ✅ 已完成（RunConfig.trace_processors: list + 链式调用 + Postgres/OTel/Console 三实现） |
| O16 | ~~Tool 并发限流~~ | P3 | ✅ 已完成（RunConfig.max_tool_concurrency + asyncio.Semaphore + 9 测试） |

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
| Team 可视化 | #5 | ✅ | TeamFlowPage + MemberNode + 3 协议布局 + dagre 自动排版 |

### v2.4 — 企业能力

**目标**：多租户和权限体系。

| 功能 | 对应编号 | 状态 | 关键交付物 |
|------|:--------:|:----:|----------|
| 完整 RBAC | #18 | ✅ | Role ORM + RBAC Service + require_permission 依赖 + API 端点 + 前端 RolePage + Migration 0023 + 29 测试 |
| 多租户 | #19 | ✅ | Organization CRUD + get_org_id 租户依赖 + 数据隔离 + 28 测试 |
| ~~操作审计~~ | O11 | ✅ | AuditLog + AuditMiddleware + API + UI（已在 v2.3 提前完成） |
| IM 渠道接入 | #16 | ✅ | IMChannel CRUD + Webhook + HMAC 验签 + 消息路由 + Migration 0025 |

### v2.5 — 可观测性 & APM

**目标**：生产级监控体系。

| 功能 | 对应编号 | 关键交付物 |
|------|:--------:|-----------|
| OTel + Jaeger | #2 | ✅ | OTelTraceProcessor + FastAPI 中间件 + Jaeger docker-compose profile |
| Prometheus + Grafana | #2 | ✅ | Prometheus docker-compose profile + scrape 配置 |
| APM 仪表盘 | #20 | ✅ | 聚合 API + ECharts + AlertRule 告警引擎 + 32 测试 |
| Agent 评估 | #21 | ✅ | RunEvaluation 7 维 + RunFeedback + AgentQualitySummary + 8 API + Migration 0026 |

### v2.6 — 高级特性

**目标**：补齐长尾功能。

| 功能 | 对应编号 | 关键交付物 |
|------|:--------:|-----------|
| Sandbox 沙箱 | #7 | Docker-in-Docker 代码执行隔离 |
| 定时/批量任务 | #17 | ✅ | SchedulerEngine + ScheduledRun + cron/interval + 27 测试 |
| ToolSearchTool | #11 | ✅ | ToolSearchTool 元工具 + keyword 匹配 + threshold 阈值 |
| 配置热更新 | #22 | ✅ | ConfigChangeLog + 回滚 + 审计 + 28 测试 |
| 灾备 | #27 | ✅ | scripts/backup.sh + restore.sh + backup-verify.sh + cron 每日 2:00 AM |

---

## 五、技术债务

| 项目 | 说明 | 风险 |
|------|------|------|
| ~~Redis 未使用~~ | ✅ 已解决：WebSocket 审批通道使用 Redis pub/sub | ~~资源浪费~~ |
| ~~前端测试极少~~ | ✅ 已解决：47 个 Vitest 测试 | ~~无法保证 UI 回归~~ |
| mypy 未集成 CI | ✅ 已解决：Framework 0/81 + Backend 0/138 全部 0 错误，CI mypy 步骤已激活 | 已修复 |
| ~~部分 test 排除~~ | ✅ 已优化：CI 仅排除 test_performance.py（SSE 流式 + 并发线程不适合 CI），smoke/e2e/mcp 已纳入 CI | 已修复 |
| Alembic 自动生成 | ✅ 已解决：`alembic/env.py` 已配置 `target_metadata = Base.metadata` + 全模型导入，`alembic revision --autogenerate -m "描述"` 直接可用 | 已修复 |

## 六、工作流引擎

| Phase | 状态 | 说明 |
|-------|:----:|------|
| Phase 1 — Framework DAG 引擎 | ✅ | 5 步骤类型 + 安全表达式求值 + DAG 验证 + 并行执行 + 64 测试 |
| Phase 2 — Backend 持久化 | ✅ | ORM + Alembic 0020 + CRUD Service + 6 端点 + 验证 API + 管理 UI + 24 测试 |
| Phase 3 — Frontend 可视化管理 | ✅ | ReactFlow DAG 可视化 + Tabs 预览 + WorkflowGraphView 组件 |
| Phase 4 — ReactFlow DAG 编辑器 | ✅ | WorkflowEditorPage 拖拽编排画布 + 节点属性 Drawer + 保存/验证 |


## 七、其它

### ~~`Settings`~~
~~`config.py`中`Settings`类，相关中间件的配置信息，采用硬编码的方式。需要改为从配置文件中读取~~

✅ 已解决：Settings 使用 Pydantic v2 BaseSettings，全部通过 `CKYCLAW_` 前缀环境变量配置，无硬编码

### 引用版本
分析引用的框架、包、基础镜像等版本是否需要升级更新

### 多渠道接入
目前支持哪些渠道，至少要规划哪些渠道？
- wechat
- 企业微信
- 钉钉
- 自定义渠道
- ...

### 用户认证
- 多种OAuth认证：github google keycloak tenant(qq/wechat) 等
- 行业常见的优秀认证方案（）

### 本地启动/调试

本机启动所有的系统，体验功能，提出缺陷。

### CI/CD

jenkins 自动构建与部署

---

*文档版本：v1.5.0*
*生成日期：2026-04-04*
*基于：PRD v2.0.9 / mvp-progress.md M0–M7 + v2.1~v2.5 增量实现*
