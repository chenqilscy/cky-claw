# CkyClaw MVP 开发进度追踪

> 此文件记录 MVP 开发的全部任务及完成状态。每次会话可从此文件回溯进度。

## M0：项目启动与基础搭建

### Phase 0.1：Monorepo 骨架 ✅
- [x] 0.1.1 创建 monorepo 根目录结构（backend/ + frontend/ + ckyclaw-framework/）
- [x] 0.1.2 根级配置文件（.editorconfig + .gitignore + docker-compose.yml）
- [x] 0.1.3 根级 README.md
- [x] Git 初始化 + 推送至 GitHub

### Phase 0.2：CkyClaw Framework 包骨架 ✅
- [x] 0.2.1 Python 包初始化（pyproject.toml + __init__.py + py.typed）
- [x] 0.2.2 核心模块空壳 — agent/（agent.py, config.py, output.py）
- [x] 0.2.3 核心模块空壳 — runner/（runner.py, run_config.py, run_context.py, result.py）
- [x] 0.2.4 核心模块空壳 — model/（provider.py, settings.py, message.py, litellm_provider.py）
- [x] 0.2.5 核心模块空壳 — tools/, tracing/, session/

### Phase 0.3：Backend 骨架 ✅
- [x] 0.3.1 FastAPI 项目初始化（pyproject.toml + app/main.py → /health 返回 200）
- [x] 0.3.2 目录结构（api/ + models/ + services/ + schemas/ + core/）
- [x] 0.3.3 基础中间件（CORS + 请求 ID + 错误处理）
- [x] 0.3.4 数据库连接（SQLAlchemy async + Alembic 初始化）

### Phase 0.4：Frontend 骨架 ✅
- [x] 0.4.1 React + Vite 项目初始化（package.json + vite.config.ts）
- [x] 0.4.2 基础脚手架（Ant Design 5 + ProLayout + React Router）
- [x] 0.4.3 登录页占位（/login 路由 + 登录表单 UI）
- [x] 0.4.4 开发工具链（ESLint + TypeScript strict）

### Phase 0.5：部署脚本 ✅
- [x] 0.5.1 Docker Compose — 基础设施（PostgreSQL 16 + Redis 7）
- [x] 0.5.2 Docker Compose — 应用（Backend + Frontend Dockerfile + Nginx）
- [ ] 0.5.3 可观测性（OTel + Jaeger + Prometheus + Grafana）— 可选，MVP 暂缓

### Phase 0.6：CI 流水线 ✅
- [x] 0.6.1 GitHub Actions — lint（ruff + eslint）
- [x] 0.6.2 GitHub Actions — test（pytest + vitest）
- [x] 0.6.3 GitHub Actions — build（前后端构建 + Docker 镜像）

---

## M1：Agent 核心引擎

### Phase 1.1：Model 抽象层 ✅
- [x] 1.1.1 LiteLLMProvider 实现（litellm.acompletion 封装 + 流式支持）
- [x] 1.1.2 Message ↔ LiteLLM 格式互转（_converter.py：5 个转换函数）
- [x] 1.1.3 ModelProvider 单元测试（11 个测试 — mock litellm）

### Phase 1.2：Function Tool 系统 ✅
- [x] 1.2.1 @function_tool 装饰器完善（自动 JSON Schema 生成）
- [x] 1.2.2 工具执行引擎（参数解析 + sync/async 调用 + 超时处理）
- [x] 1.2.3 ToolContext 定义（RunContext 透传，实际注入待 Runner 集成）
- [x] 1.2.4 Function Tool 单元测试（15 个测试）

### Phase 1.3：Runner Agent Loop ✅
- [x] 1.3.1 Runner.run 核心循环（LLM → 工具调用 → 消息追加 → 循环）
- [x] 1.3.2 max_turns 控制 + Handoff 不计 turn
- [x] 1.3.3 final_output 解析（文本输出）
- [x] 1.3.4 Runner.run_streamed 流式输出（7 种 StreamEvent 类型）
- [x] 1.3.5 Runner.run_sync 同步封装（ThreadPoolExecutor 兼容已有事件循环）
- [x] 1.3.6 Agent Loop 集成测试（20 个测试 — mock LLM，多轮对话/工具调用/Handoff/错误处理）
- [x] 1.3.7 五轮代码审查（逻辑正确性/边界条件/架构一致性/安全性/性能）

### Phase 1.4：Session 基础持久化 ✅
- [x] 1.4.1 PostgreSQL SessionBackend 实现（asyncpg，DDL + CRUD + 事务）
- [x] 1.4.2 InMemorySessionBackend（内存 + asyncio.Lock 并发安全）
- [x] 1.4.3 Session 与 Runner 集成（session 参数、历史加载 + 新消息追加、所有退出路径均保存）
- [x] 1.4.4 Message.to_dict() / from_dict() 序列化
- [x] 1.4.5 Session 单元测试（21 个测试 — 序列化/Backend CRUD/Runner 集成）
- [x] 1.4.6 五轮代码审查（Postgres 序列化修复、LLM 异常 session 保存修复）

### Phase 1.5：集成验证 ✅
- [x] 1.5.1 端到端冒烟：Agent → 发消息 → 回复（智谱 GLM-4-Flash）
- [x] 1.5.2 端到端冒烟：Agent + 工具调用 → 执行 → 回复
- [x] 1.5.3 端到端冒烟：多轮对话 + Session 持久化
- [x] 1.5.4 流式对话验证
- [x] 集成测试标记 `pytest.mark.integration`，CI 默认不跑

## M2：Web 对话与 Agent 管理

### Phase 2.1：Agent CRUD API ✅
- [x] 2.1.1 AgentConfig SQLAlchemy 模型（18 字段完整对应 Data Model v1.3）
- [x] 2.1.2 Alembic 迁移：agent_configs 表（3 索引）
- [x] 2.1.3 Agent CRUD API（5 端点：列表/创建/详情/更新/软删除）
- [x] 2.1.4 Pydantic Schema（AgentCreate/AgentUpdate/AgentResponse + name 正则校验 + approval_mode 枚举）
- [x] 2.1.5 Service 层（分页搜索 + LIKE 转义 + IntegrityError 并发冲突处理）
- [x] 2.1.6 ConflictError 异常（409）
- [x] 2.1.7 Agent API 单元测试（23 个测试）
- [x] 2.1.8 五轮代码审查（LIKE 转义 + IntegrityError + populate_by_name + import 顺序）

