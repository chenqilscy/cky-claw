# AI Agent 系统竞品架构分析

> 调研日期：2026-04-02 · 重写日期：2026-04-05
> 版本：v2.0 — 双维度重构
>
> 分析范围覆盖两大类别共 8 个系统，CkyClaw 在两个维度中分别定位。

---

## 核心洞察

AI Agent 生态中存在两类本质不同的系统，不能混为一谈：

| 维度 | 定义 | 用户 | 交互方式 | 代表 |
|------|------|------|---------|------|
| **AI Coding Agent（终端工具类）** | 面向开发者的终端编码助手 | 个人开发者 | CLI / IDE | Claude Code, Codex CLI, DeerFlow |
| **Agent 开发框架（SDK 类）** | 用于构建 Agent 应用的编程框架 | 平台开发者 | Python API | Agents SDK, LangChain, AutoGen, CrewAI |

**CkyClaw Framework** 属于维度二（Agent SDK），在此之上构建了企业级 Agent 管理平台（CkyClaw Backend + Frontend）。

---

# 维度一：AI Coding Agent（终端工具类）

## 1.1 Claude Code

| 维度 | 设计 |
|------|------|
| 开发者 | Anthropic |
| 执行模型 | 单 Agent 循环：LLM 推理 → Tool 调用 → 结果返回 → 继续推理 |
| 子 Agent | 可并行 spawn 多个 subagent，各自有独立上下文、工具、终止条件 |
| 工具扩展 | MCP（STDIO + HTTP）+ 内置工具（文件读写、bash、搜索） |
| 知识注入 | AGENTS.md（全局 / 项目 / 子目录三级）+ Plugins 系统 |
| 沙箱 | macOS Seatbelt / Linux Docker，网络隔离 |
| SDK | 提供编程接口可嵌入其他应用 |
| 模型绑定 | 仅 Anthropic Claude 系列 |
| 关键特点 | 插件生态成熟；无自定义 Agent 类型定义；subagent 并行度高 |

**架构亮点**：AGENTS.md 三级指令继承（全局→项目→子目录），简洁高效的知识注入机制。

## 1.2 OpenAI Codex CLI

| 维度 | 设计 |
|------|------|
| 开发者 | OpenAI |
| 执行模型 | 单 Agent 循环，三级审批模式（suggest / auto-edit / full-auto） |
| 子 Agent | 支持**自定义 Agent**（TOML 配置），独立指定 model、sandbox、MCP、instructions |
| 内置 Agent | `default`（通用）、`worker`（执行）、`explorer`（探索，只读） |
| 工具扩展 | MCP（STDIO + Streamable HTTP + OAuth） |
| 知识注入 | AGENTS.md + **Skills 系统**（SKILL.md + scripts/ + references/，可分发为 Plugin） |
| 沙箱 | macOS Seatbelt / Linux bubblewrap + Landlock / Windows 受限令牌 |
| 批量处理 | `spawn_agents_on_csv` — 批量任务分发，每行一个 worker |
| 配置 | `config.toml` 统一配置 |
| 模型绑定 | 默认 OpenAI，支持多 Provider（config.toml） |
| 关键特点 | 自定义 Agent 最灵活；Skills 生态可分发为 Plugin；Rust 重写性能优异 |

**架构亮点**：
- 声明式 Agent 配置（TOML），每个自定义 Agent 可独立控制 model、sandbox、instructions
- Skills 系统 = 可分发的知识包（SKILL.md + scripts/ + references/）
- Subagent 管理：`max_threads`（并发数）、`max_depth`（嵌套深度）、`job_max_runtime_seconds`（超时）

## 1.3 DeerFlow

| 维度 | 设计 |
|------|------|
| 开发者 | 社区 |
| 执行模型 | Lead Agent 单例 + 2 个内置 Sub-Agent（general-purpose、bash） |
| 自定义 Agent | 只能创建 config 包（config.yaml + SOUL.md），注入 Lead Agent 行为 |
| 工具扩展 | MCP + config.yaml 中的 Python 工具模块 |
| 知识注入 | Skills（SKILL.md，Prompt 注入） |
| Middleware | 12 个内置 Middleware（不可自定义） |
| 模型绑定 | 支持多模型 |
| 关键限制 | 不能自定义 Sub-Agent；Lead Agent 逻辑写死；文件系统存储；无多租户 |

