"""Evolution 配置。"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class EvolutionConfig:
    """Agent 自动进化配置。

    控制进化机制的触发条件、频率和安全策略。
    """

    enabled: bool = False
    """是否启用自动进化。"""

    min_samples: int = 50
    """触发优化分析的最小运行样本数。样本不足时不生成建议。"""

    eval_threshold: float = 0.7
    """评分阈值。Agent 平均评分低于此值时触发优化建议生成。"""

    feedback_negative_rate: float = 0.3
    """负反馈率阈值。负反馈占比超过此值时触发优化。"""

    tool_failure_rate: float = 0.2
    """工具失败率阈值。某工具失败率超过此值时建议调整工具配置。"""

    auto_apply: bool = False
    """是否自动应用优化建议。False 时生成建议等待人工审批，True 时自动应用。"""

    cooldown_hours: int = 24
    """两次优化分析的最小间隔（小时）。防止频繁触发。"""

    max_proposals_per_cycle: int = 3
    """每次优化周期最多生成的建议数量。"""

    rollback_threshold: float = 0.1
    """效果退化阈值。应用优化后评分下降超过此比例时自动回滚。"""

    signal_types: list[str] = field(default_factory=lambda: ["evaluation", "feedback", "tool_performance"])
    """启用的信号类型列表。"""
