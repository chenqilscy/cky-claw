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

---

*最后更新：2025-07-22*