**架构局限**：封闭的 Lead Agent 架构限制了编排灵活性，更适合简单的研究型场景。

## 1.4 Coding Agent 横向对比

| 能力 | Claude Code | Codex CLI | DeerFlow |
|------|:-----------:|:---------:|:--------:|
| 自定义 Agent 类型 | ❌ | ✅ TOML | ❌ |
| Subagent 并行 | ✅ spawn | ✅ spawn | ❌ |
| 自定义编排拓扑 | ❌ | ❌ | ❌ |
| MCP 集成 | ✅ | ✅ + OAuth | ✅ |
| Skills / 知识注入 | AGENTS.md | SKILL.md + Plugin | SOUL.md |
| 沙箱隔离 | ✅ OS 级 | ✅ OS 级 | ✅ Docker |
| 内置追踪 | ❌ | ❌ | ❌ |
| 会话记忆 | 有限（上下文内） | 有限 | memory.json |
| 模型无关 | ❌ Claude only | ⚠️ 可配置 | ✅ |
| Human-in-loop | 审批模式 | 审批模式 | ❌ |
| 代码重写 | — | Rust 重写 | Python |

**共同模式**：所有 Coding Agent 都采用「单主 Agent + 工具调用循环」模型，核心差异在于 Agent 自定义和知识注入的开放度。

---

# 维度二：Agent 开发框架（SDK 类）

## 2.1 OpenAI Agents SDK

| 维度 | 设计 |
|------|------|
| 开发者 | OpenAI |
| 语言 | Python（主）+ Node.js |
| 执行模型 | `Runner.run()` 驱动 Agent 循环，内置 tool 调用 + 结果回传 |
| Agent 定义 | `Agent` 类（instructions + tools + handoffs + output_type） |
| 多 Agent 编排 | **Handoffs**（控制权移交）+ **Agents-as-Tools**（Agent 作为工具调用） |
| 工具系统 | Python 函数自动转 Tool（Pydantic Schema）+ MCP Server + Hosted Tool |
| Guardrails | Input / Output 护栏，与 Agent 执行并行运行 |
| 会话管理 | Sessions（SQLAlchemy / SQLite / Redis / Dapr） |
| 链路追踪 | 内置 Tracing，Span 级可视化 |
| 人工介入 | 内置 Human-in-the-loop 机制 |
| 模型支持 | 提供商无关（OpenAI / LiteLLM / any-llm 支持 100+ 模型） |
| 关键特点 | 极轻量（few primitives）；Python 原生编排；唯一原生支持 Handoff 编排 |

**架构亮点**：
- 「少概念多组合」设计哲学：Agent + Tool + Handoff + Guardrail + Tracing 五个核心概念覆盖绝大多数场景
- Handoff 是真正的编排原语，不是简单的消息传递
- CkyClaw Framework 的 Agent/Runner/Handoff/Guardrail/Tracing 设计理念直接对标

## 2.2 LangChain / LangGraph

| 维度 | 设计 |
|------|------|
| 开发者 | LangChain Inc. |
| 语言 | Python + TypeScript |
| 执行模型 | LangGraph：有限状态机（StateGraph），节点 = 函数，边 = 条件路由 |
| Agent 定义 | 无统一 Agent 类，通过 Chain / Graph 组合 |
| 多 Agent 编排 | LangGraph 状态图 + 条件边；支持循环、分支、并行 |
| 工具系统 | `@tool` 装饰器 + Pydantic Schema；工具种类极多 |
| 会话管理 | LangGraph Checkpointer（内存 / SQLite / Postgres / Redis） |
| 链路追踪 | LangSmith（商业 SaaS） |
| 人工介入 | LangGraph `interrupt()` 断点 + `Command(resume=...)` 恢复 |
| 模型支持 | 100+ 模型（langchain-community 集成） |
| 生态规模 | **最大**：86k+ GitHub Stars；集成最多（700+ 工具包） |
| 关键痛点 | 抽象层过多（Chain → LCEL → LangGraph）；版本频繁 breaking；调试困难 |

**架构特点**：
- LangGraph 是目前最灵活的编排引擎（有限状态机 + 条件路由），但学习曲线陡峭
- LangSmith 追踪是 SaaS 商业产品，无法本地化部署
- 生态最大但过于臃肿，核心与社区包边界模糊

## 2.3 AutoGen

