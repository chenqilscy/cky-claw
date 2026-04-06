# CkyClaw 待办事项与演进规划

> 本文件基于 PRD v2.0 与 mvp-progress.md 的差距分析生成，记录所有未完成功能、待优化项和未来演进方向。
>
> 最后更新：2026-07-04

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
| O6 | ~~前端测试覆盖~~ | P1 | ✅ 已完成（335 个 Vitest 测试：65 个测试文件，覆盖18 Service + 4 Store + 33 Page + API + Smoke） |
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
| 前端测试覆盖 | O6 | ✅ | 181 个 Vitest 测试（31 文件） |
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

### ~~引用版本~~

✅ 已分析（2026-04-05）：当前依赖版本均为宽松下界约束（`>=`），适合快速迭代阶段。

| 层 | 关键依赖 | 当前约束 | 评估 |
|---|---|---|---|
| Framework | litellm | `>=1.40.0` | ✅ 宽松，跟随上游即可 |
| Framework | pydantic | `>=2.0.0` | ✅ 正确 |
| Backend | fastapi | `>=0.115.0` | ✅ 正确 |
| Backend | sqlalchemy[asyncio] | `>=2.0.0` | ✅ 正确 |
| Backend | alembic | `>=1.13.0` | ✅ 正确 |
| Frontend | react | `^19.0.0` | ✅ 已升级到 React 19 |
| Frontend | vite | `^6.0.0` | ✅ 已升级到 Vite 6 |
| Frontend | typescript | `~5.8.0` | ✅ 已升级到 TS 5.8 |
| Docker | python 基础镜像 | `3.12-slim` | ✅ 正确 |
| Docker | node 基础镜像 | `22-alpine` | ✅ 已升级到 Node 22 LTS |

**结论**：全部依赖版本健康。前端侧已完成 React 19 / Vite 6 / TS 5.8 / Node 22 升级。

### ~~todo.md 未完成项~~

✅ 已分析（2026-04-05）：#1–#30 全部已完成打勾，O1–O16 全部已完成打勾，v2.1–v2.6 全部已完成。本节完成标记。

### 多渠道接入

**当前状态**：已实现通用 IM 渠道框架（IMChannel ORM + CRUD + Webhook + HMAC 签名验证 + 消息路由），但尚未对接具体 IM 平台。

**规划渠道**（按优先级排序）：

| # | 渠道 | 优先级 | 复杂度 | 说明 |
|---|------|:------:|:------:|------|
| C1 | ~~**企业微信**~~ | P1 | 中 | ✅ 已完成（WeComAdapter：签名验证 + AES-256-CBC 消息加解密 + XML 解析 + 应用消息推送 + 19 测试） |
| C2 | ~~**钉钉**~~ | P1 | 中 | ✅ 已完成（DingTalkAdapter：HMAC-SHA256 签名验证 + JSON 解析 + Webhook 推送 + 15 测试） |
| C3 | ~~**飞书**~~ | P2 | 中 | ✅ 已完成（FeishuAdapter：SHA256 签名验证 + JSON 解析 + URL 验证回调 + REST API 消息推送 + 16 测试） |
| C4 | ~~**微信公众号/服务号**~~ | P2 | 高 | ✅ 已完成（WeChatOfficialAdapter：SHA1 签名验证 + 明文/加密 XML 解析 + 7 种消息类型 + 被动回复 + 客服消息推送 + 模板消息推送 + 36 测试） |
| C5 | ~~**Slack**~~ | P3 | 低 | ✅ 已完成（SlackAdapter：HMAC-SHA256 签名验证 + 时间戳防重放 + JSON 消息解析 + Bot/系统消息过滤 + challenge 验证 + chat.postMessage 推送 + 23 测试） |
| C6 | ~~**自定义 Webhook**~~ | P3 | 低 | ✅ 已完成（CustomWebhookAdapter：可配 HMAC 签名 + 嵌套字段映射 + 通用推送 + 16 测试） |

