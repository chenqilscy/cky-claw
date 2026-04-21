# Kasaya Rust 重写可行性分析

> 版本：v1.0
> 日期：2026-04-09
> 范围：kasaya-framework + backend 全部用 Rust 重写

---

## 一、重写范围量化

### 1.1 Python → Rust 工作量映射

| 模块 | Python 规模 | Rust 预估规模 | 重写工时 |
|------|------------|:------------:|:--------:|
| **Framework** | 376 文件 / 83,694 行 | ~45,000 行 | 4-5 月 |
| **Backend** | 161 端点 / 34 表 / 48 Service | ~25,000 行 | 2-3 月 |
| **合计** | ~105,820 行 | ~70,000 行 | **6-8 月** |

> Rust 代码通常比 Python 短 30-40%（去掉了测试样板、类型注解样板），但编写速度慢 3-5x。

### 1.2 后端 API 全景

| 指标 | 数量 |
|------|:----:|
| API 端点 | 161 |
| 数据库表 | 34 |
| Service 模块 | 48 |
| WebSocket 端点 | 2 |
| 后台任务 | 3（Scheduler / Redis 订阅 / 审计刷盘） |
| 中间件 | 3（RequestID / AuditLog / CORS） |
| IM 渠道适配器 | 7（企微/钉钉/飞书/微信公众号/Slack/自定义 Webhook/基类） |

最复杂模块（按端点数）：

| 模块 | 端点数 | 复杂度 |
|------|:------:|:------:|
| evolution | 10 | 高（Signal + Proposal + Analyze + Apply） |
| agents | 9 | 高（CRUD + Run + Export/Import + RealtimeStatus） |
| memories | 8 | 中 |
| providers | 8 | 中（含 Key 轮换 + 连通性测试） |
| scheduled_tasks | 8 | 中（含 Cron 调度引擎） |

---

## 二、技术栈映射

### 2.1 依赖对照表

| Python 依赖 | 用途 | Rust 替代 | 成熟度 |
|------------|------|----------|:------:|
| FastAPI | Web 框架 | **axum** | 成熟 |
| Uvicorn | ASGI 服务器 | tokio（内建） | — |
| SQLAlchemy + asyncpg | ORM + PG 驱动 | **sqlx**（编译期 SQL 检查） | 成熟 |
| Alembic | 数据库迁移 | **sqlx::migrate** 或 **refinery** | 成熟 |
| Pydantic | 数据验证/序列化 | **serde** + **schemars** + **validator** | 成熟 |
| pydantic-settings | 环境变量配置 | **dotenvy** + 手动 struct | 成熟 |
| **litellm** | **多模型统一适配（100+ 厂商）** | **无直接替代** | **缺失** |
| **mcp** | **MCP 协议客户端** | **rmcp**（早期） | **不成熟** |
| redis | Redis 客户端 | **redis** 或 **fred** | 成熟 |
| python-jose | JWT | **jsonwebtoken** | 成熟 |
| bcrypt | 密码哈希 | **bcrypt** | 成熟 |
| httpx | HTTP 客户端 | **reqwest** | 成熟 |
| pyyaml | YAML 解析 | **serde_yaml** | 成熟 |
| croniter | Cron 表达式 | **cron** | 成熟 |
| python-multipart | 文件上传 | axum 内建 | — |
| pytest | 测试 | cargo test + rstest | 成熟 |

### 2.2 核心风险项

#### 风险 1：litellm 无替代（严重度：致命）

LiteLLM 提供：
- 100+ LLM 厂商统一 API（OpenAI / Anthropic / Google / Azure / AWS Bedrock / 通义 / 文心 / 讯飞 / 混元 / DeepSeek ...）
- 自动重试、降级、限流
- 统一 Streaming 接口
- Token 计数 / 成本追踪

Rust 生态现状：
- `async-openai` — 仅覆盖 OpenAI 兼容 API
- 无统一多厂商适配层

**应对方案**：

