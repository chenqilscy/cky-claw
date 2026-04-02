# CkyClaw PRD-基础设施 v2.0

## 文档信息

| 字段 | 内容 |
|------|------|
| 版本 | v2.0.8 |
| 日期 | 2026-04-02 |
| 状态 | 进行中 |
| 维护人 | CkyClaw Team |
| 依赖 | CkyClaw PRD v2.0（总纲）、CkyClaw API Design v1.2、CkyClaw 数据模型详细设计 v1.3 |

> 本文档是 CkyClaw PRD v2.0 的分册，包含第十一章（API 设计）、第十二章（数据模型）、第十三章（用户系统与安全管理）、第十四章（部署与运维）、第十五章（非功能性需求）。

---

## 十一、API 设计

### 11.1 API 概览

CkyClaw 对外暴露 RESTful API。由于 CkyClaw Framework嵌入后端运行，所有 Agent/Session/Run 操作由 CkyClaw 统一管理，不再需要代理转发。

> 各 API 的详细请求/响应 Schema、错误码清单、SSE/WebSocket 事件协议、通用 JSON Schema 定义详见《CkyClaw API 接口设计 v1.2》。

### 11.2 认证方式

| 方式 | 适用场景 |
|------|---------|
| JWT Bearer Token | Web/移动端用户 |
| API Key | 服务端间调用 |
| OAuth 2.0 | 第三方应用集成 |

### 11.3 Agent 管理 API

| Method | Path | 说明 |
|--------|------|------|
| GET | `/api/v1/agents` | Agent 列表 |
| POST | `/api/v1/agents` | 创建 Agent（含 instructions、tools、handoffs） |
| GET | `/api/v1/agents/{name}` | 获取 Agent 详情 |
| PUT | `/api/v1/agents/{name}` | 更新 Agent 配置 |
| DELETE | `/api/v1/agents/{name}` | 删除 Agent |
| GET | `/api/v1/agents/{name}/versions` | Instructions 版本列表 |
| POST | `/api/v1/agents/{name}/versions` | 创建版本快照 |
| POST | `/api/v1/agents/{name}/rollback/{version}` | 回滚到指定版本 |

### 11.4 对话与执行 API

| Method | Path | 说明 |
|--------|------|------|
| POST | `/api/v1/sessions` | 创建 Session |
| GET | `/api/v1/sessions/{id}` | Session 详情（含历史消息） |
| DELETE | `/api/v1/sessions/{id}` | 删除 Session |
| POST | `/api/v1/sessions/{id}/run` | 在 Session 中发起 Run（指定 Agent + 用户输入） |
| GET | `/api/v1/sessions/{id}/run` | SSE 流式获取 Run 执行事件 |
| POST | `/api/v1/runs/{run_id}/cancel` | 取消执行 |
| POST | `/api/v1/runs/{run_id}/retry` | 重试执行 |

### 11.5 执行记录 API

| Method | Path | 说明 |
|--------|------|------|
| GET | `/api/v1/executions` | 执行记录列表（支持按 Agent、状态、时间筛选） |
| GET | `/api/v1/executions/{run_id}` | 执行详情（含 Trace 数据） |
| GET | `/api/v1/executions/{run_id}/trace` | Trace/Span 详情（完整执行图数据） |

### 11.6 工具与 MCP API

| Method | Path | 说明 |
|--------|------|------|
| GET | `/api/v1/tools` | 工具列表（按 Tool Group 分组） |
| GET | `/api/v1/tool-groups` | 工具组列表 |
| GET | `/api/v1/mcp/servers` | MCP Server 列表 |
| PUT | `/api/v1/mcp/servers/{id}` | 更新 MCP Server 配置 |
| GET | `/api/v1/skills` | Skill 列表 |
| POST | `/api/v1/skills/install` | 安装 Skill 包 |
| PUT | `/api/v1/skills/{name}/toggle` | 启用/禁用 Skill |

### 11.7 用户与权限 API

| Method | Path | 说明 |
|--------|------|------|
| POST | `/api/v1/auth/login` | 登录 |
| POST | `/api/v1/auth/refresh` | 刷新 Token |
| POST | `/api/v1/auth/logout` | 登出 |
| GET/POST | `/api/v1/users` | 用户列表/创建 |
| GET/PUT | `/api/v1/users/{id}` | 获取/更新用户 |
| GET/POST | `/api/v1/organizations` | 组织管理 |
| GET/POST | `/api/v1/organizations/{id}/teams` | 团队管理 |
| GET/POST | `/api/v1/roles` | 角色管理 |

