"""FunctionTool — @function_tool 装饰器与 FunctionTool 类。"""

from __future__ import annotations

import asyncio
import inspect
import json
import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Callable, get_args, get_origin, get_type_hints

if TYPE_CHECKING:
    from ckyclaw_framework.runner.run_context import RunContext

logger = logging.getLogger(__name__)

# Python 类型 → JSON Schema 类型映射
_TYPE_MAP: dict[type, str] = {
    str: "string",
    int: "integer",
    float: "number",
    bool: "boolean",
    list: "array",
    dict: "object",
}


def _python_type_to_json_schema(annotation: Any) -> dict[str, Any]:
    """将 Python 类型注解转为 JSON Schema 片段。"""
    if annotation is inspect.Parameter.empty or annotation is Any:
        return {"type": "string"}

    origin = get_origin(annotation)
    args = get_args(annotation)

    # list[X]
    if origin is list:
        item_schema = _python_type_to_json_schema(args[0]) if args else {"type": "string"}
        return {"type": "array", "items": item_schema}

    # dict[str, X]
    if origin is dict:
        value_schema = _python_type_to_json_schema(args[1]) if len(args) > 1 else {}
        return {"type": "object", "additionalProperties": value_schema}

    # Optional[X] = Union[X, None]
    if origin is type(int | str):  # types.UnionType for X | Y
        non_none = [a for a in args if a is not type(None)]
        if len(non_none) == 1:
            return _python_type_to_json_schema(non_none[0])
        return {"type": "string"}

    # 基本类型
    json_type = _TYPE_MAP.get(annotation)
    if json_type:
        return {"type": json_type}

    return {"type": "string"}


def _generate_parameters_schema(fn: Callable[..., Any]) -> dict[str, Any]:
    """从函数签名和类型注解自动生成 JSON Schema。"""
    try:
        hints = get_type_hints(fn)
    except Exception:
        hints = {}

    sig = inspect.signature(fn)
    properties: dict[str, Any] = {}
    required: list[str] = []

    for name, param in sig.parameters.items():
        # 跳过 self、ctx（ToolContext）
        if name in ("self", "ctx", "context", "tool_context"):
            continue

        annotation = hints.get(name, param.annotation)
        prop_schema = _python_type_to_json_schema(annotation)

        # 从 docstring 提取参数描述（简单实现：不解析 Google Style，用参数名）
        properties[name] = prop_schema

        if param.default is inspect.Parameter.empty:
            required.append(name)
        else:
            properties[name]["default"] = param.default

    schema: dict[str, Any] = {
        "type": "object",
        "properties": properties,
    }
    if required:
        schema["required"] = required

    return schema


@dataclass
class FunctionTool:
    """Function Tool 定义。"""

    name: str
    """工具名称"""

    description: str = ""
    """工具描述"""

    fn: Callable[..., Any] | None = None
    """底层函数"""

    parameters_schema: dict[str, Any] = field(default_factory=dict)
    """JSON Schema 参数定义"""

    group: str | None = None
    """工具组名"""

    timeout: float | None = None
    """执行超时（秒）"""

    approval_required: bool = False
    """是否需要审批"""

    condition: Callable[[RunContext], bool] | None = None
    """条件启用函数。返回 False 时工具不会暴露给 LLM。None 表示始终启用。"""

    def to_openai_schema(self) -> dict[str, Any]:
        """转为 OpenAI function calling 格式。"""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters_schema or {"type": "object", "properties": {}},
            },
        }

    async def execute(self, arguments: dict[str, Any], **extra_kwargs: Any) -> str:
        """执行工具函数，返回字符串结果。"""
        if self.fn is None:
            return f"Error: Tool '{self.name}' has no implementation."

        try:
            # 过滤函数签名中实际接受的参数
            sig = inspect.signature(self.fn)
            filtered_args: dict[str, Any] = {}
            has_var_keyword = False
            for param_name, param in sig.parameters.items():
                if param.kind == inspect.Parameter.VAR_KEYWORD:
                    has_var_keyword = True
                elif param_name in arguments:
                    filtered_args[param_name] = arguments[param_name]
                elif param_name in extra_kwargs:
                    filtered_args[param_name] = extra_kwargs[param_name]

            # **kwargs 函数接收所有参数（MCP 工具等场景）
            if has_var_keyword:
                for k, v in arguments.items():
                    if k not in filtered_args:
                        filtered_args[k] = v

            # 带超时执行
            fn = self.fn
            if asyncio.iscoroutinefunction(fn):
                coro = fn(**filtered_args)
                if self.timeout:
                    result = await asyncio.wait_for(coro, timeout=self.timeout)
                else:
                    result = await coro
            else:
                loop = asyncio.get_running_loop()
                if self.timeout:
                    result = await asyncio.wait_for(
                        loop.run_in_executor(None, lambda: fn(**filtered_args)),
                        timeout=self.timeout,
                    )
                else:
                    result = await loop.run_in_executor(None, lambda: fn(**filtered_args))

            # 结果转字符串
            if isinstance(result, str):
                return result
            return json.dumps(result, ensure_ascii=False, default=str)

        except asyncio.TimeoutError:
            return f"Error: Tool '{self.name}' timed out after {self.timeout}s."
        except Exception as e:
            logger.exception("Tool '%s' execution failed", self.name)
            return f"Error: Tool '{self.name}' failed: {e}"


def function_tool(
    name: str | None = None,
    description: str | None = None,
    group: str | None = None,
    timeout: float | None = None,
    approval_required: bool = False,
    condition: Callable[[RunContext], bool] | None = None,
) -> Callable[..., Any]:
    """装饰器：将 Python 函数注册为 Function Tool。自动生成 JSON Schema。"""

    def decorator(fn: Callable[..., Any]) -> FunctionTool:
        tool_name = name or fn.__name__
        tool_desc = description or (fn.__doc__ or "").split("\n")[0].strip()
        params_schema = _generate_parameters_schema(fn)

        return FunctionTool(
            name=tool_name,
            description=tool_desc,
            fn=fn,
            parameters_schema=params_schema,
            group=group,
            timeout=timeout,
            approval_required=approval_required,
            condition=condition,
        )

    return decorator
