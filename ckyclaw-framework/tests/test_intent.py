"""Intent Detection — 意图检测与飘移处理测试。"""

from __future__ import annotations

import pytest

from ckyclaw_framework.intent import (
    IntentDetector,
    IntentSignal,
    KeywordIntentDetector,
    _compute_drift_score,
    _extract_keywords,
)
from ckyclaw_framework.model.message import Message, MessageRole


# ---------------------------------------------------------------------------
# IntentSignal 测试
# ---------------------------------------------------------------------------


class TestIntentSignal:
    """IntentSignal 数据类测试。"""

    def test_default_values(self) -> None:
        signal = IntentSignal()
        assert signal.drift_score == 0.0
        assert signal.is_drifted is False
        assert signal.original_keywords == frozenset()
        assert signal.current_keywords == frozenset()

    def test_frozen(self) -> None:
        """IntentSignal 应该是不可变的。"""
        signal = IntentSignal(drift_score=0.5)
        with pytest.raises(AttributeError):
            signal.drift_score = 0.8  # type: ignore[misc]


# ---------------------------------------------------------------------------
# _extract_keywords 测试
# ---------------------------------------------------------------------------


class TestExtractKeywords:
    """关键词提取测试。"""

    def test_chinese_text(self) -> None:
        kw = _extract_keywords("帮我写一个排序算法")
        assert "排序" in kw or "算法" in kw
        # 停用词 "帮我" 应被过滤
        assert "帮我" not in kw

    def test_english_text(self) -> None:
        kw = _extract_keywords("write a sorting algorithm in Python")
        assert "sorting" in kw
        assert "algorithm" in kw
        assert "python" in kw
        # 停用词 "a", "in" 应被过滤
        assert "a" not in kw
        assert "in" not in kw

    def test_mixed_text(self) -> None:
        kw = _extract_keywords("用 Python 实现一个 binary search")
        assert "python" in kw
        assert "binary" in kw
        assert "search" in kw

    def test_empty_text(self) -> None:
        kw = _extract_keywords("")
        assert kw == frozenset()

    def test_only_stop_words(self) -> None:
        kw = _extract_keywords("的 了 是")
        assert kw == frozenset()

    def test_max_keywords_limit(self) -> None:
        text = " ".join(f"keyword{i}" for i in range(50))
        kw = _extract_keywords(text, max_keywords=5)
        assert len(kw) <= 5

    def test_single_char_filtered(self) -> None:
        """单字符 token 应被过滤（len > 1 条件）。"""
        kw = _extract_keywords("a b c")
        assert kw == frozenset()


# ---------------------------------------------------------------------------
# _compute_drift_score 测试
# ---------------------------------------------------------------------------


class TestComputeDriftScore:
    """飘移分数计算测试。"""

    def test_identical_sets(self) -> None:
        score = _compute_drift_score(frozenset({"a", "b"}), frozenset({"a", "b"}))
        assert score == 0.0

    def test_completely_different(self) -> None:
        score = _compute_drift_score(frozenset({"a", "b"}), frozenset({"c", "d"}))
        assert score == 1.0

    def test_partial_overlap(self) -> None:
        score = _compute_drift_score(frozenset({"a", "b", "c"}), frozenset({"b", "c", "d"}))
        # Jaccard = 2/4 = 0.5, drift = 0.5
        assert score == 0.5

    def test_both_empty(self) -> None:
        score = _compute_drift_score(frozenset(), frozenset())
        assert score == 0.0

    def test_one_empty(self) -> None:
        score = _compute_drift_score(frozenset({"a"}), frozenset())
        assert score == 1.0

    def test_other_empty(self) -> None:
        score = _compute_drift_score(frozenset(), frozenset({"a"}))
        assert score == 1.0


# ---------------------------------------------------------------------------
# KeywordIntentDetector 测试
# ---------------------------------------------------------------------------


def _msg(role: str, content: str) -> Message:
    """快速构造 Message。"""
    return Message(role=MessageRole(role), content=content)


