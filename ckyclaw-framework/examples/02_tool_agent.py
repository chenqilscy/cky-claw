"""示例 2: 带工具的 Agent — 展示 @function_tool 的使用。

运行方式：
    export OPENAI_API_KEY=sk-...
    python examples/02_tool_agent.py
"""

from __future__ import annotations

from ckyclaw_framework import Agent, Runner, function_tool


@function_tool
async def calculate(expression: str) -> str:
    """计算数学表达式并返回结果。仅支持基本四则运算。"""
    allowed = set("0123456789+-*/.(). ")
    if not all(c in allowed for c in expression):
        return "错误：仅支持数字和 +-*/ 运算符"
    try:
        result = eval(expression, {"__builtins__": {}}, {})  # noqa: S307
        return str(result)
    except Exception:
        return "计算错误，请检查表达式"


@function_tool
async def get_current_time() -> str:
    """获取当前系统时间。"""
    from datetime import datetime, timezone

    now = datetime.now(tz=timezone.utc)
    return now.strftime("%Y-%m-%d %H:%M:%S UTC")


agent = Agent(
    name="tool-agent",
    instructions="你是一个工具助手。使用 calculate 做数学运算，使用 get_current_time 获取时间。",
    model="gpt-4o-mini",
    tools=[calculate, get_current_time],
)


def main() -> None:
    """运行带工具的 Agent。"""
    result = Runner.run_sync(agent, "现在几点了？另外帮我算一下 (15 + 27) * 3")
    print(f"回复: {result.final_output}")


if __name__ == "__main__":
    main()
