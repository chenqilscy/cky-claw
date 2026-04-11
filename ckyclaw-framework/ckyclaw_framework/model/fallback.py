"""FallbackChainProvider — Provider 级降级链。

包装多个 ModelProvider，按优先级 + CircuitBreaker 状态选择可用 Provider。
主 Provider 失败后自动切换到备用，直到链路耗尽或成功。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, AsyncIterator

from ckyclaw_framework.model.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitBreakerOpenError,
    CircuitState,
)
from ckyclaw_framework.model.provider import ModelChunk, ModelProvider, ModelResponse

if TYPE_CHECKING:
    from ckyclaw_framework.model.message import Message
    from ckyclaw_framework.model.settings import ModelSettings

logger = logging.getLogger(__name__)


@dataclass
class FallbackEntry:
    """降级链中的一个 Provider 条目。"""

    provider: ModelProvider
    """模型提供商实例"""

    model: str | None = None
    """覆盖模型名称。None 时使用调用者指定的 model。"""

    circuit_breaker: CircuitBreaker | None = None
    """可选的独立熔断器。None 时自动创建默认配置的熔断器。"""

    priority: int = 0
    """优先级（数字越小优先级越高）。"""


@dataclass
class FallbackChainConfig:
    """降级链配置。"""

    auto_circuit_breaker: bool = True
    """是否为未配置 CircuitBreaker 的 Entry 自动创建。"""

    default_cb_config: CircuitBreakerConfig = field(default_factory=CircuitBreakerConfig)
    """自动创建 CircuitBreaker 时使用的配置。"""


class FallbackChainProvider(ModelProvider):
    """降级链 Provider，包装多个后备 Provider。

    用法::

        chain = FallbackChainProvider([
            FallbackEntry(provider=openai_provider, model="gpt-4o"),
            FallbackEntry(provider=azure_provider, model="gpt-4o", priority=1),
            FallbackEntry(provider=deepseek_provider, model="deepseek-chat", priority=2),
        ])
        # 自动按优先级尝试，失败自动切换
        response = await chain.chat(model="gpt-4o", messages=[...])
    """

    def __init__(
        self,
        entries: list[FallbackEntry],
        config: FallbackChainConfig | None = None,
    ) -> None:
        if not entries:
            raise ValueError("FallbackChainProvider requires at least one FallbackEntry")
        self._config = config or FallbackChainConfig()
        self._entries = sorted(entries, key=lambda e: e.priority)
        self._last_used_entry: FallbackEntry | None = None

        # 为未配置 CircuitBreaker 的条目自动创建
        if self._config.auto_circuit_breaker:
            for i, entry in enumerate(self._entries):
                if entry.circuit_breaker is None:
                    name = f"fallback-{i}-{type(entry.provider).__name__}"
                    entry.circuit_breaker = CircuitBreaker(
                        name=name,
                        config=self._config.default_cb_config,
                    )

    @property
    def entries(self) -> list[FallbackEntry]:
        """降级链条目（只读）。"""
        return list(self._entries)

    @property
    def last_used_entry(self) -> FallbackEntry | None:
        """上次成功使用的条目。"""
        return self._last_used_entry

    async def chat(
        self,
        model: str,
        messages: list[Message],
        *,
        settings: ModelSettings | None = None,
        tools: list[dict[str, Any]] | None = None,
        stream: bool = False,
        response_format: dict[str, Any] | None = None,
    ) -> ModelResponse | AsyncIterator[ModelChunk]:
        """按优先级尝试降级链中的 Provider。

        遍历所有 Entry：
        1. 检查 CircuitBreaker 状态，OPEN 则跳过
        2. 调用 provider.chat()，成功则返回
        3. 失败则记录到 CircuitBreaker，继续下一个 Entry

        Raises:
            RuntimeError: 所有 Provider 均不可用
        """
        errors: list[tuple[str, Exception]] = []

        for entry in self._entries:
            # 使用 entry 级别的 model 覆盖
            effective_model = entry.model or model
            cb = entry.circuit_breaker
            provider_name = f"{type(entry.provider).__name__}({effective_model})"

            # 检查 CircuitBreaker
            if cb is not None and cb.state == CircuitState.OPEN:
                logger.debug("Skipping '%s': circuit breaker OPEN", provider_name)
                continue

            try:
                if cb is not None:
                    result = await cb.call(
                        entry.provider.chat,
                        effective_model,
                        messages,
                        settings=settings,
                        tools=tools,
                        stream=stream,
                        response_format=response_format,
                    )
                else:
                    result = await entry.provider.chat(
                        effective_model,
                        messages,
                        settings=settings,
                        tools=tools,
                        stream=stream,
                        response_format=response_format,
                    )

                self._last_used_entry = entry
                logger.debug("FallbackChain: '%s' succeeded", provider_name)
                return result  # type: ignore[return-value]

            except CircuitBreakerOpenError:
                logger.debug("Skipping '%s': circuit breaker OPEN (during call)", provider_name)
                continue
            except Exception as e:
                logger.warning(
                    "FallbackChain: '%s' failed: %s, trying next", provider_name, e,
                )
                errors.append((provider_name, e))
                continue

        # 所有 Provider 均失败
        error_details = "; ".join(f"{name}: {err}" for name, err in errors)
        raise RuntimeError(
            f"All providers in FallbackChain exhausted. Errors: [{error_details}]"
        )

    def get_health_status(self) -> list[dict[str, Any]]:
        """获取所有条目的健康状态（用于 APM Dashboard）。"""
        result = []
        for i, entry in enumerate(self._entries):
            provider_name = type(entry.provider).__name__
            status: dict[str, Any] = {
                "index": i,
                "provider": provider_name,
                "model": entry.model,
                "priority": entry.priority,
                "is_last_used": entry is self._last_used_entry,
            }
            if entry.circuit_breaker:
                status["circuit_breaker"] = entry.circuit_breaker.to_dict()
            result.append(status)
        return result