class TestKeywordIntentDetector:
    """KeywordIntentDetector 核心逻辑测试。"""

    @pytest.mark.asyncio
    async def test_no_drift_same_topic(self) -> None:
        """同一主题的多轮对话不应判定飘移。"""
        detector = KeywordIntentDetector()
        messages = [
            _msg("user", "帮我写一个排序算法"),
            _msg("assistant", "好的，这是一个快速排序的实现..."),
            _msg("user", "能优化这个排序算法的性能吗"),
        ]
        signal = await detector.detect(messages, threshold=0.6)
        assert signal.is_drifted is False

    @pytest.mark.asyncio
    async def test_drift_different_topic(self) -> None:
        """完全不同主题应判定飘移。"""
        detector = KeywordIntentDetector()
        messages = [
            _msg("user", "帮我写一个排序算法"),
            _msg("assistant", "好的..."),
            _msg("user", "今天天气怎么样"),
        ]
        signal = await detector.detect(messages, threshold=0.3)
        assert signal.is_drifted is True
        assert signal.drift_score > 0.3

    @pytest.mark.asyncio
    async def test_single_message_no_drift(self) -> None:
        """只有一条 user 消息时不应判定飘移。"""
        detector = KeywordIntentDetector()
        messages = [_msg("user", "hello")]
        signal = await detector.detect(messages)
        assert signal.is_drifted is False
        assert signal.drift_score == 0.0

    @pytest.mark.asyncio
    async def test_no_user_messages(self) -> None:
        """无 user 消息时不应判定飘移。"""
        detector = KeywordIntentDetector()
        messages = [_msg("system", "你是一个助手")]
        signal = await detector.detect(messages)
        assert signal.is_drifted is False

    @pytest.mark.asyncio
    async def test_empty_messages(self) -> None:
        """空消息列表不应判定飘移。"""
        detector = KeywordIntentDetector()
        signal = await detector.detect([])
        assert signal.is_drifted is False

    @pytest.mark.asyncio
    async def test_custom_threshold(self) -> None:
        """自定义阈值生效。"""
        detector = KeywordIntentDetector()
        messages = [
            _msg("user", "Python sorting algorithm implementation"),
            _msg("assistant", "Here's quicksort..."),
            _msg("user", "What about weather forecast today"),
        ]
        # 高阈值 → 不飘移
        signal_high = await detector.detect(messages, threshold=0.99)
        # 低阈值 → 飘移
        signal_low = await detector.detect(messages, threshold=0.1)
        assert signal_high.is_drifted is False or signal_low.is_drifted is True

    @pytest.mark.asyncio
    async def test_recent_window(self) -> None:
        """recent_window 参数控制检测窗口大小。"""
        detector = KeywordIntentDetector(recent_window=1)
        messages = [
            _msg("user", "写排序算法"),
            _msg("assistant", "..."),
            _msg("user", "写搜索算法"),  # 仍然是算法主题
            _msg("assistant", "..."),
            _msg("user", "今天天气"),  # 飘移
        ]
        signal = await detector.detect(messages, threshold=0.3)
        # recent_window=1 → 只看最后一条 "今天天气"
        assert signal.drift_score > 0.0

    @pytest.mark.asyncio
    async def test_return_keywords(self) -> None:
        """返回的 IntentSignal 包含关键词。"""
        detector = KeywordIntentDetector()
        messages = [
            _msg("user", "Python machine learning tutorial"),
            _msg("assistant", "Sure..."),
            _msg("user", "How about deep learning frameworks"),
        ]
        signal = await detector.detect(messages)
        assert len(signal.original_keywords) > 0
        assert len(signal.current_keywords) > 0

    @pytest.mark.asyncio
    async def test_recent_window_min_one(self) -> None:
        """recent_window 不能小于 1。"""
        detector = KeywordIntentDetector(recent_window=0)
        assert detector._recent_window == 1


class TestIntentDetectorABC:
    """IntentDetector ABC 测试。"""

    def test_is_abstract(self) -> None:
        """IntentDetector 不能直接实例化。"""
        with pytest.raises(TypeError):
            IntentDetector()  # type: ignore[abstract]

    def test_subclass(self) -> None:
        """KeywordIntentDetector 是 IntentDetector 子类。"""
        assert issubclass(KeywordIntentDetector, IntentDetector)


# ---------------------------------------------------------------------------
# Runner 集成测试（mock）
# ---------------------------------------------------------------------------


class TestRunnerIntegration:
    """Runner 中意图检测集成测试。"""

    def test_run_config_has_intent_fields(self) -> None:
        """RunConfig 应有 intent_detector 和 drift_threshold 字段。"""
        from ckyclaw_framework.runner.run_config import RunConfig

        config = RunConfig()
        assert config.intent_detector is None
        assert config.drift_threshold == 0.6

    def test_run_config_custom_threshold(self) -> None:
        from ckyclaw_framework.runner.run_config import RunConfig

        config = RunConfig(drift_threshold=0.8)
        assert config.drift_threshold == 0.8

    def test_run_hooks_has_on_intent_drift(self) -> None:
        """RunHooks 应有 on_intent_drift 字段。"""
        from ckyclaw_framework.runner.hooks import RunHooks

        hooks = RunHooks()
        assert hooks.on_intent_drift is None

    def test_run_hooks_on_intent_drift_callable(self) -> None:
        from ckyclaw_framework.runner.hooks import RunHooks

        async def my_handler(ctx, signal):
            pass

        hooks = RunHooks(on_intent_drift=my_handler)
        assert hooks.on_intent_drift is my_handler
