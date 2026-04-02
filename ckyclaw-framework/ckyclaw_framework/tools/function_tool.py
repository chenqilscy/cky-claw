"""FunctionTool — @function_tool 装饰器与 FunctionTool 类。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable


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


def function_tool(
    name: str | None = None,
    description: str | None = None,
    group: str | None = None,
    timeout: float | None = None,
) -> Callable:
    """装饰器：将 Python 函数注册为 Function Tool。"""

    def decorator(fn: Callable) -> FunctionTool:
        tool_name = name or fn.__name__
        tool_desc = description or (fn.__doc__ or "").split("\n")[0].strip()
        return FunctionTool(
            name=tool_name,
            description=tool_desc,
            fn=fn,
            group=group,
            timeout=timeout,
        )

    return decorator