**已实现架构**：`ChannelAdapter` 抽象基类 + `WeComAdapter` / `DingTalkAdapter` / `FeishuAdapter` / `CustomWebhookAdapter` / `WeChatOfficialAdapter` / `SlackAdapter` 子类 + 适配器注册表 + Webhook 端点集成，位于 `backend/app/services/channel_adapters/`。

### 用户认证

**当前状态**：已实现 JWT + bcrypt 本地认证 + Admin/User 双角色 + RBAC 权限 + **OAuth 2.0 框架 + GitHub OAuth 登录**。

**规划升级**（按优先级排序）：

| # | 方案 | 优先级 | 说明 |
|---|------|:------:|------|
| A1 | ~~**OAuth 2.0 / OIDC 框架**~~ | P1 | ✅ 已完成（OAuthProviderConfig + oauth_service + Redis CSRF state + Fernet token 加密 + 6 API + Migration 0036 + 21 测试） |
| A2 | ~~**GitHub OAuth**~~ | P1 | ✅ 已完成（GitHub Authorization Code Flow + 前端 OAuth 跳转 + Token 交换 + 登录页 GitHub 按钮） |
| ~~A3~~ | ~~**企业微信/钉钉/飞书扫码登录**~~ | ~~P1~~ | ✅ 已完成（Backend 3 Provider 完整实现 + Frontend LoginPage 动态 Provider 按钮 + 12 页面测试） |
| A4 | ~~**Keycloak / Casdoor 集成**~~ | P2 | ✅ 已完成（OIDC Discovery + 标准 token 交换 + UserInfo 字段映射 + 20 测试） |
| A5 | ~~**Google OAuth**~~ | P3 | ✅ 已完成（标准 OAuth 2.0 + authorize builder + userinfo fetcher + 11 测试） |

**已实现架构**：Backend 统一 OAuth 2.0 回调端点 `/api/v1/auth/oauth/{provider}/callback`，前端 OAuth 跳转 + Token 交换，`user_oauth_connections` 表记录 Provider 绑定关系。

### 本地启动/调试

**当前状态**：
- `docker-compose up -d db redis` 启动基础设施 ✅
- Backend `uv run uvicorn app.main:app --reload` 开发模式 ✅
- Frontend `pnpm dev` 开发模式 ✅
- Alembic 迁移 `uv run alembic upgrade head` ✅

**待验证**：需实际启动全链路（PG + Redis + Backend + Frontend），体验完整功能流程、发现和修复 UI/API 缺陷。

### ~~CI/CD~~

✅ 已完成：
- **GitHub Actions**: 5 Job 全激活（lint-python / lint-frontend / test-python / test-frontend / build）
- **Jenkinsfile**: 5 Stage 流水线（Lint 3 并行 + Test 3 并行 + Frontend Build + Docker Build），使用容器化执行

## 八、开放性分析

### ~~框架分析~~

✅ 已完成（2026-04-05）：`docs/references/competitive-analysis.md` 已按双维度重构（v2.0）。

**维度一：AI Coding Agent（终端工具类）** — Claude Code、Codex CLI、DeerFlow
**维度二：Agent 开发框架（SDK 类）** — Agents SDK、LangChain/LangGraph、AutoGen、CrewAI

CkyClaw Framework 属于维度二，横向对比 5 个 SDK 框架 + 纵向分析 3 个 Coding Agent 的设计借鉴。

### 自研 vs OpenAI Agents SDK

**决策分析**：

CkyClaw Framework 的核心设计（Agent 数据类、Runner 循环、Handoff、Guardrails、Tracing、Sessions）大量借鉴 OpenAI Agents SDK 的优秀设计。选择自研而非直接依赖 SDK 的原因：

| 维度 | 直接依赖 Agents SDK | 自研 CkyClaw Framework |
|------|:---:|:---:|
| **多 Provider 支持** | ❌ 默认绑定 OpenAI | ✅ LiteLLM 适配 10+ 厂商 |
| **国产模型适配** | ❌ 无原生支持 | ✅ 通义/文心/讯飞/混元/DeepSeek... |
| **数据主权** | ⚠️ 依赖 OpenAI 基础设施 | ✅ 完全本地化部署 |
| **定制深度** | ⚠️ 受 SDK API 限制 | ✅ 完全掌控 Runner/Tracing/Session |
| **企业级扩展** | ❌ 无内置 RBAC/多租户/审计 | ✅ 企业能力深度集成 |
| **依赖风险** | ⚠️ SDK 版本更新可能 breaking | ✅ 自主演进节奏 |
| **开发成本** | ✅ 开箱即用 | ⚠️ 需自行实现核心逻辑 |

