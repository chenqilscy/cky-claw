"""HistoryTrimmer 扩展测试 — 覆盖 SUMMARY_PREFIX / system 消息溢出 / keep_system=False 等路径。"""

from __future__ import annotations

import pytest

from ckyclaw_framework.model.message import Message, MessageRole, TokenUsage
from ckyclaw_framework.session.history_trimmer import (
    HistoryTrimConfig,
    HistoryTrimStrategy,
    HistoryTrimmer,
)


def _make_msg(role: MessageRole, content: str, tokens: int | None = None) -> Message:
    """创建测试 Message。"""
    return Message(
        role=role,
        content=content,
        token_usage=TokenUsage(tokens or 0, 0, tokens or 0) if tokens else None,
    )


class TestHistoryTrimmerSummaryPrefix:

    def test_summary_prefix_falls_back_to_token_budget(self) -> None:
        """SUMMARY_PREFIX 回退到 TOKEN_BUDGET 行为。"""
        msgs = [
            _make_msg(MessageRole.USER, "a" * 300),
            _make_msg(MessageRole.ASSISTANT, "b" * 300),
            _make_msg(MessageRole.USER, "c" * 300),
        ]
        config = HistoryTrimConfig(
            strategy=HistoryTrimStrategy.SUMMARY_PREFIX,
            max_history_tokens=200,
        )
        result = HistoryTrimmer.trim(msgs, config)
        # 应该和 TOKEN_BUDGET 行为一致：只保留最新的 ~200 tokens
        assert len(result) >= 1
        assert result[-1].content == "c" * 300


class TestSlidingWindowSystemOverflow:

    def test_system_messages_exceed_limit(self) -> None:
        """system 消息数 >= max_history_messages 时 budget <= 0。"""
        msgs = [
            _make_msg(MessageRole.SYSTEM, "sys1"),
            _make_msg(MessageRole.SYSTEM, "sys2"),
            _make_msg(MessageRole.SYSTEM, "sys3"),
            _make_msg(MessageRole.USER, "user1"),
            _make_msg(MessageRole.ASSISTANT, "asst1"),
        ]
        config = HistoryTrimConfig(
            strategy=HistoryTrimStrategy.SLIDING_WINDOW,
            max_history_messages=2,
            keep_system_messages=True,
        )
        result = HistoryTrimmer.trim(msgs, config)
        # budget = 2 - 3 = -1, 所以 budget <= 0
        # 返回 system_msgs[-2:] 即最后 2 条 system
        assert len(result) == 2
        assert all(m.role == MessageRole.SYSTEM for m in result)

    def test_sliding_window_no_keep_system(self) -> None:
        """keep_system_messages=False 的滑动窗口。"""
        msgs = [
            _make_msg(MessageRole.SYSTEM, "sys1"),
            _make_msg(MessageRole.USER, "u1"),
            _make_msg(MessageRole.ASSISTANT, "a1"),
            _make_msg(MessageRole.USER, "u2"),
            _make_msg(MessageRole.ASSISTANT, "a2"),
        ]
        config = HistoryTrimConfig(
            strategy=HistoryTrimStrategy.SLIDING_WINDOW,
            max_history_messages=2,
            keep_system_messages=False,
        )
        result = HistoryTrimmer.trim(msgs, config)
        assert len(result) == 2
        assert result[0].content == "u2"
        assert result[1].content == "a2"


class TestTokenBudgetSystemOverflow:

    def test_token_budget_system_tokens_exceed_budget(self) -> None:
        """system 消息的 token 数超过总预算时只返回 system 消息。"""
        msgs = [
            _make_msg(MessageRole.SYSTEM, "x" * 3000),  # ~1000 tokens
            _make_msg(MessageRole.USER, "hi"),
            _make_msg(MessageRole.ASSISTANT, "hello"),
        ]
        config = HistoryTrimConfig(
            strategy=HistoryTrimStrategy.TOKEN_BUDGET,
            max_history_tokens=100,  # 预算 100 < system ~1000
            keep_system_messages=True,
        )
        result = HistoryTrimmer.trim(msgs, config)
        # remaining_budget <= 0，只返回 system 消息
        assert len(result) == 1
        assert result[0].role == MessageRole.SYSTEM

    def test_token_budget_no_keep_system(self) -> None:
        """keep_system_messages=False 的 token budget。"""
        msgs = [
            _make_msg(MessageRole.SYSTEM, "sys"),
            _make_msg(MessageRole.USER, "a" * 300),
            _make_msg(MessageRole.ASSISTANT, "b" * 300),
            _make_msg(MessageRole.USER, "c" * 300),
        ]
        config = HistoryTrimConfig(
            strategy=HistoryTrimStrategy.TOKEN_BUDGET,
            max_history_tokens=200,
            keep_system_messages=False,
        )
        result = HistoryTrimmer.trim(msgs, config)
        # 不保留 system，从最新向前累加
        assert all(m.role != MessageRole.SYSTEM for m in result)
        assert result[-1].content == "c" * 300

    def test_token_budget_pre_trim_system_overflow(self) -> None:
        """消息数超限 + system 消息数 >= max 时 budget <= 0 分支。"""
        # 5 条 system + 5 条 user = 10 条总消息
        msgs = [
            _make_msg(MessageRole.SYSTEM, f"sys{i}") for i in range(5)
        ] + [
            _make_msg(MessageRole.USER, f"user{i}") for i in range(5)
        ]
        config = HistoryTrimConfig(
            strategy=HistoryTrimStrategy.TOKEN_BUDGET,
            max_history_tokens=10000,
            max_history_messages=3,  # 硬上限 3 条，但 system 有 5 条
            keep_system_messages=True,
        )
        result = HistoryTrimmer.trim(msgs, config)
        # budget = 3 - 5 = -2, 所以 budget <= 0
        # 返回 system_msgs[-3:] 即最后 3 条 system
        assert len(result) == 3
        assert all(m.role == MessageRole.SYSTEM for m in result)

    def test_token_budget_pre_trim_no_keep_system(self) -> None:
        """消息数超限 + keep_system_messages=False 的预裁剪。"""
        msgs = [
            _make_msg(MessageRole.SYSTEM, "sys"),
            _make_msg(MessageRole.USER, "u1"),
            _make_msg(MessageRole.ASSISTANT, "a1"),
            _make_msg(MessageRole.USER, "u2"),
            _make_msg(MessageRole.ASSISTANT, "a2"),
        ]
        config = HistoryTrimConfig(
            strategy=HistoryTrimStrategy.TOKEN_BUDGET,
            max_history_tokens=10000,
            max_history_messages=2,
            keep_system_messages=False,
        )
        result = HistoryTrimmer.trim(msgs, config)
        # 只保留最后 2 条（不考虑 system）
        assert len(result) == 2
        assert result[0].content == "u2"
        assert result[1].content == "a2"
