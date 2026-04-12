"""MaturityModel — Agent 成熟度等级模型。

基于 S5 LearningLoop 的 RunReflection 四维评分，
自动评估 Agent 的成熟度等级（Newborn→Learner→Competent→Expert），
并根据等级解锁不同的能力权限。
"""

from __future__ import annotations

import logging
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class MaturityLevel(str, Enum):
    """Agent 成熟度等级。"""

    NEWBORN = "newborn"
    """新生（overall 0-0.4）：需要监督，能力受限。"""

    LEARNER = "learner"
    """学习者（overall 0.4-0.6）：能完成任务但不稳定。"""

    COMPETENT = "competent"
    """胜任者（overall 0.6-0.8）：稳定完成任务。"""

    EXPERT = "expert"
    """专家（overall 0.8-1.0）：高质量输出，可自主优化。"""


# 等级顺序，用于升降级比较
_LEVEL_ORDER: list[MaturityLevel] = [
    MaturityLevel.NEWBORN,
    MaturityLevel.LEARNER,
    MaturityLevel.COMPETENT,
    MaturityLevel.EXPERT,
]

# 默认升级阈值
_DEFAULT_UPGRADE_THRESHOLDS: dict[MaturityLevel, float] = {
    MaturityLevel.NEWBORN: 0.4,    # NEWBORN → LEARNER
    MaturityLevel.LEARNER: 0.6,    # LEARNER → COMPETENT
    MaturityLevel.COMPETENT: 0.8,  # COMPETENT → EXPERT
}

# 默认降级阈值（低于此值降级）
_DEFAULT_DOWNGRADE_THRESHOLDS: dict[MaturityLevel, float] = {
    MaturityLevel.LEARNER: 0.3,    # LEARNER → NEWBORN
    MaturityLevel.COMPETENT: 0.5,  # COMPETENT → LEARNER
    MaturityLevel.EXPERT: 0.7,     # EXPERT → COMPETENT
}

# 每个等级的能力配置
_LEVEL_CAPABILITIES: dict[MaturityLevel, dict[str, Any]] = {
    MaturityLevel.NEWBORN: {
        "auto_apply_proposals": False,
        "max_tools": 10,
        "max_turns": 5,
        "can_create_skills": False,
        "can_handoff": False,
        "approval_mode": "suggest",
    },
    MaturityLevel.LEARNER: {
        "auto_apply_proposals": False,
        "max_tools": 20,
        "max_turns": 10,
        "can_create_skills": False,
        "can_handoff": True,
        "approval_mode": "suggest",
    },
    MaturityLevel.COMPETENT: {
        "auto_apply_proposals": False,
        "max_tools": 50,
        "max_turns": 20,
        "can_create_skills": True,
        "can_handoff": True,
        "approval_mode": "auto-edit",
    },
    MaturityLevel.EXPERT: {
        "auto_apply_proposals": True,
        "max_tools": 100,
        "max_turns": 50,
        "can_create_skills": True,
        "can_handoff": True,
        "approval_mode": "full-auto",
    },
}


@dataclass
class MaturityConfig:
    """成熟度模型配置。"""

    upgrade_thresholds: dict[MaturityLevel, float] = field(
        default_factory=lambda: dict(_DEFAULT_UPGRADE_THRESHOLDS),
    )
    """每个等级的升级阈值：当前等级 → 升级所需最低分。"""

    downgrade_thresholds: dict[MaturityLevel, float] = field(
        default_factory=lambda: dict(_DEFAULT_DOWNGRADE_THRESHOLDS),
    )
    """每个等级的降级阈值：低于此分时降级。"""

    min_samples: int = 10
    """升级所需最低评估样本数。"""

    downgrade_enabled: bool = True
    """是否启用自动降级。"""

    max_history: int = 100
    """保留的评分历史最大条数（滑动窗口）。"""

    score_weights: dict[str, float] = field(
        default_factory=lambda: {
            "accuracy": 0.35,
            "efficiency": 0.20,
            "tool_usage": 0.20,
            "safety": 0.25,
        },
    )
    """四维评分的加权权重（总和为 1.0）。"""


@dataclass
class ReflectionScore:
    """单次运行的四维评分快照。"""

    accuracy: float = 0.0
    efficiency: float = 0.0
    tool_usage: float = 0.0
    safety: float = 0.0

    @property
    def as_dict(self) -> dict[str, float]:
        """转为字典。"""
        return {
            "accuracy": self.accuracy,
            "efficiency": self.efficiency,
            "tool_usage": self.tool_usage,
            "safety": self.safety,
        }


