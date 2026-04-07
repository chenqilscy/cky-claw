# CkyClaw

基于自研 **CkyClaw Framework** 构建的 AI Agent 管理与运行平台。CkyClaw 汲取了 Claude Code、OpenAI Agents SDK、DeerFlow 等业界方案的优秀设计，提供开放、可扩展的 Agent 运行时基础设施，并在此之上构建企业级的 Agent 配置管理、多模式编排、执行可视化、人工监督、多渠道接入和 APM 监控等上层能力。

## 关键指标

| 指标 | 数值 |
|------|------|
| 测试通过 | **2958+**（Backend 1740 + Framework 1218） |
| 测试覆盖率 | Backend **98%** · Framework **100%** |
| Alembic 迁移 | **45** 个 |
| API 路由模块 | **37** 个 |
| 前端页面 | **38** 个（React.lazy 懒加载） |
| 前端测试文件 | **74** 个 |
| TypeScript · mypy · ruff E501 | 全部 **0** 错误 |

## 项目结构

```
cky-claw/
├── ckyclaw-framework/   # CkyClaw Framework — Python Agent 运行时库
│   ├── agent/           #   Agent 定义（Agent dataclass + as_tool）
│   ├── runner/          #   Runner 执行引擎（Agent Loop + Hooks + RunConfig）
│   ├── model/           #   Model Provider 抽象 + CostRouter
│   ├── tools/           #   工具系统（FunctionTool + ToolGroup + ToolRegistry）
│   ├── guardrails/      #   护栏（Regex/Keyword/LLM × Input/Output/Tool）
│   ├── handoff/         #   Handoff 多级编排
│   ├── approval/        #   审批模式（suggest/auto-edit/full-auto）
│   ├── session/         #   Session 会话管理
│   ├── tracing/         #   Tracing 链路追踪
│   ├── memory/          #   记忆系统（指数衰减 + 自动提取 Hook）
│   ├── checkpoint/      #   Checkpoint 断点续跑
│   ├── intent/          #   意图检测与飘移处理
│   ├── evolution/       #   自动进化（Signal + Strategy）
│   └── mcp/             #   MCP 客户端（stdio/sse/http）
├── backend/             # CkyClaw Backend — FastAPI 后端服务（37 路由模块）
├── frontend/            # CkyClaw Frontend — React SPA（38 页面）
├── docs/                # 产品与技术文档
├── scripts/             # 灾备 + 压测脚本
├── .github/             # GitHub Actions CI（6 Job）+ 编辑器指令
└── docker-compose.yml   # Docker Compose 编排
```

## 核心能力

### CkyClaw Framework

| 能力 | 说明 |
|------|------|
| Agent Loop | `run` / `run_sync` / `run_streamed` + `max_turns` + TaskGroup 并行工具 |
| Handoff 编排 | 多级递归 + InputFilter + 循环检测 |
| Agent Team | Sequential / Parallel / Coordinator + 8 协议 |
| Guardrails | Input / Output / Tool × Regex / Keyword / LLM |
| Tools | FunctionTool + ToolGroup + ToolRegistry + MCP 集成 |
| Approval | suggest / auto-edit / full-auto + 审批回调 |
| Tracing | Agent / LLM / Tool / Handoff / Guardrail Span |
| Session | InMemory / Postgres + HistoryTrimmer |
| Memory | 指数衰减 + MemoryExtractionHook |
| Checkpoint | InMemory / Postgres + Runner resume_from |
| Intent Detection | KeywordIntentDetector + 飘移 Hook |
| Cost Router | ModelTier 分类 + 规则路由器 |
| Evolution | SignalCollector + StrategyEngine + 自动应用 |
| Multi-Provider | LiteLLM 适配 10+ 厂商 |

### Backend — 37 路由模块

