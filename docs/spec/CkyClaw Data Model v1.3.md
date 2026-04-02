# CkyClaw 数据模型详细设计 v1.3

## 文档信息

| 字段 | 内容 |
|------|------|
| 版本 | v1.3.0 |
| 日期 | 2026-04-02 |
| 状态 | 进行中 |
| 维护人 | CkyClaw Team |
| 依赖 | CkyClaw PRD v2.0、CkyClaw Framework Design v2.0 |

> 本文档从 CkyClaw PRD v2.0 的第十二章抽取，包含所有数据实体的列级 Schema 定义。
> PRD 保留实体关系概览与核心字段摘要，本文档提供完整的字段类型、约束和索引设计。

---

## 一、Agent 与执行

### 1.1 AgentConfig

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | UUID | PK | 主键 |
| name | VARCHAR(64) | UNIQUE per org | Agent 标识（小写字母、数字、连字符） |
| description | TEXT | NOT NULL | 功能描述 |
| instructions | TEXT | NOT NULL | SOUL.md 内容 |
| model | VARCHAR(128) | NULLABLE | LLM 模型标识（空则使用默认） |
| model_settings | JSONB | NULLABLE | temperature、max_tokens 等 |
| tool_groups | VARCHAR[] | DEFAULT '{}' | 工具组白名单 |
| handoffs | VARCHAR[] | DEFAULT '{}' | 可 Handoff 的目标 Agent 名称列表 |
| guardrails | JSONB | DEFAULT '{}' | 护栏配置（input/output/tool 列表） |
| approval_mode | VARCHAR(16) | DEFAULT 'suggest' | suggest / auto-edit / full-auto |
| mcp_servers | VARCHAR[] | DEFAULT '{}' | 关联的 MCP Server 名称 |
| skills | VARCHAR[] | DEFAULT '{}' | 已启用 Skill 名称 |
| org_id | UUID | FK → Organization | 所属组织 |
| is_active | BOOLEAN | DEFAULT true | 是否启用 |
| created_by | UUID | FK → User | 创建者 |
| created_at | TIMESTAMPTZ | DEFAULT now() | 创建时间 |
| updated_at | TIMESTAMPTZ | DEFAULT now() | 更新时间 |

### 1.2 Run

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | UUID | PK | 主键 |
| session_id | UUID | FK → Session | 所属会话 |
| agent_name | VARCHAR(64) | NOT NULL | 入口 Agent |
| last_agent_name | VARCHAR(64) | NULLABLE | 最终处理的 Agent（Handoff 后可能不同） |
| status | VARCHAR(16) | NOT NULL | pending / running / completed / failed / cancelled |
| input | TEXT | NOT NULL | 用户输入 |
| output | TEXT | NULLABLE | Agent 最终输出 |
| token_usage | JSONB | DEFAULT '{}' | {prompt_tokens, completion_tokens, total_tokens} |
| duration_ms | INTEGER | NULLABLE | 执行耗时（毫秒） |
| turn_count | INTEGER | DEFAULT 0 | 实际执行轮次 |
| error_message | TEXT | NULLABLE | 失败时的错误信息 |
| created_at | TIMESTAMPTZ | DEFAULT now() | 创建时间 |
| completed_at | TIMESTAMPTZ | NULLABLE | 完成时间 |

### 1.3 Span

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | VARCHAR(64) | PK | Span ID |
| trace_id | VARCHAR(64) | FK → Trace, INDEX | 所属 Trace |
| parent_span_id | VARCHAR(64) | NULLABLE, INDEX | 父 Span（用于构建层级） |
| type | VARCHAR(16) | NOT NULL | agent / llm / tool / handoff / guardrail |
| name | VARCHAR(128) | NOT NULL | 节点名称（Agent 名 / 工具名 / 模型名） |
| status | VARCHAR(16) | NOT NULL | pending / running / completed / failed |
| start_time | TIMESTAMPTZ | NOT NULL | 开始时间 |
| end_time | TIMESTAMPTZ | NULLABLE | 结束时间 |
| duration_ms | INTEGER | NULLABLE | 耗时（毫秒） |
| input | JSONB | NULLABLE | 输入数据（可配置脱敏） |
| output | JSONB | NULLABLE | 输出数据（可配置脱敏） |
| token_usage | JSONB | NULLABLE | LLM Span 的 Token 消耗 |
| model | VARCHAR(128) | NULLABLE | LLM Span 使用的模型 |
| metadata | JSONB | DEFAULT '{}' | 扩展元数据 |

