# CkyClaw API 接口设计 v1.2

## 文档信息

| 字段 | 内容 |
|------|------|
| 版本 | v1.2.0 |
| 日期 | 2026-04-02 |
| 状态 | 进行中 |
| 维护人 | CkyClaw Team |
| 依赖 | CkyClaw PRD v2.0（第十一章）、CkyClaw 数据模型详细设计 v1.3 |
| 协议 | REST API: OpenAPI 3.1；实时事件: AsyncAPI 3.0 |

---

## 一、通用约定

### 1.1 基础信息

| 项 | 值 |
|----|-----|
| Base URL | `https://{host}/api/v1` |
| 协议 | HTTPS |
| 内容类型 | `application/json`（除文件上传和 SSE） |
| 字符编码 | UTF-8 |

### 1.2 认证

所有 API（除 `/auth/login`）需携带认证凭据：

| 认证方式 | Header | 格式 |
|---------|--------|------|
| JWT Bearer | `Authorization` | `Bearer <access_token>` |
| API Key | `X-API-Key` | `<api_key>` |

### 1.3 分页

列表接口统一使用 offset 分页：

**请求参数：**

| 参数 | 类型 | 默认 | 说明 |
|------|------|------|------|
| `limit` | integer | 20 | 每页数量（max: 100） |
| `offset` | integer | 0 | 偏移量 |
| `sort` | string | `created_at` | 排序字段 |
| `order` | string | `desc` | `asc` / `desc` |

**响应格式：**

```json
{
  "data": [...],
  "total": 142,
  "limit": 20,
  "offset": 0
}
```

### 1.4 成功响应

```json
{
  "data": { ... },
  "message": "ok"
}
```

### 1.5 错误响应

```json
{
  "error": {
    "code": "AGENT_NOT_FOUND",
    "message": "Agent 'unknown-agent' does not exist",
    "details": null
  }
}
```

**HTTP 状态码：**

| 状态码 | 含义 | 典型 code |
|--------|------|----------|
| 400 | 请求参数无效 | VALIDATION_ERROR |
| 401 | 未认证 | UNAUTHORIZED |
| 403 | 权限不足 | FORBIDDEN |
| 404 | 资源不存在 | NOT_FOUND |
| 409 | 资源冲突 | CONFLICT |
| 422 | 业务逻辑错误 | BUSINESS_ERROR |
| 429 | 请求过于频繁 | RATE_LIMITED |
| 500 | 服务器内部错误 | INTERNAL_ERROR |

### 1.6 错误码清单

| 错误码 | HTTP | 说明 |
|--------|------|------|
| `UNAUTHORIZED` | 401 | Token 过期或无效 |
| `FORBIDDEN` | 403 | 角色权限不足 |
| `AGENT_NOT_FOUND` | 404 | Agent 不存在 |
| `SESSION_NOT_FOUND` | 404 | Session 不存在 |
| `RUN_NOT_FOUND` | 404 | Run 不存在 |
| `PROVIDER_NOT_FOUND` | 404 | 厂商不存在 |
| `AGENT_NAME_CONFLICT` | 409 | Agent 名称已存在 |
| `RUN_ALREADY_COMPLETED` | 409 | Run 已完成，无法取消 |
| `SESSION_ALREADY_PAUSED` | 409 | 会话已暂停 |
| `BUDGET_EXHAUSTED` | 422 | Token 预算已耗尽 |
| `MODEL_UNAVAILABLE` | 422 | 模型不可用或未启用 |
| `APPROVAL_TIMEOUT` | 422 | 审批超时 |
| `RATE_LIMITED` | 429 | 超过限流阈值 |
| `VALIDATION_ERROR` | 400 | 输入参数校验失败 |
| `INTERNAL_ERROR` | 500 | 未知服务器错误 |

### 1.7 限流

| 维度 | 默认限制 | Header |
|------|---------|--------|
| 用户级 | 100 req/min | `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset` |
| API Key 级 | 300 req/min | 同上 |
| IP 级 | 60 req/min（未认证） | 同上 |

---

## 二、Agent 管理 API

### 2.1 获取 Agent 列表

`GET /agents`

**查询参数：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `search` | string | 否 | 按名称/描述模糊搜索 |
| `org_id` | UUID | 否 | 按组织筛选 |
| `limit` | integer | 否 | 分页 |
| `offset` | integer | 否 | 分页 |

**响应 200：**

```json
{
  "data": [
    {
      "name": "triage-agent",
      "description": "Triages user requests to the right specialist",
      "model": "gpt-4o",
      "tool_groups": ["web-search"],
      "handoffs": ["data-analyst", "code-executor"],
      "approval_mode": "auto-edit",
      "is_active": true,
      "created_at": "2026-04-01T10:00:00Z",
      "updated_at": "2026-04-02T08:30:00Z"
    }
  ],
  "total": 5,
  "limit": 20,
  "offset": 0
}
```

### 2.2 创建 Agent

`POST /agents`

**请求体：**

