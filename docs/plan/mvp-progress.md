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

### Phase 2.1：Agent CRUD API
- [ ] 2.1.1 AgentConfig SQLAlchemy 模型
- [ ] 2.1.2 Alembic 迁移：agent_configs 表
- [ ] 2.1.3 Agent CRUD API（创建/查看/列表/编辑/删除）
- [ ] 2.1.4 Agent API 单元测试

### Phase 2.2：对话 API + SSE
- [ ] 2.2.1 Session/Run SQLAlchemy 模型 + 迁移
- [ ] 2.2.2 创建 Session + 发起 Run API
- [ ] 2.2.3 SSE 流式事件输出端点
- [ ] 2.2.4 Runner 与 FastAPI 集成（后台任务 + 事件推送）
- [ ] 2.2.5 对话 API 测试

### Phase 2.3：用户认证
- [ ] 2.3.1 User 模型 + 迁移
- [ ] 2.3.2 注册/登录 API（JWT）
- [ ] 2.3.3 认证中间件（依赖注入 current_user）
- [ ] 2.3.4 2 个角色：Admin + User

### Phase 2.4：前端对话页
- [ ] 2.4.1 对话页 UI（消息列表 + 输入框 + 流式渲染）
- [ ] 2.4.2 SSE 客户端（EventSource 封装）
- [ ] 2.4.3 Agent 选择器
- [ ] 2.4.4 对话历史列表

### Phase 2.5：前端 Agent 管理页
- [ ] 2.5.1 Agent 列表页（ProTable）
- [ ] 2.5.2 Agent 创建/编辑表单（ProForm）
- [ ] 2.5.3 登录页对接后端认证

## M3：编排与 Tracing

### Phase 3.1：Handoff 机制
- [ ] 3.1.1 Handoff 定义 + transfer_to 工具生成
- [ ] 3.1.2 Runner Agent Loop Handoff 分支（Agent 切换 + 消息历史传递）
- [ ] 3.1.3 InputFilter 历史过滤
- [ ] 3.1.4 Handoff 测试（Triage → Specialist）

### Phase 3.2：Agent-as-Tool
- [ ] 3.2.1 Agent.as_tool() 封装
- [ ] 3.2.2 Runner 中 AgentTool 的递归执行
- [ ] 3.2.3 Agent-as-Tool 测试

### Phase 3.3：Tracing 自动采集
- [ ] 3.3.1 Runner 中自动创建 Trace + Agent/LLM/Tool Span
- [ ] 3.3.2 TraceProcessor 回调触发
- [ ] 3.3.3 PostgreSQL TraceProcessor（Trace/Span 写入数据库）
- [ ] 3.3.4 ConsoleTraceProcessor（调试用）
- [ ] 3.3.5 Tracing 数据模型 + 迁移

### Phase 3.4：Token 审计基础
- [ ] 3.4.1 TokenUsageLog 模型 + 迁移
- [ ] 3.4.2 LLM Span 自动填充 token_usage
- [ ] 3.4.3 Token 统计查询 API

### Phase 3.5：前端执行记录页
- [ ] 3.5.1 执行列表页（Run 列表 + 状态/时间/Token）
- [ ] 3.5.2 Span 详情展示（树形结构）

## M4：监督与安全

### Phase 4.1：Input Guardrail
- [ ] 4.1.1 InputGuardrail 执行（Runner 中 blocking/parallel 模式）
- [ ] 4.1.2 基础 Prompt 注入检测护栏
- [ ] 4.1.3 GuardrailResult → TripwireTriggered 错误处理
- [ ] 4.1.4 Guardrail 测试

### Phase 4.2：Approval Mode
- [ ] 4.2.1 ApprovalHandler 接口实现（WebSocket 推送 + 等待响应）
- [ ] 4.2.2 suggest 模式 Runner 集成
- [ ] 4.2.3 审批请求 API（创建/查询/批准/拒绝）
- [ ] 4.2.4 审批超时处理

### Phase 4.3：监督面板
- [ ] 4.3.1 活跃会话列表 API
- [ ] 4.3.2 前端监督面板（会话列表 + 只读对话查看）
- [ ] 4.3.3 审批操作 UI（WebSocket 实时推送）

### Phase 4.4：Model Provider 管理
- [ ] 4.4.1 ProviderConfig 模型 + 迁移
- [ ] 4.4.2 Provider CRUD API（API Key 加密存储）
- [ ] 4.4.3 Provider 管理前端页面

### Phase 4.5：Token 统计
- [ ] 4.5.1 按用户/模型 Token 消耗查询 API
- [ ] 4.5.2 Token 统计基础前端页面

## M5：MVP 完整交付

### Phase 5.1：集成测试
- [ ] 5.1.1 端到端场景：对话 + Handoff + 工具调用
- [ ] 5.1.2 端到端场景：审批触发 + 批准 + 继续执行
- [ ] 5.1.3 端到端场景：Tracing 完整链路验证

### Phase 5.2：性能测试
- [ ] 5.2.1 并发 10 用户基准测试
- [ ] 5.2.2 p95 API 响应 < 200ms 验证
- [ ] 5.2.3 首 Token < 2s SSE 延迟验证

### Phase 5.3：文档与部署
- [ ] 5.3.1 Docker Compose 一键部署指南
- [ ] 5.3.2 用户手册（创建 Agent + 对话 + 查看执行记录）
- [ ] 5.3.3 API 文档最终校验

---

*最后更新：2025-07-15*
