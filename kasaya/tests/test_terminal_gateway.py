"""E4 Terminal Gateway 测试。"""

from __future__ import annotations

import io

import pytest

from kasaya.terminal.gateway import (
    OutputType,
    PlainTerminalBackend,
    StructuredOutput,
    TerminalBackend,
)

# ---------------------------------------------------------------------------
# OutputType 枚举
# ---------------------------------------------------------------------------


class TestOutputType:
    """OutputType 枚举测试。"""

    def test_values(self) -> None:
        """枚举值正确。"""
        assert OutputType.TEXT.value == "text"
        assert OutputType.TOOL_CALL.value == "tool_call"
        assert OutputType.ERROR.value == "error"
        assert OutputType.SYSTEM.value == "system"
        assert OutputType.HANDOFF.value == "handoff"

    def test_is_str_enum(self) -> None:
        """可作为字符串比较。"""
        assert OutputType.TEXT == "text"


# ---------------------------------------------------------------------------
# StructuredOutput
# ---------------------------------------------------------------------------


class TestStructuredOutput:
    """StructuredOutput 测试。"""

    def test_defaults(self) -> None:
        """默认值。"""
        o = StructuredOutput(output_type=OutputType.TEXT, content="hello")
        assert o.metadata == {}

    def test_with_metadata(self) -> None:
        """附带 metadata。"""
        o = StructuredOutput(
            output_type=OutputType.TOOL_CALL,
            content="search",
            metadata={"args": {"query": "test"}},
        )
        assert o.metadata["args"]["query"] == "test"


# ---------------------------------------------------------------------------
# TerminalBackend ABC
# ---------------------------------------------------------------------------


class TestTerminalBackendABC:
    """ABC 不可直接实例化。"""

    def test_cannot_instantiate(self) -> None:
        """直接实例化抛 TypeError。"""
        with pytest.raises(TypeError):
            TerminalBackend()  # type: ignore[abstract]


# ---------------------------------------------------------------------------
# PlainTerminalBackend — write
# ---------------------------------------------------------------------------


class TestPlainWrite:
    """PlainTerminalBackend 写入测试。"""

    @pytest.mark.asyncio
    async def test_write_text(self) -> None:
        """写入纯文本。"""
        out = io.StringIO()
        backend = PlainTerminalBackend(output_stream=out)
        await backend.write("hello\n")
        assert out.getvalue() == "hello\n"

    @pytest.mark.asyncio
    async def test_write_multiple(self) -> None:
        """多次写入拼接。"""
        out = io.StringIO()
        backend = PlainTerminalBackend(output_stream=out)
        await backend.write("a")
        await backend.write("b")
        assert out.getvalue() == "ab"


# ---------------------------------------------------------------------------
# PlainTerminalBackend — write_structured
# ---------------------------------------------------------------------------


class TestPlainWriteStructured:
    """结构化输出测试。"""

    @pytest.mark.asyncio
    async def test_text_output(self) -> None:
        """TEXT 类型无前缀。"""
        out = io.StringIO()
        backend = PlainTerminalBackend(output_stream=out)
        await backend.write_structured(
            StructuredOutput(output_type=OutputType.TEXT, content="hello"),
        )
        assert out.getvalue() == "hello\n"

    @pytest.mark.asyncio
    async def test_error_output(self) -> None:
        """ERROR 类型有 [Error] 前缀。"""
        out = io.StringIO()
        backend = PlainTerminalBackend(output_stream=out)
        await backend.write_structured(
            StructuredOutput(output_type=OutputType.ERROR, content="bad request"),
        )
        assert out.getvalue() == "[Error] bad request\n"

    @pytest.mark.asyncio
    async def test_tool_call_with_args(self) -> None:
        """TOOL_CALL 附带参数信息。"""
        out = io.StringIO()
        backend = PlainTerminalBackend(output_stream=out)
        await backend.write_structured(
            StructuredOutput(
                output_type=OutputType.TOOL_CALL,
                content="search",
                metadata={"args": {"q": "test"}},
            ),
        )
        result = out.getvalue()
        assert "[Tool] search" in result
        assert "args:" in result

    @pytest.mark.asyncio
    async def test_system_output(self) -> None:
        """SYSTEM 类型有前缀。"""
        out = io.StringIO()
        backend = PlainTerminalBackend(output_stream=out)
        await backend.write_structured(
            StructuredOutput(output_type=OutputType.SYSTEM, content="initializing..."),
        )
        assert "[System]" in out.getvalue()

    @pytest.mark.asyncio
    async def test_handoff_output(self) -> None:
        """HANDOFF 类型。"""
        out = io.StringIO()
        backend = PlainTerminalBackend(output_stream=out)
        await backend.write_structured(
            StructuredOutput(output_type=OutputType.HANDOFF, content="transfer to agent-b"),
        )
        assert "[Handoff]" in out.getvalue()

    @pytest.mark.asyncio
    async def test_tool_result_output(self) -> None:
        """TOOL_RESULT 类型。"""
        out = io.StringIO()
        backend = PlainTerminalBackend(output_stream=out)
        await backend.write_structured(
            StructuredOutput(output_type=OutputType.TOOL_RESULT, content="found 5 items"),
        )
        assert "[Result]" in out.getvalue()