| 维度 | 设计 |
|------|------|
| 开发者 | Microsoft |
| 语言 | Python + .NET |
| 执行模型 | 消息驱动的多 Agent 对话（AgentChat），Agent 之间通过消息交互 |
| Agent 定义 | `AssistantAgent` / `UserProxyAgent` / `SocietyOfMindAgent` |
| 多 Agent 编排 | `RoundRobinGroupChat` / `SelectorGroupChat` / `Swarm`（Handoff） |
| 工具系统 | Python 函数注册 + MCP 扩展 |
| 会话管理 | Teams 级状态保存/恢复 |
| 链路追踪 | AutoGen Studio（调试 UI） |
| 人工介入 | `UserProxyAgent` 代理人类输入 |
| 模型支持 | OpenAI / Azure / 本地模型 |
| 关键特点 | 微软背景；多 Agent 对话模式成熟；v0.4 大重写（从 pyautogen 到 autogen-agentchat） |

**架构特点**：
- 「对话即编排」：Agent 之间通过消息协作，GroupChat 自动调度发言顺序
- 适合模拟人类团队协作的场景（brainstorm、debate、review）
- v0.4 大重写导致社区分裂（AG2 分支），API 稳定性存疑

## 2.4 CrewAI

| 维度 | 设计 |
|------|------|
| 开发者 | CrewAI Inc. |
| 语言 | Python |
| 执行模型 | Crew（团队）协调多个 Agent 执行 Task 列表 |
| Agent 定义 | `Agent(role, goal, backstory, tools)` |
| 多 Agent 编排 | 顺序执行（sequential）/ 层级执行（hierarchical，manager 分配） |
| 工具系统 | `@tool` 装饰器 + crewai-tools 预建工具集 |
| 会话管理 | 短期/长期/实体记忆（RAG-based） |
| 链路追踪 | 内置基础日志 |
| 人工介入 | `human_input=True` |
| 模型支持 | LiteLLM 支持 100+ 模型 |
| 关键特点 | 低代码上手快；角色扮演（role-playing）驱动 |

**架构特点**：
- 「角色扮演」：每个 Agent 有 role + goal + backstory，用人格化方式驱动任务分配
- Crew → Task → Agent 三层模型非常直观，适合快速原型
- 企业级能力弱：无 RBAC、无审计、无多租户、无细粒度权限

## 2.5 Agent SDK 横向对比

| 能力 | Agents SDK | LangChain/Graph | AutoGen | CrewAI | **CkyClaw Framework** |
|------|:----------:|:---------------:|:-------:|:------:|:---------------------:|
| Agent 定义 | ✅ 声明式 | ⚠️ 组合式 | ✅ 类继承 | ✅ 角色化 | ✅ 声明式 dataclass |
| 编排模式 | Handoff + as-Tool | 状态机 + 条件边 | GroupChat | Sequential/Hierarchical | **Handoff + as-Tool + Team** |
| Guardrails | ✅ Input/Output | ❌ 需自建 | ❌ | ❌ | **✅ Input/Output/Tool 三级** |
| 工具系统 | 函数 + MCP | 函数 + 700+ 集成 | 函数 + MCP | 函数 + crewai-tools | 函数 + MCP + ToolGroup + ToolRegistry |
| 结构化输出 | ✅ output_type | ✅ with_structured_output | ⚠️ | ⚠️ | ✅ output_type |
| 链路追踪 | ✅ 内置 | ⚠️ LangSmith(SaaS) | ⚠️ Studio | ❌ 基础日志 | **✅ 内置 5 类 Span** |
| 会话持久化 | ✅ Sessions | ✅ Checkpointer | ✅ 状态保存 | ⚠️ RAG 记忆 | **✅ Sessions + HistoryTrimmer** |
| Memory 系统 | ❌ | ⚠️ 第三方 | ⚠️ 基础 | ✅ 多类型 | **✅ 多类型持久化** |
| 人工介入 | ✅ HITL | ✅ interrupt | ✅ UserProxy | ⚠️ human_input | **✅ 三级审批 + DB 持久化** |
| 模型无关 | ✅ 100+ | ✅ 100+ | ⚠️ 有限 | ✅ LiteLLM | **✅ LiteLLM 10+ 厂商** |
| Workflow DAG | ❌ | ✅ StateGraph | ❌ | ❌ | **✅ DAG 引擎 + ReactFlow 编辑器** |
| 国产模型原生支持 | ❌ | ⚠️ 社区包 | ❌ | ⚠️ LiteLLM | **✅ 通义/文心/讯飞/混元/DeepSeek** |
| 企业级能力 | ❌ | ❌ | ❌ | ❌ | **✅ RBAC + 多租户 + 审计** |
| API 轻量度 | **最轻** | 最重 | 中等 | 轻 | 轻（对标 Agents SDK） |

