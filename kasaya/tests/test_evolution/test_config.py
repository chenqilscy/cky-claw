"""EvolutionConfig 测试。"""

from __future__ import annotations

from kasaya.evolution.config import EvolutionConfig


class TestEvolutionConfig:
    """EvolutionConfig dataclass 测试。"""

    def test_defaults(self) -> None:
        """默认配置值正确。"""
        cfg = EvolutionConfig()
        assert cfg.enabled is False
        assert cfg.min_samples == 50
        assert cfg.eval_threshold == 0.7
        assert cfg.feedback_negative_rate == 0.3
        assert cfg.tool_failure_rate == 0.2
        assert cfg.auto_apply is False
        assert cfg.cooldown_hours == 24
        assert cfg.max_proposals_per_cycle == 3
        assert cfg.rollback_threshold == 0.1
        assert cfg.signal_types == ["evaluation", "feedback", "tool_performance"]

    def test_custom_values(self) -> None:
        """自定义配置值正确。"""
        cfg = EvolutionConfig(
            enabled=True,
            min_samples=100,
            eval_threshold=0.8,
            auto_apply=True,
            cooldown_hours=48,
            max_proposals_per_cycle=5,
        )
        assert cfg.enabled is True
        assert cfg.min_samples == 100
        assert cfg.eval_threshold == 0.8
        assert cfg.auto_apply is True
        assert cfg.cooldown_hours == 48
        assert cfg.max_proposals_per_cycle == 5