| 方案 | 优点 | 缺点 |
|------|------|------|
| **A. 基于 OpenAI 兼容协议统一** | 国产大模型大多支持 OpenAI 兼容 API，`async-openai` 一个 crate 覆盖 80% 场景 | Anthropic Messages API、Google Gemini 不兼容 |
| **B. 自建 Provider 抽象层** | 完全自主，支持任意 API 格式 | 工作量大（每个厂商一个 adapter，约 2-3 月） |
| **C. LiteLLM sidecar** | 零重写成本，Python 微服务独立部署 | 引入额外进程 + 网络延迟，违背 Rust 重写初衷 |
| **D. A+B 混合** | 主流用 OpenAI 兼容，少数用自建 adapter | 平衡方案 |

**推荐：方案 D**。用 `async-openai` 作为基础，为 Anthropic / Google 等非兼容厂商自建 adapter。国产模型（通义/文心/讯飞/DeepSeek/混元）均已支持 OpenAI 兼容 API，零额外工作。

#### 风险 2：MCP SDK 不成熟（严重度：中等）

Python MCP SDK 提供完整的 stdio/SSE/HTTP 传输 + 工具发现/调用。

Rust `rmcp` crate：
- 支持 stdio/SSE 传输
- 支持工具发现和调用
- 社区活跃度低，可能缺少边界情况处理

**应对**：Kasaya 实际使用的 MCP 功能面很窄（`list_tools` + `call_tool` + 连接管理），`rmcp` 可覆盖。如遇问题可 fork 维护。

#### 风险 3：运行时类型内省不存在（严重度：中等）

Python `@function_tool` 装饰器用 `inspect.signature()` + `get_type_hints()` 在运行时自动生成 JSON Schema。

Rust 无运行时类型内省。

**应对**：用过程宏 `#[function_tool]` 在编译期生成 JSON Schema。需要编写一个 proc-macro crate。

---

## 三、架构设计

### 3.1 Rust 项目结构

```
kasaya/
├── crates/
│   ├── kasaya-core/              # Framework 核心（Agent/Runner/Handoff/Guardrail/Tool/Tracing）
│   │   ├── src/
│   │   │   ├── lib.rs
│   │   │   ├── agent/
│   │   │   │   ├── mod.rs         # Agent struct + AgentBuilder
│   │   │   │   └── output.rs      # OutputType trait
│   │   │   ├── runner/
│   │   │   │   ├── mod.rs         # Runner（Agent Loop）
│   │   │   │   ├── config.rs      # RunConfig
│   │   │   │   ├── context.rs     # RunContext
│   │   │   │   ├── hooks.rs       # Lifecycle Hooks
│   │   │   │   └── result.rs      # RunResult / StreamEvent
│   │   │   ├── model/
│   │   │   │   ├── mod.rs         # ModelProvider trait
│   │   │   │   ├── provider.rs    # OpenAIProvider + 自建 Adapter
│   │   │   │   ├── message.rs     # Message / MessageRole
│   │   │   │   └── settings.rs    # ModelSettings
│   │   │   ├── tools/
│   │   │   │   ├── mod.rs         # FunctionTool trait
│   │   │   │   ├── registry.rs    # ToolRegistry
│   │   │   │   ├── group.rs       # ToolGroup
│   │   │   │   └── context.rs     # ToolContext
│   │   │   ├── handoff/
│   │   │   │   └── mod.rs         # Handoff + InputFilter
│   │   │   ├── guardrails/
│   │   │   │   ├── mod.rs         # Guardrail trait
│   │   │   │   ├── input.rs       # InputGuardrail
│   │   │   │   ├── output.rs      # OutputGuardrail
│   │   │   │   ├── tool.rs        # ToolGuardrail
│   │   │   │   ├── regex.rs       # RegexGuardrail
│   │   │   │   ├── keyword.rs     # KeywordGuardrail
│   │   │   │   └── llm.rs         # LLMGuardrail
│   │   │   ├── session/
│   │   │   │   ├── mod.rs         # SessionBackend trait
│   │   │   │   ├── memory.rs      # InMemoryBackend
│   │   │   │   └── postgres.rs    # PostgresBackend（可选）
│   │   │   ├── tracing/
│   │   │   │   ├── mod.rs         # Trace / Span
│   │   │   │   └── processor.rs   # TraceProcessor trait
│   │   │   ├── mcp/
│   │   │   │   └── mod.rs         # MCP 连接管理（依赖 rmcp）
│   │   │   ├── memory/
│   │   │   │   └── mod.rs         # Memory 系统
│   │   │   ├── team/
│   │   │   │   └── mod.rs         # Team 协作协议
│   │   │   ├── workflow/
│   │   │   │   └── mod.rs         # DAG 工作流引擎
│   │   │   └── approval/
│   │   │       └── mod.rs         # 审批模式
│   │   └── Cargo.toml
│   │
│   ├── kasaya-derive/            # 过程宏（#[function_tool]）
│   │   ├── src/
│   │   │   └── lib.rs             # 编译期 JSON Schema 生成
│   │   └── Cargo.toml
│   │
│   ├── kasaya-server/            # 后端 HTTP 服务（对应 backend/）
│   │   ├── src/
│   │   │   ├── main.rs            # 启动入口
│   │   │   ├── config.rs          # Settings（对应 core/config.py）
│   │   │   ├── db/
│   │   │   │   ├── mod.rs         # 连接池 + 迁移
│   │   │   │   └── models.rs      # 34 张表的 ORM 映射（sqlx::FromRow）
│   │   │   ├── api/               # 161 个端点
│   │   │   │   ├── mod.rs         # Router 组装
│   │   │   │   ├── agents.rs
│   │   │   │   ├── auth.rs
│   │   │   │   ├── sessions.rs
│   │   │   │   ├── ...（37 个模块）
│   │   │   │   └── ws.rs          # WebSocket（axum::extract::ws）
│   │   │   ├── services/          # 48 个服务模块
│   │   │   │   ├── mod.rs
│   │   │   │   ├── agent.rs
│   │   │   │   ├── ...
│   │   │   │   └── channel_adapters/
│   │   │   │       ├── mod.rs     # 适配器注册表
│   │   │   │       ├── wecom.rs
│   │   │   │       ├── dingtalk.rs
│   │   │   │       └── ...
│   │   │   ├── middleware/
│   │   │   │   ├── request_id.rs
│   │   │   │   ├── audit_log.rs
│   │   │   │   └── auth.rs        # JWT 提取器
│   │   │   └── error.rs           # AppError → IntoResponse
│   │   └── Cargo.toml
│   │
│   └── kasaya-cli/               # 命令行工具（可选）
│       ├── src/
│       │   └── main.rs
│       └── Cargo.toml
│
├── migrations/                    # sqlx 迁移文件（从 Alembic 迁移）
│   ├── 001_create_agent_configs.sql
│   ├── 002_create_sessions.sql
│   └── ...
│
├── frontend/                      # 前端不变
│   └── ...
│
├── Cargo.toml                     # Workspace 定义
└── docker-compose.yml
```

