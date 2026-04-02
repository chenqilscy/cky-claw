# AI Agent 系统竞品架构分析

> 调研日期：2026-04-02
> 分析范围：Claude Code、OpenAI Codex CLI、OpenAI Agents SDK、DeerFlow

## 核心发现

所有主流 AI Agent 系统都采用 **"单主 Agent + 委派"** 模式，而非传统意义上的"多个独立 Agent 协作"。

```
共同架构：
用户消息 → 【主 Agent（LLM 推理循环）】→ 调用工具 / 委派子 Agent → 汇总 → 回复用户
                    ↑                              │
                    └──────── 循环直到完成 ──────────┘
```

---

## 一、Claude Code

| 维度 | 设计 |
|------|------|
| 执行模型 | 单个 Agent 循环：LLM 推理 → Tool 调用 → 结果返回 → 继续推理 |
| 子 Agent | 可并行 spawn 多个 subagent，各自有独立上下文、工具、终止条件 |
| 工具扩展 | MCP（STDIO + HTTP）+ 内置工具（文件读写、bash、搜索） |
| 知识注入 | AGENTS.md（全局 / 项目 / 子目录三级）、Plugins 系统 |
| 沙箱 | macOS Seatbelt / Linux Docker，网络隔离 |
| SDK | 提供编程接口可嵌入其他应用 |
| 关键特点 | 插件生态；无自定义 Agent 类型定义 |

---

## 二、OpenAI Codex CLI

| 维度 | 设计 |
|------|------|
| 执行模型 | 单 Agent 循环，三级审批模式（suggest / auto-edit / full-auto） |
| 子 Agent | 支持**自定义 Agent**（TOML 配置），每个可独立指定 model、sandbox、MCP、instructions |
| 内置 Agent | `default`（通用）、`worker`（执行）、`explorer`（探索，只读） |
| 工具扩展 | MCP（STDIO + Streamable HTTP + OAuth） |
| 知识注入 | AGENTS.md + **Skills 系统**（SKILL.md + scripts/ + references/，支持安装/分发为 Plugin） |
| 沙箱 | macOS Seatbelt / Linux bubblewrap+Landlock / Windows 受限令牌 |
| 批量处理 | `spawn_agents_on_csv` — 批量任务分发，每行一个 worker |
| 配置 | `config.toml` 统一配置，支持多 LLM Provider |
| 关键特点 | 自定义 Agent 最灵活；Skills 生态可分发为 Plugin |

### Codex 自定义 Agent 配置示例

```toml
# .codex/agents/reviewer.toml
name = "reviewer"
description = "PR reviewer focused on correctness, security, and missing tests."
model = "gpt-5.4"
model_reasoning_effort = "high"
sandbox_mode = "read-only"
developer_instructions = """
Review code like an owner.
Prioritize correctness, security, behavior regressions, and missing test coverage.
"""
```

### Codex Skills 结构

```
my-skill/
├── SKILL.md          # 必须：指令 + 元数据（name, description）
├── scripts/          # 可选：可执行脚本
├── references/       # 可选：参考文档
├── assets/           # 可选：模板、资源
└── agents/
    └── openai.yaml   # 可选：UI 元数据、策略、依赖声明
```

### Codex Subagent 管理

- `agents.max_threads`：最大并发 Agent 线程数（默认 6）
- `agents.max_depth`：嵌套深度（默认 1，允许直接子 Agent，不允许更深嵌套）
- `agents.job_max_runtime_seconds`：每个 worker 超时时间

---

## 三、OpenAI Agents SDK

| 维度 | 设计 |
|------|------|
| 执行模型 | `Runner.run()` 驱动 Agent 循环，内置 tool 调用 + 结果回传 |
| 多 Agent 编排 | **Handoffs**（Agent A 将控制权移交给 Agent B）+ **Agents-as-Tools**（Agent A 像调工具一样调 Agent B） |
| 工具系统 | Python 函数自动转 Tool（Pydantic Schema）+ MCP Server + Hosted Tool |
| Guardrails | 输入/输出校验，与 Agent 执行并行运行，快速失败 |
| 记忆/会话 | Sessions（SQLAlchemy / SQLite / Redis / Dapr），跨 run 持久化 |
| 人工介入 | 内置 Human-in-the-loop 机制 |
| 链路追踪 | 内置 Tracing，可视化、调试、监控 |
| 模型支持 | 提供商无关（OpenAI / LiteLLM / any-llm 支持 100+ 模型） |
| 关键特点 | **唯一真正支持 Multi-Agent 编排的框架**；极轻量（few primitives）；Python 原生编排 |

