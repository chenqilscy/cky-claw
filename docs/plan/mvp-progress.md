# CkyClaw MVP 开发进度追踪

> 此文件记录 MVP 开发的全部任务及完成状态。每次会话可从此文件回溯进度。

## M0：项目启动与基础搭建

### Phase 0.1：Monorepo 骨架 ✅
- [x] 0.1.1 创建 monorepo 根目录结构（backend/ + frontend/ + ckyclaw-framework/）
- [x] 0.1.2 根级配置文件（.editorconfig + .gitignore + docker-compose.yml）
- [x] 0.1.3 根级 README.md
- [x] Git 初始化 + 推送至 GitHub

### Phase 0.2：CkyClaw Framework 包骨架
- [ ] 0.2.1 Python 包初始化（pyproject.toml + __init__.py + py.typed）
- [ ] 0.2.2 核心模块空壳 — agent/（agent.py, config.py, output.py）
- [ ] 0.2.3 核心模块空壳 — runner/（runner.py, run_config.py, run_context.py, result.py）
- [ ] 0.2.4 核心模块空壳 — model/（provider.py, settings.py, message.py, litellm_provider.py）
- [ ] 0.2.5 核心模块空壳 — tools/, tracing/, session/

### Phase 0.3：Backend 骨架
- [ ] 0.3.1 FastAPI 项目初始化（pyproject.toml + app/main.py → /health 返回 200）
- [ ] 0.3.2 目录结构（api/ + models/ + services/ + core/）
- [ ] 0.3.3 基础中间件（CORS + 请求 ID + 错误处理）
- [ ] 0.3.4 数据库连接（SQLAlchemy async + Alembic 初始化）

### Phase 0.4：Frontend 骨架
- [ ] 0.4.1 React + Vite 项目初始化（package.json + vite.config.ts）
- [ ] 0.4.2 基础脚手架（Ant Design 5 + ProLayout + React Router）
- [ ] 0.4.3 登录页占位（/login 路由 + 登录表单 UI）
- [ ] 0.4.4 开发工具链（ESLint + Prettier + TypeScript strict）

### Phase 0.5：部署脚本
- [ ] 0.5.1 Docker Compose — 基础设施（PostgreSQL 16 + Redis 7）— 已在 0.1.2 完成骨架
- [ ] 0.5.2 Docker Compose — 应用（Backend + Frontend Dockerfile）
- [ ] 0.5.3 可观测性（OTel + Jaeger + Prometheus + Grafana）— 可选，MVP 暂缓

### Phase 0.6：CI 流水线
- [ ] 0.6.1 GitHub Actions — lint（ruff + eslint）
- [ ] 0.6.2 GitHub Actions — test（pytest + vitest）
- [ ] 0.6.3 GitHub Actions — build（前后端构建 + Docker 镜像）

---

## M1：Agent 核心引擎（待拆分）

## M2：Web 对话与 Agent 管理（待拆分）

## M3：编排与 Tracing（待拆分）

## M4：监督与安全（待拆分）

## M5：MVP 完整交付（待拆分）

---

*最后更新：2026-04-02*