### Phase 2.2：对话 API + SSE ✅
- [x] 2.2.1 SessionRecord SQLAlchemy 模型 + Alembic 迁移（sessions 表）
- [x] 2.2.2 Session CRUD API（创建/列表/详情/删除）
- [x] 2.2.3 POST /sessions/{id}/run — 非流式 JSON 响应
- [x] 2.2.4 POST /sessions/{id}/run — SSE 流式事件输出（10 种事件类型）
- [x] 2.2.5 AgentConfig → Framework Agent 构建桥梁
- [x] 2.2.6 对话 API 测试（15 个测试）
- [x] 2.2.7 五轮代码审查（unused import + StreamingResponse 生命周期确认）

### Phase 2.3：用户认证 ✅
- [x] 2.3.1 User 模型 + 迁移（UUID PK, username/email unique, bcrypt hash, role, is_active）
- [x] 2.3.2 注册/登录 API（JWT HS256 + bcrypt 密码哈希）
- [x] 2.3.3 认证中间件（get_current_user / require_admin 依赖注入）
- [x] 2.3.4 2 个角色：Admin + User
- [x] 2.3.5 AuthenticationError（401）异常类型
- [x] 2.3.6 认证 API 测试（16 个测试）
- [x] 2.3.7 五轮代码审查（AuthenticationError 语义修正 + 延迟导入提升 + 未用 import 清理）

### Phase 2.4：前端对话页 ✅
- [x] 2.4.1 对话页 UI（ChatPage + ChatSidebar + ChatWindow 三组件布局）
- [x] 2.4.2 SSE 客户端（fetch + ReadableStream 流式解析，AbortController 生命周期管理）
- [x] 2.4.3 Agent 选择器（下拉选择 + 自动加载列表）
- [x] 2.4.4 对话历史列表（按 Agent 筛选会话列表）
- [x] 2.4.5 流式消息渲染（text_delta 实时拼接 + agent_start/run_end 状态处理）

### Phase 2.5：前端 Agent 管理页 ✅
- [x] 2.5.1 Agent 列表页（ProTable + 搜索 + 分页 + 删除确认）
- [x] 2.5.2 Agent 创建/编辑表单（Ant Design Form + name 正则校验 + approval_mode 枚举）
- [x] 2.5.3 登录页对接后端认证（authStore + JWT Token 管理 + 路由守卫）
- [x] 2.5.4 API 服务层（fetch 封装 + JWT 自动注入 + 错误解析）
- [x] 2.5.5 TypeScript 零错误 + ESLint 零新增错误
- [x] 2.5.6 五轮代码审查（逻辑/边界/规范/安全/性能）

## M3：编排与 Tracing

### Phase 3.1：Handoff 机制 ✅
- [x] 3.1.1 Handoff 数据类（agent、tool_name、tool_description、input_filter）
- [x] 3.1.2 InputFilter 类型（`Callable[[list[Message]], list[Message]]`）
- [x] 3.1.3 自定义 tool_name / tool_description 支持
- [x] 3.1.4 Runner 中 Handoff 分支应用 InputFilter（run + run_streamed）
- [x] 3.1.5 向后兼容（Agent 直接引用仍可用）
- [x] 3.1.6 Handoff 测试（16 个测试 — 数据类/兼容性/Runner/InputFilter/流式）
- [x] 3.1.7 五轮代码审查（unused import 修复）

### Phase 3.2：Agent-as-Tool ✅
- [x] 3.2.1 Agent.as_tool() 封装（FunctionTool 包装 + 延迟导入避免循环 + config 注入）
- [x] 3.2.2 Runner 中 AgentTool 的递归执行（独立 Runner.run 子调用 + 消息历史隔离）
- [x] 3.2.3 Agent-as-Tool 测试（11 个测试 — 基础/执行/流式/边界条件）
- [x] 3.2.4 五轮代码审查（unused import 修复）

### Phase 3.3：Tracing 自动采集 ✅
- [x] 3.3.1 Runner 中自动创建 Trace + Agent/LLM/Tool Span（`_TracingCtx` 内部上下文管理器）
- [x] 3.3.2 TraceProcessor 回调触发（Runner.run + Runner.run_streamed 全路径）
- [x] 3.3.3 ConsoleTraceProcessor（调试用日志输出）
- [x] 3.3.4 Tracing 测试（20 个测试 — Span/Trace 基础、启禁用、run/streamed/handoff/tool/边界条件）
- [x] 3.3.5 五轮代码审查（逻辑/边界/规范/安全/性能）
- [ ] 3.3.6 PostgreSQL TraceProcessor（Trace/Span 写入数据库）— 后续阶段
- [ ] 3.3.7 Tracing 数据模型 + 迁移 — 后续阶段

### Phase 3.4：Token 审计基础 ✅
- [x] 3.4.1 TokenUsageLog 模型 + 迁移（token_usage_logs 表 + 5 索引）
- [x] 3.4.2 LLM Span 自动填充 token_usage（_TracingCtx 数据采集与 processor 通知解耦）
- [x] 3.4.3 Token 统计查询 API（GET /api/v1/token-usage + GET /api/v1/token-usage/summary）
- [x] 3.4.4 RunResult.trace → TokenUsageLog 自动提取写入（execute_run + execute_run_stream）
- [x] 3.4.5 Token 审计测试（16 个测试 — Schema/Service/API/Model）
- [x] 3.4.6 五轮代码审查（异常保护加固）

### Phase 3.5：前端执行记录页 ✅
- [x] 3.5.1 执行列表页（Token 消耗明细 ProTable + Agent/时间筛选 + 汇总统计卡片）
- [x] 3.5.2 Agent Token 汇总表（按 Agent+模型分组汇总）
- [ ] 3.5.3 Span 详情展示（树形结构）— 后续迭代（需 Trace 持久化 API）

