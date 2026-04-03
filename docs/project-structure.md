# CkyClaw 项目目录结构说明

## 顶层结构

```
cky-claw/
├── AGENTS.md                  # AI 代理协作规则与编码规范
├── README.md                  # 项目总览
├── docker-compose.yml         # 开发环境基础设施（PostgreSQL、Redis）
├── .env.example               # 环境变量模板
├── .editorconfig              # 编辑器统一配置
├── .gitignore
├── .gitattributes
├── ckyclaw-framework/         # CkyClaw Framework — Python Agent 运行时库
├── backend/                   # CkyClaw Backend — FastAPI 后端服务
├── frontend/                  # CkyClaw Frontend — React Web 前端
├── docs/                      # 产品与技术文档
└── .github/                   # GitHub Actions CI + 编辑器指令
```

---

## ckyclaw-framework/ — Agent 运行时库

自研 Python Agent Framework，提供 Agent 编排、工具执行、Guardrails、Tracing 等核心能力。

```
ckyclaw-framework/
├── pyproject.toml                        # 包定义与依赖（uv 管理）
├── py.typed                              # PEP 561 类型标记
├── README.md
├── uv.lock
├── ckyclaw_framework/
│   ├── __init__.py
│   ├── _internal/
│   │   └── types.py                      # 内部共享类型
│   ├── agent/
│   │   ├── agent.py                      # Agent 核心定义
│   │   ├── config.py                     # Agent 配置模型
│   │   └── output.py                     # Agent 输出类型
│   ├── approval/
│   │   ├── handler.py                    # 审批处理器
│   │   └── mode.py                       # 审批模式枚举
│   ├── guardrails/
│   │   ├── input_guardrail.py            # 输入护栏
│   │   ├── output_guardrail.py           # 输出护栏
│   │   ├── tool_guardrail.py             # 工具调用护栏
│   │   ├── tool_whitelist_guardrail.py   # 工具白名单护栏
│   │   ├── content_safety_guardrail.py   # 内容安全护栏
│   │   ├── pii_guardrail.py              # PII 检测护栏
│   │   ├── prompt_injection_guardrail.py # 提示注入检测护栏
│   │   ├── regex_guardrail.py            # 正则表达式护栏
│   │   ├── llm_guardrail.py              # LLM 护栏
│   │   ├── max_token_guardrail.py        # Token 上限护栏
│   │   └── result.py                     # 护栏结果类型
│   ├── handoff/
│   │   └── handoff.py                    # Agent 交接（Handoff）机制
│   ├── mcp/
│   │   ├── connection.py                 # MCP 连接管理
│   │   └── server.py                     # MCP Server 封装
│   ├── model/
│   │   ├── provider.py                   # 模型提供商抽象
│   │   ├── litellm_provider.py           # LiteLLM 统一适配
│   │   ├── message.py                    # 消息类型定义
│   │   ├── settings.py                   # 模型调用设置
│   │   └── _converter.py                 # 消息格式转换
│   ├── runner/
│   │   ├── runner.py                     # Agent Runner 主循环
│   │   ├── run_config.py                 # 运行配置
│   │   ├── run_context.py                # 运行上下文
│   │   ├── hooks.py                      # 生命周期钩子
│   │   └── result.py                     # 运行结果
│   ├── session/
│   │   ├── session.py                    # Session 抽象接口
│   │   ├── in_memory.py                  # 内存 Session 实现
│   │   ├── postgres.py                   # PostgreSQL Session 实现
│   │   └── history_trimmer.py            # 历史消息裁剪
│   ├── tools/
│   │   ├── function_tool.py              # 函数工具定义
│   │   ├── tool_registry.py              # 工具注册表
│   │   ├── tool_group.py                 # 工具分组
│   │   └── tool_context.py               # 工具执行上下文
│   └── tracing/
│       ├── trace.py                      # Trace 定义
│       ├── span.py                       # Span 定义
│       ├── processor.py                  # Trace 处理器抽象
│       └── console_processor.py          # 控制台 Trace 输出
└── tests/                                # 单元测试与集成测试
    ├── test_smoke.py
    ├── test_runner.py
    ├── test_agent_as_tool.py
    ├── test_handoff.py
    ├── test_approval.py
    ├── test_builtin_guardrails.py
    ├── test_input_guardrail.py
    ├── test_output_guardrail.py
    ├── test_tool_guardrail.py
    ├── test_function_tool.py
    ├── test_tool_group.py
    ├── test_model_provider.py
    ├── test_session.py
    ├── test_tracing.py
    ├── test_mcp_integration.py
    ├── test_lifecycle_hooks.py
    ├── test_runconfig_guardrails.py
    ├── test_integration.py
    ├── test_e2e_integration.py
    └── test_e2e_phase69.py
```

