# CkyClaw 部署指南

> 本文档介绍如何使用 Docker Compose 一键部署 CkyClaw 平台。

## 环境要求

| 组件 | 最低版本 |
|------|----------|
| Docker | 24.0+ |
| Docker Compose | 2.20+ |
| 磁盘空间 | ≥ 2 GB |
| 内存 | ≥ 4 GB |

## 快速部署

### 1. 克隆代码

```bash
git clone https://github.com/chenqilscy/cky-claw.git
cd cky-claw
```

### 2. 配置环境变量

在项目根目录创建 `.env` 文件：

```bash
# 数据库密码（必须修改）
POSTGRES_PASSWORD=your_secure_password_here

# JWT 密钥（必须修改，建议 32 位随机字符串）
CKYCLAW_SECRET_KEY=your-random-jwt-secret-key-32chars

# 可选配置
CKYCLAW_DEBUG=false
CKYCLAW_CORS_ORIGINS=["http://localhost:3000"]
```

> **安全警告**：生产环境必须修改 `POSTGRES_PASSWORD` 和 `CKYCLAW_SECRET_KEY`，不要使用默认值。

### 3. 启动服务

```bash
docker-compose up -d
```

首次启动会自动构建镜像，耗时约 3-5 分钟。启动完成后，服务列表：

| 服务 | 端口 | 说明 |
|------|------|------|
| frontend | 3000 | Web 前端（Nginx） |
| backend | 8000 | API 后端（FastAPI） |
| db | 5432 | PostgreSQL 16 |
| redis | 6379 | Redis 7 |

### 4. 初始化数据库

```bash
# 执行数据库迁移
docker-compose exec backend uv run alembic upgrade head
```

### 5. 验证部署

```bash
# 健康检查
curl http://localhost:8000/health

# 预期响应
# {"status":"ok","service":"CkyClaw","version":"0.1.0"}
```

访问 `http://localhost:3000` 进入 Web 界面。

## 环境变量参考

| 变量名 | 默认值 | 说明 |
|--------|--------|------|
| `POSTGRES_PASSWORD` | `ckyclaw_dev` | PostgreSQL 密码 |
| `CKYCLAW_DATABASE_URL` | 自动拼接 | 数据库连接字符串（Docker 内自动设置） |
| `CKYCLAW_REDIS_URL` | `redis://redis:6379/0` | Redis 连接字符串 |
| `CKYCLAW_SECRET_KEY` | `dev-secret-key-...` | JWT 签名密钥 |
| `CKYCLAW_ACCESS_TOKEN_EXPIRE_MINUTES` | `1440`（24h） | Token 有效期（分钟） |
| `CKYCLAW_DEBUG` | `true` | 调试模式 |
| `CKYCLAW_CORS_ORIGINS` | `["http://localhost:3000", "http://localhost:5173"]` | CORS 允许来源 |
| `CKYCLAW_OAUTH_GITHUB_CLIENT_ID` | （空） | GitHub OAuth App Client ID |
| `CKYCLAW_OAUTH_GITHUB_CLIENT_SECRET` | （空） | GitHub OAuth App Client Secret |
| `CKYCLAW_OAUTH_REDIRECT_BASE_URL` | `http://localhost:3000` | OAuth 回调基础 URL |

## 服务架构

```
用户浏览器
    │
    ▼ (3000)
┌─────────────┐     /api/*     ┌─────────────┐
│  Frontend   │ ──────────────►│   Backend   │
│  (Nginx)    │  proxy_pass    │  (FastAPI)  │
└─────────────┘                └──────┬──────┘
                                      │
                          ┌───────────┼───────────┐
                          │                       │
                    ┌─────▼─────┐           ┌─────▼─────┐
                    │ PostgreSQL│           │   Redis   │
                    │  (5432)   │           │  (6379)   │
                    └───────────┘           └───────────┘
```

- **Frontend**：Nginx 托管 React SPA，反向代理 `/api/*` 到 Backend
- **Backend**：FastAPI 应用，连接 PostgreSQL 和 Redis
- **SSE 支持**：Nginx 已配置 `proxy_buffering off` 以支持流式响应

## 常用运维命令

```bash
# 查看服务状态
docker-compose ps

# 查看日志
docker-compose logs -f backend
docker-compose logs -f frontend

# 重启单个服务
docker-compose restart backend

# 停止所有服务
docker-compose down

# 停止并清除数据卷（危险：会删除所有数据）
docker-compose down -v

# 重新构建镜像
docker-compose build --no-cache

# 执行数据库迁移
docker-compose exec backend uv run alembic upgrade head

# 回滚上一次迁移
docker-compose exec backend uv run alembic downgrade -1
```

## 本地开发模式

如果不使用 Docker 运行应用服务，只需启动基础设施：

```bash
# 仅启动 PostgreSQL + Redis
docker-compose up -d db redis

# 后端本地开发
cd backend
uv sync
uv run alembic upgrade head
uv run uvicorn app.main:app --reload --port 8000

# 前端本地开发
cd frontend
pnpm install
pnpm dev
```

## 故障排查

### 数据库连接失败

```bash
# 检查 PostgreSQL 是否就绪
docker-compose exec db pg_isready -U ckyclaw

# 检查数据库是否存在
docker-compose exec db psql -U ckyclaw -c "\l"
```

### 端口冲突

如果 3000、8000、5432、6379 端口被占用，修改 `docker-compose.yml` 中的端口映射：

```yaml
ports:
  - "3001:3000"  # 前端改用 3001
```

### 镜像构建失败

```bash
# 查看构建详情
docker-compose build --progress=plain backend
```