### 11.8 人工监督 API

| Method | Path | 说明 |
|--------|------|------|
| GET | `/api/v1/supervision/sessions` | 活跃会话列表 |
| POST | `/api/v1/supervision/sessions/{id}/pause` | 暂停 |
| POST | `/api/v1/supervision/sessions/{id}/resume` | 恢复 |
| POST | `/api/v1/supervision/sessions/{id}/takeover` | 接管 |
| POST | `/api/v1/supervision/sessions/{id}/release` | 释放 |
| POST | `/api/v1/supervision/sessions/{id}/inject` | 注入消息 |
| GET/POST | `/api/v1/supervision/approvals` | 审批管理 |
| GET/POST | `/api/v1/supervision/rules` | 监督规则管理 |

### 11.9 渠道管理 API

| Method | Path | 说明 |
|--------|------|------|
| GET | `/api/v1/channels` | 渠道状态列表 |
| PUT | `/api/v1/channels/{name}/config` | 更新渠道配置 |
| POST | `/api/v1/channels/{name}/restart` | 重启渠道 |

### 11.10 模型厂商管理 API

| Method | Path | 说明 |
|--------|------|------|
| GET | `/api/v1/providers` | 厂商列表 |
| POST | `/api/v1/providers` | 注册厂商（名称、Base URL、API Key、认证方式） |
| GET | `/api/v1/providers/{id}` | 厂商详情 |
| PUT | `/api/v1/providers/{id}` | 更新厂商配置 |
| DELETE | `/api/v1/providers/{id}` | 删除厂商 |
| POST | `/api/v1/providers/{id}/test` | 连通性测试 |
| PUT | `/api/v1/providers/{id}/toggle` | 启用/禁用厂商 |
| GET | `/api/v1/providers/{id}/models` | 厂商下可用模型列表 |
| POST | `/api/v1/providers/{id}/models` | 添加模型配置 |
| PUT | `/api/v1/providers/{id}/models/{model_id}` | 更新模型配置（价格、启用状态） |
| GET | `/api/v1/models` | 所有已启用模型列表（跨厂商，供 Agent 配置选择） |
| PUT | `/api/v1/models/default` | 设置全局默认模型 |

### 11.11 APM API

| Method | Path | 说明 |
|--------|------|------|
| GET | `/api/v1/apm/metrics` | 查询指标 |
| GET | `/api/v1/apm/traces` | 查询链路追踪 |
| GET | `/api/v1/apm/traces/{trace_id}` | Trace 详情（含所有 Span） |
| GET | `/api/v1/apm/alerts` | 告警列表 |
| POST | `/api/v1/apm/alerts/rules` | 创建告警规则 |
| GET | `/api/v1/apm/dashboard` | 仪表盘数据 |

### 11.12 Token 审计 API

| Method | Path | 说明 |
|--------|------|------|
| GET | `/api/v1/token-audit/logs` | 审计日志查询（支持多维度筛选：user_id、agent_name、model、provider、org_id、team_id、时间范围、最低消耗） |
| GET | `/api/v1/token-audit/logs/export` | 导出审计日志为 CSV/Excel |
| GET | `/api/v1/token-audit/stats/summary` | 统计概览（指定时间范围的总量、均值、Top-N） |
| GET | `/api/v1/token-audit/stats/trend` | 趋势数据（按日/周/月聚合，支持 group_by 维度） |
| GET | `/api/v1/token-audit/stats/breakdown` | 维度分布（按 agent/model/provider/team 分组的占比数据） |
| GET | `/api/v1/token-audit/stats/top` | Top-N 排名（参数：dimension=user|agent|model，period，limit） |
| GET | `/api/v1/token-audit/budget/progress` | 预算进度（各层级当前消耗 vs 预算上限） |

### 11.13 API 通用规范