### 3.2 核心 Trait 设计

```rust
// === kasaya-core/src/model/mod.rs ===

/// LLM 模型提供商（替代 Python LiteLLMProvider）
#[async_trait]
pub trait ModelProvider: Send + Sync {
    async fn chat(&self, req: ChatRequest) -> Result<ModelResponse>;
    async fn chat_stream(&self, req: ChatRequest)
        -> Pin<Box<dyn Stream<Item = Result<ModelChunk>> + Send>>;
}

// === kasaya-core/src/agent/mod.rs ===

/// Agent 声明式定义
pub struct Agent {
    pub name: String,
    pub description: String,
    pub instructions: Arc<dyn AgentInstructions>,
    pub model: Option<String>,
    pub tools: Vec<Arc<dyn FunctionTool>>,
    pub handoffs: Vec<Handoff>,
    pub input_guardrails: Vec<Arc<dyn InputGuardrail>>,
    pub output_guardrails: Vec<Arc<dyn OutputGuardrail>>,
    pub tool_guardrails: Vec<Arc<dyn ToolGuardrail>>,
    pub output_type: Option<OutputType>,
    pub approval_mode: ApprovalMode,
}

/// 动态指令（str / sync fn / async fn）
pub trait AgentInstructions: Send + Sync {
    fn build(&self, ctx: &RunContext) -> Pin<Box<dyn Future<Output = String> + Send>>;
}

// === kasaya-core/src/tools/mod.rs ===

/// 函数工具（替代 Python FunctionTool）
#[async_trait]
pub trait FunctionTool: Send + Sync {
    fn name(&self) -> &str;
    fn description(&self) -> &str;
    fn parameters_schema(&self) -> serde_json::Value;
    async fn execute(&self, input: serde_json::Value, ctx: ToolContext)
        -> Result<ToolOutput>;
}

// === kasaya-core/src/runner/mod.rs ===

/// 执行引擎
pub struct Runner;

impl Runner {
    pub async fn run(agent: Arc<Agent>, input: Input, config: RunConfig)
        -> Result<RunResult>;

    pub fn run_streamed(agent: Arc<Agent>, input: Input, config: RunConfig)
        -> impl Stream<Item = StreamEvent>;

    pub fn run_sync(agent: Arc<Agent>, input: Input, config: RunConfig)
        -> Result<RunResult>;
}

// === kasaya-core/src/session/mod.rs ===

/// 会话持久化后端
#[async_trait]
pub trait SessionBackend: Send + Sync {
    async fn load(&self, session_id: &str) -> Result<Option<Vec<Message>>>;
    async fn save(&self, session_id: &str, messages: &[Message]) -> Result<()>;
}

// === kasaya-core/src/guardrails/mod.rs ===

#[async_trait]
pub trait InputGuardrail: Send + Sync {
    async fn check(&self, input: &str, ctx: &RunContext) -> GuardrailResult;
}

#[async_trait]
pub trait OutputGuardrail: Send + Sync {
    async fn check(&self, output: &str, ctx: &RunContext) -> GuardrailResult;
}

#[async_trait]
pub trait ToolGuardrail: Send + Sync {
    async fn before(&self, tool: &str, args: &serde_json::Value, ctx: &RunContext)
        -> GuardrailResult;
    async fn after(&self, tool: &str, result: &ToolOutput, ctx: &RunContext)
        -> GuardrailResult;
}

// === kasaya-core/src/tracing/mod.rs ===

#[async_trait]
pub trait TraceProcessor: Send + Sync {
    async fn on_trace_start(&self, trace: &Trace);
    async fn on_span_start(&self, span: &Span);
    async fn on_span_end(&self, span: &Span);
    async fn on_trace_end(&self, trace: &Trace);
}
```