---

## backend/ — FastAPI 后端服务

提供 Agent 配置管理、Session 管理、审批、Token 用量统计等 REST API。

```
backend/
├── pyproject.toml              # 包定义与依赖
├── alembic.ini                 # Alembic 迁移配置
├── Dockerfile                  # 后端 Docker 镜像
├── entrypoint.sh               # 容器入口脚本
├── README.md
├── uv.lock
├── alembic/
│   ├── env.py                  # Alembic 运行环境
│   ├── script.py.mako          # 迁移脚本模板
│   └── versions/               # 数据库迁移脚本（0001–0015）
├── app/
│   ├── main.py                 # FastAPI 应用入口
│   ├── core/
│   │   ├── config.py           # 应用配置（Settings）
│   │   ├── database.py         # 数据库引擎与会话
│   │   ├── deps.py             # 依赖注入
│   │   ├── auth.py             # 认证逻辑
│   │   ├── crypto.py           # 加密工具
│   │   ├── exceptions.py       # 全局异常定义
│   │   └── middleware.py       # 中间件
│   ├── models/                 # SQLAlchemy ORM 模型
│   │   ├── agent.py
│   │   ├── agent_version.py
│   │   ├── session.py
│   │   ├── session_message.py
│   │   ├── user.py
│   │   ├── provider.py
│   │   ├── token_usage.py
│   │   ├── trace.py
│   │   ├── guardrail.py
│   │   ├── approval.py
│   │   ├── mcp_server.py
│   │   └── tool_group.py
│   ├── schemas/                # Pydantic 请求/响应模型
│   │   ├── agent.py
│   │   ├── agent_version.py
│   │   ├── session.py
│   │   ├── auth.py
│   │   ├── provider.py
│   │   ├── token_usage.py
│   │   ├── trace.py
│   │   ├── guardrail.py
│   │   ├── approval.py
│   │   ├── supervision.py
│   │   ├── mcp_server.py
│   │   └── tool_group.py
│   ├── api/                    # API 路由层
│   │   ├── agents.py           # Agent CRUD
│   │   ├── agent_versions.py   # Agent 版本管理
│   │   ├── sessions.py         # Session 管理
│   │   ├── auth.py             # 认证
│   │   ├── health.py           # 健康检查
│   │   ├── providers.py        # LLM 提供商配置
│   │   ├── token_usage.py      # Token 用量统计
│   │   ├── traces.py           # Trace 查询
│   │   ├── guardrails.py       # 护栏规则管理
│   │   ├── approvals.py        # 审批管理
│   │   ├── supervision.py      # 监督面板
│   │   ├── mcp_servers.py      # MCP Server 配置
│   │   └── tool_groups.py      # 工具分组管理
│   └── services/               # 业务逻辑层
│       ├── agent.py
│       ├── agent_version.py
│       ├── session.py
│       ├── session_backend.py
│       ├── auth.py
│       ├── provider.py
│       ├── token_usage.py
│       ├── trace.py
│       ├── trace_processor.py
│       ├── guardrail.py
│       ├── approval.py
│       ├── approval_handler.py
│       ├── approval_manager.py
│       ├── supervision.py
│       ├── mcp_server.py
│       └── tool_group.py
├── scripts/
│   └── create_db.py            # 数据库初始化脚本
└── tests/                      # 后端测试
    ├── test_smoke.py
    ├── test_agent_crud.py
    ├── test_agent_version.py
    ├── test_agent_as_tool.py
    ├── test_approvals.py
    ├── test_auth.py
    ├── test_guardrails.py
    ├── test_mcp_servers.py
    ├── test_mcp_integration.py
    ├── test_output_guardrail.py
    ├── test_performance.py
    ├── test_provider.py
    ├── test_session_api.py
    ├── test_session_messages.py
    ├── test_supervision.py
    ├── test_token_usage.py
    ├── test_tool_groups.py
    ├── test_traces.py
    ├── test_handoff_orchestration.py
    └── test_e2e_backend.py
```

---

## frontend/ — React Web 前端

基于 React 18 + Ant Design 5 + TanStack Query 的管理界面。

