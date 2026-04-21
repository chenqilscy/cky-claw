"""示例 1: 最简 Agent — 定义并运行一个基础 AI 助手。

运行方式：
    export OPENAI_API_KEY=sk-...
    python examples/01_simple_agent.py
"""

from __future__ import annotations

from kasaya import Agent, Runner

agent = Agent(
    name="assistant",
    instructions="你是一个简洁、专业的 AI 助手。用中文回答问题。",
    model="gpt-4o-mini",
)


def main() -> None:
    """同步运行 Agent 并打印结果。"""
    result = Runner.run_sync(agent, "什么是 Agent？用一句话解释。")
    print(f"Agent 回复: {result.final_output}")
    print(f"Token 消耗: {result.token_usage}")


if __name__ == "__main__":
    main()