### 3.3 过程宏设计

```rust
// kasaya-derive: #[function_tool] 编译期 JSON Schema 生成

use kasaya_derive::function_tool;

/// 自动生成 JSON Schema + FunctionTool 实现
#[function_tool]
async fn search_web(
    /// 搜索关键词
    query: String,
    /// 最大结果数
    max_results: Option<u32>,
) -> Result<Vec<SearchResult>> {
    // 实现逻辑
}

// 展开为：
// impl FunctionTool for SearchWebTool {
//     fn name() -> &str { "search_web" }
//     fn description() -> &str { "搜索关键词" }
//     fn parameters_schema() -> Value {
//         json!({
//             "type": "object",
//             "properties": {
//                 "query": { "type": "string", "description": "搜索关键词" },
//                 "max_results": { "type": "integer", "description": "最大结果数" }
//             },
//             "required": ["query"]
//         })
//     }
//     async fn execute(&self, input: Value, ctx: ToolContext) -> Result<ToolOutput> { ... }
// }
```

### 3.4 Runner Agent Loop 核心循环

```rust
// kasaya-core/src/runner/mod.rs

impl Runner {
    pub async fn run(
        agent: Arc<Agent>,
        input: Input,
        config: RunConfig,
    ) -> Result<RunResult> {
        let provider = Self::resolve_provider(&agent, &config)?;
        let mut messages: Vec<Message> = Self::build_messages(&agent, input);
        let mut trace = Trace::new(&agent.name);
        let mut current_agent = agent;
        let mut token_usage = TokenUsage::default();

        for turn in 0..config.max_turns {
            // 1. 执行输入护栏
            Self::run_input_guardrails(&current_agent, &messages, &config).await?;

            // 2. 调用 LLM
            let response = provider.chat(ChatRequest {
                messages: &messages,
                model: current_agent.model.as_deref(),
                tools: &Self::build_tool_schemas(&current_agent),
                settings: &config.model_settings,
            }).await?;

            token_usage += response.usage.clone();

            // 3. 检查停止原因
            match response.stop_reason {
                StopReason::EndTurn => {
                    return Ok(RunResult {
                        final_output: response.content,
                        messages,
                        last_agent: current_agent,
                        token_usage,
                        trace,
                    });
                }
                StopReason::ToolCalls(tool_calls) => {
                    // 4. 并行执行工具调用
                    let results = Self::execute_tools_parallel(
                        &current_agent, &tool_calls, &config
                    ).await?;

                    // 5. 追加结果到消息
                    messages.push(response.into_message());
                    for result in results {
                        messages.push(result.into_message());
                    }
                }
                StopReason::Handoff(target) => {
                    // 6. 处理 Handoff
                    current_agent = Self::resolve_handoff(&current_agent, &target)?;
                    messages = Self::apply_input_filter(&messages, &target);
                }
            }
        }

        Err(RunnerError::MaxTurnsExceeded)
    }
}
```

