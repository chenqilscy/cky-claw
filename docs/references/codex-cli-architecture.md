# OpenAI Codex CLI 架构研究

> 研究日期：2026-04-02  
> 来源：https://github.com/openai/codex  
> 仓库状态：71.4k stars, 10k forks, 409 contributors  
> 主语言：Rust 94.7%, Python 3%, TypeScript 1.4%  
> 许可证：Apache-2.0

---

## 1. 概述

Codex CLI 是 OpenAI 开源的**本地终端编码代理**（coding agent），核心定位是"chat-driven development"——在终端中与 LLM 对话、自动执行代码、编辑文件、运行命令，全程受版本控制保护。

项目经历了 **TypeScript → Rust** 的迁移，当前 Rust 实现是维护版本，TypeScript 版本 (`codex-cli/`) 已标记为 legacy。

---

## 2. 代码组织（Cargo Workspace）

```
codex-rs/
├── core/           # 核心业务逻辑（agent loop, session, tools, sandboxing）
├── exec/           # 无头（headless）CLI，用于自动化 / CI
├── tui/            # 全屏 TUI（基于 Ratatui）
├── cli/            # CLI 多工具入口，通过子命令暴露上述功能
├── protocol/       # 协议定义（Event、Op、items、approvals、permissions）
├── sandboxing/     # 沙箱实现（Seatbelt/Landlock/Bubblewrap/Windows）
├── tools/          # 工具定义和发现模型提取
├── config/         # 配置加载（config.toml）
├── exec-server/    # 执行服务器
├── mcp-server/     # MCP 服务器（Codex 可作为 MCP server）
├── rmcp-client/    # MCP 客户端
├── plugin/         # 插件系统
├── skills/         # 技能系统
├── hooks/          # 钩子系统（生命周期事件）
├── state/          # 状态管理
├── network-proxy/  # 网络代理（出站控制）
├── login/          # 认证
├── analytics/      # 遥测
├── app-server/     # 应用服务器（IDE 集成等）
└── ...             # 40+ crates
```

---

## 3. 核心架构：Agent Loop

### 3.1 Session + Submission Loop 模型

Codex 采用 **Session → Submission Loop → Turn** 三层架构：

```
┌─────────────────────────────────────────┐
│  Codex::spawn()                         │
│  ├── Session::new()                     │
│  │   ├── 初始化 config, auth, models    │
│  │   ├── 加载 exec_policy               │
│  │   ├── 启动 MCP 连接管理器            │
│  │   ├── 启动网络代理                    │ 
│  │   ├── 初始化 rollout recorder         │
│  │   └── 加载对话历史                    │
│  └── tokio::spawn(submission_loop)      │
│       └── 持续接收 Op，分发给 handlers  │
└─────────────────────────────────────────┘
```

#### Submission Loop（`codex.rs` 中的 `submission_loop`）

- 通过 `async_channel` 接收 `Submission`（包含 `Op` 枚举）
- **Op 类型** 包括：
  - `UserInput` / `UserTurn` — 用户消息，触发 agent turn
  - `ExecApproval` / `PatchApproval` — 用户对命令/补丁的审批决策
  - `Interrupt` — 中断当前 turn
  - `Compact` — 压缩对话历史
  - `Undo` — 撤销操作
  - `Review` — 代码审查
  - `Shutdown` — 关闭会话
  - `InterAgentCommunication` — 子代理通信
  - `ThreadRollback` — 回滚到之前的 turn
  - `RunUserShellCommand` — 用户直接执行 shell 命令
  - `RealtimeConversation*` — 实时语音对话
  - 等等

### 3.2 Turn 执行流（`run_turn`）

```
run_turn()
│
├── 1. Pre-sampling compaction（自动压缩历史以适应上下文窗口）
├── 2. 注入初始上下文（developer instructions, env context, skills, plugins）
├── 3. 记录用户消息到对话历史
├── 4. 解析 @mentions（skills, plugins, connectors/apps）
├── 5. 运行 hooks（user_prompt_submit）
│
└── loop {  // 核心采样循环
│       ├── 收集 pending_input（用户在 agent 运行时提交的新消息）
│       ├── 构建 sampling_request_input（从对话历史）
│       ├── 调用 run_sampling_request()
│       │   ├── 构建 ToolRouter（注册所有可用工具）
│       │   ├── 构建 Prompt（input + tools + base_instructions）
│       │   ├── 发送到 LLM（流式）
│       │   └── 处理流式响应事件：
│       │       ├── OutputItemAdded → 新的 assistant 消息项
│       │       ├── OutputItemDone → 处理完成项（可能触发工具调用）
│       │       ├── OutputTextDelta → 流式文本增量
│       │       ├── ReasoningSummaryDelta → 推理摘要增量
│       │       ├── Completed → 更新 token 使用信息
│       │       └── ...
│       │
│       ├── 若 needs_follow_up = true → 继续循环（工具调用后需要追加请求）
│       ├── 若 token_limit_reached → 自动 compact，继续循环
│       ├── 运行 stop hooks → 决定是否继续
│       ├── 运行 after_agent hooks
│       └── break（turn 完成）
    }
```