Agent CRUD + 版本管理 · RBAC + 多租户 · OAuth 2.0（GitHub/企微/钉钉/飞书/Google/Keycloak）· IM 6 渠道适配 · APM 仪表盘 + 告警 · Token 审计 + 趋势 · 定时/批量任务 · 配置热更新 · Agent 评估 · 国际化 · 灾备策略 · 深度健康检查 · WebSocket 统一事件 · Span 火焰图 · Trace 回放 · A/B 模型测试 · Session 消息搜索 · 14 个 Agent 模板

### Frontend — 38 页面

Dashboard（6 统计 + 趋势图 + 自动刷新）· 对话页（SSE 流式 + Markdown）· Agent 管理（版本 diff + Handoff 可视化 + 模板市场）· ReactFlow（Handoff / Team / Workflow）· ECharts（Dashboard / APM / 火焰图）· 成本路由 · 意图检测 · Checkpoint 管理 · A/B 测试 · 暗色模式 · Vendor 5 路分包

## 技术栈

| 层 | 技术 |
|----|------|
| **Framework** | Python 3.12+, CkyClaw Framework (自研) |
| **Backend** | FastAPI, SQLAlchemy (async), Alembic, LiteLLM, Pydantic v2 |
| **Frontend** | React 19, Vite 6, TypeScript 5.8, Ant Design 5, ProComponents, TanStack Query, ReactFlow, ECharts, Zustand |
| **Database** | PostgreSQL 16, Redis 7 |
| **Deploy** | Docker Compose（Kubernetes 规划中） |
| **CI/CD** | GitHub Actions（6 Job）+ Jenkinsfile（5 Stage） |
| **可观测性** | OpenTelemetry + Jaeger + Prometheus |
| **包管理** | uv (Python), pnpm (前端) |
| **Lint** | ruff (Python), ESLint (TypeScript), pre-commit (6 hooks) |
| **测试** | pytest + pytest-asyncio (Python), Vitest + Playwright (前端) |

## 快速开始

### 前置条件

