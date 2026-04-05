"""FunctionTool 扩展测试 — 覆盖 dict 类型 schema / UnionType / var_keyword / condition 等路径。"""

from __future__ import annotations

import asyncio
import json
from typing import Any
from unittest.mock import MagicMock

import pytest

from ckyclaw_framework.tools.function_tool import (
    FunctionTool,
    _generate_parameters_schema,
    _python_type_to_json_schema,
    function_tool,
)


# ═══════════════════════════════════════════════════════════════════
# _python_type_to_json_schema 边界类型测试
# ═══════════════════════════════════════════════════════════════════


class TestPythonTypeToJsonSchema:

    def test_dict_type(self) -> None:
        """dict[str, int] → object + additionalProperties。"""
        schema = _python_type_to_json_schema(dict[str, int])
        assert schema["type"] == "object"
        assert schema["additionalProperties"]["type"] == "integer"

    def test_dict_no_args(self) -> None:
        """裸 dict → object。"""
        schema = _python_type_to_json_schema(dict)
        assert schema["type"] == "object"

    def test_list_no_args(self) -> None:
        """裸 list → array + default string items。"""
        schema = _python_type_to_json_schema(list)
        assert schema["type"] == "array"

    def test_optional_type(self) -> None:
        """int | None → integer。"""
        schema = _python_type_to_json_schema(int | None)
        assert schema["type"] == "integer"

    def test_union_multiple_non_none(self) -> None:
        """int | str → string (fallback)。"""
        schema = _python_type_to_json_schema(int | str)
        assert schema["type"] == "string"

    def test_bool_type(self) -> None:
        schema = _python_type_to_json_schema(bool)
        assert schema["type"] == "boolean"

    def test_any_type(self) -> None:
        schema = _python_type_to_json_schema(Any)
        assert schema["type"] == "string"

    def test_empty_annotation(self) -> None:
        """inspect.Parameter.empty → string。"""
        import inspect
        schema = _python_type_to_json_schema(inspect.Parameter.empty)
        assert schema["type"] == "string"

    def test_unknown_type(self) -> None:
        """自定义类 → string fallback。"""

        class CustomType:
            pass

        schema = _python_type_to_json_schema(CustomType)
        assert schema["type"] == "string"

    def test_nested_list(self) -> None:
        """list[list[int]] → array of arrays。"""
        schema = _python_type_to_json_schema(list[list[int]])
        assert schema["type"] == "array"
        assert schema["items"]["type"] == "array"
        assert schema["items"]["items"]["type"] == "integer"


# ═══════════════════════════════════════════════════════════════════
# _generate_parameters_schema 跳过 ctx 参数
# ═══════════════════════════════════════════════════════════════════


class TestGenerateParametersSchema:

    def test_skip_ctx_parameter(self) -> None:
        """ctx / context / tool_context 参数被跳过。"""

        def my_tool(ctx: Any, a: int, context: str = "default") -> str:
            return ""

        schema = _generate_parameters_schema(my_tool)
        assert "ctx" not in schema["properties"]
        # 'context' 是特殊跳过名，不应出现在 properties 中
        assert "context" not in schema["properties"]
        assert "a" in schema["properties"]

    def test_no_type_hints(self) -> None:
        """无类型注解函数也能生成 schema。"""

        def untyped(a, b="x"):
            return a

        schema = _generate_parameters_schema(untyped)
        assert "a" in schema["properties"]
        assert schema["properties"]["a"]["type"] == "string"  # fallback


# ═══════════════════════════════════════════════════════════════════
# FunctionTool.execute — var_keyword (**kwargs) 函数
# ═══════════════════════════════════════════════════════════════════


class TestFunctionToolVarKeyword:

    @pytest.mark.asyncio
    async def test_var_keyword_receives_all_args(self) -> None:
        """带 **kwargs 的函数接收所有参数。"""

        async def flexible_fn(**kwargs: Any) -> str:
            return json.dumps(kwargs, ensure_ascii=False)

        tool = FunctionTool(
            name="flexible",
            description="Flexible tool",
            fn=flexible_fn,
            parameters_schema={"type": "object", "properties": {}},
        )
        result = await tool.execute({"a": 1, "b": "hello", "c": True})
        parsed = json.loads(result)
        assert parsed["a"] == 1
        assert parsed["b"] == "hello"
        assert parsed["c"] is True

    @pytest.mark.asyncio
    async def test_extra_kwargs_passed_to_fn(self) -> None:
        """extra_kwargs 被传递给函数（如 ctx 注入）。"""

        async def tool_with_ctx(ctx: str, query: str) -> str:
            return f"{ctx}: {query}"

        tool = FunctionTool(
            name="with_ctx",
            fn=tool_with_ctx,
            parameters_schema={"type": "object", "properties": {"query": {"type": "string"}}},
        )
        result = await tool.execute({"query": "test"}, ctx="run_context")
        assert result == "run_context: test"


# ═══════════════════════════════════════════════════════════════════
# FunctionTool.to_openai_schema — 空 parameters_schema
# ═══════════════════════════════════════════════════════════════════


class TestFunctionToolOpenAISchema:

    def test_empty_schema(self) -> None:
        """parameters_schema 为空时使用默认 schema。"""
        tool = FunctionTool(name="noop", description="No params")
        schema = tool.to_openai_schema()
        assert schema["function"]["parameters"] == {"type": "object", "properties": {}}


# ═══════════════════════════════════════════════════════════════════
# FunctionTool.condition
# ═══════════════════════════════════════════════════════════════════


class TestFunctionToolCondition:

    def test_condition_field(self) -> None:
        """condition 字段被正确设置。"""

        def always_enabled(ctx: Any) -> bool:
            return True

        tool = FunctionTool(name="cond_tool", condition=always_enabled)
        assert tool.condition is not None
        assert tool.condition(None) is True

    def test_no_condition(self) -> None:
        tool = FunctionTool(name="no_cond")
        assert tool.condition is None


# ═══════════════════════════════════════════════════════════════════
# function_tool 装饰器 — 边界场景
# ═══════════════════════════════════════════════════════════════════


class TestFunctionToolDecoratorEdgeCases:

    def test_no_docstring(self) -> None:
        """无 docstring 时 description 为空。"""

        @function_tool()
        def no_doc(x: int) -> int:
            return x

        assert no_doc.description == ""

    def test_group_and_approval(self) -> None:
        """group 和 approval_required 被正确传递。"""

        @function_tool(group="admin", approval_required=True)
        def admin_tool(x: int) -> int:
            """Admin only."""
            return x

        assert admin_tool.group == "admin"
        assert admin_tool.approval_required is True

    def test_condition_decorator(self) -> None:
        """condition 通过装饰器传递。"""

        def my_cond(ctx: Any) -> bool:
            return False

        @function_tool(condition=my_cond)
        def guarded(x: int) -> str:
            """Guarded tool."""
            return str(x)

        assert guarded.condition is my_cond