@dataclass
class MaturityModel:
    """Agent 成熟度模型。

    跟踪 Agent 的运行评分历史，自动判断升降级，
    并根据当前等级返回对应的能力配置。

    与 S5 LearningLoop 的 RunReflection 集成：
    - RunReflection.scores → ReflectionScore → 记录到历史
    - 加权平均 overall → 与阈值比较 → 升/降级

    Example:
        model = MaturityModel(agent_name="my-agent")
        model.record_score(ReflectionScore(accuracy=0.9, efficiency=0.7, tool_usage=0.8, safety=1.0))
        if model.should_upgrade():
            model.upgrade()
    """

    agent_name: str
    """Agent 名称。"""

    level: MaturityLevel = MaturityLevel.NEWBORN
    """当前成熟度等级。"""

    config: MaturityConfig = field(default_factory=MaturityConfig)
    """配置。"""

    _history: deque[ReflectionScore] = field(
        default_factory=lambda: deque(maxlen=100),
        repr=False,
    )
    """评分历史（滑动窗口）。"""

    def __post_init__(self) -> None:
        """初始化后调整 deque 最大长度。"""
        if self._history.maxlen != self.config.max_history:
            old = list(self._history)
            self._history = deque(old, maxlen=self.config.max_history)

    def record_score(self, score: ReflectionScore) -> None:
        """记录一次运行评分。

        Args:
            score: 四维评分快照。
        """
        self._history.append(score)

    def record_scores_dict(self, scores: dict[str, float]) -> None:
        """从字典记录评分（与 RunReflection.scores 兼容）。

        Args:
            scores: {"accuracy": float, "efficiency": float, ...}。
        """
        self.record_score(ReflectionScore(
            accuracy=scores.get("accuracy", 0.0),
            efficiency=scores.get("efficiency", 0.0),
            tool_usage=scores.get("tool_usage", 0.0),
            safety=scores.get("safety", 0.0),
        ))

    def current_score(self) -> float:
        """计算当前加权平均分。

        Returns:
            0.0-1.0 的 overall 评分。历史为空时返回 0.0。
        """
        if not self._history:
            return 0.0

        weights = self.config.score_weights
        total_weight = sum(weights.values())
        if total_weight == 0:
            return 0.0

        overall = 0.0
        for score in self._history:
            score_sum = sum(
                score.as_dict.get(dim, 0.0) * w
                for dim, w in weights.items()
            )
            overall += score_sum / total_weight

        return overall / len(self._history)

    @property
    def sample_count(self) -> int:
        """当前历史样本数。"""
        return len(self._history)

    def should_upgrade(self) -> bool:
        """判断是否应该升级。

        条件：
        1. 当前不是最高等级
        2. 样本数 >= min_samples
        3. overall 分数 >= 当前等级的升级阈值
        """
        level_idx = _LEVEL_ORDER.index(self.level)
        if level_idx >= len(_LEVEL_ORDER) - 1:
            return False  # 已是最高级

        if self.sample_count < self.config.min_samples:
            return False

        threshold = self.config.upgrade_thresholds.get(self.level, 1.0)
        return self.current_score() >= threshold

    def should_downgrade(self) -> bool:
        """判断是否应该降级。

        条件：
        1. 降级已启用
        2. 当前不是最低等级
        3. 样本数 >= min_samples
        4. overall 分数 < 当前等级的降级阈值
        """
        if not self.config.downgrade_enabled:
            return False

        level_idx = _LEVEL_ORDER.index(self.level)
        if level_idx <= 0:
            return False  # 已是最低级

        if self.sample_count < self.config.min_samples:
            return False

        threshold = self.config.downgrade_thresholds.get(self.level, 0.0)
        return self.current_score() < threshold

    def upgrade(self) -> MaturityLevel:
        """执行升级。

        Returns:
            升级后的等级。

        Raises:
            ValueError: 已是最高等级时抛出。
        """
        level_idx = _LEVEL_ORDER.index(self.level)
        if level_idx >= len(_LEVEL_ORDER) - 1:
            raise ValueError(f"Agent '{self.agent_name}' 已是最高等级 {self.level.value}")

        old_level = self.level
        self.level = _LEVEL_ORDER[level_idx + 1]
        logger.info(
            "Agent '%s' 升级: %s → %s (score=%.3f, samples=%d)",
            self.agent_name, old_level.value, self.level.value,
            self.current_score(), self.sample_count,
        )
        return self.level

    def downgrade(self) -> MaturityLevel:
        """执行降级。

        Returns:
            降级后的等级。

        Raises:
            ValueError: 已是最低等级时抛出。
        """
        level_idx = _LEVEL_ORDER.index(self.level)
        if level_idx <= 0:
            raise ValueError(f"Agent '{self.agent_name}' 已是最低等级 {self.level.value}")

        old_level = self.level
        self.level = _LEVEL_ORDER[level_idx - 1]
        logger.info(
            "Agent '%s' 降级: %s → %s (score=%.3f, samples=%d)",
            self.agent_name, old_level.value, self.level.value,
            self.current_score(), self.sample_count,
        )
        return self.level

    def try_auto_adjust(self) -> MaturityLevel | None:
        """自动调整等级（升级或降级）。

        Returns:
            调整后的新等级，无变化时返回 None。
        """
        if self.should_upgrade():
            return self.upgrade()
        if self.should_downgrade():
            return self.downgrade()
        return None

    @property
    def capabilities(self) -> dict[str, Any]:
        """当前等级对应的能力配置。"""
        return dict(_LEVEL_CAPABILITIES.get(self.level, {}))

    def to_dict(self) -> dict[str, Any]:
        """序列化为字典（便于持久化）。"""
        return {
            "agent_name": self.agent_name,
            "level": self.level.value,
            "current_score": round(self.current_score(), 4),
            "sample_count": self.sample_count,
            "capabilities": self.capabilities,
        }

    @classmethod
    def from_dict(
        cls,
        data: dict[str, Any],
        config: MaturityConfig | None = None,
    ) -> MaturityModel:
        """从字典反序列化。"""
        return cls(
            agent_name=data["agent_name"],
            level=MaturityLevel(data.get("level", "newborn")),
            config=config or MaturityConfig(),
        )
