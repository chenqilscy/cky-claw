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
| Backend | FastAPI, SQLAlchemy (async), Alembic, LiteLLM |
| Frontend | React 18, Vite 5, TypeScript, Ant Design 5 |
| Database | PostgreSQL 16, Redis 7 |
| Deploy | Docker Compose |

## 快速开始

### 前置条件

- Python 3.12+
- Node.js 20+ & pnpm
- Docker & Docker Compose
- [uv](https://docs.astral.sh/uv/) (Python 包管理)

### 启动基础设施

```bash
docker-compose up -d db redis
```

### 启动 Backend

```bash
cd backend
uv sync
uv run uvicorn app.main:app --reload
```

### 启动 Frontend

```bash
cd frontend
pnpm install
pnpm dev
```

## 文档

详见 [docs/README.md](docs/README.md)。

## License

Private — All rights reserved.
