# Kasaya Framework 技术设计方案 v2.0

## 文档信息

| 字段 | 内容 |
|------|------|
| 版本 | v2.0.0 |
| 日期 | 2026-04-02 |
| 状态 | 进行中 |
| 维护人 | Kasaya Team |
| 依赖 | Kasaya PRD v2.0 |

## 目录

**Part I — 总体设计**
1. [设计目标](#一设计目标)
2. [包结构与模块划分](#二包结构与模块划分)
3. [核心接口定义](#三核心接口定义)
4. [核心工作流](#四核心工作流)
5. [扩展机制](#五扩展机制)

**Part II — 引擎与子系统**
6. [Runner 核心引擎](#六runner-核心引擎详细设计)
7. [Tracing 与 Token 审计](#七tracing-与-token-审计详细设计)
8. [工具系统](#八工具系统详细设计)
9. [Session 管理](#九session-详细设计)
10. [Guardrails 护栏](#十guardrails-详细设计)
11. [Memory 记忆](#十一memory-详细设计)
12. [Approval 审批](#十二approval-详细设计)
13. [Sandbox 沙箱](#十三sandbox-详细设计)
14. [Skills 技能](#十四skills-详细设计)

**Part III — 工程化**
15. [依赖管理](#十五依赖管理)
16. [配置体系](#十六配置体系)
17. [错误处理](#十七错误处理)
18. [测试策略](#十八测试策略)
19. [版本与发布](#十九版本与发布)

**Part IV — 高级能力**
20. [配置热更新机制](#二十配置热更新机制)
21. [Agent 国际化（i18n）支持](#二十一agent-国际化i18n支持)

**附录**
- [A. 内置 Agent 模板详细设计](#附录-a内置-agent-模板详细设计)
- [B. 与 Agents SDK 的关键差异](#附录-b与-agents-sdk-的关键差异)

---

## 一、设计目标

Kasaya Framework 是一个 **Python Agent 运行时框架**，为 Kasaya 平台提供底层 Agent 执行能力。

### 1.1 核心原则

| 原则 | 说明 |
|------|------|
| **框架无业务** | Kasaya Framework 不包含用户/组织/权限等业务概念，只提供 Agent 运行原语 |
| **声明式优先** | Agent 通过 YAML 或 Python 代码声明式定义，配置与逻辑分离 |
| **Provider-agnostic** | 不绑定任何 LLM 提供商，通过 Model 抽象层适配 |
| **可观测性内置** | Tracing 自动采集，无需额外接入 |
| **安全默认** | Guardrails 开箱即用，Approval Mode 默认可控 |
| **可嵌入** | 作为 Python 库嵌入应用，不强制独立进程 |

### 1.2 设计参考

| 来源 | 参考要素 |
|------|---------|
| OpenAI Agents SDK | Agent/Runner/Handoff/Guardrails/Session/Tracing 核心模型 |
| Codex CLI | 声明式配置、Skills 系统、三级审批模式 |
| Claude Code | Subagent 独立上下文、多级指令 (AGENTS.md)、沙箱执行 |
| DeerFlow | SOUL.md 人格定义、MCP 集成、工具分组 |

---

## 二、包结构与模块划分

### 2.1 包组织

```
kasaya-framework/
├── __init__.py                  # 公共 API 导出
├── py.typed                     # PEP 561 类型标记
│
├── agent/                       # Agent 定义与加载
│   ├── __init__.py
│   ├── agent.py                 # Agent 类
│   ├── config.py                # AgentConfig（YAML/dict → Agent）
│   └── output.py                # 结构化输出定义
│
├── runner/                      # 执行引擎
│   ├── __init__.py
│   ├── runner.py                # Runner（Agent Loop 驱动）
│   ├── run_config.py            # RunConfig 运行时覆盖
│   ├── run_context.py           # RunContext 执行上下文
│   ├── run_state.py             # RunState 序列化/恢复
│   └── result.py                # RunResult / StreamEvent
│
├── handoff/                     # Handoff 编排
│   ├── __init__.py
│   ├── handoff.py               # Handoff 定义
│   └── filters.py               # Input Filter / History Mapper
│
├── team/                        # Agent Team 协作
│   ├── __init__.py
│   ├── team.py                  # Team / TeamConfig 定义
│   ├── team_runner.py           # TeamRunner（Team 执行引擎）
│   ├── protocols.py             # TeamProtocol 策略实现
│   └── result.py                # TeamResult
│
├── tools/                       # 工具系统
│   ├── __init__.py
│   ├── function_tool.py         # @function_tool 装饰器
│   ├── hosted_tool.py           # 内置工具
│   ├── tool_group.py            # ToolGroup 分组管理
│   └── tool_context.py          # ToolContext（工具执行上下文）
│
├── mcp/                         # MCP 协议集成
│   ├── __init__.py
│   ├── server.py                # MCPServer 连接管理
│   ├── transport.py             # stdio / SSE / HTTP 传输
│   └── auth.py                  # OAuth 令牌流
│
├── guardrails/                  # 安全护栏
│   ├── __init__.py
│   ├── input_guardrail.py       # InputGuardrail
│   ├── output_guardrail.py      # OutputGuardrail
│   ├── tool_guardrail.py        # ToolGuardrail
│   └── result.py                # GuardrailResult / TripwireTriggered
│
├── session/                     # 会话管理
│   ├── __init__.py
│   ├── session.py               # Session 接口
│   ├── backends/                # 存储后端
│   │   ├── __init__.py
│   │   ├── postgres.py          # PostgreSQL 后端
│   │   ├── redis.py             # Redis 后端
│   │   └── sqlite.py            # SQLite 后端（开发用）
│   └── history.py               # 历史消息管理
│
├── tracing/                     # 链路追踪
│   ├── __init__.py
│   ├── trace.py                 # Trace 定义
│   ├── span.py                  # Span 定义（Agent/LLM/Tool/Handoff）
│   ├── processor.py             # TraceProcessor 接口
│   └── exporters/               # 导出器
│       ├── __init__.py
│       ├── console.py           # 控制台输出（调试用）
│       └── callback.py          # 回调导出（供应用层注册处理函数）
│
├── model/                       # 模型抽象层
│   ├── __init__.py
│   ├── provider.py              # ModelProvider 接口
│   ├── settings.py              # ModelSettings（temperature、max_tokens 等）
│   ├── message.py               # Message / MessageRole 定义
│   └── litellm_provider.py      # LiteLLM 适配实现
│
├── skills/                      # Skills 系统
│   ├── __init__.py
│   ├── skill.py                 # Skill 定义
│   ├── loader.py                # Skill 扫描/加载
│   └── installer.py             # .skill 归档包安装
│
├── memory/                      # 长期记忆
│   ├── __init__.py
│   ├── memory.py                # Memory 接口
│   ├── extractor.py             # 自动提取器（用户档案/事实）
│   └── backends/
│       ├── __init__.py
│       └── postgres.py          # PostgreSQL 后端
│
├── approval/                    # 审批模式
│   ├── __init__.py
│   ├── mode.py                  # ApprovalMode 枚举
│   ├── handler.py               # ApprovalHandler 接口
│   └── filter.py                # 工具调用审批过滤
│
├── sandbox/                     # 沙箱执行
│   ├── __init__.py
│   ├── sandbox.py               # Sandbox 接口
│   ├── local.py                 # 本地执行
│   ├── docker.py                # Docker 容器执行
│   └── kubernetes.py            # K8s Pod 执行
│
└── _internal/                   # 内部工具（不导出）
    ├── __init__.py
    ├── types.py                 # 通用类型定义
    └── json_schema.py           # JSON Schema 自动生成
```

### 2.2 公共 API（`kasaya-framework/__init__.py`）

```python
"""Kasaya Framework - Agent Runtime Framework"""

# === Core ===
from kasaya.agent.agent import Agent
from kasaya.runner.runner import Runner
from kasaya.runner.run_config import RunConfig
from kasaya.runner.result import RunResult, StreamEvent

# === Orchestration ===
from kasaya.handoff.handoff import Handoff
from kasaya.handoff.filters import InputFilter

# === Tools ===
from kasaya.tools.function_tool import function_tool
from kasaya.tools.tool_group import ToolGroup
from kasaya.tools.registry import ToolRegistry

# === MCP ===
from kasaya.mcp.server import MCPServer

# === Guardrails ===
from kasaya.guardrails.input_guardrail import InputGuardrail
from kasaya.guardrails.output_guardrail import OutputGuardrail
from kasaya.guardrails.tool_guardrail import ToolGuardrail

# === Session ===
from kasaya.session.session import Session
from kasaya.session.backend import SessionBackend, SessionMetadata

# === Tracing ===
from kasaya.tracing.trace import Trace
from kasaya.tracing.span import Span
from kasaya.tracing.processor import TraceProcessor

# === Model ===
from kasaya.model.provider import ModelProvider
from kasaya.model.settings import ModelSettings
from kasaya.model.message import Message, MessageRole

# === Skills ===
from kasaya.skills.skill import Skill

# === Memory ===
from kasaya.memory.memory import MemoryBackend, MemoryEntry, MemoryExtractor

# === Approval ===
from kasaya.approval.mode import ApprovalMode
from kasaya.approval.handler import ApprovalHandler

# === Sandbox ===
from kasaya.sandbox.sandbox import Sandbox
```

---

## 三、核心接口定义

### 3.1 Agent

```python
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Callable, Sequence

@dataclass
class Agent:
    """Agent 声明式定义。Agent 不是进程——它是配置。"""
    
    name: str
    """Agent 唯一标识（小写字母、数字、连字符）"""
    
    description: str = ""
    """Agent 功能描述（同时用于 Handoff/as_tool 时的 LLM 提示）"""
    
    instructions: str | Callable[[RunContext], str] = ""
    """行为指令（SOUL.md 内容）。支持字符串或动态函数。"""
    
    model: str | None = None
    """LLM 模型标识。None 时使用 RunConfig 默认模型。"""
    
    model_settings: ModelSettings | None = None
    """模型参数（temperature、max_tokens 等）"""
    
    tools: list[FunctionTool | ToolGroup] = field(default_factory=list)
    """可调用的工具列表（Function Tool + Tool Group）"""
    
    mcp_servers: list[MCPServer] = field(default_factory=list)
    """MCP Server 列表，加载后合并到 tools"""
    
    handoffs: list[Agent | Handoff] = field(default_factory=list)
    """可移交的目标 Agent 列表"""
    
    guardrails: GuardrailConfig | None = None
    """护栏配置"""
    
    output_type: type | None = None
    """结构化输出类型（Pydantic BaseModel 子类）"""
    
    approval_mode: ApprovalMode = ApprovalMode.SUGGEST
    """默认审批模式"""
    
    skills: list[Skill] = field(default_factory=list)
    """已启用的 Skill 列表"""

    def as_tool(
        self,
        tool_name: str | None = None,
        tool_description: str | None = None,
    ) -> AgentTool:
        """将此 Agent 包装为 Tool，供 Manager Agent 调用。"""
        ...

    @classmethod
    def from_yaml(cls, path: str) -> Agent:
        """从 YAML 文件加载 Agent 定义。"""
        ...

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Agent:
        """从字典加载 Agent 定义。"""
        ...
```

### 3.2 Runner

```python
from __future__ import annotations
from typing import AsyncIterator

class Runner:
    """Agent 执行引擎。驱动 Agent Loop 完成推理和工具调用。"""
    
    @staticmethod
    async def run(
        agent: Agent,
        input: str | list[Message],
        *,
        session: Session | None = None,
        config: RunConfig | None = None,
        context: dict | None = None,
        max_turns: int = 10,
    ) -> RunResult:
        """
        异步运行 Agent。
        
        Agent Loop:
        1. 组装消息（instructions + history + input）→ 发送 LLM
        2. LLM 返回:
           a. final_output → 结束，返回 RunResult
           b. handoff → 切换 Agent，回到步骤 1
           c. tool_calls → 执行工具，追加结果，回到步骤 1
        3. 超过 max_turns → 调用 on_max_turns_exceeded
        """
        ...

    @staticmethod
    def run_sync(
        agent: Agent,
        input: str | list[Message],
        **kwargs,
    ) -> RunResult:
        """同步运行（内部使用 asyncio.run）"""
        ...

    @staticmethod
    async def run_streamed(
        agent: Agent,
        input: str | list[Message],
        **kwargs,
    ) -> AsyncIterator[StreamEvent]:
        """
        异步流式运行。逐步产出 StreamEvent：
        - AgentStartEvent / AgentEndEvent
        - LLMChunkEvent（流式 Token）
        - ToolCallStartEvent / ToolCallEndEvent
        - HandoffEvent
        - RunCompleteEvent
        """
        ...
```

### 3.3 RunConfig

```python
from dataclasses import dataclass, field

@dataclass
class RunConfig:
    """运行时配置覆盖——不修改 Agent 定义。"""
    
    # 模型覆盖
    model: str | None = None
    """全局覆盖 Agent 的模型"""
    
    model_settings: ModelSettings | None = None
    """全局覆盖模型参数"""
    
    model_provider: ModelProvider | None = None
    """自定义模型提供商实例"""
    
    # 护栏覆盖
    input_guardrails: list[InputGuardrail] = field(default_factory=list)
    """追加运行级输入护栏"""
    
    output_guardrails: list[OutputGuardrail] = field(default_factory=list)
    """追加运行级输出护栏"""
    
    # Handoff 控制
    handoff_input_filter: InputFilter | None = None
    """全局 Handoff Input Filter"""
    
    # Tracing 配置
    tracing_enabled: bool = True
    """是否启用链路追踪"""
    
    workflow_name: str = "default"
    """工作流名称（用于 Trace 分组）"""
    
    trace_include_sensitive_data: bool = True
    """是否记录 LLM 和工具的输入/输出"""
    
    # 审批配置
    approval_mode: ApprovalMode | None = None
    """全局覆盖审批模式"""
    
    approval_handler: ApprovalHandler | None = None
    """自定义审批处理器"""
    
    # Session 配置
    session_backend: SessionBackend | None = None
    """Session 存储后端"""
    
    # 错误处理
    on_max_turns_exceeded: Callable | None = None
    """超过 max_turns 时的回调"""
    
    # 回调
    on_agent_start: Callable | None = None
    on_agent_end: Callable | None = None
    on_tool_call: Callable | None = None
    on_handoff: Callable | None = None
```

### 3.4 Handoff

```python
from dataclasses import dataclass
from typing import Callable, Any

@dataclass
class Handoff:
    """Agent 间的控制转移定义。"""
    
    agent: Agent
    """目标 Agent"""
    
    tool_name: str | None = None
    """暴露给 LLM 的工具名称（默认: transfer_to_{agent.name}）"""
    
    tool_description: str | None = None
    """工具描述（默认使用 agent.description）"""
    
    input_filter: InputFilter | None = None
    """消息历史过滤器"""
    
    on_handoff: Callable[[HandoffContext], Any] | None = None
    """移交回调（记日志、预取数据等）"""
    
    input_type: type | None = None
    """LLM 移交时可携带的结构化元数据类型"""
```

### 3.5 Tool 系统

```python
from typing import Callable, Any
from functools import wraps

def function_tool(
    name: str | None = None,
    description: str | None = None,
    group: str | None = None,
    namespace: str | None = None,
    approval_required: bool = False,
    timeout: float | None = None,
    failure_error_function: Callable | None = None,
    enabled: bool | Callable[..., bool] = True,
) -> Callable:
    """
    装饰器：将 Python 函数注册为 Function Tool。
    自动从函数签名和 docstring 生成 JSON Schema。
    
    Args:
        name: 工具名称（默认取函数名）
        description: 工具描述（默认取 docstring 首行）
        group: 工具组名
        namespace: 命名空间前缀（如 "github"，最终工具名为 "github::name"）
        approval_required: 是否需要审批
        timeout: 执行超时（秒），超时后返回错误消息给 LLM
        failure_error_function: 自定义错误处理函数 (ctx, error) → str
        enabled: 是否启用（可为布尔值或接受 RunContext 的动态函数）
    
    用法:
        @function_tool(group="web-search", timeout=30)
        async def search_web(query: str) -> str:
            '''搜索网页内容'''
            ...
    """
    ...


@dataclass
class ToolGroup:
    """工具组——按功能分组的工具集合。"""
    
    name: str
    """组名（如 web-search、code-executor）"""
    
    tools: list[FunctionTool] = field(default_factory=list)
    """组内工具列表"""
    
    description: str = ""
    """组描述"""

    def register(self, tool: FunctionTool) -> None:
        """注册工具到此组"""
        ...


# 内置工具组注册表
class ToolRegistry:
    """全局工具注册表。管理所有 ToolGroup 和 FunctionTool。"""
    
    _groups: dict[str, ToolGroup]
    _tools: dict[str, FunctionTool]
    
    def get_group(self, name: str) -> ToolGroup: ...
    def get_tool(self, name: str) -> FunctionTool: ...
    def register_group(self, group: ToolGroup) -> None: ...
    def list_groups(self) -> list[ToolGroup]: ...
```

### 3.6 Guardrails

```python
from dataclasses import dataclass
from typing import Callable

@dataclass
class GuardrailResult:
    """护栏检测结果"""
    tripwire_triggered: bool = False
    message: str = ""
    metadata: dict | None = None


class InputGuardrail:
    """输入护栏——Agent 执行前验证用户输入。"""
    
    def __init__(
        self,
        name: str,
        guardrail_fn: Callable[[RunContext, str | list[Message]], GuardrailResult],
        blocking: bool = False,
    ):
        self.name = name
        self.guardrail_fn = guardrail_fn
        self.blocking = blocking  # False=并行执行, True=阻塞执行


class OutputGuardrail:
    """输出护栏——Agent 输出后验证回复内容。"""
    
    def __init__(
        self,
        name: str,
        guardrail_fn: Callable[[RunContext, str], GuardrailResult],
    ):
        self.name = name
        self.guardrail_fn = guardrail_fn


class ToolGuardrail:
    """工具护栏——工具调用前后验证参数和返回值。"""
    
    def __init__(
        self,
        name: str,
        before_fn: Callable[[ToolContext, dict], GuardrailResult] | None = None,
        after_fn: Callable[[ToolContext, Any], GuardrailResult] | None = None,
    ):
        self.name = name
        self.before_fn = before_fn
        self.after_fn = after_fn
```

### 3.7 Session

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime

@dataclass
class SessionMetadata:
    """Session 元信息。"""
    session_id: str
    created_at: datetime
    updated_at: datetime
    message_count: int = 0
    total_tokens: int = 0
    last_agent_name: str | None = None
    extra: dict = field(default_factory=dict)

class SessionBackend(ABC):
    """Session 存储后端抽象。详细设计见第九章。"""
    
    @abstractmethod
    async def load(self, session_id: str) -> list[Message] | None:
        """加载会话历史消息"""
        ...
    
    @abstractmethod
    async def save(self, session_id: str, messages: list[Message]) -> None:
        """追加保存新消息"""
        ...
    
    @abstractmethod
    async def delete(self, session_id: str) -> None:
        """删除会话"""
        ...
    
    @abstractmethod
    async def list_sessions(self, **filters) -> list[SessionMetadata]:
        """列出会话（支持过滤）"""
        ...
    
    @abstractmethod
    async def load_metadata(self, session_id: str) -> SessionMetadata | None:
        """加载会话元数据"""
        ...


@dataclass
class Session:
    """会话管理器——自动处理多轮对话的历史存储与加载。"""
    
    session_id: str
    backend: SessionBackend
    metadata: SessionMetadata | None = None
    
    async def get_history(self) -> list[Message]:
        """获取完整历史"""
        ...
    
    async def append(self, messages: list[Message]) -> None:
        """追加消息并更新 metadata"""
        ...
    
    async def trim(self, strategy: HistoryTrimStrategy) -> list[Message]:
        """按策略裁剪历史（详见 9.4 节）"""
        ...
    
    async def clear(self) -> None:
        """清空历史"""
        ...
```

### 3.8 Tracing

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime

class SpanType(str, Enum):
    AGENT = "agent"
    LLM = "llm"
    TOOL = "tool"
    HANDOFF = "handoff"
    GUARDRAIL = "guardrail"

class SpanStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

@dataclass
class Span:
    """执行步骤追踪。"""
    span_id: str
    trace_id: str
    parent_span_id: str | None
    type: SpanType
    name: str
    status: SpanStatus = SpanStatus.PENDING
    start_time: datetime | None = None
    end_time: datetime | None = None
    input: Any | None = None
    output: Any | None = None
    metadata: dict = field(default_factory=dict)
    # LLM Span 专属
    token_usage: TokenUsage | None = None
    model: str | None = None

@dataclass 
class Trace:
    """一次完整执行的链路追踪。"""
    trace_id: str
    workflow_name: str
    group_id: str | None = None
    spans: list[Span] = field(default_factory=list)
    start_time: datetime | None = None
    end_time: datetime | None = None

class TraceProcessor(ABC):
    """追踪处理器接口。应用层实现此接口将数据导出到 APM 后端。"""
    
    @abstractmethod
    async def on_trace_start(self, trace: Trace) -> None: ...
    
    @abstractmethod
    async def on_span_start(self, span: Span) -> None: ...
    
    @abstractmethod
    async def on_span_end(self, span: Span) -> None: ...
    
    @abstractmethod
    async def on_trace_end(self, trace: Trace) -> None: ...
```

### 3.9 Message

```python
from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime

class MessageRole(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    TOOL = "tool"

@dataclass
class Message:
    """Agent 通信的基本单元。"""
    role: MessageRole
    content: str
    agent_name: str | None = None
    """产生此消息的 Agent（assistant/tool 角色时）"""
    tool_call_id: str | None = None
    """工具调用 ID（tool 角色时）"""
    token_usage: TokenUsage | None = None
    timestamp: datetime = field(default_factory=datetime.utcnow)
    metadata: dict = field(default_factory=dict)

@dataclass
class TokenUsage:
    """Token 消耗统计。"""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
```

### 3.10 Model Provider

```python
from abc import ABC, abstractmethod

class ModelProvider(ABC):
    """LLM 模型提供商抽象。"""
    
    @abstractmethod
    async def chat(
        self,
        model: str,
        messages: list[Message],
        *,
        settings: ModelSettings | None = None,
        tools: list[dict] | None = None,
        stream: bool = False,
    ) -> ModelResponse | AsyncIterator[ModelChunk]:
        """发送聊天请求。"""
        ...

@dataclass
class ModelSettings:
    """模型参数配置。"""
    temperature: float | None = None
    max_tokens: int | None = None
    top_p: float | None = None
    stop: list[str] | None = None
    # 模型特定参数
    extra: dict = field(default_factory=dict)

class LiteLLMProvider(ModelProvider):
    """基于 LiteLLM 的多模型适配实现。支持 100+ 模型。"""
    
    async def chat(self, model, messages, **kwargs):
        """通过 litellm.acompletion 调用。"""
        ...
```

### 3.11 Approval

```python
from enum import Enum
from abc import ABC, abstractmethod

class ApprovalMode(str, Enum):
    SUGGEST = "suggest"       # 每次操作需确认
    AUTO_EDIT = "auto-edit"   # 安全操作自动，高风险需确认
    FULL_AUTO = "full-auto"   # 完全自动

class ApprovalDecision(str, Enum):
    APPROVED = "approved"
    REJECTED = "rejected"
    TIMEOUT = "timeout"

class ApprovalHandler(ABC):
    """审批处理器接口。Kasaya 实现此接口对接审批工作流。"""
    
    @abstractmethod
    async def request_approval(
        self,
        run_context: RunContext,
        action_type: str,      # "tool_call" | "output" | "handoff"
        action_detail: dict,   # 工具名+参数 / 输出内容 / 目标 Agent
        timeout: int = 300,    # 超时秒数
    ) -> ApprovalDecision:
        """发起审批请求，等待结果。"""
        ...
```

### 3.12 Memory

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum

class MemoryType(str, Enum):
    USER_PROFILE = "user_profile"
    HISTORY_SUMMARY = "history_summary"
    STRUCTURED_FACT = "structured_fact"

@dataclass
class MemoryEntry:
    """记忆条目。"""
    id: str
    type: MemoryType
    content: str
    confidence: float = 1.0
    source_session_id: str | None = None
    metadata: dict = field(default_factory=dict)

class MemoryBackend(ABC):
    """记忆存储后端抽象。详细设计见第十一章。"""
    
    @abstractmethod
    async def store(self, user_id: str, entry: MemoryEntry) -> None: ...
    
    @abstractmethod
    async def search(
        self, user_id: str, query: str, limit: int = 10
    ) -> list[MemoryEntry]: ...
    
    @abstractmethod
    async def list_entries(
        self, user_id: str, type: MemoryType | None = None
    ) -> list[MemoryEntry]: ...
    
    @abstractmethod
    async def delete(self, entry_id: str) -> None: ...
    
    @abstractmethod
    async def delete_by_user(self, user_id: str) -> int:
        """删除指定用户的全部记忆（GDPR 合规）。"""
        ...
    
    @abstractmethod
    async def decay(self, before: datetime, rate: float) -> int:
        """对长期未更新的条目降低 confidence。"""
        ...

class MemoryExtractor:
    """自动记忆提取器——从对话中提取用户档案和结构化事实。"""
    
    async def extract(
        self, messages: list[Message]
    ) -> list[MemoryEntry]:
        """分析消息列表，提取记忆条目。"""
        ...
```

### 3.13 Sandbox

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass

@dataclass
class ExecutionResult:
    """沙箱执行结果。"""
    exit_code: int
    stdout: str
    stderr: str
    duration_ms: int

class Sandbox(ABC):
    """隔离代码执行环境。"""
    
    @abstractmethod
    async def execute(
        self,
        code: str,
        language: str = "python",
        timeout: int = 30,
        env: dict[str, str] | None = None,
    ) -> ExecutionResult:
        """在沙箱中执行代码。"""
        ...
    
    @abstractmethod
    async def cleanup(self) -> None:
        """清理沙箱资源。"""
        ...
```

---

## 四、核心工作流

### 4.1 Agent Loop（Runner.run 主流程）

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Runner.run(agent, input)                      │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  1. 初始化                                                           │
│     ├── 创建 Trace                                                   │
│     ├── 加载 Session 历史 → history                                  │
│     ├── 加载 Skills → instructions 追加                              │
│     ├── 加载 Memory → context 注入                                   │
│     └── 设置 current_agent = agent                                   │
│                                                                      │
│  2. Input Guardrails                                                 │
│     ├── blocking=True → 先执行护栏，通过后继续                         │
│     └── blocking=False → 护栏与 Agent 并行执行                        │
│     └── tripwire_triggered → 抛 InputGuardrailError，结束             │
│                                                                      │
│  3. Agent Loop                           ┌─────────────────────┐     │
│     │                                    │ turn_count += 1     │     │
│     ▼                                    │ if > max_turns:     │     │
│  ┌──────────────────────────┐            │   on_max_turns()    │     │
│  │ LLM 调用                 │            │   break             │     │
│  │ model.chat(              │            └─────────────────────┘     │
│  │   instructions           │                                        │
│  │   + history              │                                        │
│  │   + input                │                                        │
│  │   + tool_schemas         │                                        │
│  │ )                        │                                        │
│  └──────┬───────────────────┘                                        │
│         │                                                            │
│  ┌──────▼───────────────────────────────────────────────┐           │
│  │ 解析 LLM 响应                                         │           │
│  │                                                       │           │
│  │ CASE final_output:                                    │           │
│  │   ├── Output Guardrails 检查                           │           │
│  │   │   └── tripwire → 抛 OutputGuardrailError           │           │
│  │   ├── Approval Mode 检查                               │           │
│  │   │   ├── suggest → request_approval(output)           │           │
│  │   │   └── rejected → 修正或终止                         │           │
│  │   └── break，返回 RunResult                            │           │
│  │                                                       │           │
│  │ CASE handoff(target_agent):                           │           │
│  │   ├── on_handoff 回调                                 │           │
│  │   ├── input_filter 过滤历史                            │           │
│  │   ├── current_agent = target_agent                    │           │
│  │   └── continue loop                                   │           │
│  │                                                       │           │
│  │ CASE tool_calls:                                      │           │
│  │   for each tool_call:                                 │           │
│  │     ├── Tool Guardrail (before)                       │           │
│  │     │   └── tripwire → skip tool, append error        │           │
│  │     ├── Approval Mode 检查                            │           │
│  │     │   ├── suggest → request_approval(tool_call)     │           │
│  │     │   ├── auto-edit → 高风险时 request_approval     │           │
│  │     │   └── full-auto → 直接执行                      │           │
│  │     ├── 执行工具                                      │           │
│  │     ├── Tool Guardrail (after)                        │           │
│  │     └── 追加 tool result 到消息                        │           │
│  │   continue loop                                       │           │
│  └───────────────────────────────────────────────────────┘           │
│                                                                      │
│  4. 收尾                                                             │
│     ├── Session 持久化（新消息追加保存）                                │
│     ├── Memory 提取（异步）                                           │
│     ├── Trace 结束                                                   │
│     └── 返回 RunResult                                               │
└─────────────────────────────────────────────────────────────────────┘
```

### 4.2 Handoff 流程

```
当前 Agent (Triage) 执行中
        │
        │ LLM 返回: tool_call(transfer_to_refund_agent, metadata={reason: "退款请求"})
        │
        ▼
┌──────────────────────────────────────────────────────────────┐
│ Handoff 处理                                                  │
│                                                               │
│  1. 查找目标 Agent → refund_agent                             │
│  2. 执行 on_handoff 回调（如有）                               │
│     └── 记录移交原因，预取用户订单数据                           │
│  3. 应用 input_filter（如有）                                  │
│     └── 过滤历史消息（如只保留最近 N 条或去除系统指令）          │
│  4. 切换当前 Agent: current_agent = refund_agent              │
│  5. 产出 Handoff Span                                        │
│  6. 回到 Agent Loop 步骤 3                                    │
└──────────────────────────────────────────────────────────────┘
```

### 4.3 Agent-as-Tool 流程

```
Manager Agent 执行中
        │
        │ LLM 返回: tool_call(search_agent, input="Q1 销售数据")
        │
        ▼
┌──────────────────────────────────────────────────────────────┐
│ Agent-as-Tool 处理                                            │
│                                                               │
│  1. 创建子 Runner                                             │
│  2. 创建独立 RunContext（不共享 Manager 的对话历史）            │
│  3. Runner.run(search_agent, "Q1 销售数据")                   │
│  4. 等待子 Agent 完成                                         │
│  5. 将子 Agent 的 final_output 作为 tool_result 返回给 Manager │
│  6. 产出 Agent-as-Tool Span（嵌套在 Manager 的 Tool Span 下）  │
│  7. Manager 继续 Agent Loop                                   │
└──────────────────────────────────────────────────────────────┘
```

### 4.4 Streaming 事件流

```python
# StreamEvent 类型层级
class StreamEvent:
    """流式事件基类"""
    timestamp: datetime
    trace_id: str

class AgentStartEvent(StreamEvent):
    agent_name: str

class AgentEndEvent(StreamEvent):
    agent_name: str
    
class LLMChunkEvent(StreamEvent):
    """LLM 流式 Token 片段"""
    delta: str
    agent_name: str

class ToolCallStartEvent(StreamEvent):
    tool_name: str
    arguments: dict

class ToolCallEndEvent(StreamEvent):
    tool_name: str
    result: Any
    
class HandoffEvent(StreamEvent):
    from_agent: str
    to_agent: str
    metadata: dict | None

class GuardrailEvent(StreamEvent):
    guardrail_name: str
    triggered: bool
    message: str

class ApprovalRequestEvent(StreamEvent):
    action_type: str
    action_detail: dict

class RunCompleteEvent(StreamEvent):
    final_output: str | Any
    token_usage: TokenUsage
```

### 4.5 Team 执行流程

#### 4.5.1 Team 与 TeamConfig

```python
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable

class TeamProtocolType(Enum):
    SEQUENTIAL = "sequential"
    PARALLEL = "parallel"
    DEBATE = "debate"
    ROUND_ROBIN = "round_robin"
    BROADCAST = "broadcast"
    CUSTOM = "custom"

class ResultStrategy(Enum):
    LAST = "last"           # 取最后一个 Agent 的输出
    CONCAT = "concat"       # 拼接所有 Agent 的输出
    VOTE = "vote"           # 多数投票（需结构化输出）
    JUDGE = "judge"         # 由 Judge Agent 裁定
    CUSTOM = "custom"       # 自定义聚合函数

class ContextSharing(Enum):
    SEQUENTIAL = "sequential"   # 前者输出传入后者（流水线）
    SHARED = "shared"           # 共享完整上下文
    ISOLATED = "isolated"       # 各自独立上下文

@dataclass
class TeamMember:
    agent: Agent
    """成员 Agent 实例"""
    role: str = ""
    """角色说明（会注入到 Agent 的上下文中）"""
    is_judge: bool = False
    """是否为 Debate 模式的裁判（仅 debate 协议使用）"""

@dataclass
class TerminationConfig:
    max_rounds: int = 3
    """最大轮次（debate / round_robin 使用）"""
    timeout_seconds: float = 300
    """超时时间"""
    consensus_threshold: float = 0.8
    """共识阈值（debate 模式的 Judge 判定）"""

@dataclass
class TeamConfig:
    name: str
    """Team 唯一标识符"""
    display_name: str = ""
    description: str = ""
    """描述（同时作为 Team-as-Tool 的 tool_description）"""
    protocol: TeamProtocolType = TeamProtocolType.SEQUENTIAL
    members: list[TeamMember] = field(default_factory=list)
    termination: TerminationConfig = field(default_factory=TerminationConfig)
    result_strategy: ResultStrategy = ResultStrategy.LAST
    context_sharing: ContextSharing = ContextSharing.SEQUENTIAL
```

```python
@dataclass
class Team:
    """Agent Team — 将一组 Agent 封装为可复用的协作单元。"""
    config: TeamConfig

    def as_tool(
        self,
        tool_name: str | None = None,
        tool_description: str | None = None,
    ) -> TeamTool:
        """将 Team 包装为 Tool，供 Coordinator 或任何 Agent 调用。"""
        ...

    @classmethod
    def from_yaml(cls, path: str) -> Team:
        """从 YAML 文件加载 Team 定义。"""
        ...
```

#### 4.5.2 TeamRunner

TeamRunner 负责按 TeamProtocol 驱动成员 Agent 的交互。它不是新的 Runner，而是在现有 Runner 之上的编排层。

```python
class TeamRunner:
    """驱动 Team 内部的多 Agent 协作。"""

    @staticmethod
    async def run(
        team: Team,
        input: str,
        *,
        config: RunConfig | None = None,
        context: dict | None = None,
    ) -> TeamResult:
        """
        TeamRunner 执行策略:

        Sequential:
          for agent in team.members:
              result = await Runner.run(agent, current_input)
              current_input = result.final_output  # 流水线传递
          return last result

        Parallel:
          results = await asyncio.gather(
              *[Runner.run(agent, input) for agent in team.members]
          )
          return aggregate(results, team.config.result_strategy)

        Debate:
          for round in range(max_rounds):
              for agent in non_judge_members:
                  response = await Runner.run(agent, debate_context)
                  debate_context.append(response)
              verdict = await Runner.run(judge, debate_context)
              if verdict.consensus >= threshold:
                  break
          return judge final verdict

        RoundRobin:
          for round in range(max_rounds):
              for agent in team.members:
                  response = await Runner.run(agent, shared_context)
                  shared_context.append(response)
          return aggregate(shared_context, result_strategy)

        Broadcast:
          results = await asyncio.gather(
              *[Runner.run(agent, input) for agent in team.members]
          )
          return results  # 不聚合，返回全部
        """
        ...
```

```python
@dataclass
class TeamResult:
    """Team 执行结果"""
    team_name: str
    protocol: TeamProtocolType
    member_results: list[RunResult]
    """各成员 Agent 的 RunResult"""
    final_output: str | Any
    """聚合后的最终输出"""
    rounds: int
    """实际执行轮次"""
    token_usage: TokenUsage
    """Team 级别 Token 聚合"""
    trace_id: str
```

#### 4.5.3 Team-as-Tool 集成

Team-as-Tool 的执行方式与 Agent-as-Tool 一致：

```
Coordinator Agent Loop
    │
    │ LLM 返回: tool_call("team::research_report_team", input="分析 Q1 数据")
    │
    ▼
 ToolRouter 识别 "team::" 前缀
    │
    ▼
 TeamRunner.run(research_report_team, "分析 Q1 数据")
    │  ▲ (Sequential: Researcher → Analyst → Writer)
    │
    ▼
 tool_result = team_result.final_output
    │
    ▼
 Coordinator 继续 Agent Loop
```

ToolRouter 扩展规则：

| 前缀 | 路由目标 | 说明 |
|------|---------|------|
| `(无前缀)` | FunctionTool / HostedTool | 普通工具调用 |
| `agent::` | Agent.as_tool() → Runner.run() | Agent-as-Tool |
| `team::` | Team.as_tool() → TeamRunner.run() | **Team-as-Tool** |
| `mcp::` | MCP Tool | MCP 协议工具 |

#### 4.5.4 Team Span 结构

```
Trace
└── Run Span [coordinator]
    └── Agent Span [coordinator]
        └── Tool Span [team::research_report_team]    ← Team-as-Tool 调用
            └── Team Span [research_report_team]       ← TeamRunner 创建
                ├── Agent Span [researcher]
                │   ├── LLM Span
                │   └── Tool Span [web_search]
                ├── Agent Span [data_analyst]
                │   ├── LLM Span
                │   └── Tool Span [sql_query]
                └── Agent Span [report_writer]
                    └── LLM Span
```

Team Span 的 `attributes`：

| 属性 | 类型 | 说明 |
|------|------|------|
| team.name | string | Team 标识符 |
| team.protocol | string | 协作协议类型 |
| team.members | string[] | 成员 Agent 名称列表 |
| team.rounds | int | 实际执行轮次 |
| team.result_strategy | string | 结果聚合策略 |

---

## 五、扩展机制

### 5.1 扩展点一览

| 扩展点 | 接口 | 说明 | 详细设计 |
|--------|------|------|----------|
| 模型提供商 | `ModelProvider` | 实现 `chat()` 方法适配新的 LLM API | 3.10 |
| Session 后端 | `SessionBackend` | 实现 `load/save/delete` 适配新存储 | 第九章 |
| Memory 后端 | `MemoryBackend` | 实现 `store/search` 适配新存储 | 第十一章 |
| Trace 处理器 | `TraceProcessor` | 实现 `on_trace_start/end` 导出数据 | 第七章 |
| 审批处理器 | `ApprovalHandler` | 实现 `request_approval` 对接审批系统 | 第十二章 |
| 沙箱 | `Sandbox` | 实现 `execute` 适配新的隔离环境 | 第十三章 |
| 自定义工具 | `@function_tool` | 装饰器注册自定义函数工具 | 第八章 |
| 自定义护栏 | `InputGuardrail / OutputGuardrail / ToolGuardrail` | 自定义验证逻辑 | 第十章 |
| Team 协作协议 | `TeamProtocol` 子类 | 自定义 Team 内 Agent 交互策略 | 4.5 |
| Skills | `.skill` 归档包 | 安装领域知识包 | 第十四章 |

### 5.2 Kasaya 应用层集成示例

```python
from kasaya import Agent, Runner, RunConfig, Session
from kasaya.tracing.processor import TraceProcessor
from kasaya.approval.handler import ApprovalHandler

# Kasaya 实现 Trace Processor → MVP 默认导出到 PostgreSQL
class PostgresTraceProcessor(TraceProcessor):
    async def on_span_end(self, span):
        await pg_pool.execute("INSERT INTO spans ...", span.to_dict())
        if span.type == "llm":
            await pg_pool.execute("INSERT INTO token_usage_log ...", span.token_usage)

# Kasaya 实现自定义 Approval Handler → 对接审批工作流
class KasayaApprovalHandler(ApprovalHandler):
    async def request_approval(self, run_context, action_type, action_detail, timeout):
        # 写入审批队列，WebSocket 推送到监督面板
        approval = await supervision_service.create_approval(...)
        # 等待审批结果（阻塞直到审批人操作或超时）
        return await approval.wait(timeout=timeout)

# 组装运行
config = RunConfig(
    model_provider=LiteLLMProvider(),
    session_backend=PostgresSessionBackend(pool),
    approval_handler=KasayaApprovalHandler(),
    tracing_enabled=True,
)

# 注册全局 Trace Processor（MVP 默认 PostgreSQL）
tracing.add_processor(PostgresTraceProcessor())
# 可选：注册 OTel 导出（推荐生产环境启用）
# tracing.add_processor(OTelTraceProcessor(endpoint="http://otel-collector:4317"))
# 可选：注册 ClickHouse 导出（大规模分析场景）
# tracing.add_processor(ClickHouseTraceProcessor(dsn="clickhouse://..."))

# 运行 Agent
result = await Runner.run(
    agent=triage_agent,
    input="帮我退款",
    session=Session("session-123", backend=config.session_backend),
    config=config,
)
```

---

## 六、Runner 核心引擎详细设计

### 6.1 Runner 内部架构

Runner 是 Kasaya Framework 最核心的模块，负责驱动 Agent Loop。其内部分为以下子组件：

```
┌─────────────────────────────────────────────────────────────┐
│                         Runner                               │
│                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │ MessagePipe  │  │  LLMAdapter  │  │  ToolRouter  │      │
│  │ ────────────  │  │ ────────────  │  │ ────────────  │      │
│  │ 组装消息序列  │  │ 调用LLM API  │  │ 路由工具调用  │      │
│  │ 注入指令     │  │ 解析响应     │  │ 执行+超时    │      │
│  │ 历史裁剪     │  │ 流式适配     │  │ 错误处理     │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
│                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │ HandoffCtrl  │  │ GuardrailExe │  │ ApprovalGate │      │
│  │ ────────────  │  │ ────────────  │  │ ────────────  │      │
│  │ Agent切换    │  │ 护栏并行执行  │  │ 审批拦截     │      │
│  │ 历史过滤     │  │ Tripwire检测 │  │ 超时策略     │      │
│  │ 回调触发     │  │ 阻塞/非阻塞  │  │ 状态持久化   │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
│                                                              │
│  ┌──────────────────────────────────────────┐               │
│  │              TracingEmitter               │               │
│  │  自动创建/关闭 Trace 和 Span             │               │
│  └──────────────────────────────────────────┘               │
└─────────────────────────────────────────────────────────────┘
```

### 6.2 Run 状态机

每次 `Runner.run()` 创建一个 Run 实例，其生命周期遵循以下状态机：

```
                ┌─────────────┐
                │   CREATED   │  ← Runner.run() 入口
                └──────┬──────┘
                       │ 初始化 Trace、加载 Session/Skill/Memory
                       ▼
                ┌─────────────┐
           ┌────│  GUARDING   │  ← Input Guardrails 执行中
           │    └──────┬──────┘
    tripwire│          │ 通过
           ▼          ▼
    ┌──────────┐ ┌─────────────┐
    │  FAILED  │ │   RUNNING   │ ←→ Agent Loop（LLM / Tool / Handoff 循环）
    └──────────┘ └──────┬──────┘
                       │
         ┌─────────────┼─────────────┐
         ▼             ▼             ▼
  ┌──────────┐  ┌──────────┐  ┌──────────┐
  │ COMPLETED│  │ CANCELLED│  │  FAILED  │
  └──────────┘  └──────────┘  └──────────┘
         │                          │
         ▼                          ▼
  ┌──────────┐              ┌──────────┐
  │ APPROVED │              │ REJECTED │  (Approval Mode 流转)
  └──────────┘              └──────────┘
```

**状态定义：**

| 状态 | 触发条件 | 可转移至 |
|------|---------|---------|
| CREATED | `Runner.run()` 调用 | GUARDING |
| GUARDING | Input Guardrails 开始执行 | RUNNING, FAILED |
| RUNNING | Guardrails 通过，Agent Loop 执行中 | COMPLETED, FAILED, CANCELLED |
| COMPLETED | LLM 返回 final_output 且 Output Guardrails 通过 | APPROVED, REJECTED |
| FAILED | 异常（Guardrail Tripwire / LLM Error / max_turns / 未捕获异常） | - |
| CANCELLED | 外部调用 `cancel()` | - |
| APPROVED | suggest 模式下审批通过 | - |
| REJECTED | suggest 模式下审批拒绝 | RUNNING（修正后重试） |

### 6.3 MessagePipe（消息组装流水线）

MessagePipe 负责在每轮 LLM 调用前组装完整的消息序列：

```
Step 1: System Message
  ├── Agent.instructions（静态字符串 或 动态函数调用）
  ├── Skill 知识摘要注入（已启用 Skill 的名称+描述列表）
  └── Memory 上下文注入（相关记忆条目）

Step 2: History Messages
  ├── Session.load() → 历史消息列表
  └── 历史裁剪策略：
      ├── max_history_tokens: 限制历史 Token 总量
      ├── max_history_messages: 限制历史消息条数
      └── 超出时采用「保留最近 + 压缩摘要」策略

Step 3: User Input
  └── 当前用户输入消息

Step 4: Tool Schemas
  ├── 从 ToolRegistry 加载 Agent.tool_groups 指定的工具
  ├── 加载 Agent.mcp_servers 的 MCP 工具
  ├── 加载 Handoff 目标（作为特殊 tool）
  └── 工具数 > deferred_threshold → 替换为 ToolSearchTool
```

### 6.4 LLMAdapter（模型调用适配）

LLMAdapter 封装 LLM API 调用细节，通过 LiteLLM 适配多厂商：

```python
class LLMAdapter:
    """LLM 调用适配器。"""
    
    async def chat(
        self, 
        messages: list[Message],
        tools: list[ToolSchema] | None,
        model: str,
        model_settings: ModelSettings,
        stream: bool = False,
    ) -> LLMResponse | AsyncIterator[LLMChunk]:
        """
        调用 LLM。
        
        内部流程:
        1. Message 列表 → LiteLLM 消息格式转换
        2. ToolSchema 列表 → OpenAI function calling 格式
        3. 调用 litellm.acompletion() 或 litellm.acompletion(stream=True)
        4. 解析响应 → LLMResponse(content, tool_calls, finish_reason)
        5. 提取 token_usage → 写入当前 LLM Span
        """
        ...

@dataclass
class LLMResponse:
    """LLM 调用结果。"""
    content: str | None          # 文本内容
    tool_calls: list[ToolCall]   # 工具调用请求
    finish_reason: str           # stop / tool_calls / length
    token_usage: TokenUsage      # Token 消耗

@dataclass
class TokenUsage:
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
```

### 6.5 ToolRouter（工具路由与执行）

ToolRouter 负责将 LLM 返回的 `tool_calls` 路由到正确的工具并执行：

```python
class ToolRouter:
    """工具路由器。"""
    
    _registry: ToolRegistry
    _mcp_manager: MCPManager
    
    async def execute_tool_calls(
        self,
        tool_calls: list[ToolCall],
        context: RunContext,
    ) -> list[ToolResult]:
        """
        批量执行工具调用。
        
        内部流程:
        1. 对每个 tool_call:
           a. 解析 namespace → 确定工具来源
              ├── 无 namespace → 查找 ToolRegistry
              ├── mcp_server:: → 通过 MCPManager 转发
              └── agent:: → 通过 Agent.as_tool() 执行
           b. 执行 Tool Guardrail (before)
              └── tripwire → 产出错误 ToolResult，跳过执行
           c. Approval 检查
              └── suggest/auto-edit 模式 → 等待审批
           d. 带超时执行工具
              ├── 成功 → ToolResult(output=result)
              ├── 超时 → ToolResult(output=timeout_message)
              └── 异常 → failure_error_function 转换 或 默认错误消息
           e. 执行 Tool Guardrail (after)
           f. 产出 Tool Span
        2. 返回 ToolResult 列表
        """
        ...
```

### 6.6 Error Recovery 策略

| 错误类型 | Runner 行为 | 可恢复 |
|---------|------------|-------|
| LLM API 临时错误（429/5xx） | 指数退避重试（最多 3 次） | ✅ |
| LLM API 认证错误（401/403） | 立即终止，抛 `ModelProviderError` | ❌ |
| LLM 返回格式异常 | 忽略本轮响应，retry 本轮（最多 2 次） | ✅ |
| 工具执行异常 | 错误信息作为 tool_result 返回 LLM | ✅ |
| 工具执行超时 | 超时消息作为 tool_result 返回 LLM | ✅ |
| MCP Server 断连 | 尝试重连 1 次，仍失败则返回错误给 LLM | ✅ |
| 护栏 Tripwire 触发 | 终止 Run，抛对应 GuardrailError | ❌ |
| max_turns 超限 | 调用 `on_max_turns_exceeded` 回调，终止 | ❌ |
| Approval 拒绝 | 终止或修正后重试（取决于 rejection policy） | 可选 |
| Approval 超时 | 执行 `timeout_policy`（reject/approve/escalate） | 可选 |

### 6.7 并发与资源管理

| 资源 | 管理策略 |
|------|---------|
| LLM 连接 | `httpx.AsyncClient` 连接池，per-provider 实例复用 |
| MCP 连接 | 长连接保持，断线自动重连，空闲超时关闭 |
| 并发 Run | Runner 无状态，可多实例并行；并发度由应用层（Kasaya）控制 |
| 内存 | 消息历史按需加载；大上下文通过 Prompt 压缩策略控制 |
| Trace 写入 | 异步批量写入，不阻塞 Agent Loop |

### 6.8 RunnerHooks（生命周期钩子）

Runner 在执行关键节点触发 Lifecycle Hooks，应用层通过 `RunConfig.hooks` 注入。

```python
@dataclass
class RunnerHooks:
    """Runner 生命周期 Hook 集合。所有 Hook 均为可选的异步回调。"""
    
    # Run 级别
    on_run_start: Callable[[RunContext], Awaitable[None]] | None = None
    on_run_end: Callable[[RunContext, RunResult | Exception], Awaitable[None]] | None = None
    
    # Agent 级别
    on_agent_start: Callable[[RunContext, Agent], Awaitable[None]] | None = None
    on_agent_end: Callable[[RunContext, Agent], Awaitable[None]] | None = None
    
    # LLM 调用级别
    on_llm_start: Callable[[RunContext, list[Message]], Awaitable[None]] | None = None
    on_llm_end: Callable[[RunContext, LLMResponse], Awaitable[None]] | None = None
    
    # Tool 调用级别
    on_tool_start: Callable[[RunContext, ToolCall], Awaitable[None]] | None = None
    on_tool_end: Callable[[RunContext, ToolCall, ToolResult], Awaitable[None]] | None = None
    
    # Handoff 级别
    on_handoff: Callable[[RunContext, Agent, Agent], Awaitable[None]] | None = None
    
    # 错误处理
    on_error: Callable[[RunContext, Exception], Awaitable[None]] | None = None
```

**RunConfig 集成：**

```python
@dataclass
class RunConfig:
    # ... 现有字段 ...
    hooks: RunnerHooks | None = None
    """生命周期 Hook 集合。"""
```

**执行语义：**

| 规则 | 说明 |
|------|------|
| 非阻塞 | Hook 异步执行，使用 `asyncio.shield()` 保护，异常被捕获并记录日志，不中断 Agent Loop |
| 执行顺序 | 同一触发点的多个 Hook 按注册顺序依次触发（非并行） |
| 与 Guardrails 区别 | Hook 无拦截能力（纯观察/通知）；Guardrails 可终止执行 |
| 与 TraceProcessor 区别 | TraceProcessor 仅处理 Span 数据导出；Hook 可访问完整 RunContext 和业务对象 |
| 超时 | 单个 Hook 执行超过 5s 自动取消并记录 warning 日志 |

**Runner 主循环中的 Hook 触发位置：**

```
Runner.run(agent, input, config)
│
├── hooks.on_run_start(run_context)                    ← Run 开始
│
├── Input Guardrails 执行
│
├── Agent Loop 开始
│   │
│   ├── hooks.on_agent_start(ctx, current_agent)       ← Agent 切入
│   │
│   ├── MessagePipe 组装消息
│   ├── hooks.on_llm_start(ctx, messages)              ← LLM 调用前
│   ├── LLMAdapter.call()
│   ├── hooks.on_llm_end(ctx, llm_response)            ← LLM 返回后
│   │
│   ├── if tool_calls:
│   │   ├── hooks.on_tool_start(ctx, tool_call)        ← 每个工具调用前
│   │   ├── ToolRouter.execute()
│   │   └── hooks.on_tool_end(ctx, tool_call, result)  ← 每个工具调用后
│   │
│   ├── if handoff:
│   │   ├── hooks.on_handoff(ctx, from_agent, to_agent)← 移交时
│   │   └── hooks.on_agent_end(ctx, from_agent)        ← 旧 Agent 结束
│   │
│   └── if final_output:
│       └── hooks.on_agent_end(ctx, current_agent)     ← Agent 结束
│
├── Output Guardrails 执行
│
├── hooks.on_run_end(ctx, result)                      ← Run 正常结束
│
└── (异常路径) hooks.on_error(ctx, exc)                ← 异常触发
    └── hooks.on_run_end(ctx, exc)
```

**Kasaya 应用层典型 Hook 使用：**

| Hook | Kasaya 应用层用途 |
|------|-------------------|
| `on_run_start` | 执行权限校验（用户对 Agent 的 RBAC 权限）、预算预检查 |
| `on_run_end` | 写入执行记录、推送完成通知 |
| `on_tool_start` | 敏感工具审计日志、额外参数校验 |
| `on_handoff` | Agent 切换审计、目标 Agent 可见性校验 |
| `on_error` | 统一错误上报、告警触发 |

---

## 七、Tracing 与 Token 审计详细设计

### 7.1 Span 生命周期

Runner 在 Agent Loop 的关键节点自动创建和关闭 Span：

```
Agent Loop 开始
│
├── create Agent Span (type=AGENT, name=current_agent.name)
│   │
│   ├── LLM 调用
│   │   └── create LLM Span (type=LLM, name=model)
│   │       ├── start_time = now()
│   │       ├── input = messages (if trace_include_sensitive_data)
│   │       ├── ... LLM API 调用 ...
│   │       ├── output = response (if trace_include_sensitive_data)
│   │       ├── token_usage = {prompt, completion, total}
│   │       ├── model = "gpt-4o"
│   │       └── end_time = now(), status = COMPLETED
│   │
│   ├── Tool 调用
│   │   └── create Tool Span (type=TOOL, name=tool_name)
│   │       ├── input = arguments
│   │       ├── ... 工具执行 ...
│   │       ├── output = result
│   │       └── status = COMPLETED / FAILED
│   │
│   ├── Handoff
│   │   └── create Handoff Span (type=HANDOFF, name=target_agent)
│   │       └── metadata = {from: current, to: target, reason: ...}
│   │
│   └── Guardrail
│       └── create Guardrail Span (type=GUARDRAIL, name=guardrail_name)
│           └── metadata = {triggered: bool, message: ...}
│
└── close Agent Span
```

每个 Span 创建/结束时，TracingEmitter 同步调用所有已注册的 `TraceProcessor.on_span_start/end`。

### 7.2 OTelTraceProcessor 设计

```python
class OTelTraceProcessor(TraceProcessor):
    """将 Kasaya Framework Span 转换为 OTel Span 并通过 OTLP 导出。"""
    
    def __init__(
        self,
        endpoint: str = "http://localhost:4317",  # OTel Collector gRPC
        protocol: str = "grpc",                    # grpc | http
        resource_attributes: dict | None = None,   # service.name, etc.
        batch_size: int = 100,
        flush_interval: float = 5.0,               # 秒
    ): ...

    async def on_span_end(self, span: Span) -> None:
        """
        转换逻辑:
        1. span.trace_id → W3C trace_id (32 hex chars)
        2. span.span_id → W3C span_id (16 hex chars)
        3. span.type → OTel Span attributes:
           - agent → kind=INTERNAL, attributes={agent.name, agent.model}
           - llm → kind=CLIENT, attributes={gen_ai.system, gen_ai.request.model, 
                    gen_ai.usage.prompt_tokens, gen_ai.usage.completion_tokens}
           - tool → kind=INTERNAL, attributes={tool.name, tool.namespace}
           - handoff → kind=INTERNAL, attributes={handoff.from, handoff.to}
        4. 写入发送队列 → 达到 batch_size 或 flush_interval 触发批量发送
        """
        ...
```

**OTel 语义约定映射：**

| Kasaya Span 字段 | OTel Attribute | 说明 |
|-------------------|---------------|------|
| `span.type = llm` | `gen_ai.system` | "openai" / "anthropic" |
| `span.model` | `gen_ai.request.model` | 模型标识 |
| `span.token_usage.prompt_tokens` | `gen_ai.usage.prompt_tokens` | OTel GenAI 语义约定 |
| `span.token_usage.completion_tokens` | `gen_ai.usage.completion_tokens` | OTel GenAI 语义约定 |
| `span.type = tool` | `tool.name` | 工具名称（含 namespace） |
| `span.type = agent` | `agent.name` | 自定义属性 |

### 7.3 PostgresTraceProcessor 设计（MVP 默认）

```python
class PostgresTraceProcessor(TraceProcessor):
    """将 Span 数据写入 PostgreSQL，同时提取 LLM Span 的 token_usage 写入审计表。
    作为 MVP 默认 TraceProcessor，无需额外基础设施依赖。"""
    
    def __init__(
        self,
        pool: asyncpg.Pool,                        # PostgreSQL 连接池
        batch_size: int = 200,
        flush_interval: float = 2.0,               # 秒
    ): ...

    async def on_span_end(self, span: Span) -> None:
        """
        双写逻辑:
        1. 写入 spans 表（所有类型 Span）
        2. 若 span.type == LLM:
           a. 从 span.token_usage 提取 Token 数据
           b. 从 RunContext 提取 user_id, org_id, team_id
           c. 从 ModelConfig 查找 pricing → 计算 cost_usd
           d. 写入 token_usage_log 表
        """
        ...
```

**PostgreSQL 表结构：**

```sql
-- Span 详情表
CREATE TABLE spans (
    trace_id       UUID NOT NULL,
    span_id        UUID NOT NULL,
    parent_span_id UUID,
    type           VARCHAR(20) NOT NULL,  -- agent / llm / tool / handoff / guardrail
    name           VARCHAR(255) NOT NULL,
    status         VARCHAR(20) NOT NULL,  -- pending / running / completed / failed / cancelled
    start_time     TIMESTAMPTZ NOT NULL,
    end_time       TIMESTAMPTZ,
    duration_ms    INTEGER,
    input          JSONB,                 -- 可脱敏
    output         JSONB,                 -- 可脱敏
    token_usage    JSONB,                 -- {prompt_tokens, completion_tokens, total_tokens}
    model          VARCHAR(100),
    metadata       JSONB DEFAULT '{}',
    org_id         UUID NOT NULL,
    created_at     TIMESTAMPTZ DEFAULT now(),
    PRIMARY KEY (trace_id, span_id)
) PARTITION BY RANGE (created_at);

-- 按月分区（pg_partman 管理）
-- 保留 90 天在线数据，超期归档到对象存储

-- Token 审计日志表
CREATE TABLE token_usage_log (
    id                BIGSERIAL PRIMARY KEY,
    trace_id          UUID NOT NULL,
    span_id           UUID NOT NULL,
    user_id           UUID NOT NULL,
    org_id            UUID NOT NULL,
    team_id           UUID,
    agent_name        VARCHAR(255) NOT NULL,
    model             VARCHAR(100) NOT NULL,
    provider          VARCHAR(100) NOT NULL,
    prompt_tokens     INTEGER NOT NULL,
    completion_tokens INTEGER NOT NULL,
    total_tokens      INTEGER NOT NULL,
    cost_usd          NUMERIC(12,6) NOT NULL,
    session_id        UUID NOT NULL,
    run_id            UUID NOT NULL,
    timestamp         TIMESTAMPTZ NOT NULL
) PARTITION BY RANGE (timestamp);

-- 统计聚合表（pg_cron 定时刷新，每 5 分钟增量聚合）
CREATE TABLE token_usage_summary (
    org_id                UUID NOT NULL,
    period_date           DATE NOT NULL,
    user_id               UUID NOT NULL,
    model                 VARCHAR(100) NOT NULL,
    provider              VARCHAR(100) NOT NULL,
    agent_name            VARCHAR(255) NOT NULL,
    total_prompt_tokens   BIGINT DEFAULT 0,
    total_completion_tokens BIGINT DEFAULT 0,
    total_tokens          BIGINT DEFAULT 0,
    total_cost            NUMERIC(14,6) DEFAULT 0,
    request_count         INTEGER DEFAULT 0,
    updated_at            TIMESTAMPTZ DEFAULT now(),
    PRIMARY KEY (org_id, period_date, user_id, model, agent_name)
);

-- 索引
CREATE INDEX idx_spans_trace ON spans (trace_id);
CREATE INDEX idx_spans_org_time ON spans (org_id, created_at DESC);
CREATE INDEX idx_token_log_org_time ON token_usage_log (org_id, timestamp DESC);
CREATE INDEX idx_token_log_user ON token_usage_log (user_id, timestamp DESC);
CREATE INDEX idx_token_summary_org_date ON token_usage_summary (org_id, period_date DESC);
```

### 7.4 ClickHouseTraceProcessor 设计（可选：大规模分析场景）

> **适用场景：** 当 Trace/Token 数据规模超过 PostgreSQL 负载能力（日均 > 100 万 Span 或 > 50 万 Token 审计记录）时，可引入 ClickHouse 作为专用分析存储。MVP 阶段不需要部署。

```python
class ClickHouseTraceProcessor(TraceProcessor):
    """将 Span 数据写入 ClickHouse，同时提取 LLM Span 的 token_usage 写入审计表。"""
    
    def __init__(
        self,
        dsn: str,                                  # ClickHouse 连接串
        batch_size: int = 500,
        flush_interval: float = 2.0,               # 秒
    ): ...

    async def on_span_end(self, span: Span) -> None:
        """
        双写逻辑:
        1. 写入 spans 表（所有类型 Span）
        2. 若 span.type == LLM:
           a. 从 span.token_usage 提取 Token 数据
           b. 从 RunContext 提取 user_id, org_id, team_id
           c. 从 ModelConfig 查找 pricing → 计算 cost_usd
           d. 写入 token_usage_log 表
        """
        ...
```

**ClickHouse 表结构：**

```sql
-- Span 详情表
CREATE TABLE spans (
    trace_id     String,
    span_id      String,
    parent_span_id Nullable(String),
    type         Enum8('agent'=1, 'llm'=2, 'tool'=3, 'handoff'=4, 'guardrail'=5),
    name         String,
    status       Enum8('pending'=1, 'running'=2, 'completed'=3, 'failed'=4, 'cancelled'=5),
    start_time   DateTime64(3),
    end_time     Nullable(DateTime64(3)),
    duration_ms  Nullable(UInt32),
    input        Nullable(String),    -- JSON, 可脱敏
    output       Nullable(String),    -- JSON, 可脱敏
    token_usage  Nullable(String),    -- JSON: {prompt_tokens, completion_tokens, total_tokens}
    model        Nullable(String),
    metadata     String DEFAULT '{}', -- JSON
    org_id       String,
    _timestamp   DateTime DEFAULT now()
) ENGINE = MergeTree()
PARTITION BY toYYYYMM(_timestamp)
ORDER BY (org_id, trace_id, start_time);

-- Token 审计日志表
CREATE TABLE token_usage_log (
    trace_id          String,
    span_id           String,
    user_id           String,
    org_id            String,
    team_id           String,
    agent_name        String,
    model             String,
    provider          String,
    prompt_tokens     UInt32,
    completion_tokens UInt32,
    total_tokens      UInt32,
    cost_usd          Decimal64(6),
    session_id        String,
    run_id            String,
    timestamp         DateTime64(3)
) ENGINE = MergeTree()
PARTITION BY (org_id, toYYYYMM(timestamp))
ORDER BY (org_id, timestamp, agent_name);

-- 统计聚合物化视图（按用户+模型+日）
CREATE MATERIALIZED VIEW token_usage_daily_mv
ENGINE = AggregatingMergeTree()
PARTITION BY toYYYYMM(day)
ORDER BY (org_id, day, user_id, model)
AS SELECT
    org_id,
    toDate(timestamp) AS day,
    user_id,
    model,
    provider,
    agent_name,
    sumState(prompt_tokens)     AS total_prompt_tokens,
    sumState(completion_tokens) AS total_completion_tokens,
    sumState(total_tokens)      AS total_tokens,
    sumState(cost_usd)          AS total_cost,
    countState()                AS request_count
FROM token_usage_log
GROUP BY org_id, day, user_id, model, provider, agent_name;
```

### 7.5 敏感数据控制

| 配置 | 默认 | 说明 |
|------|------|------|
| `trace_include_sensitive_data` | `True` | 是否记录 LLM input/output 和 Tool input/output |
| 脱敏策略 | 无 | `trace_include_sensitive_data=False` 时，input/output 字段不写入存储 |
| PostgreSQL 分区保留 | 90 天 | Span 详情数据过期归档；token_usage_summary 保留 2 年 |
| ClickHouse TTL（可选） | 90 天 | 启用 ClickHouse 时，Span 详情数据过期删除；聚合物化视图保留 2 年 |
| OTel 导出 | 遵从配置 | OTelTraceProcessor 同样遵守 `trace_include_sensitive_data` 设置 |

---

## 八、工具系统详细设计

### 8.1 ToolRegistry 与 Namespace

```python
class ToolRegistry:
    """全局工具注册表。支持命名空间隔离。"""
    
    _groups: dict[str, ToolGroup]
    _tools: dict[str, FunctionTool]       # key = qualified_name（含 namespace）
    _namespaces: dict[str, list[str]]     # namespace → tool_names
    
    def register(
        self,
        tool: FunctionTool,
        namespace: str | None = None,
    ) -> None:
        """
        注册工具。
        - 若指定 namespace，工具名变为 "{namespace}::{tool.name}"
        - 同一 namespace 内不允许重名
        - 不同 namespace 允许同名
        """
        ...

    def get_tool(self, qualified_name: str) -> FunctionTool:
        """按 qualified_name 查找（如 "github::create_issue"）"""
        ...

    def get_tools_by_namespace(self, namespace: str) -> list[FunctionTool]:
        """获取某 namespace 下所有工具"""
        ...

    def get_tools_for_agent(self, agent: Agent) -> list[FunctionTool]:
        """
        为 Agent 组装工具列表：
        1. 加载 agent.tool_groups 指定组的工具
        2. 加载 agent.mcp_servers 的 MCP 工具（自动加 namespace）
        3. 加载 agent.skills 注入的工具（自动加 namespace）
        4. 添加 agent.handoffs 作为特殊 tool
        5. 若总数 > deferred_threshold → 替换为 ToolSearchTool
        """
        ...
```

### 8.2 ToolSearchTool（延迟加载）

```python
class ToolSearchTool:
    """元工具——LLM 通过搜索按需加载具体工具。"""
    
    _registry: ToolRegistry
    _agent_tools: list[FunctionTool]    # 该 Agent 的全量工具列表
    _loaded_tools: set[str]             # 本次 Run 已加载的工具名
    _search_index: SearchIndex          # 基于工具 name+description 的搜索索引
    
    def __init__(
        self,
        registry: ToolRegistry,
        agent_tools: list[FunctionTool],
        top_k: int = 5,
        strategy: str = "hybrid",        # keyword | semantic | hybrid
    ): 
        # 构建搜索索引
        self._search_index = self._build_index(agent_tools)
    
    @function_tool(name="search_tools", description="搜索可用工具。返回匹配的工具名称和描述。")
    async def search_tools(self, query: str) -> str:
        """
        内部流程:
        1. 在 _search_index 中搜索 query
        2. 返回 Top-K 匹配的工具名称+描述
        3. Runner 将这些工具的完整 Schema 注入下一轮 Prompt
        4. 记录已加载工具到 _loaded_tools（同一 Run 内缓存）
        """
        ...
    
    def _build_index(self, tools: list[FunctionTool]) -> SearchIndex:
        """
        搜索策略:
        - keyword: TF-IDF on name + description
        - semantic: 预计算工具描述的 embedding（若配置了 embedding model）
        - hybrid: keyword + semantic 混合排名
        """
        ...
```

### 8.3 MCP 集成详细设计

```python
class MCPManager:
    """MCP Server 连接管理器。"""
    
    _connections: dict[str, MCPConnection]  # server_name → 连接实例
    
    async def connect(self, config: MCPServerConfig) -> MCPConnection:
        """
        建立 MCP 连接:
        - stdio: 启动子进程，通过 stdin/stdout 通信
        - sse: 建立 SSE 长连接
        - http: 初始化 HTTP client
        """
        ...
    
    async def discover_tools(self, server_name: str) -> list[FunctionTool]:
        """
        发现 MCP Server 工具:
        1. 调用 mcp.list_tools()
        2. 遍历结果，将每个 MCP tool 封装为 FunctionTool
        3. 自动添加 namespace = server_name
        4. 注册到 ToolRegistry
        """
        ...
    
    async def call_tool(
        self, 
        server_name: str, 
        tool_name: str, 
        arguments: dict,
    ) -> Any:
        """通过 MCP 协议调用远程工具"""
        ...

@dataclass
class MCPServerConfig:
    name: str
    transport: str              # stdio | sse | http
    command: str | None = None  # stdio 模式的命令
    url: str | None = None      # sse/http 模式的 URL
    auth: MCPAuth | None = None # 认证配置
    env: dict = field(default_factory=dict)  # 环境变量
```

### 8.4 工具执行流水线

每次工具调用经过完整的流水线：

```
LLM 返回 tool_call(name, arguments)
        │
        ▼
┌──────────────────────────────┐
│ 1. Namespace 解析             │
│    "github::create_issue"    │
│    → namespace = "github"    │
│    → tool_name = "create_issue" │
└──────────┬───────────────────┘
           ▼
┌──────────────────────────────┐
│ 2. 工具查找                   │
│    ├── Function Tool → 本地   │
│    ├── MCP Tool → MCPManager  │
│    └── Agent Tool → Runner    │
└──────────┬───────────────────┘
           ▼
┌──────────────────────────────┐
│ 3. Tool Guardrail (before)   │
│    ├── pass → 继续            │
│    └── tripwire → 返回错误    │
└──────────┬───────────────────┘
           ▼
┌──────────────────────────────┐
│ 4. Approval 检查              │
│    ├── full-auto → 跳过       │
│    ├── auto-edit + 非高风险 → 跳过 │
│    └── 需审批 → 等待审批结果   │
└──────────┬───────────────────┘
           ▼
┌──────────────────────────────┐
│ 5. 带超时执行                 │
│    asyncio.wait_for(         │
│      tool.execute(args),     │
│      timeout=tool.timeout    │
│    )                         │
│    ├── 成功 → result          │
│    ├── 超时 → TimeoutError    │
│    └── 异常 → Exception       │
└──────────┬───────────────────┘
           ▼
┌──────────────────────────────┐
│ 6. 错误处理                   │
│    ├── 成功 → ToolResult(ok)  │
│    ├── 异常 → failure_error_  │
│    │   function(ctx, err)     │
│    │   → ToolResult(error_msg)│
│    └── 无自定义 → 默认错误消息 │
└──────────┬───────────────────┘
           ▼
┌──────────────────────────────┐
│ 7. Tool Guardrail (after)    │
│    验证返回值                 │
└──────────┬───────────────────┘
           ▼
┌──────────────────────────────┐
│ 8. 产出 Tool Span            │
│    记录 input/output/duration │
└──────────────────────────────┘
```

---

## 九、Session 详细设计

### 9.1 Session 管理架构

Session 模块负责多轮对话状态的持久化。其内部分为以下子组件：

```
┌─────────────────────────────────────────────────────────────┐
│                      Session 模块                            │
│                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │ Session      │  │ SessionBackend│  │ HistoryTrimmer│     │
│  │ ────────────  │  │ ────────────  │  │ ────────────  │     │
│  │ 对话状态容器  │  │ 存储抽象     │  │ 历史裁剪     │      │
│  │ 消息追加/读取 │  │ CRUD 操作    │  │ 摘要压缩     │      │
│  │ 元数据管理   │  │ 多后端适配   │  │ Token 预算   │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
└─────────────────────────────────────────────────────────────┘
```

**Session 生命周期：**

```
  ┌──────────┐    Runner.run() 时      ┌──────────┐
  │ CREATED  │ ──── load history ────→ │  ACTIVE  │
  └──────────┘                         └────┬─────┘
                                            │
                              ┌──────────────┼──────────────┐
                              ▼              ▼              ▼
                       ┌──────────┐  ┌──────────┐  ┌──────────┐
                       │  ACTIVE  │  │ EXPIRED  │  │ ARCHIVED │
                       │ (继续)   │  │ (TTL 到期)│  │ (手动)   │
                       └──────────┘  └──────────┘  └──────────┘
```

### 9.2 Session 数据模型（框架层）

框架层 Session 聚焦于消息历史管理，不涉及业务实体（user_id / org_id 由 Kasaya 应用层维护）：

```python
@dataclass
class SessionMetadata:
    """Session 元信息。"""
    session_id: str
    created_at: datetime
    updated_at: datetime
    message_count: int = 0
    total_tokens: int = 0          # 历史消息累计 Token 数
    last_agent_name: str | None = None
    extra: dict = field(default_factory=dict)  # 应用层可注入自定义字段

@dataclass
class Session:
    """对话会话。"""
    session_id: str
    backend: SessionBackend
    metadata: SessionMetadata | None = None

    async def get_history(self) -> list[Message]:
        """获取完整历史"""
        ...

    async def append(self, messages: list[Message]) -> None:
        """追加消息并更新 metadata"""
        ...

    async def trim(self, strategy: HistoryTrimStrategy) -> list[Message]:
        """按策略裁剪历史，返回裁剪后的消息列表"""
        ...

    async def clear(self) -> None:
        """清空历史"""
        ...
```

### 9.3 SessionBackend 实现规范

```python
class SessionBackend(ABC):
    """Session 存储后端抽象。"""

    @abstractmethod
    async def load(self, session_id: str) -> list[Message] | None: ...

    @abstractmethod
    async def save(self, session_id: str, messages: list[Message]) -> None: ...

    @abstractmethod
    async def delete(self, session_id: str) -> None: ...

    @abstractmethod
    async def list_sessions(self, **filters) -> list[SessionMetadata]: ...

    @abstractmethod
    async def load_metadata(self, session_id: str) -> SessionMetadata | None: ...
```

**PostgresSessionBackend：**

```sql
-- 消息存储表
CREATE TABLE session_messages (
    id          BIGSERIAL PRIMARY KEY,
    session_id  VARCHAR(128) NOT NULL,
    role        VARCHAR(16)  NOT NULL,     -- user / assistant / system / tool
    content     TEXT         NOT NULL,
    agent_name  VARCHAR(64),
    tool_call_id VARCHAR(64),
    token_count INTEGER      DEFAULT 0,
    metadata    JSONB        DEFAULT '{}',
    created_at  TIMESTAMPTZ  DEFAULT now(),
    CONSTRAINT idx_session_messages UNIQUE (session_id, id)
);

CREATE INDEX idx_session_messages_session ON session_messages(session_id, created_at);

-- 元数据表
CREATE TABLE session_metadata (
    session_id    VARCHAR(128) PRIMARY KEY,
    message_count INTEGER      DEFAULT 0,
    total_tokens  INTEGER      DEFAULT 0,
    last_agent    VARCHAR(64),
    extra         JSONB        DEFAULT '{}',
    created_at    TIMESTAMPTZ  DEFAULT now(),
    updated_at    TIMESTAMPTZ  DEFAULT now()
);
```

**RedisSessionBackend：**

| Key Pattern | 类型 | 说明 |
|-------------|------|------|
| `session:{id}:messages` | List (JSON) | 消息列表，RPUSH 追加 |
| `session:{id}:meta` | Hash | message_count / total_tokens / updated_at |
| `session:{id}` | TTL | 全局 TTL（如 7 天），通过 EXPIRE 设置 |

```python
class RedisSessionBackend(SessionBackend):
    """Redis 存储后端——适合低延迟、短生命周期会话。"""

    async def save(self, session_id: str, messages: list[Message]) -> None:
        """
        RPUSH session:{id}:messages [msg1_json, msg2_json, ...]
        HINCRBY session:{id}:meta message_count len(messages)
        EXPIRE session:{id}:messages ttl
        """
        ...

    async def load(self, session_id: str) -> list[Message] | None:
        """LRANGE session:{id}:messages 0 -1"""
        ...
```

**InMemorySessionBackend（测试用）：**

```python
class InMemorySessionBackend(SessionBackend):
    """内存存储后端——仅用于单元测试和本地开发。"""
    _store: dict[str, list[Message]] = {}
```

### 9.4 历史裁剪策略

MessagePipe（6.3 节）在每轮 LLM 调用前调用 HistoryTrimmer，确保上下文不超限：

```python
class HistoryTrimStrategy(str, Enum):
    SLIDING_WINDOW = "sliding_window"     # 保留最近 N 条
    TOKEN_BUDGET = "token_budget"         # 保留最近 N Token
    SUMMARY_PREFIX = "summary_prefix"     # 摘要 + 最近消息

@dataclass
class HistoryTrimConfig:
    strategy: HistoryTrimStrategy = HistoryTrimStrategy.TOKEN_BUDGET
    max_history_tokens: int = 8000        # Token 预算
    max_history_messages: int = 100       # 消息条数上限
    summary_model: str | None = None      # 摘要使用的模型（默认 = Agent 模型）
    keep_recent: int = 10                 # SUMMARY_PREFIX 策略保留最近消息数

class HistoryTrimmer:
    """历史裁剪器。"""

    async def trim(
        self,
        messages: list[Message],
        config: HistoryTrimConfig,
        model_provider: ModelProvider | None = None,
    ) -> list[Message]:
        """
        裁剪流程:
        1. SLIDING_WINDOW → 保留最后 max_history_messages 条
        2. TOKEN_BUDGET   → 从最新消息向前累加 Token，超出 max_history_tokens 截断
        3. SUMMARY_PREFIX → 超出预算时：
           a. 将早期消息交给 LLM 生成摘要
           b. 摘要作为 system message 前缀
           c. 保留最近 keep_recent 条原始消息
        """
        ...
```

**裁剪策略对比：**

| 策略 | 延迟 | 信息保留 | LLM 调用 | 适用场景 |
|------|------|---------|---------|---------|
| SLIDING_WINDOW | < 1ms | 低 | 无 | 简单任务、短对话 |
| TOKEN_BUDGET | < 1ms | 中 | 无 | 通用场景（默认） |
| SUMMARY_PREFIX | 1-5s | 高 | 1 次 | 长对话、需保留全局语境 |

### 9.5 并发安全

| 后端 | 并发控制策略 | 说明 |
|------|------------|------|
| PostgreSQL | 行级锁 + version 列 | `UPDATE ... WHERE version = ? RETURNING version + 1` |
| Redis | WATCH + MULTI/EXEC | CAS 模式，冲突时自动重试（最多 3 次） |
| InMemory | asyncio.Lock | 单进程内互斥 |

Runner 保证：同一 `session_id` 同一时刻只有一个 `Runner.run()` 持有写权限（通过 `RunConfig.session_lock_timeout` 配置等待超时）。

### 9.6 Session TTL 与清理

| 配置 | 默认值 | 说明 |
|------|--------|------|
| `session_ttl` | 7 天 | Session 不活跃超时（从 `updated_at` 计算） |
| `session_max_messages` | 10000 | 单 Session 最大消息数 |
| `cleanup_interval` | 1 小时 | 后台清理任务间隔 |
| `archive_before_delete` | `True` | 删除前是否归档到冷存储 |

清理策略由 Kasaya 应用层的后台任务调用 `SessionBackend.delete()` 执行，框架本身不启动定时任务。

---

## 十、Guardrails 详细设计

### 10.1 GuardrailExecutor 引擎

GuardrailExecutor 是 Runner 内部的子组件（6.1 节 GuardrailExe），负责执行所有护栏检测：

```
┌─────────────────────────────────────────────────────────────┐
│                    GuardrailExecutor                          │
│                                                              │
│  ┌───────────────────┐  ┌───────────────────┐              │
│  │ InputGuardrailPipe│  │ OutputGuardrailPipe│              │
│  │ ─────────────────  │  │ ─────────────────  │              │
│  │ Agent 执行前       │  │ Agent 输出后       │              │
│  │ 并行/阻塞可选     │  │ 始终阻塞           │              │
│  └───────────────────┘  └───────────────────┘              │
│                                                              │
│  ┌───────────────────┐  ┌───────────────────┐              │
│  │ ToolGuardrailPipe │  │ GuardrailRegistry │              │
│  │ ─────────────────  │  │ ─────────────────  │              │
│  │ 工具调用前后       │  │ 内置护栏注册       │              │
│  │ per-tool 配置     │  │ 名称→实例映射      │              │
│  └───────────────────┘  └───────────────────┘              │
└─────────────────────────────────────────────────────────────┘
```

### 10.2 Input Guardrail 执行流水线

```
用户输入到达
        │
        ▼
┌──────────────────────────────────────────────────────────┐
│  1. 收集 Guardrails                                       │
│     ├── Agent.guardrails.input（Agent 级）                 │
│     └── RunConfig.input_guardrails（Run 级追加）           │
│     → 合并去重，Agent 级优先                               │
└──────────┬───────────────────────────────────────────────┘
           ▼
┌──────────────────────────────────────────────────────────┐
│  2. 判断执行模式                                           │
│     ├── blocking=True  → 步骤 3a（阻塞模式）              │
│     └── blocking=False → 步骤 3b（并行模式）              │
└──────────┬──────────────────────────────┬────────────────┘
           ▼                              ▼
┌─────────────────────┐    ┌─────────────────────────────┐
│ 3a. 阻塞模式         │    │ 3b. 并行模式                 │
│   for g in guardrails│    │   tasks = [                  │
│     result = await   │    │     g.guardrail_function()   │
│       g.guardrail_   │    │     for g in guardrails      │
│       function(...)  │    │   ]                          │
│     if tripwire:     │    │   agent_task = Runner._llm() │
│       raise Input-   │    │   results = await gather(    │
│       GuardrailError │    │     *tasks, agent_task)      │
│   → 全部通过后进入   │    │   any tripwire?              │
│     Agent Loop       │    │     → cancel agent_task      │
└─────────────────────┘    │     → raise Error             │
                            └─────────────────────────────┘
```

**并行模式细节：** 使用 `asyncio.gather(*guardrail_tasks, agent_task, return_exceptions=True)`。若任一 Guardrail 触发 Tripwire，通过 `agent_task.cancel()` 取消正在进行的 LLM 调用，避免浪费 Token。

### 10.3 Tool Guardrail 执行流水线

```
LLM 返回 tool_call
        │
        ▼
┌──────────────────────────────────────────┐
│  1. 匹配 Tool Guardrail                  │
│     ├── Agent 级 tool_guardrails          │
│     ├── Tool 自身的 guardrails 属性       │
│     └── RunConfig 级 tool_guardrails      │
│     → 按 tool_name 过滤适用的 guardrail   │
└──────────┬───────────────────────────────┘
           ▼
┌──────────────────────────────────────────┐
│  2. Before 阶段                           │
│     for g in matched_guardrails:          │
│       result = await g.before_fn(         │
│         context, tool_name, arguments)    │
│       if tripwire:                        │
│         → ToolResult(error=message)       │
│         → 跳过执行，不抛异常              │
│         → 产出 Guardrail Span             │
└──────────┬───────────────────────────────┘
           ▼
        工具执行
           │
           ▼
┌──────────────────────────────────────────┐
│  3. After 阶段                            │
│     for g in matched_guardrails:          │
│       result = await g.after_fn(          │
│         context, tool_name, tool_result)  │
│       if tripwire:                        │
│         → 替换 ToolResult 为错误消息      │
│         → 产出 Guardrail Span             │
└──────────────────────────────────────────┘
```

**与 Input/Output Guardrail 的关键区别：** Tool Guardrail 触发 Tripwire 时**不中断**整个 Run，而是将错误消息作为 `ToolResult` 返回给 LLM，让 LLM 自行决策（重试、换工具或报告错误）。

### 10.4 LLM-Based Guardrail 模式

对于需要语义理解的安全检测，提供基于 LLM 的 Guardrail 模式：

```python
class LLMGuardrail:
    """基于 LLM 的语义护栏基类。"""

    def __init__(
        self,
        model: str = "gpt-4o-mini",     # 使用轻量模型降低延迟
        model_provider: ModelProvider | None = None,
        prompt_template: str = "",
        threshold: float = 0.8,          # 判定阈值
    ): ...

    async def evaluate(
        self,
        content: str,
        context: RunContext,
    ) -> GuardrailResult:
        """
        1. 将 content 填入 prompt_template
        2. 调用 LLM → 返回结构化判定（safe/unsafe + confidence + reason）
        3. confidence >= threshold → tripwire_triggered = True
        4. 创建 Guardrail Span 记录判定过程
        """
        ...
```

**性能考虑：**

| 措施 | 说明 |
|------|------|
| 轻量模型 | 默认使用 gpt-4o-mini / deepseek-chat 等低延迟模型 |
| 缓存 | 相同输入 hash → 缓存判定结果（可配置 TTL） |
| 超时 | LLM Guardrail 默认 5s 超时，超时视为通过（fail-open） |
| 并行 | Input Guardrail 与 Agent LLM 调用并行执行 |

### 10.5 内置 Guardrail 库

框架提供开箱即用的常见安全护栏：

| 名称 | 类型 | 检测方式 | 说明 |
|------|------|---------|------|
| `PromptInjectionGuardrail` | Input | LLM-Based | 检测 Prompt 注入攻击（jailbreak、角色覆盖） |
| `ContentSafetyGuardrail` | Input/Output | LLM-Based | 检测有害/不当内容（暴力、歧视、违法） |
| `PIIDetectionGuardrail` | Output | Regex + NER | 检测 PII 泄露（手机号、身份证、银行卡、邮箱） |
| `RegexGuardrail` | Input/Output | Regex | 通用正则匹配（黑名单词汇、格式校验） |
| `MaxTokenGuardrail` | Input | Token Count | 输入长度限制，防止超大入 |
| `ToolWhitelistGuardrail` | Tool | 白名单 | 仅允许指定工具调用 |

```python
# 内置 Guardrail 使用示例
from kasaya.guardrails import (
    PromptInjectionGuardrail,
    PIIDetectionGuardrail,
    ContentSafetyGuardrail,
    RegexGuardrail,
)

agent = Agent(
    name="support-agent",
    instructions="...",
    input_guardrails=[
        InputGuardrail(guardrail_function=PromptInjectionGuardrail().as_input_fn()),
        InputGuardrail(guardrail_function=RegexGuardrail(
            patterns=[r"DROP\s+TABLE", r"DELETE\s+FROM"],
            message="检测到 SQL 注入风险",
        ).as_input_fn()),
    ],
    output_guardrails=[
        OutputGuardrail(guardrail_function=PIIDetectionGuardrail(
            patterns={"phone": r"1[3-9]\d{9}", "id_card": r"\d{17}[\dXx]"},
        ).as_output_fn()),
        OutputGuardrail(guardrail_function=ContentSafetyGuardrail().as_output_fn()),
    ],
)
```

### 10.6 Guardrail 配置与组合

**优先级与合并规则：**

| 层级 | 来源 | 合并方式 |
|------|------|---------|
| Agent 级 | `Agent.input_guardrails / output_guardrails` | 基础列表 |
| Run 级 | `RunConfig.input_guardrails / output_guardrails` | 追加到 Agent 级之后 |
| 全局级 | `ToolRegistry.global_tool_guardrails` | 对所有工具生效 |

**执行顺序：** 按列表顺序依次执行。首个 Tripwire 触发后立即中断（短路），后续 Guardrail 不再执行。

**Guardrail 结果日志：** 每次 Guardrail 执行都产出 Guardrail Span（type=GUARDRAIL），记录：

```python
# Guardrail Span metadata
{
    "guardrail_name": "prompt_injection",
    "guardrail_type": "input",        # input / output / tool_before / tool_after
    "triggered": False,
    "confidence": 0.15,
    "message": "safe",
    "duration_ms": 120,
    "model": "gpt-4o-mini",           # LLM-Based 时记录
}
```

---

## 十一、Memory 详细设计

### 11.1 Memory 系统架构

Memory 模块提供跨会话的长期记忆能力，分为**提取**、**存储**、**检索**三个子系统：

```
┌─────────────────────────────────────────────────────────────┐
│                       Memory 模块                            │
│                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │ MemoryExtract│  │ MemoryBackend│  │ MemoryRetriev│      │
│  │ ────────────  │  │ ────────────  │  │ ────────────  │      │
│  │ 从对话提取   │  │ 持久化存储   │  │ 相关记忆检索  │      │
│  │ LLM 分析     │  │ 向量索引     │  │ 注入上下文    │      │
│  │ 去重/合并    │  │ CRUD         │  │ Token 预算    │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
└─────────────────────────────────────────────────────────────┘
```

**与 Runner 的集成点：**

```
Runner.run() 开始
│
├── 1. 记忆检索（MemoryRetriever）
│     query = user_input
│     memories = await backend.search(user_id, query, limit=5)
│     → 注入 MessagePipe Step 1（System Message 尾部）
│
├── 2. Agent Loop 执行 ...
│
└── 3. 记忆提取（MemoryExtractor，异步非阻塞）
      messages = 本轮新增消息
      new_entries = await extractor.extract(messages)
      → 去重后写入 backend.store()
```

### 11.2 记忆提取流水线

```python
class MemoryExtractor:
    """从对话中自动提取记忆条目。"""

    def __init__(
        self,
        model: str = "gpt-4o-mini",
        model_provider: ModelProvider | None = None,
        extraction_prompt: str = DEFAULT_EXTRACTION_PROMPT,
        min_confidence: float = 0.6,
    ): ...

    async def extract(self, messages: list[Message]) -> list[MemoryEntry]:
        """
        提取流水线:
        1. 将 messages 序列化为文本（保留最近 20 条）
        2. 调用 LLM → 结构化输出:
           [
             {"type": "user_profile", "content": "用户偏好 Python", "confidence": 0.9},
             {"type": "structured_fact", "content": "项目使用 PG 16", "confidence": 0.85},
           ]
        3. 过滤: confidence < min_confidence 的条目丢弃
        4. 返回 MemoryEntry 列表
        """
        ...
```

**提取 Prompt 模板（DEFAULT_EXTRACTION_PROMPT）：**

```
分析以下对话，提取值得长期记住的信息。分类为：
- user_profile: 用户的偏好、习惯、技术栈、身份信息
- structured_fact: 项目事实、技术决策、业务规则
- history_summary: 本次对话的核心结论和决策

对每条信息给出 0.0-1.0 的置信度分数。
只提取明确陈述或可高度推断的信息，不要猜测。
以 JSON 数组格式返回。
```

**去重逻辑：** 提取后与现有记忆条目对比（基于语义相似度），若新条目与已有条目相似度 > 0.85，则更新已有条目的 `content` 和 `confidence`，而非新增。

### 11.3 记忆检索与注入

```python
class MemoryRetriever:
    """检索相关记忆并注入上下文。"""

    def __init__(
        self,
        backend: MemoryBackend,
        embedding_model: str = "text-embedding-3-small",
        max_memory_tokens: int = 1000,    # 记忆注入的 Token 预算
        retrieval_strategy: str = "hybrid", # vector / keyword / hybrid / recency
    ): ...

    async def retrieve(
        self,
        user_id: str,
        query: str,
        limit: int = 5,
    ) -> list[MemoryEntry]:
        """
        检索策略:
        - vector: 基于 Embedding 余弦相似度
        - keyword: 基于关键词匹配（TF-IDF）
        - hybrid: vector + keyword 混合排名（RRF 融合）
        - recency: 按更新时间倒序
        """
        ...

    def format_for_injection(self, entries: list[MemoryEntry]) -> str:
        """
        将记忆条目格式化为可注入 System Message 的文本:
        
        ## 用户记忆
        - [用户档案] 用户偏好 Python，使用 macOS（置信度: 0.9）
        - [事实] 项目使用 PostgreSQL 16（置信度: 0.85）
        - [摘要] 上次讨论了 Q1 报告，结论是需要增加预算（置信度: 0.8）
        
        控制总 Token 数不超过 max_memory_tokens。
        """
        ...
```

### 11.4 MemoryBackend 实现规范

**PostgresMemoryBackend（推荐生产使用）：**

```sql
-- 需要 pgvector 扩展
CREATE EXTENSION IF NOT EXISTS vector;

-- 记忆条目表
CREATE TABLE memory_entries (
    id              VARCHAR(64)  PRIMARY KEY,
    user_id         VARCHAR(128) NOT NULL,
    type            VARCHAR(32)  NOT NULL,  -- user_profile / history_summary / structured_fact
    content         TEXT         NOT NULL,
    confidence      REAL         DEFAULT 1.0,
    embedding       vector(1536),            -- text-embedding-3-small 维度
    source_session_id VARCHAR(128),
    metadata        JSONB        DEFAULT '{}',
    created_at      TIMESTAMPTZ  DEFAULT now(),
    updated_at      TIMESTAMPTZ  DEFAULT now()
);

CREATE INDEX idx_memory_user ON memory_entries(user_id, type);
CREATE INDEX idx_memory_embedding ON memory_entries
    USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
```

```python
class PostgresMemoryBackend(MemoryBackend):
    """PostgreSQL + pgvector 实现。"""

    async def store(self, user_id: str, entry: MemoryEntry) -> None:
        """
        1. 计算 entry.content 的 embedding
        2. INSERT ... ON CONFLICT (id) DO UPDATE（upsert 语义）
        """
        ...

    async def search(
        self, user_id: str, query: str, limit: int = 10
    ) -> list[MemoryEntry]:
        """
        1. 计算 query 的 embedding
        2. SELECT ... WHERE user_id = ?
           ORDER BY embedding <=> query_embedding
           LIMIT ?
        """
        ...
```

**InMemoryMemoryBackend（测试用）：**

```python
class InMemoryMemoryBackend(MemoryBackend):
    """内存存储后端——仅用于单元测试。"""
    _store: dict[str, list[MemoryEntry]] = {}   # user_id → entries
```

### 11.5 隐私与生命周期管理

| 策略 | 配置 | 默认值 | 说明 |
|------|------|--------|------|
| 用户隔离 | 强制 | - | 所有 API 都以 `user_id` 为必需参数，无法跨用户访问 |
| 记忆 TTL | `memory_ttl` | 90 天 | 超过 TTL 未更新的条目自动标记为过期 |
| 置信度衰减 | `confidence_decay_rate` | 0.01/天 | 长期未被检索命中的条目置信度逐步降低 |
| 最低置信度 | `min_retention_confidence` | 0.3 | 低于阈值的条目在清理时删除 |
| 显式删除 | `MemoryBackend.delete()` | - | 用户或管理员可主动删除任意记忆条目 |
| 批量清理 | `MemoryBackend.delete_by_user()` | - | 删除用户全部记忆（GDPR 合规） |

```python
class MemoryBackend(ABC):
    # ... 已有方法 ...

    @abstractmethod
    async def delete_by_user(self, user_id: str) -> int:
        """删除指定用户的全部记忆，返回删除条数。GDPR 合规。"""
        ...

    @abstractmethod
    async def decay(self, before: datetime, rate: float) -> int:
        """对 updated_at < before 的条目降低 confidence，返回受影响条数。"""
        ...
```

---

## 十二、Approval 详细设计

### 12.1 Approval 系统架构

Approval 模块在 Runner Agent Loop 中拦截需要审批的操作，通过 ApprovalHandler 接口对接外部审批系统：

```
┌─────────────────────────────────────────────────────────────┐
│                     Approval 模块                            │
│                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │ ApprovalGate │  │ RiskClassifier│  │ ApprovalHandler│    │
│  │ ────────────  │  │ ────────────  │  │ ────────────  │     │
│  │ Runner 拦截点 │  │ 风险评估     │  │ 外部审批适配  │     │
│  │ 挂起/恢复    │  │ 工具分级     │  │ 等待结果      │     │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
└─────────────────────────────────────────────────────────────┘
```

### 12.2 Approval Mode 决策矩阵

ApprovalGate 根据 `ApprovalMode` 和操作类型决定是否拦截：

| 操作类型 | suggest | auto-edit | full-auto |
|---------|---------|-----------|-----------|
| 任何工具调用 | ✅ 审批 | 看风险等级 | ❌ 直接执行 |
| 高风险工具调用 | ✅ 审批 | ✅ 审批 | ❌ 直接执行 |
| Agent 最终输出 | ✅ 审批 | ❌ 直接输出 | ❌ 直接输出 |
| Handoff 切换 | ✅ 审批 | ❌ 直接切换 | ❌ 直接切换 |

### 12.3 风险分级

```python
class RiskLevel(str, Enum):
    LOW = "low"        # 只读操作（查询、搜索）
    MEDIUM = "medium"  # 数据变更（创建、更新）
    HIGH = "high"      # 高危操作（删除、外部 API 写入、金融操作）

class RiskClassifier:
    """工具风险分级器。"""
    
    _rules: dict[str, RiskLevel]   # tool_name → risk_level 配置
    _default: RiskLevel = RiskLevel.MEDIUM
    
    def classify(self, tool_name: str, arguments: dict) -> RiskLevel:
        """
        分级策略:
        1. 精确匹配: _rules[tool_name]
        2. namespace 匹配: _rules["github::*"]
        3. 默认级别: _default
        """
        ...
```

**风险等级配置（YAML）：**

```yaml
approval:
  risk_rules:
    "database::drop_*": high
    "database::delete_*": high
    "database::select_*": low
    "github::create_issue": medium
    "sandbox::execute": high
  default_risk: medium
```

### 12.4 ApprovalGate 执行流程

```
Runner Agent Loop 中遇到操作
        │
        ▼
┌──────────────────────────────────────┐
│ 1. 检查 ApprovalMode                 │
│    ├── full-auto → 跳过，直接执行     │
│    ├── suggest → 进入审批流程          │
│    └── auto-edit → 步骤 2             │
└──────────┬───────────────────────────┘
           ▼
┌──────────────────────────────────────┐
│ 2. 风险评估 (auto-edit 模式)          │
│    risk = RiskClassifier.classify()  │
│    ├── LOW → 跳过, 直接执行           │
│    ├── MEDIUM → 跳过, 直接执行        │
│    └── HIGH → 进入审批流程            │
└──────────┬───────────────────────────┘
           ▼
┌──────────────────────────────────────┐
│ 3. 发起审批                           │
│    decision = await ApprovalHandler   │
│      .request_approval(               │
│        context, action_type,          │
│        action_detail, timeout)        │
│    ├── APPROVED → 继续执行            │
│    ├── REJECTED → 处理拒绝            │
│    └── TIMEOUT → 执行 timeout_policy  │
└──────────┬───────────────────────────┘
           ▼
┌──────────────────────────────────────┐
│ 4. 拒绝/超时处理                      │
│    rejection_policy:                  │
│    ├── abort → 抛 ApprovalRejected    │
│    ├── retry → 通知 LLM 被拒原因     │
│    │   → LLM 修改后重试（max 2次）    │
│    └── escalate → 升级到上级审批人     │
└──────────────────────────────────────┘
```

### 12.5 Runner 挂起与恢复

审批等待期间 Runner 状态管理：

```python
class ApprovalWaiter:
    """审批等待器——Runner 挂起期间的状态管理。"""
    
    async def wait_for_approval(
        self,
        handler: ApprovalHandler,
        context: RunContext,
        action_type: str,
        action_detail: dict,
        timeout: int,
    ) -> ApprovalDecision:
        """
        1. 产出 ApprovalRequestEvent（StreamEvent）
        2. 创建 approval Span（type=GUARDRAIL, name="approval_wait"）
        3. await handler.request_approval(...)
        4. 记录结果到 Span metadata
        5. 返回 decision
        
        超时处理:
        - asyncio.wait_for(handler.request_approval(...), timeout)
        - TimeoutError → ApprovalDecision.TIMEOUT
        """
        ...
```

| 配置 | 默认值 | 说明 |
|------|--------|------|
| `approval_timeout` | 300s | 单次审批等待超时 |
| `timeout_policy` | reject | timeout → reject / approve / escalate |
| `max_retry_on_reject` | 2 | 拒绝后 LLM 可重试次数 |
| `rejection_policy` | abort | reject → abort / retry / escalate |

---

## 十三、Sandbox 详细设计

### 13.1 Sandbox 架构

Sandbox 模块为代码执行工具提供隔离运行环境，框架定义接口，应用层实现具体沙箱：

```
┌─────────────────────────────────────────────────────────────┐
│                      Sandbox 模块                            │
│                                                              │
│  ┌──────────────────────────────────────────────────┐       │
│  │               Sandbox (ABC)                       │       │
│  │  execute(code, language, timeout, env) → Result   │       │
│  │  cleanup()                                        │       │
│  └──────────────────────────────────────────────────┘       │
│         ▲                 ▲                 ▲               │
│         │                 │                 │               │
│  ┌──────┴─────┐  ┌───────┴──────┐  ┌───────┴──────┐       │
│  │ LocalSandbox│  │DockerSandbox │  │  K8sSandbox  │       │
│  │ 开发测试用   │  │ 生产推荐     │  │ 大规模生产   │       │
│  └────────────┘  └──────────────┘  └──────────────┘       │
└─────────────────────────────────────────────────────────────┘
```

### 13.2 Sandbox 实现规范

**LocalSandbox（开发/测试）：**

```python
class LocalSandbox(Sandbox):
    """本地子进程执行——仅用于开发测试。"""
    
    async def execute(self, code, language="python", timeout=30, env=None):
        """
        1. 写入临时文件
        2. subprocess.run(["python", temp_file], timeout=timeout, env=env)
        3. 捕获 stdout/stderr
        4. 返回 ExecutionResult
        ⚠️ 无隔离，不适用于生产环境
        """
        ...
```

**DockerSandbox（生产推荐）：**

```python
class DockerSandbox(Sandbox):
    """Docker 容器隔离执行。"""
    
    def __init__(
        self,
        image: str = "kasaya/sandbox:latest",
        memory_limit: str = "256m",
        cpu_limit: float = 0.5,
        network_mode: str = "none",    # 默认禁用网络
        read_only: bool = True,
        tmpfs: dict = {"/tmp": "size=64m"},
    ): ...
    
    async def execute(self, code, language="python", timeout=30, env=None):
        """
        1. docker.containers.run(
             image, code,
             mem_limit, cpu_period, cpu_quota,
             network_mode="none",
             read_only=True,
             tmpfs={"/tmp": "size=64m"},
           )
        2. 等待完成或超时强制 kill
        3. 读取 stdout/stderr
        4. 自动移除容器
        """
        ...
    
    async def cleanup(self):
        """清理所有由本实例创建的容器"""
        ...
```

**K8sSandbox（大规模生产）：**

```python
class K8sSandbox(Sandbox):
    """Kubernetes Pod 隔离执行——适合多租户大规模场景。"""
    
    def __init__(
        self,
        namespace: str = "kasaya-sandbox",
        image: str = "kasaya/sandbox:latest",
        service_account: str = "sandbox-runner",
        resource_limits: dict = {"cpu": "500m", "memory": "256Mi"},
        network_policy: str = "deny-all",
    ): ...
```

### 13.3 安全约束

| 约束 | LocalSandbox | DockerSandbox | K8sSandbox |
|------|-------------|---------------|------------|
| 文件系统隔离 | ❌ | ✅ read_only + tmpfs | ✅ ephemeral volume |
| 网络隔离 | ❌ | ✅ network=none | ✅ NetworkPolicy deny-all |
| 资源限制 | ❌ | ✅ memory + CPU | ✅ ResourceQuota |
| 进程隔离 | ❌ (子进程) | ✅ (容器) | ✅ (Pod) |
| 超时强制终止 | ✅ SIGKILL | ✅ docker kill | ✅ Pod delete |
| 多租户隔离 | ❌ | ⚠️ (共享 daemon) | ✅ (namespace 隔离) |

### 13.4 执行流水线

```
工具调用 sandbox::execute(code, language)
        │
        ▼
┌──────────────────────────────────────┐
│ 1. 代码预检                           │
│    ├── 语言白名单检查                  │
│    ├── 危险 import/模块检测            │
│    └── 代码长度限制                    │
└──────────┬───────────────────────────┘
           ▼
┌──────────────────────────────────────┐
│ 2. 环境准备                           │
│    ├── 选择 Sandbox 实现              │
│    ├── 注入环境变量（脱敏后）          │
│    └── 挂载只读数据卷（如有）          │
└──────────┬───────────────────────────┘
           ▼
┌──────────────────────────────────────┐
│ 3. 隔离执行                           │
│    ├── 创建隔离环境                    │
│    ├── 执行代码                        │
│    ├── 等待完成 / 超时强制终止         │
│    └── 捕获 stdout + stderr            │
└──────────┬───────────────────────────┘
           ▼
┌──────────────────────────────────────┐
│ 4. 结果处理                           │
│    ├── 构造 ExecutionResult            │
│    ├── 截断过长输出（max 10KB）        │
│    ├── 产出 Tool Span                  │
│    └── 清理沙箱资源                    │
└──────────────────────────────────────┘
```

---

## 十四、Skills 详细设计

### 14.1 Skill 系统架构

Skills 将领域知识打包为可复用的知识单元，Agent 启用 Skill 后自动获得相关 instructions 和工具：

```
┌─────────────────────────────────────────────────────────────┐
│                       Skill 模块                             │
│                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │ SkillLoader  │  │ SkillRegistry │  │ SkillInjector │     │
│  │ ────────────  │  │ ────────────  │  │ ────────────  │     │
│  │ 解析.skill包 │  │ 已安装Skill表 │  │ Runner注入   │      │
│  │ 校验metadata │  │ 版本管理     │  │ instructions  │      │
│  │ 注册工具     │  │ 启用/禁用    │  │ + 工具        │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
└─────────────────────────────────────────────────────────────┘
```

### 14.2 Skill 包加载流程

```
.skill 包安装 / 更新
        │
        ▼
┌──────────────────────────────────────┐
│ 1. SkillLoader 解析                   │
│    ├── 读取 metadata.yaml             │
│    │   name, version, description,    │
│    │   tags, applicable_agents,       │
│    │   category (public/custom)       │
│    ├── 读取 SKILL.md → 知识文档       │
│    ├── 扫描 scripts/ → 函数工具       │
│    │   每个 .py 文件注册为             │
│    │   FunctionTool(namespace=skill)  │
│    └── 索引 assets/ → 静态资源路径     │
└──────────┬───────────────────────────┘
           ▼
┌──────────────────────────────────────┐
│ 2. SkillRegistry 注册                 │
│    ├── 验证 name 唯一性              │
│    ├── 版本冲突检查                    │
│    ├── 注册工具到 ToolRegistry        │
│    │   namespace = skill_name         │
│    └── 记录安装信息                    │
└──────────────────────────────────────┘
```

### 14.3 Skill 注入机制

Runner 在 MessagePipe（6.3 节）Step 1 中注入已启用 Skill：

```python
class SkillInjector:
    """将 Skill 知识注入 Agent 上下文。"""
    
    _registry: SkillRegistry
    
    async def inject(
        self,
        agent: Agent,
        context: RunContext,
    ) -> tuple[str, list[FunctionTool]]:
        """
        返回:
        - instructions_suffix: 追加到 System Message 的知识摘要
        - tools: Skill 注入的工具列表
        
        流程:
        1. 获取 Agent.skills 列表
        2. 从 SkillRegistry 加载每个 Skill
        3. 拼接知识摘要:
           ## 已启用技能
           ### customer-service-handbook (v1.0.0)
           {SKILL.md 内容}
           ### data-analysis (v2.1.0)
           {SKILL.md 内容}
        4. 收集所有 Skill 的工具（已加 namespace）
        5. Token 预算控制：若知识文档过长，截取前 N Token
        """
        ...
```

### 14.4 Skill 版本管理

| 策略 | 说明 |
|------|------|
| 版本格式 | Semantic Versioning（MAJOR.MINOR.PATCH） |
| 安装时 | 检查是否已有同名 Skill；高版本覆盖低版本 |
| 兼容性 | MAJOR 变更需手动确认升级 |
| 回滚 | 支持回退到上一版本（保留最近 3 个版本） |

### 14.5 Skill 发现与搜索

Kasaya 应用层提供 Skill 管理 UI：

| 功能 | 说明 |
|------|------|
| Skill 市场 | 浏览公共 Skill 列表（分类、标签、评分） |
| 安装/卸载 | 一键安装 / 卸载 Skill 包 |
| 为 Agent 启用 | 在 Agent 配置中选择需要的 Skill |
| @mention 调用 | 用户在对话中 @skill_name 临时启用特定 Skill |
| 自定义 Skill | 导入自定义 .skill 包 |

---

## 十五、依赖管理

### 15.1 核心依赖

| 包 | 用途 | 必选 |
|----|------|------|
| `pydantic>=2.0` | 数据验证、结构化输出 | ✅ |
| `httpx` | HTTP 客户端（LLM API、MCP HTTP） | ✅ |
| `anyio` | 异步运行时抽象 | ✅ |

### 15.2 可选依赖（extras）

| Extra | 包 | 用途 |
|-------|-----|------|
| `litellm` | `litellm>=1.40` | LiteLLM 模型适配 |
| `postgres` | `asyncpg`, `sqlalchemy[asyncio]` | PostgreSQL Session/Memory 后端 |
| `redis` | `redis[hiredis]` | Redis Session 后端 |
| `docker` | `docker` | Docker Sandbox |
| `mcp` | `mcp>=1.0` | MCP 协议支持 |

安装示例：

```bash
pip install kasaya-framework[litellm,postgres,mcp]
```

### 15.3 Python 版本

- 最低：Python 3.12+
- 类型注解：PEP 604（`X | Y`）、PEP 585（`list[T]`）全面使用
- 标记 `py.typed`，支持 mypy / pyright 静态检查

---

## 十六、配置体系

### 16.1 Agent YAML 配置格式

```yaml
# agent.yaml
name: triage-agent
description: "客户服务分诊 Agent，根据用户意图路由到对应专家"
model: gpt-4o
model_settings:
  temperature: 0.3
  max_tokens: 2048

instructions: |
  你是一个客户服务分诊专家。
  分析用户意图，路由到对应专家 Agent：
  - 退款 → refund-agent
  - 账单 → billing-agent
  - 技术支持 → support-agent

tool_groups:
  - web-search

handoffs:
  - refund-agent
  - billing-agent
  - support-agent

guardrails:
  input:
    - name: content-safety
      blocking: true
  output:
    - name: pii-filter

approval_mode: auto-edit

skills:
  - customer-service-handbook
```

### 16.2 MCP Server 配置格式

```yaml
# mcp-servers.yaml
servers:
  - name: github-mcp
    transport: stdio
    command: "npx -y @modelcontextprotocol/server-github"
    env:
      GITHUB_TOKEN: "${GITHUB_TOKEN}"
    
  - name: database-mcp
    transport: http
    url: "https://db-mcp.internal.example.com"
    auth:
      type: oauth
      client_id: "${MCP_CLIENT_ID}"
      client_secret: "${MCP_CLIENT_SECRET}"
      token_url: "https://auth.example.com/token"
```

### 16.3 Skill 包结构

```
customer-service.skill/
├── SKILL.md              # 领域知识文档（必需）
├── metadata.yaml         # 元数据
│   # name: customer-service-handbook
│   # version: 1.0.0
│   # description: 客户服务领域知识
│   # author: Kasaya Team
│   # tags: [customer-service, faq]
│   # applicable_agents: ["support-agent"]
│   # category: public
├── scripts/              # 辅助脚本（可选，自动注册为 Skill 命名空间下的 Function Tool）
│   └── lookup_faq.py
├── references/           # 参考资料（可选，Agent 按需读取）
│   └── faq-database.json
└── assets/               # 静态资源（可选，模板文件、配置模板、Prompt 片段）
    └── reply-template.md
```

---

## 十七、错误处理

### 17.1 异常层级

```python
class KasayaFrameworkError(Exception):
    """Kasaya Framework 基础异常"""

class AgentError(KasayaFrameworkError):
    """Agent 相关错误"""

class RunnerError(KasayaFrameworkError):
    """Runner 执行错误"""

class MaxTurnsExceeded(RunnerError):
    """超过最大执行轮次"""

class InputGuardrailError(KasayaFrameworkError):
    """输入护栏拦截"""
    guardrail_name: str
    result: GuardrailResult

class OutputGuardrailError(KasayaFrameworkError):
    """输出护栏拦截"""
    guardrail_name: str
    result: GuardrailResult

class ToolGuardrailError(KasayaFrameworkError):
    """工具护栏拦截"""
    guardrail_name: str
    tool_name: str
    result: GuardrailResult

class ApprovalRejectedError(KasayaFrameworkError):
    """审批被拒绝"""
    action_type: str

class ApprovalTimeoutError(KasayaFrameworkError):
    """审批超时"""

class ModelProviderError(KasayaFrameworkError):
    """模型调用失败"""
    model: str
    status_code: int | None

class MCPError(KasayaFrameworkError):
    """MCP 协议错误"""
    server_name: str

class SandboxError(KasayaFrameworkError):
    """沙箱执行错误"""
    exit_code: int
```

### 17.2 Runner 错误处理策略

| 场景 | 默认行为 | 可配置 |
|------|---------|--------|
| LLM 调用失败 | 重试 2 次，间隔指数退避 | `RunConfig.retry_config` |
| 工具调用失败 | 将错误信息追加到消息，让 LLM 决策 | - |
| Guardrail Tripwire | 立即中断执行，抛出异常 | - |
| 审批被拒 | 终止当前操作，通知 LLM | - |
| 审批超时 | 默认拒绝 | `ApprovalHandler.on_timeout` |
| max_turns 超限 | 抛 `MaxTurnsExceeded` | `RunConfig.on_max_turns_exceeded` |
| MCP Server 断连 | 标记工具不可用，通知 LLM | - |

---

## 十八、测试策略

### 18.1 测试分层

| 层级 | 范围 | 工具 |
|------|------|------|
| 单元测试 | 各模块独立逻辑 | pytest + pytest-asyncio |
| 集成测试 | Runner + Agent + Tools 联动 | 使用 Mock ModelProvider |
| E2E 测试 | 完整 Agent Loop + 真实 LLM | 使用低成本模型 |

### 18.2 Mock 支持

```python
# Kasaya Framework 提供测试用 Mock
from kasaya.testing import MockModelProvider, MockSession

# Mock LLM 响应
provider = MockModelProvider(responses=[
    MockResponse(content="我来帮你处理退款"),
    MockResponse(tool_calls=[
        MockToolCall(name="query_order", arguments={"order_id": "123"})
    ]),
])

# 使用 Mock 运行测试
result = await Runner.run(
    agent=test_agent,
    input="退款",
    config=RunConfig(model_provider=provider),
)
assert "退款" in result.final_output
```

---

## 十九、版本与发布

### 19.1 版本策略

遵循 Semantic Versioning 2.0.0：

| 版本号 | 触发条件 |
|--------|---------|
| MAJOR (X.0.0) | 公共 API 不兼容变更 |
| MINOR (0.X.0) | 新增功能，向后兼容 |
| PATCH (0.0.X) | Bug 修复 |

### 19.2 发布计划

| 里程碑 | 版本 | 目标内容 |
|--------|------|---------|
| Alpha | 0.1.0 | Agent + Runner + Tools + Handoff 基础功能 |
| Beta | 0.5.0 | + Guardrails + Session + Tracing + MCP |
| RC | 0.9.0 | + Memory + Approval + Skills + Sandbox |
| GA | 1.0.0 | 稳定 API，完整文档，测试覆盖 ≥ 80% |

---

## 二十、配置热更新机制

PRD 4.13.1 定义了配置热更新的产品需求。本章描述 Framework 和应用层的实现设计。

### 20.1 架构概览

```
配置变更流程:
Admin UI → PUT /api/config → 写入 PostgreSQL → Redis Pub/Sub 通知 → 各应用实例刷新本地缓存
```

### 20.2 可热更新配置注册表

```python
from enum import Enum
from dataclasses import dataclass
from typing import Any

class ConfigScope(Enum):
    """配置生效范围"""
    NEW_RUN = "new_run"           # 仅对新创建的 Run 生效
    NEXT_CHECK = "next_check"     # 下一次检查点生效（如 Guardrail）
    IMMEDIATE = "immediate"       # 即时生效

@dataclass
class HotConfigEntry:
    key: str
    scope: ConfigScope
    validator: callable  # 校验函数，变更前校验新值合法性

# 注册表
HOT_CONFIG_REGISTRY: dict[str, HotConfigEntry] = {
    "agent.{name}.instructions":  HotConfigEntry("agent.instructions",  ConfigScope.NEW_RUN, validate_instructions),
    "agent.{name}.model":         HotConfigEntry("agent.model",         ConfigScope.NEW_RUN, validate_model_ref),
    "agent.{name}.tools":         HotConfigEntry("agent.tools",         ConfigScope.NEW_RUN, validate_tool_groups),
    "guardrail.{name}.enabled":   HotConfigEntry("guardrail.enabled",   ConfigScope.NEXT_CHECK, validate_bool),
    "guardrail.{name}.rules":     HotConfigEntry("guardrail.rules",     ConfigScope.NEXT_CHECK, validate_guardrail_rules),
    "system.rate_limit":          HotConfigEntry("system.rate_limit",   ConfigScope.IMMEDIATE, validate_rate_limit),
    "system.token_budget":        HotConfigEntry("system.token_budget", ConfigScope.IMMEDIATE, validate_positive_int),
    "feature.sandbox_enabled":    HotConfigEntry("feature.sandbox",     ConfigScope.IMMEDIATE, validate_bool),
    "feature.approval_mode":      HotConfigEntry("feature.approval",    ConfigScope.IMMEDIATE, validate_approval_mode),
}
```

### 20.3 配置缓存与刷新

```python
class ConfigCache:
    """应用实例本地配置缓存"""
    
    def __init__(self, redis_client, pg_pool):
        self._cache: dict[str, Any] = {}
        self._redis = redis_client
        self._pg = pg_pool
    
    async def start(self):
        """启动时全量加载 + 订阅变更"""
        await self._load_all()
        await self._subscribe_changes()
    
    async def _load_all(self):
        """从 PostgreSQL 全量加载配置"""
        rows = await self._pg.fetch("SELECT key, value FROM config_entries WHERE is_active = true")
        self._cache = {r["key"]: r["value"] for r in rows}
    
    async def _subscribe_changes(self):
        """Redis Pub/Sub 监听配置变更事件"""
        pubsub = self._redis.pubsub()
        await pubsub.subscribe("config:changed")
        async for message in pubsub.listen():
            if message["type"] == "message":
                changed_key = message["data"]
                await self._refresh_key(changed_key)
    
    async def _refresh_key(self, key: str):
        """刷新单个配置项"""
        row = await self._pg.fetchrow("SELECT value FROM config_entries WHERE key = $1 AND is_active = true", key)
        if row:
            self._cache[key] = row["value"]
        else:
            self._cache.pop(key, None)
    
    def get(self, key: str, default=None):
        return self._cache.get(key, default)
```

### 20.4 配置变更审计

每次配置变更自动写入 `config_change_log` 表：

```python
@dataclass
class ConfigChangeRecord:
    id: str
    config_key: str
    old_value: Any       # 变更前的值（JSON）
    new_value: Any       # 变更后的值（JSON）
    changed_by: str      # 操作人 user_id
    changed_at: datetime
    change_source: str   # "web_ui" | "api" | "system"
    rollback_ref: str    # 可选：如果是回滚操作，引用原始变更 ID
```

### 20.5 回滚机制

```python
async def rollback_config(config_key: str, target_change_id: str):
    """回滚配置到指定变更记录的 old_value"""
    target = await get_change_record(target_change_id)
    assert target.config_key == config_key
    
    # 写入新变更（类型为回滚）
    await update_config(
        key=config_key,
        new_value=target.old_value,
        change_source="rollback",
        rollback_ref=target_change_id,
    )
```

---

## 二十一、Agent 国际化（i18n）支持

PRD 4.13.2 定义了 Agent 国际化的产品需求。本章描述 Framework 层的实现设计。

### 21.1 多语言 Instructions 存储模型

```python
@dataclass
class LocalizedInstructions:
    """Agent 的多语言 Instructions"""
    default_locale: str = "zh-CN"  # 默认语言
    instructions: dict[str, str] = field(default_factory=dict)
    # 示例: {"zh-CN": "你是一个...", "en-US": "You are a..."}
    
    def resolve(self, locale: str) -> str:
        """按优先级解析 Instructions：精确匹配 → 语言匹配 → 默认"""
        if locale in self.instructions:
            return self.instructions[locale]
        # 尝试语言级匹配（zh-TW → zh-CN）
        lang = locale.split("-")[0]
        for key in self.instructions:
            if key.startswith(lang):
                return self.instructions[key]
        return self.instructions[self.default_locale]
```

### 21.2 Locale 解析链

Runner 在构建 Agent Instructions 时，按以下优先级确定 locale：

```
1. RunConfig.locale（API 调用时显式指定）
2. Session.user_locale（用户个人偏好设置）
3. Agent.default_locale（Agent 默认语言）
4. 系统默认值（"zh-CN"）
```

```python
def resolve_locale(run_config: RunConfig, session: Session, agent: Agent) -> str:
    return (
        run_config.locale
        or session.metadata.get("user_locale")
        or agent.localized_instructions.default_locale
        or "zh-CN"
    )
```

### 21.3 Agent 描述多语言

```python
@dataclass
class AgentLocaleInfo:
    """Agent 的多语言展示信息（存储在应用层）"""
    agent_name: str
    locale: str
    display_name: str
    description: str
```

> 应用层 API 返回 Agent 信息时，根据请求的 `Accept-Language` 头或用户 locale 偏好选择对应的 `AgentLocaleInfo`。

### 21.4 MVP 实现范围

| 能力 | MVP | Post-MVP |
|------|-----|----------|
| 多语言 Instructions 存储 | ✅ Agent 可配置多个语言版本 | — |
| 手动 locale 选择 | ✅ 用户在设置中选择语言 | — |
| 自动语言检测 | — | ✅ 根据输入语言自动路由 |
| 前端 UI i18n | ✅ 中/英双语 | 日/韩/法等更多语言 |
| Agent 描述多语言 | ✅ display_name + description | — |

---

## 附录 A：内置 Agent 模板详细设计

PRD 4.12.1 定义了 10 个内置 Agent 模板。本节提供每个模板的完整配置，包括 Instructions 核心指令、Handoff 配置、Tool 绑定和 Guardrail 设置。

### A.1 Triage（分诊）

```yaml
name: triage
display_name: "分诊路由 Agent"
model: default  # 推荐 gpt-4o 或同级模型
instructions: |
  你是一个智能分诊助手。你的职责是：
  1. 理解用户意图并归类到预定义类别
  2. 如果意图明确，立即使用 handoff 转交给最合适的专家 Agent
  3. 如果意图不明确，通过最多 2 轮追问澄清
  4. 不要自己回答专业问题，你的唯一职责是路由
  
  意图分类参考：
  - 数据分析请求 → data-analyst
  - 代码相关 → code-assistant
  - 信息调研 → researcher
  - 客服/订单 → customer-service
  - 通用问答 → faq-bot
handoffs:
  - agent: data-analyst
  - agent: code-assistant
  - agent: researcher
  - agent: customer-service
  - agent: faq-bot
tools: []
guardrails:
  input:
    - prompt_injection_detector
    - content_safety_filter
  output: []
```

### A.2 FAQ Bot

```yaml
name: faq-bot
display_name: "FAQ 问答 Agent"
model: default  # 推荐 gpt-4o-mini（成本优化）
instructions: |
  你是一个 FAQ 问答助手。你的职责是：
  1. 基于加载的知识库和 Skill 文档回答用户常见问题
  2. 如果知识库中找不到答案，礼貌告知并建议联系人工客服
  3. 回答简洁、准确，引用来源
  4. 不编造信息
handoffs: []
tools: []
skills:
  - customer-service-handbook
guardrails:
  input:
    - prompt_injection_detector
  output:
    - content_safety_filter
    - pii_redactor
```

### A.3 Researcher

```yaml
name: researcher
display_name: "网络调研 Agent"
model: default  # 推荐 gpt-4o（需要较强推理能力）
instructions: |
  你是一个专业的网络调研助手。你的工作流程：
  1. 分析调研主题，拆解为 3-5 个搜索关键词
  2. 使用 web_search 工具搜索每个关键词
  3. 对搜索结果中的高质量链接使用 fetch_webpage 获取详细内容
  4. 综合多个来源，输出结构化调研报告：
     - 摘要（3 句话内）
     - 关键发现（要点列表）
     - 信息来源（附链接）
     - 局限性说明
  5. 注明信息时效性
handoffs: []
tools:
  - group: web-search
skills:
  - research-methodology
guardrails:
  input:
    - prompt_injection_detector
  output:
    - content_safety_filter
```

### A.4 Data Analyst

```yaml
name: data-analyst
display_name: "数据分析 Agent"
model: default  # 推荐 gpt-4o
instructions: |
  你是一个数据分析专家。你的工作流程：
  1. 理解用户的分析需求
  2. 如需查询数据库，先用 SQL 查询获取数据
  3. 使用 Python 进行数据处理和统计分析
  4. 生成可视化图表（matplotlib/seaborn）
  5. 输出分析报告，包含：
     - 数据概览
     - 分析方法说明
     - 关键指标和发现
     - 图表
     - 建议
  注意：SQL 查询必须为只读（SELECT），禁止 DDL/DML 操作。
handoffs: []
tools:
  - group: code-executor
  - group: database
skills:
  - data-analysis
guardrails:
  input:
    - prompt_injection_detector
  output:
    - pii_redactor
```

### A.5 Report Writer

```yaml
name: report-writer
display_name: "报告撰写 Agent"
model: default  # 推荐 gpt-4o
instructions: |
  你是一个专业的报告撰写助手。你的职责是：
  1. 接收分析数据/调研结果，整理为结构化报告
  2. 报告格式：Markdown，包含标题、摘要、正文、结论、附录
  3. 使用 file-ops 工具将报告保存为文件
  4. 遵循 writing-style-guide Skill 中的写作规范
  5. 图表和数据引用必须标注来源
handoffs: []
tools:
  - group: file-ops
skills:
  - writing-style-guide
  - data-analysis
guardrails:
  input:
    - prompt_injection_detector
  output:
    - content_safety_filter
```

### A.6 Code Assistant

```yaml
name: code-assistant
display_name: "代码辅助 Agent"
model: default  # 推荐 gpt-4o 或 claude-sonnet
instructions: |
  你是一个代码辅助助手，支持多种编程语言。你可以：
  1. 根据需求编写代码
  2. 审阅已有代码，指出问题和改进建议
  3. 解释代码逻辑
  4. 调试和修复 Bug
  5. 使用 code-executor 执行代码验证结果
  
  编码规范：
  - 遵循语言社区的最佳实践
  - 关注安全性（参考 code-review Skill）
  - 代码需包含必要的错误处理
  - 输出代码附带简要说明
handoffs: []
tools:
  - group: code-executor
skills:
  - code-review
guardrails:
  input:
    - prompt_injection_detector
  output:
    - content_safety_filter
```

### A.7 Translator

```yaml
name: translator
display_name: "多语言翻译 Agent"
model: default  # 推荐 gpt-4o
instructions: |
  你是一个专业翻译助手。翻译规则：
  1. 自动检测源语言，翻译为用户指定的目标语言
  2. 保持原文语义、语气和风格
  3. 专业术语保留原文并在括号中注释翻译
  4. 对于有歧义的表达，提供多种翻译方案并说明差异
  5. 支持中/英/日/韩/法/德/西等主要语言
handoffs: []
tools: []
guardrails:
  input:
    - prompt_injection_detector
  output:
    - content_safety_filter
```

### A.8 Customer Service

```yaml
name: customer-service
display_name: "客服助手 Agent"
model: default  # 推荐 gpt-4o-mini（成本优化 + 响应速度）
instructions: |
  你是一个客服助手。工作流程：
  1. 理解客户问题（产品咨询/订单查询/退款申请/投诉等）
  2. 参考 customer-service-handbook Skill 中的标准话术和政策
  3. 通过 http 工具调用业务 API 查询订单/账户信息
  4. 对于需要人工介入的请求（如复杂投诉），使用 handoff 转交
  5. 始终保持礼貌、耐心、专业
  6. 绝不泄露内部系统信息或其他客户数据
handoffs:
  - agent: human-escalation  # 可配置：转人工
tools:
  - group: http
skills:
  - customer-service-handbook
guardrails:
  input:
    - prompt_injection_detector
    - content_safety_filter
  output:
    - pii_redactor
    - content_safety_filter
```

### A.9 Summarizer

```yaml
name: summarizer
display_name: "文本摘要 Agent"
model: default  # 推荐 gpt-4o-mini
instructions: |
  你是一个文本摘要专家。摘要规则：
  1. 提取输入文本的核心信息
  2. 输出结构：一句话摘要 → 关键要点（3-5 个）→ 详细摘要
  3. 摘要长度约为原文的 20-30%
  4. 保留关键数据、人名、日期等事实信息
  5. 不添加原文中没有的推断
handoffs: []
tools: []
guardrails:
  input:
    - prompt_injection_detector
  output:
    - content_safety_filter
```

### A.10 Coordinator

```yaml
name: coordinator
display_name: "总协调员 Agent"
model: default  # 推荐 gpt-4o（需要较强的任务分解和调度能力）
instructions: |
  你是系统的总协调员。你的职责是分解复杂任务并调度执行：
  1. 分析用户任务，判断是否需要多步骤/多 Agent 协作
  2. 如果任务简单，直接使用 team::* 中合适的单个 Agent 处理
  3. 如果任务复杂，选择最合适的 Agent Team 执行：
     - 调研+报告 → research-report-team（Sequential）
     - 方案评估 → debate-team（Debate）
     - 数据分析+可视化 → data-pipeline-team（Sequential）
     - 多维度并行分析 → parallel-analysis-team（Parallel）
  4. 汇总 Team 执行结果，生成最终回复
  5. 处理执行失败的情况，进行重试或降级
handoffs: []
tools:
  - prefix: "team::*"  # Team-as-Tool，可调用所有已注册 Team
guardrails:
  input:
    - prompt_injection_detector
  output:
    - content_safety_filter
```

> 以上模板配置为默认值。用户基于模板创建 Agent 时，可修改任何字段。已创建的 Agent 不受模板后续更新影响。

---

## 附录 B：与 Agents SDK 的关键差异

| 维度 | OpenAI Agents SDK | Kasaya Framework |
|------|-------------------|----------|
| 模型绑定 | 仅 OpenAI API | Provider-agnostic（LiteLLM 适配 100+ 模型） |
| Session 后端 | SQLAlchemy / SQLite / Redis / Dapr | PostgreSQL / Redis / SQLite + 历史裁剪策略（sliding_window / token_budget / summary_prefix） |
| Approval | 无内置 | 三级审批模式 + ApprovalHandler 接口 |
| Skills | 无 | SKILL.md + metadata.yaml + scripts/ + assets/ 完整包结构 |
| Memory | 无内置 | 记忆提取（LLM-Based）/ 向量检索（pgvector）/ 置信度衰减 / GDPR 合规 |
| Sandbox | 无 | Local / Docker / K8s 三级隔离 + 安全约束矩阵 |
| 配置格式 | 纯代码 | YAML 声明式 + 代码 |
| 流式事件 | RunResultStreaming | StreamEvent 层级（更细粒度） |
| Tool Namespace | `tool_namespace()` 函数 | 自动命名空间（MCP/Skill/自定义） |
| 延迟工具加载 | `ToolSearchTool` 类 | `ToolSearchTool` + 可配置搜索策略（keyword/semantic/hybrid） |
| 工具错误处理 | `failure_error_function` | `failure_error_function` + `timeout` + 条件启用 |
| Tracing 导出 | 内置 20+ 集成 | 自研 TraceProcessor + PostgresTraceProcessor（默认）+ OTelTraceProcessor（OTel 兼容）+ ClickHouseTraceProcessor（可选） |
| Token 审计 | 无 | 内置 TokenUsageLog 提取 + PostgreSQL 聚合表（默认）/ ClickHouse 物化视图（可选） |
| Session 历史裁剪 | 无内置 | 3 种策略（sliding_window / token_budget / summary_prefix）+ HistoryTrimmer |
| Guardrails 内置库 | 无内置实现 | 6 个开箱即用护栏（PromptInjection / ContentSafety / PII / Regex / MaxToken / ToolWhitelist） |
| Memory 提取 | 无 | LLM-Based 自动提取 + 语义去重 + 置信度衰减 |
| Approval 风险分级 | 无 | RiskClassifier（工具级 LOW/MEDIUM/HIGH 分级）+ timeout/rejection policy |
| Skills 系统 | 无 | SkillLoader + SkillRegistry + SkillInjector + 版本管理 + @mention |
| Agent Team | 无 | Team / TeamConfig / TeamRunner / TeamProtocol（6 种协作协议）/ Team-as-Tool |

---

*文档版本：v2.0.0*
*最后更新：2026-04-02*
*作者：Kasaya Team*
