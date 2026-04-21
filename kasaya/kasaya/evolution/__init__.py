"""自动学习进化机制（Auto-Learning Evolution）。

提供 Agent 自进化能力：从运行信号（评分、反馈、工具成功率等）自动生成优化建议，
经人工审批后安全应用到 Agent 配置。

三层架构：
- **信号采集（Signal Collection）**：从 Evaluation/Feedback/Tracing 提取优化信号
- **策略生成（Strategy Generation）**：基于信号生成 Instructions/Tools/Guardrails 优化建议
- **安全应用（Safe Application）**：版本快照 + 人工审批 + 效果对比 + 自动回滚
"""

from __future__ import annotations

from kasaya.evolution.config import EvolutionConfig
from kasaya.evolution.hooks import EvolutionHook
from kasaya.evolution.learning_loop import (
    LearningLoop,
    RunReflection,
    RunReflector,
)
from kasaya.evolution.maturity import (
    MaturityConfig,
    MaturityLevel,
    MaturityModel,
    ReflectionScore,
)
from kasaya.evolution.proposal import (
    EvolutionProposal,
    ProposalStatus,
    ProposalType,
)
from kasaya.evolution.signals import (
    EvolutionSignal,
    FeedbackSignal,
    MetricSignal,
    SignalCollector,
    SignalType,
    ToolPerformanceSignal,
)
from kasaya.evolution.strategy import EvolutionStrategy, StrategyEngine

__all__ = [
    "EvolutionConfig",
    "EvolutionHook",
    "EvolutionProposal",
    "EvolutionSignal",
    "EvolutionStrategy",
    "FeedbackSignal",
    "LearningLoop",
    "MaturityConfig",
    "MaturityLevel",
    "MaturityModel",
    "MetricSignal",
    "ProposalStatus",
    "ProposalType",
    "ReflectionScore",
    "RunReflection",
    "RunReflector",
    "SignalCollector",
    "SignalType",
    "StrategyEngine",
    "ToolPerformanceSignal",
]
