"""E2 Agent Maturity Model 测试。"""

from __future__ import annotations

import pytest

from ckyclaw_framework.evolution.maturity import (
    MaturityConfig,
    MaturityLevel,
    MaturityModel,
    ReflectionScore,
    _DEFAULT_DOWNGRADE_THRESHOLDS,
    _DEFAULT_UPGRADE_THRESHOLDS,
    _LEVEL_CAPABILITIES,
    _LEVEL_ORDER,
)


# ---------------------------------------------------------------------------
# MaturityLevel 枚举
# ---------------------------------------------------------------------------


class TestMaturityLevel:
    """成熟度等级枚举测试。"""

    def test_values(self) -> None:
        """枚举值正确。"""
        assert MaturityLevel.NEWBORN.value == "newborn"
        assert MaturityLevel.LEARNER.value == "learner"
        assert MaturityLevel.COMPETENT.value == "competent"
        assert MaturityLevel.EXPERT.value == "expert"

    def test_level_order(self) -> None:
        """等级顺序正确。"""
        assert _LEVEL_ORDER == [
            MaturityLevel.NEWBORN,
            MaturityLevel.LEARNER,
            MaturityLevel.COMPETENT,
            MaturityLevel.EXPERT,
        ]

    def test_is_str_enum(self) -> None:
        """值可作为字符串使用。"""
        assert MaturityLevel.EXPERT.value == "expert"
        assert MaturityLevel.EXPERT == "expert"


# ---------------------------------------------------------------------------
# MaturityConfig
# ---------------------------------------------------------------------------


class TestMaturityConfig:
    """配置测试。"""

    def test_defaults(self) -> None:
        """默认值正确。"""
        cfg = MaturityConfig()
        assert cfg.min_samples == 10
        assert cfg.downgrade_enabled is True
        assert cfg.max_history == 100
        assert sum(cfg.score_weights.values()) == pytest.approx(1.0)

    def test_custom_thresholds(self) -> None:
        """自定义阈值。"""
        custom = {MaturityLevel.NEWBORN: 0.5}
        cfg = MaturityConfig(upgrade_thresholds=custom)
        assert cfg.upgrade_thresholds[MaturityLevel.NEWBORN] == 0.5

    def test_default_thresholds_independent(self) -> None:
        """不同实例的默认阈值互不影响。"""
        cfg1 = MaturityConfig()
        cfg2 = MaturityConfig()
        cfg1.upgrade_thresholds[MaturityLevel.NEWBORN] = 0.99
        assert cfg2.upgrade_thresholds[MaturityLevel.NEWBORN] == 0.4


# ---------------------------------------------------------------------------
# ReflectionScore
# ---------------------------------------------------------------------------


class TestReflectionScore:
    """评分快照测试。"""

    def test_defaults(self) -> None:
        """默认全 0。"""
        s = ReflectionScore()
        assert s.accuracy == 0.0
        assert s.efficiency == 0.0
        assert s.tool_usage == 0.0
        assert s.safety == 0.0

    def test_as_dict(self) -> None:
        """转字典。"""
        s = ReflectionScore(accuracy=0.9, efficiency=0.7, tool_usage=0.8, safety=1.0)
        d = s.as_dict
        assert d == {"accuracy": 0.9, "efficiency": 0.7, "tool_usage": 0.8, "safety": 1.0}


# ---------------------------------------------------------------------------
# MaturityModel — 基础功能
# ---------------------------------------------------------------------------