### Agents SDK 核心概念

```python
from agents import Agent, Runner

# 定义 Agent
agent = Agent(
    name="Assistant",
    instructions="You are a helpful assistant",
    tools=[...],           # Python 函数 / MCP / Hosted Tool
    handoffs=[...],        # 可移交的其他 Agent
)

# 运行
result = Runner.run_sync(agent, "Write a haiku about recursion")
```

### 编排模式

1. **Handoff**：Agent A 完成后将控制权完整移交给 Agent B
2. **Agent-as-Tool**：Agent A 在执行中调用 Agent B 获取结果，然后继续自己的工作

---

## 四、DeerFlow

| 维度 | 设计 |
|------|------|
| 执行模型 | Lead Agent 单例 + 2 个内置 Sub-Agent（general-purpose、bash） |
| 自定义 Agent | 只能创建 config 包（config.yaml + SOUL.md），注入 Lead Agent 行为 |
| 工具扩展 | MCP + config.yaml 中的 Python 工具模块 |
| 知识注入 | Skills（SKILL.md，Prompt 注入） |
| Middleware | 12 个内置 Middleware（不可自定义） |
| 关键限制 | 不能自定义 Sub-Agent；Lead Agent 代码写死；文件系统存储；无多租户 |

---

## 五、横向对比矩阵

| 能力 | Claude Code | Codex CLI | Agents SDK | DeerFlow |
|------|-------------|-----------|------------|----------|
| 自定义 Agent 类型 | ❌ | ✅ TOML | ✅ Python 类 | ❌ |
| Agent 间协作 | spawn 并行 | spawn 并行 | Handoff + Agent-as-Tool | ❌ |
| 自定义编排拓扑 | ❌ | ❌ | ✅ | ❌ |
| MCP 集成 | ✅ | ✅ + OAuth | ✅ | ✅ |
| Skills/知识注入 | AGENTS.md | SKILL.md + Plugin | Agent instructions | SOUL.md |
| 沙箱 | ✅ OS级 | ✅ OS级 | ❌ 需自建 | ✅ Docker |
| 内置追踪 | ❌ | ❌ | ✅ | ❌ |
| 会话记忆 | 有限 | 有限 | ✅ Sessions | memory.json |
| 模型无关 | ❌ | ❌ | ✅ 100+ | ✅ |
| Human-in-loop | 审批模式 | 审批模式 | ✅ 编程接口 | ❌ |
| 开放程度 | 中 | 高 | **最高** | 低 |

---

## 六、对 CkyClaw 的架构启示

### 关键设计模式可借鉴

| 来源 | 设计模式 | CkyClaw 应用 |
|------|---------|-------------|
| Codex | 声明式 Agent 配置（TOML） | 用 YAML/TOML 定义 Agent 类型 |
| Codex | Skills 系统（SKILL.md + scripts/ + references/） | 可分发的知识包 |
| Codex | 三级审批模式 | 任务执行的人工介入级别 |
| Agents SDK | Handoff / Agent-as-Tool | Agent 间协作的两种模式 |
| Agents SDK | Sessions | 跨会话记忆持久化 |
| Agents SDK | Tracing | 执行可视化的数据源 |
| Agents SDK | Guardrails | 输入/输出校验 |
| 所有竞品 | MCP 作为工具扩展标准 | 统一的工具扩展接口 |

### CkyClaw 的差异化定位

所有竞品都是"编码 Agent"，CkyClaw 是"任务管理系统"：

| 竞品共有 | CkyClaw 差异化 |
|---------|---------------|
| 单用户终端工具 | 多租户 Web 平台 |
| Agent 自主决策做什么 | 用户管理任务，Agent 执行 |
| 无执行可视化 | 流程图式执行监控 |
| 无审批工作流 | 内置审批/监督/干预 |
| 无 APM | 完整的性能监控 |
| 无 IM 集成 | 多渠道接入 |