```
frontend/
├── package.json                # 依赖与脚本
├── pnpm-lock.yaml
├── tsconfig.json
├── tsconfig.node.json
├── vite.config.ts              # Vite 构建配置
├── eslint.config.js
├── index.html                  # 入口 HTML
├── Dockerfile                  # 前端 Docker 镜像
├── nginx.conf                  # Nginx 配置
├── src/
│   ├── main.tsx                # 应用入口
│   ├── App.tsx                 # 路由定义
│   ├── vite-env.d.ts
│   ├── components/
│   │   └── ErrorBoundary.tsx   # 全局错误边界
│   ├── layouts/
│   │   └── BasicLayout.tsx     # 主布局（侧边栏 + 内容区）
│   ├── pages/
│   │   ├── Login.tsx           # 登录页
│   │   ├── NotFoundPage.tsx    # 404 页面
│   │   ├── dashboard/
│   │   │   └── DashboardPage.tsx    # 平台概览面板
│   │   ├── agents/
│   │   │   ├── AgentListPage.tsx    # Agent 列表
│   │   │   ├── AgentEditPage.tsx    # Agent 编辑
│   │   │   ├── AgentVersionPage.tsx # Agent 版本历史
│   │   │   └── HandoffEditorPage.tsx # Handoff 编排编辑器
│   │   ├── chat/
│   │   │   ├── ChatPage.tsx         # 对话主页面
│   │   │   ├── ChatSidebar.tsx      # 会话侧边栏
│   │   │   └── ChatWindow.tsx       # 对话窗口
│   │   ├── runs/
│   │   │   └── RunListPage.tsx      # 运行记录
│   │   ├── traces/
│   │   │   ├── TracesPage.tsx       # Trace 列表
│   │   │   └── SpanWaterfall.tsx    # Span 瀑布图
│   │   ├── approvals/
│   │   │   └── ApprovalQueuePage.tsx # 审批队列
│   │   ├── supervision/
│   │   │   └── SupervisionPage.tsx  # 监督面板
│   │   ├── guardrails/
│   │   │   └── GuardrailRulesPage.tsx # 护栏规则管理
│   │   ├── providers/
│   │   │   ├── ProviderListPage.tsx  # 提供商列表
│   │   │   └── ProviderEditPage.tsx  # 提供商编辑
│   │   ├── mcp/
│   │   │   └── MCPServerPage.tsx     # MCP Server 管理
│   │   └── tool-groups/
│   │       └── ToolGroupPage.tsx     # 工具分组管理
│   ├── services/               # API 调用层
│   │   ├── api.ts              # Axios 实例与拦截器
│   │   ├── agentService.ts
│   │   ├── agentVersionService.ts
│   │   ├── chatService.ts
│   │   ├── approvalService.ts
│   │   ├── guardrailService.ts
│   │   ├── providerService.ts
│   │   ├── supervisionService.ts
│   │   ├── tokenUsageService.ts
│   │   ├── toolGroupService.ts
│   │   ├── traceService.ts
│   │   └── mcpServerService.ts
│   ├── stores/
│   │   └── authStore.ts        # Zustand 认证状态管理
│   └── __tests__/
│       └── smoke.test.ts       # 前端冒烟测试
```

---

## docs/ — 文档

```
docs/
├── README.md                          # 文档索引
├── project-structure.md               # 本文件 — 目录结构说明
├── api-validation.md                  # API 校验规范
├── deployment-guide.md                # 部署指南
├── user-guide.md                      # 用户使用指南
├── plan/
│   └── mvp-progress.md               # MVP 进度追踪
├── spec/                              # 产品与技术规格
│   ├── CkyClaw PRD v2.0.md           # 产品需求文档
│   ├── CkyClaw PRD-Agent编排 v2.0.md # Agent 编排 PRD
│   ├── CkyClaw PRD-企业能力 v2.0.md  # 企业能力 PRD
│   ├── CkyClaw PRD-基础设施 v2.0.md  # 基础设施 PRD
│   ├── CkyClaw Application Design v1.2.md  # 应用设计
│   ├── CkyClaw API Design v1.2.md    # API 设计
│   ├── CkyClaw Data Model v1.3.md    # 数据模型
│   └── CkyClaw Framework Design v2.0.md    # Framework 设计
└── references/                        # 参考资料
    ├── competitive-analysis.md        # 竞品分析
    ├── codex-cli-architecture.md      # Codex CLI 架构参考
    └── DeerFlow/                      # DeerFlow 项目参考
        ├── github.md
        └── local dir.md
```

---

## .github/ — CI 与编辑器配置

```
.github/
├── workflows/
│   └── ci.yml                  # GitHub Actions CI 流水线
└── instructions/
    └── copilot.instructions.md # GitHub Copilot 指令
```