## M4：监督与安全

### Phase 4.1：Input Guardrail ✅
- [x] 4.1.1 InputGuardrail 执行（Runner 中 blocking 阻塞模式 + run/run_streamed 集成）
- [x] 4.1.2 GuardrailResult + InputGuardrailTripwireError 定义
- [x] 4.1.3 Agent.input_guardrails 字段 + Guardrail Span Tracing
- [x] 4.1.4 Guardrail 测试（23 个测试 — Result/InputGuardrail/执行函数/Runner 集成/Tracing/流式）
- [x] 4.1.5 五轮代码审查（run_streamed guardrail 异常处理对齐）
- [ ] 4.1.6 基础 Prompt 注入检测内置护栏 — 后续迭代（需 LLM-Based 模式）

### Phase 4.2：Approval Mode ✅
- [x] 4.2.1 ApprovalMode 枚举（SUGGEST/AUTO_EDIT/FULL_AUTO）+ ApprovalDecision 枚举 + ApprovalRejectedError
- [x] 4.2.2 ApprovalHandler 抽象接口（request_approval → ApprovalDecision）
- [x] 4.2.3 Agent.approval_mode 字段 + RunConfig 覆盖（RunConfig > Agent > 默认 FULL_AUTO）
- [x] 4.2.4 Runner 集成（_resolve_approval_mode + _check_approval + _execute_tool_calls 审批检查）
- [x] 4.2.5 三种模式语义：SUGGEST 必审批 / AUTO_EDIT MVP 等同 FULL_AUTO / FULL_AUTO 跳过
- [x] 4.2.6 Approval 测试（15 个测试 — 枚举/Handler/Runner 集成/RunConfig 覆盖/auto-edit/handler 详情）
- [x] 4.2.7 五轮代码审查（_resolve_approval_mode truthiness → is not None）
- [ ] 4.2.8 WebSocket 审批通道实现 + 审批请求 API — 后续迭代（需前后端 WebSocket 基础设施）

### Phase 4.3：监督面板 ✅
- [x] 4.3.1 活跃会话列表 API（GET /supervision/sessions + GET /{id} 详情 + Token 聚合统计）
- [x] 4.3.2 暂停/恢复操作 API（POST pause/resume + 状态前置检查 + ConflictError）
- [x] 4.3.3 前端监督面板（活跃会话 ProTable + 统计卡片 + 详情 Modal + 暂停/恢复操作）
- [x] 4.3.4 监督面板测试（25 个测试 — Schema/API/认证/路由注册）
- [x] 4.3.5 五轮代码审查（全部通过）
- [ ] 4.3.6 审批操作 UI（WebSocket 实时推送）— 后续迭代（需 WebSocket 基础设施）

### Phase 4.4：Model Provider 管理 ✅
- [x] 4.4.1 ProviderConfig 模型 + 迁移（provider_configs 表，4 索引 + Fernet API Key 加密）
- [x] 4.4.2 Provider CRUD API（6 端点：列表/创建/详情/更新/删除/启禁用 + require_admin 认证）
- [x] 4.4.3 Pydantic Schema（ProviderCreate/Update/Response + provider_type/auth_type 枚举校验）
- [x] 4.4.4 Provider API 单元测试（36 个测试 — Schema/Crypto/API/认证/路由注册）
- [x] 4.4.5 五轮代码审查（认证保护 + rate_limit 校验修复）
- [x] 4.4.6 Provider 管理前端页面（列表 ProTable + 创建/编辑表单 + 启禁用 Switch + 删除确认）

### Phase 4.5：Token 统计 ✅
- [x] 4.5.1 按用户/模型 Token 消耗查询 API（SummaryGroupBy 多维度分组 + model 筛选参数 + 10 新测试）
- [x] 4.5.2 Token 统计前端页面增强（模型筛选 + Segmented 维度切换 + 动态汇总列）
- [x] 4.5.3 五轮代码审查（后端 + 前端全部通过）

## M5：MVP 完整交付

### Phase 5.1：集成测试 ✅
- [x] 5.1.1 端到端场景：对话 + Handoff + 工具调用（7 个测试 — 单级/三级 Handoff + Tool + Session 持久化 + InputFilter + 自定义 tool_name + 多工具并行 + 流式）
- [x] 5.1.2 端到端场景：审批触发 + 批准 + 继续执行（7 个测试 — 通过/拒绝/Handoff+审批/full-auto/RunConfig 覆盖/多工具审批/流式审批）
- [x] 5.1.3 端到端场景：Tracing 完整链路验证（11 个测试 — 基本 Span/Tool Span/Handoff Span/全类型/token_usage/禁用/敏感数据/流式/Guardrail 拦截/workflow_name/审批+Tracing）
- [x] 5.1.4 综合管线测试（2 个测试 — 全能力协作/Guardrail 拦截终止）
- [x] 5.1.5 五轮代码审查（unused import 修复）

### Phase 5.2：性能测试 ✅
- [x] 5.2.1 并发 10 用户基准测试（4 个测试 — health/agents/sessions/token-usage 并发 10 线程全部 200/201）
- [x] 5.2.2 p95 API 响应 < 200ms 验证（8 个测试 — 6 端点 p95 断言 + 综合延迟报告 + token-usage summary）
- [x] 5.2.3 首 Token < 2s SSE 延迟验证（4 个测试 — 首事件 <2s/完整事件序列/p95/并发 5 流）
- [x] 5.2.4 综合基准（1 个测试 — 混合负载 10 并发 agent+session+health p95<200ms）
- [x] 5.2.5 五轮代码审查（unused import 清理 + mock 数据修复）

### Phase 5.3：文档与部署 ✅
- [x] 5.3.1 Docker Compose 一键部署指南（`docs/deployment-guide.md` — 快速部署/环境变量/运维命令/故障排查）
- [x] 5.3.2 用户手册（`docs/user-guide.md` — 登录/Agent 管理/对话/执行记录/监督面板/Provider 管理）
- [x] 5.3.3 API 文档最终校验（`docs/api-validation.md` — 26 端点全部实现/SSE 事件类型/后续迭代规划）
- [x] 5.3.4 Nginx SSE 代理路径修正（`/api/v1/chat/` → `/api/v1/sessions/.+/run`）
- [x] 5.3.5 五轮文档审查（全部通过）