**关键设计**：模型返回 **function call** 时，Codex 执行它并将输出发回模型进入下一次采样；返回 **assistant message** 则表示 turn 完成。

### 3.3 Tool 调用并发模型

- 使用 `FuturesOrdered` 管理 in-flight 工具调用
- 工具调用结果作为 `ResponseInputItem` 注入回对话历史
- 支持 `parallel_tool_calls`（取决于模型能力）

---

## 4. 工具系统

### 4.1 ToolRouter

工具通过 `ToolRouter` 统一管理，来源包括：

| 来源 | 说明 |
|---|---|
| **内置工具** | shell (exec), apply_patch, file read 等 |
| **MCP 工具** | 通过 MCP 协议连接的外部工具服务器 |
| **Dynamic Tools** | 运行时动态注册的工具 |
| **App/Connector 工具** | Codex Apps 平台的工具 |
| **Discoverable Tools** | tool_suggest 发现的工具 |
| **Skills 注入工具** | 通过 skills 系统注入的工具 |

### 4.2 内置工具

```
codex-rs/core/src/tools/
├── handlers/       # 各工具的执行 handler
├── code_mode/      # code-mode 工具适配器
├── js_repl/        # JavaScript REPL 工具
├── runtimes/       # 工具运行时
├── orchestrator.rs # 工具编排
├── router.rs       # ToolRouter（工具路由/注册/可见性）
├── registry.rs     # 工具注册表
├── sandboxing.rs   # 工具沙箱化
├── network_approval.rs # 网络审批
└── spec.rs         # 工具规格定义
```

### 4.3 Shell / Exec 工具（`exec.rs`）

核心命令执行逻辑（1233 行）：

- **ExecParams**: command, cwd, expiration, capture_policy, env, network, sandbox_permissions
- **超时机制**: `ExecExpiration`（Timeout / DefaultTimeout / Cancellation）
- **输出捕获**: stdout/stderr 流式读取，带最大字节限制 (`EXEC_OUTPUT_MAX_BYTES`)
- **输出增量**: 通过 `ExecCommandOutputDeltaEvent` 实时推送
- **IO drain 超时**: 防止孙进程继承 stdout/stderr 导致挂起

### 4.4 MCP 支持

- **MCP Client**: Codex 连接到外部 MCP 服务器获取工具
- **MCP Server**: `codex mcp-server` 让 Codex 自身作为 MCP 服务器
- MCP 连接通过 `McpConnectionManager` 管理
- 支持 MCP OAuth 认证
- 支持 MCP elicitation（UI 表单交互）

---

## 5. 安全模型 & 沙箱

### 5.1 审批策略（Approval Policy）

| 模式 | 自动读取 | 自动执行 | 需审批 |
|---|---|---|---|
| **Suggest**（默认） | 仓库文件 | — | 所有写操作和命令 |
| **Auto Edit** | 仓库文件 | 文件编辑 | 所有 shell 命令 |
| **Full Auto** | 仓库文件 | 文件编辑 + 命令 | —（沙箱保护） |

### 5.2 沙箱策略（Sandbox Policy）

```
--sandbox read-only          # 默认：只读
--sandbox workspace-write    # 允许写当前工作区
--sandbox danger-full-access # 禁用沙箱（危险）
```

### 5.3 平台沙箱实现

```
codex-rs/sandboxing/src/
├── seatbelt.rs              # macOS: Apple Seatbelt (sandbox-exec)
├── seatbelt_base_policy.sbpl
├── seatbelt_network_policy.sbpl
├── landlock.rs              # Linux: Landlock LSM
├── bwrap.rs                 # Linux: Bubblewrap 容器
├── manager.rs               # 沙箱管理器
└── policy_transforms.rs     # 策略转换
```

| 平台 | 机制 | 特点 |
|---|---|---|
| **macOS 12+** | Apple Seatbelt (`sandbox-exec`) | 只读 jail，网络完全阻断 |
| **Linux** | Landlock + Bubblewrap | 文件系统限制 + 可选 Docker 隔离 |
| **Windows** | Restricted Token / Elevated sandbox | 受限令牌 + 可选 Private Desktop |

### 5.4 网络控制

- **Full Auto 模式下网络默认禁用**
- 专用 `network-proxy` crate 实现出站代理
- `iptables`/`ipset` 脚本仅允许 OpenAI API
- 支持网络策略审批（allowlist/denylist）
- `ExecPolicy` 管理命令和网络规则白名单

---

## 6. LLM 集成

### 6.1 模型交互

- 使用 **OpenAI Responses API**（非 Chat Completions）
- 支持 **WebSocket** 流式传输（sticky routing）
- `ModelClient` 是 session 级别，`ModelClientSession` 是 turn 级别
- 支持 **Realtime API**（语音对话）

### 6.2 Prompt 构建