---

## 四、数据库迁移策略

### 4.1 现有 45 个 Alembic 迁移 → Rust sqlx 迁移

**方案**：不逐个翻译 Alembic 迁移，而是从最终 schema 生成一个初始迁移。

```
Alembic 0001-0045（Python）
        ↓ 导出最终 schema
pg_dump --schema-only > schema.sql
        ↓ 清理为 sqlx 格式
migrations/001_initial.sql（单文件，包含全部 34 张表）
```

后续增量迁移直接在 Rust 侧用 `sqlx migrate add` 创建。

### 4.2 ORM 映射

```rust
// Python SQLAlchemy → Rust sqlx::FromRow

// Python:
// class AgentConfig(Base):
//     __tablename__ = "agent_configs"
//     id: Mapped[str] = mapped_column(String, primary_key=True)
//     name: Mapped[str] = mapped_column(String, unique=True)
//     instructions: Mapped[str] = mapped_column(Text)

// Rust:
#[derive(Debug, FromRow, Serialize, Deserialize)]
pub struct AgentConfig {
    pub id: String,
    pub name: String,
    pub instructions: String,
    pub model: Option<String>,
    pub tools_json: Option<serde_json::Value>,   // JSONB
    pub handoffs_json: Option<serde_json::Value>, // JSONB
    pub guardrails_json: Option<serde_json::Value>,
    pub output_type: Option<serde_json::Value>,
    pub provider_name: Option<String>,
    pub org_id: Option<String>,
    pub is_deleted: bool,
    pub created_at: chrono::NaiveDateTime,
    pub updated_at: chrono::NaiveDateTime,
}
```

---

## 五、性能预期

### 5.1 量化提升预估

| 指标 | Python (当前) | Rust (预期) | 提升倍数 |
|------|:------------:|:-----------:|:--------:|
| 冷启动 | ~3s | ~50ms | 60x |
| 空载内存 | ~200MB | ~30MB | 7x |
| GET /api/v1/agents p95 | ~200ms | ~5ms | 40x |
| POST /api/v1/agents p95 | ~200ms | ~8ms | 25x |
| 并发 100 用户 QPS | ~500 | ~50,000+ | 100x |
| 二进制大小 | ~500MB（含 Python） | ~50MB | 10x |
| WebSocket 并发连接 | ~1,000 | ~100,000+ | 100x |

> 注意：**LLM API 调用耗时不变**（网络 IO 1-10s），Rust 只加速后端处理部分。

### 5.2 真实收益场景

| 场景 | Rust 收益 |
|------|----------|
| **高频 API 查询**（Agent 列表、Trace 查询、Token 统计） | 显著提升，p95 从 200ms → 5ms |
| **大批量数据处理**（Token 审计聚合、APM 统计） | 显著提升，CPU 密集计算快 10-50x |
| **高并发 WebSocket**（实时事件推送） | 显著提升，单机支撑 10 万连接 |
| **Guardrail 正则匹配**（内容安全检查） | 显著提升，正则引擎性能远超 Python re |
| **LLM 流式转发**（SSE 代理） | 中等提升，瓶颈在 LLM API 不在本地 |
| **单次 Agent 对话** | 几乎无感知，瓶颈在 LLM API（2-10s） |

---

## 六、实施计划

### 阶段 1：基础骨架（4 周）

| 周 | 任务 | 交付物 |
|----|------|--------|
| 1 | Workspace 搭建 + `kasaya-core` 骨架 | Cargo.toml + Agent/Message/RunConfig struct |
| 2 | Model Provider trait + OpenAI Provider（基于 async-openai） | `ModelProvider` trait + `OpenAIProvider` 实现 |
| 3 | `#[function_tool]` 过程宏 | kasaya-derive crate |
| 4 | Runner Agent Loop 核心循环 | `run()` / `run_streamed()` 基本流程 |