---

## M6：迭代功能

### Phase 6.1：Trace 持久化与查询（P0）✅
- [x] 6.1.1 数据模型 — `TraceRecord`、`SpanRecord` ORM 模型 + Alembic 迁移 `0006_create_traces_spans.py`（9 索引）
- [x] 6.1.2 PostgresTraceProcessor — 实现 Framework TraceProcessor 接口，收集 Trace/Span 数据
- [x] 6.1.3 Trace 查询服务 — `list_traces`（多维筛选 + 分页）、`get_trace_detail`、`save_trace`
- [x] 6.1.4 Trace 查询 API — `GET /api/v1/traces`（列表）、`GET /api/v1/traces/{trace_id}`（详情含 Span 树）
- [x] 6.1.5 Schema 定义 — `SpanResponse`（alias input/output）、`TraceResponse`、`TraceDetailResponse`、`TraceListResponse`
- [x] 6.1.6 Session 集成 — `execute_run` 与 `execute_run_stream` 均注入 PostgresTraceProcessor
- [x] 6.1.7 后端测试 — 15 个测试（4 Schema + 6 API + 4 Processor + 1 路由验证），全部通过
- [x] 6.1.8 前端 Trace 服务 — `traceService.ts`（TypeScript 类型 + list/detail API）
- [x] 6.1.9 前端 TracesPage — ProTable 列表 + Agent 筛选 + 详情 Modal（Span 树 + Span 详情面板）
- [x] 6.1.10 路由 + 导航 — `/traces` 路由 + 侧边栏「Trace 追踪」菜单项
- [x] 6.1.11 五轮代码审查（2 个问题修复：flush 替代 commit + Pydantic model 序列化）

### Phase 6.2：Guardrails 配置化（P1）✅
- [x] 6.2.1 Framework 层 — `RegexGuardrail` 内置护栏类（支持 patterns + keywords + case_sensitive）
- [x] 6.2.2 数据模型 — `GuardrailRule` ORM + Alembic 迁移 `0007_create_guardrail_rules.py`（3 索引）
- [x] 6.2.3 CRUD 服务 — `create/list/get/update/delete` + `get_by_names` + regex/keyword 配置校验（正则预编译验证 + 长度限制）
- [x] 6.2.4 API 端点 — `POST/GET/PUT/DELETE /api/v1/guardrails` 5 个端点
- [x] 6.2.5 运行时桥接 — `_build_agent_from_config` 加载 GuardrailRule → 构造 InputGuardrail 注入 Agent
- [x] 6.2.6 后端测试 — 35 个测试（6 Schema + 8 API + 9 RegexGuardrail + 4 Agent集成 + 1 路由 + 7 校验），全部通过
- [x] 6.2.7 前端服务 — `guardrailService.ts`（TypeScript 类型 + CRUD API）
- [x] 6.2.8 前端 GuardrailRulesPage — ProTable 列表 + 创建/编辑 Modal（regex/keyword 切换）+ 启用开关 + 删除
- [x] 6.2.9 Agent 编辑页集成 — Input Guardrails 多选下拉框 + 保存到 `guardrails.input`
- [x] 6.2.10 路由 + 导航 — `/guardrails` 路由 + 侧边栏「Guardrail 护栏」菜单项
- [x] 6.2.11 前端类型修正 — `AgentConfig.guardrails` 接口修正为 `{ input, output, tool }`
- [x] 6.2.12 五轮代码审查（全部通过）

### Phase 6.3：Approval 人工审批（P1）✅
- [x] 6.3.1 数据模型 — `ApprovalRequest` ORM + Alembic 迁移 `0008_create_approval_requests.py`（4 索引）
- [x] 6.3.2 ApprovalManager 单例 — 进程内 `asyncio.Event` 事件管理（register/wait/resolve/cleanup）
- [x] 6.3.3 HttpApprovalHandler — 实现 Framework `ApprovalHandler` 接口（DB 记录 + 进程内等待 + 超时）
- [x] 6.3.4 CRUD 服务 — `list/get/resolve` + status/action 校验 + Manager 通知
- [x] 6.3.5 Schema — `ApprovalResolveRequest`/`ApprovalResponse`/`ApprovalListResponse`
- [x] 6.3.6 API 端点 — `GET /api/v1/approvals` + `GET /{id}` + `POST /{id}/resolve` 3 个端点
- [x] 6.3.7 运行时桥接 — `_build_agent_from_config` 传递 `approval_mode`，`execute_run/stream` 创建 `HttpApprovalHandler` 注入 `RunConfig`
- [x] 6.3.8 后端测试 — 32 个测试（5 Schema + 8 API + 8 Manager + 2 Handler + 4 Agent集成 + 1 路由 + 4 校验），全部通过
- [x] 6.3.9 前端服务 — `approvalService.ts`（TypeScript 类型 + list/get/resolve API）
- [x] 6.3.10 前端 ApprovalQueuePage — ProTable 审批队列 + 批准/拒绝按钮 + 拒绝原因 Modal
- [x] 6.3.11 路由 + 导航 — `/approvals` 路由 + 侧边栏「审批队列」菜单项
- [x] 6.3.12 五轮代码审查（1 个问题修复：handler DB 双写保护）