```json
{
  "name": "data-analyst",
  "description": "Analyzes data and generates insights",
  "instructions": "You are a data analyst agent...",
  "model": "gpt-4o",
  "tool_groups": ["web-search", "code-executor"],
  "handoffs": [],
  "guardrails": {
    "input": ["prompt-injection-detector"],
    "output": [],
    "tool": []
  },
  "approval_mode": "suggest",
  "metadata": {}
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `name` | string | 是 | Agent 唯一标识（英文+连字符，3-64 字符） |
| `description` | string | 否 | Agent 描述 |
| `instructions` | string | 是 | Agent 行为指令（SOUL.md 内容） |
| `model` | string | 是 | 模型名称（须已在 ModelConfig 中启用） |
| `tool_groups` | string[] | 否 | 工具组名称列表 |
| `handoffs` | string[] | 否 | 可 Handoff 的目标 Agent 名称列表 |
| `guardrails` | object | 否 | 护栏配置 |
| `approval_mode` | string | 否 | `suggest` / `auto-edit` / `full-auto`，默认 `full-auto` |
| `metadata` | object | 否 | 自定义元数据 |

**响应 201：**

```json
{
  "data": {
    "name": "data-analyst",
    "created_at": "2026-04-02T10:00:00Z"
  },
  "message": "Agent created"
}
```

**错误：**

| 场景 | 错误码 |
|------|--------|
| 名称已存在 | `AGENT_NAME_CONFLICT` (409) |
| 模型未启用 | `MODEL_UNAVAILABLE` (422) |
| 名称格式非法 | `VALIDATION_ERROR` (400) |

### 2.3 获取 Agent 详情

`GET /agents/{name}`

**响应 200：**

```json
{
  "data": {
    "name": "data-analyst",
    "description": "Analyzes data and generates insights",
    "instructions": "You are a data analyst agent...",
    "model": "gpt-4o",
    "tool_groups": ["web-search", "code-executor"],
    "handoffs": [],
    "guardrails": { "input": [], "output": [], "tool": [] },
    "approval_mode": "suggest",
    "is_active": true,
    "metadata": {},
    "created_at": "2026-04-02T10:00:00Z",
    "updated_at": "2026-04-02T10:00:00Z",
    "version": 1
  }
}
```

### 2.4 更新 Agent

`PUT /agents/{name}`

请求体同 2.2，字段为可选（PATCH 语义）。

### 2.5 删除 Agent

`DELETE /agents/{name}`

**响应 200：** `{"message": "Agent deleted"}`

> 软删除。若有活跃 Session 关联该 Agent，返回 409。

### 2.6 Agent 版本管理

`GET /agents/{name}/versions` — 获取 Agent 版本列表（全量快照）。

```json
{
  "data": [
    {
      "version_number": 3,
      "status": "published",
      "change_description": "优化 instructions 提升准确率",
      "created_by": "admin",
      "created_at": "2026-04-02T10:00:00Z"
    },
    {
      "version_number": 2,
      "status": "archived",
      "created_by": "admin",
      "created_at": "2026-04-01T08:00:00Z"
    }
  ]
}
```

`GET /agents/{name}/versions/{version_number}` — 获取指定版本的完整快照（含 instructions、model、tools、handoffs、guardrails 等全部配置字段）。

`POST /agents/{name}/versions` — 从当前配置创建版本快照（可附 `change_description`）。

`POST /agents/{name}/versions/{version_number}/publish` — 发布指定版本（将其设为 published，当前版本归档）。

`POST /agents/{name}/rollback/{version_number}` — 回滚到指定版本（创建内容相同的新版本并发布）。

`GET /agents/{name}/versions/diff?from={v1}&to={v2}` — 对比两个版本的字段级差异。

`POST /agents/{name}/versions/{version_number}/tag` — 为版本添加标签（如 `stable`、`production`）。

---

## 三、对话与执行 API

### 3.1 创建 Session

`POST /sessions`

**请求体：**

```json
{
  "agent_name": "triage-agent",
  "metadata": {
    "source": "web"
  }
}
```

**响应 201：**

```json
{
  "data": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "agent_name": "triage-agent",
    "status": "active",
    "created_at": "2026-04-02T10:00:00Z"
  }
}
```

### 3.2 获取 Session 详情

`GET /sessions/{id}`

**查询参数：**

| 参数 | 类型 | 说明 |
|------|------|------|
| `include_messages` | boolean | 是否返回历史消息，默认 true |
| `message_limit` | integer | 消息数量限制，默认 50 |

**响应 200：**

```json
{
  "data": {
    "id": "550e8400-...",
    "agent_name": "triage-agent",
    "status": "active",
    "messages": [
      { "role": "user", "content": "帮我分析这个数据", "timestamp": "2026-04-02T10:01:00Z" },
      { "role": "assistant", "content": "好的，我来分析...", "timestamp": "2026-04-02T10:01:05Z" }
    ],
    "created_at": "2026-04-02T10:00:00Z",
    "updated_at": "2026-04-02T10:01:05Z"
  }
}
```

### 3.3 删除 Session

`DELETE /sessions/{id}`

### 3.4 发起 Run

`POST /sessions/{id}/run`

**请求体：**

```json
{
  "input": "帮我搜索一下 CkyClaw 的最新文档",
  "config": {
    "model_override": null,
    "max_turns": 10,
    "stream": true
  }
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `input` | string | 是 | 用户输入消息 |
| `config.model_override` | string | 否 | 覆盖 Agent 默认模型 |
| `config.max_turns` | integer | 否 | 最大执行轮次，默认 10 |
| `config.stream` | boolean | 否 | 是否流式输出，默认 true |

**非流式响应 200：**

```json
{
  "data": {
    "run_id": "660e8400-...",
    "status": "completed",
    "output": "根据搜索结果，CkyClaw 最新版本...",
    "token_usage": {
      "prompt_tokens": 850,
      "completion_tokens": 320,
      "total_tokens": 1170
    },
    "duration_ms": 4200,
    "trace_id": "770e8400-..."
  }
}
```

**流式响应：** 返回 SSE 事件流（见第八章）。

### 3.5 获取 Run 事件流（SSE）

`GET /sessions/{id}/run?stream=true`

返回 `text/event-stream`。事件详见第八章。

### 3.6 取消 Run

`POST /runs/{run_id}/cancel`

**响应 200：** `{"message": "Run cancelled"}`

> 若 Run 已完成，返回 `RUN_ALREADY_COMPLETED` (409)。

### 3.7 重试 Run

`POST /runs/{run_id}/retry`

重新执行上一次 Run 的输入，创建新 Run。

---

## 四、执行记录 API

### 4.1 执行记录列表

`GET /executions`

**查询参数：**

| 参数 | 类型 | 说明 |
|------|------|------|
| `agent_name` | string | 按 Agent 筛选 |
| `status` | string | `running` / `completed` / `failed` / `cancelled` |
| `start_time` | datetime | 起始时间 |
| `end_time` | datetime | 结束时间 |
| `min_duration_ms` | integer | 最小耗时 |

**响应 200：**

```json
{
  "data": [
    {
      "run_id": "660e8400-...",
      "session_id": "550e8400-...",
      "agent_name": "triage-agent",
      "status": "completed",
      "input_preview": "帮我分析...",
      "output_preview": "根据搜索...",
      "token_usage": { "total_tokens": 1170 },
      "duration_ms": 4200,
      "trace_id": "770e8400-...",
      "created_at": "2026-04-02T10:01:00Z"
    }
  ],
  "total": 89
}
```

### 4.2 执行详情

`GET /executions/{run_id}`

### 4.3 Trace 详情

`GET /executions/{run_id}/trace`

**响应 200：**

```json
{
  "data": {
    "trace_id": "770e8400-...",
    "run_id": "660e8400-...",
    "workflow_name": "triage → data-analyst",
    "duration_ms": 8200,
    "spans": [
      {
        "span_id": "aaa-...",
        "parent_span_id": null,
        "type": "agent",
        "name": "triage-agent",
        "status": "completed",
        "start_time": "2026-04-02T10:01:00.000Z",
        "end_time": "2026-04-02T10:01:03.100Z",
        "duration_ms": 3100,
        "token_usage": { "prompt_tokens": 500, "completion_tokens": 200, "total_tokens": 700 },
        "metadata": {},
        "children": [
          {
            "span_id": "bbb-...",
            "parent_span_id": "aaa-...",
            "type": "llm",
            "name": "gpt-4o",
            "status": "completed",
            "duration_ms": 2800,
            "token_usage": { "prompt_tokens": 500, "completion_tokens": 200, "total_tokens": 700 }
          },
          {
            "span_id": "ccc-...",
            "parent_span_id": "aaa-...",
            "type": "handoff",
            "name": "→ data-analyst",
            "status": "completed",
            "duration_ms": 50
          }
        ]
      },
      {
        "span_id": "ddd-...",
        "parent_span_id": null,
        "type": "agent",
        "name": "data-analyst",
        "status": "completed",
        "duration_ms": 5000,
        "children": ["..."]
      }
    ]
  }
}
```

---

## 五、工具与 MCP API

### 5.1 工具列表

`GET /tools`

```json
{
  "data": [
    {
      "name": "web_search",
      "group": "web-search",
      "description": "Search the web for information",
      "parameters_schema": { "type": "object", "properties": { "query": { "type": "string" } } },
      "source": "builtin"
    }
  ]
}
```

### 5.2 工具组列表

`GET /tool-groups`

```json
{
  "data": [
    {
      "name": "web-search",
      "tools": ["web_search", "fetch_page"],
      "description": "Web search and browsing tools"
    }
  ]
}
```

### 5.3 MCP Server 管理

`GET /mcp/servers` — 列表。

`PUT /mcp/servers/{id}` — 更新配置。

```json
{
  "name": "file-server",
  "transport_type": "stdio",
  "command": "npx @modelcontextprotocol/server-filesystem /data",
  "auth_config": null,
  "is_enabled": true
}
```

### 5.4 Skill 管理

`GET /skills` — Skill 列表。

`POST /skills/install` — 安装 Skill 包。

```json
{
  "source": "url",
  "url": "https://registry.ckyclaw.dev/skills/data-analysis-v1.0.skill"
}
```

`PUT /skills/{name}/toggle` — 启用/禁用。

```json
{ "is_enabled": false }
```

---

## 六、用户与权限 API

### 6.1 认证

`POST /auth/login`

```json
{
  "username": "admin",
  "password": "..."
}
```

**响应 200：**

```json
{
  "data": {
    "access_token": "eyJhbGc...",
    "refresh_token": "dGhpcyBp...",
    "token_type": "Bearer",
    "expires_in": 900
  }
}
```

`POST /auth/refresh`

```json
{ "refresh_token": "dGhpcyBp..." }
```

`POST /auth/logout` — 使当前 Token 失效。

### 6.2 用户管理

`GET /users` — 用户列表（Admin 权限）。
`POST /users` — 创建用户（Admin）。

```json
{
  "username": "zhang3",
  "email": "zhang3@example.com",
  "password": "...",
  "role": "Developer",
  "org_id": "...",
  "team_ids": ["..."]
}
```

`GET /users/{id}` — 用户详情。
`PUT /users/{id}` — 更新用户。

### 6.3 组织与团队

`GET /organizations` — 组织列表。
`POST /organizations` — 创建组织。

```json
{
  "name": "CkyClaw Corp",
  "description": "Main organization",
  "quota_config": {
    "monthly_token_limit": 10000000,
    "max_concurrent_runs": 50,
    "max_agents": 100
  }
}
```

`GET /organizations/{id}/teams` — 团队列表。
`POST /organizations/{id}/teams` — 创建团队。

```json
{
  "name": "Research Team",
  "description": "AI research team",
  "budget_limit": 5000.0
}
```

### 6.4 角色管理

`GET /roles` — 角色列表。
`POST /roles` — 创建角色。

```json
{
  "name": "Reviewer",
  "permissions": ["agent:read", "session:read", "execution:read", "supervision:approve"],
  "description": "Can view and approve agent actions"
}
```

**权限标识格式：** `{resource}:{action}`

| 资源 | 可用操作 |
|------|---------|
| `agent` | `read`, `write`, `delete` |
| `session` | `read`, `write`, `delete` |
| `execution` | `read` |
| `supervision` | `read`, `pause`, `inject`, `takeover`, `approve`, `rules` |
| `apm` | `read`, `alerts` |
| `provider` | `read`, `write`, `delete` |
| `user` | `read`, `write`, `delete` |
| `channel` | `read`, `write` |
| `token-audit` | `read`, `export` |

---

## 七、人工监督 API

### 7.1 活跃会话列表

`GET /supervision/sessions`

**查询参数：**

| 参数 | 类型 | 说明 |
|------|------|------|
| `agent_name` | string | 按 Agent 筛选 |
| `status` | string | `running` / `paused` / `taken_over` |

**响应 200：**

```json
{
  "data": [
    {
      "session_id": "550e8400-...",
      "user": { "id": "...", "username": "zhang3" },
      "agent_name": "triage-agent",
      "status": "running",
      "current_run_id": "660e8400-...",
      "duration_sec": 45,
      "token_used": 1200,
      "started_at": "2026-04-02T10:00:00Z"
    }
  ]
}
```

### 7.2 暂停 / 恢复

`POST /supervision/sessions/{id}/pause`

```json
{ "reason": "Need to review tool call" }
```

`POST /supervision/sessions/{id}/resume`

```json
{
  "injected_instructions": "请不要调用外部 API，改用本地数据分析"
}
```

### 7.3 接管 / 释放

`POST /supervision/sessions/{id}/takeover`

```json
{ "reason": "Agent unable to handle this request" }
```

接管后，监督员可直接发送消息：

`POST /supervision/sessions/{id}/inject`

```json
{
  "inject_type": "reply",
  "content": "请稍候，正在为您人工处理..."
}
```

| inject_type | 说明 |
|-------------|------|
| `system` | 追加系统指令（恢复后 Agent 可见） |
| `reply` | 直接回复用户（替代 Agent） |
| `context` | 补充上下文信息 |
| `override` | 覆盖最后一条 Agent 输出 |

`POST /supervision/sessions/{id}/release` — 释放接管，交还 Agent。

### 7.4 审批管理

`GET /supervision/approvals`

**查询参数：**

| 参数 | 类型 | 说明 |
|------|------|------|
| `status` | string | `pending` / `approved` / `rejected` / `timeout` |
| `agent_name` | string | 按 Agent 筛选 |

**响应 200：**

```json
{
  "data": [
    {
      "id": "880e8400-...",
      "run_id": "660e8400-...",
      "session_id": "550e8400-...",
      "agent_name": "data-analyst",
      "trigger": "tool_call",
      "content": {
        "tool_name": "write_file",
        "arguments": { "path": "/tmp/report.csv", "content": "..." }
      },
      "risk_level": "HIGH",
      "status": "pending",
      "created_at": "2026-04-02T10:02:00Z"
    }
  ]
}
```

`POST /supervision/approvals`

审批操作：

```json
{
  "approval_id": "880e8400-...",
  "action": "approve",
  "comment": "Approved for write to tmp"
}
```

| action | 说明 |
|--------|------|
| `approve` | 批准 |
| `reject` | 拒绝（Runner 终止或重试） |
| `modify` | 修改后批准（附带修改内容） |

### 7.5 监督规则

`GET /supervision/rules` — 规则列表。

`POST /supervision/rules` — 创建规则。

```json
{
  "name": "High-risk tool approval",
  "trigger_type": "tool_call",
  "trigger_config": {
    "tool_names": ["write_file", "execute_sql"],
    "agent_names": ["*"]
  },
  "action": "require_approval",
  "approver_roles": ["Admin", "Operator"],
  "timeout_sec": 300,
  "timeout_policy": "reject",
  "scope": "global"
}
```

---

## 八、实时事件协议（AsyncAPI）

### 8.1 SSE 事件流（Agent 执行）

**连接：** `GET /sessions/{id}/run` （`Accept: text/event-stream`）

**事件格式：**

```
event: {event_type}
data: {json_payload}

```

#### 事件类型

| 事件 | 触发时机 | payload |
|------|---------|---------|
| `run_start` | Run 开始 | `{ "run_id": "...", "agent_name": "..." }` |
| `agent_start` | Agent 开始执行 | `{ "agent_name": "...", "span_id": "..." }` |
| `text_delta` | LLM 输出增量文本 | `{ "delta": "你好", "agent_name": "..." }` |
| `tool_call_start` | 工具调用开始 | `{ "tool_name": "...", "arguments": {...}, "span_id": "..." }` |
| `tool_call_end` | 工具调用结束 | `{ "tool_name": "...", "result_preview": "...", "status": "success", "duration_ms": 1200 }` |
| `handoff` | Agent 移交 | `{ "from_agent": "triage", "to_agent": "analyst", "reason": "..." }` |
| `approval_request` | 需要审批 | `{ "approval_id": "...", "trigger": "tool_call", "content": {...} }` |
| `approval_resolved` | 审批已处理 | `{ "approval_id": "...", "action": "approve" }` |
| `guardrail_trip` | 护栏拦截 | `{ "guardrail": "prompt-injection", "message": "..." }` |
| `agent_end` | Agent 执行结束 | `{ "agent_name": "...", "token_usage": {...} }` |
| `run_end` | Run 结束 | `{ "run_id": "...", "status": "completed", "total_tokens": 1170, "duration_ms": 4200 }` |
| `error` | 执行错误 | `{ "code": "...", "message": "..." }` |

### 8.2 WebSocket 事件（监督面板）

**连接：** `ws://{host}/api/v1/supervision/ws?token={jwt}`

**服务端 → 客户端事件：**

| 事件 | payload |
|------|---------|
| `session_active` | `{ "session_id": "...", "user": {...}, "agent_name": "...", "started_at": "..." }` |
| `session_end` | `{ "session_id": "...", "reason": "completed" }` |
| `message` | `{ "session_id": "...", "role": "user\|assistant", "content": "...", "timestamp": "..." }` |
| `tool_call` | `{ "session_id": "...", "tool_name": "...", "arguments": {...}, "result": "...", "status": "..." }` |
| `handoff` | `{ "session_id": "...", "from": "...", "to": "..." }` |
| `approval_request` | `{ "session_id": "...", "approval_id": "...", "trigger": "...", "content": {...}, "risk_level": "..." }` |
| `approval_resolved` | `{ "session_id": "...", "approval_id": "...", "action": "...", "by": "..." }` |
| `session_paused` | `{ "session_id": "...", "by": "...", "reason": "..." }` |
| `session_resumed` | `{ "session_id": "...", "by": "..." }` |
| `session_taken_over` | `{ "session_id": "...", "by": "...", "reason": "..." }` |
| `token_update` | `{ "session_id": "...", "delta_tokens": 150, "cumulative_tokens": 1200 }` |

**客户端 → 服务端命令：**

| 命令 | payload | 说明 |
|------|---------|------|
| `subscribe` | `{ "session_ids": ["..."] }` | 订阅指定会话事件 |
| `unsubscribe` | `{ "session_ids": ["..."] }` | 取消订阅 |
| `subscribe_all` | `{}` | 订阅所有活跃会话 |
| `ping` | `{}` | 心跳（服务端回 `pong`） |

---

## 九、渠道管理 API

### 9.1 渠道状态列表

`GET /channels`

```json
{
  "data": [
    {
      "name": "telegram",
      "channel_type": "telegram",
      "status": "running",
      "config": {
        "bot_token_set": true,
        "polling_interval_sec": 1
      },
      "is_enabled": true,
      "last_health_check": "2026-04-02T10:00:00Z"
    }
  ]
}
```

### 9.2 更新渠道配置

`PUT /channels/{name}/config`

```json
{
  "config": {
    "bot_token": "123456:ABC-...",
    "allowed_chat_ids": ["-1001234567890"],
    "default_agent": "triage-agent"
  },
  "is_enabled": true
}
```

> `bot_token` 等敏感字段在响应中不返回明文，仅返回 `bot_token_set: true`。

### 9.3 重启渠道

`POST /channels/{name}/restart`

---

## 十、模型厂商管理 API

### 10.1 厂商 CRUD

`GET /providers` — 列表。

```json
{
  "data": [
    {
      "id": "990e8400-...",
      "name": "OpenAI",
      "provider_type": "openai",
      "base_url": "https://api.openai.com/v1",
      "auth_type": "api_key",
      "api_key_set": true,
      "is_enabled": true,
      "model_count": 5,
      "last_health_check": "2026-04-02T10:00:00Z",
      "health_status": "healthy"
    }
  ]
}
```

`POST /providers` — 注册。

```json
{
  "name": "OpenAI",
  "provider_type": "openai",
  "base_url": "https://api.openai.com/v1",
  "api_key": "sk-...",
  "auth_type": "api_key",
  "rate_limit_config": {
    "requests_per_minute": 500,
    "tokens_per_minute": 150000
  }
}
```

> `api_key` 仅在创建/更新时提交，存储使用 AES-256-GCM 加密，响应中永不返回。

`PUT /providers/{id}` — 更新。
`DELETE /providers/{id}` — 删除（需先删除关联模型）。

### 10.2 连通性测试

`POST /providers/{id}/test`

```json
{
  "data": {
    "status": "success",
    "latency_ms": 230,
    "models_available": 12
  }
}
```

### 10.3 启用/禁用

`PUT /providers/{id}/toggle`

```json
{ "is_enabled": false }
```

### 10.4 模型管理

`GET /providers/{id}/models` — 厂商下模型列表。

`POST /providers/{id}/models` — 添加模型。

```json
{
  "model_name": "gpt-4o",
  "display_name": "GPT-4o",
  "context_window": 128000,
  "pricing": {
    "prompt_per_1k_tokens": 0.005,
    "completion_per_1k_tokens": 0.015
  },
  "is_enabled": true,
  "is_default": false
}
```

`PUT /providers/{id}/models/{model_id}` — 更新模型配置。

### 10.5 全局模型视图

`GET /models` — 所有已启用模型（跨厂商，供 Agent 配置时选择）。

`PUT /models/default` — 设置全局默认模型。

```json
{ "model_id": "..." }
```

---

## 十一、APM API

### 11.1 查询指标

`GET /apm/metrics`

**查询参数：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `metric` | string | 是 | `task_count` / `success_rate` / `p95_latency` / `total_cost` / `total_tokens` |
| `start_time` | datetime | 是 | 起始时间 |
| `end_time` | datetime | 是 | 结束时间 |
| `group_by` | string | 否 | `agent` / `model` / `provider` / `hour` / `day` |
| `agent_name` | string | 否 | 按 Agent 筛选 |

**响应 200：**

```json
{
  "data": {
    "metric": "success_rate",
    "value": 97.3,
    "unit": "%",
    "time_range": { "start": "...", "end": "..." },
    "series": [
      { "time": "2026-04-02T09:00:00Z", "value": 98.1 },
      { "time": "2026-04-02T10:00:00Z", "value": 96.5 }
    ]
  }
}
```

### 11.2 链路追踪查询

`GET /apm/traces`

**查询参数：**

| 参数 | 类型 | 说明 |
|------|------|------|
| `trace_id` | string | 精确查找 |
| `agent_name` | string | 按 Agent |
| `status` | string | `completed` / `failed` / `running` |
| `min_duration_ms` | integer | 最小耗时 |
| `start_time` / `end_time` | datetime | 时间范围 |

`GET /apm/traces/{trace_id}` — Trace 详情（含所有 Span）。

### 11.3 告警管理

`GET /apm/alerts` — 告警列表（含活跃和历史）。

```json
{
  "data": [
    {
      "id": "...",
      "rule_id": "...",
      "rule_name": "任务失败率过高",
      "status": "active",
      "severity": "critical",
      "metric_value": 8.2,
      "threshold": 5.0,
      "fired_at": "2026-04-02T10:05:00Z",
      "resolved_at": null
    }
  ]
}
```

`POST /apm/alerts/rules` — 创建告警规则。

```json
{
  "name": "Agent response too slow",
  "metric_type": "agent",
  "metric_name": "p95_latency",
  "condition": ">",
  "threshold": 3000,
  "duration_sec": 60,
  "severity": "warning",
  "scope_type": "global",
  "notification_channels": ["email", "webhook"]
}
```

`PUT /apm/alerts/rules/{id}` — 更新规则。
`DELETE /apm/alerts/rules/{id}` — 删除规则。

### 11.4 仪表盘聚合数据

`GET /apm/dashboard`

**查询参数：** `time_range`（`1h` / `6h` / `24h` / `7d` / `30d`）

返回仪表盘所需的预聚合数据（活跃 Run 数、成功率、P95 延迟、当日成本、Token 消耗、趋势、Agent 排名、活跃告警）。

---

## 十二、Token 审计 API

### 12.1 审计日志查询

`GET /token-audit/logs`

**查询参数：**

| 参数 | 类型 | 说明 |
|------|------|------|
| `user_id` | UUID | 按用户 |
| `agent_name` | string | 按 Agent |
| `model` | string | 按模型 |
| `provider` | string | 按厂商 |
| `org_id` | UUID | 按组织 |
| `team_id` | UUID | 按团队 |
| `start_time` | datetime | 起始时间 |
| `end_time` | datetime | 结束时间 |
| `min_tokens` | integer | 最低 Token 数 |
| `min_cost` | float | 最低费用 |

**响应 200：**

```json
{
  "data": [
    {
      "trace_id": "...",
      "span_id": "...",
      "user_id": "...",
      "agent_name": "data-analyst",
      "model": "gpt-4o",
      "provider": "openai",
      "prompt_tokens": 850,
      "completion_tokens": 320,
      "total_tokens": 1170,
      "cost_usd": 0.0089,
      "session_id": "...",
      "run_id": "...",
      "timestamp": "2026-04-02T10:01:05Z"
    }
  ],
  "total": 1523
}
```

### 12.2 导出

`GET /token-audit/logs/export`

**查询参数：** 同 12.1 + `format`（`csv` / `xlsx`）

**响应：** `Content-Type: text/csv` 或 `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`

### 12.3 统计概览

`GET /token-audit/stats/summary`

**查询参数：** `start_time`, `end_time`

```json
{
  "data": {
    "total_tokens": 1230000,
    "total_cost_usd": 156.30,
    "daily_avg_tokens": 41000,
    "active_users": 23,
    "request_count": 4521
  }
}
```

### 12.4 趋势数据

`GET /token-audit/stats/trend`

**查询参数：**

| 参数 | 类型 | 说明 |
|------|------|------|
| `start_time` | datetime | 起始 |
| `end_time` | datetime | 结束 |
| `granularity` | string | `day` / `week` / `month` |
| `group_by` | string | `agent` / `model` / `provider` / `team`（可选） |

```json
{
  "data": {
    "series": [
      { "time": "2026-04-01", "total_tokens": 38000, "cost_usd": 4.90 },
      { "time": "2026-04-02", "total_tokens": 45000, "cost_usd": 5.80 }
    ]
  }
}
```

### 12.5 维度分布

`GET /token-audit/stats/breakdown`

**查询参数：** `dimension`（`agent` / `model` / `provider` / `team`）、`start_time`、`end_time`

```json
{
  "data": {
    "dimension": "agent",
    "items": [
      { "name": "triage-agent", "total_tokens": 450000, "cost_usd": 58.20, "percentage": 36.5 },
      { "name": "data-analyst", "total_tokens": 380000, "cost_usd": 49.10, "percentage": 30.9 }
    ]
  }
}
```

### 12.6 Top-N 排名

`GET /token-audit/stats/top`

**查询参数：** `dimension`（`user` / `agent` / `model`）、`period`（`day` / `week` / `month`）、`limit`（默认 10）

### 12.7 预算进度

`GET /token-audit/budget/progress`

```json
{
  "data": {
    "levels": [
      {
        "scope": "organization",
        "name": "CkyClaw Corp",
        "used_tokens": 980000,
        "limit_tokens": 10000000,
        "used_cost_usd": 156.30,
        "limit_cost_usd": 200.00,
        "usage_percentage": 78.15
      },
      {
        "scope": "team",
        "name": "Research Team",
        "used_cost_usd": 89.20,
        "limit_cost_usd": 150.00,
        "usage_percentage": 59.47
      }
    ]
  }
}
```

---

## 十三、Agent Team API

### 13.1 Team 列表

`GET /teams`

**Query 参数：**

| 参数 | 类型 | 说明 |
|------|------|------|
| page / page_size | int | 分页 |
| protocol | string | 按协议类型筛选（sequential / parallel / debate / round_robin / broadcast） |

**响应 200：**

```json
{
  "data": [
    {
      "name": "research_report_team",
      "display_name": "调研分析团队",
      "description": "对指定主题进行多源调研、数据分析和报告撰写",
      "protocol": "sequential",
      "members": [
        { "agent_ref": "researcher", "role": "信息收集员" },
        { "agent_ref": "data_analyst", "role": "数据分析师" },
        { "agent_ref": "report_writer", "role": "报告撰写员" }
      ],
      "is_builtin": true,
      "created_at": "2026-04-02T00:00:00Z"
    }
  ],
  "pagination": { "page": 1, "page_size": 20, "total": 6 }
}
```

### 13.2 创建 Team

`POST /teams`

**请求体：**

| 字段 | 必填 | 说明 |
|------|------|------|
| name | ✅ | Team 唯一标识符（`^[a-z][a-z0-9_-]{2,63}$`） |
| display_name | ✅ | 显示名称 |
| description | | 描述 |
| protocol | ✅ | 协作协议 |
| members | ✅ | 成员列表（至少 2 个） |
| termination | | 终止条件（max_rounds, timeout_seconds, consensus_threshold） |
| result_strategy | | 结果聚合策略，默认 `last` |
| context_sharing | | 上下文共享策略，默认 `sequential` |

**响应 201：** 返回完整 Team 对象。

### 13.3 获取 Team 详情

`GET /teams/{name}`

### 13.4 更新 Team

`PUT /teams/{name}` — 请求体同创建，name 不可修改。

### 13.5 删除 Team

`DELETE /teams/{name}` — 内置 Team 不可删除。

### 13.6 Team 模板列表

`GET /teams/templates` — 返回所有内置 Team 模板，可用于快速创建。

---

## 十四、定时与批量任务 API

### 14.1 创建定时任务

`POST /scheduled-runs`

**请求体：**

| 字段 | 必填 | 说明 |
|------|------|------|
| agent_name | ✅ | 执行的 Agent |
| cron_expression | ✅ | Cron 表达式 |
| input_template | ✅ | 输入模板（支持 `{{date}}` 等变量） |
| run_config_override | | 可选 RunConfig 覆盖 |
| notification | | 完成通知配置（email / webhook / in_app） |
| max_retries | | 最大重试次数（默认 0） |

**响应 201：**

```json
{
  "schedule_id": "sch_abc123",
  "agent_name": "daily-report",
  "cron_expression": "0 9 * * *",
  "next_run_at": "2026-04-03T09:00:00Z",
  "is_enabled": true,
  "created_by": "admin"
}
```

### 14.2 定时任务列表

`GET /scheduled-runs` — 支持按 agent_name、is_enabled 筛选。

### 14.3 更新定时任务

`PUT /scheduled-runs/{schedule_id}` — 可更新 cron_expression、input_template、is_enabled 等。

### 14.4 删除定时任务

`DELETE /scheduled-runs/{schedule_id}`

### 14.5 启停定时任务

`POST /scheduled-runs/{schedule_id}/enable`

`POST /scheduled-runs/{schedule_id}/disable`

### 14.6 创建批量任务

`POST /batch-runs`

**请求体：**

| 字段 | 必填 | 说明 |
|------|------|------|
| agent_name | ✅ | 执行的 Agent |
| inputs | ✅ | 输入列表（JSON Array） |
| concurrency | | 最大并行度（默认 5） |
| run_config_override | | 可选 RunConfig 覆盖 |
| on_item_complete | | 单项完成 Webhook URL |

**响应 201：**

```json
{
  "batch_id": "bat_xyz789",
  "agent_name": "resume-screener",
  "total_items": 200,
  "concurrency": 5,
  "status": "running",
  "created_by": "admin"
}
```

### 14.7 批量任务进度

`GET /batch-runs/{batch_id}`

**响应 200：**

```json
{
  "batch_id": "bat_xyz789",
  "status": "running",
  "progress": {
    "total": 200,
    "completed": 87,
    "failed": 3,
    "in_progress": 5,
    "pending": 105
  },
  "created_at": "2026-04-02T10:00:00Z"
}
```

### 14.8 取消批量任务

`POST /batch-runs/{batch_id}/cancel` — 取消未开始的项，等待进行中的项完成。

---

## 十五、Agent 评估与反馈 API

### 15.1 提交 Run 反馈

`POST /runs/{run_id}/feedback`

**请求体：**

| 字段 | 必填 | 说明 |
|------|------|------|
| rating | ✅ | 评分：`thumbs_up` 或 `thumbs_down` |
| comment | | 文字反馈（最长 1000 字） |

**响应 201：**

```json
{
  "feedback_id": "fb_123",
  "run_id": "run_abc",
  "user_id": "user_001",
  "rating": "thumbs_up",
  "created_at": "2026-04-02T10:00:00Z"
}
```

### 15.2 Agent 评估报表

`GET /agents/{name}/evaluation`

**Query 参数：**

| 参数 | 说明 |
|------|------|
| period | 时间范围：`7d` / `30d` / `90d` |
| version | 可选，按版本号筛选 |

**响应 200：**

```json
{
  "agent_name": "data-analyst",
  "period": "30d",
  "metrics": {
    "total_runs": 342,
    "success_rate": 0.94,
    "avg_token_per_run": 2150,
    "avg_latency_ms": 3200,
    "thumbs_up_rate": 0.87,
    "guardrail_trigger_rate": 0.02,
    "tool_success_rate": 0.96
  },
  "version_comparison": [
    { "version": 3, "success_rate": 0.96, "thumbs_up_rate": 0.90 },
    { "version": 2, "success_rate": 0.91, "thumbs_up_rate": 0.82 }
  ]
}
```

### 15.3 反馈列表

`GET /agents/{name}/feedback`

**Query 参数：** page / page_size / rating（thumbs_up / thumbs_down）/ date_from / date_to

**响应 200：** 分页返回 feedback 列表（含 run_id、user_id、rating、comment、created_at）。

---

## 十六、通用 Schema 定义

### 13.1 Agent

```json
{
  "type": "object",
  "properties": {
    "name": { "type": "string", "pattern": "^[a-z][a-z0-9-]{2,63}$" },
    "description": { "type": "string", "maxLength": 500 },
    "instructions": { "type": "string", "maxLength": 50000 },
    "model": { "type": "string" },
    "tool_groups": { "type": "array", "items": { "type": "string" } },
    "handoffs": { "type": "array", "items": { "type": "string" } },
    "guardrails": {
      "type": "object",
      "properties": {
        "input": { "type": "array", "items": { "type": "string" } },
        "output": { "type": "array", "items": { "type": "string" } },
        "tool": { "type": "array", "items": { "type": "string" } }
      }
    },
    "approval_mode": { "type": "string", "enum": ["suggest", "auto-edit", "full-auto"] },
    "metadata": { "type": "object" }
  },
  "required": ["name", "instructions", "model"]
}
```

### 13.2 Session

```json
{
  "type": "object",
  "properties": {
    "id": { "type": "string", "format": "uuid" },
    "agent_name": { "type": "string" },
    "user_id": { "type": "string", "format": "uuid" },
    "status": { "type": "string", "enum": ["active", "paused", "taken_over", "closed"] },
    "messages": { "type": "array", "items": { "$ref": "#/Message" } },
    "created_at": { "type": "string", "format": "date-time" },
    "updated_at": { "type": "string", "format": "date-time" }
  }
}
```

### 13.3 Run

```json
{
  "type": "object",
  "properties": {
    "id": { "type": "string", "format": "uuid" },
    "session_id": { "type": "string", "format": "uuid" },
    "agent_name": { "type": "string" },
    "status": { "type": "string", "enum": ["running", "completed", "failed", "cancelled", "waiting_approval"] },
    "input": { "type": "string" },
    "output": { "type": "string" },
    "token_usage": { "$ref": "#/TokenUsage" },
    "duration_ms": { "type": "integer" },
    "trace_id": { "type": "string", "format": "uuid" },
    "created_at": { "type": "string", "format": "date-time" }
  }
}
```

### 13.4 TokenUsage

```json
{
  "type": "object",
  "properties": {
    "prompt_tokens": { "type": "integer" },
    "completion_tokens": { "type": "integer" },
    "total_tokens": { "type": "integer" }
  }
}
```

### 13.5 Message

```json
{
  "type": "object",
  "properties": {
    "role": { "type": "string", "enum": ["user", "assistant", "system", "tool"] },
    "content": { "type": "string" },
    "tool_calls": { "type": "array", "items": { "$ref": "#/ToolCall" } },
    "timestamp": { "type": "string", "format": "date-time" }
  }
}
```

### 13.6 Span

```json
{
  "type": "object",
  "properties": {
    "span_id": { "type": "string" },
    "parent_span_id": { "type": "string", "nullable": true },
    "type": { "type": "string", "enum": ["agent", "llm", "tool", "handoff", "guardrail", "approval"] },
    "name": { "type": "string" },
    "status": { "type": "string", "enum": ["running", "completed", "failed"] },
    "start_time": { "type": "string", "format": "date-time" },
    "end_time": { "type": "string", "format": "date-time" },
    "duration_ms": { "type": "integer" },
    "token_usage": { "$ref": "#/TokenUsage" },
    "metadata": { "type": "object" },
    "children": { "type": "array", "items": { "$ref": "#/Span" } }
  }
}
```

---

## 十七、配置热更新与国际化 API

### 17.1 配置变更历史

#### `GET /api/v1/config/changes`

查询配置变更审计记录。

**Query Parameters：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|:----:|------|
| config_key | string | 否 | 按配置项键名筛选 |
| operator_id | string (UUID) | 否 | 按操作人筛选 |
| start_time | string (ISO 8601) | 否 | 起始时间 |
| end_time | string (ISO 8601) | 否 | 结束时间 |
| limit | integer | 否 | 分页大小（默认 20） |
| offset | integer | 否 | 偏移量（默认 0） |

**Response 200：**

```json
{
  "data": [
    {
      "id": "uuid",
      "config_key": "agent.default_model",
      "old_value": "gpt-4o",
      "new_value": "claude-sonnet-4",
      "operator_id": "uuid",
      "operator_name": "admin",
      "change_description": "切换默认模型到 Claude",
      "created_at": "2026-04-02T10:30:00Z"
    }
  ],
  "total": 42,
  "limit": 20,
  "offset": 0
}
```

### 17.2 配置回滚

#### `POST /api/v1/config/rollback`

将指定配置项回滚到历史变更点的值。

**Request Body：**

| 字段 | 类型 | 必填 | 说明 |
|------|------|:----:|------|
| change_id | string (UUID) | 是 | 目标变更记录 ID，系统将恢复该记录的 `old_value` |

**Response 200：**

```json
{
  "data": {
    "config_key": "agent.default_model",
    "restored_value": "gpt-4o",
    "new_change_id": "uuid"
  },
  "message": "配置已回滚"
}
```

### 17.3 配置更新

#### `PUT /api/v1/config/{key}`

更新系统配置项。变更自动记录审计日志，并通过 Redis Pub/Sub 通知所有实例。

**Path Parameters：**

| 参数 | 类型 | 说明 |
|------|------|------|
| key | string | 配置项键名（如 `agent.default_model`、`guardrail.prompt_injection.enabled`） |

**Request Body：**

| 字段 | 类型 | 必填 | 说明 |
|------|------|:----:|------|
| value | any | 是 | 新配置值（字符串 / 数字 / 布尔 / JSON 对象） |
| description | string | 否 | 变更说明 |

**Response 200：**

```json
{
  "data": {
    "config_key": "agent.default_model",
    "old_value": "gpt-4o",
    "new_value": "claude-sonnet-4",
    "change_id": "uuid",
    "effective_at": "2026-04-02T10:30:05Z"
  },
  "message": "配置已更新"
}
```

### 17.4 Agent 多语言 Instructions 管理

#### `GET /api/v1/agents/{name}/locales`

获取 Agent 的所有语言版本 Instructions。

**Response 200：**

```json
{
  "data": [
    {
      "locale": "zh-CN",
      "instructions": "你是一名专业的数据分析师...",
      "is_default": true,
      "updated_at": "2026-04-02T10:00:00Z"
    },
    {
      "locale": "en-US",
      "instructions": "You are a professional data analyst...",
      "is_default": false,
      "updated_at": "2026-04-02T09:00:00Z"
    }
  ]
}
```

#### `POST /api/v1/agents/{name}/locales`

为 Agent 新增一个语言版本的 Instructions。

**Request Body：**

| 字段 | 类型 | 必填 | 说明 |
|------|------|:----:|------|
| locale | string | 是 | 语言标识（BCP 47 格式，如 `zh-CN`、`en-US`、`ja-JP`） |
| instructions | string | 是 | 该语言版本的 Instructions 全文 |
| is_default | boolean | 否 | 是否设为默认语言版本（默认 false） |

#### `PUT /api/v1/agents/{name}/locales/{locale}`

更新指定语言版本的 Instructions。

**Request Body：**

| 字段 | 类型 | 必填 | 说明 |
|------|------|:----:|------|
| instructions | string | 是 | 更新后的 Instructions 全文 |
| is_default | boolean | 否 | 是否设为默认 |

#### `DELETE /api/v1/agents/{name}/locales/{locale}`

删除指定语言版本的 Instructions。默认语言版本不可删除。

---

*文档版本：v1.2.0*
*最后更新：2026-04-02*
*作者：CkyClaw Team*