### 阶段 2：Framework 核心完成（6 周）

| 周 | 任务 | 交付物 |
|----|------|--------|
| 5-6 | Handoff + Agent-as-Tool | 多 Agent 编排 |
| 7-8 | 三级 Guardrails（Input/Output/Tool × Regex/Keyword/LLM） | 护栏系统 |
| 9 | Session + Tracing | 会话持久化 + 链路追踪 |
| 10 | MCP 集成（rmcp） | MCP 工具发现 + 调用 |

### 阶段 3：Framework 扩展模块（4 周）

| 周 | 任务 | 交付物 |
|----|------|--------|
| 11 | Memory + Skill | 记忆系统 + 技能系统 |
| 12 | Team（Sequential/Parallel/Coordinator） | 多 Agent 协作 |
| 13 | Workflow DAG | DAG 工作流引擎 |
| 14 | Approval + Sandbox + Checkpoint + Intent + CostRouter + Evolution | 剩余模块 |

### 阶段 4：后端 HTTP 服务（8 周）

| 周 | 任务 | 交付物 |
|----|------|--------|
| 15-16 | axum 骨架 + DB 连接池 + 迁移 + 中间件 + JWT 认证 | kasaya-server 可启动 |
| 17-18 | 核心 CRUD（agents / providers / sessions / traces / token-usage） | 高频 API 可用 |
| 19-20 | 剩余 28 个路由模块 | 全部 161 端点 |
| 21-22 | WebSocket + IM 渠道适配器 + 后台任务（Scheduler/审计刷盘） | 全功能后端 |

### 阶段 5：测试 + 集成（4 周）

| 周 | 任务 | 交付物 |
|----|------|--------|
| 23-24 | Framework 单元测试（对标 1218 个 Python 测试） | 核心路径覆盖 |
| 25-26 | 集成测试 + 前端对接 + 性能基准 | 前端无缝切换到 Rust 后端 |

### 总计：26 周（~6 个月）

---

## 七、风险与缓解

| 风险 | 概率 | 影响 | 缓解措施 |
|------|:----:|:----:|---------|
| litellm 多厂商适配不完整 | 高 | 高 | 先支持 OpenAI 兼容 API（覆盖 80% 国产模型），非兼容厂商后续逐步添加 |
| Rust 编写速度慢导致延期 | 中 | 中 | 优先完成核心路径（Agent/Runner/Tool），其余模块渐进式迁移 |
| rmcp 不成熟导致 MCP 功能缺失 | 中 | 低 | MCP 功能面窄，必要时 fork 维护或自建 |
| 数据库迁移出错 | 低 | 高 | 从 Python 侧导出最终 schema，不逐个翻译迁移 |
| 前端 API 不兼容 | 低 | 中 | 保持 REST API 路径和 JSON 格式完全一致 |
| 人才稀缺 | 中 | 高 | 选择成熟 crate（axum/sqlx/serde）降低学习曲线 |

---

## 八、结论

### Rust 重写是可行的，但需注意：

1. **最大风险是 litellm 替代** — 建议用 OpenAI 兼容协议 + 少数自建 adapter 的混合方案
2. **6 个月是合理预估** — 不要压缩，Rust 的所有权模型需要更多设计思考时间
3. **建议渐进式迁移** — 不是一次性替换，可以先让 Python 和 Rust 后端并行运行，逐步切换流量
4. **前端零改动** — 只要 REST API 契约一致，前端完全不需要变动
5. **最大的性能收益在高并发和 CPU 密集场景** — 如果主要瓶颈是 LLM API 调用延迟，性能体感提升有限

### 推荐的启动方式

```
第 1 周：搭建 Workspace + Hello World axum 服务
第 2 周：实现 Agent struct + Message 类型
第 3 周：实现 OpenAI Provider（async-openai）
第 4 周：实现 Runner 核心循环（单 Agent 对话跑通）
```

**四周后可以做一个评估点** — 如果 Agent 单轮对话在 Rust 中跑通了，说明核心路径可行，继续推进；如果卡在 Provider 适配上，可以及时调整策略。
