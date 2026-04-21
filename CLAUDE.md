# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 语言要求

**永远使用中文回答。** AI 助手名字叫 cky，用户叫 boss。

## 项目概览

Kasaya 是基于自研 Kasaya Framework 构建的 AI Agent 管理与运行平台。Monorepo 包含三个核心包：

| 包 | 路径 | 说明 |
|---|---|---|
| **kasaya** | `kasaya/` | Python Agent 运行时库（独立 pip 包） |
| **backend** | `backend/` | FastAPI 后端服务，依赖 framework 作为 editable 包 |
| **frontend** | `frontend/` | React SPA 管理面板 |

基础设施：PostgreSQL 16 + Redis 7，Docker Compose 编排。

## 常用命令

### 基础设施

```bash
docker-compose up -d db redis          # 仅启动数据库和缓存
docker-compose up -d                    # 全部服务（含 backend/frontend）
cp .env.example .env                    # 复制后按需修改
```

### kasaya

```bash
cd kasaya && uv sync
uv run pytest tests/ -q                # 全部测试
uv run pytest tests/test_foo.py -q     # 单个测试文件
uv run ruff check .                     # Lint
uv run mypy kasaya/          # 类型检查
```

### backend

```bash
cd backend && uv sync
uv run alembic upgrade head             # 数据库迁移
uv run alembic revision --autogenerate -m "描述"  # 创建迁移
uv run uvicorn app.main:app --reload    # 开发服务器 (端口 8000)
uv run pytest tests/ -q                 # 测试
uv run ruff check .                     # Lint
uv run mypy app/                        # 类型检查
```

### frontend

```bash
cd frontend && pnpm install
pnpm dev                                # 开发服务器 (端口 5173)
pnpm build                              # 编译
pnpm lint                               # ESLint
pnpm test                               # Vitest
npx tsc --noEmit                        # 类型检查
```

## 架构

### kasaya — Agent 运行时

核心模块（均在 `kasaya/` 下）：

- **`agent/`** — `Agent` 数据类：声明式 Agent 定义（指令、模型、工具、Handoff、Guardrail、审批模式）。`as_tool()` 支持将 Agent 包装为工具。
- **`runner/`** — 执行引擎 `Runner`：`run()` / `run_sync()` / `run_streamed()`。核心循环：构建消息 → 调用 LLM → 并行执行工具(`asyncio.TaskGroup`) → 处理 Handoff → 重复直到最终输出或 `max_turns`。
- **`model/`** — LLM 抽象层：`ModelProvider`（抽象）→ `LiteLLMProvider`（实现，支持多 LLM 厂商）。
- **`guardrails/`** — 三阶段护栏：Input（LLM 调用前）、Output（最终输出后）、Tool（工具执行前后）。内置：正则、PII、Token 限制、工具白名单、LLM 护栏、注入检测、内容安全。
- **`tools/`** — 工具系统：`FunctionTool`（异步函数 + JSON Schema）、`ToolContext`、`ToolGroup`、`ToolRegistry`。`@function_tool` 装饰器为主要 API。
- **`handoff/`** — Agent 间任务交接：`Handoff` 包装目标 Agent + 可选 `InputFilter`，在 LLM 工具 schema 中合成为 `transfer_to_<name>` 工具。
- **`approval/`** — 人工审批：`ApprovalMode`（FULL_AUTO / SUGGEST / AUTO_EDIT），`ApprovalHandler` 抽象回调。
- **`session/`** — 多轮对话：`Session` + `SessionBackend`（内存 / PostgreSQL），`HistoryTrimmer` 支持按 token 预算或消息数裁剪。
- **`tracing/`** — 可观测性：`Trace` 包含 `Span`（AGENT / LLM / TOOL / GUARDRAIL / HANDOFF），`TraceProcessor` 抽象sink。
- **`mcp/`** — Model Context Protocol 集成。
- **`compat/`** — OpenAI Agents SDK 兼容层：`from_openai_agent/tool/handoff/guardrail` + `SdkAgentAdapter`，将 SDK 定义转换为 Kasaya 原生对象。

### backend — 分层架构

```
app/
  main.py          → create_app() 工厂，注册路由和中间件
  core/
    config.py      → Settings(BaseSettings)，环境变量前缀 KASAYA_
    database.py    → AsyncEngine, async_session_factory, Base, get_db 依赖
    auth.py        → JWT (python-jose + passlib/bcrypt)
    deps.py        → get_current_user, require_admin 依赖
  api/             → 每个域一个路由文件，全部挂载在 /api/v1/
  models/          → SQLAlchemy ORM 模型（Mapped[]/mapped_column 风格，JSONB 存灵活配置）
  schemas/         → Pydantic v2 请求/响应 schema（与 models 对应）
  services/        → 纯异步函数模块（非类），业务逻辑层
```

关键模式：
- 配置通过 `Settings(BaseSettings)` 单例，环境变量前缀 `KASAYA_`
- 数据库用 asyncpg + SQLAlchemy async，`get_db()` 异步生成器依赖
- Services 层是纯函数模块，`session_backend.py` 桥接 framework 的 `SessionBackend` 到 SQLAlchemy
- Alembic 异步模式，`entrypoint.sh` 在 Docker 启动时自动运行迁移

### frontend — React SPA

```
src/
  App.tsx                    → 路由定义，lazy() 代码分割，RequireAuth 守卫
  layouts/BasicLayout.tsx    → ProLayout 侧边栏（11 个菜单项）
  pages/                     → 按域划分：dashboard, chat, agents, providers, runs, traces 等
  services/api.ts            → fetch 封装：JWT 认证、ApiError 类型化
  stores/authStore.ts        → Zustand 管理认证状态
```

API 调用：手写 fetch wrapper，JWT 从 `localStorage('kasaya_token')` 读取注入 `Authorization: Bearer`。

## 参考文档

以下规范和流程定义在 [AGENTS.md](AGENTS.md) 中，遇到相关场景时查阅：

- **编码规范** — Python（ruff/mypy strict/async）和 TypeScript（ESLint/strict/禁止 any）的详细风格要求 → AGENTS.md §Python 编码规范 / §TypeScript 规范
- **Git 提交规范** — `<type>: <中文描述>`，type 列表 → AGENTS.md §Git 提交规范
- **macOS 代理** — 外部 URL 访问需设置 HTTP_PROXY → AGENTS.md §代理网络
- **十角色团队流程与五轮代码审查** → AGENTS.md §十角色团队流程 / §五轮代码审查
- **定位守卫与优先级定义** — P0~P3 优先级判断 → AGENTS.md §定位守卫
- **核心信念与底线** → AGENTS.md §核心信念 / §底线
- **环境变量说明** → [.env.example](.env.example)
- **详细目录结构** → [docs/project-structure.md](docs/project-structure.md)

## graphify

This project has a graphify knowledge graph at graphify-out/.

Rules:
- Before answering architecture or codebase questions, read graphify-out/GRAPH_REPORT.md for god nodes and community structure
- If graphify-out/wiki/index.md exists, navigate it instead of reading raw files
- After modifying code files in this session, run `python3 -c "from graphify.watch import _rebuild_code; from pathlib import Path; _rebuild_code(Path('.'))"` to keep the graph current
