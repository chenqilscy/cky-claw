"""Step — 工作流步骤定义。"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class StepType(StrEnum):
    """步骤类型。"""

    AGENT = "agent"
    PARALLEL = "parallel"
    CONDITIONAL = "conditional"
    LOOP = "loop"


class StepStatus(StrEnum):
    """步骤执行状态。"""

    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    CANCELLED = "cancelled"


@dataclass
class StepIO:
    """步骤输入/输出映射。"""

    input_keys: dict[str, str] = field(default_factory=dict)
    output_keys: dict[str, str] = field(default_factory=dict)


@dataclass
class RetryConfig:
    """步骤重试配置。"""

    max_retries: int = 2
    delay_seconds: float = 1.0
    backoff_multiplier: float = 2.0


@dataclass
class Step:
    """步骤基类。"""

    id: str
    name: str = ""
    type: StepType = StepType.AGENT
    io: StepIO = field(default_factory=StepIO)
    retry_config: RetryConfig | None = None
    timeout: float | None = None


@dataclass
class AgentStep(Step):
    """Agent 执行步骤。"""

    agent_name: str = ""
    prompt_template: str = ""
    max_turns: int = 10

    def __post_init__(self) -> None:
        self.type = StepType.AGENT


@dataclass
class BranchCondition:
    """条件分支。"""

    label: str
    condition: str
    target_step_id: str


@dataclass
class ConditionalStep(Step):
    """条件分支步骤。"""

    branches: list[BranchCondition] = field(default_factory=list)
    default_step_id: str | None = None

    def __post_init__(self) -> None:
        self.type = StepType.CONDITIONAL


@dataclass
class ParallelStep(Step):
    """并行执行步骤 — sub_steps 通过 TaskGroup 真正并行执行。"""

    sub_steps: list[AgentStep | ConditionalStep] = field(default_factory=list)
    fail_policy: str = "fail_fast"

    def __post_init__(self) -> None:
        self.type = StepType.PARALLEL


@dataclass
class LoopStep(Step):
    """循环迭代步骤 — while 语义（先检查 condition 再执行 body）。"""

    body_steps: list[AgentStep | ConditionalStep] = field(default_factory=list)
    condition: str = ""
    max_iterations: int = 10
    iteration_output_key: str = ""

    def __post_init__(self) -> None:
        self.type = StepType.LOOP