| 规范 | 说明 |
|------|------|
| 版本策略 | URL path 版本控制 `/api/v1/` |
| 分页 | `?limit=20&offset=0`，响应含 `total` |
| 排序 | `?sort=created_at&order=desc` |
| 错误格式 | 统一错误码 + 错误消息 + 详情 |
| 限流 | 令牌桶限流，默认 100 req/min |
| 响应格式 | 成功: `{data, message}` / 分页: `{data, total, limit, offset}` / 错误: `{error: {code, message, details}}` |---

## 十二、数据模型

### 12.1 实体关系概览

```
┌──────────┐     1:N     ┌──────────┐│   User   │────────────►│  Role    │└────┬─────┘
└──────────┘
│ 1:N
▼┌────────────────┐│ Organization   │└────────┬───────┘
│ 1:N
▼┌──────────┐
┌──────────────────┐
┌──────────────┐│  Team    │
│   AgentConfig    │────►│InstructionVer│└──────────┘
└────────┬─────────┘
└──────────────┘
│ 1:N
▼
┌──────────────────┐
┌──────────────┐
│    Session       │────►│    Run        │
└──────────────────┘
└──────┬───────┘
│ 1:N
▼
┌──────────────┐
│   Trace      │
└──────┬───────┘
│ 1:N
▼
┌──────────────┐
│    Span      │
└──────────────┘
┌────────────────┐
┌──────────────┐
┌──────────────┐
┌──────────┐│SupervisionEvent│
│SupervisionRule│
│ApprovalRequest│
│ AuditLog │└────────────────┘
└──────────────┘
└──────────────┘
└──────────┘
┌────────────────┐
┌──────────────┐│ChannelConfig   │
│  MCPConfig   │└────────────────┘
└──────────────┘
┌────────────────┐
┌──────────────┐│ProviderConfig  │──►│ ModelConfig  │└────────────────┘
└──────────────┘

```

### 12.2 核心数据实体

#### 12.2.1 Agent 与执行

| 实体 | 说明 | 核心字段 |
|------|------|---------|
| **AgentConfig** | Agent 配置定义 | name, description, instructions, model, tool_groups, handoffs, guardrails, approval_mode, org_id |
| **InstructionVersion** | Instructions 版本快照 | agent_name, version, content, created_by, created_at |
| **Session** | 对话会话 | id, agent_name, user_id, org_id, status, created_at, updated_at |
| **Run** | 一次 Agent 执行 | id, session_id, agent_name, status, input, output, token_usage, duration, created_at |
| **Trace** | 执行链路追踪 | id, run_id, workflow_name, group_id, duration, span_count, created_at |
| **Span** | 追踪中的执行步骤 | id, trace_id, parent_span_id, type(agent/llm/tool/handoff), name, status, duration, token_usage, input, output |

> 各实体的完整列级 Schema（字段类型、约束、索引）详见《CkyClaw 数据模型详细设计 v1.3》。

#### 12.2.2 用户与组织

| 实体 | 说明 | 核心字段 |
|------|------|---------|
| **User** | 用户 | username, email, password_hash, role, org_id, is_active |
| **Role** | 角色 | name, permissions, description |
| **Organization** | 组织 | name, description, quota_config, is_active |
| **Team** | 团队 | org_id, name, description, budget_limit |
| **UserPreference** | 用户偏好 | user_id, default_agent, language, notification_config |
| **ApiKey** | 用户 API Key | user_id, key_hash, name, expires_at, is_active |

#### 12.2.3 监督与审计

| 实体 | 说明 | 核心字段 |
|------|------|---------|
| **SupervisionEvent** | 监督事件 | session_id, run_id, event_type, operator_id, action_detail |
| **SupervisionRule** | 监督规则 | trigger_type, trigger_config, action, approver_roles, timeout |
| **ApprovalRequest** | 审批请求 | run_id, rule_id, content, status, approver_id |
| **AuditLog** | 审计日志 | user_id, action, resource_type, resource_id, ip_address, details |
| **Notification** | 通知 | user_id, type, title, content, is_read |

#### 12.2.4 配置

| 实体 | 说明 | 核心字段 |
|------|------|---------|
| **ProviderConfig** | 模型厂商配置 | name, provider_type, base_url, api_key_encrypted, auth_type, is_enabled, rate_limit_config, org_id |
| **ModelConfig** | 模型配置 | provider_id, model_name, display_name, context_window, pricing, is_enabled, is_default |
| **ChannelConfig** | IM 渠道配置 | channel_name, channel_type, config, is_enabled, status |
| **MCPConfig** | MCP Server 配置 | name, transport_type, url/command, auth_config, is_enabled |
| **SkillConfig** | Skill 配置 | name, category(public/custom), is_enabled, install_path |