**结论**：对于面向中国企业的 AI Agent 平台，多 Provider 适配（尤其国产模型）、数据本地化、深度定制能力是刚需。自研框架在设计理念上与 Agents SDK 对齐，同时获得了完全的架构自主权。

**后续方向**：可考虑实现 Agents SDK 兼容层（Adapter），允许用户用 Agents SDK 的 Agent 定义直接在 CkyClaw 上运行。

## 九、当前关键指标

> 更新日期：2026-07-05

| 指标 | 数值 |
|------|------|
| 测试总数 | **3524**（Backend 1608 + Framework 1289 + Frontend 383 + E2E 35 + Channel 53 ignored） |
| 测试覆盖率 | Backend **98%** · Framework **100%** |
| Alembic 迁移 | **45** 个（0001–0045） |
| API 路由模块 | **34** 个 |
| 前端页面 | **29** 个（React.lazy 懒加载 + Vendor 分包 + MarkdownRenderer 动态加载） |
| CI Job | **5** 个 GitHub Actions + **5** Stage Jenkinsfile |
| TypeScript 错误 | **0**（含测试文件） |
| Backend mypy | **0** 错误（166 源文件） |
| Framework mypy | **0** 错误（92 源文件） |
| Backend ruff E501 | **0** 错误（51 个行宽全修复） |

---

## 十、未完成项汇总

> 截至 2026-04-05，以下功能已有设计或基础支撑，但尚未实现：

### 10.1 多渠道接入（待开发）

| # | 渠道 | 优先级 | 依赖 | 预计工作量 |
|---|------|:------:|------|-----------|
| ~~C3~~ | ~~飞书~~ | ~~P2~~ | — | ✅ 已完成 |
| ~~C4~~ | ~~微信公众号/服务号~~ | ~~P2~~ | — | ✅ 已完成（WeChatOfficialAdapter + 36 测试） |
| ~~C5~~ | ~~Slack~~ | ~~P3~~ | — | ✅ 已完成（SlackAdapter + 23 测试） |
| ~~C6~~ | ~~自定义 Webhook~~ | ~~P3~~ | — | ✅ 已完成 |

### 10.2 用户认证扩展（待开发）

| # | 方案 | 优先级 | 依赖 | 预计工作量 |
|---|------|:------:|------|-----------|
| ~~A3~~ | ~~企微/钉钉/飞书扫码登录~~ | ~~P1~~ | — | ✅ 已完成（三种 Provider 的 token 交换 + 用户信息获取 + 授权 URL 构建 + 分发表架构 + 52 测试） |
| ~~A4~~ | ~~Keycloak / Casdoor 集成~~ | ~~P2~~ | — | ✅ 已完成（OIDC Discovery + well-known 端点自动发现 + 20 测试） |
| ~~A5~~ | ~~Google OAuth~~ | ~~P3~~ | — | ✅ 已完成（标准 OAuth 2.0 流程 + 11 测试） |

### 10.3 其它待完成

| # | 项目 | 优先级 | 说明 |
|---|------|:------:|------|
| ~~V1~~ | ~~完整功能流程验证~~ | ~~P1~~ | ✅ 已完成（PG + Redis healthy → 36 迁移成功 → Backend 启动 → health 200 → OpenAPI 98 路径 → 401 认证保护 → 2582 测试通过） |
| ~~V2~~ | ~~Agents SDK 兼容层~~ | ~~P3~~ | ~~实现 Adapter 允许 OpenAI Agents SDK 的 Agent 定义直接在 CkyClaw 上运行~~ |
| ~~V3~~ | ~~竞品分析：LangChain/LangGraph 深度对比~~ | ~~P2~~ | ~~分析基于 LangChain/LangGraph 重构所需调整，补充到竞品分析文档~~ |