### Phase 6.4：Multi-Agent Handoff 编排（P0）✅
- [x] 6.4.1 `_resolve_handoff_agents` 递归解析 — 从 DB `AgentConfig.handoffs` 名称列表批量加载目标 Agent 配置，递归构建 Framework Agent 对象图
- [x] 6.4.2 循环引用检测 — `visited` 集合 + `_MAX_HANDOFF_DEPTH = 5` 深度限制，安全跳过并打印警告
- [x] 6.4.3 目标 Agent 完整构建 — 子 Agent 的 guardrails、approval_mode、model_settings 均从 DB 加载
- [x] 6.4.4 运行时桥接 — `execute_run` 和 `execute_run_stream` 均调用 `_resolve_handoff_agents`，传入 `handoff_agents` 构建主 Agent
- [x] 6.4.5 后端测试 — 18 个测试（4 构建 + 9 解析 + 2 常量 + 2 工具集成 + 1 运行集成），全部通过
- [x] 6.4.6 前端 UI — Agent 编辑页已有 Handoff 目标配置（逗号分隔输入），无需新增
- [x] 6.4.7 五轮代码审查通过，无阻塞问题

### Phase 6.5：MCP Server 配置管理（P1）✅
- [x] 6.5.1 数据模型 — `MCPServerConfig` ORM + Alembic 迁移 `0009_create_mcp_server_configs.py`（4 索引：name unique + org_id + transport_type + is_enabled）
- [x] 6.5.2 Schema — `MCPServerCreate`（transport_type 枚举校验 + model_validator 跨字段校验 stdio/command、sse+http/url）、`MCPServerUpdate`（PATCH 语义）、`MCPServerResponse`（auth_config 自动脱敏）、`MCPServerListResponse`
- [x] 6.5.3 CRUD 服务 — `create/list/get/update/delete` + `get_mcp_servers_by_names` 批量加载 + auth_config 加密存储（Fernet）+ 解密容错
- [x] 6.5.4 API 端点 — `POST/GET/PUT/DELETE /api/v1/mcp/servers` 5 个端点（create/update/delete 需 require_admin）
- [x] 6.5.5 运行时桥接 — `_resolve_mcp_tools(db, config)` 加载 MCP 配置 + 日志记录 + 缺失告警，返回空列表（MCP SDK 集成待后续）
- [x] 6.5.6 后端测试 — 37 个测试（13 Schema + 4 脱敏 + 8 API + 6 Service + 1 路由 + 2 ORM + 3 运行时桥接），全部通过
- [x] 6.5.7 前端服务 — `mcpServerService.ts`（TypeScript 类型 + CRUD API）
- [x] 6.5.8 前端 MCPServerPage — ProTable 列表 + 创建/编辑 Modal（transport_type 动态表单 + 环境变量 KEY=VALUE 编辑）+ 启用开关 + 删除
- [x] 6.5.9 路由 + 导航 — `/mcp-servers` 路由 + 侧边栏「MCP Server」菜单项
- [x] 6.5.10 五轮代码审查（1 个问题修复：write 端点 require_admin 安全加固）

### Phase 6.6：MCP SDK 集成（P0）✅
- [x] 6.6.1 Framework `mcp/` 模块 — `MCPServerConfig` 数据类（name/transport/command/url/args/env/headers/connect_timeout/tool_call_timeout）
- [x] 6.6.2 Framework `mcp/connection.py` — `connect_and_discover(stack, config)` 支持 stdio/sse/http 三种传输，工具以 `{server_name}::{tool_name}` 命名空间隔离
- [x] 6.6.3 MCP SDK 可选依赖 — `pyproject.toml` 新增 `[mcp]` extras（`mcp>=1.0.0`）
- [x] 6.6.4 Backend 运行时桥接 — `_resolve_mcp_tools(db, config, stack)` 通过 `AsyncExitStack` 管理 MCP 连接生命周期，`execute_run`/`execute_run_stream` 均接入
- [x] 6.6.5 FunctionTool `**kwargs` 参数透传修复 — MCP 工具调用正确传递所有参数
- [x] 6.6.6 安全降级 — `connect_and_discover` 中 `_ensure_mcp_installed()` + backend 捕获 `ImportError` 优雅降级
- [x] 6.6.7 Framework 测试 — 29 个新测试（MCPServerConfig 5 + _ensure_mcp_installed 2 + _create_mcp_tool 8 + _discover_tools 4 + connect_and_discover 8 + kwargs 修复 1 + 原有 15 FunctionTool）
- [x] 6.6.8 Backend 测试 — 11 个新测试（_resolve_mcp_tools 7 + _build_agent_from_config 4）
- [x] 6.6.9 五轮代码审查（2 个问题修复：FunctionTool **kwargs bug + ImportError 优雅降级）

### Phase 6.7：Agent 即工具 / Agent-as-Tool（P0）✅
- [x] 6.7.1 数据模型 — Alembic 迁移 `0010_add_agent_tools.py`：`agent_tools ARRAY(String) NOT NULL DEFAULT '{}'`
- [x] 6.7.2 ORM 模型 — `AgentConfig.agent_tools` 字段（`ARRAY(String)`）
- [x] 6.7.3 Schema — `AgentCreate` / `AgentUpdate` / `AgentResponse` 增加 `agent_tools` 字段
- [x] 6.7.4 Backend `_resolve_agent_tools()` — 递归解析 Agent-as-Tool 名称列表为 `FunctionTool`，含循环检测（`visited` 集合）+ 深度限制（`_MAX_AGENT_TOOL_DEPTH = 3`）
- [x] 6.7.5 `execute_run` 集成 — 轻量 `sub_run_config`（共享 model_provider，无 trace/approval）+ 工具合并（mcp_tools + agent_tool_fns）
- [x] 6.7.6 `execute_run_stream` 集成 — 同上模式 + 异常时清理 mcp_stack
- [x] 6.7.7 Frontend TypeScript 接口 — `AgentConfig.agent_tools` / `AgentCreateInput.agent_tools`
- [x] 6.7.8 Frontend Agent 编辑页 — Agent-as-Tool 多选表单字段（排除自身）
- [x] 6.7.9 Backend 测试 — 12 个新测试（_resolve_agent_tools 7 + _build_agent_from_config 1 + Schema 4）
- [x] 6.7.10 五轮代码审查（1 个问题修复：execute_run_stream model_override 缺失）

