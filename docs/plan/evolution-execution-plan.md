# Kasaya 演进执行计划

> 创建：2026-04-09
> 状态：进行中
> 基于：[Kasaya 演进方向分析 v1.0](../spec/Kasaya%20演进方向分析%20v1.0.md)

---

## 总览

| 顺序 | Phase | 方向 | 优先级 | 状态 |
|:----:|-------|------|:------:|:----:|
| 1 | **Phase 1** | P0-1 全链路启动验证 | P0 | ✅ 完成 |
| 2 | **Phase 2** | P0-2 代码审查 Agent 场景 | P0 | ✅ 完成 |
| 3 | **Phase 3** | P0-3 Framework 独立化 | P0 | ✅ 完成 |
| 4 | **Phase 4** | 技术债务清理 | P1 | ✅ 完成 |
| 5 | **Phase 5** | kasaya-cli 命令行工具（仅 chat） | P2 | ✅ 完成 |

> **执行策略**：严格串行，一个 Phase 完成后再开始下一个（十角色团队讨论决策 2026-04-09）

---

## Phase 1：P0-1 全链路启动验证

**目标**：确保 Agent 创建→对话→工具调用→Handoff→审批→Trace 查看的完整流程可正常运行。

### 1.1 Backend 本地验证

| # | 任务 | 验证标准 |
|---|------|---------|
| 1 | Backend 测试全部通过 | `uv run pytest tests/ -q` 0 failures |
| 2 | Framework 测试全部通过 | `uv run pytest tests/ -q` 0 failures |
| 3 | Backend 本地启动正常 | `uv run uvicorn app.main:app --reload` 无报错 |
| 4 | 数据库迁移正常执行 | `uv run alembic upgrade head` 成功 |
| 5 | API 文档可访问 | `http://localhost:8000/docs` 正常渲染 |

### 1.2 Frontend 验证

| # | 任务 | 验证标准 |
|---|------|---------|
| 6 | 前端编译无错误 | `pnpm build` 成功，`tsc --noEmit` 0 errors |
| 7 | 前端测试通过 | `pnpm test` 0 failures |
| 8 | 前端开发服务器正常 | `pnpm dev` 可访问 |

### 1.3 端到端流程验证

| # | 任务 | 涉及的 API/页面 |
|---|------|----------------|
| 9 | 用户注册/登录 | POST /api/v1/auth/register → POST /api/v1/auth/login |
| 10 | 创建 Provider | POST /api/v1/providers |
| 11 | 创建 Agent | POST /api/v1/agents |
| 12 | Agent 对话 | POST /api/v1/sessions → SSE 对话 |
| 13 | 工具调用执行 | Agent 内置工具或 Hosted Tool |
| 14 | Handoff 编排 | 多 Agent 编排测试 |
| 15 | 审批流程 | Approval 触发 → UI 审批 |
| 16 | Trace 查看 | GET /api/v1/traces → SpanWaterfall UI |

### 1.4 Docker 全量验证

| # | 任务 | 验证标准 |
|---|------|---------|
| 17 | `docker-compose up -d` 全部服务健康 | 所有容器 healthy |
| 18 | 冷启动测试 | `down -v && up -d` 无错误启动 |

---

## Phase 2：P0-3 Framework 独立化

**目标**：`pip install kasaya-framework` 能独立使用，不依赖 Backend。

### 2.1 包发布准备

| # | 任务 | 说明 |
|---|------|------|
| 1 | pyproject.toml 完善 | 确认 PyPI 元数据（description、license、classifiers、urls） |
| 2 | README.md 独立化 | Framework 专属 README，含安装、快速入门、API 概览 |
| 3 | 版本号管理 | 确认 `__version__` 和 pyproject.toml 一致 |
| 4 | 发布测试 | `uv build` → `twine check` → TestPyPI 验证 |

### 2.2 独立使用验证

| # | 任务 | 说明 |
|---|------|------|
| 5 | 纯 Framework 示例 | 不依赖 Backend 的 3 个完整示例 |
| 6 | 最小依赖安装测试 | 新 venv 中 `pip install kasaya-framework` 验证 |
| 7 | 可选依赖分组测试 | `pip install kasaya-framework[postgres,mcp]` 验证 |

### 2.3 文档站

| # | 任务 | 说明 |
|---|------|------|
| 8 | Getting Started 教程 | 5 分钟上手指南 |
| 9 | API Reference | 基于 docstring 的自动化 API 文档 |
| 10 | 3 个完整示例文档 | 客服 Agent、代码审查 Agent、数据分析 Agent |

---

## Phase 3：技术债务清理

### 3.1 Framework/Backend 边界清晰化

| # | 任务 | 说明 |
|---|------|------|
| 1 | Backend 对 Framework 的 import 审计 | 确认无越界依赖 |
| 2 | Framework 公共 API 明确 | `__init__.py` 显式导出 |
| 3 | 接口稳定性标记 | 标记哪些是 public API，哪些是 internal |

### 3.2 API 文档自动生成

| # | 任务 | 说明 |
|---|------|------|
| 4 | FastAPI OpenAPI Schema 验证 | 确认所有 API 的 OpenAPI 描述完整 |
| 5 | API 文档中文化 | 所有端点描述和参数说明添加中文 |
| 6 | Swagger UI 增强 | 添加使用示例和请求/响应样例 |

### 3.3 其他债务

| # | 任务 | 说明 |
|---|------|------|
| 7 | 日志结构化 | 统一使用 structlog |
| 8 | 真实 LLM 集成测试 | 至少覆盖 DeepSeek + 通义 |

---

## Phase 4：P0-2 代码审查 Agent 场景

**目标**：构建可演示的 AI 代码审查 Agent，验证核心能力。

| # | 任务 | 说明 |
|---|------|------|
| 1 | 设计代码审查 Agent 配置 | Instructions、工具列表、Guardrails |
| 2 | 实现代码分析工具 | 读取代码文件、AST 分析、diff 解析 |
| 3 | 实现 GitHub PR 集成工具 | 读取 PR diff、添加评论 |
| 4 | Agent 模板入库 | 添加到模板市场 |
| 5 | 端到端演示流程 | 提交 PR → Agent 自动审查 → 输出建议 |

---

## Phase 5：kasaya-cli 命令行工具原型

**目标**：类似 Claude Code 的终端 Agent 对话工具。

| # | 任务 | 说明 |
|---|------|------|
| 1 | CLI 骨架 | typer/click 命令行框架 |
| 2 | `kasaya chat` | 终端交互式对话 |
| 3 | `kasaya run` | 执行 Agent 或 Workflow |
| 4 | `kasaya agent list/create` | Agent 管理命令 |
| 5 | 流式输出 | Rich/Textual 美观的终端渲染 |

---

## 执行日志

| 日期 | Phase | 任务 | 状态 |
|------|-------|------|:----:|
| 2026-04-09 | 1 | 全链路摸底调研完成 | ✅ |
| 2026-04-09 | 1 | Frontend antd.message mock 修复 | ✅ |
| 2026-04-09 | 1 | 本地启动验证 (Backend + Frontend) | ✅ |
| 2026-04-09 | 2 | P0-2 代码审查工具 3 个 + Backend 同步 | ✅ |
| 2026-04-09 | 3 | P0-3 子模块导出 + pyproject.toml + README + 示例 | ✅ |
| 2026-04-09 | 4 | 技术债评估：API 文档已完整、日志延期 | ✅ |
| 2026-04-09 | 5 | kasaya-cli MVP：chat 命令 + 11 个测试 | ✅ |