class TestMaturityModelBasic:
    """MaturityModel 基础功能测试。"""

    def test_default_level(self) -> None:
        """默认等级为 NEWBORN。"""
        m = MaturityModel(agent_name="test")
        assert m.level == MaturityLevel.NEWBORN

    def test_record_score(self) -> None:
        """记录评分后样本数增加。"""
        m = MaturityModel(agent_name="test")
        assert m.sample_count == 0
        m.record_score(ReflectionScore(accuracy=0.5))
        assert m.sample_count == 1

    def test_record_scores_dict(self) -> None:
        """从字典记录评分。"""
        m = MaturityModel(agent_name="test")
        m.record_scores_dict({"accuracy": 0.8, "efficiency": 0.7})
        assert m.sample_count == 1

    def test_empty_history_score(self) -> None:
        """历史为空时返回 0.0。"""
        m = MaturityModel(agent_name="test")
        assert m.current_score() == 0.0

    def test_current_score_single(self) -> None:
        """单条记录的加权平均分。"""
        m = MaturityModel(agent_name="test")
        # weights: accuracy=0.35, efficiency=0.20, tool_usage=0.20, safety=0.25
        # score: 1.0 × 0.35 + 0.5 × 0.20 + 0.5 × 0.20 + 1.0 × 0.25 = 0.80
        m.record_score(ReflectionScore(accuracy=1.0, efficiency=0.5, tool_usage=0.5, safety=1.0))
        assert m.current_score() == pytest.approx(0.80)

    def test_current_score_multiple(self) -> None:
        """多条记录的平均分。"""
        m = MaturityModel(agent_name="test")
        # 全 1.0 → overall = 1.0
        m.record_score(ReflectionScore(accuracy=1.0, efficiency=1.0, tool_usage=1.0, safety=1.0))
        # 全 0.0 → overall = 0.0
        m.record_score(ReflectionScore(accuracy=0.0, efficiency=0.0, tool_usage=0.0, safety=0.0))
        # 平均 = 0.5
        assert m.current_score() == pytest.approx(0.5)


# ---------------------------------------------------------------------------
# MaturityModel — 升降级
# ---------------------------------------------------------------------------


def _make_model_with_scores(
    agent_name: str,
    level: MaturityLevel,
    accuracy: float,
    count: int = 10,
) -> MaturityModel:
    """辅助：创建带稳定评分历史的 model。"""
    m = MaturityModel(agent_name=agent_name, level=level)
    for _ in range(count):
        m.record_score(ReflectionScore(
            accuracy=accuracy,
            efficiency=accuracy,
            tool_usage=accuracy,
            safety=accuracy,
        ))
    return m


class TestUpgrade:
    """升级逻辑测试。"""

    def test_should_upgrade_newborn_to_learner(self) -> None:
        """NEWBORN → LEARNER（score >= 0.4）。"""
        m = _make_model_with_scores("a", MaturityLevel.NEWBORN, 0.5)
        assert m.should_upgrade() is True

    def test_should_not_upgrade_insufficient_samples(self) -> None:
        """样本不足时不升级。"""
        m = _make_model_with_scores("a", MaturityLevel.NEWBORN, 0.5, count=5)
        assert m.should_upgrade() is False

    def test_should_not_upgrade_low_score(self) -> None:
        """分数不够时不升级。"""
        m = _make_model_with_scores("a", MaturityLevel.NEWBORN, 0.3)
        assert m.should_upgrade() is False

    def test_should_not_upgrade_expert(self) -> None:
        """EXPERT 不可再升。"""
        m = _make_model_with_scores("a", MaturityLevel.EXPERT, 1.0)
        assert m.should_upgrade() is False

    def test_upgrade_changes_level(self) -> None:
        """升级后等级变化。"""
        m = _make_model_with_scores("a", MaturityLevel.NEWBORN, 0.5)
        result = m.upgrade()
        assert result == MaturityLevel.LEARNER
        assert m.level == MaturityLevel.LEARNER

    def test_upgrade_expert_raises(self) -> None:
        """EXPERT 升级抛出异常。"""
        m = _make_model_with_scores("a", MaturityLevel.EXPERT, 1.0)
        with pytest.raises(ValueError, match="最高等级"):
            m.upgrade()

    def test_full_upgrade_path(self) -> None:
        """完整升级路径：NEWBORN → LEARNER → COMPETENT → EXPERT。"""
        m = MaturityModel(agent_name="grow")

        # NEWBORN → LEARNER (threshold 0.4)
        for _ in range(10):
            m.record_score(ReflectionScore(accuracy=0.5, efficiency=0.5, tool_usage=0.5, safety=0.5))
        assert m.should_upgrade() is True
        m.upgrade()
        assert m.level == MaturityLevel.LEARNER

        # LEARNER → COMPETENT (threshold 0.6)
        m._history.clear()
        for _ in range(10):
            m.record_score(ReflectionScore(accuracy=0.7, efficiency=0.7, tool_usage=0.7, safety=0.7))
        assert m.should_upgrade() is True
        m.upgrade()
        assert m.level == MaturityLevel.COMPETENT

        # COMPETENT → EXPERT (threshold 0.8)
        m._history.clear()
        for _ in range(10):
            m.record_score(ReflectionScore(accuracy=0.9, efficiency=0.9, tool_usage=0.9, safety=0.9))
        assert m.should_upgrade() is True
        m.upgrade()
        assert m.level == MaturityLevel.EXPERT