---

## 十一、自动进化机制（M8）

> 2026-07-04 新增

### M8P1 — Evolution 基础设施 ✅ 已完成

| 层 | 交付物 | 测试 |
|---|---|---|
| **Framework** | `evolution/` 模块：EvolutionConfig、SignalCollector、EvolutionProposal 状态机、StrategyEngine 策略引擎 | 50 |
| **Backend** | EvolutionProposalRecord ORM + Schema + Service + 5 API + Migration 0037 | 33 |
| **Frontend** | EvolutionPage 管理 UI + evolutionService + 服务测试 | 7 |

### M8P2 — 自动信号采集与策略执行 🔄 进行中

| 功能 | 说明 | 状态 |
|---|---|:---:|
| EvolutionHook 信号采集 | Runner hooks（on_agent_start/tool_start/tool_end/error）自动发射 ToolPerformanceSignal + as_run_hooks() 转换 | ✅ |
| Signal 持久化 API | POST/GET /signals + POST /signals/batch + EvolutionSignalRecord ORM + Migration 0038 | ✅ |
| Analyze 策略分析 API | POST /analyze/{agent_name} 读取信号 → Framework StrategyEngine → 生成 Proposal 持久化 | ✅ |
| 策略引擎定时运行 | 基于 ScheduledTask 定期触发 analyze + evolution_analyze task_type | ✅ |
| 建议自动应用 | apply_proposal_to_agent + auto_apply 参数 + min_confidence 阈值 | ✅ |

**M8P2 交付物**：

| 层 | 交付物 | 测试 |
|---|---|---|
| **Framework** | `evolution/hooks.py` EvolutionHook 自动信号采集 | +13 |
| **Backend** | EvolutionSignalRecord ORM + Signal Schema + Signal/Analyze Service + 4 API 端点 + Migration 0038 | +35 |

