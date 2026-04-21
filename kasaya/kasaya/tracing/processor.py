"""TraceProcessor — 追踪处理器接口。"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from kasaya.tracing.span import Span
    from kasaya.tracing.trace import Trace


class TraceProcessor(ABC):
    """追踪处理器接口。应用层实现此接口将数据导出到 APM 后端。"""

    @abstractmethod
    async def on_trace_start(self, trace: Trace) -> None: ...

    @abstractmethod
    async def on_span_start(self, span: Span) -> None: ...

    @abstractmethod
    async def on_span_end(self, span: Span) -> None: ...

    @abstractmethod
    async def on_trace_end(self, trace: Trace) -> None: ...