---

## 二、模型提供商配置

### 2.1 ProviderConfig

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | UUID | PK | 主键 |
| name | VARCHAR(64) | NOT NULL | 厂商显示名称（如 "OpenAI"、"智谱 AI"） |
| provider_type | VARCHAR(32) | NOT NULL | openai / anthropic / azure / deepseek / qwen / doubao / zhipu / moonshot / custom |
| base_url | VARCHAR(512) | NOT NULL | API 端点 URL（如 `https://api.openai.com/v1`） |
| api_key_encrypted | TEXT | NOT NULL | AES-256-GCM 加密存储的 API Key |
| auth_type | VARCHAR(16) | DEFAULT 'api_key' | api_key / azure_ad / custom_header |
| auth_config | JSONB | DEFAULT '{}' | 额外认证参数（Azure 需要 deployment_name 等） |
| rate_limit_rpm | INTEGER | NULLABLE | 厂商级每分钟请求数上限 |
| rate_limit_tpm | INTEGER | NULLABLE | 厂商级每分钟 Token 数上限 |
| is_enabled | BOOLEAN | DEFAULT true | 是否启用 |
| org_id | UUID | FK → Organization | 所属组织 |
| last_health_check | TIMESTAMPTZ | NULLABLE | 最近一次连通性测试时间 |
| health_status | VARCHAR(16) | DEFAULT 'unknown' | ok / error / unknown |
| created_at | TIMESTAMPTZ | DEFAULT now() | 创建时间 |
| updated_at | TIMESTAMPTZ | DEFAULT now() | 更新时间 |

### 2.2 ModelConfig

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | UUID | PK | 主键 |
| provider_id | UUID | FK → ProviderConfig | 所属厂商 |
| model_name | VARCHAR(128) | NOT NULL | 模型标识（传给 LiteLLM 的值，如 `gpt-4o`） |
| display_name | VARCHAR(128) | NOT NULL | 显示名称（如 "GPT-4o"） |
| context_window | INTEGER | NULLABLE | 上下文窗口大小（Token 数） |
| max_output_tokens | INTEGER | NULLABLE | 最大输出 Token 数 |
| pricing_input | DECIMAL(10,6) | NULLABLE | 输入 Token 单价（美元/千 Token） |
| pricing_output | DECIMAL(10,6) | NULLABLE | 输出 Token 单价（美元/千 Token） |
| supports_streaming | BOOLEAN | DEFAULT true | 是否支持流式输出 |
| supports_tools | BOOLEAN | DEFAULT true | 是否支持 Function Calling |
| supports_vision | BOOLEAN | DEFAULT false | 是否支持图像输入 |
| is_enabled | BOOLEAN | DEFAULT true | 是否启用 |
| is_default | BOOLEAN | DEFAULT false | 是否为全局默认模型（整个 org 仅一个） |
| created_at | TIMESTAMPTZ | DEFAULT now() | 创建时间 |

---

## 三、Token 审计

> **存储后端：** MVP 默认使用 PostgreSQL（详见 Framework Design 7.3 PostgresTraceProcessor）；大规模场景可选 ClickHouse（详见 7.4 ClickHouseTraceProcessor）。以下字段定义适用于两种后端。

### 3.1 TokenUsageLog

