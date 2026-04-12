"""Terminal Gateway — 终端后端统一抽象。

提供 Agent CLI 运行场景下的终端 I/O 抽象层，
支持 Plain / Rich / IPython 等多种终端后端。

设计模式参照 SessionBackend：ABC 定义接口，子类实现具体终端。
"""

from __future__ import annotations

import asyncio
import logging
import sys
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, TextIO

logger = logging.getLogger(__name__)


class OutputType(str, Enum):
    """输出内容类型。"""

    TEXT = "text"
    """纯文本。"""

    TOOL_CALL = "tool_call"
    """工具调用信息。"""

    TOOL_RESULT = "tool_result"
    """工具执行结果。"""

    ERROR = "error"
    """错误信息。"""

    SYSTEM = "system"
    """系统消息。"""

    HANDOFF = "handoff"
    """Agent 移交通知。"""


@dataclass
class StructuredOutput:
    """结构化输出消息。

    Attributes:
        output_type: 输出类型。
        content: 文本内容。
        metadata: 附加元数据（如工具名称、参数等）。
    """

    output_type: OutputType
    content: str
    metadata: dict[str, Any] = field(default_factory=dict)


class TerminalBackend(ABC):
    """终端后端抽象基类。

    定义 Agent CLI 场景下终端 I/O 的统一接口。
    子类需实现具体的输入读取和输出渲染逻辑。
    """

    @abstractmethod
    async def write(self, text: str) -> None:
        """写入纯文本到终端。

        Args:
            text: 要输出的文本。
        """

    @abstractmethod
    async def write_structured(self, output: StructuredOutput) -> None:
        """写入结构化输出到终端。

        不同终端后端可对结构化内容做不同渲染：
        - PlainTerminalBackend: 纯文本展示
        - （未来）RichTerminalBackend: 使用 Rich 库做格式化

        Args:
            output: 结构化输出消息。
        """

    @abstractmethod
    async def read(self, prompt: str = "") -> str:
        """从终端读取用户输入。

        Args:
            prompt: 输入提示符。

        Returns:
            用户输入的文本。
        """

    async def start(self) -> None:
        """终端后端启动时的初始化（可选覆盖）。"""

    async def stop(self) -> None:
        """终端后端关闭时的清理（可选覆盖）。"""

    async def __aenter__(self) -> TerminalBackend:
        """异步上下文管理器入口。"""
        await self.start()
        return self

    async def __aexit__(self, *args: Any) -> None:
        """异步上下文管理器退出。"""
        await self.stop()


class PlainTerminalBackend(TerminalBackend):
    """纯文本终端后端。

    使用标准 stdin/stdout 进行 I/O。
    结构化输出降级为纯文本格式。

    Example:
        async with PlainTerminalBackend() as terminal:
            await terminal.write("Hello!\\n")
            user_input = await terminal.read("You> ")
    """

    def __init__(
        self,
        *,
        input_stream: TextIO | None = None,
        output_stream: TextIO | None = None,
    ) -> None:
        """初始化。

        Args:
            input_stream: 输入流，默认 sys.stdin。
            output_stream: 输出流，默认 sys.stdout。
        """
        self._input = input_stream or sys.stdin
        self._output = output_stream or sys.stdout

    async def write(self, text: str) -> None:
        """写入纯文本。"""
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self._write_sync, text)

    def _write_sync(self, text: str) -> None:
        """同步写入。"""
        self._output.write(text)
        self._output.flush()

    async def write_structured(self, output: StructuredOutput) -> None:
        """将结构化输出降级为纯文本。"""
        formatted = self._format_output(output)
        await self.write(formatted)

    def _format_output(self, output: StructuredOutput) -> str:
        """格式化结构化输出为纯文本。"""
        prefix_map = {
            OutputType.TEXT: "",
            OutputType.TOOL_CALL: "[Tool] ",
            OutputType.TOOL_RESULT: "[Result] ",
            OutputType.ERROR: "[Error] ",
            OutputType.SYSTEM: "[System] ",
            OutputType.HANDOFF: "[Handoff] ",
        }
        prefix = prefix_map.get(output.output_type, "")

        lines = [f"{prefix}{output.content}"]

        # 工具调用时附加参数信息
        if output.output_type == OutputType.TOOL_CALL and "args" in output.metadata:
            lines.append(f"  args: {output.metadata['args']}")

        return "\n".join(lines) + "\n"

    async def read(self, prompt: str = "") -> str:
        """从 stdin 读取输入（在 executor 中运行以避免阻塞）。"""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._read_sync, prompt)

    def _read_sync(self, prompt: str) -> str:
        """同步读取。"""
        if prompt:
            self._output.write(prompt)
            self._output.flush()
        return self._input.readline().rstrip("\n")