#### 12.2.5 Token 审计（ClickHouse）

| 实体 | 说明 | 核心字段 |
|------|------|---------|
| **TokenUsageLog** | 每次 LLM 调用的 Token 审计记录 | trace_id, span_id, user_id, org_id, team_id, agent_name, model, provider, prompt_tokens, completion_tokens, total_tokens, cost_usd, session_id, run_id, timestamp |
| **TokenUsageSummary** | 预聚合统计物化视图 | dimension_type, dimension_value, period_start, period_end, total_prompt_tokens, total_completion_tokens, total_tokens, total_cost, request_count |

**存储引擎：** ClickHouse MergeTree，按 `(org_id, toYYYYMM(timestamp))` 分区。物化视图使用 AggregatingMergeTree 引擎预聚合。

> TokenUsageLog 完整字段定义详见《CkyClaw 数据模型详细设计 v1.3》第三章；ClickHouse DDL 详见《CkyClaw Framework Design v2.0》第七章 7.3 节。

> ProviderConfig、ModelConfig 完整列级 Schema 详见《CkyClaw 数据模型详细设计 v1.3》第二章。

### 12.3 数据存储策略

| 数据类型 | 存储后端 | 说明 |
|---------|---------|------|
| 业务实体 | PostgreSQL | AgentConfig、Session、Run、User 等 |
| 对话历史 | PostgreSQL / Redis | Session 内消息通过 CkyClaw Framework Session 机制管理 |
| Token 审计 | PostgreSQL（默认）/ ClickHouse（可选） | MVP 用 PostgreSQL；日均 > 50 万条时可切换到 ClickHouse |
| Trace/Span | OTel Collector → Jaeger/Tempo（推荐）/ PostgreSQL（MVP） | 推荐通过 OTel Collector 导出到 Jaeger/Tempo；MVP 可直写 PostgreSQL |
| Metrics | Prometheus（通过 OTel Collector） | OTel Collector 采集指标后通过 Remote Write 导出到 Prometheus |
| 缓存 | Redis | Agent 列表、模型列表等低频变更数据 |
| 文件/产物 | 对象存储 | 用户上传文件、Agent 生成产物 |

> **ClickHouse 可选增强：** 当 Trace/Token 数据规模超过 PostgreSQL 负载能力（日均 > 100 万 Span 或 > 50 万 Token 审计记录），可引入 ClickHouse 作为专用分析存储。

---

## 十三、用户系统与安全管理

### 13.1 用户管理

#### 13.1.1 注册与登录

| 流程 | 说明 |
|------|------|
| 注册 | 管理员邀请注册（生成邀请链接/邀请码）；暂不开放自助注册 |
| 登录 | 用户名/邮箱 + 密码；支持 SSO 对接企业身份源（LDAP / OIDC） |
| 多因素认证 | 可选启用 TOTP |
| 密码策略 | 最小长度 8 位；包含大小写 + 数字；90 天过期提醒 |
| 会话管理 | JWT Access Token（15 分钟）+ Refresh Token（7 天）；支持强制下线 |

#### 13.1.2 组织与团队

| 层级 | 说明 |
|------|------|
| **Organization** | 顶层隔离单元，独立的数据和配额 |
| **Team** | 组织下的团队，共享 Agent、执行记录和预算 |
| **User** | 归属一个 Organization，可属于多个 Team |

组织级资源隔离：不同 Organization 的 Agent、Session、执行记录数据完全隔离。

#### 13.1.3 通知管理

| 通知类型 | 触发场景 | 渠道 |
|---------|---------|------|
| 审批通知 | Agent 输出待审批 / Guardrail Tripwire | 站内 + 邮件 |
| 告警通知 | APM 告警触发 | 站内 + Webhook |
| 执行通知 | Agent 执行完成/失败 | 站内 |
| 系统通知 | 密码过期、版本更新 | 邮件 |

#### 13.1.4 使用配额

