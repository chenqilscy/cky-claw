"""Function Tool 单元测试。"""

from __future__ import annotations

import asyncio
import json

import pytest

from ckyclaw_framework.tools.function_tool import FunctionTool, function_tool

# ── @function_tool 装饰器测试 ───────────────────────────────────


class TestFunctionToolDecorator:
    def test_basic_decorator(self) -> None:
        @function_tool()
        def greet(name: str) -> str:
            """Say hello."""
            return f"Hello, {name}!"

        assert isinstance(greet, FunctionTool)
        assert greet.name == "greet"
        assert greet.description == "Say hello."
        assert greet.fn is not None

    def test_custom_name_and_description(self) -> None:
        @function_tool(name="my_tool", description="Custom desc")
        def foo(x: int) -> int:
            return x * 2

        assert foo.name == "my_tool"
        assert foo.description == "Custom desc"

    def test_schema_generation_basic_types(self) -> None:
        @function_tool()
        def calc(a: int, b: float, label: str) -> str:
            """Calculate."""
            return ""

        schema = calc.parameters_schema
        assert schema["type"] == "object"
        assert schema["properties"]["a"]["type"] == "integer"
        assert schema["properties"]["b"]["type"] == "number"
        assert schema["properties"]["label"]["type"] == "string"
        assert set(schema["required"]) == {"a", "b", "label"}

    def test_schema_generation_with_defaults(self) -> None:
        @function_tool()
        def search(query: str, limit: int = 10) -> str:
            """Search stuff."""
            return ""

        schema = search.parameters_schema
        assert "query" in schema["required"]
        assert "limit" not in schema.get("required", [])
        assert schema["properties"]["limit"]["default"] == 10

    def test_schema_generation_list_type(self) -> None:
        @function_tool()
        def process(items: list[str]) -> str:
            """Process items."""
            return ""

        schema = process.parameters_schema
        assert schema["properties"]["items"]["type"] == "array"
        assert schema["properties"]["items"]["items"]["type"] == "string"

    def test_openai_schema_output(self) -> None:
        @function_tool()
        def do_thing(x: int) -> str:
            """Do a thing."""
            return ""

        openai = do_thing.to_openai_schema()
        assert openai["type"] == "function"
        assert openai["function"]["name"] == "do_thing"
        assert openai["function"]["description"] == "Do a thing."
        assert "x" in openai["function"]["parameters"]["properties"]


# ── FunctionTool.execute 同步函数测试 ──────────────────────────


class TestFunctionToolExecuteSync:
    @pytest.mark.asyncio
    async def test_execute_sync_function(self) -> None:
        @function_tool()
        def add(a: int, b: int) -> int:
            """Add two numbers."""
            return a + b

        result = await add.execute({"a": 3, "b": 5})
        assert result == "8"

    @pytest.mark.asyncio
    async def test_execute_returns_string(self) -> None:
        @function_tool()
        def echo(msg: str) -> str:
            """Echo message."""
            return msg

        result = await echo.execute({"msg": "hello"})
        assert result == "hello"

    @pytest.mark.asyncio
    async def test_execute_returns_dict(self) -> None:
        @function_tool()
        def info(name: str) -> dict:
            """Get info."""
            return {"name": name, "status": "ok"}

        result = await info.execute({"name": "test"})
        parsed = json.loads(result)
        assert parsed == {"name": "test", "status": "ok"}


# ── FunctionTool.execute 异步函数测试 ──────────────────────────


class TestFunctionToolExecuteAsync:
    @pytest.mark.asyncio
    async def test_execute_async_function(self) -> None:
        @function_tool()
        async def fetch_data(url: str) -> str:
            """Fetch data from URL."""
            return f"data from {url}"

        result = await fetch_data.execute({"url": "https://example.com"})
        assert result == "data from https://example.com"


# ── 超时测试 ───────────────────────────────────────────────────


class TestFunctionToolTimeout:
    @pytest.mark.asyncio
    async def test_async_timeout(self) -> None:
        @function_tool(timeout=0.1)
        async def slow_task(x: int) -> str:
            """Slow task."""
            await asyncio.sleep(10)
            return "done"

        result = await slow_task.execute({"x": 1})
        assert "timed out" in result

    @pytest.mark.asyncio
    async def test_sync_timeout(self) -> None:
        import time

        @function_tool(timeout=0.1)
        def slow_sync(x: int) -> str:
            """Slow sync."""
            time.sleep(10)
            return "done"

        result = await slow_sync.execute({"x": 1})
        # 注意：同步函数在 executor 中执行，线程不能被真正 cancel
        # 但 wait_for 会返回 TimeoutError
        assert "timed out" in result


# ── 错误处理测试 ───────────────────────────────────────────────


class TestFunctionToolError:
    @pytest.mark.asyncio
    async def test_execute_exception(self) -> None:
        @function_tool()
        def boom(x: int) -> str:
            """Goes boom."""
            raise ValueError("kaboom!")

        result = await boom.execute({"x": 1})
        assert "failed" in result.lower()
        assert "kaboom" in result

    @pytest.mark.asyncio
    async def test_execute_no_fn(self) -> None:
        tool = FunctionTool(name="empty", description="No impl")
        result = await tool.execute({"x": 1})
        assert "no implementation" in result.lower()

    @pytest.mark.asyncio
    async def test_extra_arguments_ignored(self) -> None:
        @function_tool()
        def simple(a: int) -> int:
            """Simple."""
            return a

        # 传入额外参数不应报错
        result = await simple.execute({"a": 5, "b": 99})
        assert result == "5"
