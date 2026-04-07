# CkyClaw PRD v2.0

## 文档信息

| 字段 | 内容 |
|------|------|
| 版本 | v2.0.9 |
| 日期 | 2026-04-02 |
| 状态 | 进行中 |
| 维护人 | CkyClaw Team |

## 目录
1. [产品概述](#一产品概述)
2. [核心概念](#二核心概念)
3. [技术架构](#三技术架构)
4. [Agent 执行模式](#四agent-执行模式)
5. [工具系统与 MCP](#五工具系统与-mcp)
6. [任务执行可视化](#六任务执行可视化)
7. [IM 渠道接入](#七im-渠道接入)
8. [人工监督机制](#八人工监督机制)
9. [APM 与可观测性](#九apm-与可观测性)
10. [前端与用户界面](#十前端与用户界面)
11. [API 设计](#十一api-设计)
12. [数据模型](#十二数据模型)
13. [用户系统与安全管理](#十三用户系统与安全管理)
14. [部署与运维](#十四部署与运维)
15. [非功能性需求](#十五非功能性需求)
- [附录 A：术语表](#附录-a术语表)
- [附录 B：版本历史](#附录-b版本历史)
- [附录 C：MVP 范围与里程碑计划](#附录-cmvp-范围与里程碑计划)

---

## 一、产品概述

### 1.1 产品定位

CkyClaw 是基于自研 **CkyClaw Framework** 构建的 AI Agent 管理与运行平台。CkyClaw Framework汲取了 Claude Code、OpenAI Codex CLI、OpenAI Agents SDK、DeerFlow 等业界领先方案的优秀设计，提供一套开放、可扩展的 Agent 运行时基础设施。CkyClaw 在此基础上构建企业级的 Agent 配置管理、多模式编排、执行可视化、人工监督、多渠道接入和 APM 监控等上层能力。**分层定位：**

| 层级 | 说明 |
|------|------|
| **CkyClaw Framework（框架层）** | 自研 Agent 运行时基础设施。提供 Agent 定义、执行引擎（Runner）、编排（Handoff / Agent-as-Tool）、工具系统、MCP 集成、Session 管理、Guardrails、Tracing 等核心原语。未来可独立开源。 |
| **CkyClaw 应用层** | 基于 CkyClaw Framework 构建的企业级应用。提供 Web UI、多租户管理、RBAC 权限、人工监督、APM 仪表盘、IM 渠道接入等业务功能。 |

### 1.2 核心价值

| 价值点 | 说明 |
|--------|------|
| **自主可控** | 自研框架，不受第三方框架封闭性限制，核心逻辑完全可定制 |
| **灵活编排** | 支持 Handoff（控制转移）和 Agent-as-Tool（嵌套调用）两种编排模式，可自由组合 |
| **执行可视化** | 以流程图形式展示 Agent 编排与执行过程，实时查看各节点状态和日志 |
| **安全可控** | Guardrails 输入/输出护栏 + 人工监督 + 审批工作流，确保 AI 行为安全 |
| **可观测性** | 内建 Tracing 链路追踪，完善的监控、日志、告警体系 |
| **开放生态** | MCP 标准协议接入工具服务；Skills 知识注入；多 LLM 提供商支持 |

### 1.3 设计理念

CkyClaw 的设计汲取了以下竞品的最佳实践：

| 来源 | 借鉴要素 |
|------|---------|
| **OpenAI Agents SDK** | Agent + Runner 执行模型、Handoff 与 Agent-as-Tool 两种编排模式、Guardrails 护栏、Session 会话管理、Tracing 链路追踪 |
| **OpenAI Codex CLI** | 声明式 Agent 配置（YAML/TOML）、Skills 系统（SKILL.md + 可安装包）、三级审批模式（suggest / auto-edit / full-auto） |
| **Claude Code** | AGENTS.md 多级指令体系、Subagent 独立上下文与工具集、沙箱隔离执行 |
| **DeerFlow** | SOUL.md 人格定义、MCP 标准集成、Tool Groups 工具分组、文件系统存储模式 |

### 1.4 目标用户

| 用户类型 | 使用场景 |
|----------|----------|
| 企业 IT 团队 | 构建自动化业务流程 |
| 数据分析师 | 数据处理流水线 |
| 运维团队 | 智能运维场景 |
| 开发者 | AI 应用开发 |

### 1.5 核心功能矩阵

| 功能 | 说明 | 优先级 |
|------|------|--------|
| Agent 管理 | 声明式创建/配置 Agent，管理 Instructions（SOUL.md） | P0 |
| Agent 编排 | 支持 Handoff 和 Agent-as-Tool 两种编排模式 | P0 |
| 对话交互 | 通过 Web 或 IM 渠道与 Agent 对话 | P0 |
| 任务执行可视化 | 以流程图形式展示 Agent 编排与执行过程 | P0 |
| 人工监督 | 实时监控、干预、接管 Agent 执行；审批工作流 | P0 |
| 工具系统 / MCP | Function Calling + MCP 标准协议 | P1 |
| Guardrails 护栏 | 输入/输出/工具调用安全验证 | P1 |
| APM 监控 | 链路追踪、性能监控、成本监控 | P1 |
| 多渠道接入 | 企业微信、钉钉等 IM 渠道 | P1 |---

## 二、核心概念

### 2.1 Agent（智能体）

Agent 是 CkyClaw Framework 中的核心执行单元。每个 Agent 是一个由 **Instructions + Model + Tools + Handoffs** 组成的声明式定义。**Agent 核心属性：**

| 属性 | 说明 |
|------|------|
| name | Agent 唯一标识（小写字母、数字、连字符） |
| description | Agent 功能描述（同时用于 Handoff/as_tool 时的 LLM 提示） |
| instructions | Agent 行为指令，即 SOUL.md 内容（支持动态函数生成） |
| model | 使用的 LLM 模型（为空时使用默认模型） |
| tools | Agent 可调用的工具列表（Function Tool + MCP Tool） |
| tool_groups | 工具组白名单（按组批量加载工具） |
| handoffs | Agent 可移交的目标 Agent 列表 |
| guardrails | 输入/输出护栏列表 |
| output_type | 结构化输出类型定义（可选） |
| model_settings | 模型参数（temperature、max_tokens 等） |
| handoff_description | 作为 Handoff 目标时的描述提示 |
| skills | 已启用的 Skill 列表（用于知识注入） |
| approval_mode | 默认审批模式（suggest / auto-edit / full-auto） |

**Agent 不是进程或容器**——它是一个配置声明。当用户发起对话时，Runner 根据 Agent 定义创建执行上下文，驱动 LLM 完成推理和工具调用。

### 2.2 Runner（执行引擎）

Runner 是 Agent 的执行驱动器，实现 **Agent Loop**：

```
1. 将用户输入和 Agent 定义发送给 LLM2. LLM 返回结果：   a. 若为 final_output → 循环结束，返回结果   b. 若为 handoff → 切换当前 Agent 和输入，回到步骤 1   c. 若为 tool_calls → 执行工具调用，追加结果，回到步骤 13. 若超过 max_turns → 抛出异常或触发错误处理

```
Runner 支持三种运行方式：| 方式 | 说明 |
|------|------|
| run | 异步运行，返回完整结果 |
| run_sync | 同步运行 |
| run_streamed | 异步流式运行，实时推送事件 |**RunResult** 是 Runner 执行的返回结果：| 字段 | 说明 |
|------|------|
| final_output | Agent 最终回复内容（字符串或结构化对象） |
| messages | 本轮执行产生的全部消息 |
| last_agent | 最终处理回复的 Agent（可能经过 Handoff 切换） |
| token_usage | 累计 Token 消耗 |
| trace | 本次执行的 Trace 对象 |**StreamEvent** 是流式运行的事件类型：| 事件类型 | 说明 |
|---------|------|
| AgentStartEvent | Agent 开始执行 |
| LLMChunkEvent | LLM 流式 Token 片段 |
| ToolCallStartEvent / EndEvent | 工具调用开始 / 结束 |
| HandoffEvent | Agent 间控制转移 |
| GuardrailEvent | 护栏触发事件 |
| ApprovalRequestEvent | 审批请求事件 |
| RunCompleteEvent | 执行完成 |**RunConfig** 提供运行时配置覆盖（不修改 Agent 定义）：| 配置类别 | 说明 |
|---------|------|
| 模型覆盖 | 全局覆盖 Agent 的模型和参数（temperature、max_tokens 等） |
| 护栏覆盖 | 追加运行级输入/输出护栏 |
| Handoff 控制 | 全局 input_filter、嵌套历史控制 |
| Tracing 配置 | 链路追踪开关、工作流名称、敏感数据过滤 |
| 审批配置 | 工具调用审批模式 |

### 2.3 Handoff（移交）

Handoff 是 Agent 间的 **控制转移** 机制——当前 Agent 将对话控制权移交给另一个 Agent，由目标 Agent 继续处理后续交互。| 特性 | 说明 |
|------|------|
| 工具化 | Handoff 以工具形式暴露给 LLM（如 `transfer_to_refund_agent`），由 LLM 自主决策调用 |
| Input Filter | 可过滤传递给目标 Agent 的历史消息（控制上下文） |
| on_handoff 回调 | 移交时触发回调（如记录日志、数据预取） |
| input_type | LLM 可在移交时携带结构化元数据（如 reason、priority） |
| 动态启用 | 支持运行时动态启用/禁用特定 Handoff |

**适用场景：** 分诊路由、专家分工——Triage Agent 根据用户意图路由到 Billing Agent / Refund Agent / FAQ Agent。

### 2.4 Agent-as-Tool（嵌套调用）

Agent-as-Tool 是将一个 Agent 包装为工具，供 **Manager Agent** 调用。Manager Agent 保持对话控制权，只是借助 Specialist Agent 完成子任务。| 特性 | 说明 |
|------|------|
| 控制权保留 | Manager Agent 始终持有对话控制权 |
| 结果整合 | Manager Agent 负责汇总 Specialist 结果后回复用户 |
| 并行调用 | 可同时调用多个 Specialist Agent |
| 独立上下文 | 每个 Specialist 有独立执行上下文 |

**适用场景：** 任务分解、多源整合——Research Agent 作为 Manager，调用 Web Search Agent + Data Analysis Agent + Report Writer Agent 协作完成研究报告。

### 2.5 编排模式与执行模式

CkyClaw Framework 通过 Handoff 和 Agent-as-Tool 两个原语，支撑以下三大执行模式：

#### 2.5.1 单 Agent 执行最基础的模式——一个 Agent 独立完成任务。

```
用户 ──► Runner.run(agent, input) ──► Agent Loop（LLM ↔ Tools）──► Result

```
适用场景：简单问答、单一任务（代码生成、数据查询、文案撰写）。

#### 2.5.2 多 Agent 串行（Sequential Pipeline）

多个 Agent 按链路顺序执行，前一个 Agent 的输出（或控制权）传递给后一个。**模式 A：Handoff 链（LLM 自主决策路由）**

```
用户 ──► Triage Agent ──handoff──► Billing Agent ──handoff──► Confirm Agent ──► Result                  LLM 决定移交              LLM 决定移交

```
- 控制权逐个转移，每个 Agent 独立持有对话。- 路由由 LLM 根据对话内容自主决策（非预编排）。- 适用场景：意图分诊、多轮专家协作、工单流转。**模式 B：Agent-as-Tool 链（Manager 串行委派）**

```
用户 ──► Manager Agent ──call──► Research Agent ──return──► Manager ──call──► Writer Agent ──return──► Manager ──► Result                子任务1                          汇总中间结果         子任务2                          最终回复

```
- Manager Agent 保持控制权，按顺序调用 Specialist Agent。- 每个 Specialist 执行独立子任务后将结果返回 Manager。- 适用场景：分步骤流程（调研→分析→报告）、需要中间结果整合。

#### 2.5.3 多 Agent 并行（Parallel Fan-out / Fan-in）

Manager Agent 同时调用多个 Specialist Agent，并行执行后汇总结果。

```
                                ┌── Research Agent ──┐用户 ──► Manager Agent ──call──┼── Data Agent ──────┼──return──► Manager ──► Result
└── Market Agent ────┘
汇总所有结果                                    (并行执行)

```
**实现机制：** LLM 在单次响应中返回多个 `tool_calls`（其中 tool 为 `agent::` 前缀的 Agent-as-Tool），Runner 的 ToolRouter 通过 `asyncio.gather()` 并行执行所有调用。| 特性 | 说明 |
|------|------|
| 触发方式 | LLM 在一次响应中生成多个 agent-as-tool 调用 |
| 并行粒度 | Agent 级别——每个被调用的 Agent 拥有独立 RunContext |
| 结果汇总 | Manager Agent 收到所有 ToolResult 后由 LLM 整合回复 |
| 错误隔离 | 单个 Agent 失败不影响其他并行 Agent；Manager 会看到错误信息 |
| 超时控制 | 通过 Tool 的 `timeout` 配置控制单个 Agent-as-Tool 的超时 |

适用场景：多源信息采集（同时搜索+数据库+文档）、并行评审、竞品对比分析。

#### 2.5.4 模式组合与

选择指南三种模式可自由组合——Triage 通过 Handoff 串行路由到 Specialist，Specialist 内部再通过 Agent-as-Tool 并行调用多个子 Agent。| 维度 | Handoff（串行路由） | Agent-as-Tool 串行 | Agent-as-Tool 并行 |
|------|---------------------|--------------------|--------------------|
| 控制权 | 转移给目标 Agent | 保留在 Manager | 保留在 Manager |
| 对话归属 | 目标 Agent 直接回复用户 | Manager 回复用户 | Manager 回复用户 |
| 上下文 | 共享（可过滤）对话历史 | 独立上下文 | 独立上下文 |
| 决策者 | LLM 自主决定何时移交 | LLM 决定调用顺序 | LLM 决定同时调用哪些 |
| 适用场景 | 路由分诊、专家接管 | 分步骤流程 | 多源整合、并行评审 |

#### 2.5.5 Agent Team 协作模式

**Agent Team** 是 CkyClaw 在单 Agent / 多 Agent 委派模型之上引入的 **团队级抽象**——将一组 Agent 绑定为可复用的协作单元，通过 **TeamProtocol（协作协议）** 定义成员间的交互方式，由 **Coordinator Agent** 按需调用。

##### 核心概念

| 概念 | 定义 | 与现有概念的关系 |
|------|------|-----------------|
| **Team** | 一组 Agent + 一个 TeamProtocol 的封装 | 类比 Agent 是"个人"，Team 是"小组" |
| **TeamConfig** | Team 的声明式配置（成员列表、协议、终止条件、结果聚合） | 与 AgentConfig 对等，支持 YAML / Dict / API 管理 |
| **TeamProtocol** | 团队内部 Agent 交互策略 | 建立在 Agent-as-Tool 和消息传递原语之上 |
| **Coordinator** | 一个拥有 `Team-as-Tool` 的顶层 Agent，根据任务选择调用不同 Team | 就是一个普通 Agent，其 tools 中包含 `team.as_tool()` |
| **Team-as-Tool** | `team.as_tool()` 将 Team 暴露为单个 Tool，供任何 Agent 调用 | 与 `agent.as_tool()` 行为一致——输入一段文本，输出 Team 最终结果 |

##### TeamProtocol 类型

| 协议 | 交互方式 | 终止条件 | 适用场景 |
|------|---------|---------|---------|
| **Sequential** | Agent 按固定顺序逐一执行，前者输出作为后者输入 | 最后一个 Agent 完成 | 分步流水线（调研→分析→报告） |
| **Parallel** | 所有 Agent 同时收到相同输入，独立执行后汇总 | 全部完成（或超时） | 多源采集、并行评审、多语言翻译 |
| **Debate** | Agent 对同一问题发表观点，经多轮交互后由 Judge 裁定 | max_rounds 达到 或 Judge 判定共识 | 决策审核、代码评审、方案论证 |
| **RoundRobin** | Agent 按顺序轮流发言，每轮可看到前序 Agent 的全部输出 | max_rounds 达到 或 LLM 判定收敛 | 头脑风暴、故事接龙、迭代优化 |
| **Broadcast** | Coordinator 广播任务，各 Agent 独立响应，结果不聚合 | 全部完成 | 多渠道通知、多模型投票 |
| **Custom** | 开发者自定义 `TeamProtocol` 子类，完全控制交互逻辑 | 自定义 | 特殊领域协作流程 |

##### Team 执行流程

```
Coordinator Agent    │
│ LLM 决定: tool_call(research_team, "分析 Q1 销售下滑原因")    │
▼┌─────────────────────────────────────────────────────────────────┐│ Team-as-Tool 执行 (TeamRunner)                                   │
│
│
│  1. 加载 TeamConfig                                              │
│  2. 根据 TeamProtocol 选择执行策略                                │
│
│
│
┌── Debate ──────────────────────────────────────────────────┐
│
│
│  Round 1: Agent A 发表观点 → Agent B 反驳 → Agent C 补充   │
│
│
│  Round 2: Agent A 回应 → Agent B 修正 → Agent C 总结       │
│
│
│  Judge: 综合所有轮次产出最终结论                             │
│
│
└────────────────────────────────────────────────────────────┘
│
│
│
│  3. 结果聚合（按协议策略：concat / vote / judge / custom）       │
│  4. 返回 Team 最终输出给 Coordinator                             │
│  5. 产出 Team Span（包含所有成员 Agent 的子 Span）               │└─────────────────────────────────────────────────────────────────┘
│
▼Coordinator 继续 Agent Loop

```

##### 与现有编排模式的关系

Team 不替代 2.5.1-2.5.4 中的单 Agent / Handoff / Agent-as-Tool 模式，而是在其上层增加团队级封装：| 层级 | 抽象 | 负责人 |
|------|------|--------|
| L0 - 单 Agent | Agent + Runner | Runner |
| L1 - 委派 | Handoff / Agent-as-Tool | Manager Agent (LLM) |
| L2 - **团队**

| **Team + TeamProtocol** | **TeamRunner** |
| L3 - 编排入口 | **Coordinator** + Team-as-Tool | Coordinator Agent (LLM) |

> **设计原则：** Team 内部的多轮交互由 TeamRunner（代码驱动）控制，而 Coordinator 何时调用哪个 Team 仍由 LLM 决定。这确保了"LLM 决策 + 代码执行"的一致架构。

### 2.6 Tool（工具）

Tool 是 Agent 与外部世界交互的桥梁。CkyClaw Framework 支持以下工具类型：| 工具类型 | 说明 |
|----------|------|
| **Function Tool** | Python 函数工具，通过 `@function_tool` 装饰器注册，自动从函数签名和 docstring 生成 JSON Schema，支持同步/异步 |
| **MCP Tool** | 通过 MCP 协议从外部 MCP Server 加载的工具 |
| **Hosted Tool** | 平台内置工具（Web Search、Code Interpreter 等） |
| **Agent-as-Tool** | 将 Agent 包装为工具（`Agent.as_tool()`），支持审批门控、流式输出、条件启用 |

#### 工具分组（Tool Groups）工具通过 **Tool Groups** 分组管理，Agent 可按组加载：

| 工具组 | 说明 |
|--------|------|
| web-search | 网络搜索 |
| code-executor | 代码执行（在 Sandbox 中） |
| file-ops | 文件操作 |
| http | HTTP 请求 |

#### 工具命名空间（Tool Namespace）

借鉴 Agents SDK `tool_namespace()` 模式，对同一来源或同一领域的工具自动添加命名空间前缀，避免工具名称冲突：| 场景 | 命名空间示例 | 效果 |
|------|------------|------|
| MCP Server | `github::` | `github::create_issue`、`github::list_repos` |
| Skill 注入 | `data_analysis::` | `data_analysis::run_query`、`data_analysis::plot_chart` |
| 自定义工具组 | `custom::` | `custom::send_email` |

#### 延迟加载（Deferred Tool Loading）

当 Agent 配置了大量工具时（>20），将所有工具描述写入 Prompt 会消耗大量 Token。CkyClaw Framework 支持 **ToolSearchTool** 模式——仅向 LLM 暴露一个 `search_tools(query)` 元工具，LLM 按需搜索并加载具体工具：| 特性 | 说明 |
|------|------|
| 触发条件 | Agent 工具数超过阈值（默认 20）时自动启用 |
| 搜索方式 | 基于工具名称 + 描述的语义匹配 |
| 缓存策略 | 同一 Run 内已加载的工具缓存到 Context 中，避免重复搜索 |
| 收益 | 大幅减少初始 Prompt Token 消耗 |

#### 工具错误处理与超时

| 配置 | 说明 |
|------|------|
| `timeout` | 单工具调用超时时间（秒），超时后返回错误信息给 LLM |
| `failure_error_function` | 自定义错误处理函数，将异常转换为对 LLM 友好的错误提示 |
| 默认行为 | 工具异常不终止 Run，而是将错误信息作为工具返回值传回 LLM，由 LLM 决定重试或换方案 |

#### 条件启用

Agent-as-Tool 和 Function Tool 均支持条件启用，在 Runner 每轮循环时动态计算该工具是否可用（基于 RunContext 中的状态）。

### 2.7 Skill（技能）

Skill 是对 Agent 能力的知识注入包。Skill 不是可执行的工具函数，而是通过结构化的知识文件向 Agent 注入领域知识和操作指令。**包目录结构**（借鉴 Codex CLI AGENTS.md + VS Code Skill 设计）：

```
my-skill/├── metadata.yaml        

# Skill 元

数据（名称、描述、版本、适用 Agent 标签）├── SKILL.md             

# 主知识文件——工作流程、操作建议、领域规则├── scripts/             

# 辅助脚本（可被 Agent 调用执行）│
├── setup.sh│
└── validate.py├── references/          

# 参考资料（文档片段、API 规范、示例

数据）│
├── api-spec.json│
└── examples.md└── assets/              

# 静态资源（模板文件、配置模板、Prompt 片段）
└── report-template.md

```
**metadata.yaml 示例：**

```
yamlname: data-analysisversion: 1.2.0description: "数据分析领域知识——SQL 查询优化、图表生成建议、统计方法选择"author: CkyClaw Teamtags: [data, sql, visualization]applicable_agents: ["data-analyst", "report-writer"]

```
| 属性 | 说明 |
|------|------|
| 分类 | public（公共/内置）、custom（自定义） |
| 安装方式 | 通过 `.skill` 归档包（ZIP）安装到 Skill 目录；或从 Skill Registry 拉取 |
| 加载机制 | 已启用 Skill 的名称和描述注入 Agent Prompt，Agent 按需读取 SKILL.md |
| 调用方式 | Agent 自动匹配或用户通过 `@skill-name` 显式指定 |
| 版本管理 | metadata.yaml 中声明版本号，支持多版本并存和回滚 |
| 工具注入 | scripts/ 目录下的脚本自动注册为该 Skill 的 Function Tool（命名空间隔离） |

### 2.8 Message（消息）Message 是 Agent 通信的基本单元：

| 角色 | 说明 |
|------|------|
| user | 用户输入消息 |
| assistant | Agent 回复消息 |
| system | 系统指令（Instructions 注入） |
| tool | 工具调用结果 |

每条 Message 包含：角色、文本内容、元数据（Agent ID、时间戳、Token 消耗等）。在 Handoff 场景中，消息历史可通过 Input Filter 过滤后传递给目标 Agent。

### 2.9 Session（会话）Session 是对话状态的持久化管理机制，自动处理多轮对话的历史存储与加载。

| 特性 | 说明 |
|------|------|
| 自动持久化 | 每轮对话结束后自动保存新消息 |
| 历史加载 | 下一轮对话前自动加载历史上下文 |
| 多后端 | 支持 PostgreSQL、Redis、SQLite 等存储后端 |
| 会话隔离 | 不同 Session ID 的对话完全隔离 |
| 历史裁剪 | 支持滑动窗口、Token 预算、摘要压缩三种策略 |
| 并发安全 | 同一 Session 同时刻仅一个 Runner 持有写权限 |

> Session 详细设计（数据模型、后端实现规范、裁剪策略、TTL 管理）见《CkyClaw Framework Design v2.0》第九章。

### 2.10 Guardrails（护栏）Guardrails 提供 Agent 输入/输出的安全验证机制：

| 类型 | 运行时机 | 说明 |
|------|---------|------|
| **Input Guardrail** | Agent 执行前 | 验证用户输入（如检测恶意内容、Prompt 注入） |
| **Output Guardrail** | Agent 输出后 | 验证 Agent 回复（如检测敏感信息泄露） |
| **Tool Guardrail** | 工具调用前后 | 验证工具调用参数和返回值 |

**Tripwire 触发机制：**1. Guardrail 函数执行检测逻辑（可以调用 LLM 进行语义分析）2. 返回 `GuardrailResult`，其中 `tripwire_triggered=true` 表示触发3. 触发后 Runner 立即中断当前执行，抛出对应异常（`InputGuardrailError` / `OutputGuardrailError` / `ToolGuardrailError`）4. CkyClaw 应用层捕获异常，可转入审批工作流或直接向用户返回错误信息**执行模式：**

| 模式 | 说明 |
|------|------|
| 并行（默认） | Guardrail 与 Agent 同时执行，最低延迟 |
| 阻塞 | Guardrail 先执行完成，通过后 Agent 才开始，避免浪费 Token |

**内置 Guardrail 库：**

| 名称 | 类型 | 说明 |
|------|------|------|
| PromptInjectionGuardrail | Input | 基于 LLM 检测 Prompt 注入攻击 |
| ContentSafetyGuardrail | Input/Output | 基于 LLM 检测有害/不当内容 |
| PIIDetectionGuardrail | Output | 基于正则 + NER 检测 PII 泄露 |
| RegexGuardrail | Input/Output | 通用正则匹配黑名单 |
| MaxTokenGuardrail | Input | 输入长度限制 |
| ToolWhitelistGuardrail | Tool | 仅允许指定工具调用 |

> Guardrails 详细设计（执行引擎、流水线、LLM-Based 模式、配置组合）见《CkyClaw Framework Design v2.0》第十章。

### 2.11 Tracing（链路追踪）

Tracing 提供 Agent 执行的全链路可观测性。每次 Agent 运行产生一个 **Trace**，内部包含多个 **Span**（Agent Span、LLM Span、Tool Span、Handoff Span）。| 特性 | 说明 |
|------|------|
| 自动采集 | Runner 执行过程自动产生 Trace/Span |
| 自定义处理器 | 支持自定义 Trace Processor，将数据导出到 APM 后端 |
| 敏感数据控制 | 可配置是否记录 LLM 和工具的输入/输出 |
| 元数据 | workflow_name、trace_id、group_id 用于组织和关联追踪数据 |

### 2.12 Memory（记忆）Memory 提供跨会话的长期记忆能力：

| 类型 | 说明 | 示例 |
|------|------|------|
| **用户档案** | 对话中自动提取的用户信息 | "用户偏好 Python，使用 macOS" |
| **历史摘要** | 长对话自动生成的压缩摘要 | "上次讨论了 Q1 报告，结论是..." |
| **结构化事实** | Agent 执行中积累的事实数据 | "项目使用 PostgreSQL 16（置信度 0.95）" |CkyClaw 提供记忆管理 UI：| 能力 | 说明 |
|------|------|
| 记忆查看 | 在 UI 中按用户 / Agent / 分类浏览所有记忆条目 |
| 记忆编辑 | 人工修正或删除不准确的记忆条目 |
| 记忆检索策略 | 配置记忆注入策略：按相关性 / 按时间 / 按分类过滤 |
| 跨会话传递 | 同一用户的新会话自动加载相关记忆上下文 |
| 隐私控制 | 用户可查看并删除自己的记忆数据；管理员可按组织清理 |
| 置信度管理 | 每条记忆带置信度分数，长期未命中的记忆自动衰减 |
| 向量检索 | 基于 Embedding 的语义相似度检索（pgvector） |

> Memory 详细设计（提取流水线、向量检索、隐私生命周期管理）见《CkyClaw Framework Design v2.0》第十一章。

### 2.13 Model Provider（模型提供商）

CkyClaw Framework 采用 Provider-agnostic 设计，通过 LiteLLM 适配层支持多 LLM 提供商。**支持的主流厂商：**

| 厂商 | 支持模型 | 接入方式 |
|------|---------|---------|
| OpenAI | GPT-4o / GPT-4o-mini / o1 / o3 / o4-mini 等 | API Key |
| Anthropic | Claude 4 Opus / Claude 4 Sonnet 等 | API Key |
| Google | Gemini 2.5 Pro / Flash 等 | API Key |
| DeepSeek | DeepSeek-V3 / DeepSeek-R1 等 | API Key |
| 阿里云（通义） | Qwen 系列 | API Key |
| 字节跳动（豆包） | Doubao 系列 | API Key |
| 智谱 AI | GLM 系列 | API Key |
| 月之暗面（Kimi） | Moonshot 系列 | API Key |
| Azure OpenAI | GPT-4o 等（企业级部署） | Endpoint + Key |
| 私有部署 | vLLM / Ollama / LocalAI 等 | 自定义 Base URL |**CkyClaw 模型厂商管理：**CkyClaw 提供统一的模型厂商配置管理界面，管理员配置厂商连接信息后，Agent 配置时可从已启用的厂商和模型中选择。| 管理能力 | 说明 |
|---------|------|
| 厂商注册 | 录入厂商名称、Base URL、API Key、认证方式 |
| 模型列表 | 配置厂商下可用的模型列表（名称、上下文窗口、价格信息） |
| 连通性测试 | 测试厂商 API 连通性和 Key 有效性 |
| 默认模型 | 设置全局默认模型（Agent 未指定 model 时使用） |
| 启用/禁用 | 按厂商或按模型粒度启用/禁用 |
| 成本配置 | 配置各模型的单价（prompt_tokens / completion_tokens 单价），用于成本计算 |
| 限流配置 | 配置厂商级 RPM/TPM 限制，防止超配额 |

**模型选择优先级：** Agent 配置 model → RunConfig 覆盖 model → 全局默认模型。每个 Agent 可独立配置模型，RunConfig 可在运行时覆盖。

### 2.14 Approval Mode（审批模式）三级审批模式控制 Agent 自主权级别：

| 模式 | 说明 |
|------|------|
| **suggest** | 每次工具调用/输出前均需人工确认 |
| **auto-edit** | 安全操作自动执行，高风险操作需人工确认 |
| **full-auto** | 完全自动执行，无需人工干预 |

审批模式可在 Agent 级别、Tool 级别和 Run 级别分别配置。

### 2.15 Context（上下文）Context 是 Agent 执行过程中的信息容器：

| 类型 | 说明 | 生命周期 |
|------|------|----------|
| System Context | 系统级配置和约束 | 应用级 |
| Session Context | 会话级信息（对话历史、状态） | 会话级 |
| Run Context | 单次执行的运行时上下文（可注入自定义数据） | 执行级 |
| Agent Context | Agent 自身状态 | Agent 生命周期 |

### 2.16 Runner Lifecycle Hooks（生命周期钩子）

Runner 在 Agent 执行的关键节点提供 **Lifecycle Hooks**，允许应用层注入自定义逻辑（日志、权限校验、指标采集、行为审计等），而无需修改 Framework 内部。

#### 2.16.1 Hook 触发点

| Hook | 触发时机 | 典型用途 |
|------|---------|---------|
| **on_run_start** | `Runner.run()` 入口，初始化完成后 | 执行权限校验、记录启动日志、注入运行时上下文 |
| **on_run_end** | Run 结束（成功/失败/取消） | 执行结果记录、资源清理、通知推送 |
| **on_agent_start** | Agent 开始处理（含 Handoff 切换后新 Agent） | Agent 级权限校验、上下文预加载 |
| **on_agent_end** | Agent 完成处理 | Agent 级指标采集 |
| **on_llm_start** | LLM 调用发起前 | 模型级限流、Prompt 审计 |
| **on_llm_end** | LLM 调用返回后 | Token 记录、响应质量检查 |
| **on_tool_start** | 工具调用执行前 | 工具执行权限校验、参数审计 |
| **on_tool_end** | 工具调用完成后 | 结果审计、副作用记录 |
| **on_handoff** | Agent 间移交时 | 转交日志、目标 Agent 权限校验 |
| **on_error** | 任何阶段异常触发 | 统一错误上报、告警触发 |

#### 2.16.2 Hook 与现有机制的关系

| 机制 | 职责 | 区别 |
|------|------|------|
| **Lifecycle Hooks** | 可观测性 + 应用层扩展（无拦截能力，仅通知） | 始终执行，不影响控制流 |
| **Guardrails** | 安全护栏（有拦截能力，可终止执行） | 触发 Tripwire 时中断 Run |
| **Approval Mode** | 人工审批（阻塞执行流等待决策） | 阻塞直到审批完成 |
| **TraceProcessor** | Trace/Span 数据导出 | 仅处理 Span 数据，无业务语义 |

Hook 设计原则：- **非阻塞：** Hook 异步执行，不阻塞 Agent Loop（异常会被捕获并记录，不影响执行流）。- **可组合：** 可注册多个 Hook，按顺序触发。- **通过 RunConfig 注册：** 应用层通过 `RunConfig.hooks` 字段注入，Framework 不依赖具体 Hook 实现。

> Runner Lifecycle Hooks 完整接口设计详见《CkyClaw Framework Design v2.0》第六章 6.8 节。

#### 2.16.3 执行权限与安全

CkyClaw 通过 **多层安全模型** 控制 Agent/Tool/Skill 的执行权限：| 层级 | 机制 | 控制点 |
|------|------|--------|
| **API 层** | RBAC 权限矩阵（Ch13.3） | 谁能创建 Session、发起 Run、管理 Agent |
| **Run 层** | `on_run_start` Hook + RunConfig 约束 | 执行前校验用户预算、组织策略、运行频率 |
| **Agent 层** | `on_agent_start` Hook + Agent 可见性 | 用户是否有权使用目标 Agent |
| **Tool 层** | ToolGuardrail (before_fn) + Approval Mode | 工具调用前参数校验、敏感工具审批 |
| **Sandbox 层** | Sandbox 隔离 + 资源限制 | 代码执行在隔离环境中，CPU/内存/网络受限 |

**安全不变量：**- 任何需要执行的内容（Agent 指令、工具参数、用户输入）都经过 Guardrails 链检查。- 代码执行类工具（code-executor）必须在 Sandbox 中运行。- Approval Mode 为敏感操作提供人工阻断能力。- Lifecycle Hooks 提供全链路审计可追溯性。

---

## 三、技术架构

### 3.1 架构概览

CkyClaw 采用 **CkyClaw Framework + CkyClaw 应用** 的分层架构。CkyClaw Framework作为 Python 库嵌入后端，提供 Agent 运行时能力；CkyClaw 应用层在其上构建企业级管理与监控功能。

```
┌─────────────────────────────────────────────────────────────────────────┐│                           CkyClaw Application                           │
│
┌──────────────┐
┌──────────────┐
┌──────────────┐
┌───────────┐
│
│
│  执行可视化   │
│  人工监督     │
│  APM 监控    │
│  前端 UI   │
│
│
│  Dashboard   │
│  Supervision │
│  Observability│
│  React SPA │
│
│
└──────┬───────┘
└──────┬───────┘
└──────┬───────┘
└─────┬─────┘
│
│
│                 │
│                 │
│
│
└─────────────────┴─────────────────┴─────────────────┘
│
│
│                                    │
│                    CkyClaw Backend (FastAPI)                            │
│
┌─────────────────────────┼─────────────────────────┐
│
│
│  RBAC │ 多租户 │ 审计 │ 渠道 │ Session 管理 │ API │
│
│
└─────────────────────────┼─────────────────────────┘
│
│
│                                    │
│
┌─────────────────────────────────┼─────────────────────────────────┐ │
│
│                        CkyClaw Framework                          │ │
│
│  ┌────────┐
┌────────┐
┌────────┐
┌──────────┐
┌──────────────┐
│ │
│
│  │ Agent  │ │ Runner │ │Handoff │ │Guardrails│ │Model Provider│
│ │
│
│  └────────┘ └────────┘ └────────┘ └──────────┘ └──────────────┘
│ │
│
│  ┌────────┐
┌────────┐
┌────────┐
┌──────────┐
┌──────────────┐
│ │
│
│  │ Tools  │ │  MCP   │ │Session │ │ Tracing  │ │   Sandbox    │
│ │
│
│  └────────┘ └────────┘ └────────┘ └──────────┘ └──────────────┘
│ │
│
│  ┌────────┐
┌────────┐
┌────────┐
│ │
│
│  │ Skills │ │ Memory │ │Approval│
│ │
│
│  └────────┘ └────────┘ └────────┘
│ │
│
└───────────────────────────────────────────────────────────────────┘ │
│
│                                    │
│
┌─────────┼─────────┐
│
│
▼
▼
▼
│
│                    [LLM APIs] [MCP Servers] [Sandbox]                  │└─────────────────────────────────────────────────────────────────────────┘
│                                              │
▼
▼
┌───────────┐
┌───────────┐
┌──────────────────┐
┌───────────┐
│PostgreSQL │
│   Redis   │
│  OTel Collector  │
│  对象存储  │
│  业务数据  │
│ 缓存/消息 │
│  ↓ Trace/Metrics │
│  文件/产物 │
│ +Token审计 │
│           │
│ Jaeger/Tempo     │
│           │
│           │
│           │
│ + Prometheus     │
│           │
└───────────┘
└───────────┘
└──────────────────┘
└───────────┘
┌──────────────────┐
│ ClickHouse (可选) │
│ 大规模分析场景    │
└──────────────────┘

```

### 3.2 CkyClaw Framework 职责

| 模块 | 职责 |
|------|------|
| **Agent** | Agent 定义、配置加载、Instructions 解析 |
| **Runner** | Agent Loop 执行引擎、流式输出、max_turns 控制 |
| **Handoff** | Agent 间控制转移、Input Filter、回调机制 |
| **Tools** | Function Tool 注册/执行、Tool Groups 管理 |
| **MCP** | MCP Server 连接管理、工具发现、OAuth 令牌流 |
| **Session** | 对话历史持久化、多后端适配 |
| **Guardrails** | 输入/输出/工具护栏、Tripwire 检测 |
| **Tracing** | Trace/Span 采集、自定义 Processor 导出 |
| **Model Provider** | 多 LLM 提供商适配、Model Settings |
| **Sandbox** | 隔离代码执行环境（Local / Docker / K8s） |
| **Skills** | Skill 扫描/加载/安装、SKILL.md 知识注入 |
| **Memory** | 长期记忆存储/检索、自动提取/摘要 |
| **Approval** | 审批模式管理、工具调用拦截/等待 |

### 3.3 CkyClaw 应用层职责

| 模块 | 职责 |
|------|------|
| **Agent 管理** | 声明式 Agent CRUD、SOUL.md 版本管理、模板库 |
| **多租户** | Organization / Team 体系、数据隔离、配额管理 |
| **RBAC** | 角色权限控制、资源级细粒度授权 |
| **人工监督** | 实时监控、干预/接管、审批工作流 |
| **执行可视化** | 将 Tracing 数据渲染为可交互的执行流程图 |
| **APM 仪表盘** | 指标聚合、告警规则、成本分析 |
| **渠道管理** | IM 渠道接入、消息路由、统一消息总线 |
| **审计** | 操作审计日志、合规追溯 |

### 3.4 关键设计原则1. **框架与应用分离

**：CkyClaw Framework 无业务概念（无用户/组织/权限），CkyClaw 应用层负责所有业务逻辑2. **声明式 Agent 配置**：Agent 通过 YAML 或代码声明式定义，支持版本管理3. **Provider-agnostic**：不绑定任何特定 LLM 提供商，通过 Model Provider 抽象适配多模型4. **Tracing-first 可观测性**：所有执行行为自动产生 Trace/Span，驱动可视化和 APM5. **MCP 标准化工具接入**：遵循 Model Context Protocol 标准，工具生态开放可扩展

---

## 分册索引

本 PRD 的功能详细设计已拆分为以下分册：

| 分册 | 文件 | 章节 | 内容 |
|------|------|------|------|
| **Agent 编排** | 《CkyClaw PRD-Agent 编排 v2.0》 | 四~六 | Agent 执行模式（Handoff/Agent-as-Tool/Team）、工具系统与 MCP、任务执行可视化 |
| **企业能力** | 《CkyClaw PRD-企业能力 v2.0》 | 七~十 | IM 渠道接入、人工监督机制、APM 与可观测性、前端与用户界面 |
| **基础设施** | 《CkyClaw PRD-基础设施 v2.0》 | 十一~十五 | API 设计、数据模型、用户系统与安全管理、部署与运维、非功能性需求 |

### 设计文档索引

| 文档 | 版本 | 职责 |
|------|------|------|
| 《CkyClaw Framework Design v2.0》 | v2.0.0 | Agent 运行时库（Agent/Runner/Tool/Session/Tracing/Memory） |
| 《CkyClaw API Design v1.2》 | v1.2.0 | 完整 REST API + WebSocket/SSE 事件协议 |
| 《CkyClaw 应用层技术设计方案 v1.2》 | v1.2.0 | IM 渠道、前端 UI、APM 仪表盘、通知系统、配置/i18n 页面 |
| 《CkyClaw 数据模型详细设计 v1.3》 | v1.3.0 | 全部实体列级 Schema（字段/约束/索引） |

---

## 附录 A：术语表

| 术语 | 说明 |
|------|------|
| **CkyClaw Framework** | CkyClaw 自研的 Agent 运行时框架，提供 Agent 定义、执行引擎、编排、工具系统等核心原语 |
| **Agent** | 智能代理——由 Instructions + Model + Tools + Handoffs 组成的声明式定义 |
| **Runner** | Agent 执行引擎，实现 Agent Loop |
| **Handoff** | Agent 间控制转移机制 |
| **Agent-as-Tool** | 将 Agent 包装为工具供其他 Agent 调用 |
| **Session** | 对话会话，管理多轮对话历史 |
| **Run** | Session 中的一次 Agent 执行 |
| **Trace** | 一次执行的完整链路追踪记录 |
| **Span** | Trace 中的一个执行步骤（Agent/LLM/Tool/Handoff） |
| **Guardrail** | 安全护栏——输入/输出/工具调用的验证机制 |
| **Tripwire** | 护栏触发信号，中断执行并抛出异常 |
| **Tool** | 工具——Agent 可调用的外部能力 |
| **Tool Group** | 工具组——按功能分组的工具集合 |
| **Tool Namespace** | 工具命名空间——通过前缀隔离不同来源的同名工具 |
| **ToolSearchTool** | 延迟加载元工具——LLM 按需搜索并加载具体工具，减少 Token 消耗 |
| **TokenUsageLog** | Token 审计日志记录，存储每次 LLM 调用的 Token 消耗明细 |
| **Skill** | 技能——通过 SKILL.md 注入的领域知识 |
| **MCP** | Model Context Protocol，标准化工具服务协议 |
| **Sandbox** | 隔离的代码执行环境 |
| **Approval Mode** | 审批模式（suggest / auto-edit / full-auto） |
| **Instructions** | Agent 行为指令，即 SOUL.md 内容 |
| **SOUL.md** | Agent 人格和行为约束定义文件 |
| **Model Provider** | LLM 模型提供商抽象层 |
| **ProviderConfig** | CkyClaw 中的模型厂商配置实体 |
| **ModelConfig** | CkyClaw 中的具体模型配置实体 |
| **APM** | Application Performance Management |
| **RunConfig** | 运行时配置覆盖，不修改 Agent 定义 |
| **Agent Team** | 团队协作单元——一组 Agent 按协作协议协同工作 |
| **TeamProtocol** | 团队协作协议（Sequential / Parallel / Debate / RoundRobin / Broadcast / Custom） |
| **Coordinator** | 总协调员 Agent——按需选择并调用 Team 或单个 Agent |
| **Team-as-Tool** | 将 Agent Team 包装为工具供 Coordinator 调用（`team::` 前缀） |
| **ScheduledRun** | 定时任务——按 Cron 表达式周期性执行 Agent Run |
| **BatchRun** | 批量任务——对多组输入并行执行同一 Agent |
| **AgentVersion** | Agent 配置版本快照，支持对比和回滚 |

## 附录 B：版本历史

| 版本 | 日期 | 修改内容 |
|------|------|---------|
| 1.0.0 | 2024-01-15 | 初始版本（草稿） |
| 1.0.1 | 2025-04-01 | 结构重组；新增 DeerFlow 集成架构、API 设计、数据模型、非功能性需求章节 |
| 1.0.2 | 2026-04-01 | 更名为 CkyClaw；精简技术实现细节，回归 PRD 定位 |
| 1.0.3 | 2026-04-01 | 新增前端与用户界面章节；扩充编排边界；新增 SOUL.md 管理 |
| 1.0.4 | 2026-04-01 | 修正 Agent 概念模型；删除工作流编排引擎，替换为任务执行可视化 |
| 1.0.5 | 2026-04-01 | 扩充记忆系统、成本控制策略、性能优化策略 |
| 1.0.6 | 2026-04-01 | 新增自定义资源加载原理、Supervisor 模式说明 |
| **2.0.0** | **2026-04-01** | **架构重大变更：放弃 DeerFlow 依赖，引入自研 CkyClaw Framework。新增 Handoff/Agent-as-Tool 编排模式、Guardrails 护栏、Tracing 链路追踪、Approval Mode 审批模式、Session 管理、Model Provider 多模型支持。所有 Agent/Session/Run 操作由 CkyClaw 自主管理。** |
| 2.0.1 | 2026-04-02 | 增强工具系统：新增 Tool Namespace、延迟加载（ToolSearchTool）、工具错误处理/超时、条件启用。增强 Skill 包结构（metadata.yaml、assets/、@mention 调用、版本管理）。新增 Token 审计日志与统计功能（9.5、审计数据采集/统计聚合/审计查询/告警/仪表盘、API、数据模型）。 |
| 2.0.2 | 2026-04-02 | PRD 瘦身：技术细节抽取到《CkyClaw 数据模型详细设计 v1.3》和《CkyClaw 应用层技术设计方案 v1.2》。增强 Session（历史裁剪/并发安全）、Guardrails（6 个内置护栏）、Memory（置信度/向量检索）章节。更新 MVP 功能边界（Skills/Sandbox）。新增前端/IM/APM 章节到应用层设计文档的交叉引用。 |
| 2.0.3 | 2026-04-02 | 架构调整：ClickHouse 改为可选组件；引入 OTel + Jaeger/Tempo + Prometheus + Grafana 作为推荐可观测性基础设施；Token 审计 MVP 默认存储改为 PostgreSQL；新增 PostgresTraceProcessor 作为默认 Trace 导出路径。 |
| **2.0.4** | **2026-04-02** | **新增功能设计：4.8.1 Agent 版本管理（全量快照策略、版本生命周期）；4.10 定时/批量任务执行（ScheduledRun + BatchRun）；4.11 Agent Team 与 Coordinator 设计（TeamConfig、6 种协作协议、内置 Team 模板、Coordinator Agent 模式、Team-as-Tool、Team Tracing）；4.12 内置 Agent/工具/Skill 完整清单（10 个 Agent 模板、5 个工具组含 9 个工具、6 个 Skill 包、推荐矩阵）；9.4.3 Token 开销优化设计（6 层优化策略：上下文管理/工具描述/Prompt 工程/模型路由/缓存复用/运行时控制）；9.6 Agent 评估与质量度量（7 维评估、用户反馈采集、评估报表）；14.6 灾备策略（RTO<4h/RPO<1h、PostgreSQL/Redis/对象存储备份方案）。扩展 2.5.5 Agent Team 从"规划中"升级为正式设计。** |
| 2.0.5 | 2026-04-02 | PRD 产品化瘦身：抽离 8 处技术实现代码（YAML/Python/Schema），替换为产品级描述 + 设计文档交叉引用。新增 4.13 配置热更新（6 类可热更新项 + 审计 + 回滚）与 Agent 国际化（多语言 Instructions / UI / 描述）。新增 14.7 配置热更新运维要求。同步更新 API Design v1.1.0（新增 Team / 定时批量 / 评估 API 共 17 个端点）、Data Model v1.1.0（新增 AgentVersion / TeamConfig / ScheduledRun+BatchRun / RunFeedback 共 6 张表）、Application Design v1.1.0（新增 Team 管理 / 评估仪表盘 / 定时批量任务 UI 共 3 章）、Framework Design v1.6.0（新增附录 A：10 个内置 Agent 模板完整 YAML 配置）。 |
| 2.0.6 | 2026-04-02 | 前端技术选型明确化（10.1）：消除"按需选型"模糊描述，确定 Zustand（状态管理）、Ant Design 5（UI 组件库）；新增 ProComponents（高级业务组件）、TanStack Query（数据请求层）、ReactFlow（流程图）、ECharts（图表）。新增"说明"列阐述选型理由。同步更新 14.3 技术栈前端描述。文档格式修复（零换行符恢复为正常 Markdown 格式）。 |
| 2.0.7 | 2026-04-02 | 同步更新设计文档：API Design v1.2.0（新增第十七章：配置热更新与国际化 API，含 ConfigChangeLog 查询/回滚、配置更新、Agent 多语言 Instructions CRUD 共 6 个端点）。Application Design v1.2.0（新增第八章配置变更管理页面、第九章国际化设置页面，路由表新增 /settings/config 和 /settings/i18n）。文件名版本号统一（API Design/Application Design/Data Model 文件名与内部版本对齐至 v1.2）。交叉引用版本号批量更新（v1.0→v1.2）。清理孤儿文件和临时脚本。 |
| 2.0.8 | 2026-04-02 | 深化 Agent Team 协作模式（4.11.6）：新增 8 种协作协议详解表（sequential/parallel/hierarchical/supervisor/debate/negotiated/round_robin/broadcast），含执行模型、数据流、典型场景、关键参数；新增 hierarchical vs supervisor、debate vs negotiated 对比说明；新增 3 个内置 Team 模板（project_decomposition_team/dynamic_workflow_team/budget_planning_team）。同步更新 Data Model v1.3.0 TeamConfig.protocol 枚举。PRD 完整性终审：修复文档尾部格式缺陷。 |
| **2.0.9** | **2026-04-02** | **PRD 结构拆分（总纲 + 3 分册）：总纲保留一~三章（产品概述/核心概念/技术架构）+ 附录 + 分册索引 + 设计文档索引。Agent 编排分册（四~六章：Agent 执行模式/工具系统/可视化，585 行）。企业能力分册（七~十章：IM 渠道/人工监督/APM/前端 UI，621 行）。基础设施分册（十一~十五章：API/数据模型/安全/运维/非功能性需求，689 行）。总纲从 2757 行精简至 949 行。** |

---

## 附录 C：MVP 范围与里程碑计划

### C.1 MVP 范围定义MVP（Minimum Viable Product）

目标：在最短时间内交付可运行的端到端 Agent 平台，验证核心技术路径和用户价值。

#### C.1.1 MVP 功能边界

| 功能模块 | MVP 范围（In） | 已实现扩展（Post-MVP） | 未来规划（Out） |
|---------|---------------|----------------------|----------------|
| **CkyClaw Framework** | Agent + Runner + 基础 Agent Loop | Memory（v2.2）、Skills（v2.2）、Sandbox（v2.6）、Checkpoint（v2.6）、Intent Detection（v2.6）、Cost Router（v2.6）、Evolution（M8） | — |
| **Agent 管理** | CRUD、Instructions 编辑、模型选择 | 版本管理+回滚（M6）、14 模板（v2.5）、YAML/JSON 导入导出、国际化（v2.4） | 批量操作 UI |
| **编排** | Handoff（单级）、Agent-as-Tool（单级） | 多级 Handoff + 循环检测、条件启用（v2.1）、Agent Team + Coordinator（v2.3，8 协议） | — |
| **对话** | Web 端实时对话、SSE 流式输出 | IM 6 渠道适配器（v2.5：企微/钉钉/飞书/Slack/Discord/Telegram） | 文件上传、多模态 |
| **工具系统** | Function Tool 注册、2+ 内置工具组 | MCP 集成 stdio/sse/http（M6）、Tool Namespace、ToolSearchTool、ToolGroup + ToolRegistry | — |
| **Session** | 基础会话持久化、历史加载 | HistoryTrimmer 裁剪（M6）、消息搜索（v2.7） | 跨设备同步 |
| **Guardrails** | Input Guardrail（基础 Prompt 注入检测） | Output + Tool Guardrail（M5）、6 种护栏（Regex/Keyword/LLM × 3）、并行执行（v2.1） | 护栏编排器 |
| **监督** | 观察模式（只读查看对话）、基础审批（suggest 模式） | 干预/接管模式（v2.3）、审批队列 UI、WebSocket 统一事件（v2.7） | 高级审批规则模板 |
| **执行可视化** | 基础 Trace 展示（列表 + Span 详情） | ReactFlow 流程图（v2.3）、Span 火焰图（v2.7）、Trace 回放（v2.7） | 实时协作编辑 |
| **Tracing** | 自动采集 Agent/LLM/Tool Span、写入 PostgreSQL（MVP） | OTel 集成 Jaeger/Prometheus（v2.3）、自定义 Trace Processor | 敏感数据脱敏 |
| **Token 审计** | 基础 TokenUsageLog 记录、按用户+模型统计 | 多维仪表盘（v2.4）、趋势 API + 告警引擎（v2.4） | 实时流式统计、CSV 导出 |
| **Model Provider** | 单厂商配置（OpenAI）、手动填写 API Key | 10+ 厂商 LiteLLM 适配（M6）、Fernet 加密、连通性测试、A/B 模型测试（v2.7） | 成本预测 |
| **用户系统** | 管理员邀请注册、JWT 认证、2 个角色（Admin + User） | RBAC 多角色（v2.4）、Organization/多租户（v2.7）、OAuth 2.0 6 Provider（v2.4） | SSO SAML 2.0 |
| **前端** | 对话页、Agent 管理页、基础执行列表页、登录页 | 38 页面全套（APM/监督/Token/Team/Workflow/A-B Test 等）、暗色模式、Vendor 5 路分包 | 移动端适配 |
| **部署** | Docker Compose 单机部署 | 6 Job GitHub Actions CI + Jenkinsfile 5 Stage + Playwright E2E + Locust 压测 | Kubernetes、高可用 |

#### C.1.2 技术路径验证目标MVP 需要验证以下关键技术假设：

| 

# | 假设 | 验证标准 |
|---|------|---------|
| 1 | CkyClaw Framework Agent Loop 可稳定驱动多轮对话 | 10 轮对话无状态丢失 |
| 2 | Handoff 可实现 Agent 间控制转移 | Triage → Specialist 完成端到端任务 |
| 3 | SSE 流式输出延迟可接受 | 首 Token < 2s |
| 4 | Tracing 数据可支撑执行过程回溯 | Trace/Span 完整覆盖 Agent + LLM + Tool |
| 5 | LiteLLM 适配层不会成为性能瓶颈 | LLM 调用额外开销 < 50ms |

### C.2 里程碑计划

#### M0：项目启动与基础搭建

| 交付物 | 说明 |
|--------|------|
| 项目仓库初始化 | monorepo 结构（backend/ + frontend/ + ckyclaw-framework/） |
| CkyClaw Framework 包骨架 | Agent、Runner、Tool、Session、Tracing 模块空壳 + 公共 API |
| CkyClaw 后端骨架 | FastAPI 项目、DB 迁移脚本、基础中间件（认证、限流、错误处理） |
| CkyClaw 前端骨架 | React + Vite + Ant Design + 路由框架 + 登录页 |
| 部署脚本 | Docker Compose（Backend + Frontend + PostgreSQL + Redis + OTel Collector + Jaeger + Prometheus + Grafana） |
| CI 流水线 | lint + unit test + build |

#### M1：Agent 核心引擎

| 交付物 | 说明 |
|--------|------|
| CkyClaw Framework Agent 定义 | Agent 数据类、声明式配置解析 |
| CkyClaw Framework Runner | Agent Loop 实现（LLM 调用 → Tool 执行 → 消息追加 → 循环） |
| CkyClaw Framework Function Tool | `@function_tool` 装饰器、ToolRegistry、自动 JSON Schema 生成 |
| CkyClaw Framework Session | 基础会话管理（PostgreSQL 后端） |
| LiteLLM 集成 | OpenAI 模型调用、流式输出 |
| **可演示：** | 在 Python REPL 中创建 Agent → 发送消息 → 获得回复 → 工具调用完成 |

#### M2：Web 对话与 Agent 管理

| 交付物 | 说明 |
|--------|------|
| Agent CRUD API | 创建/查看/编辑/删除 Agent 配置 |
| 对话 API | 创建 Session + 发起 Run + SSE 流式事件 |
| 前端对话页 | Agent 选择 → 对话输入 → 流式输出展示 → 历史记录 |
| 前端 Agent 管理页 | Agent 列表、创建/编辑表单（Instructions + 模型 + 工具组） |
| 用户认证 | 注册/登录/JWT |
| **可演示：** | 在 Web 界面中与 Agent 对话，支持流式输出 |

#### M3：编排与 Tracing

| 交付物 | 说明 |
|--------|------|
| CkyClaw Framework Handoff | Handoff 机制实现 + Runner 集成 |
| CkyClaw Framework Agent-as-Tool | `Agent.as_tool()` 实现 |
| CkyClaw Framework Tracing | Trace/Span 自动采集、TracingProcessor 接口 |
| CkyClaw Trace Processor | 将 Trace 数据写入 PostgreSQL（MVP 默认）；可选开启 OTel 导出 |
| Token 审计基础 | TokenUsageLog 写入 PostgreSQL |
| 执行记录页 | 执行列表 + Span 详情展示 |
| **可演示：** | Triage Agent → Handoff → Specialist Agent → 工具调用；完整 Trace 可查 |

#### M4：监督与安全

| 交付物 | 说明 |
|--------|------|
| CkyClaw Framework Approval Mode | suggest 模式实现 |
| CkyClaw Framework Input Guardrail | 基础 Prompt 注入检测 |
| CkyClaw 审批工作流 | 审批请求创建 → WebSocket 推送 → 批准/拒绝 |
| 监督面板（基础） | 活跃会话列表 + 对话只读查看 |
| Model Provider 管理 | 单厂商 CRUD + API Key 加密存储 |
| Token 统计基础 | 按用户/模型的 Token 消耗查询 API |
| **可演示：** | Agent 工具调用触发审批 → 管理员在监督面板审批 → 继续执行 |

#### M5：MVP 完整交付

| 交付物 | 说明 |
|--------|------|
| 集成测试 | 端到端场景覆盖（对话 + 编排 + 审批 + Tracing） |
| 性能测试 | 并发 10 用户、p95 API < 200ms、首 Token < 2s |
| 部署文档 | Docker Compose 一键部署指南 |
| 用户手册 | 基础使用说明（创建 Agent + 对话 + 查看执行记录） |
| **MVP 交付标准：** | 用户可在 Web 端创建多 Agent、配置 Handoff、对话交互、查看执行 Trace、触发并完成审批 |

### C.3 MVP 后迭代优先级MVP 交付后按以下优先级迭代：

| 迭代 | 功能 | 说明 |
|------|------|------|
| **v2.1** | MCP 集成 + 完整 Guardrails | 接入外部工具生态、三级护栏完整实现 |
| **v2.2** | 执行流程图 + 完整监督 + Sandbox | 可视化执行图、干预/接管模式、审批规则配置、Docker / K8s 沙箱隔离 |
| **v2.3** | Agent Team + Coordinator + 版本管理 | Team 协作协议、内置 Team 模板、Coordinator Agent、Agent 版本管理与回滚 |
| **v2.4** | Token 审计仪表盘 + 多厂商 | 完整审计页面、多模型厂商管理 |
| **v2.5** | Skill 系统 + Memory | Skill 安装/管理、跨会话记忆 |
| **v2.6** | IM 渠道 + 完整 RBAC | Telegram/Slack/企业微信、组织/团队/角色 |
| **v2.7** | APM 仪表盘 + Agent 评估 + 告警 | 指标可视化、Agent 质量度量、告警规则、成本分析 |
| **v2.8** | 定时/批量任务 + 灾备 | ScheduledRun、BatchRun、数据备份与灾难恢复 |

---

*文档版本：v2.0.9*
*最后更新：2026-04-02*
*作者：CkyClaw Team*