| 配额维度 | 说明 |
|---------|------|
| Organization 级 | 总 Token 预算、最大并发 Run 数、最大 Agent 数 |
| Team 级 | Team 内 Token 预算上限 |
| User 级 | 个人每日 Token 上限、每日请求次数上限 |

### 13.2 认证机制

| 方式 | 说明 | 适用场景 |
|------|------|---------|
| JWT Bearer Token | 用户认证 | 前端交互 |
| API Key | 服务端间调用 | 后端集成、脚本调用 |
| OAuth 2.0 | 第三方应用集成 | 外部系统 |
| SSO | LDAP / OIDC 对接 | 企业环境 |

### 13.3 角色权限 (RBAC)

#### 13.3.1 预置角色

| 角色 | 说明 | 权限范围 |
|------|------|---------|
| Admin | 系统管理员 | 所有权限（跨组织） |
| OrgAdmin | 组织管理员 | 组织内所有权限 |
| Developer | 开发者 | Agent / Session / 执行记录管理 |
| Operator | 运维人员 | APM / MCP / 监督面板 / 审批 |
| Viewer | 查看者 | 只读权限 |

#### 13.3.2 完整权限矩阵

| 资源 \ 角色 | Admin | OrgAdmin | Developer | Operator | Viewer |
|-------------|:

-----

:|:

--------

:|:

---------

:|:

--------

:|:

------

:|
| **Agent 管理** | | | | | |
| 查看 Agent 列表与详情 | ✅ | ✅ | ✅ | ✅ | ✅ |
| 创建 / 编辑 Agent | ✅ | ✅ | ✅ | ❌ | ❌ |
| 删除 Agent | ✅ | ✅ | ❌ | ❌ | ❌ |
| 版本回滚 | ✅ | ✅ | ✅ | ❌ | ❌ |
| **对话与执行** | | | | | |
| 发起对话 / Run | ✅ | ✅ | ✅ | ✅ | ❌ |
| 查看 Session / 执行详情 | ✅ | ✅ | ✅ | ✅ | ✅ |
| 取消 / 重试 Run | ✅ | ✅ | ✅ | ✅ | ❌ |
| 删除 Session | ✅ | ✅ | ✅ | ❌ | ❌ |
| **工具与 Skill** | | | | | |
| 查看工具 / Skill 列表 | ✅ | ✅ | ✅ | ✅ | ✅ |
| 安装 / 卸载 Skill | ✅ | ✅ | ✅ | ❌ | ❌ |
| MCP Server 管理 | ✅ | ✅ | ❌ | ✅ | ❌ |
| **人工监督** | | | | | |
| 查看活跃会话 | ✅ | ✅ | ✅ | ✅ | ✅ |
| 暂停 / 恢复会话 | ✅ | ✅ | ✅ | ✅ | ❌ |
| 注入消息 | ✅ | ✅ | ✅ | ✅ | ❌ |
| 接管 / 释放会话 | ✅ | ✅ | ❌ | ✅ | ❌ |
| 审批操作 | ✅ | ✅ | ❌ | ✅ | ❌ |
| 监督规则配置 | ✅ | ✅ | ❌ | ❌ | ❌ |
| **APM 与审计** | | | | | |
| 查看仪表盘 / Trace | ✅ | ✅ | ✅ | ✅ | ✅ |
| 管理告警规则 | ✅ | ✅ | ❌ | ✅ | ❌ |
| Token 审计查询 | ✅ | ✅ | ✅ | ✅ | ✅ |
| 导出审计日志 | ✅ | ✅ | ❌ | ✅ | ❌ |
| **模型厂商** | | | | | |
| 查看厂商 / 模型列表 | ✅ | ✅ | ✅ | ✅ | ✅ |
| 添加 / 编辑 / 删除厂商 | ✅ | ✅ | ❌ | ❌ | ❌ |
| 连通性测试 | ✅ | ✅ | ❌ | ✅ | ❌ |
| 设置默认模型 | ✅ | ✅ | ❌ | ❌ | ❌ |
| **用户与组织** | | | | | |
| 查看用户列表 | ✅ | ✅ | ❌ | ❌ | ❌ |
| 创建 / 编辑 / 禁用用户 | ✅ | ✅ | ❌ | ❌ | ❌ |
| 管理组织 | ✅ | ❌ | ❌ | ❌ | ❌ |
| 管理团队 | ✅ | ✅ | ❌ | ❌ | ❌ |
| 角色管理 | ✅ | ✅ | ❌ | ❌ | ❌ |
| 管理渠道配置 | ✅ | ✅ | ❌ | ❌ | ❌ |
| **系统** | | | | | |
| 查看审计日志 | ✅ | ✅ | ❌ | ✅ | ❌ |
| 系统配置（全局设置） | ✅ | ❌ | ❌ | ❌ | ❌ |

