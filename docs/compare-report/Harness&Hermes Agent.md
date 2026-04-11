---
title: Agent Harness + Hermes Agent 深度研究与对比
date: 2026-04-11
---

# Agent Harness + Hermes Agent 深度研究

## 一、Anthropic Agent Harness — 工程化长时运行 Agent

### 1.1 核心理念

Anthropic 工程团队在 2025-2026 年提出了一套 **"有效 Harness"** 的工程方法论，核心论点：

> **Agent 的可靠性是架构属性，不是模型属性。** 即使单步准确率 95%，20 步链式执行的端到端成功率也只有 0.95^20 ≈ 36%。

Harness 的使命：**打断脆弱长链**，插入检查点、验证门、恢复机制，将无界长链变成有界可验证的短单元。

### 1.2 三 Agent Harness 模式

Anthropic 的生产实践采用三 Agent 分离架构：

```
┌──────────────────────────────────────────────────────┐
│                   Harness Controller                  │
│                                                       │
│  ┌─────────────┐  ┌─────────────┐  ┌──────────────┐ │
│  │  Planning    │  │ Generation  │  │  Evaluation  │ │
│  │  Agent       │→│ Agent       │→│  Agent        │ │
│  │             │  │             │  │              │ │
│  │ 分解任务为   │  │ 增量编码    │  │ 运行测试     │ │
│  │ 结构化特性   │  │ 实现特性    │  │ 验证输出     │ │
│  │ 列表(JSON)  │  │             │  │ 评分/反馈    │ │
│  └─────────────┘  └─────────────┘  └──────────────┘ │
│         ↑                                  │          │
│         └────── 反馈循环(5-15 轮) ──────────┘          │
└──────────────────────────────────────────────────────┘
```

**Planning Agent（规划者）**
- 首次会话使用 Initializer Agent，读取项目结构生成结构化特性列表
- 特性列表用 **JSON 而非 Markdown**（机器可解析、可追踪进度）
- 每个特性包含：名称、描述、依赖关系、验收标准

**Generation Agent（生成者）**
- 增量式进展，每次只实现 1-2 个特性
- 遵循"Initializer → Coding"两阶段：首会话理解上下文，后续会话增量编码
- **上下文重置（Context Reset）** 而非仅仅压缩——当外部状态充分时，开启全新窗口

**Evaluation Agent（评估者）**
- 运行测试套件（集成 Playwright MCP 进行浏览器测试）
- 评估代码质量、功能正确性
- 每轮运行 5-15 次迭代，单次可持续长达 4 小时

### 1.3 关键工程实践

| 实践 | 说明 |
|------|------|
| **特性列表用 JSON** | 机器可解析、进度可追踪，避免 Markdown 模糊性 |
| **上下文重置 > 压缩** | 当外部状态充分（文件、测试、文档）时，开全新窗口而非压缩历史 |
| **增量进展** | 每次只做 1-2 个特性，完成后再推进 |
| **Initializer 首会话** | 首次会话专用于理解项目结构和生成任务计划 |
| **结构化 Handoff** | 跨会话交接包含：当前状态、变更内容、已验证项、失败原因、下一步 |
| **文件系统作为交接介质** | 最通用、最持久、人类可读 |

### 1.4 Cache-First 上下文工程

```
┌────────┬──────────────────────────────────┬─────────────────────┐
│  层级  │            策略                  │      触发条件       │
├────────┼──────────────────────────────────┼─────────────────────┤
│ Tier 0 │ 结构化输出（JSON Schema）        │ 默认                │
├────────┼──────────────────────────────────┼─────────────────────┤
│ Tier 1 │ 大结果外部化到 Artifact Store    │ 工具返回 >8k token  │
├────────┼──────────────────────────────────┼─────────────────────┤
│ Tier 2 │ 延迟淘汰旧输入/工具结果          │ 上下文 80-90%       │
├────────┼──────────────────────────────────┼─────────────────────┤
│ Tier 3 │ 压缩/摘要（LLM 驱动）           │ 窗口仍然不够        │
├────────┼──────────────────────────────────┼─────────────────────┤
│ Tier 4 │ 全新窗口重启                     │ 外部状态充分时      │
└────────┴──────────────────────────────────┴─────────────────────┘
```

**缓存纪律（不可违反）：**
- 不在会话中动态增删工具（破坏 prompt prefix 缓存）
- 不在会话中切换模型
- 不重写 System Prompt 反映动态状态
- 保持序列化确定性