---

# 三、CkyClaw 定位分析

## 3.1 CkyClaw 与 Coding Agent 的关系

CkyClaw **不是** Coding Agent，但 Coding Agent 的优秀设计被广泛借鉴：

| 来源 | 借鉴设计 | CkyClaw 中的实现 |
|------|---------|----------------|
| Claude Code | AGENTS.md 三级指令 | Agent.instructions + Dynamic Instructions |
| Codex CLI | 声明式 Agent 配置（TOML） | Agent YAML/JSON 导入导出 |
| Codex CLI | Skills 系统 | Skill 技能系统（SKILL.md 映射） |
| Codex CLI | 三级审批模式 | ApprovalMode（suggest / auto-edit / full-auto） |
| Codex CLI | Subagent 管理（并发/深度/超时） | max_turns + max_tool_concurrency + Tool 并发限流 |
| 所有竞品 | MCP 工具标准 | MCP 客户端（stdio / sse / http 三传输） |

## 3.2 CkyClaw 与 Agent SDK 的关系

CkyClaw Framework 是 Agent SDK 维度的竞品，设计理念直接对标 OpenAI Agents SDK：

| Agents SDK 概念 | CkyClaw Framework 实现 | 增强点 |
|----------------|----------------------|--------|
| `Agent` | `Agent` dataclass | + Agent-as-Tool + 条件启用 + 国际化 |
| `Runner.run()` | `Runner.run() / run_sync() / run_streamed()` | + max_turns + 重试退避 + Lifecycle Hooks |
| `Handoff` | `Handoff` + `InputFilter` | + 多级递归解析 + 循环检测 + ReactFlow 可视化 |
| `Guardrail` | `InputGuardrail / OutputGuardrail / ToolGuardrail` | + Tool 级护栏 + Regex/Keyword/LLM 三引擎 |
| `Tracing` | `Trace / Span / TraceProcessor` | + 5 类 Span + Postgres 持久化 + Waterfall 可视化 |
| `Session` | `Session / SessionBackend` | + HistoryTrimmer + Token 预算裁剪 |
| — | `Memory` | ✅ 独有：跨会话记忆持久化 |
| — | `Team / TeamProtocol` | ✅ 独有：Sequential/Parallel/Coordinator 三协议 |
| — | `Workflow / DAG` | ✅ 独有：DAG 工作流引擎 + 可视化编辑器 |
| — | `Sandbox` | ✅ 独有：代码执行沙箱隔离 |
| — | `Skill` | ✅ 独有：可复用知识包系统 |

## 3.3 CkyClaw 的独特价值（平台层）

在 Agent SDK 之上，CkyClaw 构建了**业界唯一的企业级 Agent 管理平台**：

| 能力 | 竞品 SDK 共同缺失 | CkyClaw 平台实现 |
|------|:--:|-------------|
| **Web 管理界面** | ❌ 均为代码 API | ✅ 25 页 React SPA + ProLayout |
| **多租户隔离** | ❌ | ✅ Organization + get_org_id 租户依赖 |
| **RBAC 权限** | ❌ | ✅ Role + Permission + require_permission |
| **操作审计** | ❌ | ✅ AuditLog + Middleware 自动采集 |
| **Agent 版本管理** | ❌ | ✅ 自动快照 + 对比 + 回滚 |
| **执行可视化** | ❌ | ✅ SpanWaterfall + ReactFlow 编排器 |
| **审批工作流 UI** | ❌ | ✅ 审批队列 + WebSocket 实时推送 |
| **APM 监控** | ❌ | ✅ 聚合统计 + ECharts + AlertRule 告警 |
| **Token 审计** | ❌ | ✅ 自动采集 + 多维统计（Agent/Model/User） |
| **IM 渠道接入** | ❌ | ✅ IMChannel + Webhook + HMAC 验签 |
| **配置热更新** | ❌ | ✅ ConfigChangeLog + 回滚 + 审计 |
| **灾备策略** | ❌ | ✅ 自动备份 + 恢复验证 |