class TestDowngrade:
    """降级逻辑测试。"""

    def test_should_downgrade_learner(self) -> None:
        """LEARNER 分数过低时降级。"""
        m = _make_model_with_scores("a", MaturityLevel.LEARNER, 0.2)
        assert m.should_downgrade() is True

    def test_should_not_downgrade_newborn(self) -> None:
        """NEWBORN 不可再降。"""
        m = _make_model_with_scores("a", MaturityLevel.NEWBORN, 0.0)
        assert m.should_downgrade() is False

    def test_should_not_downgrade_when_disabled(self) -> None:
        """降级关闭时不降级。"""
        cfg = MaturityConfig(downgrade_enabled=False)
        m = MaturityModel(agent_name="a", level=MaturityLevel.LEARNER, config=cfg)
        for _ in range(10):
            m.record_score(ReflectionScore(accuracy=0.1))
        assert m.should_downgrade() is False

    def test_should_not_downgrade_insufficient_samples(self) -> None:
        """样本不足时不降级。"""
        m = _make_model_with_scores("a", MaturityLevel.LEARNER, 0.1, count=5)
        assert m.should_downgrade() is False

    def test_downgrade_changes_level(self) -> None:
        """降级后等级变化。"""
        m = _make_model_with_scores("a", MaturityLevel.LEARNER, 0.1)
        result = m.downgrade()
        assert result == MaturityLevel.NEWBORN
        assert m.level == MaturityLevel.NEWBORN

    def test_downgrade_newborn_raises(self) -> None:
        """NEWBORN 降级抛出异常。"""
        m = _make_model_with_scores("a", MaturityLevel.NEWBORN, 0.0)
        with pytest.raises(ValueError, match="最低等级"):
            m.downgrade()


# ---------------------------------------------------------------------------
# MaturityModel — 自动调整
# ---------------------------------------------------------------------------


class TestAutoAdjust:
    """自动调整测试。"""

    def test_auto_upgrade(self) -> None:
        """自动升级。"""
        m = _make_model_with_scores("a", MaturityLevel.NEWBORN, 0.5)
        result = m.try_auto_adjust()
        assert result == MaturityLevel.LEARNER

    def test_auto_downgrade(self) -> None:
        """自动降级。"""
        m = _make_model_with_scores("a", MaturityLevel.LEARNER, 0.1)
        result = m.try_auto_adjust()
        assert result == MaturityLevel.NEWBORN

    def test_no_change(self) -> None:
        """无变化时返回 None。"""
        # 正好在 NEWBORN 和 LEARNER 之间
        m = _make_model_with_scores("a", MaturityLevel.NEWBORN, 0.3)
        result = m.try_auto_adjust()
        assert result is None


# ---------------------------------------------------------------------------
# MaturityModel — Capabilities
# ---------------------------------------------------------------------------


class TestCapabilities:
    """能力配置测试。"""

    def test_newborn_capabilities(self) -> None:
        """NEWBORN 能力受限。"""
        m = MaturityModel(agent_name="test", level=MaturityLevel.NEWBORN)
        caps = m.capabilities
        assert caps["auto_apply_proposals"] is False
        assert caps["can_create_skills"] is False
        assert caps["can_handoff"] is False
        assert caps["approval_mode"] == "suggest"

    def test_expert_capabilities(self) -> None:
        """EXPERT 能力最强。"""
        m = MaturityModel(agent_name="test", level=MaturityLevel.EXPERT)
        caps = m.capabilities
        assert caps["auto_apply_proposals"] is True
        assert caps["can_create_skills"] is True
        assert caps["can_handoff"] is True
        assert caps["approval_mode"] == "full-auto"
        assert caps["max_tools"] == 100

    def test_capabilities_is_copy(self) -> None:
        """返回的是副本，修改不影响原始数据。"""
        m = MaturityModel(agent_name="test", level=MaturityLevel.EXPERT)
        caps = m.capabilities
        caps["max_tools"] = 999
        assert m.capabilities["max_tools"] == 100

    def test_all_levels_have_capabilities(self) -> None:
        """所有等级都有能力配置。"""
        for level in MaturityLevel:
            assert level in _LEVEL_CAPABILITIES