- Docker & Docker Compose v2
- Python 3.12+（本地开发）
- Node.js 20+ & pnpm（本地开发）
- [uv](https://docs.astral.sh/uv/)（Python 包管理）

### 方式一：Docker Compose 一键启动

```bash
# 1. 复制环境变量配置
cp .env.example .env

# 2.（可选）修改 .env 中的密码和密钥
#   生产环境务必更换 CKYCLAW_SECRET_KEY 和 POSTGRES_PASSWORD

# 3. 一键启动全部服务
docker-compose up -d

# 4. 访问
#    前端: http://localhost:3000
#    后端 API: http://localhost:8000
#    API 文档: http://localhost:8000/docs
```

启动顺序：PostgreSQL → Redis → Backend（自动迁移）→ Frontend

### 方式二：本地开发

```bash
# 1. 启动基础设施
docker-compose up -d db redis

# 2. Backend
cd backend && uv sync
cp ../.env.example ../.env  # 首次配置
# 修改 .env 中 CKYCLAW_DATABASE_URL 的 host 为 localhost
uv run alembic upgrade head
uv run uvicorn app.main:app --reload --port 8000

# 3. Frontend（新终端）
cd frontend && pnpm install
pnpm dev
```

| 服务 | 地址 |
|------|------|
| 前端（开发） | http://localhost:5173 |
| 后端 API | http://localhost:8000 |
| API 交互文档 | http://localhost:8000/docs |
| 深度健康检查 | http://localhost:8000/health/deep |

### 默认管理员

首次启动后需要注册管理员账号。通过 API 文档 (`/docs`) 的 `POST /api/v1/auth/register` 创建：

```json
{
  "username": "admin",
  "password": "your-password",
  "role": "admin"
}
```

## 开发命令

### ckyclaw-framework

```bash
cd ckyclaw-framework && uv sync
uv run pytest tests/ -q          # 全部测试（1218）
uv run ruff check .               # Lint
uv run mypy ckyclaw_framework/    # 类型检查
```

### backend

```bash
cd backend && uv sync
uv run alembic upgrade head                        # 数据库迁移
uv run alembic revision --autogenerate -m "描述"    # 创建迁移
uv run uvicorn app.main:app --reload               # 开发服务器
uv run pytest tests/ -q                            # 全部测试（1740）
uv run ruff check .                                # Lint
uv run mypy app/                                   # 类型检查
```

### frontend

```bash
cd frontend && pnpm install
pnpm dev          # 开发服务器（端口 5173）
pnpm build        # 生产构建
pnpm lint         # ESLint
pnpm test         # Vitest（74 文件）
npx tsc --noEmit  # TypeScript 类型检查
```

## 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `POSTGRES_PASSWORD` | `ckyclaw_dev` | PostgreSQL 密码 |
| `CKYCLAW_DATABASE_URL` | `postgresql+asyncpg://...` | 数据库连接字符串 |
| `CKYCLAW_REDIS_URL` | `redis://localhost:6379/0` | Redis 连接字符串 |
| `CKYCLAW_SECRET_KEY` | `dev-secret-key-...` | JWT 签名密钥（**生产必须更换**） |
| `CKYCLAW_ACCESS_TOKEN_EXPIRE_MINUTES` | `1440` | JWT 过期时间（分钟） |
| `CKYCLAW_DEBUG` | `true` | 调试模式 |
| `CKYCLAW_DB_POOL_SIZE` | `5` | 数据库连接池大小 |
| `CKYCLAW_DB_MAX_OVERFLOW` | `10` | 连接池最大溢出 |
| `CKYCLAW_OTEL_ENABLED` | `false` | OpenTelemetry 启用 |

详见 [.env.example](.env.example)。

## 文档

| 文档 | 路径 |
|------|------|
| 产品需求文档 (PRD) | [docs/spec/CkyClaw PRD v2.0.md](docs/spec/CkyClaw%20PRD%20v2.0.md) |
| API 设计文档 | [docs/spec/CkyClaw API Design v1.2.md](docs/spec/CkyClaw%20API%20Design%20v1.2.md) |
| 数据模型文档 | [docs/spec/CkyClaw Data Model v1.3.md](docs/spec/CkyClaw%20Data%20Model%20v1.3.md) |
| 部署指南 | [docs/deployment-guide.md](docs/deployment-guide.md) |
| 用户指南 | [docs/user-guide.md](docs/user-guide.md) |
| 待办与演进 | [docs/todo.md](docs/todo.md) |
| 项目结构详解 | [docs/project-structure.md](docs/project-structure.md) |

## 许可证

私有项目，未经授权不得使用。

## 数据库迁移

```bash
cd backend

# 创建新迁移
uv run alembic revision --autogenerate -m "描述"

# 执行迁移
uv run alembic upgrade head

# 回滚
uv run alembic downgrade -1
```

## 测试

```bash
# Framework 测试
cd ckyclaw-framework && uv run pytest tests/ -q

# Backend 测试
cd backend && uv run pytest tests/ -q

# Frontend 类型检查
cd frontend && npx tsc --noEmit

# Frontend ESLint
cd frontend && pnpm lint
```

## 主要功能

- **Agent 管理** — 创建、配置、版本管理 AI Agent
- **多模型支持** — 通过 LiteLLM 适配 OpenAI / Anthropic / Azure 等
- **对话系统** — Session 管理 + 流式输出（SSE）
- **工具系统** — 函数工具 + MCP Server + 工具组
- **Guardrail 护栏** — 输入/输出/工具三类护栏（正则/关键词/LLM）
- **Handoff 协作** — Agent 间任务交接
- **审批流程** — 工具调用人工审批
- **Trace 追踪** — 全链路 Span 追踪 + 可视化
- **Token 用量** — 按模型/Agent/用户统计
- **Dashboard** — 平台全局概览面板

## 文档

详见 [docs/README.md](docs/README.md)。

## License

Private — All rights reserved.