#### 13.3.3 权限模型

| 维度 | 说明 |
|------|------|
| 作用域 | Admin 跨组织；OrgAdmin/Developer/Operator/Viewer 限组织内 |
| 自定义角色 | OrgAdmin 可在组织内创建自定义角色，从预置权限标识中组合 |
| 权限标识格式 | `{resource}:{action}`（如 `agent:write`、`supervision:approve`） |
| 权限检查顺序 | Admin 直接放行 → 检查用户角色绑定的权限集合 → org_id 作用域过滤 |
| 权限继承 | 不支持角色层级继承；每个角色独立定义权限集合 |

### 13.4 通信安全

| 层级 | 措施 |
|------|------|
| 外部传输 | TLS 1.3 |
| 内部通信 | 生产环境可启用 mTLS |
| 敏感配置 | AES-256-GCM 加密存储 |
| 用户密码 | bcrypt 哈希 |

### 13.5 安全防护

| 威胁 | 防护措施 |
|------|---------|
| Prompt 注入 | Input Guardrails + 输入过滤 |
| API 滥用 | 令牌桶限流 + IP 黑名单 |
| 代码执行逃逸 | Sandbox 隔离 |
| 数据泄露 | Output Guardrails + 审计日志 + 最小权限 |
| SSRF | 工具调用白名单 + URL 校验 |

### 13.6 审计日志

#### 13.6.1 审计范围所有涉及数据变更和安全相关的操作自动记录审计日志。

| 审计类别 | 包含操作 | 严重级别 |
|---------|---------|---------|
| **认证事件** | 登录成功/失败、登出、Token 刷新、强制下线 | INFO / WARNING |
| **用户管理** | 创建/禁用用户、角色变更、密码重置 | INFO |
| **Agent 管理** | 创建/编辑/删除 Agent、版本回滚 | INFO |
| **执行事件** | Run 发起/取消/失败、Guardrail Tripwire、Budget 拦截 | INFO / WARNING |
| **监督操作** | 暂停/恢复/接管会话、审批操作、消息注入 | WARNING |
| **配置变更** | 厂商配置、模型配置、渠道配置、监督规则、告警规则 | INFO |
| **数据导出** | Token 审计导出、审计日志导出 | WARNING |
| **系统事件** | 服务启停、数据库迁移、渠道连接断开 | INFO / ERROR |

#### 13.6.2 审计日志字段

| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID | 主键 |
| timestamp | TIMESTAMP | 操作时间（UTC） |
| user_id | UUID | 操作人（系统操作为 null） |
| username | VARCHAR | 操作人用户名（冗余，便于查询） |
| org_id | UUID | 所属组织 |
| action | VARCHAR | 操作标识（如 `agent.create`、`supervision.approve`） |
| resource_type | VARCHAR | 资源类型（`agent` / `session` / `user` / `provider` …） |
| resource_id | VARCHAR | 资源标识 |
| severity | ENUM | `INFO` / `WARNING` / `ERROR` |
| ip_address | VARCHAR | 客户端 IP |
| user_agent | VARCHAR | 客户端标识 |
| details | JSONB | 操作详情（变更前后对比、请求参数摘要） |
| result | ENUM | `success` / `failure` |
| error_message | TEXT | 失败时的错误信息 |

#### 13.6.3 审计日志生命周期

| 阶段 | 策略 | 说明 |
|------|------|------|
| **写入** | 同步写入 PostgreSQL | 审计日志不允许丢失，与业务事务同步提交 |
| **在线保留** | 90 天 | 在线查询窗口（最近 3 个月） |
| **归档** | 90 天后迁移到冷存储 | 压缩后写入对象存储（S3/MinIO），保留 JSON Lines 格式 |
| **总保留** | 3 年 | 满足合规审计要求 |
| **清理** | 3 年后自动删除 | 定时任务按 `timestamp` 分区删除 |

