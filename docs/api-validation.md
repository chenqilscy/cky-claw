# CkyClaw API 校验清单

> 本文档对照设计文档与实际代码，校验所有 API 端点的实现状态。
>
> 交互式 API 文档：`http://localhost:8000/docs`（Swagger UI）、`http://localhost:8000/redoc`（ReDoc）。

## 端点总览

### 系统

| 方法 | 路径 | 说明 | 状态 |
|------|------|------|------|
| GET | `/health` | 健康检查 | ✅ |

### 认证（`/api/v1/auth`）

| 方法 | 路径 | 说明 | 状态 |
|------|------|------|------|
| POST | `/api/v1/auth/register` | 用户注册 | ✅ |
| POST | `/api/v1/auth/login` | 用户登录（返回 JWT） | ✅ |
| GET | `/api/v1/auth/me` | 获取当前用户信息 | ✅ |

### Agent 管理（`/api/v1/agents`）

| 方法 | 路径 | 说明 | 状态 |
|------|------|------|------|
| GET | `/api/v1/agents` | Agent 列表（分页+搜索） | ✅ |
| POST | `/api/v1/agents` | 创建 Agent | ✅ |
| GET | `/api/v1/agents/{name}` | Agent 详情 | ✅ |
| PUT | `/api/v1/agents/{name}` | 更新 Agent | ✅ |
| DELETE | `/api/v1/agents/{name}` | 删除 Agent（软删除） | ✅ |

### 会话管理（`/api/v1/sessions`）

| 方法 | 路径 | 说明 | 状态 |
|------|------|------|------|
| POST | `/api/v1/sessions` | 创建会话 | ✅ |
| GET | `/api/v1/sessions` | 会话列表（分页+筛选） | ✅ |
| GET | `/api/v1/sessions/{session_id}` | 会话详情 | ✅ |
| DELETE | `/api/v1/sessions/{session_id}` | 删除会话 | ✅ |
| POST | `/api/v1/sessions/{session_id}/run` | 执行对话（JSON 或 SSE） | ✅ |

### Token 统计（`/api/v1/token-usage`）

| 方法 | 路径 | 说明 | 状态 |
|------|------|------|------|
| GET | `/api/v1/token-usage` | Token 消耗明细列表 | ✅ |
| GET | `/api/v1/token-usage/summary` | Token 消耗汇总统计 | ✅ |

### 监督（`/api/v1/supervision`，需 admin 权限）

| 方法 | 路径 | 说明 | 状态 |
|------|------|------|------|
| GET | `/api/v1/supervision/sessions` | 监督会话列表 | ✅ |
| GET | `/api/v1/supervision/sessions/{session_id}` | 监督会话详情 | ✅ |
| POST | `/api/v1/supervision/sessions/{session_id}/pause` | 暂停会话 | ✅ |
| POST | `/api/v1/supervision/sessions/{session_id}/resume` | 恢复会话 | ✅ |

### Model Provider 管理（`/api/v1/providers`，需 admin 权限）

| 方法 | 路径 | 说明 | 状态 |
|------|------|------|------|
| GET | `/api/v1/providers` | Provider 列表 | ✅ |
| POST | `/api/v1/providers` | 创建 Provider | ✅ |
| GET | `/api/v1/providers/{provider_id}` | Provider 详情 | ✅ |
| PUT | `/api/v1/providers/{provider_id}` | 更新 Provider | ✅ |
| DELETE | `/api/v1/providers/{provider_id}` | 删除 Provider | ✅ |
| PUT | `/api/v1/providers/{provider_id}/toggle` | 启用/禁用 Provider | ✅ |

## 校验结果

- **总端点数**：26
- **已实现**：26 / 26（100%）
- **认证保护**：supervision 和 providers 端点已加 `require_admin` 依赖
- **SSE 支持**：`POST /sessions/{id}/run` 根据 `config.stream` 参数返回 JSON 或 SSE
- **响应模型**：所有端点均配置了 `response_model` Pydantic Schema

## SSE 事件类型

`POST /api/v1/sessions/{session_id}/run`（`stream=true`）返回的 SSE 事件：

| 事件 | 说明 |
|------|------|
| `run_start` | 运行开始 |
| `agent_start` | Agent 开始处理 |
| `text_delta` | 文本增量输出 |
| `tool_call` | 发起工具调用 |
| `tool_output` | 工具返回结果 |
| `handoff` | Agent 切换 |
| `guardrail_tripwire` | 护栏触发 |
| `approval_requested` | 请求审批 |
| `approval_resolved` | 审批结果 |
| `run_end` | 运行结束 |

## 后续迭代（MVP 暂缓）

以下 API 在设计文档中规划但 MVP 阶段暂未实现：

| 端点 | 说明 | 计划阶段 |
|------|------|----------|
| WebSocket `/ws/approval` | 实时审批通道 | M6+ |
| GET `/api/v1/traces` | Trace 查询 API | M6+（需 Trace 持久化） |
| GET `/api/v1/traces/{id}/spans` | Span 详情 | M6+ |

---

*校验时间：2025-07-18*
