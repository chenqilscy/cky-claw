"""Kasaya Framework — OpenAI Agents SDK 兼容层。

提供适配器，将 OpenAI Agents SDK 风格的 Agent 定义
无缝转换为 Kasaya Framework 原生对象并运行。

用法示例::

    from kasaya.compat import (
        from_openai_agent,
        from_openai_tool,
        from_openai_handoff,
        from_openai_guardrail,
        SdkAgentAdapter,
    )

    # 1. 直接转换 SDK Agent dict/对象
    kasaya_agent = from_openai_agent(sdk_agent_dict)

    # 2. 使用适配器类批量转换
    adapter = SdkAgentAdapter()
    agent = adapter.convert_agent(sdk_agent_dict)
    result = await adapter.run(agent, "Hello")
"""

from __future__ import annotations

from kasaya.compat.adapter import (
    SdkAgentAdapter,
    from_openai_agent,
    from_openai_guardrail,
    from_openai_handoff,
    from_openai_tool,
)

__all__ = [
    "SdkAgentAdapter",
    "from_openai_agent",
    "from_openai_guardrail",
    "from_openai_handoff",
    "from_openai_tool",
]