---

## 二、Hermes Agent — Nous Research 自改进 Agent 框架

### 2.1 基本信息

| 项目 | 信息 |
|------|------|
| 开发者 | Nous Research |
| GitHub | NousResearch/hermes-agent |
| Stars | 43,700+ |
| License | MIT |
| 版本 | v0.8.0 |
| 语言 | Python |

### 2.2 核心架构：自我改进循环

Hermes Agent 的核心创新是 **Learning Loop（学习循环）**——Agent 能在运行中自主创建新技能：

```
用户输入
  ↓
┌─────────────────────────────────────┐
│          Hermes Core Loop           │
│                                     │
│  1. 感知 → 理解任务                 │
│  2. 检索 → 搜索记忆和技能           │
│  3. 规划 → 分解步骤                 │
│  4. 执行 → 调用工具/创建新技能      │
│  5. 反思 → 评估结果                 │
│  6. 学习 → 更新程序性记忆           │
│  7. 存储 → 情景记忆归档             │
│                                     │
│  ┌─────────────────────────────┐   │
│  │   Skill Factory             │   │
│  │   Agent 可自主创建新工具/技能│   │
│  │   写入 Procedural Memory    │   │
│  └─────────────────────────────┘   │
└─────────────────────────────────────┘
  ↓
输出 + 学习结果
```

### 2.3 记忆系统

Hermes 的记忆系统是其最大亮点——**三种记忆类型**，覆盖认知全过程：

| 记忆类型 | 存储内容 | 实现方式 | 特点 |
|----------|----------|----------|------|
| **Episodic（情景）** | 具体交互事件 | FTS5 全文搜索 | 按 session 组织，可回溯 |
| **Semantic（语义）** | 提取的知识/事实 | 向量 + 关键词 | 长期知识积累 |
| **Procedural（程序性）** | Agent 自创的技能/工具 | Python 代码 | 可执行、可复用 |

**Session Search（会话搜索）：**
- 基于 SQLite FTS5 的全文搜索引擎
- 支持跨会话检索历史交互
- Agent 可自主查询过往经验

### 2.4 工具与技能系统

| 维度 | 详情 |
|------|------|
| 内置工具 | 40+ 种（文件/网络/代码/系统/浏览器/...） |
| 技能创建 | Agent 自主创建，写入 Procedural Memory |
| MCP 集成 | 支持 Model Context Protocol 连接外部工具 |
| Cron 调度 | 内置定时任务，Agent 可设置定期执行 |
| 工具热加载 | 运行时动态添加新技能 |

### 2.5 多终端 + 消息网关

Hermes 的另一大特色是 **6 种终端后端 + 消息网关**：

```
                    ┌─────────────────┐
                    │   Hermes Core   │
                    └────────┬────────┘
                             │
              ┌──────────────┼──────────────┐
              │              │              │
     ┌────────┴──┐  ┌───────┴───────┐  ┌───┴────────┐
     │ Terminal   │  │ Web/TUI      │  │ Messaging  │
     │ Backends   │  │              │  │ Gateway    │
     │            │  │              │  │            │
     │ • Rich     │  │ • Web UI     │  │ • Telegram │
     │ • Plain    │  │ • Textual    │  │ • Discord  │
     │ • Simple   │  │              │  │ • Slack    │
     │ • Prompt   │  │              │  │ • WhatsApp │
     │ • IPython  │  │              │  │ • Signal   │
     │ • Custom   │  │              │  │            │
     └────────────┘  └──────────────┘  └────────────┘
```

### 2.6 Honcho — 用户建模引擎

Hermes 集成了 **Honcho** 辩证式用户建模系统：

- 为每个用户建立独立的认知模型
- 基于对话历史推断用户偏好、技能水平、沟通风格
- 支持" dialectic"（辩证）推理——多角度理解用户意图
- 随交互深化持续优化用户画像

### 2.7 LLM 支持

- 通过 **OpenRouter** 支持 200+ 模型
- 不绑定单一 LLM 提供商
- 支持模型切换、A/B 测试

---

## 三、四平台对比矩阵

### 3.1 定位与技术栈

| 项目 | 定位 | 技术栈 | 开源 | 成熟度 |
|------|------|--------|------|--------|
| **Agent Harness（理论）** | 架构模式/方法论 | 语言无关 | N/A | 理论框架 |
| **Hermes Agent** | 自改进 Agent 框架 | Python | MIT, 43.7k stars | v0.8.0 |
| **NextCrab** | 全栈 Agent 平台 | Rust + React | 企业内部 | v0.1-0.2 |
| **CkyClaw** | Agent 运行时 + 管理平台 | Python + React | 内部 | v0.1.0 |

