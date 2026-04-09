# CkyClaw Framework

[![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-blue)](https://www.python.org)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![Typed](https://img.shields.io/badge/typing-typed-brightgreen)](https://peps.python.org/pep-0561/)

**CkyClaw Framework** 是一个声明式 Python Agent 运行时框架。它提供 Agent 定义、LLM 多模型适配、工具编排、Guardrails 护栏、Handoff 交接、Tracing 链路追踪等核心能力，让你用最少的代码构建可靠的 AI Agent。

## 核心特性

- **声明式 Agent** — 用数据类定义 Agent，指令 + 模型 + 工具 + 护栏一次声明
- **多 LLM 适配** — 基于 LiteLLM，一套代码支持 OpenAI / Claude / Gemini / 通义千问等 10+ 厂商
- **工具系统** — `@function_tool` 装饰器，自动 JSON Schema 生成，支持 ToolGroup 分组管理
- **Guardrails 三级护栏** — Input / Output / Tool 三阶段拦截，内置正则、PII、注入检测、内容安全等
- **Handoff 交接** — Agent 间任务移交，支持 InputFilter 和多级递归编排
- **Approval 审批** — suggest / auto-edit / full-auto 三种模式，可插拔审批处理器
- **Session 会话** — 内存 / PostgreSQL 后端，HistoryTrimmer 按 token 或消息数裁剪
- **Tracing 链路追踪** — 自动 Agent / LLM / Tool / Guardrail / Handoff Span，可插拔 Processor
- **Workflow 工作流** — DAG 编排 + 条件分支 + 并行 + 循环 + 重试
- **MCP 集成** — stdio / SSE / HTTP 三种传输，命名空间隔离

## 安装

```bash
pip install ckyclaw-framework
```

可选依赖：

```bash
pip install ckyclaw-framework[postgres]   # PostgreSQL Session 后端
pip install ckyclaw-framework[redis]      # Redis 缓存
pip install ckyclaw-framework[mcp]        # MCP 协议支持
```

## 快速开始

### 最简 Agent

```python
from ckyclaw_framework import Agent, Runner

agent = Agent(
    name="assistant",
    instructions="你是一个有帮助的 AI 助手。",
    model="gpt-4o-mini",
)

result = Runner.run_sync(agent, "你好，请介绍一下你自己。")
print(result.final_output)
```

### 带工具的 Agent

```python
from ckyclaw_framework import Agent, Runner, function_tool

@function_tool
async def get_weather(city: str) -> str:
    """查询指定城市的天气。"""
    return f"{city}：晴，28°C"

agent = Agent(
    name="weather-bot",
    instructions="你是天气查询助手，使用 get_weather 工具查询天气。",
    model="gpt-4o-mini",
    tools=[get_weather],
)

result = Runner.run_sync(agent, "北京今天天气怎么样？")
print(result.final_output)
```

### Guardrails 护栏

```python
from ckyclaw_framework import Agent, Runner, RegexGuardrail

no_pii = RegexGuardrail(
    name="no-phone",
    pattern=r"\d{11}",
    fail_message="检测到手机号码，已拦截。",
)

agent = Agent(
    name="safe-agent",
    instructions="你是安全助手。",
    model="gpt-4o-mini",
    input_guardrails=[no_pii],
)
```

### Handoff 多 Agent 编排

```python
from ckyclaw_framework import Agent, Handoff, Runner

translator = Agent(name="translator", instructions="将内容翻译为英文。", model="gpt-4o-mini")
reviewer = Agent(name="reviewer", instructions="审查翻译质量。", model="gpt-4o-mini")

orchestrator = Agent(
    name="orchestrator",
    instructions="根据用户需求分配任务。",
    model="gpt-4o-mini",
    handoffs=[Handoff(agent=translator), Handoff(agent=reviewer)],
)
```

## 架构概览

```
ckyclaw_framework/
├── agent/        # Agent 声明式定义
├── runner/       # Runner 执行引擎（run / run_sync / run_streamed）
├── model/        # LLM 多模型抽象（LiteLLMProvider + CostRouter）
├── tools/        # 工具系统（FunctionTool + ToolGroup + ToolRegistry）
├── guardrails/   # 三级护栏（Input / Output / Tool × 多种策略）
├── handoff/      # Agent 间交接
├── approval/     # 人工审批模式
├── session/      # 多轮会话管理
├── tracing/      # 链路追踪
├── workflow/     # DAG 工作流引擎
├── mcp/          # MCP 协议集成
├── memory/       # Agent 记忆
├── skills/       # 技能注册与注入
├── team/         # 多 Agent 团队协作
├── sandbox/      # 代码沙箱执行
├── checkpoint/   # 运行状态快照
└── evolution/    # Agent 自我进化信号收集
```

## 依赖

| 依赖 | 用途 |
|------|------|
| `litellm` | 多 LLM 厂商统一调用 |
| `pydantic` | 数据校验与 Schema 生成 |
| `pyyaml` | YAML 配置解析 |

仅 3 个核心依赖，无 Web 框架绑定，可独立嵌入任何 Python 项目。

## 开发

```bash
cd ckyclaw-framework
uv sync --extra dev
uv run pytest            # 运行测试（1300+）
uv run ruff check .      # Lint 检查
uv run mypy .            # 类型检查
```

## 许可证

MIT