## 3.4 自研 vs 直接依赖 Agents SDK

CkyClaw Framework 选择自研而非直接封装 OpenAI Agents SDK 的决策分析：

| 维度 | 直接依赖 Agents SDK | 自研 CkyClaw Framework |
|------|:---:|:---:|
| **多 Provider 支持** | ❌ 默认绑定 OpenAI | ✅ LiteLLM 适配 10+ 厂商 |
| **国产模型适配** | ❌ 无原生支持 | ✅ 通义/文心/讯飞/混元/DeepSeek 等 |
| **数据主权** | ⚠️ 依赖 OpenAI 基础设施 | ✅ 完全本地化部署 |
| **定制深度** | ⚠️ 受 SDK API 限制 | ✅ 完全掌控 Runner/Tracing/Session |
| **企业级扩展** | ❌ 无内置 RBAC/多租户/审计 | ✅ 企业能力深度集成 |
| **依赖风险** | ⚠️ SDK 版本更新可能 breaking | ✅ 自主演进节奏 |
| **开发成本** | ✅ 开箱即用 | ⚠️ 需自行实现核心逻辑 |

**决策结论**：对于面向中国企业的 AI Agent 平台，多 Provider 适配（尤其国产模型）、数据本地化、深度定制能力是刚需。自研框架在设计理念上与 Agents SDK 对齐，同时获得了完全的架构自主权。

**演进方向**：可考虑实现 Agents SDK 兼容层（Adapter），允许用户用 Agents SDK 的 Agent 定义直接在 CkyClaw 上运行，降低迁移成本。

---

# 四、竞品生态数据

> 数据截至 2026-04

| 项目 | GitHub Stars | 语言 | 许可证 | 维护活跃度 |
|------|:-----------:|------|--------|:--------:|
| Claude Code | N/A（商业） | TypeScript | 专有 | 极高 |
| Codex CLI | 71k+ | Rust 95% | Apache-2.0 | 极高 |
| DeerFlow | 8k+ | Python | Apache-2.0 | 中 |
| OpenAI Agents SDK | 18k+ | Python + Node | MIT | 高 |
| LangChain | 86k+ | Python + TS | MIT | 极高 |
| AutoGen | 40k+ | Python + .NET | MIT → CC-BY-4.0 | 高（v0.4 重写中） |
| CrewAI | 28k+ | Python | MIT | 高 |

---

# 五、总结

## 5.1 行业趋势

1. **MCP 成为标准**：所有主流系统均采用 MCP 作为工具扩展协议
2. **Handoff 成为共识**：Agent 间协作从消息传递演进为明确的控制权移交
3. **可观测性前移**：Tracing 不再是「做完了再补」，而是框架内置一等公民
4. **审批模式收敛**：suggest / auto-edit / full-auto 三级模式被 Codex CLI 和 Agents SDK 共同验证
5. **状态机编排兴起**：LangGraph 验证了 DAG/状态机编排的价值，但 API 复杂度过高

## 5.2 CkyClaw 竞争优势

| 优势维度 | 说明 |
|---------|------|
| **全栈平台** | 业界唯一从 Agent SDK → Backend API → Web UI → IM 接入的全栈方案 |
| **国产模型优先** | 原生支持通义千问、文心一言、讯飞星火、混元、DeepSeek 等国产大模型 |
| **数据主权** | 完全本地化部署，数据不出企业网络 |
| **企业级治理** | RBAC + 多租户 + 审计日志 + Token 审计 + 审批工作流 |
| **可观测性深度** | 5 类 Span + Waterfall 可视化 + APM 仪表盘 + 告警引擎 |
| **编排灵活性** | Handoff + Agent-as-Tool + Team 协作 + DAG 工作流四种编排模式 |
| **轻量 API** | 对标 Agents SDK 的「少概念多组合」设计理念 |

## 5.3 待演进方向

1. **Agents SDK 兼容层**：允许 Agents SDK 定义的 Agent 直接在 CkyClaw 上运行
2. **多渠道接入**：企微/钉钉/飞书具体平台 ChannelAdapter 实现
3. **OAuth SSO**：GitHub / 企微 / 钉钉扫码登录
4. **Agent Marketplace**：模板市场 + 社区共享 + 版本管理
5. **边缘部署**：轻量化 Runner 独立部署，适配边缘计算场景