## 十二、优化项
- ~~Agent 意图检测、意图飘移处理~~ ✅ 已完成（IntentDetector + KeywordIntentDetector + Runner 集成 + on_intent_drift Hook + 30 tests）
- ~~成本路由优化器~~：✅ Phase 1 + Phase 2 已完成（ModelTierEnum + Provider model_tier/capabilities + CostRouter 规则分类器 + /classify + /recommend API + Migration 0040 + 41 tests + 前端 CostRouterPage 可视化 + 8 tests）
- ~~大模型API密钥安全托管机制~~：✅ 已完成（key_expires_at + key_last_rotated_at + rotate-key API + Fernet 加密 + Migration 0042 + 12 tests）
- ~~用户审批机制：通过IM渠道通知用户审批~~ ✅ 已完成（ApprovalNotifier + IMChannel notify_approvals + Migration 0041 + 14 tests）
- ~~checkpoint机制~~ ✅ 已完成（Checkpoint/CheckpointBackend/InMemoryCheckpointBackend + Runner resume_from + 20 tests + PostgresCheckpointBackend + Migration 0043 + 19 tests）
- ~~前端补全 — 密钥轮换 + 检查点 + 意图检测~~ ✅ 已完成（ProviderListPage 密钥状态列/轮换弹窗 + CheckpointPage + IntentDetectionPage + intentService/checkpointService + 路由注册 + 24 前端测试 + 8 E2E 测试）
- ~~性能优化 — Vite 分包 + ChatPage 拆包 + 连接池可配置化 + 审计中间件批量刷写~~ ✅ 已完成（manualChunks 5路分包 + MarkdownRenderer 动态导入 + ChatPage 808KB→5.91KB + db_pool_size/db_max_overflow 可配置 + AuditLogMiddleware 内存缓冲批量写入）
- ~~Intent Detection 后端 API~~ ✅ 已完成（POST /api/v1/intent/detect + KeywordIntentDetector 集成 + 3 E2E 测试）
- ~~Harness Engineering 架构优化~~ ✅ 已完成（深度健康检查 /health/deep + DB/Redis 探测 + Token 趋势 API GET /trend + Dashboard Token 趋势折线图 + 审计 shutdown flush + M8P2 状态确认 + Framework mypy 92源文件0错误）
- ~~Agent 实时状态监控~~ ✅ 已完成（GET /api/v1/agents/realtime-status 基于 TraceRecord 聚合 + case 表达式错误计数 + Dashboard Agent 状态卡片 + 2 E2E 测试 + 1 前端测试）
- ~~代码质量冲刺~~ ✅ 已完成（Backend ruff F401/F841 修复 + mypy 166源文件0错误 + Frontend TypeScript 0错误含测试 + 清理无用导入/变量/死代码）
- ~~代码质量优化 (E501 + 复合索引)~~ ✅ 已完成（51 个 E501 行宽修复 + Alembic 0044 traces (agent_name, start_time) 复合索引）
- ~~Dashboard 自动刷新 + Agent 活动趋势图~~ ✅ 已完成（Switch 自动刷新 30s + GET /activity-trend 时间桶聚合 + ECharts 折线图 + 8 前端测试）
- ~~模板导入向导~~ ✅ 已完成（POST /agent-templates/{id}/instantiate 参数覆盖 + TemplatePage 导入向导弹窗 + Form 自定义参数 + 创建 Agent 直达）
- ~~性能基准测试~~ ✅ 已完成（scripts/locustfile.py 12 个 @task + 10+ API 端点覆盖 + login 认证 + Dashboard 组合场景）
- ~~多租户数据隔离加固~~ ✅ 已完成（TraceRecord org_id 字段 + Alembic 0045 + traces/agents activity-trend org_id 过滤 + 1 E2E 测试）
- ~~WebSocket 统一事件推送~~ ✅ 已完成（/api/ws/events 端点 + Redis EVENTS_CHANNEL + publish_event 通用接口 + trace.completed/trace.error 自动推送 + 1 E2E 测试）
- ~~Span 火焰图~~ ✅ 已完成（build_flame_tree 嵌套 Span 树 + GET /traces/{id}/flame API + FlameChart ECharts 自定义系列 + TracesPage Tabs 集成 + 2 E2E 测试）
- ~~Session 消息搜索~~ ✅ 已完成（get_session_messages search 参数 + LIKE 通配符转义 + 1 E2E 测试）
- ~~Handoff 编排器边线标注~~ ✅ 已完成（HandoffEditorPage edges label/labelStyle/labelBgStyle 显示 → target 名称）
- ~~慢查询告警阈值预设~~ ✅ 已完成（alertService SLOW_QUERY_PRESETS 3 条预设 + ApmDashboardPage 告警规则创建/展示）
- ~~Trace 回放器~~ ✅ 已完成（build_replay_timeline 服务 + GET /traces/{id}/replay API + TraceReplayTimeline 组件 + TracesPage 回放 Tab + 2 E2E 测试）
- ~~多模型 A/B 测试~~ ✅ 已完成（POST /api/v1/ab-test 并行调用 + ABTestPage 前端 + abTestService + 2 E2E 测试）
- ~~Agent 版本 diff 增强~~ ✅ 已完成（AgentVersionPage 色彩编码对比 + 仅变更/全部字段切换开关）
- ~~Playwright E2E 基础设施~~ ✅ 已完成（playwright.config.ts + e2e/smoke.spec.ts 6 测试 + vite.config 排除 e2e）
- ~~pre-commit Linter 集成~~ ✅ 已完成（.pre-commit-config.yaml: ruff check+format + mypy + trailing-whitespace + detect-private-key 等 8 hooks）


---

*文档版本：v2.8.0*
*生成日期：2026-07-06*
*基于：PRD v2.0.9 / M0–M7 + v2.1–v2.6 全部完成 + M8P1 完成 + M8P2 完成 + OAuth 2.0 + ChannelAdapter + 覆盖率冲刺 + 代码质量冲刺 + 前端体验优化 + 模板导入向导 + 性能基准测试 + 多租户隔离加固 + WebSocket统一事件 + Span火焰图 + Session消息搜索 + 慢查询告警预设 + Trace回放器 + A/B模型测试 + Agent版本diff增强 + Playwright E2E + pre-commit Linter*
