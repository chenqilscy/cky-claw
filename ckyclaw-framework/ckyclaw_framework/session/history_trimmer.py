"""HistoryTrimmer — 历史消息裁剪策略。"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ckyclaw_framework.model.message import Message, MessageRole


class HistoryTrimStrategy(str, Enum):
    """历史裁剪策略。"""

    SLIDING_WINDOW = "sliding_window"
    """保留最近 N 条消息。"""

    TOKEN_BUDGET = "token_budget"
    """从最新消息向前累加 Token，超出预算截断。"""

    SUMMARY_PREFIX = "summary_prefix"
    """摘要 + 最近消息（需要 LLM 调用，暂未实现）。"""


@dataclass
class HistoryTrimConfig:
    """历史裁剪配置。"""

    strategy: HistoryTrimStrategy = HistoryTrimStrategy.TOKEN_BUDGET
    """裁剪策略"""

    max_history_tokens: int = 8000
    """Token 预算（TOKEN_BUDGET 策略使用）"""

    max_history_messages: int = 100
    """消息条数上限（SLIDING_WINDOW 策略使用；TOKEN_BUDGET 时作为硬上限）"""

    keep_system_messages: bool = True
    """裁剪时是否保留 system 消息"""


def _estimate_tokens(msg: Message) -> int:
    """估算单条消息的 Token 数。

    有 token_usage 时取 total_tokens；否则按字符数 / 3 估算（中英混合保守策略）。
    """
    if msg.token_usage is not None and msg.token_usage.total_tokens > 0:
        return msg.token_usage.total_tokens
    content_len = len(msg.content) if msg.content else 0
    return max(content_len // 3, 1)


class HistoryTrimmer:
    """历史消息裁剪器。无状态工具类。"""

    @staticmethod
    def trim(messages: list[Message], config: HistoryTrimConfig) -> list[Message]:
        """按策略裁剪消息列表，返回裁剪后的新列表。

        不修改原列表。保留消息的相对顺序。
        """
        if not messages:
            return []

        if config.strategy == HistoryTrimStrategy.SLIDING_WINDOW:
            return HistoryTrimmer._trim_sliding_window(messages, config)
        elif config.strategy == HistoryTrimStrategy.TOKEN_BUDGET:
            return HistoryTrimmer._trim_token_budget(messages, config)
        elif config.strategy == HistoryTrimStrategy.SUMMARY_PREFIX:
            # P2: 暂时回退到 TOKEN_BUDGET
            return HistoryTrimmer._trim_token_budget(messages, config)
        else:
            return list(messages)

    @staticmethod
    def _trim_sliding_window(messages: list[Message], config: HistoryTrimConfig) -> list[Message]:
        """SLIDING_WINDOW：保留最后 max_history_messages 条。"""
        from ckyclaw_framework.model.message import MessageRole

        if len(messages) <= config.max_history_messages:
            return list(messages)

        if config.keep_system_messages:
            system_msgs = [m for m in messages if m.role == MessageRole.SYSTEM]
            non_system = [m for m in messages if m.role != MessageRole.SYSTEM]
            # 保留所有 system + 最近的 non-system
            budget = config.max_history_messages - len(system_msgs)
            if budget <= 0:
                return list(system_msgs[-config.max_history_messages:])
            trimmed_non_system = non_system[-budget:]
            return system_msgs + trimmed_non_system
        else:
            return list(messages[-config.max_history_messages:])

    @staticmethod
    def _trim_token_budget(messages: list[Message], config: HistoryTrimConfig) -> list[Message]:
        """TOKEN_BUDGET：从最新消息向前累加，超出预算截断。"""
        from ckyclaw_framework.model.message import MessageRole

        # 先按消息数硬上限裁剪
        if len(messages) > config.max_history_messages:
            if config.keep_system_messages:
                system_msgs = [m for m in messages if m.role == MessageRole.SYSTEM]
                non_system = [m for m in messages if m.role != MessageRole.SYSTEM]
                budget = config.max_history_messages - len(system_msgs)
                if budget <= 0:
                    messages = list(system_msgs[-config.max_history_messages:])
                else:
                    messages = system_msgs + non_system[-budget:]
            else:
                messages = list(messages[-config.max_history_messages:])

        # 分离 system 消息
        if config.keep_system_messages:
            system_msgs = [m for m in messages if m.role == MessageRole.SYSTEM]
            non_system = [m for m in messages if m.role != MessageRole.SYSTEM]
            system_tokens = sum(_estimate_tokens(m) for m in system_msgs)
            remaining_budget = config.max_history_tokens - system_tokens
            if remaining_budget <= 0:
                return list(system_msgs)
        else:
            system_msgs = []
            non_system = list(messages)
            remaining_budget = config.max_history_tokens

        # 从尾部（最新）向前累加
        selected: list[Message] = []
        accumulated = 0
        for msg in reversed(non_system):
            tokens = _estimate_tokens(msg)
            if accumulated + tokens > remaining_budget:
                break
            selected.append(msg)
            accumulated += tokens

        selected.reverse()
        return system_msgs + selected