#### 13.6.4 查询与导出

| 功能 | 说明 |
|------|------|
| 多条件筛选 | 按时间 / 用户 / 操作类型 / 资源 / 严重级别 / 结果组合查询 |
| 全文搜索 | 对 `details` JSONB 字段建立 GIN 索引，支持关键词搜索 |
| 导出 | CSV / Excel 格式导出，导出操作本身记录审计日志 |
| 实时流 | Admin 可通过 WebSocket 实时接收 WARNING / ERROR 级别审计事件 |

#### 13.6.5 合规支持

| 要求 | 实现 |
|------|------|
| 不可篡改 | 审计日志表仅允许 INSERT，禁止 UPDATE / DELETE（数据库级权限控制） |
| 用户数据删除（GDPR） | 用户删除时审计日志中的 user_id 替换为哈希值，保留操作记录但脱敏 |
| 数据隔离 | 按 org_id 隔离查询，OrgAdmin 只能查看本组织审计日志 |
| 审计审计 | 对审计日志本身的查询和导出操作也记录审计日志（防止内部人员越权） |---

## 十四、部署与运维

### 14.1 部署架构

```
┌─────────────────────────────────────────────────────────────────┐│                        生产环境拓扑                               │
│
│
│   [用户] ──► [反向代理] ──┬──► CkyClaw Frontend (React SPA)  │
│
└──► CkyClaw Backend (FastAPI)        │
│
├── CkyClaw Framework          │
│
├── Agent Runner Pool           │
│
└── Trace Processor             │
│
│                           │
│
┌──────────┼──────────┐
│
│
▼
▼
▼
│
│                      [Sandbox] [MCP Servers] [LLM APIs]         │
│
│
│   ────────── 必选基础设施 ──────────   ──── 可观测性基础设施 ────  │
│   [PostgreSQL]   [Redis]   [对象存储]        [OTel Collector]    │
│    业务数据        缓存     文件/产物          │
│
│    +Token审计
├→ Jaeger/Tempo      │
│
├→ Prometheus        │
│
└→ Grafana           │
│
│
│   ────────── 可选组件 ────────────────                            │
│   [ClickHouse]  大规模 Trace/Token 分析（日均 > 100万 Span）      │└─────────────────────────────────────────────────────────────────┘

```

### 14.2 部署模式

| 模式 | 说明 | 适用场景 |
|------|------|---------|
| Docker Compose | 单机容器化部署 | 开发/测试 |
| Kubernetes | 分布式部署，支持弹性扩缩 | 生产环境 |

### 14.3 技术栈

| 层级 | 技术选型 |
|------|---------|
| 前端 | React 18+（Vite 5 + Ant Design 5 + ProComponents + Zustand + TanStack Query + ReactFlow + ECharts） |
| 后端 | FastAPI (Python 3.12+) |
| Agent 框架 | CkyClaw Framework（自研，Python 库） |
| 模型适配 | LiteLLM（100+ 模型适配） |
| 数据库 | PostgreSQL 16 |
| 缓存/消息 | Redis 7 |
| 可观测性 | OTel Collector + Jaeger/Tempo + Prometheus + Grafana |
| 容器化 | Docker + Kubernetes |
| 反向代理 | Nginx / Traefik |

### 14.4 高可用策略

| 组件 | 策略 |
|------|------|
| CkyClaw Frontend | CDN + 多节点 Nginx |
| CkyClaw Backend | 多实例 + 负载均衡 |
| Agent Runner | 水平扩展（无状态，Session 持久化到 PostgreSQL/Redis） |
| PostgreSQL | 主从复制 + 自动故障切换 |
| Redis | Sentinel / Cluster 模式 |

### 14.5 环境差异

| 维度 | 开发环境 | 测试/预发环境 | 生产环境 |
|------|---------|-------------|----------|
| 部署方式 | Docker Compose | Docker Compose / K8s | Kubernetes 集群 |
| Sandbox | Local | Docker | Docker / Kubernetes |
| 数据库 | SQLite / 本地 PG | PostgreSQL | PostgreSQL（主从） |
| LLM | 低成本模型 / Mock | 生产模型 | 生产模型 + 限流 |
| 认证 | 可跳过 | JWT | JWT + API Key |

### 14.6 数据备份与灾难恢复