# ---------------------------------------------------------------------------
# MaturityModel — 滑动窗口
# ---------------------------------------------------------------------------


class TestSlidingWindow:
    """滑动窗口测试。"""

    def test_max_history_enforced(self) -> None:
        """超过 max_history 时自动淘汰旧记录。"""
        cfg = MaturityConfig(max_history=5)
        m = MaturityModel(agent_name="test", config=cfg)
        for i in range(10):
            m.record_score(ReflectionScore(accuracy=float(i) / 10))
        assert m.sample_count == 5

    def test_sliding_window_keeps_latest(self) -> None:
        """滑动窗口保留最新记录。"""
        cfg = MaturityConfig(max_history=3)
        m = MaturityModel(agent_name="test", config=cfg)
        for i in range(5):
            m.record_score(ReflectionScore(accuracy=float(i) / 10))
        # 保留 i=2,3,4 → accuracy=0.2,0.3,0.4
        scores = [s.accuracy for s in m._history]
        assert scores == [0.2, 0.3, 0.4]


# ---------------------------------------------------------------------------
# MaturityModel — 序列化
# ---------------------------------------------------------------------------


class TestSerialization:
    """序列化/反序列化测试。"""

    def test_to_dict(self) -> None:
        """序列化为字典。"""
        m = MaturityModel(agent_name="test-agent", level=MaturityLevel.COMPETENT)
        d = m.to_dict()
        assert d["agent_name"] == "test-agent"
        assert d["level"] == "competent"
        assert "capabilities" in d
        assert "current_score" in d

    def test_from_dict(self) -> None:
        """从字典反序列化。"""
        data = {"agent_name": "test-agent", "level": "learner"}
        m = MaturityModel.from_dict(data)
        assert m.agent_name == "test-agent"
        assert m.level == MaturityLevel.LEARNER

    def test_roundtrip(self) -> None:
        """序列化→反序列化往返。"""
        m1 = MaturityModel(agent_name="roundtrip", level=MaturityLevel.EXPERT)
        d = m1.to_dict()
        m2 = MaturityModel.from_dict(d)
        assert m2.agent_name == m1.agent_name
        assert m2.level == m1.level

    def test_from_dict_default_level(self) -> None:
        """缺少 level 字段时默认 NEWBORN。"""
        data = {"agent_name": "no-level"}
        m = MaturityModel.from_dict(data)
        assert m.level == MaturityLevel.NEWBORN


# ---------------------------------------------------------------------------
# 边界场景
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """边界条件测试。"""

    def test_zero_weights(self) -> None:
        """权重全为 0 时返回 0.0。"""
        cfg = MaturityConfig(score_weights={"accuracy": 0.0, "efficiency": 0.0, "tool_usage": 0.0, "safety": 0.0})
        m = MaturityModel(agent_name="test", config=cfg)
        m.record_score(ReflectionScore(accuracy=1.0))
        assert m.current_score() == 0.0

    def test_custom_min_samples(self) -> None:
        """自定义最低样本数。"""
        cfg = MaturityConfig(min_samples=3)
        m = MaturityModel(agent_name="test", config=cfg)
        for _ in range(3):
            m.record_score(ReflectionScore(accuracy=0.9, efficiency=0.9, tool_usage=0.9, safety=0.9))
        assert m.should_upgrade() is True

    def test_just_above_threshold_upgrade(self) -> None:
        """略高于阈值时应升级。"""
        # NEWBORN threshold = 0.4, 0.41 略高于
        m = _make_model_with_scores("a", MaturityLevel.NEWBORN, 0.41)
        assert m.should_upgrade() is True

    def test_just_above_downgrade_threshold(self) -> None:
        """略高于降级阈值时不降级。"""
        # LEARNER downgrade threshold = 0.3, 0.31 略高于
        m = _make_model_with_scores("a", MaturityLevel.LEARNER, 0.31)
        assert m.should_downgrade() is False