### 3.2 Harness 五层架构契合度

| Harness 层 | Agent Harness 理论 | Hermes Agent | NextCrab | CkyClaw |
|-------------|-------------------|--------------|----------|---------|
| **Execution Runtime** | 三 Agent 分离 + 迭代循环 | Core Loop + Skill Factory | engine_loop + CancellationToken | Runner + asyncio TaskGroup |
| **Context System** | 5 级 Tier 压缩 + Cache-First | FTS5 Session Search + Procedural Memory | 5 层压缩管道 + Deferred Tool | HistoryTrimmer (2 策略) |
| **Capability Surface** | MCP + Skills + Subagents | 40+ 工具 + 自创技能 + MCP + Cron | 38 内置 + ToolGateway + Skill 市场 | FunctionTool + ToolSearchTool |
| **Governance Layer** | Checkpoints + Guardrails + Human Injection | 基础（靠 Prompt 约束） | ConfirmPolicy + SecurityLevel + PermissionEngine | 三阶段护栏 + 7 种内置 + ApprovalHandler |
| **Surface/Protocol** | MCP/ACP/A2A 三协议 | 6 Terminal + 5 Messaging Gateway | CrabBoard (60+ 组件) | React SPA + ProLayout |

### 3.3 记忆系统对比

| 维度 | Hermes Agent | NextCrab | CkyClaw |
|------|-------------|----------|---------|
| 记忆类型 | Episodic + Semantic + Procedural | Episodic + Semantic + Procedural | 单一 MemoryEntry |
| 自创技能 | Skill Factory（核心特色） | Skill marketplace | 无 |
| 搜索能力 | FTS5 全文 + 向量 | 文本 + 向量 | 无 |
| 用户建模 | Honcho 辩证式 | Soul VAD + 成长等级 | 无 |
| 成长模型 | 隐式（技能累积） | Newborn → Sage 6 级 | 无 |
| 遗忘机制 | 无（FTS5 全存） | 每日衰减 0.98 | 指数衰减 |

### 3.4 多 Agent 协作对比

| 维度 | Agent Harness | Hermes | NextCrab | CkyClaw |
|------|-------------|--------|----------|---------|
| 协作模式 | Planning→Gen→Eval 三 Agent | 单 Agent + 自扩展 | Brain Coordinator + Mailbox | Sequential/Parallel/Coordinator |
| Agent 间通信 | 结构化 JSON 特性列表 | 无（单 Agent） | DB-backed Mailbox | Handoff + InputFilter |
| 反馈循环 | 5-15 轮 Eval 反馈 | 反思→学习循环 | 自适应策略 | 无内置 |
| 隔离 | 每个 Agent 独立上下文 | 无 | process/worktree/remote | 无 |

### 3.5 可观测性对比

| 维度 | Hermes | NextCrab | CkyClaw |
|------|--------|----------|---------|
| 核心机制 | 内置 logging | Event Journal (25+ 事件类型) | Trace/Span (6 类型) |
| 事件重放 | 无 | DB 持久化 + 按 session 重放 | 无 |
| 成本追踪 | per-model token 统计 | CostSubscriber | TokenUsage per span |
| 审计 | 基础 | AuditProjector | 无专用审计 |

---

## 四、四平台各有千秋的优势域

```
Agent Harness          Hermes Agent          NextCrab             CkyClaw
━━━━━━━━━━━━━━        ━━━━━━━━━━━━━━        ━━━━━━━━━━━━         ━━━━━━━━
• 理论完整度 ●●●●●    • 自创技能 ●●●●●     • 性能 ●●●●●         • 开发效率 ●●●●●
• 工程方法论 ●●●●●    • 记忆系统 ●●●●●     • 上下文管理 ●●●●●   • 生态兼容 ●●●●●
• 上下文工程 ●●●●●    • 多终端 ●●●●●       • 安全治理 ●●●●●     • 护栏丰富度 ●●●●
• 三Agent分离 ●●●●    • 用户建模 ●●●●●     • 多Agent协作 ●●●●●  • Python友好 ●●●●●
• Cache-First ●●●●●  • 开源生态 ●●●●●     • 前端成熟度 ●●●●●   • 快速迭代 ●●●●●
                      • LLM覆盖 ●●●●●      • 可观测性 ●●●●●
```

