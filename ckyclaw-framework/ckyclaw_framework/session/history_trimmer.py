"""HistoryTrimmer — 历史消息裁剪策略。"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ckyclaw_framework.model.message import Message


class HistoryTrimStrategy(StrEnum):
    """历史裁剪策略。"""

    SLIDING_WINDOW = "sliding_window"
    """保留最近 N 条消息。"""

    TOKEN_BUDGET = "token_budget"
    """从最新消息向前累加 Token，超出预算截断。"""

    PROGRESSIVE = "progressive"
    """分级递进裁剪：TOKEN_BUDGET → 压缩长工具结果 → 再裁剪，在同等 Token 预算下保留更多对话轮次。"""

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

    progressive_tool_result_limit: int = 500
    """PROGRESSIVE 策略：长工具结果压缩到的最大字符数。"""


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
        elif config.strategy == HistoryTrimStrategy.PROGRESSIVE:
            return HistoryTrimmer._trim_progressive(messages, config)
        elif config.strategy == HistoryTrimStrategy.SUMMARY_PREFIX:
            return HistoryTrimmer._trim_summary_prefix(messages, config)
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

    @staticmethod
    def _trim_progressive(messages: list[Message], config: HistoryTrimConfig) -> list[Message]:
        """PROGRESSIVE：分级递进裁剪。

        Phase 1: 用 TOKEN_BUDGET 策略裁剪。
        Phase 2: 如果 Phase 1 丢弃了过多消息（>50%非系统消息被裁），
                 先压缩长工具结果再重新 TOKEN_BUDGET 裁剪，在同等预算下保留更多轮次。
        """
        from ckyclaw_framework.model.message import Message as Msg
        from ckyclaw_framework.model.message import MessageRole

        # Phase 1: 标准 TOKEN_BUDGET
        phase1 = HistoryTrimmer._trim_token_budget(messages, config)

        # 计算非系统消息保留率
        non_system_total = sum(1 for m in messages if m.role != MessageRole.SYSTEM)
        non_system_kept = sum(1 for m in phase1 if m.role != MessageRole.SYSTEM)

        # 保留了一半以上，Phase 1 足够
        if non_system_total == 0 or non_system_kept >= non_system_total * 0.5:
            return phase1

        # Phase 2: 压缩长工具/助手消息，然后重新裁剪
        limit = config.progressive_tool_result_limit
        compressed: list[Message] = []
        for msg in messages:
            if msg.role == MessageRole.TOOL and msg.content and len(msg.content) > limit:
                truncated = msg.content[:limit] + "... [truncated]"
                compressed.append(Msg(
                    role=msg.role,
                    content=truncated,
                    tool_call_id=msg.tool_call_id,
                    agent_name=msg.agent_name,
                ))
            else:
                compressed.append(msg)

        return HistoryTrimmer._trim_token_budget(compressed, config)

    @staticmethod
    def _trim_summary_prefix(messages: list[Message], config: HistoryTrimConfig) -> list[Message]:
        """SUMMARY_PREFIX：被裁剪的消息浓缩为摘要前缀 + 保留最近消息。

        不依赖 LLM，使用提取式摘要：每条被裁消息取首行（最多 80 字符）。
        摘要作为 system 消息插在保留消息之前，提供对话历史概览。
        """
        from ckyclaw_framework.model.message import Message as Msg
        from ckyclaw_framework.model.message import MessageRole

        # 用 TOKEN_BUDGET 确定保留哪些消息
        kept = HistoryTrimmer._trim_token_budget(messages, config)
        kept_set = set(id(m) for m in kept)

        # 收集被裁掉的非 system 消息
        pruned = [m for m in messages if id(m) not in kept_set and m.role != MessageRole.SYSTEM]

        if not pruned:
            return kept

        # 提取式摘要：每条被裁消息取首行精简
        summary_lines: list[str] = []
        for m in pruned:
            if not m.content:
                continue
            first_line = m.content.split("\n")[0][:80]
            role_tag = m.role.value
            summary_lines.append(f"[{role_tag}] {first_line}")

        if not summary_lines:
            return kept

        # 限制摘要条目数，避免摘要本身太长
        max_summary_items = 20
        if len(summary_lines) > max_summary_items:
            summary_lines = summary_lines[-max_summary_items:]
            summary_lines.insert(0, f"... ({len(pruned) - max_summary_items} earlier messages omitted)")

        summary_text = (
            "[Conversation Summary - earlier messages condensed]\n"
            + "\n".join(summary_lines)
        )

        summary_msg = Msg(role=MessageRole.SYSTEM, content=summary_text)

        # 插入摘要：system 消息 + 摘要 + 保留的非 system 消息
        system_msgs = [m for m in kept if m.role == MessageRole.SYSTEM]
        non_system_kept = [m for m in kept if m.role != MessageRole.SYSTEM]

        return system_msgs + [summary_msg] + non_system_kept