#### 14.6.1 备份策略

| 组件 | 备份方式 | 频率 | 保留策略 |
|------|---------|------|---------|
| **PostgreSQL** | pg_basebackup 全量 + WAL 归档增量 | 全量每日 02:00；WAL 持续同步 | 全量保留 30 天；WAL 保留 7 天 |
| **Redis** | RDB 快照 + AOF | RDB 每 6 小时；AOF 持续 | RDB 保留 7 天 |
| **对象存储** | 跨区域复制（生产环境） | 实时 | 与源存储一致 |
| **Agent 配置** | AgentVersion 快照（已内置于版本管理） | 每次变更 | 最近 50 个版本 + 标签版本 |

#### 14.6.2 恢复目标

| 指标 | 目标 | 说明 |
|------|------|------|
| **RTO**（恢复时间目标） | < 4 小时 | 从灾难发生到服务恢复的最大允许时间 |
| **RPO**（恢复点目标） | < 1 小时 | 最大可接受的数据丢失时间窗口 |

#### 14.6.3 恢复流程

| 场景 | 恢复步骤 |
|------|---------|
| 单节点故障 | Kubernetes 自动重调度；PostgreSQL 主从自动切换 |
| 数据损坏 | 从最近全量备份 + WAL 恢复到指定时间点（PITR） |
| 整体灾难 | 从跨区域备份恢复 PostgreSQL → 恢复 Redis → 重建 OTel 组件 → 启动应用 |

### 14.7 配置热更新运维

| 要求 | 说明 |
|------|------|
| **变更传播** | 配置写入 PostgreSQL 后，通过 Redis Pub/Sub 通知所有应用实例刷新本地缓存 |
| **传播延迟** | 配置变更从提交到全节点生效 ≤ 5 秒 |
| **回滚能力** | 管理后台支持按审计日志一键回滚至任意历史配置 |
| **灰度变更** | Post-MVP 支持配置变更仅对指定租户/百分比流量生效 |

> 配置热更新的产品功能定义详见 4.13.1。

---

## 十五、非功能性需求

### 15.1 性能指标

| 指标 | 目标 | 说明 |
|------|------|------|
| API 响应时间 | p95 < 200ms | CkyClaw 自身 API（不含 LLM 调用） |
| Agent 执行响应 | p95 < 10s | 含 LLM 调用的端到端时间 |
| 首 Token 延迟 | p95 < 2s | SSE 流式响应首个 Token |
| 并发用户数 | ≥ 100 | 同时在线用户 |
| 并发 Run 数 | ≥ 50 | 同时执行的 Agent Run |

### 15.2 可用性目标

| 级别 | 目标 | 月最大停机时间 |
|------|------|--------------|
| 核心服务 | 99.9% | 43 分钟 |
| 管理功能 | 99.5% | 3.6 小时 |

### 15.3 可扩展性

| 维度 | 扩展方式 |
|------|---------|
| 自定义 Agent | 声明式 YAML 配置 + Instructions 编辑 |
| 自定义 Tool | Function Tool 注册 / MCP Server 接入 |
| 自定义 Skill | .skill 归档包安装 |
| Agent 编排 | Handoff + Agent-as-Tool 自由组合 |
| LLM 提供商 | 通过 Model Provider 适配 |

### 15.4 数据一致性

| 场景 | 策略 |
|------|------|
| 执行记录状态 | 最终一致性 |
| 审计日志 | 同步写入，保证不丢失 |
| Trace 数据 | 异步写入（OTel Collector / PostgreSQL），允许短暂延迟 |

### 15.5 性能优化策略

| 策略 | 说明 |
|------|------|
| **API 响应缓存** | 对 Agent 列表、模型列表等低频变更数据使用 Redis 缓存 |
| **Session 管理** | Session 历史按需加载，支持历史裁剪和压缩 |
| **Trace 异步写入** | Trace Processor 异步批量写入存储后端（PostgreSQL / OTel Collector），不阻塞 Runner |
| **前端渲染优化** | 执行图虚拟化渲染；SSE 消息 16ms 批量合并更新 |
| **静态资源** | CDN 分发，Brotli 压缩，长期缓存 |---


---

*文档版本：v2.0.8*
*最后更新：2026-04-02*
*作者：CkyClaw Team*