```
Prompt {
    input: Vec<ResponseItem>,       // 对话历史
    tools: Vec<ToolSpec>,           // 可用工具
    parallel_tool_calls: bool,      // 是否允许并行工具调用
    base_instructions: String,      // 基础系统指令
    personality: Option<Personality>,// 人格设置
    output_schema: Option<Value>,   // 结构化输出 schema
}
```

### 6.3 上下文管理

- **初始上下文注入**：developer instructions + env context + skills + plugins + personality
- **增量更新**：只在 turn 间发送 settings diff
- **自动压缩**（Auto Compact）：当 token 使用接近上下文窗口限制时自动压缩
- **模型切换压缩**：切换到更小上下文窗口模型时预先压缩
- **Rollout 记录器**：持久化所有 events 到文件，支持 resume/fork

### 6.4 多 Provider 支持

通过 `providers` 配置支持多种后端：

- OpenAI, Azure OpenAI, OpenRouter, Gemini, Ollama, Mistral, DeepSeek, xAI, Groq, ArceeAI 等
- 每个 provider 通过 `baseURL` + `envKey` 配置

---

## 7. 关键设计模式

### 7.1 Event-Driven 架构

```
Op (用户操作) → Session → Handler → EventMsg → UI/Client
```

所有通信通过 `Event` + `EventMsg` 枚举：
- `TurnStarted`, `TurnComplete`, `TurnAborted`
- `AgentMessage`, `AgentMessageDelta`, `AgentReasoning`
- `ExecApprovalRequest`, `ApplyPatchApprovalRequest`
- `TokenCount`, `TurnDiff`, `BackgroundEvent`
- `SessionConfigured`, `ShutdownComplete`
- 等等

### 7.2 Task 抽象

不同类型的 turn 通过 Task trait 抽象：
- `RegularTask` — 普通用户交互
- `CompactTask` — 历史压缩
- `UndoTask` — 撤销
- `ReviewTask` — 代码审查
- `UserShellCommandTask` — 用户 shell 命令

### 7.3 Hooks 系统

生命周期钩子：
- `user_prompt_submit` — 用户消息提交前
- `stop` — agent 准备停止时（可继续）
- `after_agent` — agent turn 完成后
- `PostToolUse` — 工具使用后

### 7.4 Skills & Plugins 系统

- **Skills**: 通过 `.codex/skills/` 目录或 `AGENTS.md` 定义
- **Plugins**: 扩展能力包，带 capability summaries
- 支持 `@mention` 语法在用户消息中引用 skills/plugins
- 隐式调用 vs 显式调用

### 7.5 Memory 系统

- `~/.codex/memories/` 持久化 agent 记忆
- 支持 drop/update memories 操作
- 记忆在沙箱 writable roots 中

### 7.6 Multi-Agent（实验性）

- `InterAgentCommunication` — 代理间通信
- `ThreadSpawn` — 生成子代理线程
- `AgentPath` — 代理路径（层级）
- `Mailbox` — 代理邮箱
- `agent_max_depth` — 最大嵌套深度

### 7.7 Guardian（安全审查）

- 独立的审查子会话 (`GuardianReviewSessionManager`)
- 审查命令/补丁的安全性
- 使用 ARC（Autonomous Review Chain）

---

## 8. 执行模型总结

```
用户输入
    ↓
Submission(Op::UserInput)
    ↓
Session.spawn_task(RegularTask)
    ↓
run_turn()
    ↓
┌─── loop ────────────────────────────┐
│ 构建 prompt (history + tools)       │
│     ↓                               │
│ LLM 流式响应                        │
│     ↓                               │
│ ┌── match event ──────────────────┐ │
│ │ AssistantMessage → 记录 → 完成  │ │
│ │ FunctionCall → 执行工具:        │ │
│ │   ├── shell → sandbox exec      │ │
│ │   ├── apply_patch → 文件编辑    │ │
│ │   ├── mcp_tool → MCP 调用       │ │
│ │   └── ... → 结果注入历史        │ │
│ └─────────────────────────────────┘ │
│ needs_follow_up? → continue         │
│ token_limit? → auto_compact         │
│ stop_hook? → maybe continue         │
│ done → break                        │
└─────────────────────────────────────┘
    ↓
TurnComplete event → UI
```

---

## 9. 对 AgentFlow 项目的启示

| Codex 模式 | 可借鉴点 |
|---|---|
| **Session ↔ Submission Loop** | 异步事件驱动的会话模型 |
| **Turn = 一次完整的 LLM 交互循环** | 明确的 turn 生命周期 |
| **ToolRouter** | 统一的工具注册/发现/路由 |
| **Approval 三级策略** | 灵活的人机协作权限 |
| **平台沙箱 + 网络隔离** | 深度防御的安全模型 |
| **Auto Compact** | 自动上下文窗口管理 |
| **Rollout 持久化** | 可 resume/fork 的会话 |
| **Hooks 生命周期** | 可扩展的事件钩子 |
| **Multi-Agent 通信** | 子代理生成和邮箱机制 |
| **AGENTS.md 层级** | 全局 → 项目 → 子目录的指令层叠 |