### Phase 6.8：Tool Groups 工具组管理（P0）✅
- [x] 6.8.1 Framework `ToolGroup` dataclass — name/tools/description，register/get_tool/tool_names 方法
- [x] 6.8.2 Framework `ToolRegistry` — 全局工具注册表单例，register_group/get_group/list_groups/get_tool/remove_group/clear
- [x] 6.8.3 数据模型 — Alembic 迁移 `0011_create_tool_group_configs.py`：name/description/tools(JSONB)/source/is_enabled
- [x] 6.8.4 ORM 模型 — `ToolGroupConfig` 完整字段定义
- [x] 6.8.5 Schema — `ToolGroupCreate` / `ToolGroupUpdate` / `ToolGroupResponse` / `ToolDefinition` / `ToolGroupListResponse`
- [x] 6.8.6 Service — `list_tool_groups` / `get_tool_group_by_name` / `create_tool_group` / `update_tool_group` / `delete_tool_group`
- [x] 6.8.7 API Endpoints — `GET/POST /tool-groups`、`GET/PUT/DELETE /tool-groups/{name}`
- [x] 6.8.8 Runtime `_resolve_tool_groups()` — 从 DB 加载工具组，构建 FunctionTool（fn=None），三路合并（mcp + agent_tools + tg_tools）
- [x] 6.8.9 Frontend `toolGroupService.ts` — list/get/create/update/delete
- [x] 6.8.10 Frontend `ToolGroupPage.tsx` — 工具组管理页（ProTable + 创建/编辑/删除 Modal）
- [x] 6.8.11 Frontend Agent 编辑页升级 — tool_groups 从逗号分隔文本改为多选 Select（从 API 加载选项）
- [x] 6.8.12 Frontend 导航菜单 — 新增"工具组"入口
- [x] 6.8.13 Framework 测试 — 14 个新测试（ToolGroup 6 + ToolRegistry 8）
- [x] 6.8.14 Backend 测试 — 12 个新测试（Schema 4 + Service 2 + _resolve_tool_groups 6）
- [x] 6.8.15 五轮代码审查（2 处未使用 import 移除）

### Phase 6.9：端到端集成测试（P0）✅
- [x] 6.9.1 Framework E2E — `test_e2e_phase69.py` 15 个测试：
  - Agent-as-Tool 管线 6 个：Manager 调用子 Agent、子 Agent 自带工具、Agent-as-Tool + Handoff、审批控制、流式模式、Session 隔离
  - ToolGroup 管线 4 个：ToolGroup 工具执行、多组工具合并、ToolRegistry 提供工具、ToolGroup + Guardrail 共存
  - 综合管线 5 个：全能力协同（Guardrail+Agent-as-Tool+Handoff+ToolGroup+Approval+Tracing+Session）、Guardrail 拦截终止、流式综合管线、多 Agent-as-Tool 依次调用、Token 聚合
- [x] 6.9.2 Backend E2E — `test_e2e_backend.py` 15 个测试：
  - _build_agent_from_config 综合 3 个：三路工具合并、Guardrail+Handoff 同配、最小配置
  - 三路工具解析 2 个：全源解析、部分源解析
  - Handoff/Agent-as-Tool 交叉 2 个：同 Agent 双配、多目标不混淆
  - 综合构建 2 个：全特性 Agent 构建、regex+keyword Guardrail 混合
  - Token Usage 提取 3 个：正常提取、None trace、无 LLM span
  - _find_parent_agent_name 3 个：正常查找、无父 span、父非 agent 类型
- [x] 6.9.3 全量测试运行 — Framework 242 + Backend 346 = 588 全部通过
- [x] 6.9.4 五轮代码审查（3 处未使用 import 移除）

### Phase 6.10：MCP Server 管理前端完善（P1）✅
- [x] 6.10.1 后端 Schema — `MCPToolInfo`（name/description/parameters_schema）+ `MCPTestResult`（success/tools/error/duration_ms）
- [x] 6.10.2 后端 Service — `test_mcp_connection()`：解密 auth_config → FrameworkMCPConfig(timeout=15s) → connect_and_discover → 返回工具列表或错误
- [x] 6.10.3 后端 API — `POST /api/v1/mcp/servers/{id}/test`（require_admin）
- [x] 6.10.4 前端 Service — `MCPToolInfo`/`MCPTestResult` 接口 + `testConnection()` 方法
- [x] 6.10.5 前端 MCPServerPage 增强：
  - **认证配置 KV 编辑器**：Form.List 动态键值对编辑，Input.Password 输入，编辑时 *** 脱敏值不回填
  - **连接测试按钮**：表格操作列增加「测试」按钮（ThunderboltOutlined）
  - **工具预览 Modal**：连接成功显示 Result + Table 列出发现的工具名称和描述
- [x] 6.10.6 全量测试 — TypeScript 零错误 + Framework 242 + Backend 346 = 588 全部通过
- [x] 6.10.7 五轮代码审查（均通过）

---

## M7：高级能力

### Phase 7.1：Runner Lifecycle Hooks（P1）✅
- [x] 7.1.1 Framework `hooks.py` — `RunHooks` dataclass（10 个钩子字段：on_run_start/end、on_agent_start/end、on_llm_start/end、on_tool_start/end、on_handoff、on_error）
- [x] 7.1.2 Framework `_invoke_hook()` — 安全异步调用辅助函数（异常捕获 + logger.exception，非阻塞语义）
- [x] 7.1.3 `RunConfig.hooks` 字段 — 替换旧 4 个未使用回调（on_agent_start/end/on_tool_call/on_handoff）为统一 `hooks: RunHooks | None`
- [x] 7.1.4 `Runner.run()` 嵌入 — 6 个触发点（run_start/end + agent_start/end + llm_start/end）+ 错误路径 on_error + 3 个退出路径 on_run_end
- [x] 7.1.5 `Runner.run_streamed()` 嵌入 — 与 run() 对称的 6 个触发点 + 流式异常处理
- [x] 7.1.6 `_execute_tool_calls()` 嵌入 — on_tool_start/end（每次工具调用前后）+ on_handoff（Handoff 检测时）
- [x] 7.1.7 `__init__.py` 导出 — `RunHooks` 加入公共 API
- [x] 7.1.8 Framework 测试 — `test_lifecycle_hooks.py` 11 个测试（_invoke_hook 基础 3 + 简单对话 hook 顺序 2 + 工具 hook 1 + Handoff hook 1 + 错误 hook 2 + 异常非阻塞 1 + 无 hook 兼容 1）
- [x] 7.1.9 全量测试 — Framework 330 + Backend 364 = 694 全部通过（排除需 API Key 的集成测试）
- [x] 7.1.10 五轮代码审查（2 个问题修复：docstring 示例 ctx.trace → ctx.agent.name + on_run_end 签名文档更正）