# ---------------------------------------------------------------------------
# PlainTerminalBackend — read
# ---------------------------------------------------------------------------


class TestPlainRead:
    """PlainTerminalBackend 读取测试。"""

    @pytest.mark.asyncio
    async def test_read_basic(self) -> None:
        """读取一行输入。"""
        inp = io.StringIO("hello world\n")
        out = io.StringIO()
        backend = PlainTerminalBackend(input_stream=inp, output_stream=out)
        result = await backend.read()
        assert result == "hello world"

    @pytest.mark.asyncio
    async def test_read_with_prompt(self) -> None:
        """带提示符的读取。"""
        inp = io.StringIO("user input\n")
        out = io.StringIO()
        backend = PlainTerminalBackend(input_stream=inp, output_stream=out)
        result = await backend.read("You> ")
        assert result == "user input"
        assert "You> " in out.getvalue()

    @pytest.mark.asyncio
    async def test_read_strips_newline(self) -> None:
        """读取结果去掉尾部换行。"""
        inp = io.StringIO("data\n")
        backend = PlainTerminalBackend(input_stream=inp, output_stream=io.StringIO())
        result = await backend.read()
        assert result == "data"

    @pytest.mark.asyncio
    async def test_read_empty(self) -> None:
        """空输入。"""
        inp = io.StringIO("\n")
        backend = PlainTerminalBackend(input_stream=inp, output_stream=io.StringIO())
        result = await backend.read()
        assert result == ""


# ---------------------------------------------------------------------------
# PlainTerminalBackend — 上下文管理器
# ---------------------------------------------------------------------------


class TestContextManager:
    """上下文管理器测试。"""

    @pytest.mark.asyncio
    async def test_async_context_manager(self) -> None:
        """async with 正常工作。"""
        out = io.StringIO()
        async with PlainTerminalBackend(output_stream=out) as backend:
            await backend.write("inside context\n")
        assert "inside context" in out.getvalue()

    @pytest.mark.asyncio
    async def test_start_stop_called(self) -> None:
        """start/stop 被调用。"""
        calls: list[str] = []

        class TrackingBackend(PlainTerminalBackend):
            async def start(self) -> None:
                calls.append("start")

            async def stop(self) -> None:
                calls.append("stop")

        async with TrackingBackend(output_stream=io.StringIO()):
            pass
        assert calls == ["start", "stop"]


# ---------------------------------------------------------------------------
# 边界条件
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """边界条件测试。"""

    @pytest.mark.asyncio
    async def test_write_empty_string(self) -> None:
        """写入空字符串。"""
        out = io.StringIO()
        backend = PlainTerminalBackend(output_stream=out)
        await backend.write("")
        assert out.getvalue() == ""

    @pytest.mark.asyncio
    async def test_write_unicode(self) -> None:
        """写入中文/Unicode。"""
        out = io.StringIO()
        backend = PlainTerminalBackend(output_stream=out)
        await backend.write("你好世界 🌍\n")
        assert "你好世界 🌍" in out.getvalue()

    @pytest.mark.asyncio
    async def test_multiple_reads(self) -> None:
        """连续多次读取。"""
        inp = io.StringIO("line1\nline2\nline3\n")
        backend = PlainTerminalBackend(input_stream=inp, output_stream=io.StringIO())
        assert await backend.read() == "line1"
        assert await backend.read() == "line2"
        assert await backend.read() == "line3"

    @pytest.mark.asyncio
    async def test_default_streams(self) -> None:
        """默认使用 sys.stdin/stdout（不抛异常）。"""
        backend = PlainTerminalBackend()
        assert backend._input is not None
        assert backend._output is not None