| 字段 | 类型 | 说明 |
|------|------|------|
| trace_id | UUID / String | 所属 Trace（关联完整执行链路） |
| span_id | UUID / String | LLM Span ID |
| user_id | UUID / String | 发起请求的用户 ID |
| org_id | UUID / String | 组织 ID |
| team_id | UUID / String | 团队 ID |
| agent_name | VARCHAR / String | 执行的 Agent 名称 |
| model | VARCHAR / String | 模型标识（如 gpt-4o） |
| provider | VARCHAR / String | 厂商标识（如 openai） |
| prompt_tokens | INTEGER / UInt32 | 输入 Token 数 |
| completion_tokens | INTEGER / UInt32 | 输出 Token 数 |
| total_tokens | INTEGER / UInt32 | 总 Token 数 |
| cost_usd | NUMERIC(12,6) / Decimal64(6) | 费用（美元，基于 ModelConfig 单价计算） |
| session_id | UUID / String | 会话 ID |
| run_id | UUID / String | Run ID |
| timestamp | TIMESTAMPTZ / DateTime | 调用时间 |

**PostgreSQL（默认）：** 按 `timestamp` 范围分区（pg_partman），索引 `(org_id, timestamp DESC)` 和 `(user_id, timestamp DESC)`。聚合使用 `token_usage_summary` 表（pg_cron 定时刷新）。

**ClickHouse（可选）：** MergeTree 引擎，按 `(org_id, toYYYYMM(timestamp))` 分区，按 `(org_id, timestamp, agent_name)` 排序。物化视图使用 AggregatingMergeTree 引擎预聚合。

PostgreSQL DDL 详见 CkyClaw Framework Design v2.0 第七章 7.3 节；ClickHouse DDL 详见 7.4 节。

---

## 四、Agent 版本管理

### 4.1 AgentVersion

| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID | 主键 |
| agent_name | VARCHAR(64) | Agent 名称（外键 → agent_configs.name） |
| version_number | INTEGER | 版本号（同一 Agent 内自增） |
| status | VARCHAR(20) | draft / published / archived |
| snapshot | JSONB | 完整配置快照（instructions、model、tools、handoffs、guardrails、approval_mode、metadata 等） |
| change_description | TEXT | 变更说明（可选） |
| tags | VARCHAR[] | 版本标签数组（如 stable、production） |
| created_by | UUID | 创建者 |
| created_at | TIMESTAMPTZ | 创建时间 |

**索引：** `(agent_name, version_number)` UNIQUE；`(agent_name, status)` 用于快速查找 published 版本。

---

## 五、Agent Team

### 5.1 TeamConfig（存储）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID | 主键 |
| name | VARCHAR(64) | Team 唯一标识符 |
| display_name | VARCHAR(200) | 显示名称 |
| description | TEXT | 描述 |
| protocol | VARCHAR(20) | sequential / parallel / hierarchical / supervisor / debate / negotiated / round_robin / broadcast |
| members | JSONB | 成员列表（`[{agent_ref, role, is_judge}]`） |
| termination | JSONB | 终止条件（`{max_rounds, timeout_seconds, consensus_threshold}`） |
| result_strategy | VARCHAR(20) | last / concat / vote / judge / custom |
| context_sharing | VARCHAR(20) | sequential / shared / isolated |
| is_builtin | BOOLEAN | 是否为内置 Team 模板 |
| org_id | UUID | 所属组织 |
| created_by | UUID | 创建者 |
| created_at | TIMESTAMPTZ | 创建时间 |
| updated_at | TIMESTAMPTZ | 更新时间 |

**索引：** `(org_id, name)` UNIQUE。

---

## 六、定时与批量任务

### 6.1 ScheduledRun

| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID | 主键（schedule_id） |
| agent_name | VARCHAR(64) | 执行的 Agent |
| cron_expression | VARCHAR(100) | Cron 表达式 |
| input_template | TEXT | 输入模板（支持变量） |
| run_config_override | JSONB | 可选的 RunConfig 覆盖 |
| notification | JSONB | 完成通知设置 |
| max_retries | INTEGER | 最大重试次数（默认 0） |
| is_enabled | BOOLEAN | 启停开关 |
| last_run_at | TIMESTAMPTZ | 最近执行时间 |
| next_run_at | TIMESTAMPTZ | 下次计划执行时间 |
| org_id | UUID | 所属组织 |
| created_by | UUID | 创建者 |
| created_at | TIMESTAMPTZ | 创建时间 |

