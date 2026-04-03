# CkyClaw

基于自研 **CkyClaw Framework** 构建的 AI Agent 管理与运行平台。

## 项目结构

```
cky-claw/
├── ckyclaw-framework/   # CkyClaw Framework — Python Agent 运行时库
├── backend/             # CkyClaw Backend — FastAPI 后端服务
├── frontend/            # CkyClaw Frontend — React Web 前端
├── docs/                # 产品与技术文档
├── .github/             # GitHub Actions CI + 编辑器指令
└── docker-compose.yml   # 开发环境基础设施
```

## 技术栈

| 层 | 技术 |
|----|------|
| Framework | Python 3.12+, CkyClaw Framework |
| Backend | FastAPI, SQLAlchemy (async), Alembic, LiteLLM, Pydantic v2 |
| Frontend | React 18, Vite 5, TypeScript, Ant Design 5, ProComponents |
| Database | PostgreSQL 16, Redis 7 |
| Deploy | Docker Compose |
| 包管理 | uv (Python), pnpm (前端) |

## 快速开始

### 前置条件

- Docker & Docker Compose v2
- Python 3.12+（本地开发时需要）
- Node.js 20+ & pnpm（本地开发时需要）
- [uv](https://docs.astral.sh/uv/)（Python 包管理）

### 方式一：Docker Compose 一键启动

```bash
# 1. 复制环境变量配置
cp .env.example .env

# 2. （可选）修改 .env 中的密码和密钥
#    生产环境务必更换 CKYCLAW_SECRET_KEY 和 POSTGRES_PASSWORD

# 3. 一键启动全部服务（DB + Redis + Backend + Frontend）
docker-compose up -d

# 4. 查看日志
docker-compose logs -f backend

# 5. 访问
#    - 前端: http://localhost:3000
#    - 后端 API: http://localhost:8000
#    - API 文档: http://localhost:8000/docs
```

启动顺序：PostgreSQL → Redis → Backend（自动运行数据库迁移）→ Frontend

### 方式二：本地开发

```bash
# 1. 启动基础设施
docker-compose up -d db redis

# 2. 启动 Backend
cd backend
uv sync
uv run alembic upgrade head   # 首次需要运行数据库迁移
uv run uvicorn app.main:app --reload

# 3. 启动 Frontend（新终端）
cd frontend
pnpm install
pnpm dev
```

- 前端开发: http://localhost:5173
- 后端 API: http://localhost:8000
- API 交互文档: http://localhost:8000/docs

### 方式三：仅启动基础设施 + 本地 Backend

```bash
docker-compose up -d db redis
cd backend && uv sync && uv run uvicorn app.main:app --reload
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

详见 [.env.example](.env.example)。

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