### Phase 7.2：任务执行可视化（P1）✅
- [x] 7.2.1 `SpanWaterfall` 组件 — 纯 CSS Waterfall 时间轴（横向条形图）
  - 颜色编码：agent=蓝、llm=绿、tool=橙、handoff=紫、guardrail=红
  - 父子层级缩进、按 start_time 排序、duration 百分比定位
  - Hover 高亮 + 点击联动 Span 详情面板
  - Tooltip 显示类型/名称/耗时/模型/Token/状态
  - 底部时间轴刻度（0% 25% 50% 75% 100%）
  - Duration fallback（duration_ms → end_time-start_time → 1ms min）
  - 空状态处理 + useMemo 缓存计算
- [x] 7.2.2 TracesPage 集成 — Trace 详情 Modal 新增「Span Waterfall 时间轴」Card，Modal 宽度 960→1100
- [x] 7.2.3 零新依赖 — 纯 Ant Design + CSS 实现，无 ECharts 等重型库
- [x] 7.2.4 TypeScript 零错误
- [x] 7.2.5 五轮代码审查（全部通过）

### Phase 7.3：Agent 版本管理（P1）✅
- [x] 7.3.1 数据模型 — `AgentConfigVersion` ORM + Alembic 迁移 `0013_create_agent_config_versions.py`（2 索引 + UniqueConstraint agent_config_id+version）
- [x] 7.3.2 Pydantic Schema — `AgentVersionResponse`/`AgentVersionListResponse`/`AgentVersionDiffResponse`/`AgentRollbackRequest`
- [x] 7.3.3 Service 层 — `_snapshot_from_agent`（完整配置快照提取）、`_next_version`（自增版本号）、`create_version`/`list_versions`/`get_version`/`rollback_to_version`/`get_agent_by_id`
- [x] 7.3.4 API 端点 — `GET /agents/{id}/versions`（列表）、`GET /{id}/versions/{version}`（详情）、`POST /{id}/versions/{version}/rollback`（回滚）、`GET /{id}/versions/diff?v1=X&v2=Y`（对比）
- [x] 7.3.5 自动快照 — `create_agent` 创建时 v1 快照（同一事务内）、`update_agent` 更新前快照（记录变更字段）
- [x] 7.3.6 路由注册 — `agent_versions_router` 注册到 FastAPI app
- [x] 7.3.7 后端测试 — 18 个测试（5 Schema + 11 API + 2 Service _snapshot_from_agent），全部通过
- [x] 7.3.8 前端 Service — `agentVersionService.ts`（list/get/rollback/diff API）
- [x] 7.3.9 前端 AgentVersionPage — 版本列表 ProTable + 快照详情 Modal + 版本对比 Modal（字段级高亮变更）+ 回滚操作
- [x] 7.3.10 前端集成 — Agent 列表页增加「版本」操作入口 + `/agents/:agentId/versions` 路由
- [x] 7.3.11 TypeScript 零错误
- [x] 7.3.12 全量测试 — Framework 372 + Backend 382 = 754 全部通过
- [x] 7.3.13 五轮代码审查（1 个问题修复：create_agent 事务隔离 — flush 替代首次 commit 确保 Agent+版本同事务提交）

### Phase 7.4：LLM-based Guardrails 配置化（P1）✅
- [x] 7.4.1 Framework 基础设施确认 — `LLMGuardrail`（基类 evaluate + JSON 解析 + timeout/fail-open + as_input_fn/as_output_fn/as_tool_before_fn/as_tool_after_fn）、`PromptInjectionGuardrail`（预设 threshold=0.7）、`ContentSafetyGuardrail`（预设 threshold=0.75）已就绪
- [x] 7.4.2 Backend — `_validate_config` 扩展 mode="llm"（preset 枚举、custom 必须 {content} 模板、threshold 0-1、model 字符串校验）
- [x] 7.4.3 Backend Schema — `GuardrailRuleCreate`/`Update` mode validator 放开 "llm"，description 更新
- [x] 7.4.4 Backend Bridge — `_build_agent_from_config` 新增 LLM 分支（prompt_injection→PromptInjectionGuardrail、content_safety→ContentSafetyGuardrail、custom→LLMGuardrail），input/output/tool 三类型全支持
- [x] 7.4.5 Frontend — GuardrailRulesPage 新增 LLM 模式（MODE_OPTIONS + LLM_PRESET_OPTIONS、preset/model/threshold/prompt_template 表单、mode 列 purple Tag、规则数列显示 preset）
- [x] 7.4.6 后端测试 — 新增 3 个 Schema 测试 + 11 个 Service _validate_config 测试 + 3 个 API 端点测试 = 17 个 LLM 模式测试；修复旧测试 test_rule_create_invalid_mode（"llm"→"magic"）
- [x] 7.4.7 Framework 测试 — 已有 24 个 LLM Guardrail 测试覆盖（TestLLMGuardrail 11 + TestPromptInjectionGuardrail 5 + TestContentSafetyGuardrail 6）
- [x] 7.4.8 全量测试 — Framework 372 + Backend 399 = 771 全部通过，TypeScript 零错误
- [x] 7.4.9 五轮代码审查（2 个问题修复：Schema description 缺 "llm" + 前端 InputNumber 替换 Input type="number" 避免字符串类型问题）