**索引：** `(is_enabled, next_run_at)` 用于调度器扫描。

### 6.2 BatchRun

| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID | 主键（batch_id） |
| agent_name | VARCHAR(64) | 执行的 Agent |
| total_items | INTEGER | 总输入项数 |
| concurrency | INTEGER | 最大并行度 |
| status | VARCHAR(20) | pending / running / completed / cancelled |
| run_config_override | JSONB | 可选的 RunConfig 覆盖 |
| progress | JSONB | 进度快照（`{completed, failed, in_progress, pending}`） |
| org_id | UUID | 所属组织 |
| created_by | UUID | 创建者 |
| created_at | TIMESTAMPTZ | 创建时间 |
| completed_at | TIMESTAMPTZ | 完成时间 |

**索引：** `(org_id, status)`；`(org_id, created_at DESC)`。

### 6.3 BatchRunItem

| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID | 主键 |
| batch_id | UUID | 关联 BatchRun |
| item_index | INTEGER | 输入项序号 |
| input | TEXT | 单项输入内容 |
| run_id | UUID | 关联的 Run ID（执行后填充） |
| status | VARCHAR(20) | pending / running / completed / failed / cancelled |
| error_message | TEXT | 失败原因（可选） |
| created_at | TIMESTAMPTZ | 创建时间 |

---

## 七、Agent 评估与反馈

### 7.1 RunFeedback

| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID | 主键（feedback_id） |
| run_id | UUID | 关联的 Run ID |
| user_id | UUID | 评价者 |
| rating | VARCHAR(20) | thumbs_up / thumbs_down |
| comment | TEXT | 文字反馈（最长 1000 字） |
| created_at | TIMESTAMPTZ | 创建时间 |

**索引：** `(run_id)` UNIQUE（每个 Run 只能有一条反馈）；`(user_id, created_at DESC)`。

---

## 八、配置变更审计

### 8.1 ConfigChangeLog

| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID | 主键（change_id） |
| config_key | VARCHAR(255) | 配置项键名（如 `agent.triage.instructions`） |
| old_value | JSONB | 变更前的值 |
| new_value | JSONB | 变更后的值 |
| changed_by | UUID | 操作人 user_id |
| changed_at | TIMESTAMPTZ | 变更时间 |
| change_source | VARCHAR(20) | 变更来源：`web_ui` / `api` / `system` / `rollback` |
| rollback_ref | UUID | 如果是回滚操作，引用原始变更 ID（NULL 表示非回滚） |
| org_id | UUID | 所属组织 |

**索引：** `(config_key, changed_at DESC)`（按配置项查看历史）；`(changed_by, changed_at DESC)`（按操作人审计）；`(org_id, changed_at DESC)`。

---

## 九、Agent 国际化

### 9.1 AgentLocale

| 字段 | 类型 | 说明 |
|------|------|------|
| id | UUID | 主键 |
| agent_name | VARCHAR(100) | 关联的 Agent 名称 |
| locale | VARCHAR(10) | 语言标识（如 `zh-CN`、`en-US`） |
| display_name | VARCHAR(200) | 该语言的 Agent 展示名称 |
| description | TEXT | 该语言的 Agent 描述 |
| instructions | TEXT | 该语言版本的 Instructions（可为 NULL，NULL 表示使用默认语言） |
| is_default | BOOLEAN | 是否为该 Agent 的默认语言 |
| org_id | UUID | 所属组织 |
| created_at | TIMESTAMPTZ | 创建时间 |
| updated_at | TIMESTAMPTZ | 更新时间 |

**索引：** `(agent_name, locale)` UNIQUE（每个 Agent 每种语言唯一）；`(agent_name, is_default)` WHERE `is_default = true`（快速查找默认语言）。

**说明：** MVP 阶段仅需 `zh-CN` 和 `en-US` 两条记录。Instructions 字段为 NULL 时，Runner 使用 Agent 主表中的 instructions 字段。Post-MVP 支持更多语言和自动 locale 路由。

---

*文档版本：v1.3.0*
*最后更新：2026-04-02*
*作者：CkyClaw Team*
