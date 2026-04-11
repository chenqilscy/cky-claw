"""Projector — 事件投射器抽象。

Projector 订阅 EventJournal 中的事件，产出聚合视图。
每个 Projector 关注特定事件类型，维护自己的状态。
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

from ckyclaw_framework.events.journal import EventEntry
from ckyclaw_framework.events.types import EventType

logger = logging.getLogger(__name__)


class Projector(ABC):
    """事件投射器接口。"""

    @property
    def name(self) -> str:
        """投射器名称。"""
        return type(self).__name__

    @abstractmethod
    async def on_event(self, entry: EventEntry) -> None:
        """处理一条事件。"""
        ...

    @abstractmethod
    def get_state(self) -> dict[str, Any]:
        """获取当前聚合状态。"""
        ...

    def reset(self) -> None:
        """重置状态。"""


@dataclass
class _CostState:
    """CostProjector 内部状态。"""

    total_prompt_tokens: int = 0
    total_completion_tokens: int = 0
    total_calls: int = 0
    by_model: dict[str, dict[str, int]] = field(default_factory=lambda: defaultdict(lambda: {"prompt": 0, "completion": 0, "calls": 0}))


class CostProjector(Projector):
    """Token 成本投射器。

    监听 LLM_CALL_END 事件，聚合 Token 消耗。
    """

    def __init__(self) -> None:
        self._state = _CostState()

    async def on_event(self, entry: EventEntry) -> None:
        """处理 LLM 调用结束事件。"""
        if entry.event_type != EventType.LLM_CALL_END:
            return

        usage = entry.payload.get("token_usage")
        if not usage:
            return

        prompt = usage.get("prompt_tokens", 0)
        completion = usage.get("completion_tokens", 0)
        model = entry.payload.get("model", "unknown")

        self._state.total_prompt_tokens += prompt
        self._state.total_completion_tokens += completion
        self._state.total_calls += 1

        model_stats = self._state.by_model[model]
        model_stats["prompt"] += prompt
        model_stats["completion"] += completion
        model_stats["calls"] += 1

    def get_state(self) -> dict[str, Any]:
        """获取 Token 消耗统计。"""
        return {
            "total_prompt_tokens": self._state.total_prompt_tokens,
            "total_completion_tokens": self._state.total_completion_tokens,
            "total_tokens": self._state.total_prompt_tokens + self._state.total_completion_tokens,
            "total_calls": self._state.total_calls,
            "by_model": dict(self._state.by_model),
        }

    def reset(self) -> None:
        """重置状态。"""
        self._state = _CostState()


class AuditProjector(Projector):
    """审计投射器。

    记录所有事件的摘要，用于合规审计。
    """

    def __init__(self, max_entries: int = 1000) -> None:
        self._max_entries = max_entries
        self._entries: list[dict[str, Any]] = []

    async def on_event(self, entry: EventEntry) -> None:
        """记录审计条目。"""
        audit_record = {
            "event_id": entry.event_id,
            "event_type": entry.event_type.value,
            "timestamp": entry.timestamp.isoformat(),
            "run_id": entry.run_id,
            "agent_name": entry.agent_name,
        }

        # 敏感事件附加更多上下文
        if entry.event_type in (EventType.ERROR, EventType.GUARDRAIL_TRIPWIRE):
            audit_record["detail"] = entry.payload.get("error") or entry.payload.get("message", "")

        self._entries.append(audit_record)

        # 限制条目数
        if len(self._entries) > self._max_entries:
            self._entries = self._entries[-self._max_entries:]

    def get_state(self) -> dict[str, Any]:
        """获取审计日志。"""
        return {
            "total_events": len(self._entries),
            "entries": list(self._entries),
        }

    def reset(self) -> None:
        """重置状态。"""
        self._entries.clear()


class MetricsProjector(Projector):
    """指标投射器。

    聚合各类事件的计数和耗时统计。
    """

    def __init__(self) -> None:
        self._event_counts: dict[str, int] = defaultdict(int)
        self._tool_durations: dict[str, list[int]] = defaultdict(list)
        self._llm_durations: list[int] = []
        self._error_count: int = 0
        self._guardrail_tripwires: int = 0

    async def on_event(self, entry: EventEntry) -> None:
        """聚合事件指标。"""
        self._event_counts[entry.event_type.value] += 1

        if entry.event_type == EventType.TOOL_CALL_END:
            duration = entry.payload.get("duration_ms")
            tool_name = entry.payload.get("span_name", "unknown")
            if duration is not None:
                self._tool_durations[tool_name].append(duration)

        elif entry.event_type == EventType.LLM_CALL_END:
            duration = entry.payload.get("duration_ms")
            if duration is not None:
                self._llm_durations.append(duration)

        elif entry.event_type == EventType.ERROR:
            self._error_count += 1

        elif entry.event_type == EventType.GUARDRAIL_TRIPWIRE:
            self._guardrail_tripwires += 1

    def get_state(self) -> dict[str, Any]:
        """获取聚合指标。"""
        tool_stats: dict[str, dict[str, Any]] = {}
        for name, durations in self._tool_durations.items():
            if durations:
                tool_stats[name] = {
                    "count": len(durations),
                    "avg_ms": sum(durations) / len(durations),
                    "max_ms": max(durations),
                    "min_ms": min(durations),
                }
            # 限制工具统计条目
            if len(tool_stats) >= 200:
                break

        llm_avg = sum(self._llm_durations) / len(self._llm_durations) if self._llm_durations else 0

        return {
            "event_counts": dict(self._event_counts),
            "tool_stats": tool_stats,
            "llm_call_count": len(self._llm_durations),
            "llm_avg_duration_ms": llm_avg,
            "error_count": self._error_count,
            "guardrail_tripwires": self._guardrail_tripwires,
        }

    def reset(self) -> None:
        """重置状态。"""
        self._event_counts.clear()
        self._tool_durations.clear()
        self._llm_durations.clear()
        self._error_count = 0
        self._guardrail_tripwires = 0