### Phase 7.5：Agent Handoff 可视化编排（P0）✅
- [x] 7.5.1 安装依赖 — `@xyflow/react` v12 + `@dagrejs/dagre` v3
- [x] 7.5.2 HandoffEditorPage — ReactFlow 画布，自定义 AgentNode（name + model + handoff 数量），拖拽连线创建 Handoff 关系
- [x] 7.5.3 dagre 自动布局 — TB 方向（上→下），nodesep=60 ranksep=80
- [x] 7.5.4 循环检测 — DFS 检测循环引用，显示 Warning Tag（不阻断保存，Framework 有 _MAX_HANDOFF_DEPTH=5 保护）
- [x] 7.5.5 智能保存 — diff 比对初始快照，只更新变更的 Agent，批量 PUT
- [x] 7.5.6 悬挂引用过滤 — 加载时忽略 handoff_targets 中不存在的 Agent
- [x] 7.5.7 路由集成 — `/agents/handoff-editor` 路由 + Agent 列表页 "Handoff 编排" 按钮入口
- [x] 7.5.8 TypeScript 零错误
- [x] 7.5.9 全量测试 — Framework 372 + Backend 399 = 771 全部通过
- [x] 7.5.10 五轮代码审查（1 个问题修复：Card bodyStyle → styles.body 适配 Ant Design 5.x）

### Phase 7.6：Runner 并行工具执行优化（P0）✅
- [x] 7.6.1 RunConfig 新增 `tool_timeout: float | None`（全局工具执行超时，当 FunctionTool 无自身 timeout 时生效）
- [x] 7.6.2 _execute_tool_calls 重构 — Handoff 检测 + 普通工具 asyncio.TaskGroup 并行执行
- [x] 7.6.3 超时优先级 — FunctionTool.timeout > RunConfig.tool_timeout > 无限
- [x] 7.6.4 结果顺序保证 — dict 收集结果后按原始 tool_call 顺序追加到 messages
- [x] 7.6.5 单工具优化 — 单个工具直接 await，跳过 TaskGroup 开销
- [x] 7.6.6 异常隔离 — _run_one 内完整 try/except，单工具失败不影响其他
- [x] 7.6.7 Handoff 兼容 — 首个 Handoff 之前的普通工具并行执行，然后 Handoff 控制权转移
- [x] 7.6.8 测试 — 新增 9 个测试（5 并行 + 4 超时），覆盖并行执行时间验证、消息顺序、异常隔离、Handoff 混合、超时优先级
- [x] 7.6.9 全量测试 — Framework 381 + Backend 399 = 780 全部通过
- [x] 7.6.10 五轮代码审查（无问题）

### Phase 7.7：Multi-Provider 多模型厂商管理（P1）✅
- [x] 7.7.1 LiteLLMProvider `__init__` 增强 — 支持 `api_key`, `api_base`, `extra_headers` 构造参数，条件注入到 `litellm.acompletion` kwargs
- [x] 7.7.2 AgentConfig 新增 `provider_name` 字段 — Alembic migration 0014 + ORM + Schema（Create/Update/Response）
- [x] 7.7.3 `_resolve_provider(db, agent_config)` 运行时桥接 — 根据 provider_name 加载 ProviderConfig，解密 API Key，构建 LiteLLMProvider 构造参数
- [x] 7.7.4 `execute_run` / `execute_run_stream` 接入 — 调用 `_resolve_provider`，LiteLLMProvider 和子 Agent RunConfig 均使用 provider_kwargs
- [x] 7.7.5 Provider 连通性测试 — `POST /api/v1/providers/{id}/test` 端点，`_DEFAULT_TEST_MODELS` 覆盖 9 种 provider_type，更新 health_status
- [x] 7.7.6 前端 Provider 测试按钮 — ProviderListPage 增加⚡测试按钮 + 结果 Modal（成功/失败/延迟/模型）
- [x] 7.7.7 前端 Agent 编辑页 Provider 选择器 — AgentEditPage 增加 Provider Select（加载启用的 Provider，allowClear，保存/加载 provider_name）
- [x] 7.7.8 Agent 版本快照 — `_snapshot_from_agent` 包含 `provider_name`
- [x] 7.7.9 测试 — Framework 新增 6 个（LiteLLMProvider init），Backend 新增 21 个（ProviderTestResult/API/DefaultModels/AgentProviderNameSchema/ResolveProvider），全量 Framework 387 + Backend 399 = 786 通过
- [x] 7.7.10 五轮代码审查（无问题）

### Phase 7.8：Session 持久化 — SQLAlchemySessionBackend（P0）✅
- [x] 7.8.1 数据模型 — Alembic 迁移 `0015_create_session_messages.py`：`session_messages` 表（BIGSERIAL PK, session_id, role, content, agent_name, tool_call_id, tool_calls JSONB, token_usage JSONB, metadata_ JSONB, created_at）+ 组合索引 `(session_id, id)`；`session_metadata` 表（session_id PK, message_count, total_tokens, last_agent, extra JSONB, created_at, updated_at）
- [x] 7.8.2 ORM 模型 — `SessionMessage`（session_messages 表）+ `SessionMetadataRecord`（session_metadata 表），`backend/app/models/session_message.py`
- [x] 7.8.3 `SQLAlchemySessionBackend` — 实现 Framework `SessionBackend` 接口（load/save/delete/list_sessions/load_metadata），使用 SQLAlchemy AsyncSession + flush（不 commit，由外层事务控制）
- [x] 7.8.4 `execute_run` / `execute_run_stream` 接入 — 替换 `InMemorySessionBackend()` 为 `SQLAlchemySessionBackend(db)`，消息跨请求持久化
- [x] 7.8.5 消息查询 API — `GET /api/v1/sessions/{session_id}/messages` 返回 `SessionMessagesResponse`（session_id, messages[], total）
- [x] 7.8.6 Schema — `SessionMessageItem`（id, role, content, agent_name, tool_call_id, tool_calls, token_usage, created_at）+ `SessionMessagesResponse`
- [x] 7.8.7 测试 — 20 个新测试（3 Schema + 2 Load + 3 Save + 1 Delete + 3 Metadata + 3 API + 4 ORM + 1 路由），全量 Framework 387 + Backend 419 = 806 通过
- [x] 7.8.8 五轮代码审查（无问题）

---

*最后更新：2025-07-22*
