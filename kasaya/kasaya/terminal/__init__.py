"""Terminal — 终端后端统一抽象。"""

from __future__ import annotations

from kasaya.terminal.gateway import (
    OutputType,
    PlainTerminalBackend,
    StructuredOutput,
    TerminalBackend,
)

__all__ = [
    "OutputType",
    "PlainTerminalBackend",
    "StructuredOutput",
    "TerminalBackend",
]
