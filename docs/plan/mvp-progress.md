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

### Phase 5.3：文档与部署
- [ ] 5.3.1 Docker Compose 一键部署指南
- [ ] 5.3.2 用户手册（创建 Agent + 对话 + 查看执行记录）
- [ ] 5.3.3 API 文档最终校验

---

*最后更新：2025-07-18*