---

## 五、对 CkyClaw 的启示与行动建议

### 5.1 短期可落地（1-2 周）

| # | 方向 | 来源 | 具体行动 |
|---|------|------|----------|
| 1 | **5 层上下文压缩** | Harness + NextCrab | 替换简单 HistoryTrimmer，实现 Tier 0-4 渐进压缩 |
| 2 | **Artifact Store** | Harness | 大型工具输出外部化到文件系统/S3，只返回引用 ID |
| 3 | **Cache-First Prompt** | Harness | 固定 System Prompt 前缀 + 追加式历史，不动态改写 |
| 4 | **结构化 Handoff** | Harness | 跨会话交接标准化：状态 + 变更 + 已验证 + 下一步 |

### 5.2 中期增强（1-2 月）

| # | 方向 | 来源 | 具体行动 |
|---|------|------|----------|
| 5 | **Learning Loop** | Hermes | Agent 运行后反思→提取模式→存入 Procedural Memory |
| 6 | **Circuit Breaker** | NextCrab | LLM 多 provider 容错：熔断 + 降级 + 重试 |
| 7 | **ToolGateway 中间件** | NextCrab | Auth/Cache/LoopGuard 作为工具执行中间件管道 |
| 8 | **Event Journal** | NextCrab | 事件溯源：所有 Agent 操作持久化，支持审计和重放 |

### 5.3 长期演进（3+ 月）

| # | 方向 | 来源 | 具体行动 |
|---|------|------|----------|
| 9 | **三 Agent Harness** | Anthropic | Planning → Generation → Evaluation 分离架构 |
| 10 | **Skill Factory** | Hermes | Agent 自主创建工具/技能，存入可复用知识库 |
| 11 | **Soul 成长模型** | NextCrab | 三类记忆 + 成熟度等级 + 情绪 + 目标系统 |
| 12 | **多终端 + 消息网关** | Hermes | Telegram/Discord/Slack/微信/钉钉接入 |

### 5.4 独特竞争力（CkyClaw 应保持的优势）

1. **Python 生态 + LiteLLM 多厂商** — Hermes 虽支持 OpenRouter 但不直接集成；CkyClaw 的 LiteLLM 原生支持更灵活
2. **三阶段护栏体系** — Input/Output/Tool 三阶段 + 7 种内置护栏，比 Hermes 的 Prompt 约束更可靠
3. **ApprovalHandler 审批模式** — FULL_AUTO/SUGGEST/AUTO_EDIT 三模式，比 NextCrab 的 ConfirmPolicy 更清晰
4. **声明式 Agent 定义** — `@dataclass` + `InstructionsType`，比 Hermes 和 NextCrab 更简洁

---

## 六、关键洞察

1. **Harness 不是可选配件，是必须品。** 0.95^20 = 36% 的可靠性问题在所有 Agent 系统中都存在。CkyClaw 的 Guardrails + Approval + Handoff 已经是 Harness 实现，但缺少 **Checkpoint（检查点）** 和 **Replay（重放）** 能力。

2. **Hermes 的自改进循环是差异化方向。** 当前所有框架中，只有 Hermes 让 Agent 自主创建技能。这是 Agent 从"工具使用者"到"工具创造者"的关键跃迁。

3. **Anthropic 的三 Agent 分离是工程最佳实践。** Planning/Generation/Evaluation 分离使每个 Agent 的上下文更小、目标更明确、错误更容易定位。

4. **记忆系统是下一竞争焦点。** NextCrab 的 Soul 和 Hermes 的三种记忆都远超简单的 key-value 存储。CkyClaw 需要从"简单记忆"升级到"认知成长模型"。

5. **Cache-First 是 2026 最被低估的技术。** 上下文缓存直接降低成本和延迟。CkyClaw 应优先实现固定前缀 + 追加式历史模式。

---

Sources:
- https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents — Anthropic Engineering Blog
- https://www.infoq.com/news/2025/06/anthropic-three-agent-harness/ — InfoQ: Anthropic 三 Agent Harness
- https://github.com/NousResearch/hermes-agent — NousResearch/hermes-agent GitHub
- https://www.linkedin.com/pulse/agent-harness-architecture-dominate-2026-bassel-haidar-sczfe — LinkedIn (Bassel Haidar)
- https://gist.github.com/amazingvince/52158d00fb8b3ba1b8476bc62bb562e3 — GitHub Gist (Agent Harness Architecture)
